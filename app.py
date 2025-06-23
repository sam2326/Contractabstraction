import streamlit as st
import pytesseract
from pdf2image import convert_from_bytes
import fitz  # PyMuPDF
import io
import zipfile

st.title("🧾 OCR PDF Extractor (Scanned or Hybrid)")

uploaded_files = st.file_uploader("Upload scanned or text-based PDFs", type="pdf", accept_multiple_files=True)

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # Update path if needed

def extract_text(pdf_bytes):
    # Try direct text extraction (if hybrid)
    text = ""
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page in doc:
                text += page.get_text()
    except:
        pass

    if len(text.strip()) < 50:
        # Fallback to OCR on images
        st.info("Running OCR on image-based PDF...")
        images = convert_from_bytes(pdf_bytes)
        text = ""
        for image in images:
            text += pytesseract.image_to_string(image)

    return text.strip()

if uploaded_files:
    extracted_data = []
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zipf:
        for uploaded_file in uploaded_files:
            pdf_bytes = uploaded_file.read()
            text = extract_text(pdf_bytes)

            filename = uploaded_file.name.replace(".pdf", ".txt")
            zipf.writestr(filename, text)

            st.subheader(f"📝 Text from {uploaded_file.name}")
            st.text_area("", text[:5000], height=200)

    st.download_button(
        label="⬇️ Download All OCR Results (ZIP)",
        data=zip_buffer.getvalue(),
        file_name="ocr_results.zip",
        mime="application/zip"
    )
