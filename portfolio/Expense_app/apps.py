from django.apps import AppConfig


class ExpenseAppConfig(AppConfig):
    name = 'Expense_app'
    verbose_name = "Expense tracker"

    def ready(self):
        from . import signals  # noqa: F401  (connect signal handlers)
