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
    return datetime.now()  # اگر هیچ فرمت نخورد، تاریخ امروز رو برمی‌گردونه

def upload_page():
    st.title("📤 Upload Receipt")
    img_file = st.file_uploader("Upload Receipt Image", type=["png","jpg","jpeg"])
    if img_file is None:
        return

    try:
        img_bytes = img_file.read()
    except Exception as e:
        st.error(f"Error to reading file: {e}")
        return

    # نمایش عکس رسید
    st.image(img_bytes, caption="Uploaded Receipt", use_container_width=True)

    # تحلیل رسید با مدل NER و Textract
    try:
        result = parser.parse(img_bytes)
    except RuntimeError as e:
        st.error(str(e))
        return
     # نمایش متن خام OCR
    st.markdown("---")
    st.subheader("🔍 OCR Raw Text")
    st.text_area("Raw OCR Text", result["text"], height=200)


    # جدول آیتم‌های استخراج شده (مستقل از Textract)
    items_df_ner = pd.DataFrame(result["items"])
    if not items_df_ner.empty:
        items_df_ner["Total"] = items_df_ner["price"] * items_df_ner["quantity"]
    else:
        items_df_ner = pd.DataFrame(columns=["item", "price", "quantity", "category", "Total"])
    st.subheader("🛒 Items Table (NER Extracted)")
    st.dataframe(items_df_ner, use_container_width=True)
    csv_items_ner = items_df_ner.to_csv(index=False).encode("utf-8")
    st.download_button("Download NER Items CSV", csv_items_ner, "items_ner.csv", "text/csv", key="items-ner-csv-btn")

   
    # تحلیل با Textract Expense (ساختار رسمی AWS)
    exp_resp = call_expense_analyzer(img_bytes)
    exp_data = parse_expense_response(exp_resp)

    # اضافه‌کردن دسته‌بندی پیش‌بینی‌شده به آیتم‌های exp_data
    for it in exp_data["items"]:
        if isinstance(it, dict) and "item" in it and "price" in it:
            item_name = it["item"]
            price = it["price"]
            pred = classifier.predict_category(item_name)
            it["category"] = pred
        else:
            print("Warning: Unexpected item structure:", it)

   
    # جدول متادیتا (فروشگاه، آدرس، تاریخ، تلفن)
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

    # ذخیره فایل OCR در output
    text_hash = hashlib.sha256(result["text"].encode()).hexdigest()
    ocr_path  = OUTPUT_DIR / f"{text_hash}.txt"
    with open(ocr_path, "w", encoding="utf-8") as f:
        f.write(result["text"])

    # آماده‌سازی داده برای دیتابیس
    parsed = exp_data
    date_str = parsed["date"]
    purchase_date = parse_datetime_safe(date_str)
    items_list = []
    for it in parsed["items"]:
        if isinstance(it, dict) and "item" in it and "price" in it:
            items_list.append({
                "name": it["item"],
                "price": it["price"],
                "count": it.get("quantity", 1),
                "category": it.get("category", "")
            })
        else:
            print("Warning: unexpected item format in items_list:", it)
    # ذخیره در دیتابیس با مدیریت ارور
    try:
        receipt = db.save_receipt(
            st.session_state.user_id,
            parsed["store_name"] or "",
            purchase_date,
            items_list,
            store_address=parsed.get("store_address"),
            phone=parsed.get("phone"),
            text_hash=text_hash,
            ocr_path=str(ocr_path),
        )
        st.success("Receipt successfully saved.")
    except Exception as e:
        if "UNIQUE constraint failed: receipts.text_hash" in str(e):
            st.warning("This receipt has already been uploaded and cannot be registered again.")
        else:
            st.error(f"Error saving receipt: {str(e)}")


def history_page():
    st.title("🕒 Receipt History")
    render_receipt_history(db, st.session_state.user_id, classifier)

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
