import base64
import csv
import io
import json
import math
from collections import Counter
from datetime import timedelta
from decimal import Decimal, InvalidOperation

import openpyxl
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from openpyxl.styles import Font, PatternFill

from .forms import CategoriaForm, MovimientoForm, ProductoForm, ProveedorForm
from .models import Categoria, MovimientoInventario, Producto, Proveedor


ROLE_ADMIN = 'Administrador'
ROLE_OPERADOR = 'Operador'
ROLE_CONSULTA = 'Consulta'


def es_admin(user):
    return user.is_superuser or user.groups.filter(name=ROLE_ADMIN).exists()


def es_operador(user):
    return es_admin(user) or user.groups.filter(name=ROLE_OPERADOR).exists()


def es_consulta(user):
    return es_operador(user) or user.groups.filter(name=ROLE_CONSULTA).exists()


def tiene_rol_lectura(user):
    return es_consulta(user)


def aplicar_filtros_productos(request):
    q = request.GET.get('q', '').strip()
    filtro_categoria = request.GET.get('categoria')
    filtro_vendedor = request.GET.get('vendedor')
    filtro_estado = request.GET.get('estado')
    orden = request.GET.get('orden', 'nombre')

    productos = Producto.objects.select_related('categoria', 'vendedor').all()

    if q:
        productos = productos.filter(Q(nombre__icontains=q) | Q(sku__icontains=q))
    if filtro_categoria:
        productos = productos.filter(categoria_id=filtro_categoria)
    if filtro_vendedor:
        productos = productos.filter(vendedor_id=filtro_vendedor)
    if filtro_estado == 'sin_stock':
        productos = productos.filter(stock=0)
    elif filtro_estado == 'stock_bajo':
        productos = productos.filter(stock__gt=0, stock__lte=F('stock_minimo'))
    elif filtro_estado == 'disponible':
        productos = productos.filter(stock__gt=F('stock_minimo'))
    elif filtro_estado == 'inactivo':
        productos = productos.filter(activo=False)
    elif filtro_estado == 'activo':
        productos = productos.filter(activo=True)

    ordenes = {
        'nombre': 'nombre',
        '-nombre': '-nombre',
        'stock': 'stock',
        '-stock': '-stock',
        'precio': 'precio',
        '-precio': '-precio',
        'fecha': 'fecha_creacion',
        '-fecha': '-fecha_creacion',
    }
    productos = productos.order_by(ordenes.get(orden, 'nombre'))

    return productos, {
        'query': q,
        'filtro_categoria': filtro_categoria,
        'filtro_vendedor': filtro_vendedor,
        'filtro_estado': filtro_estado,
        'orden': orden,
    }


def aplicar_filtros_movimientos(request):
    producto_id = request.GET.get('producto')
    tipo = request.GET.get('tipo')
    fecha_desde = request.GET.get('desde')
    fecha_hasta = request.GET.get('hasta')

    movimientos = MovimientoInventario.objects.select_related('producto', 'usuario').order_by('-fecha')

    if producto_id:
        movimientos = movimientos.filter(producto_id=producto_id)
    if tipo:
        movimientos = movimientos.filter(tipo=tipo)
    if fecha_desde:
        movimientos = movimientos.filter(fecha__date__gte=fecha_desde)
    if fecha_hasta:
        movimientos = movimientos.filter(fecha__date__lte=fecha_hasta)

    return movimientos, {
        'filtro_producto': producto_id,
        'filtro_tipo': tipo,
        'filtro_desde': fecha_desde,
        'filtro_hasta': fecha_hasta,
    }


def preparar_hoja(ws):
    fill = PatternFill('solid', fgColor='111318')
    font = Font(color='FFFFFF', bold=True)
    for cell in ws[1]:
        cell.fill = fill
        cell.font = font
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = ws.dimensions
    for column in ws.columns:
        max_length = max(len(str(cell.value or '')) for cell in column)
        ws.column_dimensions[column[0].column_letter].width = min(max(max_length + 2, 12), 34)


@login_required
@user_passes_test(tiene_rol_lectura)
def lista_productos(request):
    productos, filtros = aplicar_filtros_productos(request)
    paginator = Paginator(productos, 20)
    productos_page = paginator.get_page(request.GET.get('page'))

    stock_total = productos.aggregate(total=Sum('stock'))['total'] or 0
    bajo_stock = productos.filter(stock__gt=0, stock__lte=F('stock_minimo')).count()
    sin_stock = productos.filter(stock=0).count()

    context = {
        'productos': productos_page,
        'stock_total': stock_total,
        'bajo_stock': bajo_stock,
        'sin_stock': sin_stock,
        'categorias': Categoria.objects.all().order_by('nombre'),
        'vendedores': Proveedor.objects.all().order_by('nombre'),
        'puede_editar': es_admin(request.user),
        'puede_mover': es_operador(request.user),
        **filtros,
    }
    return render(request, 'inventario/lista_productos.html', context)


@login_required
@user_passes_test(es_admin)
def crear_producto(request):
    form = ProductoForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Producto creado. Registra una entrada para aumentar su stock.')
        return redirect('lista_productos')
    return render(request, 'inventario/crear_producto.html', {'form': form})


@login_required
@user_passes_test(es_operador)
def registrar_movimiento(request):
    productos = Producto.objects.filter(activo=True).order_by('nombre')
    form = MovimientoForm(request.POST or None)
    form.fields['producto'].queryset = productos

    if request.method == 'POST' and form.is_valid():
        tipo = form.cleaned_data['tipo']
        producto = form.cleaned_data['producto']
        cantidad = int(form.cleaned_data['cantidad'])

        with transaction.atomic():
            producto_bloqueado = Producto.objects.select_for_update().get(pk=producto.pk)
            if tipo == 'S' and cantidad > producto_bloqueado.stock:
                messages.error(request, f'Stock insuficiente. Disponible: {producto_bloqueado.stock}')
                return render(request, 'inventario/registrar_movimiento.html', {'form': form, 'productos': productos})

            movimiento = form.save(commit=False)
            movimiento.producto = producto_bloqueado
            movimiento.usuario = request.user
            movimiento.save()

            if movimiento.tipo == 'E':
                producto_bloqueado.stock += movimiento.cantidad
            else:
                producto_bloqueado.stock -= movimiento.cantidad
            producto_bloqueado.save(update_fields=['stock'])

        messages.success(request, 'Movimiento registrado correctamente.')
        return redirect('historial_movimientos')

    return render(request, 'inventario/registrar_movimiento.html', {'form': form, 'productos': productos})


@login_required
@user_passes_test(es_admin)
def eliminar_producto(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)
    if request.method == 'POST':
        try:
            producto.delete()
            messages.success(request, 'Producto eliminado correctamente.')
        except ProtectedError:
            messages.error(request, 'No se puede eliminar un producto con movimientos registrados.')
        return redirect('lista_productos')
    return render(request, 'inventario/confirmar_eliminar_producto.html', {'producto': producto})


@login_required
@user_passes_test(es_admin)
def editar_producto(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)
    form = ProductoForm(request.POST or None, instance=producto)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Producto actualizado correctamente.')
        return redirect('lista_productos')
    return render(request, 'inventario/editar_producto.html', {'form': form, 'producto': producto})


@login_required
@user_passes_test(tiene_rol_lectura)
def historial_movimientos(request):
    movimientos, filtros = aplicar_filtros_movimientos(request)
    paginator = Paginator(movimientos, 25)
    movimientos_page = paginator.get_page(request.GET.get('page'))
    context = {
        'movimientos': movimientos_page,
        'productos': Producto.objects.all().order_by('nombre'),
        **filtros,
    }
    return render(request, 'inventario/historial_movimientos.html', context)


@login_required
@user_passes_test(tiene_rol_lectura)
def exportar_productos_excel(request):
    productos, _ = aplicar_filtros_productos(request)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Productos'
    ws.append(['SKU', 'Nombre', 'Categoria', 'Proveedor', 'Unidad', 'Ubicacion categoria', 'Ubicacion detalle', 'Stock', 'Stock minimo', 'Estado', 'Precio', 'Activo', 'Fecha'])

    for p in productos:
        ws.append([
            p.sku or '',
            p.nombre,
            p.categoria.nombre if p.categoria else '',
            p.vendedor.nombre if p.vendedor else '',
            p.get_unidad_display(),
            p.get_ubicacion_categoria_display() if p.ubicacion_categoria else '',
            p.ubicacion,
            p.stock,
            p.stock_minimo,
            p.estado_stock,
            float(p.precio),
            'Si' if p.activo else 'No',
            p.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
        ])
    preparar_hoja(ws)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=productos.xlsx'
    wb.save(response)
    return response


@login_required
@user_passes_test(tiene_rol_lectura)
def exportar_stock_bajo_excel(request):
    productos = Producto.objects.filter(stock__lte=F('stock_minimo')).select_related('categoria', 'vendedor').order_by('stock', 'nombre')
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Requiere reposicion'
    ws.append(['SKU', 'Nombre', 'Categoria', 'Proveedor', 'Stock', 'Stock minimo', 'Faltante sugerido', 'Ubicacion categoria', 'Ubicacion detalle'])

    for p in productos:
        ws.append([
            p.sku or '',
            p.nombre,
            p.categoria.nombre if p.categoria else '',
            p.vendedor.nombre if p.vendedor else '',
            p.stock,
            p.stock_minimo,
            max(p.stock_minimo - p.stock, 0),
            p.get_ubicacion_categoria_display() if p.ubicacion_categoria else '',
            p.ubicacion,
        ])
    preparar_hoja(ws)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=stock_bajo.xlsx'
    wb.save(response)
    return response


@login_required
@user_passes_test(tiene_rol_lectura)
def exportar_movimientos_excel(request):
    movimientos, _ = aplicar_filtros_movimientos(request)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Movimientos'
    ws.append(['Fecha', 'Producto', 'SKU', 'Tipo', 'Cantidad', 'Usuario', 'Motivo'])

    for m in movimientos:
        ws.append([
            m.fecha.strftime('%d/%m/%Y %H:%M'),
            m.producto.nombre,
            m.producto.sku or '',
            m.get_tipo_display(),
            m.cantidad,
            m.usuario.username if m.usuario else '',
            m.motivo,
        ])
    preparar_hoja(ws)

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=movimientos.xlsx'
    wb.save(response)
    return response


@login_required
@user_passes_test(tiene_rol_lectura)
def dashboard(request):
    productos = Producto.objects.select_related('categoria', 'vendedor').all()
    movimientos = MovimientoInventario.objects.select_related('producto', 'usuario')
    desde = timezone.now() - timedelta(days=14)
    movimientos_recientes = movimientos.filter(fecha__gte=desde)

    total_productos = productos.count()
    stock_total = productos.aggregate(total=Sum('stock'))['total'] or 0
    valor_total = sum(p.stock * p.precio for p in productos)
    bajo_stock = productos.filter(stock__gt=0, stock__lte=F('stock_minimo')).count()
    sin_stock = productos.filter(stock=0).count()
    requiere_reposicion = productos.filter(stock__lte=F('stock_minimo')).order_by('stock', 'nombre')[:8]
    ultimos_movimientos = movimientos.order_by('-fecha')[:8]

    conteo = Counter(p.categoria.nombre if p.categoria else 'Sin categoria' for p in productos)
    labels = json.dumps(list(conteo.keys()), ensure_ascii=False)
    data = json.dumps(list(conteo.values()))

    entradas_salidas = (
        movimientos_recientes
        .values('fecha__date', 'tipo')
        .annotate(total=Sum('cantidad'))
        .order_by('fecha__date')
    )
    por_fecha = {}
    for row in entradas_salidas:
        fecha = row['fecha__date'].strftime('%d/%m')
        por_fecha.setdefault(fecha, {'E': 0, 'S': 0})
        por_fecha[fecha][row['tipo']] = row['total'] or 0

    movimiento_labels = list(por_fecha.keys())
    entradas_data = [por_fecha[f]['E'] for f in movimiento_labels]
    salidas_data = [por_fecha[f]['S'] for f in movimiento_labels]

    return render(request, 'inventario/dashboard.html', {
        'total_productos': total_productos,
        'stock_total': stock_total,
        'valor_total': valor_total,
        'bajo_stock': bajo_stock,
        'sin_stock': sin_stock,
        'requiere_reposicion': requiere_reposicion,
        'ultimos_movimientos': ultimos_movimientos,
        'labels': labels,
        'data': data,
        'movimiento_labels': json.dumps(movimiento_labels, ensure_ascii=False),
        'entradas_data': json.dumps(entradas_data),
        'salidas_data': json.dumps(salidas_data),
    })


@login_required
@user_passes_test(tiene_rol_lectura)
def productos_reposicion(request):
    productos = Producto.objects.select_related('categoria', 'vendedor').filter(stock__lte=F('stock_minimo')).order_by('stock', 'nombre')
    paginator = Paginator(productos, 20)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'inventario/productos_reposicion.html', {
        'productos': page,
        'total_reposicion': productos.count(),
        'sin_stock': productos.filter(stock=0).count(),
        'bajo_stock': productos.filter(stock__gt=0, stock__lte=F('stock_minimo')).count(),
    })


def normalizar_bool(valor):
    if valor is None:
        return True
    return str(valor).strip().lower() not in ['no', 'false', '0', 'inactivo']


def normalizar_decimal(valor):
    if valor is None:
        return Decimal('0')
    if isinstance(valor, float) and math.isnan(valor):
        return Decimal('0')
    if str(valor).strip() == '':
        return Decimal('0')
    try:
        return Decimal(str(valor))
    except (InvalidOperation, ValueError):
        raise ValueError('precio invalido')


def analizar_archivo_productos(ruta):
    def es_vacio(valor):
        if valor is None:
            return True
        if isinstance(valor, float) and math.isnan(valor):
            return True
        texto = str(valor).strip()
        return texto == '' or texto.lower() == 'nan'

    columnas_requeridas = {'nombre'}
    filas_archivo = []
    if str(ruta).lower().endswith('.csv'):
        with open(ruta, newline='', encoding='utf-8-sig') as archivo:
            lector = csv.DictReader(archivo)
            filas_archivo = [{str(k).strip().lower(): v for k, v in fila.items()} for fila in lector]
            columnas = {str(c).strip().lower() for c in (lector.fieldnames or [])}
    else:
        wb = openpyxl.load_workbook(ruta, data_only=True, read_only=True)
        ws = wb.active
        encabezados = [str(c.value).strip().lower() if c.value is not None else '' for c in next(ws.iter_rows(min_row=1, max_row=1))]
        columnas = {c for c in encabezados if c}
        for row in ws.iter_rows(min_row=2, values_only=True):
            fila = {encabezados[i]: row[i] for i in range(min(len(encabezados), len(row))) if encabezados[i]}
            filas_archivo.append(fila)

    faltantes = columnas_requeridas - columnas
    if faltantes:
        return [], [f'Faltan columnas obligatorias: {", ".join(sorted(faltantes))}'], []

    errores = []
    advertencias = []
    filas = []
    sku_vistos = set()
    nombres_sin_sku = set()
    for index, fila in enumerate(filas_archivo):
        numero = index + 2
        nombre = str(fila.get('nombre', '')).strip()
        if es_vacio(nombre):
            errores.append(f'Fila {numero}: nombre vacio.')
            continue
        try:
            precio = normalizar_decimal(fila.get('precio', 0))
            stock = int(0 if es_vacio(fila.get('stock', 0)) else fila.get('stock', 0))
            stock_minimo = int(5 if es_vacio(fila.get('stock_minimo', 5)) else fila.get('stock_minimo', 5))
            if stock < 0 or stock_minimo < 0:
                raise ValueError('stock negativo')
        except ValueError as exc:
            errores.append(f'Fila {numero}: {exc}.')
            continue

        unidad = str(fila.get('unidad', 'unidad')).strip().lower() or 'unidad'
        unidades_validas = {choice[0] for choice in Producto.UNIDAD_CHOICES}
        if unidad not in unidades_validas:
            unidad = 'unidad'

        ubicacion_categoria = str(fila.get('ubicacion_categoria', '')).strip().lower()
        ubicaciones_validas = {choice[0] for choice in Producto.UBICACION_CATEGORIA_CHOICES}
        if ubicacion_categoria and ubicacion_categoria not in ubicaciones_validas:
            ubicacion_categoria = ''

        sku = str(fila.get('sku', '')).strip().upper() or None
        if sku:
            if sku in sku_vistos:
                errores.append(f'Fila {numero}: SKU duplicado dentro del archivo ({sku}).')
                continue
            sku_vistos.add(sku)
        else:
            if nombre.lower() in nombres_sin_sku:
                advertencias.append(f'Fila {numero}: nombre repetido sin SKU ({nombre}). Se creara como producto separado.')
            nombres_sin_sku.add(nombre.lower())

        filas.append({
            'sku': sku,
            'nombre': nombre,
            'categoria': str(fila.get('categoria', '')).strip(),
            'proveedor': str(fila.get('proveedor', fila.get('vendedor', ''))).strip(),
            'stock': stock,
            'stock_minimo': stock_minimo,
            'precio': precio,
            'unidad': unidad,
            'ubicacion_categoria': ubicacion_categoria,
            'ubicacion': str(fila.get('ubicacion', '')).strip(),
            'activo': normalizar_bool(fila.get('activo', True)),
        })
    return filas, errores, advertencias


@login_required
@user_passes_test(es_admin)
def cargar_productos_excel(request):
    if request.method == 'POST':
        if request.POST.get('confirmar') and request.POST.get('archivo_guardado'):
            nombre_archivo = request.POST['archivo_guardado']
            ruta = default_storage.path(nombre_archivo)
            filas, errores, advertencias = analizar_archivo_productos(ruta)
            if errores:
                return render(request, 'inventario/cargar_excel.html', {'errores': errores, 'advertencias': advertencias})

            creados = 0
            actualizados = 0
            stock_iniciales = 0
            with transaction.atomic():
                for fila in filas:
                    categoria = None
                    proveedor = None
                    if fila['categoria']:
                        categoria, _ = Categoria.objects.get_or_create(nombre=fila['categoria'])
                    if fila['proveedor']:
                        proveedor, _ = Proveedor.objects.get_or_create(nombre=fila['proveedor'])

                    if fila['sku']:
                        producto, creado = Producto.objects.update_or_create(
                            sku=fila['sku'],
                            defaults={
                                'nombre': fila['nombre'],
                                'categoria': categoria,
                                'vendedor': proveedor,
                                'stock_minimo': fila['stock_minimo'],
                                'precio': fila['precio'],
                                'unidad': fila['unidad'],
                                'ubicacion_categoria': fila['ubicacion_categoria'],
                                'ubicacion': fila['ubicacion'],
                                'activo': fila['activo'],
                            }
                        )
                    else:
                        producto = Producto.objects.create(
                            sku=None,
                            nombre=fila['nombre'],
                            categoria=categoria,
                            vendedor=proveedor,
                            stock_minimo=fila['stock_minimo'],
                            precio=fila['precio'],
                            unidad=fila['unidad'],
                            ubicacion_categoria=fila['ubicacion_categoria'],
                            ubicacion=fila['ubicacion'],
                            activo=fila['activo'],
                        )
                        creado = True
                    if creado:
                        creados += 1
                    else:
                        actualizados += 1

                    if fila['stock'] > 0:
                        producto.stock += fila['stock']
                        producto.save(update_fields=['stock'])
                        stock_iniciales += 1
                        MovimientoInventario.objects.create(
                            producto=producto,
                            cantidad=fila['stock'],
                            tipo='E',
                            usuario=request.user,
                            motivo='Carga inicial desde Excel/CSV',
                        )

            default_storage.delete(nombre_archivo)
            return render(request, 'inventario/cargar_excel.html', {
                'resumen': {
                    'creados': creados,
                    'actualizados': actualizados,
                    'stock_iniciales': stock_iniciales,
                    'filas_procesadas': len(filas),
                    'advertencias': advertencias,
                }
            })

        archivo = request.FILES.get('archivo')
        if archivo:
            nombre_archivo = default_storage.save(f'importaciones/{archivo.name}', archivo)
            filas, errores, advertencias = analizar_archivo_productos(default_storage.path(nombre_archivo))
            return render(request, 'inventario/cargar_excel.html', {
                'preview': filas[:20],
                'total_preview': len(filas),
                'errores': errores,
                'advertencias': advertencias,
                'archivo_guardado': nombre_archivo,
            })

    return render(request, 'inventario/cargar_excel.html')


@login_required
@user_passes_test(tiene_rol_lectura)
def predecir_stock(request):
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    from sklearn.linear_model import LinearRegression

    movimientos = MovimientoInventario.objects.all().order_by('fecha')
    if not movimientos.exists():
        return render(request, 'inventario/prediccion.html', {'mensaje': 'No hay datos suficientes para predecir.'})

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

    dias_futuros = np.array(range(df['dias'].max() + 1, df['dias'].max() + 16)).reshape(-1, 1)
    predicciones = modelo.predict(dias_futuros)

    fig, ax = plt.subplots()
    ax.plot(df['dias'], y, label='Historico', marker='o')
    ax.plot(dias_futuros.flatten(), predicciones, label='Prediccion', linestyle='--')
    ax.set_title('Prediccion de Inventario (total)')
    ax.set_xlabel('Dias desde inicio')
    ax.set_ylabel('Stock acumulado')
    ax.legend()
    plt.tight_layout()

    buffer = io.BytesIO()
    plt.savefig(buffer, format='png')
    plt.close(fig)
    buffer.seek(0)
    grafico = base64.b64encode(buffer.getvalue()).decode()

    return render(request, 'inventario/prediccion.html', {'grafico': grafico})


@login_required
@user_passes_test(es_admin)
def lista_categorias(request):
    categorias = Categoria.objects.all().order_by('nombre')
    paginator = Paginator(categorias, 20)
    return render(request, 'inventario/lista_categorias.html', {'categorias': paginator.get_page(request.GET.get('page'))})


@login_required
@user_passes_test(es_admin)
def crear_categoria(request):
    form = CategoriaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('lista_categorias')
    return render(request, 'inventario/form_categoria.html', {'form': form})


@login_required
@user_passes_test(es_admin)
def editar_categoria(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)
    form = CategoriaForm(request.POST or None, instance=categoria)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('lista_categorias')
    return render(request, 'inventario/form_categoria.html', {'form': form, 'categoria': categoria})


@login_required
@user_passes_test(es_admin)
def eliminar_categoria(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)
    if request.method == 'POST':
        categoria.delete()
        return redirect('lista_categorias')
    return render(request, 'inventario/confirmar_eliminar_categoria.html', {'categoria': categoria})


@login_required
@user_passes_test(es_admin)
def lista_proveedores(request):
    proveedores = Proveedor.objects.all().order_by('nombre')
    return render(request, 'inventario/lista_proveedores.html', {'proveedores': proveedores})


@login_required
@user_passes_test(es_admin)
def crear_proveedor(request):
    form = ProveedorForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('lista_proveedores')
    return render(request, 'inventario/form_proveedor.html', {'form': form})


@login_required
@user_passes_test(es_admin)
def editar_proveedor(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)
    form = ProveedorForm(request.POST or None, instance=proveedor)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('lista_proveedores')
    return render(request, 'inventario/form_proveedor.html', {'form': form, 'proveedor': proveedor})


@login_required
@user_passes_test(es_admin)
def eliminar_proveedor(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)
    if request.method == 'POST':
        proveedor.delete()
        return redirect('lista_proveedores')
    return render(request, 'inventario/confirmar_eliminar_proveedor.html', {'proveedor': proveedor})
