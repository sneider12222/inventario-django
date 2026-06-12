from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

class Categoria(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

class Proveedor(models.Model):
    nombre = models.CharField(max_length=150)
    contacto = models.CharField(max_length=100, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

class Producto(models.Model):
    UNIDAD_CHOICES = [
        ('unidad', 'Unidad'),
        ('caja', 'Caja'),
        ('paquete', 'Paquete'),
        ('kg', 'Kilogramo'),
        ('litro', 'Litro'),
        ('metro', 'Metro'),
    ]
    UBICACION_CATEGORIA_CHOICES = [
        ('bodega', 'Bodega'),
        ('estanteria', 'Estanteria'),
        ('mostrador', 'Mostrador'),
        ('oficina', 'Oficina'),
        ('frio', 'Cadena de frio'),
        ('externo', 'Externo'),
    ]

    sku = models.CharField(max_length=50, unique=True, null=True, blank=True, verbose_name='Código/SKU')
    nombre = models.CharField(max_length=100)
    categoria = models.ForeignKey('Categoria', on_delete=models.SET_NULL, null=True, blank=True)
    stock = models.PositiveIntegerField(default=0)
    stock_minimo = models.PositiveIntegerField(default=5)
    unidad = models.CharField(max_length=20, choices=UNIDAD_CHOICES, default='unidad')
    lote = models.CharField(max_length=60, blank=True, default='')
    fecha_vencimiento = models.DateField(null=True, blank=True)
    ubicacion_categoria = models.CharField(max_length=20, choices=UBICACION_CATEGORIA_CHOICES, blank=True, default='')
    ubicacion = models.CharField(max_length=120, blank=True, default='', verbose_name='Detalle de ubicacion')
    activo = models.BooleanField(default=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    vendedor = models.ForeignKey('Proveedor', on_delete=models.SET_NULL, null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    @property
    def sin_stock(self):
        return self.stock == 0

    @property
    def stock_bajo(self):
        return 0 < self.stock <= self.stock_minimo

    @property
    def estado_stock(self):
        if self.sin_stock:
            return 'Sin stock'
        if self.stock_bajo:
            return 'Stock bajo'
        return 'Disponible'

    @property
    def faltante_reposicion(self):
        return max(self.stock_minimo - self.stock, 0)

    @property
    def vence_pronto(self):
        if not self.fecha_vencimiento:
            return False
        return self.fecha_vencimiento <= timezone.localdate() + timedelta(days=30)

    @property
    def ubicacion_completa(self):
        partes = []
        if self.ubicacion_categoria:
            partes.append(self.get_ubicacion_categoria_display())
        if self.ubicacion:
            partes.append(self.ubicacion)
        return ' - '.join(partes)

    def __str__(self):
        return self.nombre  

class MovimientoInventario(models.Model):
    TIPO_CHOICES = [
        ('E', 'Entrada'),
        ('S', 'Salida'),
    ]
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField()
    tipo = models.CharField(max_length=1, choices=TIPO_CHOICES)
    motivo = models.CharField(max_length=180, blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.producto.nombre} ({self.cantidad})"


class TransferenciaUbicacion(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='transferencias_ubicacion')
    ubicacion_categoria_origen = models.CharField(max_length=20, choices=Producto.UBICACION_CATEGORIA_CHOICES, blank=True, default='')
    ubicacion_origen = models.CharField(max_length=120, blank=True, default='')
    ubicacion_categoria_destino = models.CharField(max_length=20, choices=Producto.UBICACION_CATEGORIA_CHOICES, blank=True, default='')
    ubicacion_destino = models.CharField(max_length=120, blank=True, default='')
    motivo = models.CharField(max_length=180, blank=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Traslado - {self.producto.nombre}"


class AuditoriaCambio(models.Model):
    fecha = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    accion = models.CharField(max_length=40)
    modelo = models.CharField(max_length=80)
    objeto = models.CharField(max_length=120, blank=True)
    detalle = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.accion} - {self.modelo}"
