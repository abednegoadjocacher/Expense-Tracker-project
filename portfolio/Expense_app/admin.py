from django.contrib import admin

from .models import Category, Expense, Notification, PlannedExpense, Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "currency", "timezone", "monthly_budget", "alert_threshold", "email_alerts")
    search_fields = ("user__username", "user__email")
    list_select_related = ("user",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "monthly_budget", "color", "created_at")
    list_filter = ("color",)
    search_fields = ("name", "user__username")
    list_select_related = ("user",)


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("date", "description", "amount", "category", "payment_method", "user")
    list_filter = ("payment_method", "date")
    search_fields = ("description", "notes", "user__username", "category__name")
    date_hierarchy = "date"
    list_select_related = ("user", "category")
    raw_id_fields = ("user", "category")


@admin.register(PlannedExpense)
class PlannedExpenseAdmin(admin.ModelAdmin):
    list_display = ("title", "amount", "due_date", "recurrence", "is_completed", "user")
    list_filter = ("recurrence", "is_completed")
    search_fields = ("title", "user__username")
    list_select_related = ("user", "category")
    raw_id_fields = ("user", "category")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "level", "user", "is_read", "created_at")
    list_filter = ("level", "is_read")
    search_fields = ("title", "message", "user__username")
    list_select_related = ("user",)
    raw_id_fields = ("user", "category")