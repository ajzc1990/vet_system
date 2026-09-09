# apps/usuarios/management/commands/crear_roles_iniciales.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

class Command(BaseCommand):
    help = "Crea los grupos 'Veterinarios' y 'Recepcionistas' con sus permisos por defecto."

    def handle(self, *args, **options):
        # 1. Grupo Veterinarios
        grupo_vet, created_vet = Group.objects.get_or_create(name='Veterinarios')
        if created_vet:
            self.stdout.write(self.style.SUCCESS("✅ Grupo 'Veterinarios' creado."))
        else:
            self.stdout.write("ℹ️ El grupo 'Veterinarios' ya existía.")

        # 2. Grupo Recepcionistas
        grupo_rec, created_rec = Group.objects.get_or_create(name='Recepcionistas')
        if created_rec:
            self.stdout.write(self.style.SUCCESS("✅ Grupo 'Recepcionistas' creado."))
        else:
            self.stdout.write("ℹ️ El grupo 'Recepcionistas' ya existía.")

        self.stdout.write(self.style.SUCCESS("\n🎉 Configuración de roles completada con éxito."))