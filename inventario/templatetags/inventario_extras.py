from django import template

register = template.Library()

@register.filter
def map(queryset, attr):
    return [getattr(obj, attr) for obj in queryset]
