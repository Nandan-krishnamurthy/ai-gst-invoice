import json
import re
from typing import Any, Dict, Optional


def call_llm(prompt: str) -> str:
    """Temporary mock LLM that returns strict JSON extracted from the prompt input."""
    text = prompt.split("Input:\n", 1)[-1].strip()

    name = None
    phone = None
    email = None
    address = None

    name_match = re.search(
        r"\bcustomer\s+([A-Za-z][A-Za-z\s.'-]*?)(?=\s+(?:from|phone|email|gstin|at|in|,|his\b|her\b)\b|,|$)",
        text,
        re.IGNORECASE,
    )
    if name_match:
        name = name_match.group(1).strip()

    phone_match = re.search(r"(?:phone(?:\s+number)?(?:\s+is)?|mobile(?:\s+number)?(?:\s+is)?)[^\d]*([6-9]\d{9})\b", text, re.IGNORECASE)
    if phone_match:
        phone = phone_match.group(1)

    email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text, re.IGNORECASE)
    if email_match:
        email = email_match.group(0).lower()

    address_match = re.search(
        r"\bfrom\s+([A-Za-z][A-Za-z\s.'-]*?)(?=\s*,?\s*(?:his\b|her\b|phone|email|gstin)\b|,|$)",
        text,
        re.IGNORECASE,
    )
    if address_match:
        address = address_match.group(1).strip()

    return json.dumps(
        {
            "name": name,
            "phone": phone,
            "email": email,
            "address": address,
        }
    )


def _normalize_phone(value: Any) -> Optional[str]:
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value))
    return digits or None


def _clean(value: Any) -> Optional[str]:
    if value in ("", None):
        return None
    return str(value).strip()


def extract_customer_llm(text: str) -> Dict[str, Any]:
    """
    Extract customer fields from natural language using an LLM.
    """

    prompt = (
        "You are a data extraction system.\n"
        "Return ONLY valid JSON. Do not include any text before or after.\n"
        "Schema:\n"
        '{"name": string|null, "phone": string|null, "email": string|null, "address": string|null}\n'
        "Rules:\n"
        "- Do not guess missing values\n"
        "- Use null if missing\n"
        "- Phone must contain digits only\n"
        f"Input:\n{text}"
    )

    try:
        raw = call_llm(prompt)
        parsed = json.loads(raw.strip())

        if not isinstance(parsed, dict):
            return {}

    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    except Exception:
        return {}

    email = _clean(parsed.get("email"))
    email = email.lower() if email else None

    result: Dict[str, Any] = {
        "name": _clean(parsed.get("name")),
        "phone": _normalize_phone(parsed.get("phone")),
        "email": email,
        "address": _clean(parsed.get("address")),
    }

    return result