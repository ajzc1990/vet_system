import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from faker import Faker

from apps.usuarios.models import Veterinaria
from apps.inventario.models import Categoria, Producto, MovimientoStock

class Command(BaseCommand):
    help = 'Carga Categorías y Productos de prueba para el Inventario'

    def handle(self, *args, **kwargs):
        fake = Faker('es_AR')

        veterinarias = list(Veterinaria.objects.filter(activo=True))
        if not veterinarias:
            self.stdout.write(self.style.ERROR(
                "No hay veterinarias registradas. Ejecutá primero: python manage.py cargar_veterinarias"
            ))
            return

        self.stdout.write("Creando Categorías e Insumos...")

        # 1. Categorías Globales
        categorias_datos = [
            ("Antiparasitarios", "Comprimidos, pipetas y suspensiones externas/internas"),
            ("Vacunas", "Biológicos para inmunización canina y felina"),
            ("Antibióticos y Antiinflamatorios", "Fármacos de tratamiento clínico"),
            ("Anestésicos y Quirúrgicos", "Material e insumos para quirófano"),
            ("Descartables", "Jeringas, agujas, gasas, guantes y patines"),
            ("Alimentos Medicados", "Nutrición clínica y dietas de prescripción")
        ]

        categorias_objs = []
        for nombre, desc in categorias_datos:
            cat, _ = Categoria.objects.get_or_create(
                nombre=nombre,
                defaults={'descripcion': desc}
            )
            categorias_objs.append(cat)

        # 2. Productos típicos por categoría
        productos_catalogo = [
            # Antiparasitarios
            ("Simparica 10-20kg (1 comp)", "MEDICAMENTO", "Antiparasitarios", 3500.00, 5200.00),
            ("Bravecto 20-40kg", "MEDICAMENTO", "Antiparasitarios", 12000.00, 18500.00),
            ("Total Full CG Suspension 15ml", "MEDICAMENTO", "Antiparasitarios", 1800.00, 2900.00),
            # Vacunas
            ("Vacuna Quíntuple Canina (Nobivac)", "VACUNA", "Vacunas", 2500.00, 4800.00),
            ("Vacuna Antirrábica", "VACUNA", "Vacunas", 1200.00, 2500.00),
            ("Vacuna Triple Felina", "VACUNA", "Vacunas", 2800.00, 5100.00),
            # Fármacos
            ("Amoxicilina + Ac. Clavulánico 500mg", "MEDICAMENTO", "Antibióticos y Antiinflamatorios", 1500.00, 2600.00),
            ("Meloxicam Oral 0.5%", "MEDICAMENTO", "Antibióticos y Antiinflamatorios", 2100.00, 3400.00),
            # Descartables
            ("Jeringas 3ml con Aguja (Caja x 100)", "DESCARTABLE", "Descartables", 4500.00, 7200.00),
            ("Guantes de Látex Talle M (Caja)", "DESCARTABLE", "Descartables", 3200.00, 5500.00),
            # Alimento
            ("Royal Canin Renal Canino 3kg", "ALIMENTO", "Alimentos Medicados", 11000.00, 16800.00),
            ("Pro Plan Vet Diets Gastrointestinal 2.5kg", "ALIMENTO", "Alimentos Medicados", 9800.00, 15200.00),
        ]

        prods_creados = 0
        movs_creados = 0

        for vet in veterinarias:
            for nombre_p, tipo_p, cat_p, costo, venta in productos_catalogo:
                categoria_obj = next((c for c in categorias_objs if c.nombre == cat_p), None)
                
                stock_inicial = random.randint(2, 40)
                
                prod, created = Producto.objects.get_or_create(
                    veterinaria=vet,
                    nombre=nombre_p,
                    defaults={
                        'categoria': categoria_obj,
                        'tipo': tipo_p,
                        'codigo_barras': str(fake.unique.random_number(digits=12)),
                        'stock_minimo': random.choice([3, 5, 10]),
                        'precio_costo': costo,
                        'precio_venta': venta,
                        'fecha_vencimiento': timezone.now().date() + timedelta(days=random.randint(90, 730))
                    }
                )

                if created:
                    prods_creados += 1
                    # Producto se crea con stock_actual=0 (default del modelo); el movimiento
                    # de ENTRADA es el que efectivamente carga el stock inicial vía su save().
                    MovimientoStock.objects.create(
                        producto=prod,
                        tipo='ENTRADA',
                        cantidad=stock_inicial,
                        motivo="Stock inicial de carga masiva"
                    )
                    movs_creados += 1

        self.stdout.write(self.style.SUCCESS(
            f"\n¡Carga de Inventario finalizada exitosamente!"
            f"\n- Productos creados: {prods_creados}"
            f"\n- Movimientos de stock iniciales: {movs_creados}"
        ))