"""
GST Rate Lookup Tool
Core authority module for GST HSN code to rate mapping.
Returns structured JSON (Python dicts) for AI-native GST invoicing system.
"""

import json
from pathlib import Path
from typing import Dict, Any


# Ambiguous HSN codes that require clarification
AMBIGUOUS_HSN_CONFIG = {
    "210690": {
        "possible_rates": [12, 18, 28],
        "question": "Is the item namkeen/bhujia, branded food preparation, or pan masala/tobacco?"
    }
}

# Supported GST rate slabs
SUPPORTED_GST_SLABS = [5, 12, 18, 28]


def get_gst_rate_by_hsn(hsn_code: str) -> Dict[str, Any]:
    """
    Look up GST rate for a given HSN code.
    
    This function is the core GST authority for the invoicing system.
    It ONLY determines GST slab - it does NOT calculate tax amounts.
    
    Args:
        hsn_code: The HSN/SAC code to look up (will be normalized)
    
    Returns:
        CASE 1 - Clear GST rate:
        {
            "hsn": "0801",
            "gst_rate": 5,
            "description": "Cashew nuts, whether or not shelled or peeled",
            "source": "Notification No. 1/2017 – Central Tax (Rate)"
        }
        
        CASE 2 - Ambiguous GST rate:
        {
            "hsn": "210690",
            "status": "AMBIGUOUS",
            "possible_rates": [12, 18, 28],
            "question": "Is the item namkeen/bhujia, branded food preparation, or pan masala/tobacco?",
            "source": "Notification No. 1/2017 – Central Tax (Rate)"
        }
        
        CASE 3 - HSN not found:
        {
            "error": "HSN_NOT_FOUND",
            "message": "HSN <code> is not configured in the GST system"
        }
    """
    # Normalize HSN code
    hsn_code = hsn_code.strip().upper()
    
    # Check if this is a known ambiguous HSN
    if hsn_code in AMBIGUOUS_HSN_CONFIG:
        ambiguous_info = AMBIGUOUS_HSN_CONFIG[hsn_code]
        return {
            "hsn": hsn_code,
            "status": "AMBIGUOUS",
            "possible_rates": ambiguous_info["possible_rates"],
            "question": ambiguous_info["question"],
            "source": "Notification No. 1/2017 – Central Tax (Rate)"
        }
    
    # Locate the GST rates file
    current_file = Path(__file__)
    project_root = current_file.parent.parent
    gst_data_file = project_root / "data" / "gst_rates.json"
    
    # Load GST data
    try:
        with open(gst_data_file, "r", encoding="utf-8") as f:
            gst_data = json.load(f)
    except FileNotFoundError:
        return {
            "error": "DATA_FILE_NOT_FOUND",
            "message": f"GST rates file not found at {gst_data_file}"
        }
    except json.JSONDecodeError as e:
        return {
            "error": "INVALID_JSON",
            "message": f"Failed to parse GST rates file: {str(e)}"
        }
    except Exception as e:
        return {
            "error": "FILE_READ_ERROR",
            "message": f"Error reading GST rates file: {str(e)}"
        }
    
    # Look up HSN code
    hsn_rates = gst_data.get("hsn_rates", {})
    
    if hsn_code not in hsn_rates:
        return {
            "error": "HSN_NOT_FOUND",
            "message": f"HSN {hsn_code} is not configured in the GST system"
        }
    
    # Extract rate information
    rate_info = hsn_rates[hsn_code]
    gst_rate = rate_info["gst_rate"]
    
    # Validate GST rate is in supported slabs
    if gst_rate not in SUPPORTED_GST_SLABS:
        return {
            "error": "INVALID_GST_RATE",
            "message": f"GST rate {gst_rate}% for HSN {hsn_code} is not in supported slabs: {SUPPORTED_GST_SLABS}"
        }
    
    # Get source from metadata
    source_info = gst_data.get("metadata", {}).get("source", "Notification No. 1/2017 – Central Tax (Rate)")
    
    return {
        "hsn": hsn_code,
        "gst_rate": gst_rate,
        "description": rate_info["description"],
        "source": source_info
    }


if __name__ == "__main__":
    # Test the function with sample HSN codes
    import json as json_pretty
    
    test_cases = [
        ("0801", "Clear rate - 5%"),
        ("9983", "Clear rate - 18%"),
        ("1806", "Clear rate - 28%"),
        ("210690", "Ambiguous rate"),
        ("INVALID123", "Unknown HSN"),
    ]
    
    print("GST Rate Lookup Tool - Test Suite")
    print("=" * 70)
    
    for hsn_code, description in test_cases:
        print(f"\nTest: {description}")
        print(f"HSN Code: {hsn_code}")
        print("-" * 70)
        
        result = get_gst_rate_by_hsn(hsn_code)
        print(json_pretty.dumps(result, indent=2))
    
    print("\n" + "=" * 70)
    print("✓ All test cases completed")
