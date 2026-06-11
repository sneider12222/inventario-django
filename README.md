# Sistema de Control de Stock con Django

Aplicacion web para gestionar productos, entradas, salidas, alertas de reposicion, historial de movimientos, importacion/exportacion en Excel y dashboard operativo.

## Funcionalidades

- Productos con SKU, categoria, proveedor, unidad, ubicacion, precio, estado activo y stock minimo.
- Stock actualizado desde movimientos de entrada/salida.
- Bloqueo de salidas cuando no hay stock suficiente.
- Alertas de stock bajo y productos sin stock.
- Dashboard con valor total, productos criticos, ultimos movimientos y grafica de entradas vs salidas.
- Historial con filtros por producto, tipo y fechas.
- Usuario y motivo registrados en cada movimiento.
- Importacion CSV/XLSX con validacion, vista previa y confirmacion.
- Exportacion de productos, movimientos y productos que requieren reposicion.
- Roles sugeridos por grupos de Django:
  - `Administrador`: crea, edita, elimina, importa y administra catalogos.
  - `Operador`: registra entradas y salidas.
  - `Consulta`: revisa productos, dashboard, historial y reportes.

## Instalacion

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Crear un archivo `.env`:

```env
SECRET_KEY=tu-clave-local
DEBUG=True
```

## Importacion masiva

Columnas recomendadas:

```text
sku,nombre,categoria,proveedor,stock,stock_minimo,precio,unidad,ubicacion,activo
```

La unica columna obligatoria es `nombre`. Si `categoria` o `proveedor` no existen, se crean automaticamente. Si el archivo trae `stock`, se registra como movimiento de entrada con motivo "Carga inicial desde Excel/CSV".

## Pruebas

```powershell
python manage.py test
```
