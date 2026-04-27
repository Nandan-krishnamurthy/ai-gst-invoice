import re
from typing import Any, Dict, List


CONFIRMATION_PATTERN = re.compile(r"\b(ok|okay|done|confirm|confirmed|final|go ahead|proceed)\b", re.IGNORECASE)


def detect_intent(parsed_data: Dict[str, Any], raw_text: str, customer_type: str) -> Dict[str, List[str]]:
	"""Rule-based action suggestion from parsed data and conversation text."""
	actions: List[str] = []
	items = parsed_data.get("items") or []
	phone = parsed_data.get("phone")

	has_confirmation = bool(CONFIRMATION_PATTERN.search(raw_text or ""))
	if items and has_confirmation:
		actions.append("create_invoice")

	if customer_type == "new" and phone:
		actions.append("add_customer")

	if not actions:
		actions.append("preview")

	return {"actions": actions}
