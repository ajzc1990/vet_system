import random
from datetime import timedelta, date

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from faker import Faker

from apps.usuarios.models import Veterinaria, PerfilUsuario, Plan, Suscripcion
from apps.clientes.models import Cliente, Mascota
from apps.turnos.models import Veterinario, Turno, SolicitudTurnoWeb
from apps.historia_clinica.models import (
    ConsultaMedica, RegistroVacuna, RegistroDesparasitacion, Internacion, EvolucionInternacion,
)
from apps.inventario.models import Categoria, Producto
from apps.ventas.models import CajaDiaria, Venta, DetalleVenta

DEMO_VET_NOMBRE = "Veterinaria Demo VeterSystem"
DEMO_ADMIN_USERNAME = "demo_admin"
DEMO_VET_USERNAME = "demo_vet"
DEMO_PASSWORD = "Demo2026!"
DEMO_CLIENTE_DNI = "20111222"


class Command(BaseCommand):
    help = (
        "Crea (o reconstruye con --reset) un tenant de demostración completo, con datos "
        "realistas en todos los módulos, listo para mostrar a clientes potenciales."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset', action='store_true',
            help="Borra por completo el tenant de demo existente y lo vuelve a crear desde cero."
        )

    def handle(self, *args, **options):
        fake = Faker('es_AR')

        if options['reset']:
            self._borrar_demo_existente()

        vet = Veterinaria.objects.filter(nombre=DEMO_VET_NOMBRE).first()
        if vet:
            self.stdout.write(self.style.WARNING(
                f"El tenant de demo ya existe (id={vet.id}). Usá --reset para reconstruirlo desde cero."
            ))
            self._imprimir_credenciales(vet)
            return

        with transaction.atomic():
            vet = self._crear_veterinaria()
            plan = self._crear_plan_y_suscripcion(vet)
            admin_user, vet_user, veterinario_1, veterinario_2 = self._crear_staff(vet)
            clientes_mascotas = self._crear_clientes_y_mascotas(fake, vet)
            self._dar_acceso_portal(clientes_mascotas)
            self._crear_inventario(fake, vet)
            self._crear_turnos_y_consultas(fake, vet, clientes_mascotas, [veterinario_1, veterinario_2])
            self._crear_vacunas_y_desparasitaciones(fake, vet, clientes_mascotas, [veterinario_1, veterinario_2])
            self._crear_internaciones(fake, vet, clientes_mascotas, [veterinario_1, veterinario_2])
            self._crear_ventas(fake, vet, admin_user, clientes_mascotas)
            self._crear_solicitudes_web(fake, vet)

        self.stdout.write(self.style.SUCCESS(f"\n¡Tenant de demo creado con éxito! (Veterinaria id={vet.id})"))
        self._imprimir_credenciales(vet)

    # --------------------------------------------------------------------------
    def _borrar_demo_existente(self):
        vet = Veterinaria.objects.filter(nombre=DEMO_VET_NOMBRE).first()
        if vet:
            # DetalleVenta.producto usa on_delete=PROTECT: hay que borrar las ventas
            # explícitamente antes de borrar la Veterinaria, o el cascade a Producto falla.
            DetalleVenta.objects.filter(venta__veterinaria=vet).delete()
            vet.delete()
            self.stdout.write("Tenant de demo anterior eliminado.")
        User.objects.filter(username__in=[DEMO_ADMIN_USERNAME, DEMO_VET_USERNAME, DEMO_CLIENTE_DNI]).delete()

    def _crear_veterinaria(self):
        vet = Veterinaria.objects.create(
            nombre=DEMO_VET_NOMBRE,
            cuit_rif="30-71234567-9",
            telefono="3815551234",
            direccion="Av. Aconquija 2100, Yerba Buena, Tucumán",
            email_contacto="contacto@vetersystemdemo.com.ar",
            activo=True,
        )
        self.stdout.write(self.style.SUCCESS(f"Veterinaria creada: {vet.nombre}"))
        return vet

    def _crear_plan_y_suscripcion(self, vet):
        plan, _ = Plan.objects.get_or_create(
            nombre="Profesional",
            defaults={
                'precio_mensual': 25000,
                'max_usuarios': 10,
                'max_mascotas': 1000,
                'permite_internacion': True,
                'permite_multiples_veterinarios': True,
                'descripcion': "Plan completo con internación, portal del cliente y reserva online.",
                'orden': 1,
            }
        )
        # La señal de alta de Veterinaria ya crea una Suscripcion de PRUEBA; la
        # reemplazamos por una ACTIVA con buen margen para que la demo no muestre alertas.
        Suscripcion.objects.update_or_create(
            veterinaria=vet,
            defaults={
                'plan': plan,
                'estado': 'ACTIVA',
                'fecha_inicio': timezone.now().date() - timedelta(days=30),
                'fecha_vencimiento': timezone.now().date() + timedelta(days=60),
                'ultimo_pago_registrado': timezone.now().date() - timedelta(days=2),
            }
        )
        return plan

    def _crear_staff(self, vet):
        admin_user = User.objects.create_user(
            username=DEMO_ADMIN_USERNAME, password=DEMO_PASSWORD,
            first_name="Laura", last_name="Fernández", email="admin@vetersystemdemo.com.ar",
        )
        PerfilUsuario.objects.create(user=admin_user, veterinaria=vet, rol="ADMIN", is_approved=True, telefono="3815551111")

        vet_django_user = User.objects.create_user(
            username=DEMO_VET_USERNAME, password=DEMO_PASSWORD,
            first_name="Sofía", last_name="Herrera", email="vet@vetersystemdemo.com.ar",
        )
        PerfilUsuario.objects.create(user=vet_django_user, veterinaria=vet, rol="VET", is_approved=True, telefono="3815552222")

        veterinario_1 = Veterinario.objects.create(
            veterinaria=vet, usuario=vet_django_user, nombre="Sofía", apellido="Herrera",
            matricula="MP-1234", telefono="3815552222", email="vet@vetersystemdemo.com.ar", activo=True,
        )
        veterinario_2 = Veterinario.objects.create(
            veterinaria=vet, nombre="Martín", apellido="Ibáñez",
            matricula="MP-5678", telefono="3815553333", email="martin@vetersystemdemo.com.ar", activo=True,
        )

        self.stdout.write(self.style.SUCCESS("Staff y veterinarios creados."))
        return admin_user, vet_django_user, veterinario_1, veterinario_2

    def _crear_clientes_y_mascotas(self, fake, vet):
        razas = {
            'CANINO': ['Labrador', 'Ovejero Alemán', 'Caniche', 'Bulldog Francés', 'Mestizo', 'Boxer', 'Golden Retriever'],
            'FELINO': ['Siamés', 'Persa', 'Mestizo', 'Bengalí', 'Común Europeo'],
            'AVE': ['Canario', 'Cotorra', 'Periquito'],
            'OTRO': ['Conejo', 'Hámster', 'Cobayo'],
        }
        resultado = []

        for i in range(12):
            dni = DEMO_CLIENTE_DNI if i == 0 else str(fake.unique.random_int(min=18000000, max=50000000))
            cliente = Cliente.objects.create(
                veterinaria=vet,
                nombre=fake.first_name(),
                apellido=fake.last_name(),
                dni=dni,
                telefono=f"381{fake.random_int(min=4000000, max=6999999)}",
                email=fake.email(),
                direccion=fake.address().replace('\n', ', '),
                activo=True,
            )
            mascotas = []
            for _ in range(random.randint(1, 2)):
                especie = random.choice(['CANINO', 'CANINO', 'FELINO', 'FELINO', 'AVE', 'OTRO'])
                mascota = Mascota.objects.create(
                    cliente=cliente,
                    nombre=fake.first_name(),
                    especie=especie,
                    raza=random.choice(razas[especie]),
                    fecha_nacimiento=fake.date_of_birth(minimum_age=0, maximum_age=14),
                    sexo=random.choice(['M', 'H']),
                    peso_kg=round(random.uniform(1.5, 40.0), 2),
                    castrado=random.choice([True, False]),
                )
                mascotas.append(mascota)
            resultado.append((cliente, mascotas))

        self.stdout.write(self.style.SUCCESS(f"{len(resultado)} clientes y sus mascotas creados."))
        return resultado

    def _dar_acceso_portal(self, clientes_mascotas):
        cliente_demo, _ = clientes_mascotas[0]
        portal_user = User.objects.create_user(
            username=DEMO_CLIENTE_DNI, password=DEMO_PASSWORD,
            first_name=cliente_demo.nombre, last_name=cliente_demo.apellido,
        )
        cliente_demo.usuario = portal_user
        cliente_demo.save(update_fields=['usuario'])
        self.stdout.write(self.style.SUCCESS(f"Acceso al Portal del Cliente activado para {cliente_demo.nombre} {cliente_demo.apellido}."))

    def _crear_inventario(self, fake, vet):
        categorias_data = ['Medicamentos', 'Vacunas', 'Alimento', 'Descartables']
        categorias = {}
        for nombre in categorias_data:
            categorias[nombre], _ = Categoria.objects.get_or_create(veterinaria=vet, nombre=nombre)

        productos = [
            ("Meloxicam 0.5%", "MEDICAMENTO", 'Medicamentos', 4, 5, 1200, 2500, 90),
            ("Amoxicilina 500mg", "MEDICAMENTO", 'Medicamentos', 30, 10, 800, 1800, 180),
            ("Antiparasitario Simparica", "MEDICAMENTO", 'Medicamentos', 15, 5, 3500, 7000, 15),
            ("Vacuna Quíntuple", "VACUNA", 'Vacunas', 3, 8, 2000, 4500, 20),
            ("Vacuna Antirrábica", "VACUNA", 'Vacunas', 25, 10, 1500, 3200, 200),
            ("Vacuna Triple Felina", "VACUNA", 'Vacunas', 2, 6, 2200, 4800, 10),
            ("Alimento Balanceado Adulto 15kg", "ALIMENTO", 'Alimento', 8, 5, 18000, 32000, None),
            ("Alimento Balanceado Cachorro 3kg", "ALIMENTO", 'Alimento', 12, 5, 7000, 13500, None),
            ("Jeringas Descartables x100", "DESCARTABLE", 'Descartables', 40, 15, 5000, 9000, None),
            ("Guantes de Látex x100", "DESCARTABLE", 'Descartables', 20, 10, 4000, 7500, None),
        ]

        hoy = timezone.now().date()
        for nombre, tipo, cat, stock, minimo, costo, venta, dias_venc in productos:
            Producto.objects.create(
                veterinaria=vet, nombre=nombre, categoria=categorias[cat], tipo=tipo,
                stock_actual=stock, stock_minimo=minimo,
                precio_costo=costo, precio_venta=venta,
                fecha_vencimiento=(hoy + timedelta(days=dias_venc)) if dias_venc else None,
            )

        self.stdout.write(self.style.SUCCESS(f"{len(productos)} productos cargados (con stock bajo y vencimientos próximos incluidos)."))

    def _crear_turnos_y_consultas(self, fake, vet, clientes_mascotas, veterinarios):
        motivos = [
            'Control general de salud', 'Vacunación anual', 'Vómitos y decaimiento',
            'Cojera en pata trasera', 'Chequeo pre-quirúrgico', 'Consulta dermatológica',
        ]
        ahora = timezone.now()
        turnos_creados = 0
        consultas_creadas = 0

        for cliente, mascotas in clientes_mascotas:
            for mascota in mascotas:
                # Turno pasado ya atendido, con su consulta médica
                fecha_pasada = ahora - timedelta(days=random.randint(5, 60), hours=random.randint(0, 8))
                turno_pasado = Turno.objects.create(
                    veterinaria=vet, mascota=mascota, veterinario=random.choice(veterinarios),
                    fecha_hora=fecha_pasada, motivo=random.choice(motivos), estado='COMPLETADO',
                )
                turnos_creados += 1
                ConsultaMedica.objects.create(
                    veterinaria=vet, mascota=mascota, veterinario=turno_pasado.veterinario, turno=turno_pasado,
                    fecha_hora=fecha_pasada,
                    peso_actual_kg=mascota.peso_kg, temperatura_c=round(random.uniform(37.5, 39.2), 1),
                    frecuencia_cardiaca=random.randint(70, 140), frecuencia_respiratoria=random.randint(15, 35),
                    motivo_consulta=turno_pasado.motivo,
                    anamnesis=fake.sentence(),
                    examen_clinico="Mucosas rosadas, hidratado, buen estado general.",
                    diagnostico=fake.sentence(nb_words=5),
                    tratamiento="Se indica reposo y medicación vía oral según receta entregada.",
                )
                consultas_creadas += 1

                # Turno futuro / de hoy, todavía pendiente (para que la agenda no esté vacía)
                if random.random() < 0.6:
                    fecha_futura = ahora + timedelta(days=random.randint(0, 10), hours=random.randint(1, 6))
                    Turno.objects.create(
                        veterinaria=vet, mascota=mascota, veterinario=random.choice(veterinarios),
                        fecha_hora=fecha_futura, motivo=random.choice(motivos),
                        estado=random.choice(['PENDIENTE', 'CONFIRMADO']),
                    )
                    turnos_creados += 1

        self.stdout.write(self.style.SUCCESS(f"{turnos_creados} turnos y {consultas_creadas} consultas médicas creadas."))

    def _crear_vacunas_y_desparasitaciones(self, fake, vet, clientes_mascotas, veterinarios):
        hoy = timezone.now().date()
        vacunas_creadas = 0
        despara_creadas = 0

        for _, mascotas in clientes_mascotas:
            for mascota in mascotas:
                # Una vacuna vencida (para mostrar la alerta roja) y una próxima a vencer
                RegistroVacuna.objects.create(
                    veterinaria=vet, mascota=mascota, veterinario=random.choice(veterinarios),
                    nombre_vacuna="Quíntuple" if mascota.especie == 'CANINO' else "Triple Felina",
                    fecha_aplicacion=hoy - timedelta(days=370),
                    fecha_proxima_dosis=hoy - timedelta(days=random.randint(1, 20)),
                )
                vacunas_creadas += 1
                RegistroVacuna.objects.create(
                    veterinaria=vet, mascota=mascota, veterinario=random.choice(veterinarios),
                    nombre_vacuna="Antirrábica",
                    fecha_aplicacion=hoy - timedelta(days=340),
                    fecha_proxima_dosis=hoy + timedelta(days=random.randint(1, 6)),
                )
                vacunas_creadas += 1

                RegistroDesparasitacion.objects.create(
                    veterinaria=vet, mascota=mascota, veterinario=random.choice(veterinarios),
                    tipo=random.choice(['INTERNA', 'EXTERNA', 'AMBAS']),
                    producto="Simparica" if mascota.especie == 'CANINO' else "Drontal",
                    dosis="1 comprimido",
                    fecha_aplicacion=hoy - timedelta(days=95),
                    fecha_proxima_dosis=hoy + timedelta(days=random.randint(-5, 5)),
                )
                despara_creadas += 1

        self.stdout.write(self.style.SUCCESS(f"{vacunas_creadas} vacunas y {despara_creadas} desparasitaciones registradas."))

    def _crear_internaciones(self, fake, vet, clientes_mascotas, veterinarios):
        activa_cliente, activa_mascotas = clientes_mascotas[1]
        mascota_activa = activa_mascotas[0]

        internacion_activa = Internacion.objects.create(
            veterinaria=vet, mascota=mascota_activa, veterinario_responsable=veterinarios[0],
            box="Box 2", motivo_ingreso="Politraumatismo por accidente automovilístico, requiere observación.",
            diagnostico_ingreso="Sospecha de fractura de pelvis, sin compromiso neurológico aparente.",
            dieta_indicaciones="Reposo absoluto, dieta blanda, control de diuresis.",
            fecha_ingreso=timezone.now() - timedelta(hours=30),
            fecha_alta_estimada=timezone.now().date() + timedelta(days=2),
            costo_dia_estadia=15000,
        )
        EvolucionInternacion.objects.create(
            internacion=internacion_activa, veterinario=veterinarios[0],
            fecha_hora=timezone.now() - timedelta(hours=20), estado_general='ESTABLE',
            peso_kg=mascota_activa.peso_kg, temperatura_c=38.3, frecuencia_cardiaca=100, frecuencia_respiratoria=24,
            notas="Paciente estable, buena diuresis, tolera dieta blanda.",
            medicacion_administrada="Meloxicam 0.2mg/kg SC",
        )
        EvolucionInternacion.objects.create(
            internacion=internacion_activa, veterinario=veterinarios[0],
            fecha_hora=timezone.now() - timedelta(hours=6), estado_general='MEJORANDO',
            peso_kg=mascota_activa.peso_kg, temperatura_c=38.1, frecuencia_cardiaca=92, frecuencia_respiratoria=22,
            notas="Evolución favorable, se incorpora sin asistencia, apetito conservado.",
        )

        # Una internación histórica ya con alta, para mostrar el informe cerrado
        historica_cliente, historica_mascotas = clientes_mascotas[2]
        mascota_historica = historica_mascotas[0]
        internacion_historica = Internacion.objects.create(
            veterinaria=vet, mascota=mascota_historica, veterinario_responsable=veterinarios[1],
            box="Box 1", motivo_ingreso="Gastroenteritis aguda con deshidratación moderada.",
            diagnostico_ingreso="Gastroenteritis aguda, probable origen alimentario.",
            fecha_ingreso=timezone.now() - timedelta(days=10),
            fecha_alta_real=timezone.now() - timedelta(days=7),
            estado='ALTA',
            resumen_alta="Paciente recupera hidratación y apetito. Alta con dieta blanda progresiva y control en 7 días.",
            costo_dia_estadia=15000,
        )
        EvolucionInternacion.objects.create(
            internacion=internacion_historica, veterinario=veterinarios[1],
            fecha_hora=timezone.now() - timedelta(days=9), estado_general='MEJORANDO',
            notas="Buena respuesta a fluidoterapia, cede el vómito.",
        )

        self.stdout.write(self.style.SUCCESS("Internaciones de demo creadas (1 activa + 1 con alta)."))

    def _crear_ventas(self, fake, vet, admin_user, clientes_mascotas):
        caja = CajaDiaria.objects.create(
            veterinaria=vet, usuario_apertura=admin_user, monto_inicial=10000, estado='ABIERTA',
        )
        productos = list(Producto.objects.filter(veterinaria=vet))
        medios = ['EFECTIVO', 'MERCADO_PAGO', 'DEBITO', 'CREDITO']

        for cliente, _ in random.sample(clientes_mascotas, k=min(6, len(clientes_mascotas))):
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

        self.stdout.write(self.style.SUCCESS("Caja diaria abierta con ventas de ejemplo cargadas."))

    def _crear_solicitudes_web(self, fake, vet):
        SolicitudTurnoWeb.objects.create(
            veterinaria=vet, nombre_tutor=fake.name(), telefono=f"381{fake.random_int(min=4000000, max=6999999)}",
            email=fake.email(), nombre_mascota=fake.first_name(), especie="Perro",
            motivo="Mi perro está decaído y no quiere comer desde ayer.",
            fecha_deseada=timezone.now().date() + timedelta(days=2), franja_preferida='MANANA',
        )
        SolicitudTurnoWeb.objects.create(
            veterinaria=vet, nombre_tutor=fake.name(), telefono=f"381{fake.random_int(min=4000000, max=6999999)}",
            email=fake.email(), nombre_mascota=fake.first_name(), especie="Gato",
            motivo="Necesito turno para el esquema de vacunación.",
            fecha_deseada=timezone.now().date() + timedelta(days=4), franja_preferida='TARDE',
        )
        self.stdout.write(self.style.SUCCESS("Solicitudes de turno online de ejemplo creadas."))

    def _imprimir_credenciales(self, vet):
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("CREDENCIALES PARA LA DEMO"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"  Login de staff:   http://<tu-dominio>/login/")
        self.stdout.write(f"    Usuario (Admin): {DEMO_ADMIN_USERNAME}  /  Contraseña: {DEMO_PASSWORD}")
        self.stdout.write(f"    Usuario (Vet.):  {DEMO_VET_USERNAME}  /  Contraseña: {DEMO_PASSWORD}")
        self.stdout.write(f"  Portal del Cliente (mismo login, mismo dominio):")
        self.stdout.write(f"    Usuario: {DEMO_CLIENTE_DNI}  /  Contraseña: {DEMO_PASSWORD}")
        self.stdout.write(f"  Reserva pública de turnos (sin login):")
        self.stdout.write(f"    /turnos/reservar/{vet.id}/")
        self.stdout.write("=" * 70)
        self.stdout.write("Para reiniciar la demo con datos frescos: python manage.py seed_demo --reset\n")
