from django.contrib import admin
from django.utils.html import format_html
from .models import Veterinaria, PerfilUsuario, MensajeContacto


@admin.register(Veterinaria)
class VeterinariaAdmin(admin.ModelAdmin):
    list_display = ('id', 'ver_logo', 'nombre', 'cuit_rif', 'telefono', 'email_contacto', 'activo', 'creado')
    list_filter = ('activo', 'creado')
    search_fields = ('nombre', 'cuit_rif', 'email_contacto')
    ordering = ('-creado',)

    @admin.display(description="Logo")
    def ver_logo(self, obj):
        if obj.logo:
            return format_html('<img src="{}" style="max-height: 35px; max-width: 60px; border-radius: 4px;" />', obj.logo.url)
        return "-"


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ('user_username', 'user_full_name', 'user_email', 'veterinaria', 'rol', 'is_approved')
    list_filter = ('is_approved', 'rol', 'veterinaria')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'user__email', 'veterinaria__nombre')
    list_editable = ('is_approved',)  # Permite tildar/destildar directamente desde la lista
    actions = ['aprobar_usuarios', 'revocar_aprobacion']

    @admin.display(description="Usuario", ordering="user__username")
    def user_username(self, obj):
        return obj.user.username

    @admin.display(description="Nombre Completo", ordering="user__first_name")
    def user_full_name(self, obj):
        return obj.user.get_full_name() or "-"

    @admin.display(description="Correo Electrónico", ordering="user__email")
    def user_email(self, obj):
        return obj.user.email

    # --------------------------------------------------------------------------
    # ACCIONES PERSONALIZADAS DEL ADMIN
    # --------------------------------------------------------------------------
    @admin.action(description="✅ Aprobar acceso a los usuarios seleccionados")
    def aprobar_usuarios(self, request, queryset):
        filas_actualizadas = queryset.update(is_approved=True)
        self.message_user(
            request, 
            f"Se aprobó exitosamente el acceso para {filas_actualizadas} usuario(s)."
        )

    @admin.action(description="❌ Revocar aprobación (Bloquear acceso)")
    def revocar_aprobacion(self, request, queryset):
        filas_actualizadas = queryset.update(is_approved=False)
        self.message_user(
            request, 
            f"Se revocó el acceso para {filas_actualizadas} usuario(s)."
        )


@admin.register(MensajeContacto)
class MensajeContactoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'email', 'telefono', 'asunto', 'fecha_envio', 'leido')
    list_filter = ('leido', 'fecha_envio')
    search_fields = ('nombre', 'email', 'asunto', 'mensaje')
    readonly_fields = ('fecha_envio',)
    list_editable = ('leido',)
    ordering = ('-fecha_envio',)