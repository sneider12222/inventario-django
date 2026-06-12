from .views import es_admin, es_consulta, es_operador


def permisos_rol(request):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {
            'puede_ver_inventario': False,
            'puede_gestionar_catalogos': False,
            'puede_operar_movimientos': False,
            'puede_administrar_usuarios': False,
        }

    return {
        'puede_ver_inventario': es_consulta(user),
        'puede_gestionar_catalogos': es_admin(user),
        'puede_operar_movimientos': es_operador(user),
        'puede_administrar_usuarios': es_admin(user),
    }
