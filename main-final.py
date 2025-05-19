import os
import hashlib
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
# ─── Shim for st.experimental_rerun ──────────────────────────────────
# در نسخه‌های جدید Streamlit این تابع حذف شده، پس اگر در دسترس نبود، با RerunException جایگزینش می‌کنیم.
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
    render_items_table,   
    render_upload,
    render_summary,
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
def build_items_df(exp_data: dict) -> pd.DataFrame:
    rows = []
    for nm, it in exp_data["items"].items():
        rows.append({
            "Item": nm,
            "Price": it["price"],
            "Quantity": it["count"],
            "Total": (it["price"] or 0) * it["count"]
        })
    return pd.DataFrame(rows)

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

def upload_page():
    st.title("📤 Upload Receipt")
    img_file = st.file_uploader("Upload Receipt Image", type=["png","jpg","jpeg"])
    if img_file is None:
        # no file uploaded, wait for user to upload
        return

    # when a file is uploaded
    try:
        img_bytes = img_file.read()
    except Exception as e:
        st.error(f"Error to reading file: {e}")
        return

    # send the image to Textract
    try:
        result = parser.parse(img_bytes)
    except RuntimeError as e:
        st.error(str(e))
        return

    # show the image
    st.image(img_bytes, caption="Uploaded Receipt", use_container_width=True)

    # Scanned before , just show the text
    for nm, it in result["items"].items():
        it["category"] = classifier.predict_category(nm)
    render_items_table(result["items"])
    render_summary(
        total=result.get("total", 0.0),
        tax=result.get("tax", 0.0),
        discount=result.get("discount", 0.0)
    )

    # 2) TEMP: نمایش OCR و تولید CSV مشابه کنسول Textract
    st.markdown("---")
    st.subheader("🔍 Temporary Textract Expense Debug")
    st.text_area("Raw OCR Text", result["text"], height=200)

    # Expense API
    exp_resp = call_expense_analyzer(img_bytes)
    exp_data = parse_expense_response(exp_resp)

    # CSV metadata
    meta_df = pd.DataFrame([{
        "Store Name": exp_data["store_name"],
        "Address": exp_data["store_address"],
        "Date": exp_data["date"],
        "Phone": exp_data["phone"]
    }])
    csv_meta = meta_df.to_csv(index=False).encode("utf-8")
    st.download_button("Download metadata CSV", csv_meta, "metadata.csv", "text/csv")

    # ── METADATA TABLE DISPLAY START
    st.subheader("🏷️ Receipt Metadata")
    st.table(meta_df)
# ── METADATA TABLE DISPLAY END

    # CSV items
    items_df = build_items_df(exp_data)
    st.dataframe(items_df)
    csv_it = items_df.to_csv(index=False).encode("utf-8")
    st.download_button("Download items CSV", csv_it, "items.csv", "text/csv")

    # 3) save to DB (optional)
    text_hash = hashlib.sha256(result["text"].encode()).hexdigest()
    ocr_path  = OUTPUT_DIR / f"{text_hash}.txt"
    with open(ocr_path, "w", encoding="utf-8") as f:
        f.write(result["text"])

    parsed = exp_data
    # convert parsed date string into a datetime object
    date_str = parsed["date"]  # e.g. "3/23/2025"
    try:
        # assuming month/day/year format
        purchase_date = datetime.strptime(date_str, "%m/%d/%Y")
    except (TypeError, ValueError):
        # fallback: if it's already a datetime, use it as-is
        purchase_date = parsed["date"]
    items_list = [
        {"name": name, "price": info["price"], "count": info["count"]}
        for name, info in parsed["items"].items()
    ]
    receipt = db.save_receipt(
        st.session_state.user_id,
        parsed["store_name"] or "",
        purchase_date,     # now a datetime, not a string
        items_list,
        store_address=parsed.get("store_address"),
        phone=parsed.get("phone"),
        text_hash=text_hash,
        ocr_path=str(ocr_path),
    )

    st.success("✅ Receipt saved!")

def history_page():
    st.title("🕒 Receipt History")
    render_receipt_history(db, st.session_state.user_id)

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
    main()
