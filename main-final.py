import os
import logging
import hashlib
from pathlib import Path

import streamlit as st
import pandas as pd

# اصلاح import برای ماژول ReceiptParser مطابق نام فایل
from ReceiptParser import ReceiptParser
from product_classifier import ProductClassifier
from db_handler import DBHandler
from ui_components import render_items_table, render_summary

# -------------------- Configuration --------------------
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = os.getenv("DB_PATH", "receipts.db")
AWS_REGION = os.getenv("AWS_REGION", "ca-central-1")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "raw_ocr_new")

# -------------------- Logging Setup --------------------
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# -------------------- Core Components --------------------
parser = ReceiptParser(
    ner_model_path=BASE_DIR / "receipt_ner_model",
    cls_model_path=BASE_DIR / "product_classifier" / "training" / "model-best",
    aws_region=AWS_REGION
)
classifier = ProductClassifier(
    model_path=BASE_DIR / "product_classifier" / "training" / "model-best"
)
db = DBHandler(DB_PATH)

# -------------------- Streamlit UI --------------------
def main():
    st.set_page_config(page_title="SmartReceipt AI", layout="wide")
    st.title("SmartReceipt AI")

    uploaded = st.file_uploader("Upload Receipt Image", type=["png", "jpg", "jpeg"])
    if not uploaded:
        return

    image_bytes = uploaded.read()
    with st.spinner("Processing receipt…"):
        result = parser.parse(image_bytes)

    # classify each item
    for name, data in result.get("items", {}).items():
        data["category"] = classifier.predict_category(name)

    # Display raw OCR text
    st.subheader("📄 Raw OCR Text:")
    st.text(result.get("text", ""))

    # Display recognized entities
    st.subheader("🧠 Recognized Entities (NER):")
    for text, label in result.get("entities", []):
        st.markdown(f"- **{label}**: {text}")

    # Display items table
    render_items_table(result.get("items", {}))

    # Display summary
    render_summary(
        total=result.get("total", 0.0),
        tax=result.get("tax"),
        discount=result.get("discount")
    )

    # Save to database
    if st.button("Save Receipt"):
        text_hash = hashlib.sha256(result.get("text", "").encode()).hexdigest()
        ocr_filename = f"{text_hash}.txt"
        ocr_path = os.path.join(OUTPUT_DIR, ocr_filename)
        with open(ocr_path, "w", encoding="utf-8") as f:
            f.write(result.get("text", ""))
        receipt_id = db.save_receipt(result, ocr_path)
        st.success(f"Receipt saved with ID: {receipt_id}")


if __name__ == "__main__":
    main()
