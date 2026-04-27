import re
from typing import Any, Dict, List


def _normalize_ocr_text(text: str) -> str:
    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    raw = re.sub(r"[^\w\s%.,:/@+&\-]", " ", raw)
    raw = re.sub(r"[ \t]+", " ", raw)
    lines = [re.sub(r"\s+", " ", line).strip() for line in raw.split("\n")]
    return "\n".join(line for line in lines if line)


def _parse_number_token(token: str) -> float:
    cleaned = (token or "").strip().lower().replace(",", "").replace(" ", "")
    if not cleaned:
        return 0.0

    multiplier = 1.0
    if cleaned.endswith("k"):
        multiplier = 1000.0
        cleaned = cleaned[:-1]

    value = float(cleaned)
    return value * multiplier


def _coerce_number(value: float) -> Any:
    return int(value) if float(value).is_integer() else value


def extract_name_and_gstin(text: str) -> tuple[str, str | None]:
    cleaned_text = " ".join((text or "").replace("\n", " ").split())
    gstin_match = re.search(r"\b([0-9A-Za-z]{15})\b", cleaned_text)
    gstin = gstin_match.group(1) if gstin_match else None

    name = cleaned_text
    if gstin:
        name = re.sub(
            rf"(?i)\b(?:gstin|gst)\b\s*[:\-]?\s*{re.escape(gstin)}\b",
            " ",
            name,
        )
        name = re.sub(rf"(?i)\b{re.escape(gstin)}\b", " ", name)

    name = re.sub(r"(?i)^\s*(?:create|make)\s+invoice\s+for\s+", "", name)
    name = re.sub(r"(?i)\b(?:gstin|gst)\b\s*[:\-]?", " ", name)
    name = re.sub(r"\s*,\s*", " ", name)
    name = re.sub(r"\s+", " ", name).strip(" ,")
    return name, gstin


def _extract_customer_details(normalized_text: str) -> tuple[str | None, str | None]:
    candidate_patterns = [
        r"\b(?:name|customer|buyer)\s*[:\-]?\s*([A-Za-z][A-Za-z0-9 &'.,()\-]{1,80}?)(?=\s+(?:phone|mobile|price|rate|amount|item|qty|quantity)\b|$)",
        r"\bcreate\s+invoice\s+for\s+([A-Za-z][A-Za-z0-9 &'.,()\-]{1,80}?)(?=\s+(?:\d+\.?\d*\s+[A-Za-z]|hsn\b|buyer\s+address\b|phone\b|mobile\b|price\b|rate\b|amount\b|qty\b|quantity\b|$))",
    ]

    for pattern in candidate_patterns:
        name_match = re.search(pattern, normalized_text, re.IGNORECASE)
        if not name_match:
            continue

        name, gstin = extract_name_and_gstin(name_match.group(1))
        if name:
            return name, gstin

    return None, None


def _extract_items(lines: List[str]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    consumed_lines = set()

    same_line_pattern = re.compile(
        r"\b(\d+(?:\.\d+)?)\s+([A-Za-z][A-Za-z0-9\s\-/&]{1,50}?)\s+(?:at|@|for)\s*(?:rs\.?\s*|inr\s*)?([0-9][0-9,]*(?:\.\d+)?\s*[kK]?)\b",
        re.IGNORECASE,
    )

    qty_item_pattern = re.compile(
        r"\b(?:need|add|want|require|order)?\s*(\d+(?:\.\d+)?)\s*(?:x|nos?|pcs?|pieces?)?\s+([A-Za-z][A-Za-z0-9\s\-/&]{1,50})\b",
        re.IGNORECASE,
    )

    price_line_pattern = re.compile(
        r"\b(?:price|rate|amount|mrp|unit\s*price)\s*[:\-]?\s*(?:rs\.?\s*|inr\s*)?([0-9][0-9,]*(?:\.\d+)?\s*[kK]?)\b",
        re.IGNORECASE,
    )

    each_price_pattern = re.compile(
        r"\b(?:rs\.?\s*|inr\s*)?([0-9][0-9,]*(?:\.\d+)?\s*[kK]?)\s*(?:each|per\s+piece|per\s+unit)?\b",
        re.IGNORECASE,
    )

    for idx, line in enumerate(lines):
        match = same_line_pattern.search(line)
        if not match:
            continue

        quantity = _parse_number_token(match.group(1))
        price = _parse_number_token(match.group(3))
        items.append(
            {
                "name": " ".join(match.group(2).split()),
                "quantity": _coerce_number(quantity),
                "price": _coerce_number(price),
            }
        )
        consumed_lines.add(idx)

    for idx, line in enumerate(lines):
        if idx in consumed_lines:
            continue
        if re.search(r"\b(price|rate|amount|mrp|unit\s*price)\b", line, re.IGNORECASE):
            continue

        qty_item_match = qty_item_pattern.search(line)
        if not qty_item_match:
            continue

        quantity = _parse_number_token(qty_item_match.group(1))
        item_name = " ".join(qty_item_match.group(2).split())
        price = None

        for offset in (0, 1, 2):
            probe_idx = idx + offset
            if probe_idx >= len(lines):
                break
            probe_line = lines[probe_idx]

            price_match = price_line_pattern.search(probe_line)
            if price_match:
                price = _parse_number_token(price_match.group(1))
                break

            each_match = each_price_pattern.search(probe_line)
            if each_match and re.search(r"\b(each|per|price|rate|amount|rs|inr)\b", probe_line, re.IGNORECASE):
                price = _parse_number_token(each_match.group(1))
                break

        if price is None:
            continue

        items.append(
            {
                "name": item_name,
                "quantity": _coerce_number(quantity),
                "price": _coerce_number(price),
            }
        )
        consumed_lines.add(idx)

    deduped: List[Dict[str, Any]] = []
    seen = set()
    for item in items:
        key = (item["name"].lower(), item["quantity"], item["price"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    return deduped


def parse_conversation(text: str) -> Dict[str, Any]:
    normalized_multiline = _normalize_ocr_text(text)
    lines = normalized_multiline.split("\n") if normalized_multiline else []
    normalized = " ".join(lines)

    phone_match = re.search(r"(?:\+?91[-\s]?)?([6-9]\d{9})\b", normalized)
    phone = phone_match.group(1) if phone_match else None

    gstin_match = re.search(r"\b([0-9A-Za-z]{15})\b", normalized)
    global_gstin = gstin_match.group(1) if gstin_match else None

    gst_match = re.search(r"\b(\d{1,2})\s*%\s*gst\b|\bgst\s*(?:is|:|at|of)?\s*(\d{1,2})\s*%?\b", normalized, re.IGNORECASE)
    gst = int((gst_match.group(1) or gst_match.group(2))) if gst_match else None

    address_match = re.search(r"(?mi)^\s*address\s*[:\-]?\s*(.+?)\s*$", normalized_multiline)
    customer_address = address_match.group(1).strip() if address_match else None

    items: List[Dict[str, Any]] = _extract_items(lines)
    customer_name, customer_gstin = _extract_customer_details(normalized)
    customer_gstin = global_gstin or customer_gstin

    result: Dict[str, Any] = {
        "customer_name": customer_name,
        "customer_gstin": customer_gstin,
        "customer_address": customer_address,
        "phone": phone,
        "items": items,
        "gst": gst,
    }

    return result