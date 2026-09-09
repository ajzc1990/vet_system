import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def crear_pdf():
    pdf_filename = "Acta_de_Constitucion_Proyecto_Veterinaria.pdf"
    doc = SimpleDocTemplate(pdf_filename, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []

    styles = getSampleStyleSheet()
    
    # Estilos personalizados
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=colors.HexColor('#1A365D'),
        alignment=1, # Centrado
        spaceAfter=15
    )
    
    h2_style = ParagraphStyle(
        'H2Style',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#2C5282'),
        spaceBefore=10,
        spaceAfter=6
    )

    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#2D3748')
    )

    table_body = ParagraphStyle(
        'TableBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#2D3748')
    )

    table_header = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.white
    )

    # Encabezado
    story.append(Paragraph("UTN - FACULTAD REGIONAL TUCUMÁN", ParagraphStyle('Sub', parent=body_style, alignment=1, fontSize=10, fontName='Helvetica-Bold')))
    story.append(Paragraph("ACTA DE CONSTITUCIÓN DEL PROYECTO", title_style))
    story.append(Spacer(1, 5))

    # Encabezado Tabla Datos Generales
    data_header = [
        [Paragraph("<b>PROYECTO:</b> Sistema de Gestión Veterinaria Multi-Tenant", table_body), Paragraph("<b>CLIENTE:</b> Clínicas Veterinarias / Sucursales", table_body)],
        [Paragraph("<b>PATROCINADOR:</b> UTN-FRT / Desarrollo Profesional", table_body), Paragraph("<b>ELABORADO POR:</b> Agustín Zelaya Cossio", table_body)],
        [Paragraph("<b>FECHA:</b> Agosto 2026", table_body), Paragraph("<b>ESTADO:</b> En Desarrollo", table_body)]
    ]
    t_header = Table(data_header, colWidths=[270, 270])
    t_header.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#EDF2F7')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#CBD5E0')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E0')),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_header)
    story.append(Spacer(1, 10))

    # 1. Estado del Arte
    story.append(Paragraph("1. ESTADO DEL ARTE Y CONTEXTO", h2_style))
    p1 = "Las clínicas e instituciones veterinarias locales suelen gestionar turnos e historias clínicas mediante papel, planillas tradicionales o sistemas monolíticos rígidos. Nuestra solución implementa una arquitectura SaaS Multi-Tenant sobre Django que permite a múltiples clínicas compartir la misma infraestructura manteniendo sus datos aislados lógicamente."
    story.append(Paragraph(p1, body_style))
    story.append(Spacer(1, 8))

    # 2. Objetivos
    story.append(Paragraph("2. OBJETIVOS DEL PROYECTO", h2_style))
    p2 = "<b>Objetivo General:</b> Desplegar una plataforma web multi-tenant estable para la gestión clínica e integral de veterinarias, garantizando el aislamiento de datos y optimizando la carga de historias clínicas."
    story.append(Paragraph(p2, body_style))
    story.append(Spacer(1, 8))

    # 3. Roadmap de Hitos
    story.append(Paragraph("3. ESTADO DE AVANCE Y ROADMAP DE HITOS", h2_style))
    
    hitos_data = [
        [Paragraph("HITO / EVENTO", table_header), Paragraph("ESTADO", table_header), Paragraph("DESCRIPCIÓN / LOGRO TÉCNICO", table_header)],
        [Paragraph("1. Corrección Multitenancy y Dashboard", table_body), Paragraph("COMPLETADO", table_body), Paragraph("Solución a errores 500/NoneType en dashboard.html para superusuarios y tenants.", table_body)],
        [Paragraph("2. Refactorización ORM/Views", table_body), Paragraph("COMPLETADO", table_body), Paragraph("Alineación con ConsultaMedica, RegistroVacuna y RegistroDesparasitacion.", table_body)],
        [Paragraph("3. Resolución de Imports Circulares", table_body), Paragraph("COMPLETADO", table_body), Paragraph("Implementación de helper lazy get_historia_components().", table_body)],
        [Paragraph("4. Interfaz Historia Clínica HTML", table_body), Paragraph("PENDIENTE", table_body), Paragraph("Diseño e integración del template historia_clinica.html con tabs y modales.", table_body)],
        [Paragraph("5. Modulos Vacunas y Desparasitación", table_body), Paragraph("PENDIENTE", table_body), Paragraph("Formularios y endpoints para agregar/editar dosis y alertas de revacunación.", table_body)],
        [Paragraph("6. Integración Turnos e Inventario", table_body), Paragraph("PENDIENTE", table_body), Paragraph("Descuento automático de stock e integración con agenda de turnos.", table_body)],
    ]
    
    t_hitos = Table(hitos_data, colWidths=[150, 80, 310])
    t_hitos.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2C5282')),
        ('ALIGN', (1,0), (1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E0')),
        ('PADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_hitos)

    # Construir el PDF
    doc.build(story)
    print(f"✅ Archivo '{pdf_filename}' generado con éxito.")

if __name__ == '__main__':
    crear_pdf()