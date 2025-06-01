import os
import hashlib
import logging
from functools import lru_cache
from pathlib import Path
from datetime import datetime
from config import (
    BASE_DIR,
    OUTPUT_DIR,
    DATABASE_URL,   # if you need it in DBHandler
    NER_MODEL_DIR,
    CLS_MODEL_DIR,
    AWS_REGION,
)

import streamlit as st
# Shim for st.experimental_rerun
# In newer versions of Streamlit this function is removed, so if not available, we replace it with RerunException
try:
    _ = st.experimental_rerun
except AttributeError:
    from streamlit.runtime.scriptrunner.script_runner import RerunException

    def experimental_rerun():
        """Re-raise a RerunException to force Streamlit to rerun the script."""
        raise RerunException("Rerun requested")

    st.experimental_rerun = experimental_rerun
# ────────────────────────────────────────────────────────────────────────
from services.textract_service import (
    call_expense_analyzer,
    parse_expense_response,
)
import pandas as pd

from database import engine
from models import Base
from services.db_handler import DBHandler
from receipt_parser import ReceiptParser
from product_classifier import ProductClassifier
from ui_components import (   
    render_upload,
    render_receipt_history,   
    render_dashboard,
    render_profile,
    render_login,
    render_logout
)


os.makedirs(OUTPUT_DIR, exist_ok=True)
# create table at startup
Base.metadata.create_all(bind=engine)

# Initialize database handler (uses DATABASE_URL from config)
db = DBHandler()

# Initialize Textract-based parser with model paths and AWS region from config
parser = ReceiptParser(
    ner_model_path=str(NER_MODEL_DIR),
    cls_model_path=str(CLS_MODEL_DIR),
    aws_region=AWS_REGION,
)

# Initialize product classifier with the directory from config
classifier = ProductClassifier(
    model_path=str(CLS_MODEL_DIR)
)
def build_items_df(exp_data):
    items_data = []
    for it in exp_data["items"]:
        if isinstance(it, dict) and "item" in it and "price" in it:
            item_name = it["item"]
            price = it["price"]
            count = it.get("quantity", 1)
            category = it.get("category", "")
            items_data.append({
                "item": item_name,
                "price": price,
                "quantity": count,
                "category": category,
                "total": price * count
            })
        else:
            print("Warning: Unexpected item format in build_items_df:", it)
    return pd.DataFrame(items_data)
    

# ─── Streamlit Pages ───────────────────────────────────────────────────────────
def auth_flow():
    st.title("Welcome to SmartReceipt AI")
    mode = st.selectbox("Login or Sign Up", ["Login", "Sign Up"])
    if mode == "Sign Up":
        u = st.text_input("Username", key="su_user")
        e = st.text_input("Email", key="su_email")
        p1 = st.text_input("Password", type="password", key="su_p1")
        p2 = st.text_input("Confirm Password", type="password", key="su_p2")
        if st.button("Sign Up"):
            if not (u and e and p1):
                st.error("All fields are required.")
            elif p1 != p2:
                st.error("Passwords do not match.")
            else:
                uid = db.create_user(u, e, p1)
                if uid:
                    st.success("Account created! Please log in.")
                else:
                    st.error("Username exists.")
    else:
        u = st.text_input("Username", key="li_user")
        p = st.text_input("Password", type="password", key="li_pw")
        if st.button("Login"):
            uid = db.authenticate_user(u, p)
            if uid:
                st.session_state.user_id = uid
                st.session_state.username = u
                st.experimental_rerun()
            else:
                st.error("Invalid credentials.")
def parse_datetime_safe(date_str):
    if isinstance(date_str, datetime):
        return date_str
    formats = [
        "%m/%d/%Y",   # 4/6/2025
        "%Y-%m-%d",   # 2025-04-06
        "%b %d %Y",   # Apr 06 2025
        "%B %d %Y",   # April 06 2025
        "%d %b %Y",   # 06 Apr 2025
        "%d %B %Y",   # 06 April 2025
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except Exception:
            continue
    return datetime.now()  # If no format matches, return current date

def upload_page():
    st.title("📤 Upload Receipt")
    img_file = st.file_uploader("Upload Receipt Image", type=["png","jpg","jpeg"])
    if img_file is None:
        return

    try:
        img_bytes = img_file.read()
        if len(img_bytes) > 5 * 1024 * 1024:  # 5MB limit
            st.error("File size too large. Maximum size is 5MB.")
            return
    except Exception as e:
        logging.error(f"Error reading file: {e}")
        st.error("Error reading file. Please try again.")
        return

    # Display receipt image
    st.image(img_bytes, caption="Uploaded Receipt", use_container_width=True)

    # Analyze receipt with NER model and Textract
    try:
        result = parser.parse(img_bytes)
        total_amount = result.get("total_amount", 0.0)
    except Exception as e:
        logging.error(f"Error parsing receipt: {e}")
        st.error("Error processing receipt. Please try again.")
        return

    # Display items table with breakdown
    items_df_ner = pd.DataFrame(result["items"])
    if not items_df_ner.empty:
        # Convert price to float first
        items_df_ner["price"] = pd.to_numeric(items_df_ner["price"], errors='coerce')
        items_df_ner["Total"] = items_df_ner["price"] * items_df_ner["quantity"]
        
        # Calculate subtotal before formatting
        subtotal = items_df_ner["Total"].sum() if not items_df_ner.empty else 0.0
        
        # Now format for display
        items_df_ner["price"] = items_df_ner["price"].apply(lambda x: f"{x:.2f}")
        items_df_ner["Total"] = items_df_ner["Total"].apply(lambda x: f"{x:.2f}")
    else:
        items_df_ner = pd.DataFrame(columns=["item", "price", "quantity", "category", "Total"])
        subtotal = 0.0
    
    st.subheader("🛒 Items Table (NER Extracted)")
    st.dataframe(items_df_ner, use_container_width=True)
    
    # Calculate all amounts first
    subtotal = items_df_ner["Total"].astype(float).sum() if not items_df_ner.empty else 0.0
    total_amount = float(result.get("total_amount", 0.0))
    discount = float(result.get("discount", 0.0))
    subtotal_after_discount = subtotal - discount
    tax = round(total_amount - subtotal_after_discount, 2)

    # Create summary DataFrame with all fields always present
    summary_data = [
        {"Type": "Subtotal", "Amount": f"${subtotal:.2f}", "Note": ""},
        {"Type": "Discount", "Amount": f"-${discount:.2f}", "Note": f"({(discount/subtotal*100):.1f}% off)" if discount > 0 else ""},
        {"Type": "Subtotal after discount", "Amount": f"${subtotal_after_discount:.2f}", "Note": ""},
        {"Type": "Tax", "Amount": f"${tax:.2f}", "Note": f"({(tax/subtotal_after_discount*100):.1f}%)" if tax > 0 else ""},
        {"Type": "Total Amount", "Amount": f"${total_amount:.2f}", "Note": ""}
    ]
    
    # Create and display summary table
    summary_df = pd.DataFrame(summary_data)
    summary_df = summary_df.set_index("Type")
    
    st.subheader("💰 Receipt Summary")
    st.table(summary_df)

    csv_items_ner = items_df_ner.to_csv(index=False).encode("utf-8")
    st.download_button("Download NER Items CSV", csv_items_ner, "items_ner.csv", "text/csv", key="items-ner-csv-btn")

   
    # Analysis with Textract Expense (AWS official structure)
    exp_resp = call_expense_analyzer(img_bytes)
    exp_data = parse_expense_response(exp_resp)

    # Add predicted categories to exp_data items
    for it in exp_data["items"]:
        if isinstance(it, dict) and "item" in it and "price" in it:
            item_name = it["item"]
            price = it["price"]
            pred = classifier.predict_category(item_name)
            it["category"] = pred
        else:
            print("Warning: Unexpected item structure:", it)

    # Metadata table (store, address, date, phone)
    meta_df = pd.DataFrame([{
        "Store Name": exp_data["store_name"],
        "Address": exp_data["store_address"],
        "Date": exp_data["date"],
        "Phone": exp_data["phone"]
    }])
    st.subheader("🏷️ Receipt Metadata")
    st.table(meta_df)
    csv_meta = meta_df.to_csv(index=False).encode("utf-8")
    st.download_button("Download metadata CSV", csv_meta, "metadata.csv", "text/csv", key="meta-csv-btn")

    # Save OCR file in output directory
    text_hash = hashlib.sha256(result["text"].encode()).hexdigest()
    ocr_path  = OUTPUT_DIR / f"{text_hash}.txt"
    with open(ocr_path, "w", encoding="utf-8") as f:
        f.write(result["text"])

    # Prepare data for database
    parsed = exp_data
    date_str = parsed["date"]
    purchase_date = parse_datetime_safe(date_str)
    
    # Fix: Use items from result instead of parsed["items"]
    items_list = []
    for item in result["items"]:
        items_list.append({
            "name": item["item"],
            "price": item["price"],
            "count": item["quantity"],
            "category": item["category"]
        })

    try:
        receipt = db.save_receipt(
            st.session_state.user_id,
            parsed["store_name"] or "",
            purchase_date,
            items_list,  # Now contains actual items
            store_address=parsed.get("store_address"),
            phone=parsed.get("phone"),
            text_hash=text_hash,
            ocr_path=str(ocr_path),
            total_amount=total_amount
        )
        st.success(f"Receipt successfully saved. Total amount: ${total_amount:.2f}")
        
        # Log the total amount for debugging
        logging.info(f"Saved receipt with total_amount: ${total_amount:.2f}")
        
    except Exception as e:
        logging.error(f"Error saving receipt: {e}, total_amount: {total_amount}")
        if "UNIQUE constraint failed: receipts.text_hash" in str(e):
            st.warning("This receipt has already been uploaded and cannot be registered again.")
        else:
            st.error(f"Error saving receipt: {str(e)}")


def history_page():
    st.title("🕒 Receipt History")
    try:
        render_receipt_history(db, st.session_state.user_id, classifier)
    except Exception as e:
        logging.error(f"Error in history page: {e}")
        st.error("An error occurred loading the history. Please try refreshing the page.")

def dashboard_page():
    st.title("📊 Dashboard")
    render_dashboard(db, st.session_state.user_id)

def profile_page():
    st.title("👤 Profile")
    render_profile(db, st.session_state.user_id)

def logout():
    st.session_state.pop("user_id", None)
    st.session_state.pop("username", None)
    st.experimental_rerun()

def main():
    st.set_page_config(page_title="SmartReceipt AI", layout="wide")
    if "user_id" not in st.session_state:
        auth_flow()
        return
    st.sidebar.title(f"👤 {st.session_state.username}")
    page = st.sidebar.selectbox("Navigate to", ["Upload","History","Dashboard","Profile"])
    if st.sidebar.button("Logout"):
        logout()
        return
    if page=="Upload":
        upload_page()
    elif page=="History":
        history_page()
    elif page=="Dashboard":
        dashboard_page()
    elif page=="Profile":
        profile_page()

if __name__ == "__main__":
    # logging
    logging.basicConfig(
        filename='app.log',
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    # Classifier
    @lru_cache(maxsize=1000)
    def cached_predict_category(item_name: str) -> str:
        return classifier.predict_category(item_name)
    main()
