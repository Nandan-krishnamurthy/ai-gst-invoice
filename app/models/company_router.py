from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.company import Company

router = APIRouter(prefix="/company", tags=["Company"])


@router.get("/")
def get_company(db: Session = Depends(get_db)):
    """Return the company (seller) profile used as the default seller on all invoices."""
    company = db.query(Company).first()
    if not company:
        raise HTTPException(status_code=404, detail="No company profile found.")
    return {
        "name": company.name,
        "gstin": company.gstin,
        "state": company.state,
        "address": company.address,
    }
