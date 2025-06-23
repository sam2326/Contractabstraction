import streamlit as st
import pandas as pd
import re
from pdf2docx import Converter
from docx import Document
import os
import tempfile
from datetime import datetime, timedelta

st.set_page_config(page_title="PDF Contract Extractor", layout="wide")
st.title("📄 Contract Metadata Extractor (PDF → Word)")

# --- Conversion ---
def convert_pdf_to_docx(pdf_file):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
        temp_pdf.write(pdf_file.read())
        pdf_path = temp_pdf.name
    docx_path = pdf_path.replace(".pdf", ".docx")
    Converter(pdf_path).convert(docx_path, start=0, end=None)
    return docx_path

def extract_text_from_docx(docx_path):
    doc = Document(docx_path)
    return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])

# --- Extraction Functions ---
def detect_document_type(text):
    types = {
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
    text_lower = text.lower()
    for t, keywords in types.items():
        if any(k in text_lower for k in keywords):
            return t
    return "Unknown"

def extract_effective_date(text):
    pattern = r"(made and entered into|effective(?: as of)?|dated)[^\n]{0,100}?(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        date_match = re.search(r"(January|February|...|December)\s+\d{1,2},\s+\d{4}", match.group(), re.IGNORECASE)
        return date_match.group(0) if date_match else ""
    return ""

def extract_expiry_date(text, effective):
    match = re.search(r"(remain in effect|term|continue).*?(one|two|three|1|2|3).*?(year|years)", text, re.IGNORECASE)
    if match and effective:
        years_map = {"one": 1, "two": 2, "three": 3, "1": 1, "2": 2, "3": 3}
        val = match.group(2).lower().strip()
        try:
            dt = datetime.strptime(effective, "%B %d, %Y")
            return (dt + timedelta(days=365 * years_map[val])).strftime("%B %d, %Y")
        except:
            return ""
    return ""

def extract_entities(text):
    match = re.search(r"between\s+(.*?)\s+and\s+(.*?)[\.,\n]", text, re.IGNORECASE)
    if match:
        entities = [match.group(1).strip(), match.group(2).strip()]
        customer = next((e for e in entities if "circle k" in e.lower() or "couche-tard" in e.lower()), "")
        supplier = next((e for e in entities if e != customer), "")
        return customer, supplier
    return "", ""

def extract_governing_law(text):
    match = re.search(r"governed by the laws of\s+(?:the\s+)?(?:state|province)?\s*of\s*([A-Za-z\s]+)[\.,\n]", text, re.IGNORECASE)
    return match.group(1).strip() if match else ""

def extract_payment_term(text):
    match = re.search(r"net\s+(30|45|60|90)", text, re.IGNORECASE)
    return f"{match.group(1)} days" if match else "Not specified"

def detect_missing_exhibits(text):
    text_l = text.lower()
    if "exhibit" in text_l or "schedule" in text_l:
        if not any(x in text_l for x in ["attached", "included", "annexed"]):
            return "Yes"
    return "No"

# --- Field Aggregator ---
def extract_fields(text):
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
        "Payment Term": extract_payment_term(text),
        "Is Document Complete?": "Yes",
        "Missing Exhibits/Schedules?": detect_missing_exhibits(text),
        "Comments": ""
    }

# --- Streamlit UI ---
uploaded_files = st.file_uploader("Upload PDF contracts", type="pdf", accept_multiple_files=True)

if uploaded_files:
    rows = []
    for file in uploaded_files:
        with st.spinner(f"Processing {file.name}..."):
            docx_path = convert_pdf_to_docx(file)
            text = extract_text_from_docx(docx_path)
            fields = extract_fields(text)
            fields["File Name"] = file.name
            rows.append(fields)
            os.remove(docx_path)

    df = pd.DataFrame(rows)[["File Name", "Document Type", "Term Type", "Effective Date", "Expiry Date",
                             "Customer Legal Entity", "Supplier Legal Entity", "Governing Law", "Payment Term",
                             "Is Document Complete?", "Missing Exhibits/Schedules?", "Comments"]]

    st.success("✅ Extraction complete.")
    st.dataframe(df, use_container_width=True)
    st.download_button("📥 Download CSV", df.to_csv(index=False).encode("utf-8"), "contract_metadata.csv", "text/csv")
