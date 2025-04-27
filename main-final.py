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
    """Initialize SQLite DB and tables."""
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
    """Load spaCy NER and classification models."""
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
    """Call Textract analyze_expense."""
    try:
        client = boto3.client("textract", region_name=AWS_REGION)
        return client.analyze_expense(Document={"Bytes": image_bytes})
    except (BotoCoreError, ClientError):
        logger.exception("Textract API error")
        st.error("Failed to connect to AWS Textract.")
        return {}

# -------------------- Extraction Utilities --------------------

def extract_text_textract(response: dict) -> str:
    """Extract raw OCR text from Textract response."""
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
    """Run NER and return list of (text, label)."""
    return [(ent.text, ent.label_) for ent in ner_model(text).ents]


def predict_category(text: str, classifier) -> str:
    """Predict product category."""
    doc = classifier(text)
    return max(doc.cats, key=doc.cats.get) if doc.cats else ""


def aggregate_items(entities: list, classifier) -> dict:
    """Aggregate ITEM/PRICE entities."""
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
    """Save receipt and items, avoid duplicates by hash. Returns receipt_id."""
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
    # new receipt
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

    menu = st.sidebar.radio("Menu", ["Upload Receipt", "📁 Receipt History", "📊 Reports"])

    if menu == "Upload Receipt":
        uploaded = st.file_uploader("Upload receipt image or PDF", type=["jpg", "jpeg", "png", "pdf"])
        if uploaded:
            img = uploaded.read()
            st.image(img, use_container_width=True)
            with st.spinner("Processing with Textract…"):
                resp = analyze_receipt_bytes(img)
                text = extract_text_textract(resp)
                fname = uploaded.name.replace(' ', '_').split('.')[0]
                path = os.path.join(OUTPUT_DIR, f"{fname}.txt")
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(text)

                st.subheader("📄 Raw OCR Text:")
                st.text(text)

                entities = extract_entities(ner_model, text)
                st.subheader("🧠 Recognized Entities (NER):")
                for t, l in entities:
                    st.markdown(f"- **{l}**: {t}")

                item_dict = aggregate_items(entities, cls_model)
                if item_dict:
                    df = pd.DataFrame([
                        {"Item": k, "Price": v["price"], "Count": v["count"], "Category": v["category"]}
                        for k, v in item_dict.items()
                    ])
                    df.index += 1
                    st.subheader("📋 Final Items Table")
                    st.dataframe(df, use_container_width=True)

                    # save or show duplicate
                    receipt_id = save_receipt(conn, text, path, item_dict, entities)

                    # price consistency check
                    total_items_price = df['Price'].sum()
                    total_receipt = next((float(v.replace("$", "")) for v, l in entities if l == "TOTAL"), 0.0)
                    tax = next((float(v.replace("$", "")) for v, l in entities if l in ("TAX", "TAX_AMOUNT")), 0.0)
                    discount = next((float(v.replace("$", "")) for v, l in entities if l in ("DISCOUNT", "DISCOUNT_AMOUNT")), 0.0)

                    st.markdown("### 💰 Price Consistency Check:")
                    st.markdown(f"- Items total: ${total_items_price:.2f}")
                    if tax:
                        st.markdown(f"- Tax: ${tax:.2f}")
                    if discount:
                        st.markdown(f"- Discount: ${discount:.2f}")
                    expected = total_items_price - abs(discount) + tax
                    st.markdown(f"- Calculated total: ${expected:.2f}")
                    st.markdown(f"- Receipt total: ${total_receipt:.2f}")
                    if abs(expected - total_receipt) > 0.1:
                        st.warning("❗ Calculated total does not match the receipt total.")
                    else:
                        st.success("✅ Calculated total matches the receipt.")
                else:
                    st.warning("No items found to display.")

    elif menu == "📁 Receipt History":
        st.header("Submitted Receipts")
        df = pd.read_sql_query("SELECT * FROM receipts ORDER BY receipt_date DESC", conn)
        if df.empty:
            st.warning("No receipts found in the database.")
        else:
            df['receipt_date'] = pd.to_datetime(df['receipt_date'], errors='coerce')
            df['Month'] = df['receipt_date'].dt.to_period('M').astype(str)
            sel = st.selectbox("📅 Select Month:", ['All'] + sorted(df['Month'].unique().tolist()))
            df_f = df if sel == 'All' else df[df['Month'] == sel]
            st.subheader("📄 Receipts")
            st.dataframe(df_f[['id', 'receipt_date', 'total_amount', 'item_count']].reset_index(drop=True))
            sid = st.selectbox("🧾 Receipt Details:", df_f['id'].tolist())
            if sid:
                df_i = pd.read_sql_query(
                    "SELECT item_name as Item, price as Price, category as Category FROM items WHERE receipt_id = ?", conn, params=(sid,)
                )
                st.subheader("📋 Items in This Receipt:")
                st.dataframe(df_i, use_container_width=True)
                import plotly.express as px
                pie = px.pie(df_f.groupby('Month')['total_amount'].sum().reset_index(), names='Month', values='total_amount', title='Monthly Purchase Totals')
                st.plotly_chart(pie, use_container_width=True)

    else:  # Reports
        st.header("📊 Purchase Category Report")
        df_items = pd.read_sql_query(
            "SELECT i.price, i.category, r.receipt_date FROM items i JOIN receipts r ON i.receipt_id = r.id", conn
        )
        if df_items.empty:
            st.warning("No data available to display.")
        else:
            df_items['receipt_date'] = pd.to_datetime(df_items['receipt_date'], errors='coerce')
            df_items['Month'] = df_items['receipt_date'].dt.to_period('M').astype(str)
            sel = st.selectbox("📅 Select Month:", sorted(df_items['Month'].unique(), reverse=True))
            df_s = df_items[df_items['Month'] == sel]
            summary = df_s.groupby('category')['price'].sum().reset_index().sort_values('price', ascending=False)
            st.subheader(f"💵 Total Expenses by Category for {sel}")
            st.dataframe(summary, use_container_width=True)
            import plotly.express as px
            fig = px.pie(summary, names='category', values='price', title='Share by Category')
            st.plotly_chart(fig, use_container_width=True)

    conn.close()

if __name__ == "__main__":
    main()
