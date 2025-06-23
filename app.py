import streamlit as st
import pytesseract
from pdf2image import convert_from_bytes
import pdfplumber
import pandas as pd
import re
import tempfile
import os

st.title("Contract Metadata Extractor")
uploaded_files = st.file_uploader("Upload PDF files", type="pdf", accept_multiple_files=True)

def extract_text_from_pdf(file):
    try:
        with pdfplumber.open(file) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            return text.strip()
    except:
        return ""

def extract_text_from_scanned_pdf(file):
    images = convert_from_bytes(file.read())
    text = ""
    for img in images:
        text += pytesseract.image_to_string(img)
    return text.strip()

def extract_field(text, label):
    match = re.search(rf"{label}[:\s\-–]*([\w\s,\.\/-]+)", text, re.IGNORECASE)
    return match.group(1).strip() if match else "Not found"

def get_document_type(text):
    types = {
        "nda": "NDA", "non-disclosure": "NDA",
        "master service": "MSA",
        "statement of work": "SOW",
        "order form": "Order Form",
        "change order": "Change Order",
        "data processing": "DPA",
        "amendment": "Amendment",
        "addendum": "Amendment",
        "quote": "Quote",
        "invoice": "Invoice"
    }
    for key, val in types.items():
        if key in text.lower():
            return val
    return "Other"

def get_term_type(text):
    if "perpetual" in text.lower():
        return "Perpetual"
    elif "effective date" in text.lower() or "term of" in text.lower():
        return "Fixed"
    return "Unknown"

def get_completeness(text):
    return "Yes" if len(text) > 500 else "Possibly Incomplete"

results = []

if uploaded_files:
    for file in uploaded_files:
        st.write(f"Processing: {file.name}")
        text = extract_text_from_pdf(file)
        if not text or len(text.strip()) < 50:
            text = extract_text_from_scanned_pdf(file)

        metadata = {
            "Document Name": file.name,
            "Document Type": get_document_type(text),
            "Term Type": get_term_type(text),
            "Effective Date": extract_field(text, "Effective Date"),
            "Expiry Date": extract_field(text, "Expiry Date"),
            "Customer Legal Entity": extract_field(text, "Circle K"),
            "Supplier Legal Entity": extract_field(text, "Inc|LLC|Ltd|GmbH"),
            "Governing Law": extract_field(text, "Governing Law"),
            "Payment Terms": extract_field(text, "Payment Terms"),
            "Is Document Complete?": get_completeness(text),
            "Missing Exhibits or Schedules": "Check manually"
        }
        results.append(metadata)

    df = pd.DataFrame(results)
    st.dataframe(df)

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", csv, "contract_metadata.csv", "text/csv")
