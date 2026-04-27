"""
PDF Generator for GST Invoices using ReportLab.
"""

from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT


def format_party_details(party: dict, title: str, include_state: bool, state_label: str = "State"):
    """
    Format seller/buyer details into a paragraph.
    """
    if not isinstance(party, dict):
        party = {}

    name = party.get("name", "N/A")
    gstin = party.get("gstin", "N/A")
    address = party.get("address", "N/A")
    lines = [
        f"<b>{title}</b>",
        f"Name: {name}",
        f"Address: {address}",
        f"GSTIN: {gstin}",
    ]

    if include_state:
        state = party.get("state", "N/A")
        lines.append(f"{state_label}: {state}")

    return "<br/>".join(lines)


def generate_invoice_pdf(invoice) -> bytes:
    """
    Generate a GST invoice PDF from invoice data.
    """
    # Create PDF buffer
    buffer = BytesIO()
    
    # Create PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )
    
    # Container for PDF elements
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#333333'),
        spaceAfter=12
    )
    
    # Title
    elements.append(Paragraph("GST INVOICE", title_style))
    elements.append(Spacer(1, 0.2 * inch))
    
    # Invoice date formatting
    invoice_date = invoice.invoice_date
    if isinstance(invoice_date, datetime):
        date_str = invoice_date.strftime('%Y-%m-%d')
    else:
        date_str = str(invoice_date)

    # Invoice header (number + date)
    invoice_header = [
        ['Invoice No:', invoice.invoice_no],
        ['Invoice Date:', date_str],
    ]

    header_table = Table(invoice_header, colWidths=[2 * inch, 3 * inch])
    header_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#333333')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))

    elements.append(header_table)
    elements.append(Spacer(1, 0.2 * inch))

    # Seller and Buyer blocks
    print("PDF INPUT DATA:", invoice.buyer_name, invoice.seller_name)
    seller_dict = {
    "name": invoice.seller_name,
    "gstin": invoice.seller_gstin,
    "address": invoice.seller_address,
    "state": invoice.seller_state,
    }

    buyer_dict = {
    "name": invoice.buyer_name,
    "gstin": invoice.buyer_gstin,
    "address": invoice.buyer_address,
    "state": invoice.buyer_state,
    }

    seller_details = format_party_details(seller_dict, "Seller", include_state=False)
    buyer_details = format_party_details(buyer_dict, "Buyer", include_state=True, state_label="Place of Supply")


    party_table = Table([
        [
            Paragraph(seller_details, styles['Normal']),
            Paragraph(buyer_details, styles['Normal'])
        ]
    ], colWidths=[3 * inch, 3 * inch])

    party_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX', (0, 0), (0, 0), 1, colors.grey),
        ('BOX', (1, 0), (1, 0), 1, colors.grey),
        ('INNERPADDING', (0, 0), (-1, -1), 8),
    ]))

    elements.append(party_table)
    elements.append(Spacer(1, 0.3 * inch))
    
    # Items table
    elements.append(Paragraph("ITEMS", heading_style))
    
    items_data = [
        ['Description', 'HSN', 'Qty', 'Rate', 'Taxable', 'GST%', 'Total']
    ]
    
    # Parse items from JSON
    items = invoice.items if isinstance(invoice.items, list) else []
    
    for item in items:
        quantity = float(item.get('quantity', 0))
        unit_price = float(item.get('unit_price', 0))
        gst_rate = float(item.get('gst_rate', 0))
        
        # Calculate taxable and total
        taxable = quantity * unit_price
        gst_amount = (taxable * gst_rate) / 100
        total = taxable + gst_amount
        
        items_data.append([
            item.get('description', ''),
            item.get('hsn') or item.get('hsn_code', ''),
            f"{quantity:.0f}",
            f"₹{unit_price:.2f}",
            f"₹{taxable:.2f}",
            f"{gst_rate:.0f}%",
            f"₹{total:.2f}",
        ])
    
    items_table = Table(items_data, colWidths=[1.8*inch, 0.7*inch, 0.5*inch, 0.9*inch, 1*inch, 0.7*inch, 1*inch])
    items_table.setStyle(TableStyle([
        # Header row styling
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a90e2')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        
        # Data rows styling
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        
        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        
        # Alternating row colors
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
    ]))
    
    elements.append(items_table)
    elements.append(Spacer(1, 0.3 * inch))
    
    # Totals with GST breakdown
    gst_summary = invoice.gst_summary if isinstance(invoice.gst_summary, dict) else {}
    igst_amount = gst_summary.get('igst', 0)
    cgst_amount = gst_summary.get('cgst', 0)
    sgst_amount = gst_summary.get('sgst', 0)
    
    totals_data = [
        ['Subtotal:', f"₹{invoice.subtotal:.2f}"],
    ]
    
    # Display GST breakdown based on supply type
    if igst_amount > 0:
        # Inter-state: show IGST
        totals_data.append(['IGST:', f"₹{igst_amount:.2f}"])
    else:
        # Intra-state: show CGST and SGST
        if cgst_amount > 0:
            totals_data.append(['CGST:', f"₹{cgst_amount:.2f}"])
        if sgst_amount > 0:
            totals_data.append(['SGST:', f"₹{sgst_amount:.2f}"])
    
    # Total always appears at the end
    totals_data.append(['Total:', f"₹{invoice.grand_total:.2f}"])
    
    totals_table = Table(totals_data, colWidths=[4.5 * inch, 2 * inch])
    totals_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -2), 'Helvetica'),
        ('FONTNAME', (0, -1), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -2), 11),
        ('FONTSIZE', (0, -1), (-1, -1), 13),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -2), 8),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 12),
        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.HexColor('#4a90e2')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f0f8ff')),
    ]))
    
    elements.append(totals_table)
    
    # Build PDF
    doc.build(elements)
    
    # Get PDF bytes
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes
