from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="homepage"),
    path("healthz/", views.healthz, name="healthz"),
    path("signup/", views.signup, name="signup"),
    path("dashboard/", views.dashboard, name="dashboard"),

    path("expenses/", views.expense_list, name="expense_list"),
    path("expenses/new/", views.expense_create, name="expense_create"),
    path("expenses/quick-add/", views.expense_quick_add, name="expense_quick_add"),
    path("expenses/export.csv", views.expense_export, name="expense_export"),
    path("expenses/<int:pk>/edit/", views.expense_update, name="expense_edit"),
    path("expenses/<int:pk>/delete/", views.expense_delete, name="expense_delete"),

    path("categories/", views.category_list, name="category_list"),
    path("categories/new/", views.category_create, name="category_create"),
    path("categories/<int:pk>/edit/", views.category_update, name="category_edit"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category_delete"),

    path("plans/", views.plan_list, name="plan_list"),
    path("plans/new/", views.plan_create, name="plan_create"),
    path("plans/<int:pk>/edit/", views.plan_update, name="plan_edit"),
    path("plans/<int:pk>/delete/", views.plan_delete, name="plan_delete"),
    path("plans/<int:pk>/paid/", views.plan_mark_paid, name="plan_mark_paid"),

    path("reports/", views.reports, name="reports"),

    path("notifications/", views.notification_list, name="notification_list"),
    path("notifications/read-all/", views.notification_mark_all_read, name="notification_mark_all_read"),
    path("notifications/<int:pk>/read/", views.notification_mark_read, name="notification_mark_read"),

    path("settings/", views.settings_view, name="settings"),
]