import os
import logging
import hashlib
from pathlib import Path

import streamlit as st
import pandas as pd

from ReceiptParser import ReceiptParser
from product_classifier import ProductClassifier
from db_handler import DBHandler
from ui_components import render_items_table, render_summary
from database import engine
from models import Base

# Ensure tables exist
Base.metadata.create_all(bind=engine)

# -------------------- Configuration --------------------
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = os.getenv("OUTPUT_DIR", str(BASE_DIR / "raw_ocr_new"))

# -------------------- Logging Setup --------------------
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

os.makedirs(OUTPUT_DIR, exist_ok=True)

# -------------------- Core Components --------------------
parser = ReceiptParser(
    ner_model_path=BASE_DIR / "receipt_ner_model",
    cls_model_path=BASE_DIR / "product_classifier" / "training" / "model-best",
    aws_region=os.getenv("AWS_REGION", "ca-central-1"),
)
classifier = ProductClassifier(
    model_path=BASE_DIR / "product_classifier" / "training" / "model-best"
)
db = DBHandler()

# -------------------- Streamlit UI --------------------
def main():
    # Must be the first Streamlit command
    st.set_page_config(page_title="SmartReceipt AI", layout="wide")

    # Initialize session state for authentication
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
        st.session_state.username = None

    # --- Authentication Forms ---
    if st.session_state.user_id is None:
        auth_choice = st.sidebar.selectbox("Login or Sign Up", ["Login", "Sign Up"])
        if auth_choice == "Sign Up":
            with st.sidebar.form("signup_form"):
                new_username = st.text_input("Username")
                new_email = st.text_input("Email")
                new_password = st.text_input("Password", type="password")
                new_password2 = st.text_input("Confirm Password", type="password")
                signup_submit = st.form_submit_button("Sign Up")
                if signup_submit:
                    if not new_username or not new_password:
                        st.error("Username and password are required.")
                    elif new_password != new_password2:
                        st.error("Passwords do not match.")
                    else:
                        try:
                            user_id = db.create_user(new_username, new_email, new_password)
                            st.session_state.user_id = user_id
                            st.session_state.username = new_username
                            st.success("Account created and logged in.")
                        except Exception as e:
                            st.error(f"Error creating account: {e}")
        else:
            with st.sidebar.form("login_form"):
                username_input = st.text_input("Username")
                password_input = st.text_input("Password", type="password")
                login_submit = st.form_submit_button("Login")
                if login_submit:
                    if not username_input or not password_input:
                        st.error("Username and password are required.")
                    else:
                        user_id = db.authenticate_user(username_input, password_input)
                        if user_id:
                            st.session_state.user_id = user_id
                            st.session_state.username = username_input
                            st.success(f"Welcome, {username_input}!")
                        else:
                            st.error("Invalid username or password.")
    
    # --- Main App: Receipt Upload ---
    if st.session_state.user_id is not None:
        st.title(f"SmartReceipt AI  |  {st.session_state.username}")
        uploaded = st.file_uploader("Upload Receipt Image", type=["png", "jpg", "jpeg"])
        if uploaded:
            image_bytes = uploaded.read()
            with st.spinner("Processing receipt…"):
                result = parser.parse(image_bytes)

            # Classify items
            for name, data in result.get("items", {}).items():
                data["category"] = classifier.predict_category(name)

            # Display results
            st.subheader("📄 Raw OCR Text:")
            st.text(result.get("text", ""))
            st.subheader("🧠 Recognized Entities:")
            for text_val, label in result.get("entities", []):
                st.markdown(f"- **{label}**: {text_val}")

            render_items_table(result.get("items", {}))
            render_summary(
                total=result.get("total", 0.0), tax=result.get("tax"), discount=result.get("discount"),
            )

            # Auto-save
            text_hash = hashlib.sha256(result.get("text", "").encode()).hexdigest()
            ocr_filename = f"{text_hash}.txt"
            ocr_path = os.path.join(OUTPUT_DIR, ocr_filename)
            with open(ocr_path, "w", encoding="utf-8") as f:
                f.write(result.get("text", ""))

            store_name = next((t for t, l in result.get("entities", []) if l in ("STORE", "VENDOR", "MERCHANT")), "unknown")
            store_location = next((t for t, l in result.get("entities", []) if l == "LOCATION"), None)

            receipt_id = db.save_receipt(
                data=result,
                ocr_path=ocr_path,
                username=st.session_state.username,
                store_name=store_name,
                store_location=store_location,
            )
            st.info(f"Receipt automatically saved with ID: {receipt_id}")

if __name__ == "__main__":
    main()
