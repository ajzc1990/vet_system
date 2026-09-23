import anthropic
from django.conf import settings

MODEL = "claude-haiku-4-5"

SYSTEM_PROMPT = (
    "Sos un asistente para veterinarios. A partir de datos estructurados de la "
    "historia clínica de una mascota, escribís un resumen breve (4 a 6 líneas) "
    "en español, en prosa, pensado para que el veterinario lo lea en segundos "
    "antes de atender al paciente. Destacá antecedentes relevantes, patologías "
    "crónicas o recurrentes, alergias, tratamientos en curso y vacunas o "
    "desparasitaciones vencidas. No repitas la lista de datos tal cual te la "
    "paso, sintetizala. No inventes información que no esté en los datos "
    "provistos. No des recomendaciones de tratamiento ni diagnóstiques: solo "
    "resumí lo ya registrado."
)


class ResumenIADeshabilitado(Exception):
    """La función de resúmenes con IA no está habilitada en este entorno."""


class ResumenIAError(Exception):
    """Falló la generación del resumen (error de red, de la API, etc.)."""


def _formatear_historia(mascota):
    partes = [
        f"Mascota: {mascota.nombre}, {mascota.get_especie_display()}, "
        f"raza {mascota.raza or 'mestizo'}, {mascota.get_sexo_display()}, "
        f"peso {mascota.peso_kg or 'sin registrar'} kg."
    ]

    consultas = mascota.consultas.order_by('-fecha_hora')[:5]
    if consultas:
        partes.append("\nÚltimas consultas médicas:")
        for c in consultas:
            partes.append(
                f"- {c.fecha_hora.strftime('%d/%m/%Y')}: motivo \"{c.motivo_consulta}\", "
                f"diagnóstico \"{c.diagnostico}\", tratamiento \"{c.tratamiento}\"."
            )
    else:
        partes.append("\nSin consultas médicas registradas.")

    vacunas = mascota.vacunas.order_by('-fecha_aplicacion')[:5]
    if vacunas:
        partes.append("\nVacunas aplicadas:")
        for v in vacunas:
            proxima = f", próxima dosis {v.fecha_proxima_dosis.strftime('%d/%m/%Y')}" if v.fecha_proxima_dosis else ""
            partes.append(f"- {v.nombre_vacuna} ({v.fecha_aplicacion.strftime('%d/%m/%Y')}){proxima}.")

    desparasitaciones = mascota.desparasitaciones.order_by('-fecha_aplicacion')[:3]
    if desparasitaciones:
        partes.append("\nDesparasitaciones:")
        for d in desparasitaciones:
            partes.append(f"- {d.producto} ({d.fecha_aplicacion.strftime('%d/%m/%Y')}).")

    recetas = mascota.recetas.order_by('-fecha_emision')[:3]
    if recetas:
        partes.append("\nRecetas recientes:")
        for r in recetas:
            medicamentos = ", ".join(i.medicamento for i in r.items.all())
            if medicamentos:
                partes.append(f"- {r.fecha_emision.strftime('%d/%m/%Y')}: {medicamentos}.")

    internaciones = mascota.internaciones.order_by('-fecha_ingreso')[:2]
    if internaciones:
        partes.append("\nInternaciones:")
        for i in internaciones:
            partes.append(
                f"- {i.fecha_ingreso.strftime('%d/%m/%Y')}: {i.motivo_ingreso} "
                f"({i.get_estado_display()})."
            )

    return "\n".join(partes)


def generar_resumen_clinico(mascota, usuario=None):
    """Genera (o regenera) el resumen clínico de una mascota con IA y lo guarda."""
    if not settings.IA_RESUMENES_ENABLED or not settings.ANTHROPIC_API_KEY:
        raise ResumenIADeshabilitado("La función de resúmenes con IA no está habilitada.")

    from .models import ResumenClinicoIA

    historia = _formatear_historia(mascota)
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": historia}],
        )
    except anthropic.APIError as e:
        raise ResumenIAError(str(e)) from e

    texto = "".join(block.text for block in response.content if block.type == "text").strip()
    if not texto:
        raise ResumenIAError("La IA no devolvió contenido.")

    resumen, _ = ResumenClinicoIA.objects.update_or_create(
        mascota=mascota,
        defaults={'texto': texto, 'generado_por': usuario},
    )
    return resumen
