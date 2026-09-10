# apps/turnos/admin.py
from django.contrib import admin
from .models import Veterinario, Turno, SolicitudTurnoWeb
from apps.clientes.models import Mascota


def _get_admin_veterinaria(request):
    """Auxiliar para obtener la veterinaria activa del usuario en el Admin."""
    if hasattr(request, 'veterinaria') and request.veterinaria:
        return request.veterinaria
    if hasattr(request.user, 'perfil') and request.user.perfil and request.user.perfil.veterinaria:
        return request.user.perfil.veterinaria
    if hasattr(request.user, 'veterinaria') and request.user.veterinaria:
        return request.user.veterinaria
    return None


@admin.register(Veterinario)
class VeterinarioAdmin(admin.ModelAdmin):
    list_display = ('apellido', 'nombre', 'matricula', 'telefono', 'veterinaria', 'activo')
    list_filter = ('veterinaria', 'activo')
    search_fields = ('nombre', 'apellido', 'matricula')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        
        vet = _get_admin_veterinaria(request)
        return qs.filter(veterinaria=vet) if vet else qs.none()

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser and not obj.veterinaria_id:
            obj.veterinaria = _get_admin_veterinaria(request)
        super().save_model(request, obj, form, change)


@admin.register(Turno)
class TurnoAdmin(admin.ModelAdmin):
    list_display = ('fecha_hora', 'mascota', 'get_cliente', 'veterinario', 'veterinaria', 'estado')
    list_filter = ('estado', 'veterinaria', 'fecha_hora', 'veterinario')
    search_fields = ('mascota__nombre', 'mascota__cliente__nombre', 'mascota__cliente__apellido', 'veterinario__apellido', 'motivo')
    date_hierarchy = 'fecha_hora'

    @admin.display(description="Cliente / Dueño")
    def get_cliente(self, obj):
        if obj.mascota and obj.mascota.cliente:
            return f"{obj.mascota.cliente.apellido}, {obj.mascota.cliente.nombre}"
        return "-"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        
        vet = _get_admin_veterinaria(request)
        return qs.filter(veterinaria=vet) if vet else qs.none()

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser and not obj.veterinaria_id:
            obj.veterinaria = _get_admin_veterinaria(request)
        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if not request.user.is_superuser:
            vet = _get_admin_veterinaria(request)
            if vet:
                if db_field.name == "mascota":
                    kwargs["queryset"] = Mascota.objects.filter(cliente__veterinaria=vet, cliente__activo=True)
                elif db_field.name == "veterinario":
                    kwargs["queryset"] = Veterinario.objects.filter(veterinaria=vet, activo=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(SolicitudTurnoWeb)
class SolicitudTurnoWebAdmin(admin.ModelAdmin):
    list_display = ('nombre_tutor', 'nombre_mascota', 'veterinaria', 'fecha_deseada', 'franja_preferida', 'estado', 'creado_el')
    list_filter = ('estado', 'veterinaria', 'franja_preferida')
    search_fields = ('nombre_tutor', 'nombre_mascota', 'telefono', 'email')
    date_hierarchy = 'fecha_deseada'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs

        vet = _get_admin_veterinaria(request)
        return qs.filter(veterinaria=vet) if vet else qs.none()