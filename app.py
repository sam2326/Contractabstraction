import streamlit as st
import pytesseract
from pdf2image import convert_from_bytes
import fitz  # PyMuPDF
import io
import zipfile

# Optional: Set Tesseract path if it's not in system PATH
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Optional: Set Poppler path for Windows if not in PATH
# poppler_path = r"C:\Program Files\poppler-xx\bin"
poppler_path = None  # leave as None if already in PATH

st.set_page_config(page_title="PDF OCR Extractor", layout="wide")
st.title("📄 OCR PDF Extractor")
st.markdown("Upload scanned or hybrid PDFs. We'll extract readable text using OCR if needed.")

uploaded_files = st.file_uploader("📤 Upload PDF files", type="pdf", accept_multiple_files=True)

def extract_text(pdf_bytes):
    text = ""
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page in doc:
                text += page.get_text()
    except:
        pass

    if len(text.strip()) < 50:
        images = convert_from_bytes(pdf_bytes, poppler_path=poppler_path)
        text = ""
        for img in images:
            text += pytesseract.image_to_string(img)

    return text.strip()

if uploaded_files:
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zipf:
        for file in uploaded_files:
            pdf_bytes = file.read()
            text = extract_text(pdf_bytes)
            filename = file.name.replace(".pdf", ".txt")
            zipf.writestr(filename, text)
            st.subheader(f"📝 Extracted: {file.name}")
            st.text_area("Text Preview", text[:5000], height=200)

    st.download_button(
        label="⬇️ Download All Extracted Texts (ZIP)",
        data=zip_buffer.getvalue(),
        file_name="ocr_texts.zip",
        mime="application/zip"
    )
