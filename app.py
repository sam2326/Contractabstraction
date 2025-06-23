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
                # OCR fallback
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
    pattern = rf"{label}.*?(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{{1,2}},\s+\d{{4}}"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1) + " " + re.findall(r"\d{1,2},\s+\d{4}", match.group())[0]
    return ""

def extract_relative_expiry(text, eff_date):
    match = re.search(r"valid.*?(one|two|three|1|2|3).*?year", text, re.IGNORECASE)
    if match and eff_date:
        years = {"one": 1, "two": 2, "three": 3, "1": 1, "2": 2, "3": 3}
        val = match.group(1).lower()
        try:
            base = datetime.strptime(eff_date, "%B %d, %Y")
            return (base + timedelta(days=365 * years[val])).strftime("%B %d, %Y")
        except:
            return ""
    return ""

def extract_entity(text, entity_list):
    for e in entity_list:
        if re.search(re.escape(e), text, re.IGNORECASE):
            return e
    return ""

def extract_governing_law(text):
    match = re.search(r"governed by.*?(state|province)?\s*of\s*([\w\s]+)[\.,]", text, re.IGNORECASE)
    return match.group(2).strip() if match else ""

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
    return {
        "Document Type": detect_document_type(text),
        "Term Type": detect_term_type(text),
        "Effective Date": effective,
        "Expiry Date": expiry,
        "Customer Legal Entity": extract_entity(text, ["Circle K", "Couche-Tard", "Mac's Convenience Stores"]),
        "Supplier Legal Entity": extract_entity(text, ["Zycus", "Zillion", "Zoom", "PDI", "Worldline", "Workday"]),
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
