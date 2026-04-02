import re
from typing import Any, Dict, Optional

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import Session

from app.agent.agent_state import AgentState
from app.agent.schemas import AgentResponse
from app.customer.crud import create_customer, find_by_gstin_or_name
from app.customer.llm_extractor import extract_customer_llm
from app.customer.validator import validate_customer_llm
from app.db.database import Base, engine

# ---------------------------------------------------------------------------
# CustomerContact model (inline — avoids creating new files)
# ---------------------------------------------------------------------------

try:
    from app.db.models import CustomerContact  # type: ignore
except ImportError:
    class CustomerContact(Base):  # type: ignore
        __tablename__ = "customer_contacts"

        id = Column(Integer, primary_key=True, index=True)
        customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
        contact_name = Column(String, nullable=True)
        phone = Column(String, nullable=True)
        email = Column(String, nullable=True)
        designation = Column(String, nullable=True)

    Base.metadata.create_all(bind=engine, tables=[CustomerContact.__table__])


# Session-scoped in-memory customer conversation state.
CUSTOMER_STATE: Dict[str, Dict[str, Any]] = {}


def _get_state(session_id: str) -> Dict[str, Any]:
    if session_id not in CUSTOMER_STATE:
        CUSTOMER_STATE[session_id] = {
            "customer": {
                "name": None,
                "gstin": None,
                "phone": None,
                "email": None,
                "city": None,
                "state": None,
            },
            "awaiting": None,
        }
    return CUSTOMER_STATE[session_id]  # Already has city, state initialized


def _clear_state(session_id: str) -> None:
    CUSTOMER_STATE.pop(session_id, None)


def has_active_customer_session(session_id: str) -> bool:
    """Return True if this session has an active customer conversation in progress."""
    state = CUSTOMER_STATE.get(session_id)
    return state is not None and state.get("awaiting") is not None


# ---------------------------------------------------------------------------
# Customer preview (distinct from invoice preview)
# ---------------------------------------------------------------------------

def build_customer_preview(customer_state: Dict[str, Any], ready: bool = False) -> Dict[str, Any]:
    return {
        "type": "customer_preview",
        "data": {
            "name": customer_state.get("name"),
            "gstin": customer_state.get("gstin"),
            "phone": customer_state.get("phone"),
            "email": customer_state.get("email"),
            "city": customer_state.get("city"),
            "state": customer_state.get("state"),
        },
        "ready": ready,
    }


# ---------------------------------------------------------------------------
# Field extractors
# ---------------------------------------------------------------------------

def _extract_inline_fields(message: str):
    """
    Parse one-liner like:
            create customer nandan phone 9876543210 email abc@gmail.com gstin 29ABCDE1234F1Z5, Bangalore, Karnataka
            create customer nandan city Bangalore state Karnataka
        Returns dict with name, gstin, phone, email, city, state.
    """
    text = message.strip()

    phone: Optional[str] = None
    email: Optional[str] = None
    gstin: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None

    phone_m = re.search(r"\bphone\s+([6-9]\d{9})\b", text, re.IGNORECASE)
    if phone_m:
        phone = phone_m.group(1)

    email_m = re.search(r"\bemail\s+(\S+@\S+\.\S+)\b", text, re.IGNORECASE)
    if email_m:
        email = email_m.group(1).lower()

    gstin_m = re.search(r"\bgstin\s+([A-Za-z0-9]{8,15})\b", text, re.IGNORECASE)
    if gstin_m:
        gstin = gstin_m.group(1).upper()

    # Format: "city Bangalore state Karnataka" (order can vary)
    city_m = re.search(
        r"\bcity\s*[:=]?\s*([A-Za-z][A-Za-z\s.-]{1,60}?)(?=\s+\b(?:state|phone|email|gstin)\b|,|$)",
        text,
        re.IGNORECASE,
    )
    if city_m:
        city = " ".join(city_m.group(1).strip().split()).title()

    state_m = re.search(
        r"\bstate\s*[:=]?\s*([A-Za-z][A-Za-z\s.-]{1,60}?)(?=\s+\b(?:city|phone|email|gstin)\b|,|$)",
        text,
        re.IGNORECASE,
    )
    if state_m:
        state = " ".join(state_m.group(1).strip().split()).title()

    # Name: text between "customer " and first keyword tag
    name_m = re.search(
        r"(?:create|add)\s+customer\s+([A-Za-z0-9&.'\-\s]+?)(?=,|\s+\b(?:phone|email|gstin|city|state)\b|$)",
        text, re.IGNORECASE,
    )
    name: Optional[str] = None
    if name_m:
        name = name_m.group(1).strip() or None

    # Format: trailing location "..., Bangalore, Karnataka"
    # Use comma chunks that are not known tagged fields.
    if not city or not state:
        chunks = [chunk.strip() for chunk in text.split(",") if chunk.strip()]
        free_chunks = []
        for chunk in chunks:
            lowered = chunk.lower()
            if any(tag in lowered for tag in ["phone", "email", "gstin", "city", "state"]):
                continue
            if re.search(r"[6-9]\d{9}", chunk) or "@" in chunk:
                continue

            cleaned_chunk = " ".join(chunk.split())
            from_m = re.search(r"\bfrom\s+([A-Za-z][A-Za-z\s.-]{1,60})$", cleaned_chunk, re.IGNORECASE)
            if from_m:
                cleaned_chunk = from_m.group(1).strip()

            if cleaned_chunk:
                free_chunks.append(cleaned_chunk.title())

        if len(free_chunks) >= 2:
            city = city or free_chunks[-2]
            state = state or free_chunks[-1]

    return {
        "name": name,
        "gstin": gstin,
        "phone": phone,
        "email": email,
        "city": city,
        "state": state,
    }


def _looks_like_full_customer_command(text: str) -> bool:
    lowered = text.lower()
    if "create customer" in lowered or "add customer" in lowered:
        return True
    keyword_count = sum(1 for key in ["phone", "email", "gstin", "city", "state"] if key in lowered)
    return keyword_count >= 2


def _extract_gstin(message: str) -> Optional[str]:
    explicit = re.search(r"\bgstin\s*[:=]?\s*([A-Za-z0-9]{8,15})\b", message, re.IGNORECASE)
    if explicit:
        return explicit.group(1).upper()
    bare = re.search(r"\b([A-Za-z0-9]{15})\b", message)
    return bare.group(1).upper() if bare else None


def _extract_phone(message: str) -> Optional[str]:
    m = re.search(r"(?:\+?91[-\s]?)?([6-9]\d{9})\b", message)
    return m.group(1) if m else None


def _extract_email(message: str) -> Optional[str]:
    m = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", message)
    return m.group(0).lower() if m else None


# ---------------------------------------------------------------------------
# DB save: both customers + customer_contacts
# ---------------------------------------------------------------------------

def _save_customer(session_id: str, customer_state: Dict[str, Any], db: Session) -> AgentResponse:
    name = customer_state["name"]
    gstin = customer_state.get("gstin")
    city = customer_state.get("city")
    state_value = customer_state.get("state")
    phone = customer_state.get("phone")
    email = customer_state.get("email")

    existing = find_by_gstin_or_name(db=db, name=name, gstin=gstin)
    if existing:
        name_display = " ".join(w.capitalize() for w in existing.name.split())
        _clear_state(session_id)
        return AgentResponse(
            message=f"Customer {name_display} already exists.",
            agent_state=AgentState.AWAITING_CONFIRMATION,
            invoice={"type": "customer_created", "message": f"Customer {name_display} already exists."},
            next_expected_input="",
        )

    created = create_customer(
        db=db,
        customer_state={
            "name": name,
            "gstin": gstin,
            "city": city,
            "state": state_value,
        },
        auto_commit=False,
    )
    customer_id = created.id

    contact = CustomerContact(
        customer_id=customer_id,
        contact_name=name,
        phone=phone,
        email=email,
        designation=None,
    )
    db.add(contact)
    # Single transaction for both inserts: customer row and contact row.
    db.commit()

    name_display = " ".join(w.capitalize() for w in name.split())
    _clear_state(session_id)
    return AgentResponse(
        message=f"Customer {name_display} created successfully.",
        agent_state=AgentState.AWAITING_CONFIRMATION,
        invoice={"type": "customer_created", "message": f"Customer {name_display} created successfully."},
        next_expected_input="",
    )


# ---------------------------------------------------------------------------
# Main conversational handler
# ---------------------------------------------------------------------------

def handle_customer_message(session_id: str, message: str, db: Session) -> AgentResponse:
    text = (message or "").strip()
    state = _get_state(session_id)
    customer_state = state["customer"]
    awaiting = state.get("awaiting")

    # ------------------------------------------------------------------
    # Step 1: Initial trigger
    # ------------------------------------------------------------------
    if not awaiting:
        extracted = _extract_inline_fields(text)
        name = extracted["name"]
        gstin = extracted["gstin"]
        phone = extracted["phone"]
        email = extracted["email"]
        city = extracted["city"]
        state_value = extracted["state"]

        # LLM fallback: only when regex is weak (missing name or missing phone)
        if not name or not phone:
            try:
                llm_raw = extract_customer_llm(text)
                llm_clean = validate_customer_llm(llm_raw)
                if not name:
                    name = llm_clean.get("name")
                if not phone:
                    phone = llm_clean.get("phone")
                if not email:
                    email = llm_clean.get("email")
            except Exception:
                pass  # LLM failure is non-fatal; regex result continues unchanged

        if not name:
            return AgentResponse(
                message="Could not parse customer name. Use: 'create customer <name>'",
                agent_state=AgentState.COLLECTING_INFO,
                next_expected_input="Use 'create customer Rahul' to begin.",
            )

        customer_state["name"] = name
        customer_state["gstin"] = gstin
        customer_state["phone"] = phone
        customer_state["email"] = email
        customer_state["city"] = city
        customer_state["state"] = state_value

        # Determine next step: gstin → phone → email → city (if all prior present)
        if not gstin:
            state["awaiting"] = "gstin"
            return AgentResponse(
                message="Do you want to add GSTIN? (optional — reply 'skip' to skip)",
                agent_state=AgentState.COLLECTING_INFO,
                invoice=build_customer_preview(customer_state),
                next_expected_input="Provide GSTIN or reply 'skip'.",
            )

        if not phone:
            state["awaiting"] = "phone"
            return AgentResponse(
                message="What is the phone number?",
                agent_state=AgentState.COLLECTING_INFO,
                invoice=build_customer_preview(customer_state),
                next_expected_input="Provide a 10-digit phone number.",
            )

        if not email:
            state["awaiting"] = "email"
            return AgentResponse(
                message="What is the email address?",
                agent_state=AgentState.COLLECTING_INFO,
                invoice=build_customer_preview(customer_state),
                next_expected_input="Provide email or reply 'skip'.",
            )

        if not customer_state.get("city"):
            state["awaiting"] = "city"
            return AgentResponse(
                message="What is the city?",
                agent_state=AgentState.COLLECTING_INFO,
                invoice=build_customer_preview(customer_state),
                next_expected_input="Provide city name.",
            )

        if not customer_state.get("state"):
            state["awaiting"] = "state"
            return AgentResponse(
                message="What is the state?",
                agent_state=AgentState.COLLECTING_INFO,
                invoice=build_customer_preview(customer_state),
                next_expected_input="Provide state name.",
            )

        state["awaiting"] = "confirm"
        return AgentResponse(
            message="All details collected. Confirm to create customer.",
            agent_state=AgentState.AWAITING_CONFIRMATION,
            invoice=build_customer_preview(customer_state, ready=True),
            next_expected_input="Reply 'confirm' to create or 'cancel' to abort.",
        )

    # ------------------------------------------------------------------
    # Step 2: GSTIN collection (optional)
    # ------------------------------------------------------------------
    if awaiting == "gstin":
        if text.lower() in {"skip", "no", "none", "na", "n/a"}:
            customer_state["gstin"] = None
        else:
            gstin = _extract_gstin(text)
            if not gstin:
                return AgentResponse(
                    message="Could not read GSTIN. Provide a valid GSTIN or reply 'skip'.",
                    agent_state=AgentState.COLLECTING_INFO,
                    invoice=build_customer_preview(customer_state),
                    next_expected_input="Provide GSTIN like '29ABCDE1234F1Z5' or reply 'skip'.",
                )
            customer_state["gstin"] = gstin

        if not customer_state.get("phone"):
            state["awaiting"] = "phone"
            return AgentResponse(
                message="What is the phone number?",
                agent_state=AgentState.COLLECTING_INFO,
                invoice=build_customer_preview(customer_state),
                next_expected_input="Provide a 10-digit phone number.",
            )

        if not customer_state.get("email"):
            state["awaiting"] = "email"
            return AgentResponse(
                message="What is the email address?",
                agent_state=AgentState.COLLECTING_INFO,
                invoice=build_customer_preview(customer_state),
                next_expected_input="Provide email or reply 'skip'.",
            )

        if not customer_state.get("city"):
            state["awaiting"] = "city"
            return AgentResponse(
                message="What is the city?",
                agent_state=AgentState.COLLECTING_INFO,
                invoice=build_customer_preview(customer_state),
                next_expected_input="Provide city name.",
            )

        if not customer_state.get("state"):
            state["awaiting"] = "state"
            return AgentResponse(
                message="What is the state?",
                agent_state=AgentState.COLLECTING_INFO,
                invoice=build_customer_preview(customer_state),
                next_expected_input="Provide state name.",
            )

        state["awaiting"] = "confirm"
        return AgentResponse(
            message="All details collected. Confirm to create customer.",
            agent_state=AgentState.AWAITING_CONFIRMATION,
            invoice=build_customer_preview(customer_state, ready=True),
            next_expected_input="Reply 'confirm' to create or 'cancel' to abort.",
        )

    # ------------------------------------------------------------------
    # Step 3: Phone collection (required)
    # ------------------------------------------------------------------
    if awaiting == "phone":
        phone = _extract_phone(text)
        if not phone:
            return AgentResponse(
                message="Could not read phone number. Provide a valid 10-digit number.",
                agent_state=AgentState.COLLECTING_INFO,
                invoice=build_customer_preview(customer_state),
                next_expected_input="Provide a 10-digit phone number.",
            )
        customer_state["phone"] = phone

        inline_email = _extract_email(text)
        if inline_email:
            customer_state["email"] = inline_email
            state["awaiting"] = "city"
            return AgentResponse(
                message="What is the city?",
                agent_state=AgentState.COLLECTING_INFO,
                invoice=build_customer_preview(customer_state),
                next_expected_input="Provide city name.",
            )

        if not customer_state.get("email"):
            state["awaiting"] = "email"
            return AgentResponse(
                message="What is the email address?",
                agent_state=AgentState.COLLECTING_INFO,
                invoice=build_customer_preview(customer_state),
                next_expected_input="Provide email or reply 'skip'.",
            )

        if not customer_state.get("city"):
            state["awaiting"] = "city"
            return AgentResponse(
                message="What is the city?",
                agent_state=AgentState.COLLECTING_INFO,
                invoice=build_customer_preview(customer_state),
                next_expected_input="Provide city name.",
            )

        if not customer_state.get("state"):
            state["awaiting"] = "state"
            return AgentResponse(
                message="What is the state?",
                agent_state=AgentState.COLLECTING_INFO,
                invoice=build_customer_preview(customer_state),
                next_expected_input="Provide state name.",
            )

        state["awaiting"] = "confirm"
        return AgentResponse(
            message="All details collected. Confirm to create customer.",
            agent_state=AgentState.AWAITING_CONFIRMATION,
            invoice=build_customer_preview(customer_state, ready=True),
            next_expected_input="Reply 'confirm' to create or 'cancel' to abort.",
        )

    # ------------------------------------------------------------------
    # Step 4: Email collection (optional)
    # ------------------------------------------------------------------
    if awaiting == "email":
        if text.lower() in {"skip", "no", "none", "na", "n/a"}:
            customer_state["email"] = None
        else:
            email = _extract_email(text)
            if not email:
                return AgentResponse(
                    message="Could not read email. Provide a valid email or reply 'skip'.",
                    agent_state=AgentState.COLLECTING_INFO,
                    invoice=build_customer_preview(customer_state),
                    next_expected_input="Provide a valid email or reply 'skip'.",
                )
            customer_state["email"] = email

        # Move to city collection after email
        state["awaiting"] = "city"
        return AgentResponse(
            message="What is the city?",
            agent_state=AgentState.COLLECTING_INFO,
            invoice=build_customer_preview(customer_state),
            next_expected_input="Provide city name.",
        )

    # ------------------------------------------------------------------
    # Step 5: City collection (free text)
    # ------------------------------------------------------------------
    if awaiting == "city":
        extracted = _extract_inline_fields(text)
        city = extracted.get("city") or text.strip()

        # Guard against storing full command/message into city.
        if _looks_like_full_customer_command(text) and not extracted.get("city"):
            return AgentResponse(
                message="Please provide only city name (e.g., Bangalore) or 'city Bangalore'.",
                agent_state=AgentState.COLLECTING_INFO,
                invoice=build_customer_preview(customer_state),
                next_expected_input="Provide city name only.",
            )

        if not city:
            return AgentResponse(
                message="City cannot be empty. Please provide a city name.",
                agent_state=AgentState.COLLECTING_INFO,
                invoice=build_customer_preview(customer_state),
                next_expected_input="Provide city name.",
            )

        customer_state["city"] = " ".join(city.split()).title()

        # If state was included in the same input, capture it and move to confirmation.
        if extracted.get("state"):
            customer_state["state"] = " ".join(extracted["state"].split()).title()
            state["awaiting"] = "confirm"
            return AgentResponse(
                message="All details collected. Confirm to create customer.",
                agent_state=AgentState.AWAITING_CONFIRMATION,
                invoice=build_customer_preview(customer_state, ready=True),
                next_expected_input="Reply 'confirm' to create or 'cancel' to abort.",
            )

        state["awaiting"] = "state"
        return AgentResponse(
            message="What is the state?",
            agent_state=AgentState.COLLECTING_INFO,
            invoice=build_customer_preview(customer_state),
            next_expected_input="Provide state name.",
        )

    # ------------------------------------------------------------------
    # Step 6: State collection (free text)
    # ------------------------------------------------------------------
    if awaiting == "state":
        extracted = _extract_inline_fields(text)
        state_value = extracted.get("state") or text.strip()

        if _looks_like_full_customer_command(text) and not extracted.get("state"):
            return AgentResponse(
                message="Please provide only state name (e.g., Karnataka) or 'state Karnataka'.",
                agent_state=AgentState.COLLECTING_INFO,
                invoice=build_customer_preview(customer_state),
                next_expected_input="Provide state name only.",
            )

        if not state_value:
            return AgentResponse(
                message="State cannot be empty. Please provide a state name.",
                agent_state=AgentState.COLLECTING_INFO,
                invoice=build_customer_preview(customer_state),
                next_expected_input="Provide state name.",
            )
        customer_state["state"] = " ".join(state_value.split()).title()

        # All details collected → move to confirmation
        state["awaiting"] = "confirm"
        return AgentResponse(
            message="All details collected. Confirm to create customer.",
            agent_state=AgentState.AWAITING_CONFIRMATION,
            invoice=build_customer_preview(customer_state, ready=True),
            next_expected_input="Reply 'confirm' to create or 'cancel' to abort.",
        )

    # ------------------------------------------------------------------
    # Step 7: Confirmation — DB write happens here
    # ------------------------------------------------------------------
    if awaiting == "confirm":
        if text.lower() in {"confirm", "yes", "create", "ok", "proceed"}:
            return _save_customer(session_id=session_id, customer_state=customer_state, db=db)

        if text.lower() in {"no", "cancel", "abort"}:
            _clear_state(session_id)
            return AgentResponse(
                message="Customer creation cancelled.",
                agent_state=AgentState.COLLECTING_INFO,
                next_expected_input="Use 'create customer <name>' to start again.",
            )

        return AgentResponse(
            message="Please reply 'confirm' to create or 'cancel' to abort.",
            agent_state=AgentState.AWAITING_CONFIRMATION,
            invoice=build_customer_preview(customer_state, ready=True),
            next_expected_input="Reply 'confirm' to create or 'cancel' to abort.",
        )

    # Safety fallback
    _clear_state(session_id)
    return AgentResponse(
        message="Customer flow was reset. Please start again.",
        agent_state=AgentState.COLLECTING_INFO,
        next_expected_input="Use 'create customer <name>' to start.",
    )

