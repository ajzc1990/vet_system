from django.db import migrations

PRECIO_MENSUAL = 20000
PRECIO_ANUAL = 200000


def fijar_precios_reales(apps, schema_editor):
    Plan = apps.get_model('usuarios', 'Plan')
    Plan.objects.filter(nombre='Profesional').update(
        precio_mensual=PRECIO_MENSUAL, precio_anual=PRECIO_ANUAL,
    )


def revertir(apps, schema_editor):
    """No hay un valor anterior único y confiable para volver a poner (el precio
    mensual venía de una carga manual previa a este esquema); no-op intencional."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0006_plan_precio_anual_suscripcion_ciclo_facturacion'),
    ]

    operations = [
        migrations.RunPython(fijar_precios_reales, revertir),
    ]
