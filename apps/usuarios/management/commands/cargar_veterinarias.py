import random
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from faker import Faker

from apps.usuarios.models import Veterinaria, PerfilUsuario


class Command(BaseCommand):
    help = 'Carga veterinarias y usuarios con perfiles (Admin, Vet, Recepción)'

    def handle(self, *args, **kwargs):
        fake = Faker('es_AR')

        self.stdout.write("Poblando clínicas y equipo de trabajo...")

        # 1. Crear 3 Veterinarias de prueba
        vets_data = [
            {"nombre": "Veterinaria San Martín", "direccion": "Av. Mitre 1234, San Miguel de Tucumán"},
            {"nombre": "Centro Veterinario Yerba Buena", "direccion": "Av. Aconquija 2100, Yerba Buena"},
            {"nombre": "Clínica Veterinaria Tafí", "direccion": "San Martín 450, Tafí del Valle"}
        ]

        veterinarias = []
        for v_info in vets_data:
            cuit_generado = f"30-{fake.random_int(min=10000000, max=99999999)}-{random.randint(0, 9)}"
            vet, created = Veterinaria.objects.get_or_create(
                nombre=v_info["nombre"],
                defaults={
                    'cuit_rif': cuit_generado,
                    'telefono': f"381{fake.random_int(min=4000000, max=6999999)}",
                    'direccion': v_info["direccion"],
                    'email_contacto': fake.company_email(),
                    'activo': True
                }
            )
            veterinarias.append(vet)
            accion = "Creada" if created else "Existente"
            self.stdout.write(self.style.SUCCESS(f"[{accion}] Veterinaria: {vet.nombre}"))

        # 2. Crear Usuarios y Perfiles para cada Veterinaria
        roles_distribucion = [
            ('ADMIN', 'admin'),
            ('VET', 'vet1'),
            ('VET', 'vet2'),
            ('RECEPCION', 'recep')
        ]

        usuarios_creados = 0

        for vet in veterinarias:
            slug_vet = vet.nombre.lower().replace(' ', '_').replace('á', 'a').replace('í', 'i')[:10]

            for rol, prefix in roles_distribucion:
                username = f"{prefix}_{slug_vet}"

                if not User.objects.filter(username=username).exists():
                    first_name = fake.first_name()
                    last_name = fake.last_name()
                    email = fake.email()

                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        password='Admin123!',
                        first_name=first_name,
                        last_name=last_name
                    )

                    PerfilUsuario.objects.create(
                        user=user,
                        veterinaria=vet,
                        rol=rol,
                        telefono=f"381{fake.random_int(min=4000000, max=6999999)}"
                    )
                    usuarios_creados += 1

        self.stdout.write(self.style.SUCCESS(
            f"\n¡Éxito! Se procesaron {len(veterinarias)} veterinarias y se crearon {usuarios_creados} usuarios/perfiles."
        ))
        self.stdout.write("Contraseña por defecto para todos los usuarios: Admin123!")