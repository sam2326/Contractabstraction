import streamlit as st
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import pandas as pd
import io
import re
from datetime import datetime, timedelta

st.set_page_config(page_title="Contract Metadata Extractor", layout="wide")
st.title("📄 Contract Metadata Extractor (with OCR)")

# --- Helpers ---
def extract_text_from_pdf(uploaded_file):
    text = ""
    with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
        for page in doc:
            page_text = page.get_text()
            if not page_text.strip():
                pix = page.get_pixmap(dpi=300)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                page_text = pytesseract.image_to_string(img)
            text += page_text + "\n"
    return text

def detect_document_type(text):
    t = text.lower()
    keywords = {
        "NDA": ["non-disclosure", "confidentiality"],
        "MSA": ["master services agreement"],
        "SOW": ["statement of work", "sow effective date"],
        "DPA": ["data processing agreement", "controller", "processor"],
        "EULA": ["end user license", "eula"],
        "Order Form": ["order form"],
        "Quote": ["quotation", "quote", "pricing"],
        "Amendment": ["amendment", "modification"],
        "Lease": ["lease agreement", "rent"],
        "Maintenance Agreement": ["maintenance agreement", "support service"]
    }
    for doc_type, keys in keywords.items():
        if any(k in t for k in keys):
            return doc_type
    return "Unknown"

def detect_term_type(text):
    t = text.lower()
    if "perpetual" in t or "until terminated" in t:
        return "Perpetual"
    if any(x in t for x in ["expires", "valid for", "term of", "terminate", "continue through"]):
        return "Fixed"
    return ""

def extract_date(text, label):
    patterns = [
        rf"(?i){label}.*?(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{{1,2}},\s+\d{{4}}",
        r"(?i)this agreement.*?(is )?(made and )?(entered into )?(as of )?(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}",
        r"(?i)dated\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}"
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            date_match = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}", match.group(), re.IGNORECASE)
            if date_match:
                return date_match.group(0)
    return ""

def extract_relative_expiry(text, eff_date):
    if not eff_date:
        return ""
    match = re.search(r"(?i)(remain in effect|continue|valid).*?(one|two|three|1|2|3)(\s*\(\d\))?\s+(year|years)", text)
    if match:
        word = match.group(2).lower()
        years = {"one": 1, "two": 2, "three": 3, "1": 1, "2": 2, "3": 3}
        try:
            start = datetime.strptime(eff_date, "%B %d, %Y")
            return (start + timedelta(days=365 * years[word])).strftime("%B %d, %Y")
        except Exception:
            return ""
    return ""

def extract_entity(text, entity_list):
    for e in entity_list:
        if re.search(rf"\b{re.escape(e)}\b", text, re.IGNORECASE):
            return e
    return ""

def extract_entities_from_intro(text):
    patterns = [
        r"(?i)(?:by and )?between\s+(.+?)\s+and\s+(.+?)[\.,\n]",
        r"(?i)entered into by\s+(.+?)\s+and\s+(.+?)[\.,\n]",
        r"(?i)this agreement.*?made.*?between\s+(.+?)\s+and\s+(.+?)[\.,\n]"
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip(), match.group(2).strip()
    return "", ""

def extract_governing_law(text):
    match = re.search(r"governed by the laws of\s+(?:the\s+)?(?:state|province)?\s*of\s*([A-Za-z\s]+)", text, re.IGNORECASE)
    return match.group(1).strip() if match else ""

def extract_payment_term(text):
    match = re.search(r"net\s+(30|45|60|90)", text, re.IGNORECASE)
    return match.group(1) if match else "Not specified"

def detect_missing_exhibits(text):
    if re.search(r"(exhibit|schedule|order form)", text, re.IGNORECASE):
        if not re.search(r"(attached|included|annexed)", text, re.IGNORECASE):
            return "Yes"
    return "No"

# --- Main Extraction ---
def extract_fields(text):
    effective = extract_date(text, "effective|start date|commence")
    expiry = extract_date(text, "expire|end date|terminate") or extract_relative_expiry(text, effective)
    customer = extract_entity(text, ["Circle K", "Couche-Tard", "Mac's Convenience Stores"])
    supplier = extract_entity(text, ["Zycus", "Zillion", "Zoom", "PDI", "Worldline", "Workday"])
    if not customer or not supplier:
        c2, s2 = extract_entities_from_intro(text)
        customer = customer or c2
        supplier = supplier or s2
    return {
        "Document Type": detect_document_type(text),
        "Term Type": detect_term_type(text),
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

# --- UI ---
uploaded_files = st.file_uploader("Upload PDF contracts", type="pdf", accept_multiple_files=True)

if uploaded_files:
    rows = []
    for file in uploaded_files:
        with st.spinner(f"Processing {file.name}..."):
            text = extract_text_from_pdf(file)
            fields = extract_fields(text)
            fields["File Name"] = file.name
            rows.append(fields)

    df = pd.DataFrame(rows)[["File Name", "Document Type", "Term Type", "Effective Date", "Expiry Date",
                             "Customer Legal Entity", "Supplier Legal Entity", "Governing Law", "Payment Term",
                             "Is Document Complete?", "Missing Exhibits/Schedules?", "Comments"]]

    st.success("✅ Extraction complete.")
    st.dataframe(df, use_container_width=True)
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download CSV", csv, "contract_metadata.csv", "text/csv")
