import csv
from datetime import date

from dateutil.relativedelta import relativedelta
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_not_required
from django.core.paginator import Paginator
from django.db import connection, transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import services
from .forms import (
    CategoryDeleteForm,
    CategoryForm,
    ExpenseFilterForm,
    ExpenseForm,
    PlannedExpenseForm,
    ProfileForm,
    QuickExpenseForm,
    SignUpForm,
)
from .models import Category, Expense, Notification, PlannedExpense


def _next_url(request, default):
    """Return a safe same-site `next` URL from the POST body, or the named default."""
    target = request.POST.get("next") or request.GET.get("next")
    if target and url_has_allowed_host_and_scheme(target, {request.get_host()}, require_https=request.is_secure()):
        return target
    return default


# --------------------------------------------------------------------------
# Public pages
# --------------------------------------------------------------------------

@login_not_required
def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "Expense_app/home.html")


@login_not_required
@require_http_methods(["GET", "POST"])
def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, "Welcome! We've set up some starter categories — set budgets to get alerts.")
        return redirect("dashboard")
    return render(request, "registration/signup.html", {"form": form})


@login_not_required
@require_GET
def healthz(request):
    """Liveness/readiness probe for load balancers and uptime monitors."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return JsonResponse({"status": "error", "database": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------

def dashboard(request):
    user = request.user
    today = timezone.localdate()
    month_start, month_end = services.month_bounds(today)
    last_month_start = month_start - relativedelta(months=1)
    profile = services.get_profile(user)

    month_stats, month_total = services.month_category_stats(user, today)
    all_time_stats, all_time_total = services.category_breakdown(user)
    last_month_total = services.total_spent(user, last_month_start, month_start)
    planned_remaining = services.planned_remaining_this_month(user)

    context = {
        "today": today,
        "profile": profile,
        "all_time_total": all_time_total,
        "all_time_stats": [s for s in all_time_stats if s.count],
        "month_total": month_total,
        "month_stats": month_stats,
        "month_spent_stats": [s for s in month_stats if s.count],
        "flagged_stats": [s for s in month_stats if s.is_flagged],
        "today_total": services.total_spent(user, today, today + relativedelta(days=1)),
        "last_month_total": last_month_total,
        "month_change_pct": (services.pct(month_total, last_month_total) - 100) if last_month_total else None,
        "budget_pct": services.pct(month_total, profile.monthly_budget),
        "budget_status": services.budget_status(month_total, profile.monthly_budget, profile.alert_threshold),
        "planned_remaining": planned_remaining,
        "projected_total": month_total + planned_remaining,
        "daily": services.daily_series(user, 30),
        "donut": services.donut_gradient([s for s in month_stats if s.count]),
        "recent_expenses": user.expenses.select_related("category")[:8],
        "upcoming_plans": user.planned_expenses.filter(
            is_completed=False, due_date__lte=today + relativedelta(days=30)
        ).select_related("category")[:6],
        "quick_form": QuickExpenseForm(user=user, initial={"date": today}),
        "has_categories": user.categories.exists(),
    }
    return render(request, "Expense_app/dashboard.html", context)


# --------------------------------------------------------------------------
# Expenses
# --------------------------------------------------------------------------

def _filtered_expenses(request):
    form = ExpenseFilterForm(request.GET or None, user=request.user)
    qs = form.filter(Expense.objects.filter(user=request.user).select_related("category"))
    return form, qs


def expense_list(request):
    form, qs = _filtered_expenses(request)
    totals = qs.aggregate(total=services.money_sum())
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(request, "Expense_app/expenses/list.html", {
        "filter_form": form,
        "page_obj": page,
        "filtered_total": totals["total"],
        "filtered_count": page.paginator.count,
        "is_filtered": bool(request.GET.dict().keys() - {"page"}),
    })


def expense_export(request):
    _, qs = _filtered_expenses(request)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="expenses-{timezone.localdate():%Y%m%d}.csv"'
    writer = csv.writer(response)
    writer.writerow(["Date", "Description", "Category", "Amount", "Payment method", "Notes"])
    for e in qs.iterator(chunk_size=500):
        writer.writerow([e.date.isoformat(), _csv_safe(e.description), e.category.name, e.amount,
                         e.get_payment_method_display(), _csv_safe(e.notes)])
    return response


def _csv_safe(value: str) -> str:
    """Neutralise spreadsheet formula injection (=, +, -, @ prefixes)."""
    return f"'{value}" if value and value[0] in "=+-@\t\r" else value


@require_http_methods(["GET", "POST"])
def expense_create(request):
    if not request.user.categories.exists():
        messages.info(request, "Create a category first, then add expenses to it.")
        return redirect("category_create")
    form = ExpenseForm(request.POST or None, user=request.user, initial={"date": timezone.localdate()})
    if request.method == "POST" and form.is_valid():
        return _save_expense(request, form)
    return render(request, "Expense_app/expenses/form.html", {"form": form, "title": "Add expense"})


@require_POST
def expense_quick_add(request):
    form = QuickExpenseForm(request.POST, user=request.user)
    if form.is_valid():
        return _save_expense(request, form, redirect_to="dashboard")
    for field, errors in form.errors.items():
        label = form.fields[field].label if field in form.fields else ""
        messages.error(request, f"{label}: {' '.join(errors)}" if label else " ".join(errors))
    return redirect("dashboard")


@require_http_methods(["GET", "POST"])
def expense_update(request, pk):
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    form = ExpenseForm(request.POST or None, instance=expense, user=request.user)
    if request.method == "POST" and form.is_valid():
        return _save_expense(request, form, created=False)
    return render(request, "Expense_app/expenses/form.html", {"form": form, "title": "Edit expense",
                                                              "expense": expense})


def _save_expense(request, form, created=True, redirect_to=None):
    before = set(request.user.notifications.values_list("pk", flat=True))
    expense = form.save(commit=False)
    expense.user = request.user
    expense.save()
    verb = "Added" if created else "Updated"
    messages.success(request, f"{verb} “{expense.description}”.")
    for n in request.user.notifications.exclude(pk__in=before):
        messages.warning(request, f"{n.title}. {n.message}")
    return redirect(redirect_to or _next_url(request, "expense_list"))


@require_http_methods(["GET", "POST"])
def expense_delete(request, pk):
    expense = get_object_or_404(Expense, pk=pk, user=request.user)
    if request.method == "POST":
        expense.delete()
        messages.success(request, f"Deleted “{expense.description}”.")
        return redirect("expense_list")
    return render(request, "Expense_app/confirm_delete.html", {
        "object": expense, "kind": "expense", "cancel_url": "expense_list",
    })


# --------------------------------------------------------------------------
# Categories
# --------------------------------------------------------------------------

def category_list(request):
    today = timezone.localdate()
    month_stats, month_total = services.month_category_stats(request.user, today)
    all_time = {s.category.pk: s for s in services.category_breakdown(request.user)[0]}
    rows = [{"month": s, "all_time": all_time.get(s.category.pk)} for s in month_stats]
    rows.sort(key=lambda r: r["month"].category.name.lower())
    return render(request, "Expense_app/categories/list.html", {
        "rows": rows, "month_total": month_total, "today": today,
        "all_time_total": sum((r["all_time"].total for r in rows if r["all_time"]), services.ZERO),
    })


@require_http_methods(["GET", "POST"])
def category_create(request):
    form = CategoryForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        category = form.save(commit=False)
        category.user = request.user
        category.save()
        messages.success(request, f"Category “{category.name}” created.")
        return redirect("category_list")
    return render(request, "Expense_app/categories/form.html", {"form": form, "title": "New category"})


@require_http_methods(["GET", "POST"])
def category_update(request, pk):
    category = get_object_or_404(Category, pk=pk, user=request.user)
    form = CategoryForm(request.POST or None, instance=category, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        # A lower budget may mean this category is now over its limit.
        services.evaluate_alerts(request.user, categories=[category])
        messages.success(request, f"Category “{category.name}” updated.")
        return redirect("category_list")
    return render(request, "Expense_app/categories/form.html", {"form": form, "title": "Edit category",
                                                                "category": category})


@require_http_methods(["GET", "POST"])
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk, user=request.user)
    form = CategoryDeleteForm(request.POST or None, category=category)
    if request.method == "POST" and form.is_valid():
        target = form.cleaned_data.get("move_to")
        with transaction.atomic():
            if target:
                category.expenses.update(category=target)
                category.planned_expenses.update(category=target)
            category.delete()
        messages.success(request, f"Category “{category.name}” deleted.")
        return redirect("category_list")
    return render(request, "Expense_app/categories/delete.html", {
        "category": category, "form": form,
        "expense_count": category.expenses.count(), "plan_count": category.planned_expenses.count(),
    })


# --------------------------------------------------------------------------
# Planned expenses
# --------------------------------------------------------------------------

def plan_list(request):
    plans = request.user.planned_expenses.select_related("category")
    active = plans.filter(is_completed=False)
    today = timezone.localdate()
    _, month_end = services.month_bounds(today)
    return render(request, "Expense_app/plans/list.html", {
        "active_plans": active,
        "completed_plans": plans.filter(is_completed=True).order_by("-due_date")[:20],
        "due_this_month": active.filter(due_date__lt=month_end).aggregate(t=services.money_sum())["t"],
        "overdue_count": active.filter(due_date__lt=today).count(),
        "today": today,
    })


@require_http_methods(["GET", "POST"])
def plan_create(request):
    if not request.user.categories.exists():
        messages.info(request, "Create a category first.")
        return redirect("category_create")
    form = PlannedExpenseForm(request.POST or None, user=request.user,
                              initial={"due_date": timezone.localdate()})
    if request.method == "POST" and form.is_valid():
        plan = form.save(commit=False)
        plan.user = request.user
        plan.save()
        messages.success(request, f"Planned “{plan.title}”.")
        return redirect("plan_list")
    return render(request, "Expense_app/plans/form.html", {"form": form, "title": "Plan an expense"})


@require_http_methods(["GET", "POST"])
def plan_update(request, pk):
    plan = get_object_or_404(PlannedExpense, pk=pk, user=request.user)
    form = PlannedExpenseForm(request.POST or None, instance=plan, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Updated “{plan.title}”.")
        return redirect("plan_list")
    return render(request, "Expense_app/plans/form.html", {"form": form, "title": "Edit plan", "plan": plan})


@require_http_methods(["GET", "POST"])
def plan_delete(request, pk):
    plan = get_object_or_404(PlannedExpense, pk=pk, user=request.user)
    if request.method == "POST":
        plan.delete()
        messages.success(request, f"Deleted plan “{plan.title}”.")
        return redirect("plan_list")
    return render(request, "Expense_app/confirm_delete.html", {
        "object": plan, "kind": "plan", "cancel_url": "plan_list",
    })


@require_POST
def plan_mark_paid(request, pk):
    plan = get_object_or_404(PlannedExpense, pk=pk, user=request.user, is_completed=False)
    before = set(request.user.notifications.values_list("pk", flat=True))
    plan.mark_paid()
    messages.success(request, f"Recorded “{plan.title}” as an expense.")
    for n in request.user.notifications.exclude(pk__in=before):
        messages.warning(request, f"{n.title}. {n.message}")
    return redirect(_next_url(request, "plan_list"))


# --------------------------------------------------------------------------
# Reports
# --------------------------------------------------------------------------

PERIODS = {
    "this_month": "This month",
    "last_month": "Last month",
    "last_3_months": "Last 3 months",
    "this_year": "This year",
    "all": "All time",
    "custom": "Custom range",
}


def _resolve_period(request):
    today = timezone.localdate()
    period = request.GET.get("period", "this_month")
    month_start, month_end = services.month_bounds(today)
    start = end = None  # end is exclusive
    if period == "this_month":
        start, end = month_start, month_end
    elif period == "last_month":
        start, end = month_start - relativedelta(months=1), month_start
    elif period == "last_3_months":
        start, end = month_start - relativedelta(months=2), month_end
    elif period == "this_year":
        start, end = date(today.year, 1, 1), date(today.year + 1, 1, 1)
    elif period == "custom":
        try:
            start = date.fromisoformat(request.GET.get("start", ""))
            end = date.fromisoformat(request.GET.get("end", "")) + relativedelta(days=1)
            if end <= start:
                raise ValueError
        except ValueError:
            messages.error(request, "Pick a valid start and end date.")
            period, start, end = "this_month", month_start, month_end
    else:
        period = "all"
    return period, start, end


def reports(request):
    user = request.user
    period, start, end = _resolve_period(request)
    stats, total = services.category_breakdown(user, start, end, include_empty=False)
    count = sum(s.count for s in stats)
    days = (end - start).days if start and end else None
    return render(request, "Expense_app/reports.html", {
        "periods": PERIODS,
        "period": period,
        "period_label": PERIODS[period],
        "start": start,
        "end_inclusive": end - relativedelta(days=1) if end else None,
        "stats": stats,
        "total": total,
        "count": count,
        "average_expense": total / count if count else None,
        "daily_average": total / days if days else None,
        "donut": services.donut_gradient(stats),
        "monthly": services.monthly_series(user, 12),
        "methods": services.payment_method_breakdown(user, start, end),
    })


# --------------------------------------------------------------------------
# Notifications & settings
# --------------------------------------------------------------------------

def notification_list(request):
    notifications = request.user.notifications.select_related("category")
    page = Paginator(notifications, 20).get_page(request.GET.get("page"))
    return render(request, "Expense_app/notifications.html", {"page_obj": page})


@require_POST
def notification_mark_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.is_read = True
    notification.save(update_fields=["is_read"])
    return redirect(_next_url(request, "notification_list"))


@require_POST
def notification_mark_all_read(request):
    updated = request.user.notifications.filter(is_read=False).update(is_read=True)
    if updated:
        messages.success(request, f"Marked {updated} notification{'s' if updated != 1 else ''} as read.")
    return redirect(_next_url(request, "notification_list"))


@require_http_methods(["GET", "POST"])
def settings_view(request):
    profile = services.get_profile(request.user)
    form = ProfileForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        form.save()
        services.evaluate_alerts(request.user)
        messages.success(request, "Settings saved.")
        return redirect("settings")
    return render(request, "Expense_app/settings.html", {"form": form})
