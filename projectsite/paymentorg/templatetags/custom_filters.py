from django import template

register = template.Library()

@register.filter
def replace(value, arg):
    """Replace the first argument with the second argument in the given value."""
    if not arg or '|' not in arg:
        return value
    
    search, replace_with = arg.split('|', 1)
    return str(value).replace(search, replace_with)
