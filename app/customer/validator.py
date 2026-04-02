from typing import Any, Dict


def validate_customer_llm(data: Dict[str, Any]) -> Dict[str, Any]:
	"""
	Clean and validate customer extraction payload from LLM.

	Allowed fields: name, phone, email, address.
	Unknown fields are removed.
	"""
	allowed_fields = ("name", "phone", "email", "address")

	cleaned: Dict[str, Any] = {}
	for field in allowed_fields:
		value = data.get(field)

		if isinstance(value, str):
			value = value.strip()
			if value == "":
				value = None

		if field == "phone" and value is not None:
			value_str = str(value)
			value = value_str if value_str.isdigit() else None

		if field == "email" and value is not None:
			value_str = str(value)
			value = value_str if "@" in value_str else None

		cleaned[field] = value

	return cleaned
