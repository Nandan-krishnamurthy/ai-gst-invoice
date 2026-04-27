from typing import Any, Dict, List

from app.agent.interpreter import intent, matcher, parser


def _compute_confidence(parsed_data: Dict[str, Any], actions: List[str]) -> float:
    score = 0.3
    if parsed_data.get("phone"):
        score += 0.2
    if parsed_data.get("customer_name"):
        score += 0.2
    if parsed_data.get("items"):
        score += 0.2
    if parsed_data.get("gst") is not None:
        score += 0.05
    if "create_invoice" in actions:
        score += 0.05
    return round(min(score, 0.99), 2)


def _calculate_total(items: List[Dict[str, Any]]) -> float:
    total = 0
    for item in items:
        quantity = item.get("quantity", 0)
        price = item.get("price", 0)
        total += quantity * price
    return total


def interpret_conversation(raw_text: str) -> Dict[str, Any]:
    """Preview-only interpreter flow: parse -> match -> detect intent."""

    # 🔍 DEBUG LOGS (temporary)
    print("\n🧾 RAW TEXT:\n", raw_text)

    parsed_data = parser.parse_conversation(raw_text)
    print("📦 PARSED DATA:\n", parsed_data)

    customer_match = matcher.match_customer(parsed_data.get("phone"))
    print("👤 CUSTOMER MATCH:\n", customer_match)

    intent_result = intent.detect_intent(
        parsed_data=parsed_data,
        raw_text=raw_text,
        customer_type=customer_match.get("type", "unknown"),
    )
    print("⚡ INTENT RESULT:\n", intent_result)

    actions = intent_result.get("actions") or ["preview"]

    warnings: List[str] = []
    if not parsed_data.get("items"):
        warnings.append("No invoice items could be extracted.")
    if parsed_data.get("phone") is None:
        warnings.append("Customer phone is missing or invalid.")

    return {
        "message": "This is what I understood from the conversation",
        "customer": {
            "type": customer_match.get("type", "unknown"),
            "name": parsed_data.get("customer_name"),
            "phone": parsed_data.get("phone"),
            "gstin": parsed_data.get("customer_gstin"),
            "address": parsed_data.get("customer_address"),
            "details": customer_match.get("customer"),
        },
        "invoice": {
            "items": parsed_data.get("items", []),
            "gst": parsed_data.get("gst"),
            "total": _calculate_total(parsed_data.get("items", [])),
        },
        "actions": actions,
        "confidence": _compute_confidence(parsed_data, actions),
        "warnings": warnings,
    }