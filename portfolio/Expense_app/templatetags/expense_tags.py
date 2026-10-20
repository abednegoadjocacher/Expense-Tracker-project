from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def money(context, amount, decimals=None):
    """Format an amount in the current user's currency, e.g. {% money 1234.5 %} -> $1,234.50."""
    symbol = context.get("currency_symbol", "$")
    if decimals is None:
        decimals = 0 if context.get("currency_code") == "JPY" else 2
    try:
        value = Decimal(amount or 0)
    except (InvalidOperation, TypeError, ValueError):
        return amount
    sign = "-" if value < 0 else ""
    return f"{sign}{symbol}{abs(value):,.{decimals}f}"


@register.filter
def clamp_pct(value):
    """Clamp a percentage to 0-100 for progress bars."""
    try:
        return max(0, min(100, float(value)))
    except (TypeError, ValueError):
        return 0


@register.filter
def budget_class(status):
    return {"over": "progress-error", "warning": "progress-warning", "ok": "progress-success"}.get(status, "")


@register.simple_tag(takes_context=True)
def querystring_without(context, *keys):
    """Current GET params minus `keys`, for building pagination/filter links."""
    params = context["request"].GET.copy()
    for key in keys:
        params.pop(key, None)
    encoded = params.urlencode()
    return f"&{encoded}" if encoded else ""


@register.filter
def style_field(bound_field):
    """Ensure built-in Django form fields (e.g. auth forms) also get daisyUI classes."""
    try:
        attrs = bound_field.field.widget.attrs
    except AttributeError:
        return bound_field
    if not attrs.get("class"):
        wtype = getattr(bound_field, "widget_type", "")
        if wtype == "checkbox":
            attrs["class"] = "toggle toggle-primary"
        elif wtype == "select":
            attrs["class"] = "select w-full"
        elif wtype == "textarea":
            attrs["class"] = "textarea w-full"
        else:
            attrs["class"] = "input w-full"
    return bound_field

