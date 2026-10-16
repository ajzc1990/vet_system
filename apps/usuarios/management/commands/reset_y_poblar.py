import random
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction, connection
from django.utils import timezone
from faker import Faker

from apps.usuarios.models import Veterinaria, PerfilUsuario, Plan, Suscripcion
from apps.clientes.models import Cliente, Mascota
from apps.turnos.models import Veterinario, Turno, SolicitudTurnoWeb
from apps.historia_clinica.models import (
    ConsultaMedica, RegistroVacuna, RegistroDesparasitacion, Internacion, EvolucionInternacion,
)
from apps.inventario.models import Categoria, Producto
from apps.ventas.models import CajaDiaria, Venta, DetalleVenta, CobroQR
from apps.compras.models import Proveedor, Compra, DetalleCompra

VET_NOMBRE = "Veterinaria San Roque"
ADMIN_USERNAME = "sanroque_admin"
VET_USERNAME = "sanroque_vet"
PASSWORD = "SanRoque2026!"
CLIENTE_PORTAL_DNI = "20333444"


class Command(BaseCommand):
    help = (
        "PELIGROSO: borra TODAS las veterinarias y todos los usuarios no-superusuario "
        "de la base, y crea una única veterinaria nueva ('Veterinaria San Roque') con "
        "datos de prueba completos en todos los módulos (clientes, mascotas, inventario, "
        "turnos, historia clínica, internaciones, compras y ventas). Requiere --confirmar."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirmar', action='store_true',
            help="Confirma que realmente querés borrar TODOS los datos existentes antes de poblar."
        )

    def handle(self, *args, **options):
        if not options['confirmar']:
            self.stdout.write(self.style.ERROR(
                "Este comando borra TODAS las veterinarias, clientes, turnos, ventas, etc. "
                "que existan en la base. Volvé a correrlo con --confirmar si estás seguro."
            ))
            return

        fake = Faker('es_AR')

        with transaction.atomic():
            self._borrar_todo()
            vet = self._crear_veterinaria()
            self._crear_plan_y_suscripcion(vet)
            admin_user, vet_user, veterinario_1, veterinario_2 = self._crear_staff(vet)
            clientes_mascotas = self._crear_clientes_y_mascotas(fake, vet)
            self._dar_acceso_portal(clientes_mascotas)
            self._crear_inventario(vet)
            self._crear_turnos_y_consultas(fake, vet, clientes_mascotas, [veterinario_1, veterinario_2])
            self._crear_vacunas_y_desparasitaciones(vet, clientes_mascotas, [veterinario_1, veterinario_2])
            self._crear_internaciones(vet, clientes_mascotas, [veterinario_1, veterinario_2])
            self._crear_proveedores_y_compras(vet, admin_user)
            self._crear_ventas(vet, admin_user, clientes_mascotas)
            self._crear_solicitudes_web(fake, vet)

        self.stdout.write(self.style.SUCCESS(f"\n¡Listo! Veterinaria '{vet.nombre}' creada (id={vet.id})."))
        self._imprimir_credenciales(vet)

    # --------------------------------------------------------------------------
    def _borrar_todo(self):
        total_vets = Veterinaria.objects.count()
        # DetalleVenta.producto, DetalleCompra.producto y CobroQR.producto usan
        # on_delete=PROTECT: Django bloquea el borrado de Producto si CUALQUIERA de
        # estos existe, sin importar que esa fila también se vaya a borrar en cascada
        # por su propio FK a Veterinaria. Por eso hay que borrarlos explícitamente
        # antes. Lo mismo pasa con Compra.proveedor (PROTECT) respecto a Proveedor.
        # "facturacion" (AFIP) ya no está en INSTALLED_APPS, así que Django no conoce
        # su FK a Venta y no la incluye en el cascade; la tabla igual existe en
        # Postgres con esa constraint, así que la vaciamos con SQL directo primero.
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = 'facturacion_facturaelectronica'
                )
            """)
            if cursor.fetchone()[0]:
                cursor.execute("DELETE FROM facturacion_facturaelectronica")

        DetalleVenta.objects.all().delete()
        DetalleCompra.objects.all().delete()
        CobroQR.objects.all().delete()
        Compra.objects.all().delete()
        Veterinaria.objects.all().delete()
        cant_usuarios, _ = User.objects.filter(is_superuser=False).delete()
        self.stdout.write(self.style.WARNING(
            f"Borradas {total_vets} veterinaria(s) y todos sus datos. "
            f"Usuarios no-superusuario eliminados: {cant_usuarios}."
        ))

    def _crear_veterinaria(self):
        vet = Veterinaria.objects.create(
            nombre=VET_NOMBRE,
            cuit_rif="30-70123456-1",
            telefono="3815550000",
            direccion="San Martín 850, San Miguel de Tucumán",
            email_contacto="contacto@veterinariasanroque.com.ar",
            activo=True,
        )
        self.stdout.write(self.style.SUCCESS(f"Veterinaria creada: {vet.nombre}"))
        return vet

    def _crear_plan_y_suscripcion(self, vet):
        plan, _ = Plan.objects.get_or_create(
            nombre="Profesional",
            defaults={
                'precio_mensual': 25000,
                'max_usuarios': 15,
                'max_mascotas': 1000,
                'permite_internacion': True,
                'permite_multiples_veterinarios': True,
                'descripcion': "Plan completo con internación, portal del cliente y reserva online.",
                'orden': 1,
            }
        )
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
            username=ADMIN_USERNAME, password=PASSWORD,
            first_name="Agustín", last_name="Zelaya", email="admin@veterinariasanroque.com.ar",
        )
        PerfilUsuario.objects.create(user=admin_user, veterinaria=vet, rol="ADMIN", is_approved=True, telefono="3815550001")

        vet_django_user = User.objects.create_user(
            username=VET_USERNAME, password=PASSWORD,
            first_name="Carla", last_name="Gómez", email="vet@veterinariasanroque.com.ar",
        )
        PerfilUsuario.objects.create(user=vet_django_user, veterinaria=vet, rol="VET", is_approved=True, telefono="3815550002")

        veterinario_1 = Veterinario.objects.create(
            veterinaria=vet, usuario=vet_django_user, nombre="Carla", apellido="Gómez",
            matricula="MP-9001", telefono="3815550002", email="vet@veterinariasanroque.com.ar", activo=True,
        )
        veterinario_2 = Veterinario.objects.create(
            veterinaria=vet, nombre="Diego", apellido="Paz",
            matricula="MP-9002", telefono="3815550003", email="diego@veterinariasanroque.com.ar", activo=True,
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

        for i in range(15):
            dni = CLIENTE_PORTAL_DNI if i == 0 else str(fake.unique.random_int(min=18000000, max=50000000))
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
        cliente_portal, _ = clientes_mascotas[0]
        portal_user = User.objects.create_user(
            username=CLIENTE_PORTAL_DNI, password=PASSWORD,
            first_name=cliente_portal.nombre, last_name=cliente_portal.apellido,
        )
        cliente_portal.usuario = portal_user
        cliente_portal.save(update_fields=['usuario'])
        self.stdout.write(self.style.SUCCESS(f"Acceso al Portal del Cliente activado para {cliente_portal.nombre} {cliente_portal.apellido}."))

    def _crear_inventario(self, vet):
        categorias_data = ['Medicamentos', 'Vacunas', 'Alimento', 'Descartables', 'Otros']
        categorias = {}
        for nombre in categorias_data:
            categorias[nombre], _ = Categoria.objects.get_or_create(veterinaria=vet, nombre=nombre)

        # (nombre, tipo, categoria, stock, stock_minimo, precio_costo, precio_venta, dias_hasta_vencer)
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
            ("Collar Isabelino", "OTRO", 'Otros', 6, 5, 1500, 3200, None),
            ("Shampoo Antipulgas", "OTRO", 'Otros', 10, 5, 3500, 6800, None),
            ("Consulta General", "SERVICIO", 'Otros', 0, 0, 0, 8000, None),
            ("Vacunación (aplicación)", "SERVICIO", 'Otros', 0, 0, 0, 3000, None),
        ]

        hoy = timezone.now().date()
        for nombre, tipo, cat, stock, minimo, costo, venta, dias_venc in productos:
            Producto.objects.create(
                veterinaria=vet, nombre=nombre, categoria=categorias[cat], tipo=tipo,
                stock_actual=stock, stock_minimo=minimo,
                precio_costo=costo, precio_venta=venta,
                fecha_vencimiento=(hoy + timedelta(days=dias_venc)) if dias_venc else None,
            )

        self.stdout.write(self.style.SUCCESS(
            f"{len(productos)} productos cargados (incluye 2 Servicios, stock bajo y vencimientos próximos)."
        ))

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

                if random.random() < 0.6:
                    fecha_futura = ahora + timedelta(days=random.randint(1, 10), hours=random.randint(1, 6))
                    Turno.objects.create(
                        veterinaria=vet, mascota=mascota, veterinario=random.choice(veterinarios),
                        fecha_hora=fecha_futura, motivo=random.choice(motivos),
                        estado=random.choice(['PENDIENTE', 'CONFIRMADO']),
                    )
                    turnos_creados += 1

        # Turnos de HOY, uno por cada estado posible, para probar la agenda sin esperar.
        _, mascotas_0 = clientes_mascotas[0]
        for i, estado in enumerate(['PENDIENTE', 'CONFIRMADO', 'COMPLETADO', 'CANCELADO']):
            Turno.objects.create(
                veterinaria=vet, mascota=mascotas_0[0], veterinario=veterinarios[i % 2],
                fecha_hora=ahora.replace(hour=9 + i * 2, minute=0, second=0, microsecond=0),
                motivo=random.choice(motivos), estado=estado,
            )
            turnos_creados += 1

        self.stdout.write(self.style.SUCCESS(f"{turnos_creados} turnos y {consultas_creadas} consultas médicas creadas."))

    def _crear_vacunas_y_desparasitaciones(self, vet, clientes_mascotas, veterinarios):
        hoy = timezone.now().date()
        vacunas_creadas = 0
        despara_creadas = 0

        for _, mascotas in clientes_mascotas:
            for mascota in mascotas:
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

    def _crear_internaciones(self, vet, clientes_mascotas, veterinarios):
        _, activa_mascotas = clientes_mascotas[1]
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

        _, historica_mascotas = clientes_mascotas[2]
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

        self.stdout.write(self.style.SUCCESS("Internaciones creadas (1 activa + 1 con alta)."))

    def _crear_proveedores_y_compras(self, vet, admin_user):
        proveedor_1 = Proveedor.objects.create(
            veterinaria=vet, nombre="Distribuidora VetFarma SRL", contacto="Roberto Sosa",
            telefono="3815559000", email="ventas@vetfarma.com.ar", cuit="30-65432109-8",
        )
        Proveedor.objects.create(
            veterinaria=vet, nombre="Alimentos del Sur SA", contacto="Marina López",
            telefono="3815559111", email="pedidos@alimentosdelsur.com.ar",
        )

        productos_para_reponer = list(
            Producto.objects.filter(veterinaria=vet, tipo__in=['MEDICAMENTO', 'VACUNA'])
        )
        compra = Compra.objects.create(
            veterinaria=vet, proveedor=proveedor_1, usuario=admin_user,
            numero_factura="A-0001-00012345", total=0,
            observaciones="Reposición mensual de medicamentos y vacunas.",
        )
        total = 0
        for producto in random.sample(productos_para_reponer, k=min(4, len(productos_para_reponer))):
            cantidad = random.randint(5, 20)
            detalle = DetalleCompra.objects.create(
                compra=compra, producto=producto, cantidad=cantidad,
                precio_unitario=producto.precio_costo or 1000,
            )
            total += detalle.subtotal
        compra.total = total
        compra.save(update_fields=['total'])

        self.stdout.write(self.style.SUCCESS("Proveedores y una compra de ejemplo cargados (con su reposición de stock)."))

    def _crear_ventas(self, vet, admin_user, clientes_mascotas):
        caja = CajaDiaria.objects.create(
            veterinaria=vet, usuario_apertura=admin_user, monto_inicial=10000, estado='ABIERTA',
        )
        productos = list(Producto.objects.filter(veterinaria=vet))
        medios = ['EFECTIVO', 'TRANSFERENCIA', 'DEBITO', 'CREDITO']

        for cliente, _ in random.sample(clientes_mascotas, k=min(8, len(clientes_mascotas))):
            producto = random.choice(productos)
            cantidad = 1 if producto.es_servicio else random.randint(1, 2)
            venta = Venta.objects.create(
                veterinaria=vet, caja=caja, cliente=cliente, vendedor=admin_user,
                medio_pago=random.choice(medios), total=producto.precio_venta * cantidad,
            )
            DetalleVenta.objects.create(
                venta=venta, producto=producto, cantidad=cantidad,
                precio_unitario=producto.precio_venta,
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
        self.stdout.write(self.style.SUCCESS("CREDENCIALES DE VETERINARIA SAN ROQUE"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"  Login de staff:   /login/")
        self.stdout.write(f"    Usuario (Admin): {ADMIN_USERNAME}  /  Contraseña: {PASSWORD}")
        self.stdout.write(f"    Usuario (Vet.):  {VET_USERNAME}  /  Contraseña: {PASSWORD}")
        self.stdout.write(f"  Portal del Cliente (mismo login, mismo dominio):")
        self.stdout.write(f"    Usuario: {CLIENTE_PORTAL_DNI}  /  Contraseña: {PASSWORD}")
        self.stdout.write(f"  Reserva pública de turnos (sin login):")
        self.stdout.write(f"    /turnos/reservar/{vet.id}/")
        self.stdout.write("=" * 70 + "\n")
