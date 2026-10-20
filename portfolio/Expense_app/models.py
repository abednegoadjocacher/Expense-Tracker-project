from datetime import date
from decimal import Decimal
from zoneinfo import available_timezones

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import F, Q
from django.db.models.functions import Lower
from django.urls import reverse
from django.utils import timezone

MONEY = {"max_digits": 12, "decimal_places": 2}
POSITIVE_AMOUNT = [MinValueValidator(Decimal("0.01"))]

CURRENCIES = {
    "USD": ("US Dollar", "$"),
    "EUR": ("Euro", "€"),
    "GBP": ("British Pound", "£"),
    "NGN": ("Nigerian Naira", "₦"),
    "GHS": ("Ghanaian Cedi", "₵"),
    "KES": ("Kenyan Shilling", "KSh "),
    "ZAR": ("South African Rand", "R "),
    "INR": ("Indian Rupee", "₹"),
    "CAD": ("Canadian Dollar", "CA$"),
    "AUD": ("Australian Dollar", "A$"),
    "JPY": ("Japanese Yen", "¥"),
    "CNY": ("Chinese Yuan", "CN¥"),
}
CURRENCY_CHOICES = [(code, f"{code} — {name}") for code, (name, _) in CURRENCIES.items()]
TIMEZONE_CHOICES = [(tz, tz) for tz in sorted(available_timezones())]

CATEGORY_COLORS = [
    ("#ef4444", "Red"),
    ("#f97316", "Orange"),
    ("#f59e0b", "Amber"),
    ("#84cc16", "Lime"),
    ("#22c55e", "Green"),
    ("#14b8a6", "Teal"),
    ("#06b6d4", "Cyan"),
    ("#3b82f6", "Blue"),
    ("#6366f1", "Indigo"),
    ("#a855f7", "Purple"),
    ("#ec4899", "Pink"),
    ("#64748b", "Slate"),
]

# Created automatically for every new user so they can start logging right away.
DEFAULT_CATEGORIES = [
    ("Food & Groceries", "#22c55e"),
    ("Transport", "#3b82f6"),
    ("Housing & Rent", "#6366f1"),
    ("Utilities & Bills", "#f59e0b"),
    ("Health", "#ef4444"),
    ("Entertainment", "#ec4899"),
    ("Shopping", "#a855f7"),
    ("Other", "#64748b"),
]


class Profile(models.Model):
    """Per-user preferences, overall budget and alert configuration."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="USD")
    timezone = models.CharField(max_length=64, choices=TIMEZONE_CHOICES, default="UTC")
    monthly_budget = models.DecimalField(
        **MONEY, null=True, blank=True, validators=POSITIVE_AMOUNT,
        help_text="Optional overall spending limit per month.",
    )
    alert_threshold = models.PositiveSmallIntegerField(
        default=80, validators=[MinValueValidator(10), MaxValueValidator(100)],
        help_text="Warn me when I've used this % of a budget.",
    )
    spike_alerts = models.BooleanField(
        default=True, help_text="Alert me when a category is much higher than my recent average.",
    )
    email_alerts = models.BooleanField(default=False, help_text="Also send alerts to my email address.")

    def __str__(self):
        return f"Profile of {self.user}"

    @property
    def currency_symbol(self):
        return CURRENCIES.get(self.currency, ("", "$"))[1]


class Category(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=60)
    color = models.CharField(max_length=7, choices=CATEGORY_COLORS, default="#3b82f6")
    monthly_budget = models.DecimalField(
        **MONEY, null=True, blank=True, validators=POSITIVE_AMOUNT,
        help_text="Planned spending limit per month (optional).",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(Lower("name"), F("user"), name="unique_category_name_per_user"),
        ]

    def __str__(self):
        return self.name


class Expense(models.Model):
    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Cash"
        CARD = "card", "Card"
        TRANSFER = "transfer", "Bank transfer"
        MOBILE = "mobile", "Mobile money / wallet"
        OTHER = "other", "Other"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="expenses")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="expenses")
    amount = models.DecimalField(**MONEY, validators=POSITIVE_AMOUNT)
    date = models.DateField(default=timezone.localdate)
    description = models.CharField(max_length=200)
    payment_method = models.CharField(max_length=10, choices=PaymentMethod.choices, default=PaymentMethod.CARD)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        indexes = [
            models.Index(fields=["user", "date"]),
            models.Index(fields=["user", "category", "date"]),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="expense_amount_positive"),
        ]

    def __str__(self):
        return f"{self.description} ({self.amount})"

    def get_absolute_url(self):
        return reverse("expense_edit", args=[self.pk])


class PlannedExpense(models.Model):
    """An upcoming or recurring expense the user plans for (rent, subscriptions…)."""

    class Recurrence(models.TextChoices):
        NONE = "none", "One-off"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"
        YEARLY = "yearly", "Yearly"

    STEP = {
        Recurrence.WEEKLY: relativedelta(weeks=1),
        Recurrence.MONTHLY: relativedelta(months=1),
        Recurrence.YEARLY: relativedelta(years=1),
    }

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="planned_expenses")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="planned_expenses")
    title = models.CharField(max_length=120)
    amount = models.DecimalField(**MONEY, validators=POSITIVE_AMOUNT)
    due_date = models.DateField()
    recurrence = models.CharField(max_length=10, choices=Recurrence.choices, default=Recurrence.NONE)
    notes = models.TextField(blank=True)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["is_completed", "due_date"]
        indexes = [models.Index(fields=["user", "is_completed", "due_date"])]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="planned_amount_positive"),
        ]

    def __str__(self):
        return f"{self.title} due {self.due_date}"

    @property
    def is_overdue(self):
        return not self.is_completed and self.due_date < timezone.localdate()

    @transaction.atomic
    def mark_paid(self, paid_on: date | None = None) -> Expense:
        """Record this plan as an actual expense and roll recurring plans forward."""
        expense = Expense.objects.create(
            user=self.user,
            category=self.category,
            amount=self.amount,
            date=paid_on or timezone.localdate(),
            description=self.title,
            notes=self.notes,
        )
        if self.recurrence == self.Recurrence.NONE:
            self.is_completed = True
        else:
            self.due_date = self.due_date + self.STEP[self.recurrence]
        self.save(update_fields=["is_completed", "due_date"])
        return expense


class Notification(models.Model):
    class Level(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        DANGER = "danger", "Alert"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    level = models.CharField(max_length=10, choices=Level.choices, default=Level.INFO)
    title = models.CharField(max_length=150)
    message = models.TextField()
    # Prevents the same alert (e.g. "Food over budget in 2026-10") being sent twice.
    dedupe_key = models.CharField(max_length=120, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "is_read"])]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "dedupe_key"], condition=~Q(dedupe_key=""), name="unique_notification_dedupe_key",
            ),
        ]

    def __str__(self):
        return self.title
