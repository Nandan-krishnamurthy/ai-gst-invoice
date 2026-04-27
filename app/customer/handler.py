import re
from typing import Any, Dict, Optional

from sqlalchemy import Column, ForeignKey, Integer, String, func
from sqlalchemy.orm import Session

from app.agent.agent_state import AgentState
from app.agent.schemas import AgentResponse
from app.customer.crud import Customer, create_customer
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
CUSTOMER_OPTIONAL_FIELDS = ("gstin", "phone", "email", "city", "state")
CUSTOMER_SKIP_TOKENS = {"skip", "no", "none", "na", "n/a"}
CUSTOMER_CONFIRM_TOKENS = {"confirm", "yes", "create", "done", "ok", "proceed"}
FIELD_PROMPTS = {
    "gstin": (
        "Do you want to add GSTIN? (optional — reply 'skip' to skip)",
        "Provide GSTIN or reply 'skip'.",
    ),
    "phone": (
        "What is the phone number? (optional — reply 'skip' to skip)",
        "Provide a 10-digit phone number or reply 'skip'.",
    ),
    "email": (
        "What is the email address? (optional — reply 'skip' to skip)",
        "Provide email or reply 'skip'.",
    ),
    "city": (
        "What is the city? (optional — reply 'skip' to skip)",
        "Provide city name or reply 'skip'.",
    ),
    "state": (
        "What is the state? (optional — reply 'skip' to skip)",
        "Provide state name or reply 'skip'.",
    ),
}


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
            "skipped_fields": set(),
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


def normalize_phone_number(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None

    digits = re.sub(r"\D", "", phone)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if len(digits) == 10 and digits[0] in "6789":
        return digits
    return None


def _extract_phone(message: str) -> Optional[str]:
    m = re.search(r"(?:\+?91[-\s]?)?([6-9]\d{9})\b", message)
    return m.group(1) if m else None


def _extract_email(message: str) -> Optional[str]:
    m = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", message)
    return m.group(0).lower() if m else None


def _is_skip_input(text: str) -> bool:
    return text.lower() in CUSTOMER_SKIP_TOKENS


def _get_next_pending_field(state: Dict[str, Any], customer_state: Dict[str, Any]) -> Optional[str]:
    skipped_fields = state.get("skipped_fields", set())
    for field in CUSTOMER_OPTIONAL_FIELDS:
        if customer_state.get(field):
            continue
        if field in skipped_fields:
            continue
        return field
    return None


def _ask_for_field(field: str, customer_state: Dict[str, Any]) -> AgentResponse:
    message, next_expected_input = FIELD_PROMPTS[field]
    return AgentResponse(
        message=message,
        agent_state=AgentState.COLLECTING_INFO,
        invoice=build_customer_preview(customer_state),
        next_expected_input=next_expected_input,
    )


def _advance_customer_flow(state: Dict[str, Any], customer_state: Dict[str, Any]) -> AgentResponse:
    next_field = _get_next_pending_field(state, customer_state)
    if next_field:
        state["awaiting"] = next_field
        return _ask_for_field(next_field, customer_state)

    state["awaiting"] = "confirm"
    return AgentResponse(
        message="All optional details have been reviewed. Confirm to create customer or cancel to abort.",
        agent_state=AgentState.AWAITING_CONFIRMATION,
        invoice=build_customer_preview(customer_state, ready=True),
        next_expected_input="Reply 'confirm' to create or 'cancel' to abort.",
    )


# ---------------------------------------------------------------------------
# DB save: both customers + customer_contacts
# ---------------------------------------------------------------------------

def _save_customer(session_id: str, customer_state: Dict[str, Any], db: Session) -> AgentResponse:
    name = customer_state["name"]
    gstin = customer_state.get("gstin")
    address = customer_state.get("address")
    city = customer_state.get("city")
    state_value = customer_state.get("state")
    phone = customer_state.get("phone")
    email = customer_state.get("email")

    normalized_name = (name or "").strip()
    normalized_phone = normalize_phone_number(phone)
    normalized_email = (email or "").strip().lower() or None

    duplicate_query = (
        db.query(Customer, CustomerContact)
        .join(CustomerContact, Customer.id == CustomerContact.customer_id)
        .filter(func.lower(Customer.name) == normalized_name.lower())
    )

    if normalized_phone is None:
        duplicate_query = duplicate_query.filter(CustomerContact.phone.is_(None))
    else:
        duplicate_query = duplicate_query.filter(CustomerContact.phone == normalized_phone)

    if normalized_email is None:
        duplicate_query = duplicate_query.filter(CustomerContact.email.is_(None))
    else:
        duplicate_query = duplicate_query.filter(func.lower(CustomerContact.email) == normalized_email)

    duplicate_match = duplicate_query.first()
    if duplicate_match:
        existing, existing_contact = duplicate_match
        name_display = " ".join(w.capitalize() for w in existing.name.split())
        existing_customer_data = {
            "id": existing.id,
            "name": name_display,
            "gstin": existing.gstin,
            "address": existing.address,
            "phone": existing_contact.phone,
            "email": existing_contact.email,
            "city": existing.city,
            "state": existing.state,
        }
        _clear_state(session_id)
        return AgentResponse(
            message="Customer already exists",
            agent_state=AgentState.COMPLETED,
            invoice={
                "type": "customer_created",
                "data": existing_customer_data,
                "message": "Customer already exists",
            },
            next_expected_input="",
        )

    created = create_customer(
        db=db,
        customer_state={
            "name": name,
            "gstin": gstin,
            "address": address,
            "city": city,
            "state": state_value,
        },
        auto_commit=False,
    )
    customer_id = created.id

    contact = CustomerContact(
        customer_id=customer_id,
        contact_name=name,
        phone=normalized_phone,
        email=email,
        designation=None,
    )
    db.add(contact)
    # Single transaction for both inserts: customer row and contact row.
    db.commit()

    name_display = " ".join(w.capitalize() for w in name.split())
    customer_data = {
        "id": created.id,
        "name": name_display,
        "gstin": gstin,
        "address": address,
        "phone": normalized_phone,
        "email": email,
        "city": city,
        "state": state_value,
    }
    _clear_state(session_id)
    return AgentResponse(
        message=f"Customer {name_display} created successfully.",
        agent_state=AgentState.COMPLETED,
        invoice={
            "type": "customer_created",
            "data": customer_data,
            "message": "Customer created successfully",
        },
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
    skipped_fields = state.setdefault("skipped_fields", set())

    # ------------------------------------------------------------------
    # Session safety check: detect stale/corrupted state
    # ------------------------------------------------------------------
    if awaiting and not customer_state.get("name"):
        # Session exists but critical field (name) is missing - state is corrupted
        CUSTOMER_STATE.pop(session_id, None)
        return AgentResponse(
            message="Session expired, please start again",
            agent_state=AgentState.COLLECTING_INFO,
            next_expected_input="Use 'create customer <name>' to begin a new session.",
        )

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

        # LLM fallback: only name is required; optional fields are best-effort.
        if not name:
            try:
                llm_raw = extract_customer_llm(text)
                llm_clean = validate_customer_llm(llm_raw)
                name = llm_clean.get("name") or name
                phone = phone or llm_clean.get("phone")
                email = email or llm_clean.get("email")
            except Exception:
                pass

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

        for field in CUSTOMER_OPTIONAL_FIELDS:
            if customer_state.get(field):
                skipped_fields.discard(field)

        return _advance_customer_flow(state, customer_state)

    # ------------------------------------------------------------------
    # Step 2+: Optional field collection in fixed order
    # ------------------------------------------------------------------
    if awaiting in CUSTOMER_OPTIONAL_FIELDS:
        normalized_text = text.lower().strip()
        is_confirm_intent = normalized_text in CUSTOMER_CONFIRM_TOKENS
        is_skip_intent = _is_skip_input(text)
        field_updated = False

        # Always attempt to extract and persist the currently awaited field first.
        # This guarantees backend state has the latest value before confirm/advance.
        if awaiting == "gstin":
            value = _extract_gstin(text)
            if value:
                customer_state["gstin"] = value
                skipped_fields.discard("gstin")
                field_updated = True

        elif awaiting == "phone":
            value = _extract_phone(text)
            if value:
                customer_state["phone"] = value
                skipped_fields.discard("phone")
                field_updated = True

        elif awaiting == "email":
            value = _extract_email(text)
            if value:
                customer_state["email"] = value
                skipped_fields.discard("email")
                field_updated = True

        elif awaiting == "city":
            extracted = _extract_inline_fields(text)
            value = extracted.get("city")
            if not value:
                value = text.strip()

            if value:
                customer_state["city"] = " ".join(value.split()).title()
                skipped_fields.discard("city")
                field_updated = True
            if extracted.get("state") and not customer_state.get("state"):
                customer_state["state"] = " ".join(extracted["state"].split()).title()
                skipped_fields.discard("state")

        elif awaiting == "state":
            extracted = _extract_inline_fields(text)
            value = extracted.get("state")
            if not value:
                value = text.strip()

            if value:
                customer_state["state"] = " ".join(value.split()).title()
                skipped_fields.discard("state")
                field_updated = True

        if is_confirm_intent:
            return _save_customer(session_id=session_id, customer_state=customer_state, db=db)

        if is_skip_intent:
            customer_state[awaiting] = None
            skipped_fields.add(awaiting)
            return _advance_customer_flow(state, customer_state)

        if field_updated:
            return _advance_customer_flow(state, customer_state)

        if awaiting == "gstin":
            return AgentResponse(
                message="Could not read GSTIN. Provide a valid GSTIN or reply 'skip'.",
                agent_state=AgentState.COLLECTING_INFO,
                invoice=build_customer_preview(customer_state),
                next_expected_input="Provide GSTIN like '29ABCDE1234F1Z5' or reply 'skip'.",
            )

        if awaiting == "phone":
            return AgentResponse(
                message="Could not read phone number. Provide a valid 10-digit number or reply 'skip'.",
                agent_state=AgentState.COLLECTING_INFO,
                invoice=build_customer_preview(customer_state),
                next_expected_input="Provide a 10-digit phone number or reply 'skip'.",
            )

        if awaiting == "email":
            return AgentResponse(
                message="Could not read email. Provide a valid email or reply 'skip'.",
                agent_state=AgentState.COLLECTING_INFO,
                invoice=build_customer_preview(customer_state),
                next_expected_input="Provide a valid email or reply 'skip'.",
            )

        if awaiting == "city":
            if _looks_like_full_customer_command(text):
                return AgentResponse(
                    message="Please provide only city name (e.g., Bangalore) or 'city Bangalore', or reply 'skip'.",
                    agent_state=AgentState.COLLECTING_INFO,
                    invoice=build_customer_preview(customer_state),
                    next_expected_input="Provide city name only or reply 'skip'.",
                )
            return AgentResponse(
                message="City cannot be empty. Provide city name or reply 'skip'.",
                agent_state=AgentState.COLLECTING_INFO,
                invoice=build_customer_preview(customer_state),
                next_expected_input="Provide city name or reply 'skip'.",
            )

        return AgentResponse(
            message="State cannot be empty. Provide state name or reply 'skip'.",
            agent_state=AgentState.COLLECTING_INFO,
            invoice=build_customer_preview(customer_state),
            next_expected_input="Provide state name or reply 'skip'.",
        )

    # ------------------------------------------------------------------
    # Confirmation — DB write happens here after all optional fields reviewed
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


