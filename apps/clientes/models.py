from django.db import models
from apps.usuarios.models import Veterinaria

ESPECIES = [
    ('CANINO', 'Canino'),
    ('FELINO', 'Felino'),
    ('AVE', 'Ave'),
    ('OTRO', 'Otro'),
]

class Cliente(models.Model):
    veterinaria = models.ForeignKey(
        Veterinaria, 
        on_delete=models.CASCADE, 
        related_name='clientes',
        verbose_name="Veterinaria",
        null=True,
        blank=True
    )
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    dni = models.CharField(max_length=20, unique=True, verbose_name="DNI / Documento")
    telefono = models.CharField(max_length=30, verbose_name="Teléfono")
    email = models.EmailField(blank=True, null=True)
    direccion = models.CharField(max_length=255, blank=True, null=True, verbose_name="Dirección")
    activo = models.BooleanField(default=True, verbose_name="Cliente Activo")
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['apellido', 'nombre']

    def __str__(self):
        return f"{self.apellido}, {self.nombre}"


class Mascota(models.Model):
    SEXO = [
        ('M', 'Macho'),
        ('H', 'Hembra'),
    ]
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='mascotas')
    nombre = models.CharField(max_length=100)
    especie = models.CharField(max_length=20, choices=ESPECIES, default='CANINO')
    raza = models.CharField(max_length=100, blank=True, null=True)
    fecha_nacimiento = models.DateField(blank=True, null=True, verbose_name="Fecha de Nacimiento")
    sexo = models.CharField(max_length=1, choices=SEXO, default='M')
    peso_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Peso (kg)")
    castrado = models.BooleanField(default=False, verbose_name="¿Está castrado/a?")
    observaciones = models.TextField(null=True, blank=True, verbose_name="Observaciones")
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Mascota"
        verbose_name_plural = "Mascotas"
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} ({self.cliente.apellido})"