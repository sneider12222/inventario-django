from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0007_alter_movimientoinventario_producto'),
    ]

    operations = [
        migrations.AddField(
            model_name='producto',
            name='ubicacion_categoria',
            field=models.CharField(blank=True, choices=[
                ('bodega', 'Bodega'),
                ('estanteria', 'Estanteria'),
                ('oficina', 'Oficina'),
                ('frio', 'Cadena de frio'),
                ('externo', 'Externo'),
            ], default='', max_length=20),
        ),
        migrations.AlterField(
            model_name='producto',
            name='ubicacion',
            field=models.CharField(blank=True, default='', max_length=120, verbose_name='Detalle de ubicacion'),
        ),
    ]
