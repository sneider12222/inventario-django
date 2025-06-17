from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_productos, name='lista_productos'),
    path('nuevo/', views.crear_producto, name='crear_producto'),
    path('movimiento/', views.registrar_movimiento, name='registrar_movimiento'),
    path('eliminar/<int:producto_id>/', views.eliminar_producto, name='eliminar_producto'),
    path('editar/<int:producto_id>/', views.editar_producto, name='editar_producto'),
    path('historial/', views.historial_movimientos, name='historial_movimientos'),
    path('exportar/excel/', views.exportar_productos_excel, name='exportar_productos_excel'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('cargar/', views.cargar_productos_excel, name='cargar_excel'),
    path('predecir/', views.predecir_stock, name='predecir_stock'),
]