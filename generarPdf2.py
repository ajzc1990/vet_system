import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def crear_pdf_interesados():
    pdf_filename = "Registro_de_Interesados_Veterinaria.pdf"
    doc = SimpleDocTemplate(pdf_filename, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []

    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'TitleStyle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=15,
        leading=18, textColor=colors.HexColor('#1A365D'), alignment=1, spaceAfter=12
    )
    
    h2_style = ParagraphStyle(
        'H2Style', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=11,
        leading=14, textColor=colors.HexColor('#2C5282'), spaceBefore=8, spaceAfter=4
    )

    body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5, leading=11, textColor=colors.HexColor('#2D3748'))
    table_body = ParagraphStyle('TableBody', parent=styles['Normal'], fontName='Helvetica', fontSize=7.5, leading=9, textColor=colors.HexColor('#2D3748'))
    table_header = ParagraphStyle('TableHeader', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.white)

    # Header
    story.append(Paragraph("UTN - FACULTAD REGIONAL TUCUMÁN", ParagraphStyle('Sub', parent=body_style, alignment=1, fontSize=9, fontName='Helvetica-Bold')))
    story.append(Paragraph("REGISTRO DE INTERESADOS DEL PROYECTO", title_style))
    story.append(Spacer(1, 4))

    # General Data Table
    data_header = [
        [Paragraph("<b>PROYECTO:</b> Sistema Veterinaria Multi-Tenant", table_body), Paragraph("<b>ORGANIZACIÓN:</b> UTN-FRT / Clínicas", table_body)],
        [Paragraph("<b>ELABORADO POR:</b> Agustín Zelaya Cossio", table_body), Paragraph("<b>FECHA:</b> Agosto 2026", table_body)]
    ]
    t_header = Table(data_header, colWidths=[270, 270])
    t_header.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#EDF2F7')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#CBD5E0')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E0')),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_header)
    story.append(Spacer(1, 8))

    # Stakeholder Table
    story.append(Paragraph("1. MATRIZ DE IDENTIFICACIÓN Y ANÁLISIS DE INTERESADOS", h2_style))
    
    interesados_data = [
        [Paragraph("ROL / NOMBRE", table_header), Paragraph("TIPO", table_header), Paragraph("INTERÉS PRINCIPAL", table_header), Paragraph("PODER / INTERÉS", table_header), Paragraph("ESTRATEGIA", table_header)],
        [Paragraph("<b>Agustín Zelaya</b><br/>Líder Técnico", table_body), Paragraph("Interno", table_body), Paragraph("Arquitectura, código limpio y cumplimiento de objetivos.", table_body), Paragraph("Alto / Alto", table_body), Paragraph("Gestionar Atentamente", table_body)],
        [Paragraph("<b>Veterinarios</b><br/>Usuarios Core", table_body), Paragraph("Externo", table_body), Paragraph("Carga ágil de historias clínicas, vacunas y constantes.", table_body), Paragraph("Medio / Alto", table_body), Paragraph("Mantener Satisfecho", table_body)],
        [Paragraph("<b>Administradores</b><br/>Tenants", table_body), Paragraph("Externo", table_body), Paragraph("Aislamiento de datos, reportes, gestión de stock/turnos.", table_body), Paragraph("Alto / Alto", table_body), Paragraph("Gestionar Atentamente", table_body)],
        [Paragraph("<b>Recepcionistas</b><br/>Operativos", table_body), Paragraph("Externo", table_body), Paragraph("Alta rápida de clientes, agendamiento de turnos.", table_body), Paragraph("Bajo / Medio", table_body), Paragraph("Mantener Informado", table_body)],
        [Paragraph("<b>Cátedra UTN</b><br/>Evaluadores", table_body), Paragraph("Interno", table_body), Paragraph("Calidad de ingeniería, buenas prácticas y documentación PMI.", table_body), Paragraph("Alto / Medio", table_body), Paragraph("Mantener Satisfecho", table_body)],
    ]
    
    t_interesados = Table(interesados_data, colWidths=[110, 50, 160, 80, 140])
    t_interesados.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2C5282')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E0')),
        ('PADDING', (0,0), (-1,-1), 4),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(t_interesados)

    doc.build(story)
    print(f"✅ Archivo '{pdf_filename}' generado con éxito.")

if __name__ == '__main__':
    crear_pdf_interesados()