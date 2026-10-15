import random
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from faker import Faker

from apps.usuarios.models import Veterinaria, PerfilUsuario
from apps.clientes.models import Cliente, Mascota
from apps.turnos.models import Veterinario, Turno
from apps.historia_clinica.models import ConsultaMedica, RegistroVacuna, RegistroDesparasitacion
from apps.inventario.models import Categoria, Producto
from apps.ventas.models import CajaDiaria

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
    ("Meloxicam 0.5%", "MEDICAMENTO", 4, 5, 1200, 2500, 90),
    ("Amoxicilina 500mg", "MEDICAMENTO", 30, 10, 800, 1800, 180),
    ("Antiparasitario Simparica", "MEDICAMENTO", 15, 5, 3500, 7000, 15),
    ("Vacuna Quíntuple", "VACUNA", 8, 8, 2000, 4500, 20),
    ("Vacuna Antirrábica", "VACUNA", 25, 10, 1500, 3200, 200),
    ("Alimento Balanceado Adulto 15kg", "ALIMENTO", 8, 5, 18000, 32000, None),
    ("Alimento Balanceado Cachorro 3kg", "ALIMENTO", 12, 5, 7000, 13500, None),
    ("Shampoo Antipulgas", "OTRO", 10, 4, 3200, 6800, None),
    ("Collar Isabelino", "OTRO", 6, 3, 1600, 3200, None),
    ("Jeringas Descartables x100", "DESCARTABLE", 40, 15, 5000, 9000, None),
]


class Command(BaseCommand):
    help = (
        "Carga datos de prueba realistas (clientes, mascotas, turnos, consultas, "
        "inventario, caja abierta) en una veterinaria YA EXISTENTE, reusando su "
        "staff actual. Pensado para el tenant de ensayo, no crea tenants nuevos."
    )

    def add_arguments(self, parser):
        parser.add_argument('--nombre', default='Clínica Ensayo')
        parser.add_argument('--clientes', type=int, default=15)

    def handle(self, *args, **options):
        fake = Faker('es_AR')
        nombre = options['nombre']
        vet = Veterinaria.objects.filter(nombre=nombre).first()
        if not vet:
            raise CommandError(f"No existe ninguna veterinaria llamada '{nombre}'.")

        veterinarios = list(Veterinario.objects.filter(veterinaria=vet, activo=True))
        if not veterinarios:
            perfiles_vet = PerfilUsuario.objects.filter(veterinaria=vet, rol='VET')
            for perfil in perfiles_vet:
                v = Veterinario.objects.create(
                    veterinaria=vet, usuario=perfil.user,
                    nombre=perfil.user.first_name or perfil.user.username,
                    apellido=perfil.user.last_name or '',
                    matricula=f"MP-{perfil.user.id:04d}", activo=True,
                )
                veterinarios.append(v)
            if not veterinarios:
                veterinarios = [Veterinario.objects.create(
                    veterinaria=vet, nombre="Sofía", apellido="Herrera", matricula="MP-0001", activo=True,
                )]

        self.stdout.write(f"Usando {len(veterinarios)} veterinario(s): {[str(v) for v in veterinarios]}")

        # --- Clientes y mascotas ---
        dni_base = 30000000 + Cliente.objects.count() * 7
        clientes_mascotas = []
        for i in range(options['clientes']):
            cliente = Cliente.objects.create(
                veterinaria=vet, nombre=fake.first_name(), apellido=fake.last_name(),
                dni=str(dni_base + i), telefono=f"381{random.randint(4000000, 6999999)}",
                email=fake.email(), direccion=fake.address().replace('\n', ', '), activo=True,
            )
            mascotas = []
            for _ in range(random.randint(1, 2)):
                especie = random.choice(['CANINO', 'CANINO', 'FELINO', 'FELINO', 'AVE', 'OTRO'])
                mascotas.append(Mascota.objects.create(
                    cliente=cliente, nombre=fake.first_name(), especie=especie,
                    raza=random.choice(RAZAS[especie]),
                    fecha_nacimiento=fake.date_of_birth(minimum_age=0, maximum_age=14),
                    sexo=random.choice(['M', 'H']), peso_kg=round(random.uniform(1.5, 40.0), 2),
                    castrado=random.choice([True, False]),
                ))
            clientes_mascotas.append((cliente, mascotas))
        self.stdout.write(self.style.SUCCESS(f"{len(clientes_mascotas)} clientes y sus mascotas creados."))

        # --- Inventario ---
        categoria, _ = Categoria.objects.get_or_create(veterinaria=vet, nombre="General")
        hoy = timezone.now().date()
        for nombre_p, tipo, stock, minimo, costo, venta, dias_venc in PRODUCTOS:
            Producto.objects.get_or_create(
                veterinaria=vet, nombre=nombre_p, defaults=dict(
                    categoria=categoria, tipo=tipo, stock_actual=stock, stock_minimo=minimo,
                    precio_costo=costo, precio_venta=venta,
                    fecha_vencimiento=(hoy + timedelta(days=dias_venc)) if dias_venc else None,
                ),
            )
        self.stdout.write(self.style.SUCCESS(f"{len(PRODUCTOS)} productos cargados (o ya existentes)."))

        # --- Turnos y consultas ---
        ahora = timezone.now()
        turnos_creados = 0
        consultas_creadas = 0
        vacunas_creadas = 0
        for cliente, mascotas in clientes_mascotas:
            for mascota in mascotas:
                fecha_pasada = ahora - timedelta(days=random.randint(5, 60), hours=random.randint(0, 8))
                turno_pasado = Turno.objects.create(
                    veterinaria=vet, mascota=mascota, veterinario=random.choice(veterinarios),
                    fecha_hora=fecha_pasada, motivo=random.choice(MOTIVOS), estado='COMPLETADO',
                )
                turnos_creados += 1
                ConsultaMedica.objects.create(
                    veterinaria=vet, mascota=mascota, veterinario=turno_pasado.veterinario, turno=turno_pasado,
                    fecha_hora=fecha_pasada,
                    peso_actual_kg=mascota.peso_kg, temperatura_c=round(random.uniform(37.5, 39.2), 1),
                    frecuencia_cardiaca=random.randint(70, 140), frecuencia_respiratoria=random.randint(15, 35),
                    motivo_consulta=turno_pasado.motivo, anamnesis=fake.sentence(),
                    examen_clinico="Mucosas rosadas, hidratado, buen estado general.",
                    diagnostico=fake.sentence(nb_words=5),
                    tratamiento="Se indica reposo y medicación vía oral según receta entregada.",
                )
                consultas_creadas += 1

                if random.random() < 0.6:
                    es_hoy = random.random() < 0.4
                    delta = timedelta(hours=random.randint(1, 6)) if es_hoy else timedelta(days=random.randint(1, 10))
                    Turno.objects.create(
                        veterinaria=vet, mascota=mascota, veterinario=random.choice(veterinarios),
                        fecha_hora=ahora + delta, motivo=random.choice(MOTIVOS),
                        estado=random.choice(['PENDIENTE', 'CONFIRMADO']),
                    )
                    turnos_creados += 1

                if random.random() < 0.5:
                    RegistroVacuna.objects.create(
                        veterinaria=vet, mascota=mascota, veterinario=random.choice(veterinarios),
                        nombre_vacuna="Quíntuple" if mascota.especie == 'CANINO' else "Triple Felina",
                        fecha_aplicacion=hoy - timedelta(days=340),
                        fecha_proxima_dosis=hoy + timedelta(days=random.randint(-5, 20)),
                    )
                    vacunas_creadas += 1

        self.stdout.write(self.style.SUCCESS(f"{turnos_creados} turnos, {consultas_creadas} consultas, {vacunas_creadas} vacunas."))

        # --- Caja abierta ---
        admin_perfil = PerfilUsuario.objects.filter(veterinaria=vet, rol='ADMIN').first()
        if admin_perfil and not CajaDiaria.objects.filter(veterinaria=vet, estado='ABIERTA').exists():
            CajaDiaria.objects.create(veterinaria=vet, usuario_apertura=admin_perfil.user, monto_inicial=10000, estado='ABIERTA')
            self.stdout.write(self.style.SUCCESS("Caja diaria abierta (lista para probar Nueva Venta)."))
        else:
            self.stdout.write("Ya había una caja abierta, no se tocó.")

        self.stdout.write(self.style.SUCCESS(f"\n¡Listo! '{nombre}' ahora tiene datos para probar."))
