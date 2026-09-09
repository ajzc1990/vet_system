from django.contrib import admin
from .models import Cliente, Mascota

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('apellido', 'nombre', 'dni', 'telefono', 'veterinaria', 'activo')
    list_filter = ('veterinaria', 'activo')
    search_fields = ('nombre', 'apellido', 'dni')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Superusuarios ven todos los clientes
        if request.user.is_superuser:
            return qs
        # Usuarios normales solo ven los de su veterinaria
        vet = getattr(request, 'veterinaria', None)
        return qs.filter(veterinaria=vet)

    def save_model(self, request, obj, form, change):
        # Asigna automáticamente la veterinaria del usuario si no está definida
        if not request.user.is_superuser and not obj.veterinaria_id:
            obj.veterinaria = getattr(request, 'veterinaria', None)
        super().save_model(request, obj, form, change)


@admin.register(Mascota)
class MascotaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'especie', 'raza', 'cliente', 'castrado')
    list_filter = ('especie', 'castrado')
    search_fields = ('nombre', 'cliente__apellido', 'cliente__nombre')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Mascota -> cliente -> veterinaria
        vet = getattr(request, 'veterinaria', None)
        return qs.filter(cliente__veterinaria=vet)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Al crear/editar una mascota en el Admin, en el desplegable de 'cliente' 
        # solo se muestran los clientes de su propia veterinaria
        if db_field.name == "cliente" and not request.user.is_superuser:
            vet = getattr(request, 'veterinaria', None)
            kwargs["queryset"] = Cliente.objects.filter(veterinaria=vet)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)