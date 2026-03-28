from typing import Literal, Optional

from pydantic import BaseModel, field_validator, model_validator


class CustomerCreateInput(BaseModel):
	name: str
	gstin: Optional[str] = None
	city: Optional[str] = None
	state: Optional[str] = None

	@field_validator("name")
	@classmethod
	def validate_name(cls, value: str) -> str:
		normalized = value.strip()
		if not normalized:
			raise ValueError("name is required")
		return normalized

	@field_validator("gstin", "city", "state", mode="before")
	@classmethod
	def normalize_optional_text(cls, value):
		if value is None:
			return None
		if isinstance(value, str):
			normalized = value.strip()
			return normalized or None
		return value


class CustomerResponse(BaseModel):
	id: int
	name: str
	gstin: Optional[str] = None
	city: Optional[str] = None
	state: Optional[str] = None
	customer_type: Literal["B2B", "B2C"] = "B2C"

	@field_validator("name")
	@classmethod
	def validate_name(cls, value: str) -> str:
		normalized = value.strip()
		if not normalized:
			raise ValueError("name is required")
		return normalized

	@field_validator("gstin", "city", "state", mode="before")
	@classmethod
	def normalize_optional_text(cls, value):
		if value is None:
			return None
		if isinstance(value, str):
			normalized = value.strip()
			return normalized or None
		return value

	@model_validator(mode="after")
	def derive_customer_type(self):
		self.customer_type = "B2B" if self.gstin else "B2C"
		return self
