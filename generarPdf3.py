import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def crear_pdf_alcance():
    pdf_filename = "Declaracion_de_Alcance_Veterinaria.pdf"
    doc = SimpleDocTemplate(pdf_filename, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []

    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'TitleStyle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=14,
        leading=18, textColor=colors.HexColor('#1A365D'), alignment=1, spaceAfter=10
    )
    
    h2_style = ParagraphStyle(
        'H2Style', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=10.5,
        leading=13, textColor=colors.HexColor('#2C5282'), spaceBefore=8, spaceAfter=4
    )

    body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=11, textColor=colors.HexColor('#2D3748'))
    table_body = ParagraphStyle('TableBody', parent=styles['Normal'], fontName='Helvetica', fontSize=7.5, leading=9, textColor=colors.HexColor('#2D3748'))
    table_header = ParagraphStyle('TableHeader', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.white)

    # Header Documento
    story.append(Paragraph("UTN - FACULTAD REGIONAL TUCUMÁN", ParagraphStyle('Sub', parent=body_style, alignment=1, fontSize=9, fontName='Helvetica-Bold')))
    story.append(Paragraph("DECLARACIÓN DEL ALCANCE DEL PROYECTO", title_style))
    story.append(Spacer(1, 4))

    # General Data Table
    data_header = [
        [Paragraph("<b>ID PROYECTO:</b> VET-2026", table_body), Paragraph("<b>PROYECTO:</b> Sistema Veterinaria Multi-Tenant", table_body)],
        [Paragraph("<b>PATROCINADOR:</b> Cátedra Proyecto Final / UTN-FRT", table_body), Paragraph("<b>ELABORADO POR:</b> Agustín Zelaya Cossio", table_body)],
        [Paragraph("<b>CÓDIGO DOC:</b> DOC-SCOPE-01", table_body), Paragraph("<b>FECHA:</b> Agosto 2026", table_body)]
    ]
    t_header = Table(data_header, colWidths=[270, 270])
    t_header.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#EDF2F7')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#CBD5E0')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E0')),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_header)
    story.append(Spacer(1, 6))

    # 1. Descripcion
    story.append(Paragraph("1. DESCRIPCIÓN DEL ALCANCE DEL PROYECTO Y PRODUCTO", h2_style))
    p1 = "Desarrollo de una solución web SaaS bajo arquitectura Multi-Tenant para la gestión integral de clínicas veterinarias. Incluye el control centralizado de pacientes (mascotas), historias clínicas (consultas, vacunas y desparasitaciones), agenda de turnos y control de inventario con aislamiento lógico estricto por veterinaria."
    story.append(Paragraph(p1, body_style))
    story.append(Spacer(1, 6))

    # 2. Criterios Aceptacion
    story.append(Paragraph("2. CRITERIOS DE ACEPTACIÓN PRINCIPALES", h2_style))
    p2 = "• <b>Aislamiento Tenant:</b> Denegación de acceso (403/404) si se intenta acceder a registros de otra veterinaria.<br/>" \
         "• <b>Manejo de Superusuarios:</b> Navegación fluida del administrador sin excepciones 500 por falta de tenant.<br/>" \
         "• <b>Normalización ORM:</b> Consultas relacionales directas a Mascota mediante <i>related_names</i>.<br/>" \
         "• <b>Tiempo de Respuesta:</b> Renderizado de la ficha de Historia Clínica en menos de 1.0 segundo."
    story.append(Paragraph(p2, body_style))
    story.append(Spacer(1, 6))

    # 3. Entregables
    story.append(Paragraph("3. ENTREGABLES DEL PROYECTO", h2_style))
    entregables_data = [
        [Paragraph("ENTREGABLE", table_header), Paragraph("FECHA", table_header), Paragraph("DESCRIPCIÓN DEL ENTREGABLE", table_header), Paragraph("RESPONSABLE", table_header)],
        [Paragraph("Acta y Registro Interesados", table_body), Paragraph("05/08/2026", table_body), Paragraph("Documentación inicial PMI de gestión y contexto.", table_body), Paragraph("Agustín Zelaya", table_body)],
        [Paragraph("Declaración de Alcance", table_body), Paragraph("05/08/2026", table_body), Paragraph("Definición de alcance, criterios y exclusiones.", table_body), Paragraph("Agustín Zelaya", table_body)],
        [Paragraph("Refactorización Core ORM", table_body), Paragraph("06/08/2026", table_body), Paragraph("Normalización de modelos, lazy imports y multitenancy.", table_body), Paragraph("Agustín Zelaya", table_body)],
        [Paragraph("Template Historia Clínica", table_body), Paragraph("08/08/2026", table_body), Paragraph("Interfaz historia_clinica.html con tabs y modales.", table_body), Paragraph("Agustín Zelaya", table_body)],
        [Paragraph("Módulos Vacunas/Desparasitaciones", table_body), Paragraph("12/08/2026", table_body), Paragraph("Formularios y endpoints de dosis clínicas.", table_body), Paragraph("Agustín Zelaya", table_body)],
        [Paragraph("Integración Turnos/Inventario", table_body), Paragraph("18/08/2026", table_body), Paragraph("Descuento automático de stock y agenda.", table_body), Paragraph("Agustín Zelaya", table_body)]
    ]
    t_entregables = Table(entregables_data, colWidths=[120, 55, 265, 100])
    t_entregables.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2C5282')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E0')),
        ('PADDING', (0,0), (-1,-1), 4),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_entregables)
    story.append(Spacer(1, 6))

    # 4. Exclusiones y Supuestos
    story.append(Paragraph("4. EXCLUSIONES Y RESTRICCIONES", h2_style))
    p4 = "• <b>Exclusiones:</b> No procesará pagos con tarjeta en vivo, no funcionará offline, ni sustituirá equipos médicos.<br/>" \
         "• <b>Restricciones:</b> Uso exclusivo del stack Python 3, Django, PostgreSQL/SQLite y Bootstrap."
    story.append(Paragraph(p4, body_style))

    doc.build(story)
    print(f"✅ Archivo '{pdf_filename}' generado con éxito.")

if __name__ == '__main__':
    crear_pdf_alcance()