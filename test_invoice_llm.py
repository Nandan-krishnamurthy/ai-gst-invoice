from app.llm.llm_service import extract_invoice_data

text = """
Create invoice for Rahul from Karnataka.
Address: MG Road, Bangalore.
2 laptop at 100000 each with 18% GST.
"""

result = extract_invoice_data(text)
print(result)
