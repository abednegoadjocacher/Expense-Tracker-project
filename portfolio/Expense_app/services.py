"""Spending analytics and the alert engine.

Everything that computes totals, breakdowns or "higher than usual" signals
lives here so views stay thin and logic is easy to test.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce, TruncMonth
from django.template.loader import render_to_string
from django.utils import timezone

from .models import Category, Expense, Notification, PlannedExpense, Profile

logger = logging.getLogger(__name__)

ZERO = Decimal("0.00")
# A category is "higher than usual" when this month exceeds its recent average by 50%.
SPIKE_MULTIPLIER = Decimal("1.5")
SPIKE_LOOKBACK_MONTHS = 3


def money_sum(expression="amount", **kwargs):
    return Coalesce(
        Sum(expression, **kwargs), Value(ZERO), output_field=DecimalField(max_digits=14, decimal_places=2)
    )


def month_bounds(day: date) -> tuple[date, date]:
    """Return (first day of month, first day of next month) — end is exclusive."""
    start = day.replace(day=1)
    return start, start + relativedelta(months=1)


def get_profile(user) -> Profile:
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


def pct(part: Decimal, whole: Decimal | None) -> float:
    if not whole:
        return 0.0
    return float(part / whole * 100)


def total_spent(user, start: date | None = None, end: date | None = None) -> Decimal:
    qs = Expense.objects.filter(user=user)
    if start:
        qs = qs.filter(date__gte=start)
    if end:
        qs = qs.filter(date__lt=end)
    return qs.aggregate(total=money_sum())["total"]


# --------------------------------------------------------------------------
# Category breakdown
# --------------------------------------------------------------------------

@dataclass
class CategoryStat:
    category: Category
    total: Decimal
    count: int
    share: float = 0.0  # % of the period's total spend
    budget: Decimal | None = None
    budget_pct: float = 0.0
    average: Decimal | None = None  # recent monthly average (for spike detection)
    is_spike: bool = False
    status: str = "none"  # none | ok | warning | over

    @property
    def remaining(self):
        return None if self.budget is None else self.budget - self.total

    @property
    def is_flagged(self):
        return self.status in {"warning", "over"} or self.is_spike


def category_breakdown(user, start: date | None = None, end: date | None = None, *, include_empty=True):
    """Totals per category for a period (None/None = all time), largest first."""
    date_filter = Q()
    if start:
        date_filter &= Q(expenses__date__gte=start)
    if end:
        date_filter &= Q(expenses__date__lt=end)

    rows = (
        Category.objects.filter(user=user)
        .annotate(
            total=money_sum("expenses__amount", filter=date_filter),
            count=Count("expenses", filter=date_filter),
        )
        .order_by("-total", "name")
    )
    stats = [CategoryStat(category=c, total=c.total, count=c.count) for c in rows]
    if not include_empty:
        stats = [s for s in stats if s.count]
    grand_total = sum((s.total for s in stats), ZERO)
    for s in stats:
        s.share = pct(s.total, grand_total)
    return stats, grand_total


def recent_monthly_averages(user, month_start: date, months: int = SPIKE_LOOKBACK_MONTHS) -> dict[int, Decimal]:
    """Average monthly spend per category over the `months` before `month_start`.

    Only months in which the category had spending are averaged, so a new
    category isn't compared against months before it existed.
    """
    window_start = month_start - relativedelta(months=months)
    rows = (
        Expense.objects.filter(user=user, date__gte=window_start, date__lt=month_start)
        .annotate(month=TruncMonth("date"))
        .values("category_id", "month")
        .annotate(total=Sum("amount"))
    )
    buckets: dict[int, list[Decimal]] = {}
    for row in rows:
        buckets.setdefault(row["category_id"], []).append(row["total"])
    return {cid: sum(vals, ZERO) / len(vals) for cid, vals in buckets.items()}


def is_spike(current: Decimal, average: Decimal | None) -> bool:
    return bool(average) and current > 0 and current > average * SPIKE_MULTIPLIER


def budget_status(spent: Decimal, budget: Decimal | None, threshold: int) -> str:
    if not budget:
        return "none"
    used = pct(spent, budget)
    if used >= 100:
        return "over"
    if used >= threshold:
        return "warning"
    return "ok"


def month_category_stats(user, day: date | None = None):
    """Breakdown for the month containing `day`, enriched with budget and spike flags."""
    day = day or timezone.localdate()
    start, end = month_bounds(day)
    profile = get_profile(user)
    stats, total = category_breakdown(user, start, end)
    averages = recent_monthly_averages(user, start)
    for s in stats:
        s.budget = s.category.monthly_budget
        s.budget_pct = pct(s.total, s.budget)
        s.status = budget_status(s.total, s.budget, profile.alert_threshold)
        s.average = averages.get(s.category.pk)
        s.is_spike = is_spike(s.total, s.average)
    return stats, total


# --------------------------------------------------------------------------
# Trends & charts
# --------------------------------------------------------------------------

def daily_series(user, days: int = 30):
    """Spend per day for the last `days` days (zero-filled), oldest first."""
    today = timezone.localdate()
    start = today - timedelta(days=days - 1)
    rows = (
        Expense.objects.filter(user=user, date__gte=start, date__lte=today)
        .values("date")
        .annotate(total=Sum("amount"))
    )
    by_day = {r["date"]: r["total"] for r in rows}
    series = [{"date": start + timedelta(days=i), "total": by_day.get(start + timedelta(days=i), ZERO)}
              for i in range(days)]
    return _with_heights(series)


def monthly_series(user, months: int = 12):
    """Spend per month for the last `months` months (zero-filled), oldest first."""
    this_month = timezone.localdate().replace(day=1)
    start = this_month - relativedelta(months=months - 1)
    rows = (
        Expense.objects.filter(user=user, date__gte=start)
        .annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(total=Sum("amount"))
    )
    by_month = {}
    for r in rows:
        month = r["month"]
        month = month.date() if hasattr(month, "date") else month
        by_month[month] = r["total"]
    series = []
    for i in range(months):
        m = start + relativedelta(months=i)
        series.append({"date": m, "total": by_month.get(m, ZERO)})
    return _with_heights(series)


def _with_heights(series):
    peak = max((p["total"] for p in series), default=ZERO)
    for p in series:
        p["height"] = round(pct(p["total"], peak), 1) if peak else 0
    return series


def donut_gradient(stats) -> str:
    """Build a CSS conic-gradient for a category share donut chart."""
    segments, cursor = [], 0.0
    for s in stats:
        if s.share <= 0:
            continue
        end = min(cursor + s.share, 100.0)
        segments.append(f"{s.category.color} {cursor:.2f}% {end:.2f}%")
        cursor = end
    if not segments:
        return "conic-gradient(var(--color-base-300) 0% 100%)"
    return f"conic-gradient({', '.join(segments)})"


def payment_method_breakdown(user, start=None, end=None):
    qs = Expense.objects.filter(user=user)
    if start:
        qs = qs.filter(date__gte=start)
    if end:
        qs = qs.filter(date__lt=end)
    labels = dict(Expense.PaymentMethod.choices)
    rows = qs.values("payment_method").annotate(total=Sum("amount"), count=Count("id")).order_by("-total")
    grand = sum((r["total"] for r in rows), ZERO)
    return [
        {"label": labels.get(r["payment_method"], r["payment_method"]), "total": r["total"],
         "count": r["count"], "share": pct(r["total"], grand)}
        for r in rows
    ]


def planned_remaining_this_month(user) -> Decimal:
    today = timezone.localdate()
    _, end = month_bounds(today)
    return (
        PlannedExpense.objects.filter(user=user, is_completed=False, due_date__lt=end)
        .aggregate(total=money_sum())["total"]
    )


# --------------------------------------------------------------------------
# Alert engine
# --------------------------------------------------------------------------

@dataclass
class AlertSpec:
    key: str
    level: str
    title: str
    message: str
    category: Category | None = None
    extra: dict = field(default_factory=dict)


def format_money(amount: Decimal, profile: Profile) -> str:
    places = 0 if profile.currency == "JPY" else 2
    return f"{profile.currency_symbol}{amount:,.{places}f}"


def build_alerts(user, day: date | None = None, categories=None) -> list[AlertSpec]:
    """Work out which alerts apply for the month containing `day`."""
    day = day or timezone.localdate()
    start, end = month_bounds(day)
    month_key, month_label = start.strftime("%Y-%m"), start.strftime("%B %Y")
    profile = get_profile(user)
    threshold = profile.alert_threshold
    alerts: list[AlertSpec] = []

    stats, month_total = month_category_stats(user, day)
    if categories is not None:
        wanted = {c.pk for c in categories}
        stats = [s for s in stats if s.category.pk in wanted]

    for s in stats:
        name, spent = s.category.name, format_money(s.total, profile)
        if s.status == "over":
            alerts.append(AlertSpec(
                key=f"budget-over:{s.category.pk}:{month_key}", level=Notification.Level.DANGER,
                title=f"{name} is over budget",
                message=(f"You've spent {spent} on {name} in {month_label} — {s.budget_pct:.0f}% of your "
                         f"{format_money(s.budget, profile)} budget."),
                category=s.category,
            ))
        elif s.status == "warning":
            alerts.append(AlertSpec(
                key=f"budget-warn:{s.category.pk}:{month_key}", level=Notification.Level.WARNING,
                title=f"{name} is at {s.budget_pct:.0f}% of budget",
                message=(f"You've spent {spent} of your {format_money(s.budget, profile)} {name} budget "
                         f"for {month_label}. {format_money(s.remaining, profile)} left."),
                category=s.category,
            ))
        if profile.spike_alerts and s.is_spike:
            alerts.append(AlertSpec(
                key=f"spike:{s.category.pk}:{month_key}", level=Notification.Level.WARNING,
                title=f"Higher than usual spending on {name}",
                message=(f"{name} spending this month is {spent}, compared with your recent average of "
                         f"{format_money(s.average, profile)} per month "
                         f"({pct(s.total, s.average) - 100:.0f}% higher)."),
                category=s.category,
            ))

    if profile.monthly_budget:
        status = budget_status(month_total, profile.monthly_budget, threshold)
        used = pct(month_total, profile.monthly_budget)
        if status == "over":
            alerts.append(AlertSpec(
                key=f"overall-over:{month_key}", level=Notification.Level.DANGER,
                title="You've exceeded your monthly budget",
                message=(f"Total spending for {month_label} is {format_money(month_total, profile)} — "
                         f"{used:.0f}% of your {format_money(profile.monthly_budget, profile)} budget."),
            ))
        elif status == "warning":
            alerts.append(AlertSpec(
                key=f"overall-warn:{month_key}", level=Notification.Level.WARNING,
                title=f"You've used {used:.0f}% of your monthly budget",
                message=(f"Total spending for {month_label} is {format_money(month_total, profile)} of "
                         f"{format_money(profile.monthly_budget, profile)}."),
            ))
    return alerts


def evaluate_alerts(user, day: date | None = None, categories=None) -> list[Notification]:
    """Create (deduplicated) notifications for any new alerts. Returns the new ones.

    Alerts are only raised for the current month — back-dating an old expense
    shouldn't produce a stale "over budget in March" notification.
    """
    today = timezone.localdate()
    day = day or today
    if month_bounds(day) != month_bounds(today):
        return []

    created = []
    for spec in build_alerts(user, day, categories):
        notification, was_created = Notification.objects.get_or_create(
            user=user, dedupe_key=spec.key,
            defaults={"level": spec.level, "title": spec.title, "message": spec.message, "category": spec.category},
        )
        if was_created:
            created.append(notification)

    if created and get_profile(user).email_alerts and user.email:
        ids = [n.pk for n in created]
        transaction.on_commit(lambda: send_alert_email(user, ids))
    return created


def send_alert_email(user, notification_ids):
    notifications = list(Notification.objects.filter(pk__in=notification_ids))
    if not notifications:
        return
    context = {"user": user, "notifications": notifications}
    subject = notifications[0].title if len(notifications) == 1 else f"{len(notifications)} new spending alerts"
    try:
        email = EmailMultiAlternatives(
            subject=f"[Expense Tracker] {subject}",
            body=render_to_string("Expense_app/emails/alerts.txt", context),
            to=[user.email],
        )
        email.attach_alternative(render_to_string("Expense_app/emails/alerts.html", context), "text/html")
        email.send()
    except Exception:  # never let email problems break saving an expense
        logger.exception("Failed to send alert email to user %s", user.pk)
