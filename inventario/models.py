from django.db import models

class Producto(models.Model):
    nombre = models.CharField(max_length=100)
    categoria = models.CharField(max_length=50)
    stock = models.IntegerField(default=0)
    precio = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    vendedor = models.CharField(max_length=100, default='Desconocido')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre  

class MovimientoInventario(models.Model):
    TIPO_CHOICES = [
        ('E', 'Entrada'),
        ('S', 'Salida'),
    ]
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    tipo = models.CharField(max_length=1, choices=TIPO_CHOICES)
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.producto.nombre} ({self.cantidad})"
