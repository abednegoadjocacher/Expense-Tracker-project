from datetime import timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import services
from .models import DEFAULT_CATEGORIES, Category, Expense, Notification, PlannedExpense

User = get_user_model()


class ExpenseTrackerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", email="alice@example.com", password="StrongPassword123!"
        )
        self.client.force_login(self.user)
        self.food = Category.objects.get(user=self.user, name="Food & Groceries")
        self.transport = Category.objects.get(user=self.user, name="Transport")

    def test_new_user_receives_profile_and_default_categories(self):
        self.assertTrue(hasattr(self.user, "profile"))
        self.assertEqual(self.user.categories.count(), len(DEFAULT_CATEGORIES))

    def test_total_and_category_breakdown_all_time_and_monthly(self):
        today = timezone.localdate()
        two_months_ago = today.replace(day=1) - relativedelta(months=2)

        Expense.objects.create(
            user=self.user, category=self.food, amount=Decimal("45.50"),
            date=today, description="Supermarket",
        )
        Expense.objects.create(
            user=self.user, category=self.transport, amount=Decimal("14.50"),
            date=today, description="Bus pass",
        )
        Expense.objects.create(
            user=self.user, category=self.food, amount=Decimal("100.00"),
            date=two_months_ago, description="Old bulk groceries",
        )

        # All-time total & per-category breakdown
        self.assertEqual(services.total_spent(self.user), Decimal("160.00"))
        all_stats, all_total = services.category_breakdown(self.user, include_empty=False)
        self.assertEqual(all_total, Decimal("160.00"))
        by_name = {s.category.name: s for s in all_stats}
        self.assertEqual(by_name["Food & Groceries"].total, Decimal("145.50"))
        self.assertEqual(by_name["Transport"].total, Decimal("14.50"))

        # Current month breakdown
        month_stats, month_total = services.month_category_stats(self.user, today)
        self.assertEqual(month_total, Decimal("60.00"))
        month_by_name = {s.category.name: s for s in month_stats}
        self.assertEqual(month_by_name["Food & Groceries"].total, Decimal("45.50"))
        self.assertEqual(month_by_name["Transport"].total, Decimal("14.50"))

    def test_category_budget_warning_and_over_alerts_with_deduplication(self):
        self.food.monthly_budget = Decimal("100.00")
        self.food.save()

        # 85% triggers warning (default threshold is 80%)
        Expense.objects.create(
            user=self.user, category=self.food, amount=Decimal("85.00"),
            date=timezone.localdate(), description="Groceries week 1",
        )
        self.assertEqual(self.user.notifications.count(), 1)
        warn = self.user.notifications.first()
        self.assertEqual(warn.level, Notification.Level.WARNING)
        self.assertIn("85%", warn.title)

        # Another small expense still under 100% does not duplicate the warning
        Expense.objects.create(
            user=self.user, category=self.food, amount=Decimal("5.00"),
            date=timezone.localdate(), description="Snack",
        )
        self.assertEqual(self.user.notifications.count(), 1)

        # Crossing 100% creates an over-budget danger alert
        Expense.objects.create(
            user=self.user, category=self.food, amount=Decimal("20.00"),
            date=timezone.localdate(), description="Dinner",
        )
        self.assertEqual(self.user.notifications.count(), 2)
        over = self.user.notifications.order_by("-id").first()
        self.assertEqual(over.level, Notification.Level.DANGER)
        self.assertIn("over budget", over.title)

    def test_higher_than_usual_spike_alert(self):
        today = timezone.localdate()
        this_month_start = today.replace(day=1)
        last_month = this_month_start - relativedelta(months=1)
        two_months_ago = this_month_start - relativedelta(months=2)

        # Historical average = $100/month
        Expense.objects.create(
            user=self.user, category=self.food, amount=Decimal("100.00"),
            date=two_months_ago, description="Month -2 groceries",
        )
        Expense.objects.create(
            user=self.user, category=self.food, amount=Decimal("100.00"),
            date=last_month, description="Month -1 groceries",
        )
        self.assertEqual(self.user.notifications.count(), 0)

        # Spending $160 this month (> 1.5x $100 average) triggers a spike alert
        Expense.objects.create(
            user=self.user, category=self.food, amount=Decimal("160.00"),
            date=today, description="Big party groceries",
        )
        self.assertTrue(
            self.user.notifications.filter(dedupe_key__startswith=f"spike:{self.food.pk}:").exists()
        )

    def test_email_alerts_sent_when_enabled(self):
        profile = self.user.profile
        profile.email_alerts = True
        profile.monthly_budget = Decimal("50.00")
        profile.save()

        with self.captureOnCommitCallbacks(execute=True):
            Expense.objects.create(
                user=self.user, category=self.food, amount=Decimal("60.00"),
                date=timezone.localdate(), description="Over budget purchase",
            )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("exceeded your monthly budget", mail.outbox[0].subject)

    def test_planned_expense_mark_paid_one_off_and_recurring(self):
        today = timezone.localdate()
        one_off = PlannedExpense.objects.create(
            user=self.user, category=self.transport, title="Car service",
            amount=Decimal("120.00"), due_date=today,
            recurrence=PlannedExpense.Recurrence.NONE,
        )
        expense = one_off.mark_paid()
        one_off.refresh_from_db()
        self.assertTrue(one_off.is_completed)
        self.assertEqual(expense.amount, Decimal("120.00"))

        recurring = PlannedExpense.objects.create(
            user=self.user, category=self.food, title="Meal box subscription",
            amount=Decimal("40.00"), due_date=today,
            recurrence=PlannedExpense.Recurrence.MONTHLY,
        )
        recurring.mark_paid()
        recurring.refresh_from_db()
        self.assertFalse(recurring.is_completed)
        self.assertEqual(recurring.due_date, today + relativedelta(months=1))

    def test_category_delete_reassigns_expenses_and_plans(self):
        Expense.objects.create(
            user=self.user, category=self.food, amount=Decimal("25.00"),
            date=timezone.localdate(), description="Lunch",
        )
        resp = self.client.post(
            reverse("category_delete", args=[self.food.pk]),
            {"move_to": self.transport.pk},
        )
        self.assertRedirects(resp, reverse("category_list"))
        self.assertFalse(Category.objects.filter(pk=self.food.pk).exists())
        self.assertEqual(self.transport.expenses.count(), 1)

    def test_csv_export_neutralizes_formula_injection(self):
        Expense.objects.create(
            user=self.user, category=self.food, amount=Decimal("10.00"),
            date=timezone.localdate(), description="=SUM(A1:A10)", notes="@cmd",
        )
        resp = self.client.get(reverse("expense_export"))
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode("utf-8")
        self.assertIn("'=SUM(A1:A10)", body)
        self.assertIn("'@cmd", body)

    def test_all_pages_render_and_enforce_user_isolation(self):
        other = User.objects.create_user(username="bob", email="bob@example.com", password="StrongPassword123!")
        other_cat = Category.objects.filter(user=other).first()
        other_expense = Expense.objects.create(
            user=other, category=other_cat, amount=Decimal("99.00"),
            date=timezone.localdate(), description="Bob secret",
        )

        # Alice cannot access Bob's expense
        self.assertEqual(
            self.client.get(reverse("expense_edit", args=[other_expense.pk])).status_code, 404
        )

        # Open redirect protection falls back to safe route
        n = Notification.objects.create(user=self.user, title="Test", message="Msg")
        resp = self.client.post(
            reverse("notification_mark_read", args=[n.pk]),
            {"next": "https://evil.example.com/phish"},
        )
        self.assertRedirects(resp, reverse("notification_list"))

        # Key pages render with HTTP 200
        for name in [
            "dashboard", "expense_list", "expense_create", "category_list",
            "category_create", "plan_list", "plan_create", "reports",
            "notification_list", "settings", "healthz",
        ]:
            with self.subTest(view=name):
                r = self.client.get(reverse(name))
                self.assertEqual(r.status_code, 200)

        # Anonymous home, login & signup render with HTTP 200
        self.client.logout()
        for name in ["homepage", "login", "signup"]:
            with self.subTest(public_view=name):
                r = self.client.get(reverse(name))
                self.assertEqual(r.status_code, 200)
