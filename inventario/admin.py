from django.contrib import admin
from .models import AuditoriaCambio, Categoria, MovimientoInventario, Producto, Proveedor, TransferenciaUbicacion

admin.site.register(Categoria)
admin.site.register(Proveedor)


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('sku', 'nombre', 'categoria', 'stock', 'stock_minimo', 'unidad', 'lote', 'fecha_vencimiento', 'ubicacion_categoria', 'ubicacion', 'activo', 'precio', 'vendedor')
    list_filter = ('activo', 'categoria', 'vendedor', 'unidad', 'ubicacion_categoria')
    search_fields = ('sku', 'nombre')
    readonly_fields = ('stock',)


@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'producto', 'tipo', 'cantidad', 'usuario', 'motivo')
    list_filter = ('tipo', 'fecha', 'usuario')
    search_fields = ('producto__nombre', 'producto__sku', 'motivo')


@admin.register(TransferenciaUbicacion)
class TransferenciaUbicacionAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'producto', 'ubicacion_categoria_origen', 'ubicacion_categoria_destino', 'usuario', 'motivo')
    list_filter = ('fecha', 'usuario', 'ubicacion_categoria_origen', 'ubicacion_categoria_destino')
    search_fields = ('producto__nombre', 'producto__sku', 'motivo')


@admin.register(AuditoriaCambio)
class AuditoriaCambioAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'accion', 'modelo', 'objeto', 'usuario')
    list_filter = ('accion', 'modelo', 'fecha', 'usuario')
    search_fields = ('accion', 'modelo', 'objeto', 'detalle')
