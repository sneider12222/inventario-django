import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
import matplotlib.pyplot as plt
import io
import base64
from django.core.files.storage import default_storage
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils.safestring import mark_safe
from django import forms
from .models import Producto, MovimientoInventario, Categoria, Proveedor
from .forms import CategoriaForm, ProveedorForm, ProductoForm
import openpyxl
from django.http import HttpResponse
import json

# === Formularios ===

# ProductoForm moved to inventario/forms.py
class MovimientoForm(forms.ModelForm):
    class Meta:
        model = MovimientoInventario
        fields = ['producto', 'cantidad', 'tipo']

# === Vistas ===

@login_required
def lista_productos(request):
    q = request.GET.get('q', '')
    filtro_categoria = request.GET.get('categoria')
    filtro_vendedor = request.GET.get('vendedor')

    productos = Producto.objects.all()

    if q:
        productos = productos.filter(
            Q(nombre__icontains=q) | Q(categoria__icontains=q)
        )
    if filtro_categoria:
        productos = productos.filter(categoria__iexact=filtro_categoria)

    if filtro_vendedor:
        productos = productos.filter(vendedor__iexact=filtro_vendedor)

    # Para los desplegables únicos
    categorias = Producto.objects.values_list('categoria', flat=True).distinct()
    vendedores = Producto.objects.values_list('vendedor', flat=True).distinct()

    stock_total = sum(p.stock for p in productos)
    labels = [p.nombre for p in productos]
    stock_data = [p.stock for p in productos]

    return render(request, 'inventario/lista_productos.html', {
        'productos': productos,
        'stock_total': stock_total,
        'labels': mark_safe(json.dumps(labels)),
        'stock_data': mark_safe(json.dumps(stock_data)),
        'query': q,
        'q': q,
        'categorias': categorias,
        'vendedores': vendedores,
        'filtro_categoria': filtro_categoria,
        'filtro_vendedor': filtro_vendedor,
    })


@login_required
def crear_producto(request):
    if request.method == 'POST':
        form = ProductoForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('lista_productos')
    else:
        form = ProductoForm()
    return render(request, 'inventario/crear_producto.html', {'form': form})

@login_required
def registrar_movimiento(request):
    productos = Producto.objects.all()
    if request.method == 'POST':
        form = MovimientoForm(request.POST)
        if form.is_valid():
            tipo = form.cleaned_data.get('tipo')
            producto = form.cleaned_data.get('producto')
            cantidad = int(form.cleaned_data.get('cantidad') or 0)

            # Validación de stock en servidor
            if tipo == 'S' and cantidad > producto.stock:
                messages.error(request, f'Stock insuficiente. Disponible: {producto.stock}')
                return render(request, 'inventario/registrar_movimiento.html', {'form': form, 'productos': productos})

            movimiento = form.save()
            if movimiento.tipo == 'E':
                movimiento.producto.stock += movimiento.cantidad
            else:
                movimiento.producto.stock -= movimiento.cantidad
            movimiento.producto.save()
            return redirect('lista_productos')
    else:
        form = MovimientoForm()
    return render(request, 'inventario/registrar_movimiento.html', {'form': form, 'productos': productos})

@login_required
@user_passes_test(lambda u: u.is_superuser)
def eliminar_producto(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)
    producto.delete()
    return redirect('lista_productos')

@login_required
@user_passes_test(lambda u: u.is_superuser)
def editar_producto(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)
    if request.method == 'POST':
        form = ProductoForm(request.POST, instance=producto)
        if form.is_valid():
            form.save()
            return redirect('lista_productos')
    else:
        form = ProductoForm(instance=producto)
    return render(request, 'inventario/editar_producto.html', {
        'form': form,
        'producto': producto
    })

@login_required
def historial_movimientos(request):
    movimientos = MovimientoInventario.objects.select_related('producto').order_by('-fecha')
    return render(request, 'inventario/historial_movimientos.html', {
        'movimientos': movimientos
    })

import openpyxl
from django.http import HttpResponse

@login_required
def exportar_productos_excel(request):
    productos = Producto.objects.all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Productos"

    # Cabeceras
    headers = ['Nombre', 'Categoría', 'Stock', 'Precio', 'Vendedor', 'Fecha']
    ws.append(headers)

    # Filas
    for p in productos:
        ws.append([
            p.nombre,
            p.categoria,
            p.stock,
            float(p.precio),
            p.vendedor,
            p.fecha_creacion.strftime('%d/%m/%Y %H:%M')
        ])

    # Configurar la respuesta HTTP
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=productos.xlsx'
    wb.save(response)
    return response

@login_required
def dashboard(request):
    productos = Producto.objects.all()

    total_productos = productos.count()
    stock_total = sum(p.stock for p in productos)
    valor_total = sum(p.stock * p.precio for p in productos)
    productos_bajo_stock = productos.filter(stock__lte=5).count()

    # Para gráfico por categoría
    from collections import Counter
    categorias = [p.categoria for p in productos]
    conteo_categorias = Counter(categorias)

    return render(request, 'inventario/dashboard.html', {
        'total_productos': total_productos,
        'stock_total': stock_total,
        'valor_total': valor_total,
        'bajo_stock': productos_bajo_stock,
        'labels': list(conteo_categorias.keys()),
        'data': list(conteo_categorias.values())
    })

@login_required
def cargar_productos_excel(request):
    if request.method == 'POST' and request.FILES.get('archivo'):
        archivo = request.FILES['archivo']
        nombre_archivo = default_storage.save(archivo.name, archivo)

        ruta = default_storage.path(nombre_archivo)

        try:
            if archivo.name.endswith('.csv'):
                df = pd.read_csv(ruta)
            else:
                df = pd.read_excel(ruta)

            for _, fila in df.iterrows():
                Producto.objects.create(
                    nombre=fila['nombre'],
                    categoria=fila['categoria'],
                    stock=int(fila['stock']),
                    precio=float(fila['precio']),
                    vendedor=fila['vendedor']
                )

            messages.success(request, "Productos cargados correctamente.")
        except Exception as e:
            messages.error(request, f"Ocurrió un error: {str(e)}")

        return redirect('lista_productos')

    return render(request, 'inventario/cargar_excel.html')

@login_required
def predecir_stock(request):
    movimientos = MovimientoInventario.objects.all().order_by('fecha')
    if not movimientos.exists():
        return render(request, 'inventario/prediccion.html', {'mensaje': 'No hay datos suficientes para predecir.'})

    # Preparar datos agrupados por fecha
    df = pd.DataFrame.from_records(movimientos.values('fecha', 'cantidad', 'tipo'))
    df['fecha'] = pd.to_datetime(df['fecha'])
    df.sort_values('fecha', inplace=True)
    df['dias'] = (df['fecha'] - df['fecha'].min()).dt.days
    df['cantidad'] = df.apply(lambda row: row['cantidad'] if row['tipo'] == 'E' else -row['cantidad'], axis=1)
    df = df.groupby('dias')['cantidad'].sum().cumsum().reset_index()

    X = df[['dias']]
    y = df['cantidad']

    modelo = LinearRegression()
    modelo.fit(X, y)

    # Predicción para los próximos 15 días
    dias_futuros = np.array(range(df['dias'].max() + 1, df['dias'].max() + 16)).reshape(-1, 1)
    predicciones = modelo.predict(dias_futuros)

    # Graficar
    fig, ax = plt.subplots()
    ax.plot(df['dias'], y, label='Histórico', marker='o')
    ax.plot(dias_futuros.flatten(), predicciones, label='Predicción', linestyle='--')
    ax.set_title('Predicción de Inventario (total)')
    ax.set_xlabel('Días desde inicio')
    ax.set_ylabel('Stock acumulado')
    ax.legend()
    plt.tight_layout()

    # Convertir gráfica a base64
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    grafico = base64.b64encode(buffer.getvalue()).decode()

    return render(request, 'inventario/prediccion.html', {'grafico': grafico})


# ======================
# CRUD Categoría
# ======================


@login_required
def lista_categorias(request):
    categorias = Categoria.objects.all().order_by('nombre')
    paginator = Paginator(categorias, 20)
    page = request.GET.get('page')
    categorias_page = paginator.get_page(page)
    return render(request, 'inventario/lista_categorias.html', {
        'categorias': categorias_page
    })


@login_required
def crear_categoria(request):
    if request.method == 'POST':
        form = CategoriaForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('lista_categorias')
    else:
        form = CategoriaForm()
    return render(request, 'inventario/form_categoria.html', {'form': form})


@login_required
def editar_categoria(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)
    if request.method == 'POST':
        form = CategoriaForm(request.POST, instance=categoria)
        if form.is_valid():
            form.save()
            return redirect('lista_categorias')
    else:
        form = CategoriaForm(instance=categoria)
    return render(request, 'inventario/form_categoria.html', {'form': form, 'categoria': categoria})


@login_required
def eliminar_categoria(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)
    if request.method == 'POST':
        categoria.delete()
        return redirect('lista_categorias')
    return render(request, 'inventario/confirmar_eliminar_categoria.html', {'categoria': categoria})


# ======================
# CRUD Proveedor
# ======================


@login_required
def lista_proveedores(request):
    proveedores = Proveedor.objects.all().order_by('nombre')
    return render(request, 'inventario/lista_proveedores.html', {'proveedores': proveedores})


@login_required
def crear_proveedor(request):
    if request.method == 'POST':
        form = ProveedorForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('lista_proveedores')
    else:
        form = ProveedorForm()
    return render(request, 'inventario/form_proveedor.html', {'form': form})


@login_required
def editar_proveedor(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)
    if request.method == 'POST':
        form = ProveedorForm(request.POST, instance=proveedor)
        if form.is_valid():
            form.save()
            return redirect('lista_proveedores')
    else:
        form = ProveedorForm(instance=proveedor)
    return render(request, 'inventario/form_proveedor.html', {'form': form, 'proveedor': proveedor})


@login_required
def eliminar_proveedor(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)
    if request.method == 'POST':
        proveedor.delete()
        return redirect('lista_proveedores')
    return render(request, 'inventario/confirmar_eliminar_proveedor.html', {'proveedor': proveedor})

