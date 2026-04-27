import re
from typing import Any, Dict, Optional


def _mock_find_customer_by_phone(phone: str) -> Optional[Dict[str, Any]]:
	"""Mock repository lookup; replace with real DB query later."""
	mock_data: Dict[str, Dict[str, Any]] = {
		"9876543210": {"id": 1, "name": "Acme Traders", "phone": "9876543210"},
		"9123456789": {"id": 2, "name": "Nanda Enterprises", "phone": "9123456789"},
	}
	return mock_data.get(phone)


def _normalize_phone(phone: Optional[str]) -> Optional[str]:
	if not phone:
		return None
	digits = re.sub(r"\D", "", phone)
	if len(digits) == 12 and digits.startswith("91"):
		digits = digits[2:]
	if len(digits) == 10 and digits[0] in "6789":
		return digits
	return None


def match_customer(phone: Optional[str]) -> Dict[str, Any]:
	normalized = _normalize_phone(phone)
	if normalized is None:
		return {"type": "unknown"}

	customer = _mock_find_customer_by_phone(normalized)
	if customer:
		return {"type": "existing", "customer": customer}
	return {"type": "new"}
