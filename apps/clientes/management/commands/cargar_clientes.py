import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.apps import apps
from faker import Faker

from apps.usuarios.models import Veterinaria
from apps.clientes.models import Cliente, Mascota

User = get_user_model()


class Command(BaseCommand):
    help = 'Carga Clientes, Mascotas e Historias Clínicas'

    def handle(self, *args, **kwargs):
        fake = Faker('es_AR')

        veterinarias = list(Veterinaria.objects.filter(activo=True))
        if not veterinarias:
            self.stdout.write(self.style.ERROR(
                "No hay veterinarias registradas. Ejecutá primero: python manage.py cargar_veterinarias"
            ))
            return

        # Obtener dinámicamente modelos de la app historia_clinica si existen
        HistoriaClinica = None
        ConsultaMedica = None
        try:
            HistoriaClinica = apps.get_model('historia_clinica', 'HistoriaClinica')
            ConsultaMedica = apps.get_model('historia_clinica', 'ConsultaMedica')
        except LookupError:
            pass

        usuarios_vets = list(User.objects.all())

        self.stdout.write("Generando 50 Clientes con sus Mascotas...")

        razas = {
            'CANINO': ['Labrador', 'Ovejero Alemán', 'Caniche', 'Bulldog', 'Mestizo', 'Boxer', 'Golden Retriever'],
            'FELINO': ['Siamés', 'Persa', 'Mestizo', 'Bengalí', 'Sphynx'],
            'AVE': ['Canario', 'Cotorra', 'Loro', 'Perico'],
            'OTRO': ['Conejo', 'Hámster', 'Cobayo']
        }

        motivos_lista = [
            'Vacunación y desparasitación anual',
            'Control general de salud',
            'Infección oídos / Otitis',
            'Problemas gastrointestinales (vómitos)',
            'Cojera en pata trasera',
            'Alergia dermatológica / Picazón'
        ]

        clientes_creados = 0
        mascotas_creadas = 0
        consultas_creadas = 0

        for _ in range(50):
            vet_asignada = random.choice(veterinarias)

            cliente = Cliente.objects.create(
                veterinaria=vet_asignada,
                nombre=fake.first_name(),
                apellido=fake.last_name(),
                dni=str(fake.unique.random_int(min=18000000, max=50000000)),
                telefono=f"381{fake.random_int(min=4000000, max=6999999)}",
                email=fake.email(),
                direccion=fake.address(),
                activo=True
            )
            clientes_creados += 1

            cant_mascotas = random.randint(1, 3)
            for _ in range(cant_mascotas):
                especie_elegida = random.choice(['CANINO', 'FELINO', 'CANINO', 'FELINO', 'AVE', 'OTRO'])
                raza_elegida = random.choice(razas[especie_elegida])

                mascota = Mascota.objects.create(
                    cliente=cliente,
                    nombre=fake.first_name(),
                    especie=especie_elegida,
                    raza=raza_elegida,
                    fecha_nacimiento=fake.date_of_birth(minimum_age=1, maximum_age=14),
                    sexo=random.choice(['M', 'H']),
                    peso_kg=round(random.uniform(1.5, 42.0), 2),
                    castrado=random.choice([True, False]),
                    observaciones=fake.sentence() if random.choice([True, False]) else None
                )
                mascotas_creadas += 1

                # Si existen los modelos de HistoriaClinica, cargamos atenciones
                if HistoriaClinica and ConsultaMedica:
                    historia, _ = HistoriaClinica.objects.get_or_create(
                        mascota=mascota,
                        defaults={
                            'alergias': "Ninguna conocida" if random.choice([True, False]) else "Sensibilidad cutánea",
                            'enfermedades_preexistentes': "Sin antecedentes",
                            'observaciones_generales': fake.sentence()
                        }
                    )

                    cant_consultas = random.randint(1, 3)
                    for _ in range(cant_consultas):
                        vet_usuario = random.choice(usuarios_vets) if usuarios_vets else None
                        try:
                            # Intenta crear la consulta adaptándose a los campos de tu modelo
                            ConsultaMedica.objects.create(
                                historia_clinica=historia,
                                veterinario=vet_usuario,
                                motivo_consulta=random.choice(motivos_lista),
                                peso_actual_kg=mascota.peso_kg,
                                temperatura_c=round(random.uniform(37.5, 39.5), 1),
                                frecuencia_cardiaca=random.randint(70, 140),
                                anamnesis=fake.paragraph(nb_sentences=2),
                                diagnostico=fake.sentence(),
                                tratamiento=fake.sentence()
                            )
                            consultas_creadas += 1
                        except Exception:
                            pass

        self.stdout.write(self.style.SUCCESS(
            f"\n¡Carga de clientes finalizada con éxito!"
            f"\n- Clientes creados: {clientes_creados}"
            f"\n- Mascotas registradas: {mascotas_creadas}"
            f"\n- Consultas Médicas vinculadas: {consultas_creadas}"
        ))