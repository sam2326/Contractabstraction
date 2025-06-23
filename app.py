import streamlit as st
import pandas as pd
import re
from pdf2docx import Converter
from docx import Document
import os
import tempfile

st.set_page_config(page_title="PDF to Word Contract Extractor", layout="wide")
st.title("📄 Contract Metadata Extractor (PDF → Word)")

def convert_pdf_to_docx(pdf_file):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
        temp_pdf.write(pdf_file.read())
        temp_pdf_path = temp_pdf.name
    docx_path = temp_pdf_path.replace(".pdf", ".docx")
    cv = Converter(temp_pdf_path)
    cv.convert(docx_path, start=0, end=None)
    cv.close()
    return docx_path

def extract_text_from_docx(docx_path):
    doc = Document(docx_path)
    text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    return text

def detect_document_type(text):
    t = text.lower()
    keywords = {
        "NDA": ["non-disclosure", "confidentiality"],
        "MSA": ["master services agreement"],
        "SOW": ["statement of work"],
        "DPA": ["data processing agreement"],
        "EULA": ["end user license"],
        "Order Form": ["order form"],
        "Quote": ["quote", "quotation"],
        "Amendment": ["amendment", "addendum"],
        "Lease": ["lease agreement"],
        "Maintenance Agreement": ["maintenance agreement"]
    }
    for doc_type, keys in keywords.items():
        if any(k in t for k in keys):
            return doc_type
    return "Unknown"

def extract_effective_date(text):
    match = re.search(r"effective\s+(?:date|as of)\s*[:\-]?\s*(\w+ \d{1,2}, \d{4})", text, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"dated\s+(\w+ \d{1,2}, \d{4})", text, re.IGNORECASE)
    if match:
        return match.group(1)
    return ""

def extract_expiry_date(text, effective):
    match = re.search(r"(term|remain in effect).*?(one|two|three|1|2|3).*?(year|years)", text, re.IGNORECASE)
    if match and effective:
        years_map = {"one": 1, "two": 2, "three": 3, "1": 1, "2": 2, "3": 3}
        years = years_map.get(match.group(2).lower(), 0)
        try:
            from datetime import datetime, timedelta
            dt = datetime.strptime(effective, "%B %d, %Y")
            return (dt + timedelta(days=365 * years)).strftime("%B %d, %Y")
        except:
            return ""
    return ""

def extract_entities(text):
    match = re.search(r"between\s+(.*?)\s+and\s+(.*?)[\.,\n]", text, re.IGNORECASE)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return "", ""

def extract_governing_law(text):
    match = re.search(r"governed by the laws of\s+(?:the\s+)?(?:state|province)?\s*of\s*([A-Za-z\s]+)[\.,\n]", text, re.IGNORECASE)
    return match.group(1).strip() if match else ""

def extract_payment_terms(text):
    match = re.search(r"net\s+(30|45|60|90)", text, re.IGNORECASE)
    return match.group(1) + " days" if match else "Not specified"

def detect_missing_exhibits(text):
    if "exhibit" in text.lower() or "schedule" in text.lower():
        if not any(x in text.lower() for x in ["attached", "included", "annexed"]):
            return "Yes"
    return "No"

def extract_fields_from_text(text):
    effective = extract_effective_date(text)
    expiry = extract_expiry_date(text, effective)
    customer, supplier = extract_entities(text)
    return {
        "Document Type": detect_document_type(text),
        "Term Type": "Perpetual" if "perpetual" in text.lower() else "Fixed",
        "Effective Date": effective,
        "Expiry Date": expiry,
        "Customer Legal Entity": customer,
        "Supplier Legal Entity": supplier,
        "Governing Law": extract_governing_law(text),
        "Payment Term": extract_payment_terms(text),
        "Is Document Complete?": "Yes",
        "Missing Exhibits/Schedules?": detect_missing_exhibits(text),
        "Comments": ""
    }

uploaded_files = st.file_uploader("Upload contract PDFs", type="pdf", accept_multiple_files=True)

if uploaded_files:
    results = []
    for uploaded_file in uploaded_files:
        with st.spinner(f"Processing {uploaded_file.name}..."):
            docx_path = convert_pdf_to_docx(uploaded_file)
            text = extract_text_from_docx(docx_path)
            fields = extract_fields_from_text(text)
            fields["File Name"] = uploaded_file.name
            results.append(fields)
            os.remove(docx_path)

    df = pd.DataFrame(results)[["File Name", "Document Type", "Term Type", "Effective Date", "Expiry Date",
                                "Customer Legal Entity", "Supplier Legal Entity", "Governing Law", "Payment Term",
                                "Is Document Complete?", "Missing Exhibits/Schedules?", "Comments"]]

    st.success("✅ Extraction complete.")
    st.dataframe(df, use_container_width=True)

    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download CSV", csv, "contract_metadata.csv", "text/csv")
