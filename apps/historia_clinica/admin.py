from django.contrib import admin
from django.utils.html import format_html
from .models import ConsultaMedica, RegistroVacuna, RegistroDesparasitacion, EstudioMedico


@admin.register(ConsultaMedica)
class ConsultaMedicaAdmin(admin.ModelAdmin):
    list_display = ('fecha_hora', 'mascota', 'veterinaria', 'veterinario', 'diagnostico_corto', 'peso_actual_kg')
    list_filter = ('veterinaria', 'fecha_hora', 'veterinario')
    search_fields = ('mascota__nombre', 'mascota__cliente__apellido', 'mascota__cliente__nombre', 'diagnostico', 'motivo_consulta')
    readonly_fields = ('creado_el', 'actualizado_el')

    @admin.display(description="Diagnóstico")
    def diagnostico_corto(self, obj):
        if obj.diagnostico:
            return obj.diagnostico[:50] + '...' if len(obj.diagnostico) > 50 else obj.diagnostico
        return "-"


@admin.register(RegistroVacuna)
class RegistroVacunaAdmin(admin.ModelAdmin):
    list_display = ('mascota', 'nombre_vacuna', 'veterinaria', 'fecha_aplicacion', 'proxima_dosis_status', 'veterinario')
    list_filter = ('veterinaria', 'nombre_vacuna', 'fecha_aplicacion')
    search_fields = ('mascota__nombre', 'mascota__cliente__apellido', 'nombre_vacuna', 'lote')

    @admin.display(description="Próxima Dosis")
    def proxima_dosis_status(self, obj):
        if not obj.fecha_proxima_dosis:
            return "-"
        if obj.proxima_dosis_vencida:
            return format_html('<span style="color: red; font-weight: bold;">⚠️ {} (Vencida)</span>', obj.fecha_proxima_dosis.strftime('%d/%m/%Y'))
        return format_html('<span style="color: green;">{}</span>', obj.fecha_proxima_dosis.strftime('%d/%m/%Y'))


@admin.register(RegistroDesparasitacion)
class RegistroDesparasitacionAdmin(admin.ModelAdmin):
    list_display = ('mascota', 'tipo', 'producto', 'veterinaria', 'fecha_aplicacion', 'proxima_dosis_status')
    list_filter = ('veterinaria', 'tipo', 'fecha_aplicacion')
    search_fields = ('mascota__nombre', 'mascota__cliente__apellido', 'producto')

    @admin.display(description="Próxima Dosis")
    def proxima_dosis_status(self, obj):
        if not obj.fecha_proxima_dosis:
            return "-"
        if obj.proxima_dosis_vencida:
            return format_html('<span style="color: red; font-weight: bold;">⚠️ {} (Vencida)</span>', obj.fecha_proxima_dosis.strftime('%d/%m/%Y'))
        return format_html('<span style="color: green;">{}</span>', obj.fecha_proxima_dosis.strftime('%d/%m/%Y'))


@admin.register(EstudioMedico)
class EstudioMedicoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'tipo_estudio', 'mascota', 'veterinaria', 'fecha_estudio', 'ver_adjunto', 'veterinario')
    list_filter = ('veterinaria', 'tipo_estudio', 'fecha_estudio')
    search_fields = ('titulo', 'mascota__nombre', 'mascota__cliente__apellido', 'observaciones')
    readonly_fields = ('creado_el', 'actualizado_el')

    @admin.display(description="Adjunto / Archivo")
    def ver_adjunto(self, obj):
        if obj.archivo:
            if obj.es_imagen:
                return format_html('<a href="{}" target="_blank"><img src="{}" style="max-height: 40px; border-radius: 4px;" /></a>', obj.archivo.url, obj.archivo.url)
            return format_html('<a href="{}" target="_blank" class="button">📄 Ver Documento</a>', obj.archivo.url)
        return "-"