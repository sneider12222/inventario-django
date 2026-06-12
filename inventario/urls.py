from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_productos, name='lista_productos'),
    path('nuevo/', views.crear_producto, name='crear_producto'),
    path('movimiento/', views.registrar_movimiento, name='registrar_movimiento'),
    path('producto/<int:producto_id>/', views.detalle_producto, name='detalle_producto'),
    path('producto/<int:producto_id>/traslado/', views.trasladar_ubicacion, name='trasladar_ubicacion'),
    path('eliminar/<int:producto_id>/', views.eliminar_producto, name='eliminar_producto'),
    path('editar/<int:producto_id>/', views.editar_producto, name='editar_producto'),
    path('historial/', views.historial_movimientos, name='historial_movimientos'),
    path('exportar/excel/', views.exportar_productos_excel, name='exportar_productos_excel'),
    path('exportar/stock-bajo/', views.exportar_stock_bajo_excel, name='exportar_stock_bajo_excel'),
    path('exportar/movimientos/', views.exportar_movimientos_excel, name='exportar_movimientos_excel'),
    path('exportar/pdf/', views.exportar_inventario_pdf, name='exportar_inventario_pdf'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('reposicion/', views.productos_reposicion, name='productos_reposicion'),
    path('reportes/', views.reportes_inventario, name='reportes_inventario'),
    path('cargar/', views.cargar_productos_excel, name='cargar_excel'),
    path('predecir/', views.predecir_stock, name='predecir_stock'),
    # Categorias
    path('categorias/', views.lista_categorias, name='lista_categorias'),
    path('categorias/nueva/', views.crear_categoria, name='crear_categoria'),
    path('categorias/<int:pk>/editar/', views.editar_categoria, name='editar_categoria'),
    path('categorias/<int:pk>/eliminar/', views.eliminar_categoria, name='eliminar_categoria'),

    # Proveedores
    path('proveedores/', views.lista_proveedores, name='lista_proveedores'),
    path('proveedores/nuevo/', views.crear_proveedor, name='crear_proveedor'),
    path('proveedores/<int:pk>/editar/', views.editar_proveedor, name='editar_proveedor'),
    path('proveedores/<int:pk>/eliminar/', views.eliminar_proveedor, name='eliminar_proveedor'),

    # Usuarios
    path('usuarios/', views.lista_usuarios, name='lista_usuarios'),
    path('usuarios/nuevo/', views.crear_usuario, name='crear_usuario'),
    path('usuarios/<int:pk>/editar/', views.editar_usuario, name='editar_usuario'),
    path('usuarios/<int:pk>/eliminar/', views.eliminar_usuario, name='eliminar_usuario'),
]
