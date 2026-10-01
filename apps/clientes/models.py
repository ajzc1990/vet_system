from django.conf import settings
from django.db import models
from apps.usuarios.models import Veterinaria

ESPECIES = [
    ('CANINO', 'Canino'),
    ('FELINO', 'Felino'),
    ('AVE', 'Ave'),
    ('OTRO', 'Otro'),
]


def formatear_telefono_whatsapp(telefono):
    """Normaliza un teléfono argentino al formato que esperan los links wa.me:
    código de país (54) + prefijo de celular (9) + área y número, todo junto
    y sin el 0 de larga distancia (ej: '381 659-0564' -> '5493816590564')."""
    digitos = "".join(ch for ch in (telefono or "") if ch.isdigit())
    if not digitos:
        return ""
    if digitos.startswith("0"):
        digitos = digitos[1:]
    if digitos.startswith("54"):
        resto = digitos[2:]
        if not resto.startswith("9"):
            resto = "9" + resto
        digitos = "54" + resto
    else:
        digitos = "549" + digitos
    return digitos


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
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cliente_portal',
        verbose_name="Acceso al Portal del Cliente"
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['apellido', 'nombre']

    def __str__(self):
        return f"{self.apellido}, {self.nombre}"

    @property
    def telefono_whatsapp(self):
        return formatear_telefono_whatsapp(self.telefono)


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