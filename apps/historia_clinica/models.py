import os
from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from apps.usuarios.models import Veterinaria
from apps.clientes.models import Mascota
from apps.turnos.models import Veterinario, Turno


class ConsultaMedica(models.Model):
    veterinaria = models.ForeignKey(
        Veterinaria,
        on_delete=models.CASCADE,
        related_name='consultas_medicas',
        null=True,
        blank=True,
        verbose_name="Veterinaria"
    )
    mascota = models.ForeignKey(
        Mascota, 
        on_delete=models.CASCADE, 
        related_name='consultas',
        verbose_name="Mascota"
    )
    veterinario = models.ForeignKey(
        Veterinario, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='consultas',
        verbose_name="Veterinario Atendiente"
    )
    turno = models.OneToOneField(
        Turno, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='consulta',
        verbose_name="Turno Asociado"
    )
    
    fecha_hora = models.DateTimeField(default=timezone.now, verbose_name="Fecha y Hora")
    
    # Constantes vitales al momento de la consulta
    peso_actual_kg = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, verbose_name="Peso (kg)")
    temperatura_c = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True, verbose_name="Temp (°C)")
    frecuencia_cardiaca = models.IntegerField(blank=True, null=True, verbose_name="FC (LPM)")
    frecuencia_respiratoria = models.IntegerField(blank=True, null=True, verbose_name="FR (RPM)")
    
    # Evaluación médica
    motivo_consulta = models.TextField(verbose_name="Motivo de Consulta")
    anamnesis = models.TextField(blank=True, null=True, verbose_name="Anamnesis / Síntomas", help_text="Historia clínica previa / Síntomas reportados")
    examen_clinico = models.TextField(blank=True, null=True, verbose_name="Examen Físico / Clinico", help_text="Hallazgos en la exploración física")
    diagnostico = models.TextField(verbose_name="Diagnóstico Presuntivo / Definitivo")
    tratamiento = models.TextField(verbose_name="Tratamiento e Indicaciones", help_text="Indicaciones, medicamentos recetados y procedimientos")
    
    observaciones_privadas = models.TextField(blank=True, null=True, verbose_name="Notas Internas", help_text="Notas privadas para el equipo de la clínica")

    creado_el = models.DateTimeField(auto_now_add=True)
    actualizado_el = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Consulta Médica"
        verbose_name_plural = "Consultas Médicas"
        ordering = ['-fecha_hora']

    def __str__(self):
        return f"Consulta {self.fecha_hora.strftime('%d/%m/%Y')} - {self.mascota.nombre}"

    def save(self, *args, **kwargs):
        # Fallback: Heredar la veterinaria de la mascota o el dueño si no viene asignada explícitamente
        if not self.veterinaria_id and self.mascota and hasattr(self.mascota, 'cliente') and self.mascota.cliente:
            self.veterinaria = self.mascota.cliente.veterinaria

        # Actualizar peso de la mascota si se proporcionó
        if self.peso_actual_kg and hasattr(self.mascota, 'peso'):
            self.mascota.peso = self.peso_actual_kg
            self.mascota.save(update_fields=['peso'])
            
        # Marcar automáticamente el turno como COMPLETADO
        if self.turno and self.turno.estado != 'COMPLETADO':
            self.turno.estado = 'COMPLETADO'
            self.turno.save(update_fields=['estado'])
            
        super().save(*args, **kwargs)


class RegistroVacuna(models.Model):
    veterinaria = models.ForeignKey(
        Veterinaria,
        on_delete=models.CASCADE,
        related_name='vacunas_aplicadas',
        null=True,
        blank=True,
        verbose_name="Veterinaria"
    )
    mascota = models.ForeignKey(
        Mascota, 
        on_delete=models.CASCADE, 
        related_name='vacunas',
        verbose_name="Mascota"
    )
    veterinario = models.ForeignKey(
        Veterinario, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="Veterinario Atendiente"
    )
    
    nombre_vacuna = models.CharField(max_length=100, verbose_name="Nombre de Vacuna", help_text="Ej: Quíntuple, Antirrábica, Séxtuple")
    lote = models.CharField(max_length=50, blank=True, null=True, verbose_name="Nº de Lote")
    
    fecha_aplicacion = models.DateField(default=timezone.now, verbose_name="Fecha de Aplicación")
    fecha_proxima_dosis = models.DateField(blank=True, null=True, verbose_name="Próxima Dosis / Revacunación")
    
    observaciones = models.CharField(max_length=255, blank=True, null=True, verbose_name="Observaciones")

    class Meta:
        verbose_name = "Registro de Vacuna"
        verbose_name_plural = "Registros de Vacunas"
        ordering = ['-fecha_aplicacion']

    def __str__(self):
        return f"{self.nombre_vacuna} - {self.mascota.nombre} ({self.fecha_aplicacion.strftime('%d/%m/%Y')})"

    def save(self, *args, **kwargs):
        if not self.veterinaria_id and self.mascota and hasattr(self.mascota, 'cliente') and self.mascota.cliente:
            self.veterinaria = self.mascota.cliente.veterinaria
        super().save(*args, **kwargs)

    @property
    def proxima_dosis_vencida(self):
        if self.fecha_proxima_dosis:
            return self.fecha_proxima_dosis < timezone.now().date()
        return False


class RegistroDesparasitacion(models.Model):
    TIPO_DESPARASITACION = [
        ('INTERNA', 'Interna'),
        ('EXTERNA', 'Externa (Pulgas/Garrapatas)'),
        ('AMBAS', 'Ambas'),
    ]

    veterinaria = models.ForeignKey(
        Veterinaria,
        on_delete=models.CASCADE,
        related_name='desparasitaciones_aplicadas',
        null=True,
        blank=True,
        verbose_name="Veterinaria"
    )
    mascota = models.ForeignKey(
        Mascota, 
        on_delete=models.CASCADE, 
        related_name='desparasitaciones',
        verbose_name="Mascota"
    )
    veterinario = models.ForeignKey(
        Veterinario, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="Veterinario Atendiente"
    )
    
    tipo = models.CharField(max_length=10, choices=TIPO_DESPARASITACION, default='INTERNA', verbose_name="Tipo")
    producto = models.CharField(max_length=100, verbose_name="Producto Utilizado", help_text="Ej: Total Full, Simparica, Bravecto")
    dosis = models.CharField(max_length=50, blank=True, null=True, verbose_name="Dosis Suministrada", help_text="Ej: 1 comprimido, 0.5 ml")
    
    fecha_aplicacion = models.DateField(default=timezone.now, verbose_name="Fecha de Aplicación")
    fecha_proxima_dosis = models.DateField(blank=True, null=True, verbose_name="Próxima Dosis")

    class Meta:
        verbose_name = "Registro de Desparasitación"
        verbose_name_plural = "Registros de Desparasitaciones"
        ordering = ['-fecha_aplicacion']

    def __str__(self):
        return f"{self.get_tipo_display()} ({self.producto}) - {self.mascota.nombre}"

    def save(self, *args, **kwargs):
        if not self.veterinaria_id and self.mascota and hasattr(self.mascota, 'cliente') and self.mascota.cliente:
            self.veterinaria = self.mascota.cliente.veterinaria
        super().save(*args, **kwargs)

    @property
    def proxima_dosis_vencida(self):
        if self.fecha_proxima_dosis:
            return self.fecha_proxima_dosis < timezone.now().date()
        return False


class EstudioMedico(models.Model):
    TIPO_ESTUDIO = [
        ('ECOGRAFIA', 'Ecografía'),
        ('RADIOGRAFIA', 'Radiografía (RX)'),
        ('ANALISIS_SANGRE', 'Análisis de Sangre / Laboratorio'),
        ('URANALISIS', 'Análisis de Orina'),
        ('CITOLOGIA', 'Citología / Histopatología'),
        ('ELECTROCARDIOGRAMA', 'Electrocardiograma (ECG)'),
        ('OTRO', 'Otro Estudio / Adjunto'),
    ]

    veterinaria = models.ForeignKey(
        Veterinaria,
        on_delete=models.CASCADE,
        related_name='estudios_medicos',
        null=True,
        blank=True,
        verbose_name="Veterinaria"
    )
    mascota = models.ForeignKey(
        Mascota, 
        on_delete=models.CASCADE, 
        related_name='estudios',
        verbose_name="Mascota"
    )
    veterinario = models.ForeignKey(
        Veterinario, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="Veterinario Solicitante/Cargador"
    )
    consulta = models.ForeignKey(
        ConsultaMedica,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='estudios',
        verbose_name="Consulta Asociada"
    )
    
    titulo = models.CharField(max_length=150, verbose_name="Título del Estudio", help_text="Ej: Ecografía Abdominal, Hemograma Completo")
    tipo_estudio = models.CharField(max_length=30, choices=TIPO_ESTUDIO, default='OTRO', verbose_name="Categoría / Tipo")
    archivo = models.FileField(upload_to='estudios/%Y/%m/', verbose_name="Archivo / Adjunto (PDF, JPG, PNG, DICOM)")
    fecha_estudio = models.DateField(default=timezone.now, verbose_name="Fecha del Estudio")
    observaciones = models.TextField(blank=True, null=True, verbose_name="Informe / Conclusiones del Estudio")

    creado_el = models.DateTimeField(auto_now_add=True)
    actualizado_el = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Estudio Médico"
        verbose_name_plural = "Estudios Médicos"
        ordering = ['-fecha_estudio', '-creado_el']

    def __str__(self):
        return f"{self.titulo} - {self.mascota.nombre} ({self.fecha_estudio.strftime('%d/%m/%Y')})"

    def save(self, *args, **kwargs):
        if not self.veterinaria_id and self.mascota and hasattr(self.mascota, 'cliente') and self.mascota.cliente:
            self.veterinaria = self.mascota.cliente.veterinaria
        super().save(*args, **kwargs)

    @property
    def es_imagen(self):
        """Devuelve True si el archivo subido es una imagen (PNG, JPG, JPEG, WEBP)."""
        if self.archivo:
            ext = os.path.splitext(self.archivo.name)[1].lower()
            return ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']
        return False


# ==============================================================================
# SEÑALES DE LIMPIEZA AUTOMÁTICA DE ARCHIVOS FÍSICOS (MEDIA CLEANUP)
# ==============================================================================

@receiver(post_delete, sender=EstudioMedico)
def auto_delete_file_on_delete(sender, instance, **kwargs):
    """Elimina el archivo físico del disco cuando se borra un EstudioMedico en la BD."""
    if instance.archivo:
        if os.path.isfile(instance.archivo.path):
            try:
                os.remove(instance.archivo.path)
            except Exception:
                pass


@receiver(pre_save, sender=EstudioMedico)
def auto_delete_old_file_on_change(sender, instance, **kwargs):
    """Elimina el archivo físico anterior cuando se sube un nuevo archivo en una edición."""
    if not instance.pk:
        return False

    try:
        old_file = EstudioMedico.objects.get(pk=instance.pk).archivo
    except EstudioMedico.DoesNotExist:
        return False

    new_file = instance.archivo
    if old_file and old_file != new_file and os.path.isfile(old_file.path):
        try:
            os.remove(old_file.path)
        except Exception:
            pass