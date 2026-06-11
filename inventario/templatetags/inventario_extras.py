from django import template
from decimal import Decimal
register = template.Library()
 
@register.filter
def cop(value):
    """
    Formatea un número como moneda colombiana COP.
    Ejemplo: 1234567.89  →  $ 1.234.567,89
    """
    try:
        value = Decimal(str(value))
        partes = f"{value:.2f}".split('.')
        entero = partes[0]
        centavos = partes[1]
 
        # Manejo de signo negativo
        negativo = entero.startswith('-')
        if negativo:
            entero = entero[1:]
 
        # Separador de miles con punto (estilo colombiano)
        entero_formateado = ''
        for i, digito in enumerate(reversed(entero)):
            if i > 0 and i % 3 == 0:
                entero_formateado = '.' + entero_formateado
            entero_formateado = digito + entero_formateado
 
        resultado = f"$ {entero_formateado},{centavos}"
        return f"-{resultado}" if negativo else resultado
    except Exception:
        return value


@register.simple_tag(takes_context=True)
def querystring(context, **kwargs):
    query = context['request'].GET.copy()
    for key, value in kwargs.items():
        if value in (None, ''):
            query.pop(key, None)
        else:
            query[key] = value
    return query.urlencode()
