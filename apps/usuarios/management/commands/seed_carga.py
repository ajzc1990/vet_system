import random
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from faker import Faker

from apps.usuarios.models import Veterinaria, PerfilUsuario
from apps.clientes.models import Cliente, Mascota
from apps.turnos.models import Veterinario, Turno
from apps.historia_clinica.models import ConsultaMedica
from apps.inventario.models import Categoria, Producto

PREFIJO_CARGA = "CARGA TEST "

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
PRODUCTOS = [
    ("Meloxicam 0.5%", "MEDICAMENTO", 4, 5, 1200, 2500),
    ("Amoxicilina 500mg", "MEDICAMENTO", 30, 10, 800, 1800),
    ("Vacuna Quíntuple", "VACUNA", 3, 8, 2000, 4500),
    ("Vacuna Antirrábica", "VACUNA", 25, 10, 1500, 3200),
    ("Alimento Balanceado Adulto 15kg", "ALIMENTO", 8, 5, 18000, 32000),
    ("Alimento Balanceado Cachorro 3kg", "ALIMENTO", 12, 5, 7000, 13500),
    ("Jeringas Descartables x100", "DESCARTABLE", 40, 15, 5000, 9000),
    ("Guantes de Látex x100", "DESCARTABLE", 20, 10, 4000, 7500),
]
PASSWORD = "CargaTest2026!"


class Command(BaseCommand):
    help = (
        "Carga N veterinarias sintéticas con datos realistas (para medir hasta dónde "
        "aguanta la infraestructura). Usar --borrar para eliminar todo lo que creó, sin "
        "tocar la veterinaria demo ni ninguna otra."
    )

    def add_arguments(self, parser):
        parser.add_argument('--cantidad', type=int, default=100)
        parser.add_argument('--clientes-por-vet', type=int, default=40)
        parser.add_argument('--borrar', action='store_true')

    def handle(self, *args, **options):
        if options['borrar']:
            self._borrar_todo()
            return

        cantidad = options['cantidad']
        n_clientes = options['clientes_por_vet']
        fake = Faker('es_AR')
        Faker.seed(0)

        dni_counter = 90000000
        usernames = []

        for i in range(cantidad):
            with transaction.atomic():
                vet = Veterinaria.objects.create(
                    nombre=f"{PREFIJO_CARGA}{i:05d}",
                    cuit_rif=f"30-{70000000 + i}-9",
                    telefono="3815550000",
                    direccion=fake.address().replace('\n', ', '),
                    email_contacto=f"carga{i:05d}@test.local",
                    activo=True,
                )

                username = f"carga_{i:05d}_admin"
                admin_user = User.objects.create_user(username=username, password=PASSWORD)
                PerfilUsuario.objects.create(user=admin_user, veterinaria=vet, rol="ADMIN", is_approved=True)
                usernames.append(username)

                veterinarios = Veterinario.objects.bulk_create([
                    Veterinario(veterinaria=vet, usuario=admin_user, nombre="Sofía", apellido="Herrera",
                                 matricula=f"MP-{i:05d}A", telefono="3815551111", activo=True),
                    Veterinario(veterinaria=vet, nombre="Martín", apellido="Ibáñez",
                                 matricula=f"MP-{i:05d}B", telefono="3815552222", activo=True),
                ])

                clientes = Cliente.objects.bulk_create([
                    Cliente(
                        veterinaria=vet, nombre=fake.first_name(), apellido=fake.last_name(),
                        dni=str(dni_counter + j), telefono=f"381{random.randint(4000000, 6999999)}",
                        email=fake.email(), direccion=fake.address().replace('\n', ', '), activo=True,
                    )
                    for j in range(n_clientes)
                ])
                dni_counter += n_clientes

                mascotas = []
                for cliente in clientes:
                    for _ in range(random.randint(1, 2)):
                        especie = random.choice(['CANINO', 'CANINO', 'FELINO', 'FELINO', 'AVE', 'OTRO'])
                        mascotas.append(Mascota(
                            cliente=cliente, nombre=fake.first_name(), especie=especie,
                            raza=random.choice(RAZAS[especie]),
                            fecha_nacimiento=fake.date_of_birth(minimum_age=0, maximum_age=14),
                            sexo=random.choice(['M', 'H']), peso_kg=round(random.uniform(1.5, 40.0), 2),
                            castrado=random.choice([True, False]),
                        ))
                mascotas = Mascota.objects.bulk_create(mascotas)

                categoria = Categoria.objects.create(veterinaria=vet, nombre="General")
                Producto.objects.bulk_create([
                    Producto(veterinaria=vet, nombre=nombre, categoria=categoria, tipo=tipo,
                              stock_actual=stock, stock_minimo=minimo, precio_costo=costo, precio_venta=venta)
                    for nombre, tipo, stock, minimo, costo, venta in PRODUCTOS
                ])

                ahora = timezone.now()
                turnos_pasados = []
                turnos_futuros = []
                for mascota in mascotas:
                    turnos_pasados.append(Turno(
                        veterinaria=vet, mascota=mascota, veterinario=random.choice(veterinarios),
                        fecha_hora=ahora - timedelta(days=random.randint(5, 60), hours=random.randint(0, 8)),
                        motivo=random.choice(MOTIVOS), estado='COMPLETADO',
                    ))
                    if random.random() < 0.6:
                        es_hoy = random.random() < 0.4
                        delta = timedelta(hours=random.randint(1, 6)) if es_hoy else timedelta(days=random.randint(1, 10))
                        turnos_futuros.append(Turno(
                            veterinaria=vet, mascota=mascota, veterinario=random.choice(veterinarios),
                            fecha_hora=ahora + delta, motivo=random.choice(MOTIVOS),
                            estado=random.choice(['PENDIENTE', 'CONFIRMADO']),
                        ))
                turnos_pasados = Turno.objects.bulk_create(turnos_pasados)
                Turno.objects.bulk_create(turnos_futuros)

                ConsultaMedica.objects.bulk_create([
                    ConsultaMedica(
                        veterinaria=vet, mascota=t.mascota, veterinario=t.veterinario, turno=t,
                        fecha_hora=t.fecha_hora, peso_actual_kg=t.mascota.peso_kg,
                        temperatura_c=round(random.uniform(37.5, 39.2), 1),
                        frecuencia_cardiaca=random.randint(70, 140), frecuencia_respiratoria=random.randint(15, 35),
                        motivo_consulta=t.motivo, anamnesis=fake.sentence(),
                        examen_clinico="Mucosas rosadas, hidratado, buen estado general.",
                        diagnostico=fake.sentence(nb_words=5),
                        tratamiento="Se indica reposo y medicación vía oral según receta entregada.",
                    )
                    for t in turnos_pasados
                ])

            if (i + 1) % 10 == 0 or (i + 1) == cantidad:
                self.stdout.write(f"  ... {i + 1}/{cantidad} veterinarias cargadas")

        self.stdout.write(self.style.SUCCESS(f"\n{cantidad} veterinarias de carga creadas."))
        self.stdout.write(f"Usuario de prueba: {usernames[0]}  /  Contraseña: {PASSWORD}")
        self.stdout.write(f"Patrón de usuarios: carga_00000_admin .. carga_{cantidad - 1:05d}_admin (misma contraseña)")

    def _borrar_todo(self):
        vets = Veterinaria.objects.filter(nombre__startswith=PREFIJO_CARGA)
        total = vets.count()
        if total == 0:
            self.stdout.write("No hay veterinarias de carga para borrar.")
            return
        User.objects.filter(username__startswith="carga_").delete()
        vets.delete()
        self.stdout.write(self.style.SUCCESS(f"{total} veterinarias de carga eliminadas."))
