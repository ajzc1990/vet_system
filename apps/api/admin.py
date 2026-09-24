from django.contrib import admin

from .models import DispositivoPush


@admin.register(DispositivoPush)
class DispositivoPushAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'plataforma', 'activo', 'actualizado_el')
    list_filter = ('activo', 'plataforma')
    search_fields = ('usuario__username', 'token')
