from django.conf import settings


def app_context(request):
    """Navbar data: unread alert count, latest alerts and the user's currency."""
    context = {"DEBUG": settings.DEBUG}
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return context

    profile = getattr(user, "profile", None)
    unread = user.notifications.filter(is_read=False)
    context.update({
        "currency_symbol": profile.currency_symbol if profile else "$",
        "currency_code": profile.currency if profile else "USD",
        "unread_notifications_count": unread.count(),
        "recent_notifications": list(unread.order_by("-created_at")[:5]),
    })
    return context
