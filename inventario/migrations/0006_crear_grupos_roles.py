from django.db import migrations


def crear_grupos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    for nombre in ['Administrador', 'Operador', 'Consulta']:
        Group.objects.get_or_create(name=nombre)


def eliminar_grupos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name__in=['Administrador', 'Operador', 'Consulta']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0005_movimientoinventario_motivo_and_more'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(crear_grupos, eliminar_grupos),
    ]
