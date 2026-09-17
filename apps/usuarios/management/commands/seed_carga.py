import random
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from faker import Faker

from apps.usuarios.models import Veterinaria, PerfilUsuario, Plan, Suscripcion
from apps.clientes.models import Cliente, Mascota
from apps.turnos.models import Veterinario, Turno
from apps.historia_clinica.models import ConsultaMedica, RegistroVacuna, RegistroDesparasitacion
from apps.inventario.models import Categoria, Producto
from apps.ventas.models import CajaDiaria, Venta, DetalleVenta

PREFIJO_NOMBRE = "Carga Test"
PASSWORD = "CargaTest2026!"

RAZAS = {
    'CANINO': ['Labrador', 'Ovejero Alemán', 'Caniche', 'Bulldog Francés', 'Mestizo', 'Boxer'],
    'FELINO': ['Siamés', 'Persa', 'Mestizo', 'Bengalí', 'Común Europeo'],
    'AVE': ['Canario', 'Cotorra', 'Periquito'],
    'OTRO': ['Conejo', 'Hámster', 'Cobayo'],
}
MOTIVOS = [
    'Control general de salud', 'Vacunación anual', 'Vómitos y decaimiento',
    'Cojera en pata trasera', 'Chequeo pre-quirúrgico', 'Consulta dermatológica',
]


class Command(BaseCommand):
    help = (
        "Prueba de carga de datos: crea N veterinarias sintéticas (tenants independientes), "
        "cada una con clientes, mascotas, turnos, vacunas y ventas realistas, para medir "
        "hasta dónde el sistema sigue respondiendo bien con muchos tenants activos a la vez. "
        "No toca la veterinaria real ni la demo pública (usa nombres 'Carga Test N' aparte). "
        "Usar --reset para borrar todo lo generado por este comando."
    )

    def add_arguments(self, parser):
        parser.add_argument('--n', type=int, default=15, help="Cantidad de veterinarias sintéticas a crear (default: 15).")
        parser.add_argument('--clientes', type=int, default=25, help="Clientes por veterinaria (default: 25).")
        parser.add_argument('--reset', action='store_true', help="Borra todas las veterinarias 'Carga Test *' generadas antes.")

    def handle(self, *args, **options):
        if options['reset']:
            self._borrar_todo()
            return

        n = options['n']
        clientes_por_vet = options['clientes']
        fake = Faker('es_AR')

        self.stdout.write(f"Generando {n} veterinarias sintéticas con ~{clientes_por_vet} clientes cada una...")

        plan, _ = Plan.objects.get_or_create(
            nombre="Profesional",
            defaults={
                'precio_mensual': 20000, 'precio_anual': 200000,
                'max_usuarios': 10, 'max_mascotas': 1000,
                'permite_internacion': True, 'permite_multiples_veterinarios': True,
                'orden': 1,
            },
        )

        existentes = Veterinaria.objects.filter(nombre__startswith=PREFIJO_NOMBRE).count()

        for i in range(existentes + 1, existentes + n + 1):
            with transaction.atomic():
                self._crear_tenant(fake, plan, i, clientes_por_vet)
            self.stdout.write(f"  [{i - existentes}/{n}] {PREFIJO_NOMBRE} {i:03d} lista.")

        self.stdout.write(self.style.SUCCESS(
            f"\nListo: {n} veterinarias nuevas ({PREFIJO_NOMBRE} {existentes + 1:03d}..{existentes + n:03d}).\n"
            f"Login de cada una: carga{{NNN}}_admin / {PASSWORD}\n"
            f"Para borrar todo esto después: python manage.py seed_carga --reset"
        ))

    def _crear_tenant(self, fake, plan, i, clientes_por_vet):
        nombre = f"{PREFIJO_NOMBRE} {i:03d}"
        vet = Veterinaria.objects.create(
            nombre=nombre, telefono=f"381{fake.random_int(min=4000000, max=6999999)}",
            email_contacto=f"carga{i:03d}@vetersystemtest.com.ar", activo=True,
        )
        Suscripcion.objects.update_or_create(
            veterinaria=vet,
            defaults={
                'plan': plan, 'estado': 'ACTIVA',
                'fecha_inicio': timezone.now().date() - timedelta(days=30),
                'fecha_vencimiento': timezone.now().date() + timedelta(days=300),
            },
        )

        admin_user = User.objects.create_user(
            username=f"carga{i:03d}_admin", password=PASSWORD,
            first_name=fake.first_name(), last_name=fake.last_name(),
        )
        PerfilUsuario.objects.create(user=admin_user, veterinaria=vet, rol="ADMIN", is_approved=True)

        veterinarios = [
            Veterinario.objects.create(
                veterinaria=vet, nombre=fake.first_name(), apellido=fake.last_name(),
                matricula=f"MP-{fake.unique.random_int(min=1000, max=99999)}", activo=True,
            )
            for _ in range(2)
        ]

        categorias = {nombre_cat: Categoria.objects.create(veterinaria=vet, nombre=nombre_cat)
                      for nombre_cat in ['Medicamentos', 'Vacunas', 'Alimento']}
        productos = [
            Producto.objects.create(
                veterinaria=vet, nombre=n, categoria=categorias[cat], tipo=tipo,
                stock_actual=random.randint(2, 40), stock_minimo=5,
                precio_costo=costo, precio_venta=costo * 2,
            )
            for n, tipo, cat, costo in [
                ("Amoxicilina 500mg", "MEDICAMENTO", 'Medicamentos', 900),
                ("Meloxicam 0.5%", "MEDICAMENTO", 'Medicamentos', 1200),
                ("Vacuna Quíntuple", "VACUNA", 'Vacunas', 2000),
                ("Vacuna Antirrábica", "VACUNA", 'Vacunas', 1500),
                ("Alimento Balanceado 15kg", "ALIMENTO", 'Alimento', 18000),
            ]
        ]

        ahora = timezone.now()
        hoy = ahora.date()
        clientes_mascotas = []
        for _ in range(clientes_por_vet):
            cliente = Cliente.objects.create(
                veterinaria=vet, nombre=fake.first_name(), apellido=fake.last_name(),
                dni=str(fake.unique.random_int(min=1000000, max=99999999)),
                telefono=f"381{fake.random_int(min=4000000, max=6999999)}", email=fake.email(), activo=True,
            )
            mascotas = []
            for _ in range(random.randint(1, 2)):
                especie = random.choice(['CANINO', 'CANINO', 'FELINO', 'FELINO', 'AVE', 'OTRO'])
                mascotas.append(Mascota.objects.create(
                    cliente=cliente, nombre=fake.first_name(), especie=especie,
                    raza=random.choice(RAZAS[especie]), sexo=random.choice(['M', 'H']),
                    peso_kg=round(random.uniform(1.5, 40.0), 2), castrado=random.choice([True, False]),
                ))
            clientes_mascotas.append((cliente, mascotas))

        for cliente, mascotas in clientes_mascotas:
            for mascota in mascotas:
                fecha_pasada = ahora - timedelta(days=random.randint(1, 180), hours=random.randint(0, 8))
                veterinario = random.choice(veterinarios)
                turno = Turno.objects.create(
                    veterinaria=vet, mascota=mascota, veterinario=veterinario,
                    fecha_hora=fecha_pasada, motivo=random.choice(MOTIVOS), estado='COMPLETADO',
                )
                ConsultaMedica.objects.create(
                    veterinaria=vet, mascota=mascota, veterinario=veterinario, turno=turno,
                    fecha_hora=fecha_pasada, peso_actual_kg=mascota.peso_kg,
                    motivo_consulta=turno.motivo, diagnostico=fake.sentence(nb_words=5),
                    tratamiento="Reposo y medicación vía oral.",
                )
                if random.random() < 0.5:
                    Turno.objects.create(
                        veterinaria=vet, mascota=mascota, veterinario=random.choice(veterinarios),
                        fecha_hora=ahora + timedelta(days=random.randint(0, 14)),
                        motivo=random.choice(MOTIVOS), estado=random.choice(['PENDIENTE', 'CONFIRMADO']),
                    )
                RegistroVacuna.objects.create(
                    veterinaria=vet, mascota=mascota, veterinario=veterinario,
                    nombre_vacuna="Antirrábica", fecha_aplicacion=hoy - timedelta(days=340),
                    fecha_proxima_dosis=hoy + timedelta(days=random.randint(-10, 20)),
                )
                RegistroDesparasitacion.objects.create(
                    veterinaria=vet, mascota=mascota, veterinario=veterinario,
                    tipo=random.choice(['INTERNA', 'EXTERNA', 'AMBAS']), producto="Simparica",
                    fecha_aplicacion=hoy - timedelta(days=90),
                    fecha_proxima_dosis=hoy + timedelta(days=random.randint(-5, 10)),
                )

        caja = CajaDiaria.objects.create(veterinaria=vet, usuario_apertura=admin_user, monto_inicial=10000, estado='ABIERTA')
        medios = ['EFECTIVO', 'MERCADO_PAGO', 'DEBITO', 'CREDITO']
        for cliente, _ in random.sample(clientes_mascotas, k=min(10, len(clientes_mascotas))):
            producto = random.choice(productos)
            cantidad = random.randint(1, 2)
            venta = Venta.objects.create(
                veterinaria=vet, caja=caja, cliente=cliente, vendedor=admin_user,
                medio_pago=random.choice(medios), total=producto.precio_venta * cantidad,
            )
            DetalleVenta.objects.create(
                venta=venta, producto=producto, cantidad=cantidad,
                precio_unitario=producto.precio_venta, subtotal=producto.precio_venta * cantidad,
            )

    def _borrar_todo(self):
        vets = Veterinaria.objects.filter(nombre__startswith=PREFIJO_NOMBRE)
        cantidad = vets.count()
        if cantidad == 0:
            self.stdout.write("No hay veterinarias de carga para borrar.")
            return

        DetalleVenta.objects.filter(venta__veterinaria__in=vets).delete()
        usuarios_admin = User.objects.filter(username__startswith="carga", username__endswith="_admin")
        usuarios_admin.delete()
        vets.delete()
        self.stdout.write(self.style.SUCCESS(f"{cantidad} veterinarias de carga eliminadas."))
