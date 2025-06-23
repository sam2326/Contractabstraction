import streamlit as st
import fitz  # PyMuPDF
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="Contract Metadata Extractor", layout="wide")
st.title("📄 Contract Metadata Extractor (PDF)")

# --- Helper functions ---
def extract_text_from_pdf(uploaded_file):
    text = ""
    with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
        for page in doc:
            text += page.get_text()
    return text

def extract_field_patterns(text):
    fields = {
        "Document Type": detect_document_type(text),
        "Term Type": detect_term_type(text),
        "Effective Date": extract_effective_date(text),
        "Expiry Date": extract_expiry_date(text),
        "Customer Legal Entity": extract_entity(text, ["Circle K", "Couche-Tard", "Mac's Convenience Stores"]),
        "Supplier Legal Entity": extract_entity(text, ["WorkJam", "Zycus", "Zillion", "Worldline", "PDI", "Zoom", "Zayo"]),
        "Governing Law": extract_governing_law(text),
        "Payment Term": extract_payment_terms(text),
        "Is Document Complete?": "Yes",
        "Missing Exhibits/Schedules?": detect_missing_exhibits(text),
        "Comments": ""
    }
    return fields

# --- Extraction logic ---
def detect_document_type(text):
    t = text.lower()
    if "non-disclosure" in t or "nda" in t: return "NDA"
    if "master services agreement" in t or "msa" in t: return "MSA"
    if "statement of work" in t or "sow" in t: return "SOW"
    if "data processing agreement" in t or "dpa" in t: return "DPA"
    if "end user license" in t or "eula" in t: return "EULA"
    if "order form" in t: return "Order Form"
    if "quote" in t or "quotation" in t: return "Quote"
    if "amendment" in t or "addendum" in t: return "Amendment"
    if "lease agreement" in t: return "Lease"
    if "maintenance agreement" in t: return "Maintenance Agreement"
    return "Unknown"

def detect_term_type(text):
    t = text.lower()
    if "perpetual" in t: return "Perpetual"
    if "term of" in t or "expires" in t or "shall continue" in t or "remain in effect for" in t or "terminate on" in t:
        return "Fixed"
    return ""

def extract_effective_date(text):
    match = re.search(r"(?i)(effective|start date|commence[s]?)\s*(as of)?\s*[:,]?\s*(\w+\s+\d{1,2},\s+\d{4})", text)
    return match.group(3) if match else ""

def extract_expiry_date(text):
    match = re.search(r"(?i)(expire[s]?|end date|terminate[s]?)\s*(on|until)?\s*[:,]?\s*(\w+\s+\d{1,2},\s+\d{4})", text)
    return match.group(3) if match else ""

def extract_entity(text, known_entities):
    for entity in known_entities:
        if re.search(re.escape(entity), text, re.IGNORECASE):
            return entity
    return ""

def extract_governing_law(text):
    match = re.search(r"(?i)governed by.*?(state|province)?\s*of\s*([\w, ]+)", text)
    return match.group(2).strip() if match else ""

def extract_payment_terms(text):
    match = re.search(r"(?i)net\s+(30|45|60|90)", text)
    return match.group(1) if match else "Not specified"

def detect_missing_exhibits(text):
    if re.search(r"(?i)exhibit|schedule|order form", text) and not re.search(r"(?i)attached|included", text):
        return "Yes"
    return "No"

# --- UI ---
uploaded_files = st.file_uploader("Upload contract PDFs", type="pdf", accept_multiple_files=True)

if uploaded_files:
    results = []
    for uploaded_file in uploaded_files:
        with st.spinner(f"Processing {uploaded_file.name}..."):
            text = extract_text_from_pdf(uploaded_file)
            data = extract_field_patterns(text)
            data["File Name"] = uploaded_file.name
            results.append(data)

    df = pd.DataFrame(results)[["File Name", "Document Type", "Term Type", "Effective Date", "Expiry Date",
                                "Customer Legal Entity", "Supplier Legal Entity", "Governing Law", "Payment Term",
                                "Is Document Complete?", "Missing Exhibits/Schedules?", "Comments"]]

    st.success("Extraction completed!")
    st.dataframe(df, use_container_width=True)

    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("Download as CSV", data=csv, file_name="contract_metadata.csv", mime="text/csv")
