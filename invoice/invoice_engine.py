from datetime import datetime, timezone
from typing import Dict, Any
from engine.gst_calculator import calculate_gst
from invoice.model import InvoiceRequest


def generate_invoice(invoice_request: InvoiceRequest) -> Dict[str, Any]:
    """
    Generate invoice with GST calculations.
    
    Args:
        invoice_request: Invoice request with seller, buyer, and items
    
    Returns:
        Dictionary matching InvoiceResponse schema
    """
    # Determine if intra-state or inter-state
    is_inter_state = invoice_request.seller.state != invoice_request.buyer.state
    supply_type = "inter" if is_inter_state else "intra"
    
    # Initialize aggregates
    taxable_total = 0.0
    gst_total = 0.0
    invoice_items = []
    
    # Process each item
    for item in invoice_request.items:
        # Calculate taxable value
        taxable_value = item.quantity * item.unit_price
        
        # Call GST calculator only if gst_rate > 0 (skip if 0)
        if item.gst_rate > 0:
            gst_result = calculate_gst(
                taxable_value=taxable_value,
                gst_rate=item.gst_rate,
                supply_type=supply_type
            )
            
            # Extract GST information from calculation result
            gst_amount = gst_result["total_tax"]
            total_amount = gst_result["total_amount"]
            cgst = gst_result["cgst_amount"]
            sgst = gst_result["sgst_amount"]
            igst = gst_result["igst_amount"]
        else:
            # No GST for 0% items
            gst_amount = 0.0
            total_amount = taxable_value
            cgst = 0.0
            sgst = 0.0
            igst = 0.0
        
        # Build item response
        invoice_items.append({
            "description": item.description,
            "hsn_code": item.hsn_code,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "taxable_value": taxable_value,
            "gst_rate": item.gst_rate,
            "cgst": cgst,
            "sgst": sgst,
            "igst": igst,
            "gst_amount": gst_amount,
            "total_amount": total_amount
        })
        
        # Aggregate totals
        taxable_total += taxable_value
        gst_total += gst_amount
    
    # Calculate grand total
    grand_total = taxable_total + gst_total
    
    # Generate invoice number and timestamp
    invoice_datetime = datetime.now(timezone.utc)
    invoice_no = f"INV-{invoice_request.invoice_date.strftime('%Y%m%d')}-{id(invoice_request)}"
    
    # Build and return invoice response
    return {
        "invoice_no": invoice_no,
        "invoice_date": invoice_request.invoice_date,
        "invoice_datetime": invoice_datetime,
        "seller": {"state": invoice_request.seller.state},
        "buyer": {"state": invoice_request.buyer.state},
        "items": invoice_items,
        "taxable_total": taxable_total,
        "gst_total": gst_total,
        "grand_total": grand_total
    }
