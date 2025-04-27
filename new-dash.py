import os
import logging
import hashlib
from collections import defaultdict

import streamlit as st
import pandas as pd
import spacy
import boto3
import sqlite3
from botocore.exceptions import BotoCoreError, ClientError

# -------------------- Configuration --------------------
DB_PATH = os.getenv("DB_PATH", "receipts.db")
AWS_REGION = os.getenv("AWS_REGION", "ca-central-1")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "raw_ocr_new")

# -------------------- Logging Setup --------------------
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# -------------------- Database Layer --------------------

def init_db(path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            receipt_date TEXT,
            total_amount REAL,
            tax_amount REAL,
            discount_amount REAL,
            item_count INTEGER,
            ocr_path TEXT,
            text_hash TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            receipt_id INTEGER,
            item_name TEXT,
            price REAL,
            category TEXT,
            FOREIGN KEY(receipt_id) REFERENCES receipts(id)
        )
        """
    )
    conn.commit()
    return conn

# -------------------- Model Loading --------------------
@st.cache_resource
def load_models(
    ner_path: str = "receipt_ner_model",
    cls_path: str = "product_classifier/training/model-best"
):
    try:
        ner = spacy.load(ner_path)
        cls = spacy.load(cls_path)
        return ner, cls
    except Exception:
        logger.exception("Failed to load models")
        st.error("Failed to load models. Please verify your model paths.")
        st.stop()

# -------------------- AWS Textract --------------------

def analyze_receipt_bytes(image_bytes: bytes) -> dict:
    try:
        client = boto3.client("textract", region_name=AWS_REGION)
        return client.analyze_expense(Document={"Bytes": image_bytes})
    except (BotoCoreError, ClientError):
        logger.exception("Textract API error")
        st.error("Failed to connect to AWS Textract.")
        return {}

# -------------------- Extraction Utilities --------------------

def extract_text_textract(response: dict) -> str:
    lines = []
    for doc in response.get("ExpenseDocuments", []):
        for field in doc.get("SummaryFields", []):
            label = field.get("LabelDetection", {}).get("Text", "")
            value = field.get("ValueDetection", {}).get("Text", "")
            if label or value:
                lines.append(f"{label}: {value}")
        for grp in doc.get("LineItemGroups", []):
            for item in grp.get("LineItems", []):
                parts = []
                for f in item.get("LineItemExpenseFields", []):
                    key = f.get("Type", {}).get("Text", "")
                    val = f.get("ValueDetection", {}).get("Text", "")
                    if key and val:
                        parts.append(f"{key}: {val}")
                if parts:
                    lines.append(" | ".join(parts))
    return "\n".join(lines)

# -------------------- NER & Aggregation --------------------

def extract_entities(ner_model, text: str) -> list:
    return [(ent.text, ent.label_) for ent in ner_model(text).ents]

def predict_category(text: str, classifier) -> str:
    doc = classifier(text)
    return max(doc.cats, key=doc.cats.get) if doc.cats else ""

def aggregate_items(entities: list, classifier) -> dict:
    items = defaultdict(lambda: {"price": 0.0, "count": 0, "category": ""})
    for i in range(len(entities) - 1):
        if entities[i][1] == "ITEM" and entities[i+1][1] == "PRICE":
            item = entities[i][0].strip()
            try:
                price = float(entities[i+1][0].replace("$", ""))
            except ValueError:
                continue
            cat = predict_category(item, classifier)
            items[item]["price"] += price
            items[item]["count"] += 1
            items[item]["category"] = cat
    return items

# -------------------- Persistence --------------------

def save_receipt(conn, text: str, ocr_path: str, items: dict, entities: list) -> int:
    cur = conn.cursor()
    text_hash = hashlib.sha256(text.encode()).hexdigest()
    cur.execute("SELECT id FROM receipts WHERE text_hash = ?", (text_hash,))
    dup = cur.fetchone()
    if dup:
        st.warning("⚠️ This receipt has already been scanned and saved.")
        dup_id = dup[0]
        df_existing = pd.read_sql_query("SELECT * FROM receipts WHERE id = ?", conn, params=(dup_id,))
        st.dataframe(df_existing, use_container_width=True)
        st.stop()
    total = next((float(v.replace("$", "")) for v, l in entities if l == "TOTAL"), 0.0)
    tax = next((float(v.replace("$", "")) for v, l in entities if l in ("TAX", "TAX_AMOUNT")), 0.0)
    discount = next((float(v.replace("$", "")) for v, l in entities if l in ("DISCOUNT", "DISCOUNT_AMOUNT")), 0.0)
    date = next((v for v, l in entities if l == "DATE"), "unknown")
    cur.execute(
        """
        INSERT INTO receipts(receipt_date, total_amount, tax_amount, discount_amount, item_count, ocr_path, text_hash)
        VALUES(?,?,?,?,?,?,?)
        """,
        (date, total, tax, abs(discount), len(items), ocr_path, text_hash)
    )
    rid = cur.lastrowid
    recs = [(rid, item, data["price"], data["category"]) for item, data in items.items()]
    cur.executemany(
        "INSERT INTO items(receipt_id,item_name,price,category) VALUES(?,?,?,?)", recs
    )
    conn.commit()
    return rid

# -------------------- Streamlit UI --------------------

def main():
    st.set_page_config(page_title="SmartReceipt AI", layout="wide")
    ner_model, cls_model = load_models()
    conn = init_db()

    menu = st.sidebar.radio("Menu", ["Upload Receipt", "📁 Receipt History", "📊 Reports", "📆 Monthly Overview"])

    if menu == "📆 Monthly Overview":
        st.header("📆 Monthly Overview")

        df = pd.read_sql_query("""
            SELECT r.receipt_date, r.total_amount, r.id AS receipt_id, i.item_name, i.price, i.category
            FROM receipts r
            JOIN items i ON r.id = i.receipt_id
        """, conn)

        if df.empty:
            st.warning("هیچ داده‌ای برای نمایش وجود ندارد.")
        else:
            df["receipt_date"] = pd.to_datetime(df["receipt_date"], errors="coerce")
            df["ماه"] = df["receipt_date"].dt.to_period("M").astype(str)
            df["روز"] = df["receipt_date"].dt.day

            selected_month = st.selectbox("📅 انتخاب ماه:", sorted(df["ماه"].dropna().unique(), reverse=True))
            current_month_df = df[df["ماه"] == selected_month]

            all_months = sorted(df["ماه"].dropna().unique(), reverse=True)
            prev_month = all_months[all_months.index(selected_month) + 1] if selected_month in all_months and all_months.index(selected_month) + 1 < len(all_months) else None
            prev_month_df = df[df["ماه"] == prev_month] if prev_month else pd.DataFrame()

            total_current = current_month_df["price"].sum()
            total_prev = prev_month_df["price"].sum() if not prev_month_df.empty else 0
            percent_change = ((total_current - total_prev) / total_prev * 100) if total_prev else 0

            receipts_count = current_month_df["receipt_id"].nunique()
            items_count = len(current_month_df)
            avg_per_receipt = total_current / receipts_count if receipts_count else 0

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("💸 مجموع خرید", f"${total_current:.2f}", f"{percent_change:+.1f}%" if prev_month else None)
            col2.metric("🧾 تعداد رسید", receipts_count)
            col3.metric("🛒 تعداد آیتم‌ها", items_count)
            col4.metric("📊 میانگین هر رسید", f"${avg_per_receipt:.2f}")

            top_categories = current_month_df.groupby("category")["price"].sum().reset_index().sort_values(by="price", ascending=False)
            top_category_name = top_categories.iloc[0]["category"] if not top_categories.empty else "-"
            top_category_amount = top_categories.iloc[0]["price"] if not top_categories.empty else 0
            st.markdown(f"### 🏆 پرهزینه‌ترین دسته‌بندی: `{top_category_name}` - ${top_category_amount:.2f}")

            st.subheader("📈 روند خرید در طول ماه")
            import plotly.express as px
            daily_trend = current_month_df.groupby("روز")["price"].sum().reset_index()
            fig = px.bar(daily_trend, x="روز", y="price", labels={"روز": "روز", "price": "مبلغ"}, title="هزینه روزانه")
            st.plotly_chart(fig, use_container_width=True)

            st.subheader("📊 نمودار دسته‌بندی‌ها")
            fig2 = px.pie(top_categories, names="category", values="price", title="سهم دسته‌بندی‌ها")
            st.plotly_chart(fig2, use_container_width=True)

    conn.close()

if __name__ == "__main__":
    main()
