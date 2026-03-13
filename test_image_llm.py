from app.llm.llm_service import extract_invoice_from_image

result = extract_invoice_from_image("chat.png")
print(result)
