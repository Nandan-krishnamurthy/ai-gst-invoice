"""
GST Calculation Engine
======================
This module performs GST tax calculations only.
It does NOT decide GST rates or contain HSN logic.

Author: GST Invoice System
Date: January 13, 2026
"""

from typing import Dict


def calculate_gst(taxable_value: float, gst_rate: int, supply_type: str) -> Dict[str, float]:
    """
    Calculate GST components based on taxable value, GST rate, and supply type.
    
    Args:
        taxable_value: The taxable amount (must be > 0)
        gst_rate: GST rate percentage (must be one of: 5, 12, 18, 28)
        supply_type: Type of supply - "intra" for intra-state, "inter" for inter-state
    
    Returns:
        Dictionary containing:
        - taxable_value: Original taxable amount
        - gst_rate: Applied GST rate
        - cgst: Central GST amount (for intra-state)
        - sgst: State GST amount (for intra-state)
        - igst: Integrated GST amount (for inter-state)
        - cgst_amount: Central GST amount (alias of cgst)
        - sgst_amount: State GST amount (alias of sgst)
        - igst_amount: Integrated GST amount (alias of igst)
        - total_tax: Total tax amount
        - invoice_total: Final invoice total (taxable_value + total_tax)
        - total_amount: Final invoice total (alias of invoice_total)
    
    Raises:
        ValueError: If inputs are invalid
    
    Examples:
        >>> calculate_gst(10000, 18, "intra")
        {'taxable_value': 10000, 'gst_rate': 18, 'cgst': 900.0, 'sgst': 900.0, 
         'igst': 0.0, 'total_tax': 1800.0, 'invoice_total': 11800.0}
        
        >>> calculate_gst(10000, 18, "inter")
        {'taxable_value': 10000, 'gst_rate': 18, 'cgst': 0.0, 'sgst': 0.0, 
         'igst': 1800.0, 'total_tax': 1800.0, 'invoice_total': 11800.0}
    """
    # Validate taxable_value
    if not isinstance(taxable_value, (int, float)):
        raise ValueError(f"taxable_value must be a number, got {type(taxable_value).__name__}")
    
    if taxable_value <= 0:
        raise ValueError(f"taxable_value must be greater than 0, got {taxable_value}")
    
    # Validate gst_rate
    ALLOWED_GST_RATES = [0, 5, 12, 18, 28]
    if gst_rate not in ALLOWED_GST_RATES:
        raise ValueError(
            f"gst_rate must be one of {ALLOWED_GST_RATES}, got {gst_rate}"
        )
    
    # Validate supply_type
    ALLOWED_SUPPLY_TYPES = ["intra", "inter"]
    supply_type_lower = supply_type.lower() if isinstance(supply_type, str) else ""
    
    if supply_type_lower not in ALLOWED_SUPPLY_TYPES:
        raise ValueError(
            f"supply_type must be one of {ALLOWED_SUPPLY_TYPES}, got '{supply_type}'"
        )
    
    # Initialize tax components
    cgst = 0.0
    sgst = 0.0
    igst = 0.0
    
    # Calculate tax based on supply type
    if gst_rate > 0:
        if supply_type_lower == "intra":
            # Intra-state: Split equally between CGST and SGST
            half_rate = gst_rate / 2
            cgst = round(taxable_value * half_rate / 100, 2)
            sgst = round(taxable_value * half_rate / 100, 2)
        else:  # inter
            # Inter-state: Full rate as IGST
            igst = round(taxable_value * gst_rate / 100, 2)
    
    # Calculate totals
    total_tax = cgst + sgst + igst
    invoice_total = taxable_value + total_tax
    
    return {
        "taxable_value": taxable_value,
        "gst_rate": gst_rate,
        "cgst": cgst,
        "sgst": sgst,
        "igst": igst,
        "cgst_amount": cgst,
        "sgst_amount": sgst,
        "igst_amount": igst,
        "total_tax": total_tax,
        "invoice_total": invoice_total,
        "total_amount": invoice_total
    }


if __name__ == "__main__":
    # Test cases
    print("=" * 60)
    print("GST Calculation Engine - Test Cases")
    print("=" * 60)
    
    # Test 1: Intra-state supply
    print("\nTest 1: Intra-state supply (₹10,000 @ 18% GST)")
    result = calculate_gst(10000, 18, "intra")
    print(f"Taxable Value: ₹{result['taxable_value']}")
    print(f"GST Rate: {result['gst_rate']}%")
    print(f"CGST (9%): ₹{result['cgst']}")
    print(f"SGST (9%): ₹{result['sgst']}")
    print(f"Total Tax: ₹{result['total_tax']}")
    print(f"Invoice Total: ₹{result['invoice_total']}")
    
    # Test 2: Inter-state supply
    print("\nTest 2: Inter-state supply (₹10,000 @ 18% GST)")
    result = calculate_gst(10000, 18, "inter")
    print(f"Taxable Value: ₹{result['taxable_value']}")
    print(f"GST Rate: {result['gst_rate']}%")
    print(f"IGST (18%): ₹{result['igst']}")
    print(f"Total Tax: ₹{result['total_tax']}")
    print(f"Invoice Total: ₹{result['invoice_total']}")
    
    # Test 3: Different GST rates
    print("\nTest 3: Different GST rates (₹5,000)")
    for rate in [5, 12, 18, 28]:
        result = calculate_gst(5000, rate, "intra")
        print(f"  @ {rate}% GST: Total Tax = ₹{result['total_tax']}, Invoice Total = ₹{result['invoice_total']}")
    
    # Test 4: Error handling
    print("\nTest 4: Error handling")
    try:
        calculate_gst(-100, 18, "intra")
    except ValueError as e:
        print(f"  ✓ Caught error: {e}")
    
    try:
        calculate_gst(1000, 15, "intra")
    except ValueError as e:
        print(f"  ✓ Caught error: {e}")
    
    try:
        calculate_gst(1000, 18, "invalid")
    except ValueError as e:
        print(f"  ✓ Caught error: {e}")
    
    print("\n" + "=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)
