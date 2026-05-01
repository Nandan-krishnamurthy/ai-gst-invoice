# GST Invoice System

An AI-assisted GST invoice system for creating tax invoices from natural language input or image-based conversation summaries. The workflow supports draft creation, review, finalization, GST calculation, and PDF generation.

---

## Features

### Completed

- Invoice creation through natural language commands
- Image-based invoice extraction from screenshots and chat exports, including WhatsApp conversations
- Draft-to-finalize workflow with invoice status tracking
- GST calculation for intra-state and inter-state invoices
- HSN-based GST rate assignment at item level
- Customer creation and lookup by phone number or GSTIN
- Company profile management for seller details
- Invoice persistence in PostgreSQL via Supabase
- PDF generation for finalized invoices
- Invoice listing and PDF download support
- Inline draft editing in the frontend
- Session-based agent flow scoped to the active browser tab

### In Progress

- Refinement of CGST/SGST/IGST presentation in the preview and PDF output
- Alignment of GST validation between draft review and final invoice generation
- Standardization of customer identifier handling across edge cases
- Persistent session support for multi-worker deployments

---

## Tech Stack

**Backend**
- Python 3.11+
- FastAPI
- SQLAlchemy ORM
- PostgreSQL via Supabase
- Mistral OCR API (image text extraction)
- Google Gemini (LLM extraction fallback)
- ReportLab (PDF generation)

**Frontend**
- React 19 (Vite)
- Plain CSS (no UI framework)

**Database**
- PostgreSQL hosted on Supabase
- JSONB columns for invoice party and item data

---

## Project Structure

```
GST-MCP-invoice/
├── main.py                    # FastAPI app entry point
├── app/
│   ├── agent/                 # Core invoice agent logic
│   │   ├── agent_service.py   # Message handler and state machine
│   │   ├── draft_service.py   # Draft creation, update, validation
│   │   ├── session_service.py # Session and active-draft tracking
│   │   ├── router.py          # Agent API endpoints
│   │   ├── schemas.py         # Request/response Pydantic models
│   │   ├── agent_state.py     # AgentState enum
│   │   └── interpreter/       # Image/text invoice parser
│   │       ├── handler.py     # OCR + parse + draft creation
│   │       ├── parser.py      # Regex-based field extraction
│   │       ├── matcher.py     # Customer phone lookup
│   │       ├── intent.py      # Action detection
│   │       └── service.py     # Orchestration
│   ├── customer/              # Customer management
│   │   ├── crud.py
│   │   ├── handler.py         # Conversational customer flow
│   │   ├── router.py
│   │   └── schemas.py
│   ├── db/
│   │   ├── database.py        # SQLAlchemy engine and session
│   │   ├── models.py          # Invoice, AgentSession ORM models
│   │   └── crud.py
│   ├── models/
│   │   ├── company.py         # Company/seller ORM model
│   │   └── company_router.py  # Company profile endpoints
│   ├── llm/
│   │   └── llm_service.py     # Gemini LLM extraction
│   └── services/
│       ├── ocr_service.py     # Mistral OCR wrapper
│       └── pdf_generator.py   # ReportLab PDF builder
├── invoice/
│   ├── invoice_engine.py      # GST calculation and invoice generation
│   ├── model.py               # Pydantic request/response models
│   ├── router.py              # Invoice CRUD endpoints
│   └── service.py             # Invoice creation service
├── engine/
│   └── gst_calculator.py      # CGST/SGST/IGST calculation logic
├── mcp/
│   └── gst_rate_tool.py       # HSN to GST rate lookup
├── data/
│   └── gst_rates.json         # HSN rate reference data
├── invoices/
│   └── pdfs/                  # Generated PDF output directory
└── frontend/
    ├── src/
    │   ├── App.jsx            # Main UI and state management
    │   ├── InvoicePreview.jsx # Editable invoice preview component
    │   └── InterpreterPreview.jsx  # Image/text parse result display
    └── vite.config.js
```

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- A Supabase project with a PostgreSQL database
- Mistral API key (for OCR)
- Google Gemini API key (for LLM extraction fallback)

### Backend

```bash
# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Fill in DATABASE_URL, MISTRAL_API_KEY, GEMINI_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

# Start the backend server
uvicorn main:app --reload --port 8000
```

API documentation is available at `http://localhost:8000/docs` once the server is running.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at `http://localhost:5173` and expects the backend at `http://localhost:8000`.

---

## Example Usage

### Natural Language (Chat)

Enter commands directly in the chat interface:

```
create invoice for Rahul Sharma, Karnataka
add 2 laptops at 80000 gst 18
hsn code is 8471
finalize
```

The system creates a draft, applies incremental updates, and finalizes the invoice with database persistence and PDF output.

### Image Upload

Upload a screenshot or exported image, such as a WhatsApp conversation or order summary. The system:
1. Extracts text from the image using Mistral OCR
2. Parses the content into structured invoice details, including customer data, line items, pricing, and GST
3. Matches the customer by phone number when an existing record is available
4. Creates a draft invoice for review and editing before finalization

---

## How It Works

```
User input (text or image)
        │
        ▼
Interpreter / Agent handler
 - Text: regex + LLM extraction
 - Image (screenshot/chat export): Mistral OCR → same parser
        │
        ▼
Draft invoice created in DB
 - session_id links browser session to draft
 - seller auto-filled from company profile
        │
        ▼
User reviews and edits (frontend InvoicePreview)
 - buyer details, items, HSN codes, quantities
        │
        ▼
Finalize
 - validate_draft_for_finalization()
 - generate_invoice() → GST calculation
 - status set to "finalized"
 - PDF generated via ReportLab
 - active_draft cleared from session
        │
        ▼
Invoice persisted, PDF downloadable
```

---

## Current Status

Core workflows are stable and operational:

- Natural language invoice creation and finalization
- Image-based invoice creation and finalization
- Customer creation and lookup
- Company profile management
- Invoice listing, retrieval, and PDF download
- Draft editing prior to finalization

Known limitations:

- GST treatment for certain CGST/SGST/IGST edge cases is still being refined.
- Minor differences may appear between preview totals and generated PDF totals in some edge cases.
- Session state is currently held in memory and is not preserved across server restarts, although invoice records remain persisted in the database.

---

## Future Improvements

- Consolidate invoice finalization into a single, consistent execution path
- Move session handling to persistent storage for restart safety and multi-worker support
- Expand invoice party models to preserve complete buyer and seller details throughout processing
- Add messaging-based integrations such as WhatsApp and webhook ingestion
- Introduce role-based access and multi-tenant seller management
- Support invoice amendments and credit notes
- Add reporting views for GST summaries and invoice activity
