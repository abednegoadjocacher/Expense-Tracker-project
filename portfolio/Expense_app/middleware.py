import zoneinfo

from django.utils import timezone


class UserTimezoneMiddleware:
    """Activate the signed-in user's timezone so "today" matches their local day."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tzname = None
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            profile = getattr(user, "profile", None)
            tzname = getattr(profile, "timezone", None)
        if tzname:
            try:
                timezone.activate(zoneinfo.ZoneInfo(tzname))
            except zoneinfo.ZoneInfoNotFoundError:
                timezone.deactivate()
        else:
            timezone.deactivate()
        return self.get_response(request)
