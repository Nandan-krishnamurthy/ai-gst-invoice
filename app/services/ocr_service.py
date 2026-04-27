import base64
import os

import requests


MISTRAL_OCR_URL = "https://api.mistral.ai/v1/ocr"
MISTRAL_OCR_MODEL = "mistral-ocr-latest"


def mistral_ocr(file_bytes: bytes, mime_type: str = "image/png") -> str:
	if not file_bytes:
		raise ValueError("file_bytes cannot be empty")

	api_key = os.getenv("MISTRAL_API_KEY")
	if not api_key:
		raise RuntimeError("MISTRAL_API_KEY is not set")

	encoded_image = base64.b64encode(file_bytes).decode("utf-8")
	data_url = f"data:{mime_type};base64,{encoded_image}"

	response = requests.post(
		MISTRAL_OCR_URL,
		headers={
			"Authorization": f"Bearer {api_key}",
			"Content-Type": "application/json",
		},
		json={
			"model": MISTRAL_OCR_MODEL,
			"document": {
				"type": "image_url",
				"image_url": data_url,
			},
		},
		timeout=60,
	)
	response.raise_for_status()

	payload = response.json()
	pages = payload.get("pages") or []
	text = "\n\n".join(
		str(page.get("markdown") or "").strip()
		for page in pages
		if page.get("markdown")
	).strip()

	if not text:
		raise RuntimeError("Mistral OCR returned empty text")

	return text
