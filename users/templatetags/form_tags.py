from django import template

register = template.Library()

@register.filter(name="add_class")
def add_class(field, css_class):
    return field.as_widget(attrs={"class": css_class})
from django import template

register = template.Library()

@register.filter(name="add_class")
def add_class(field, css_class):
    if hasattr(field, "as_widget"):
        return field.as_widget(attrs={"class": css_class})
    return field
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name='add_class')
def add_class(field, css_class):
    """
    Adds a CSS class to a form field widget.
    Usage: {{ form.field|add_class:"class1 class2" }}
    """
    if field.field.widget.attrs.get('class'):
        existing_classes = field.field.widget.attrs['class']
        new_classes = f"{existing_classes} {css_class}"
    else:
        new_classes = css_class

    return field.as_widget(attrs={"class": new_classes})