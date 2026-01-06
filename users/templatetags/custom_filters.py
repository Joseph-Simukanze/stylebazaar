from django import template

register = template.Library()

@register.filter
def split(value, delimiter=" "):
    """
    Split a string into a list using the given delimiter.
    Usage: {{ "a b c"|split:" " }}
    """
    if not value:
        return []
    return value.split(delimiter)
