"""
Pure helper functions for invoice agent logic.
No side effects, no database access.
"""
from typing import Dict, Any, List
from app.db.models import Invoice


def _normalize_party_payload(party: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure party payload has a consistent structure with nullable fields.
    """
    party = party or {}
    name = party.get("name")
    if isinstance(name, str):
        name = name.strip() or None
    gstin = party.get("gstin")
    if isinstance(gstin, str):
        gstin = gstin.strip() or None
    address = party.get("address")
    if isinstance(address, str):
        address = address.strip() or None
    state = party.get("state")
    if isinstance(state, str):
        state = state.strip() or None
    return {
        "name": name,
        "gstin": gstin,
        "address": address,
        "state": state,
    }


def _get_items_missing_hsn(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Get list of items with GST rate > 0 that are missing HSN code.
    
    Returns:
        List of dicts with 'description' and 'index' of items missing HSN
    """
    missing_hsn_items = []
    for idx, item in enumerate(items):
        # Safely handle None values: treat missing/None gst_rate as 0
        gst_rate = item.get("gst_rate") or 0
        hsn_code = item.get("hsn_code")
        if gst_rate > 0 and not hsn_code:
            missing_hsn_items.append({
                "description": item.get("description", "unknown"),
                "index": idx
            })
    return missing_hsn_items


def _build_invoice_preview(draft: Invoice) -> Dict[str, Any]:
    """
    Build invoice preview payload from draft invoice.
    
    Args:
        draft: Draft invoice object
    
    Returns:
        Dictionary with invoice preview data
    """
    return {
        "invoice_no": draft.invoice_no,
        "seller": draft.seller,
        "buyer": draft.buyer,
        "items": draft.items,
        "subtotal": draft.subtotal,
        "total_gst": draft.total_gst,
        "cgst": draft.gst_summary.get("cgst") if draft.gst_summary else 0,
        "sgst": draft.gst_summary.get("sgst") if draft.gst_summary else 0,
        "igst": draft.gst_summary.get("igst") if draft.gst_summary else 0,
        "grand_total": draft.grand_total
    }


def _get_missing_party_fields(party: Dict[str, Any], label: str) -> List[str]:
    missing = []
    for field in ["name", "state", "gstin"]:
        if not party.get(field) or party.get(field) == "TBD":
            missing.append(f"{label}.{field}")
    return missing


def _check_critical_validation_errors(draft: Invoice) -> List[str]:
    """
    Check for critical validation errors that block draft creation.
    
    Critical issues:
    * No items in invoice
    * Item quantity <= 0
    * Item unit_price <= 0
    
    Args:
        draft: Draft invoice object
        
    Returns:
        List of critical error messages (empty if valid)
    """
    critical_errors = []
    
    items = draft.items or []
    
    # Critical: Must have at least one item
    if not items:
        critical_errors.append("Invoice must have at least one item.")
        return critical_errors
    
    # Critical: Check item quantities and prices
    for idx, item in enumerate(items):
        quantity = item.get("quantity", 0)
        # Check both "price" and "unit_price" for compatibility
        unit_price = item.get("price", item.get("unit_price", 0))
        
        try:
            qty_float = float(quantity)
            price_float = float(unit_price)
        except (ValueError, TypeError):
            critical_errors.append(f"Item {idx + 1}: Invalid quantity or price.")
            continue
        
        if qty_float <= 0:
            critical_errors.append(f"Item {idx + 1}: Quantity must be greater than 0.")
        
        if price_float <= 0:
            critical_errors.append(f"Item {idx + 1}: Unit price must be greater than 0.")
    
    return critical_errors


def _get_non_critical_warnings(draft: Invoice) -> List[str]:
    """
    Collect non-critical warnings that don't block draft creation.
    
    Non-critical fields:
    * buyer.state (can be inferred or defaulted)
    * buyer.address (can be added later)
    * buyer.gstin (can be added later)
    * HSN codes (can be added later)
    
    Args:
        draft: Draft invoice object
        
    Returns:
        List of warning messages about non-critical missing fields
    """
    warnings = []
    
    buyer = draft.buyer or {}
    
    # Non-critical: Buyer state might be TBD (will be inferred later)
    if not buyer.get("state") or buyer.get("state") == "TBD":
        warnings.append("buyer.state")
    
    # Non-critical: GSTIN can be added during finalization
    if not buyer.get("gstin"):
        warnings.append("buyer.gstin")
    
    # Non-critical: Address can be added/updated later
    if not buyer.get("address"):
        warnings.append("buyer.address")
    
    # Non-critical: HSN codes for taxable items (can be added later)
    items = draft.items or []
    missing_hsn_items = _get_items_missing_hsn(items)
    for item in missing_hsn_items:
        warnings.append(f"hsn_code[{item['description']}]")
    
    return warnings
