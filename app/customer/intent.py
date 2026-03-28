import re


CUSTOMER_INTENT_PATTERNS = [
	r"^\s*create\s+customer\b",
	r"^\s*add\s+customer\b",
	r"^\s*create\s+customer\s+account\b",
]


def is_customer_intent(message: str) -> bool:
	"""
	Return True when the message is an explicit customer command.
	"""
	if not message:
		return False

	return any(re.search(pattern, message, re.IGNORECASE) for pattern in CUSTOMER_INTENT_PATTERNS)
