from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import DEFAULT_CATEGORIES, Category, Expense, Profile
from .services import evaluate_alerts


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile_and_default_categories(sender, instance, created, raw=False, **kwargs):
    """Give every new user a profile and a starter set of categories."""
    if not created or raw:
        return
    Profile.objects.get_or_create(user=instance)
    Category.objects.bulk_create(
        [Category(user=instance, name=name, color=color) for name, color in DEFAULT_CATEGORIES],
        ignore_conflicts=True,
    )


@receiver(post_save, sender=Expense)
def expense_saved(sender, instance, raw=False, **kwargs):
    """Re-check budgets and spending spikes whenever an expense is added or edited.

    (Deleting an expense can only lower spending, so it never needs new alerts.)
    """
    if raw:
        return
    evaluate_alerts(instance.user, instance.date, categories=[instance.category])
