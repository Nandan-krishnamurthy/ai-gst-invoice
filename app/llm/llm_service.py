import os
import json
from google import genai
from dotenv import load_dotenv
from google.genai import types

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)


SYSTEM_PROMPT = """
You are an invoice data extraction assistant.

Extract structured invoice data from the provided input.
The input may be:
- User text
- Chat transcript
- Screenshot of a conversation
- Image containing order details

Return ONLY valid JSON. No explanations.

Schema:
{
  "buyer": {
    "name": string or null,
    "gstin": string or null,
    "address": string or null,
    "state": string or null
  },
  "items": [
    {
      "description": string,
      "quantity": number,
      "unit_price": number or null,
      "gst_rate": number or null,
      "hsn_code": string or null
    }
  ]
}
"""


def clean_llm_output(raw_output: str) -> str:
    """
    Removes markdown code blocks if present.
    """
    raw_output = raw_output.strip()

    if raw_output.startswith("```"):
        parts = raw_output.split("```")
        if len(parts) >= 2:
            raw_output = parts[1]
        raw_output = raw_output.replace("json", "", 1).strip()

    return raw_output


def extract_invoice_data(text: str) -> dict:
    """
    Sends text to Gemini and returns structured invoice JSON.
    """

    prompt = SYSTEM_PROMPT + f"\n\nUser text:\n{text}"

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    raw_output = clean_llm_output(response.text)

    try:
        data = json.loads(raw_output)
        return data
    except json.JSONDecodeError:
        return {
            "error": "Invalid JSON from LLM",
            "raw_output": raw_output
        }


def extract_invoice_from_image(image_path: str) -> dict:
    """
    Sends image to Gemini and extracts invoice JSON.
    """

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            SYSTEM_PROMPT,
            types.Part.from_bytes(
                data=image_bytes,
                mime_type="image/png"  # change if jpg/jpeg
            ),
        ],
    )

    raw_output = clean_llm_output(response.text)

    try:
        data = json.loads(raw_output)
        return data
    except json.JSONDecodeError:
        return {
            "error": "Invalid JSON from LLM",
            "raw_output": raw_output
        }
