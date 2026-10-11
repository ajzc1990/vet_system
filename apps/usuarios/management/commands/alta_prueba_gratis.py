import re
import secrets
import string
import unicodedata
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.usuarios.models import Veterinaria, PerfilUsuario, Plan, Suscripcion

DIAS_PRUEBA = 30

# Editar esta lista en cada tanda de alta de prospectos nuevos.
VETERINARIAS = [
    {"nombre": "PachaVet Clínica Veterinaria", "direccion": "Av. Eva Perón 52, Banda del Río Salí", "telefono": "3813583968"},
    {"nombre": "Veterinaria Lastenia Dr. Diaz Carrasco", "direccion": "Av. Eva Perón, Banda del Río Salí", "telefono": "3815046804"},
    {"nombre": "Cachafaz Clinica Veterinaria", "direccion": "Av. San Martín 271, Banda del Río Salí", "telefono": "3814267920"},
    {"nombre": "Veterinaria Alelí", "direccion": "República 172, Banda del Río Salí", "telefono": "3815729506"},
    {"nombre": "Veterinaria MichiCan", "direccion": "Mario Bravo 147, Banda del Río Salí", "telefono": "3813590888"},
    {"nombre": "Veterinaria La Banda", "direccion": "Av. Monseñor Jesús Díaz 415, Banda del Río Salí", "telefono": "3814159626"},
    {"nombre": "Pet Shop Arboleda", "direccion": "Ruta 306 Barrio Arboleda, Banda del Río Salí", "telefono": "3814684447"},
    {"nombre": "Veterinaria Corazón Animal II", "direccion": "Los Vallistos, RP306 Km 7, Banda del Río Salí", "telefono": "3813449805"},
]


def _username_desde_nombre(nombre, existentes):
    sin_acentos = unicodedata.normalize('NFKD', nombre).encode('ascii', 'ignore').decode('ascii')
    base = re.sub(r'[^a-z0-9]', '', sin_acentos.lower())[:20] or "clinica"
    username = f"{base}_admin"
    i = 2
    while username in existentes or User.objects.filter(username=username).exists():
        username = f"{base}{i}_admin"
        i += 1
    existentes.add(username)
    return username


def _password_generada():
    alfabeto = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alfabeto) for _ in range(10))


class Command(BaseCommand):
    help = (
        "Da de alta en producción una tanda de veterinarias prospecto con su usuario "
        "ADMIN ya aprobado y un mes de prueba gratis, listas para entregarle el acceso "
        "al dueño. Imprime usuario/contraseña de cada una al final (no se guardan en "
        "ningún otro lado: copiarlas en el momento)."
    )

    def handle(self, *args, **options):
        plan = Plan.objects.filter(activo=True).order_by('orden', 'precio_mensual').first()
        if not plan:
            self.stderr.write(self.style.ERROR("No hay ningún Plan activo cargado; no se puede asignar la prueba."))
            return

        usernames_usados = set()
        credenciales = []

        for datos in VETERINARIAS:
            nombre = datos["nombre"]
            if Veterinaria.objects.filter(nombre=nombre).exists():
                self.stdout.write(self.style.WARNING(f"Ya existe una veterinaria llamada '{nombre}', la salteo."))
                continue

            with transaction.atomic():
                vet = Veterinaria.objects.create(
                    nombre=nombre,
                    direccion=datos.get("direccion", ""),
                    telefono=datos.get("telefono", ""),
                    activo=True,
                )

                username = _username_desde_nombre(nombre, usernames_usados)
                password = _password_generada()
                user = User.objects.create_user(username=username, password=password)
                PerfilUsuario.objects.create(user=user, veterinaria=vet, rol="ADMIN", is_approved=True)

                hoy = timezone.localdate()
                Suscripcion.objects.update_or_create(
                    veterinaria=vet,
                    defaults={
                        "plan": plan,
                        "estado": "PRUEBA",
                        "fecha_inicio": hoy,
                        "fecha_vencimiento": hoy + timedelta(days=DIAS_PRUEBA),
                    },
                )

            credenciales.append((nombre, username, password))
            self.stdout.write(self.style.SUCCESS(f"Creada: {nombre}"))

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS(f"CREDENCIALES ({DIAS_PRUEBA} días de prueba, plan {plan.nombre})"))
        self.stdout.write("=" * 70)
        for nombre, username, password in credenciales:
            self.stdout.write(f"{nombre}")
            self.stdout.write(f"  Usuario: {username}   Contraseña: {password}")
        self.stdout.write("=" * 70)
        self.stdout.write("Login de staff: https://vetersystem.com/login/\n")
