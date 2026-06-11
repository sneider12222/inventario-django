from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import MovimientoInventario, Producto


class InventarioFlowTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='pass12345',
        )
        self.client.force_login(self.admin)

    def test_crear_producto_no_edita_stock_directamente(self):
        response = self.client.post(reverse('crear_producto'), {
            'sku': 'SKU-001',
            'nombre': 'Producto prueba',
            'stock_minimo': 4,
            'unidad': 'unidad',
            'ubicacion_categoria': 'bodega',
            'ubicacion': 'Bodega A',
            'activo': 'on',
            'precio': '1200',
        })

        self.assertRedirects(response, reverse('lista_productos'))
        producto = Producto.objects.get(sku='SKU-001')
        self.assertEqual(producto.stock, 0)
        self.assertEqual(producto.stock_minimo, 4)

    def test_registrar_entrada_actualiza_stock_y_usuario(self):
        producto = Producto.objects.create(nombre='Entrada test', stock_minimo=2)

        response = self.client.post(reverse('registrar_movimiento'), {
            'producto': producto.id,
            'cantidad': 7,
            'tipo': 'E',
            'motivo': 'Compra',
        })

        self.assertRedirects(response, reverse('historial_movimientos'))
        producto.refresh_from_db()
        self.assertEqual(producto.stock, 7)
        movimiento = MovimientoInventario.objects.get(producto=producto)
        self.assertEqual(movimiento.usuario, self.admin)
        self.assertEqual(movimiento.motivo, 'Compra')

    def test_registrar_salida_valida_descuenta_stock(self):
        producto = Producto.objects.create(nombre='Salida test', stock=8, stock_minimo=2)

        response = self.client.post(reverse('registrar_movimiento'), {
            'producto': producto.id,
            'cantidad': 3,
            'tipo': 'S',
            'motivo': 'Venta',
        })

        self.assertRedirects(response, reverse('historial_movimientos'))
        producto.refresh_from_db()
        self.assertEqual(producto.stock, 5)

    def test_bloquea_salida_sin_stock_suficiente(self):
        producto = Producto.objects.create(nombre='Bloqueo test', stock=2, stock_minimo=2)

        response = self.client.post(reverse('registrar_movimiento'), {
            'producto': producto.id,
            'cantidad': 5,
            'tipo': 'S',
            'motivo': 'Venta',
        })

        self.assertEqual(response.status_code, 200)
        producto.refresh_from_db()
        self.assertEqual(producto.stock, 2)
        self.assertFalse(MovimientoInventario.objects.filter(producto=producto).exists())

    def test_importar_csv_con_vista_previa_y_confirmacion(self):
        contenido = (
            'sku,nombre,categoria,proveedor,stock,stock_minimo,precio,unidad,ubicacion_categoria,ubicacion,activo\n'
            'IMP-001,Importado,General,Proveedor A,6,2,1500,unidad,bodega,Bodega 1,si\n'
        ).encode()
        archivo = SimpleUploadedFile('productos.csv', contenido, content_type='text/csv')

        preview = self.client.post(reverse('cargar_excel'), {'archivo': archivo})
        self.assertEqual(preview.status_code, 200)
        self.assertContains(preview, 'Vista previa')

        archivo_guardado = preview.context['archivo_guardado']
        response = self.client.post(reverse('cargar_excel'), {
            'confirmar': '1',
            'archivo_guardado': archivo_guardado,
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Importacion completada')
        producto = Producto.objects.get(sku='IMP-001')
        self.assertEqual(producto.stock, 6)
        self.assertEqual(producto.stock_minimo, 2)
        self.assertEqual(MovimientoInventario.objects.filter(producto=producto, tipo='E').count(), 1)

    def test_impide_borrar_producto_con_movimientos(self):
        producto = Producto.objects.create(nombre='Con historial', stock=3, stock_minimo=1)
        MovimientoInventario.objects.create(producto=producto, cantidad=3, tipo='E', usuario=self.admin, motivo='Inicio')

        response = self.client.post(reverse('eliminar_producto', args=[producto.id]))

        self.assertRedirects(response, reverse('lista_productos'))
        self.assertTrue(Producto.objects.filter(id=producto.id).exists())

    def test_reposicion_page_renders(self):
        Producto.objects.create(nombre='Pendiente', stock=1, stock_minimo=5)

        response = self.client.get(reverse('productos_reposicion'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Reposicion')

    def test_importar_csv_con_sku_duplicado_da_error(self):
        contenido = (
            'sku,nombre,stock,stock_minimo,precio,unidad,ubicacion_categoria,ubicacion,activo\n'
            'DUP-1,Primero,1,2,100,unidad,bodega,Bodega,si\n'
            'DUP-1,Segundo,1,2,100,unidad,bodega,Bodega,si\n'
        ).encode()
        archivo = SimpleUploadedFile('duplicado.csv', contenido, content_type='text/csv')

        preview = self.client.post(reverse('cargar_excel'), {'archivo': archivo})

        self.assertEqual(preview.status_code, 200)
        self.assertContains(preview, 'SKU duplicado dentro del archivo')
