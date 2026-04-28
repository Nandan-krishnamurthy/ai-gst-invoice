"""
FastAPI application for GST rate lookup and calculation.

This module exposes HTTP APIs for:
1. GST rate lookup by HSN code
2. GST tax calculation

It wraps the backend logic without duplicating business rules.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import sys
from pathlib import Path
from app.db.database import engine
from app.db.models import Base
from fastapi.middleware.cors import CORSMiddleware



# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.gst_rate_tool import get_gst_rate_by_hsn
from engine.gst_calculator import calculate_gst
from invoice.router import router as invoice_router
from app.agent.router import router as agent_router
from app.api.upload_test import router as upload_test_router
from app.customer.router import router as customer_router
from app.models.company_router import router as company_router

app = FastAPI(
    title="GST Invoice API",
    description="AI-native GST invoicing system - Rate lookup and calculation",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(invoice_router)
app.include_router(agent_router)
app.include_router(upload_test_router)
app.include_router(customer_router)
app.include_router(company_router)

# ============================================================================
# REQUEST MODELS
# ============================================================================

class GSTRateRequest(BaseModel):
    """Request model for GST rate lookup."""
    hsn_code: str = Field(..., description="HSN code to lookup", example="0801")


class GSTCalculationRequest(BaseModel):
    """Request model for GST calculation."""
    taxable_value: float = Field(..., gt=0, description="Taxable amount", example=10000.0)
    gst_rate: int = Field(..., description="GST rate (5, 12, 18, or 28)", example=18)
    supply_type: str = Field(..., description="Supply type: 'intra' or 'inter'", example="intra")


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/")
def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "GST Invoice API",
        "version": "1.0.0"
    }


@app.post("/gst-rate")
def lookup_gst_rate(request: GSTRateRequest):
    """
    Lookup GST rate by HSN code.
    
    Returns:
    - Clear rate: hsn, gst_rate, description, source
    - Ambiguous: status, possible_rates, question, source
    - Error: error, message
    """
    try:
        result = get_gst_rate_by_hsn(request.hsn_code)
        
        # If there's an error in the result, return 404
        if "error" in result:
            raise HTTPException(status_code=404, detail=result)
        
        return result
    
    except Exception as e:
        # Catch any unexpected errors
        raise HTTPException(
            status_code=500,
            detail={"error": "INTERNAL_ERROR", "message": str(e)}
        )


@app.post("/calculate-gst")
def calculate_gst_tax(request: GSTCalculationRequest):
    """
    Calculate GST tax breakdown.
    
    Returns:
    - taxable_value, gst_rate, cgst, sgst, igst, total_tax, invoice_total
    """
    try:
        result = calculate_gst(
            taxable_value=request.taxable_value,
            gst_rate=request.gst_rate,
            supply_type=request.supply_type
        )
        return result
    
    except ValueError as e:
        # Invalid input - return 400 Bad Request
        raise HTTPException(
            status_code=400,
            detail={"error": "INVALID_INPUT", "message": str(e)}
        )
    
    except Exception as e:
        # Catch any unexpected errors
        raise HTTPException(
            status_code=500,
            detail={"error": "INTERNAL_ERROR", "message": str(e)}
        )


# ============================================================================
# MAIN (for local development)
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
