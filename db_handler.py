import os
import sqlite3
import streamlit as st
from typing import Any, Dict

class DBHandler:
    """
    کلاس مدیریت ارتباط با پایگاه‌داده SQLite:
    - ایجاد جداول receipts و items
    - درج رسید و آیتم‌ها با جلوگیری از تکرار
    """
    def __init__(self, db_path: str):
        # اطمینان از وجود دایرکتوری برای فایل دیتابیس
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_tables()

    def _init_tables(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS receipts (
                id INTEGER PRIMARY KEY,
                date TEXT,
                total REAL,
                tax REAL,
                discount REAL,
                text_hash TEXT UNIQUE,
                ocr_path TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY,
                receipt_id INTEGER,
                name TEXT,
                price REAL,
                count INTEGER,
                category TEXT,
                FOREIGN KEY(receipt_id) REFERENCES receipts(id)
            )
        """)
        self.conn.commit()

    def save_receipt(self, data: Dict[str, Any], ocr_path: str) -> int:
        cur = self.conn.cursor()
        text_hash = data.get("text_hash")
        # جلوگیری از درج رسید تکراری
        cur.execute("SELECT id FROM receipts WHERE text_hash = ?", (text_hash,))
        existing = cur.fetchone()
        if existing:
            st.warning("⚠️ این رسید قبلاً ذخیره شده.")
            return existing[0]

        # درج رسید جدید
        cur.execute(
            """
            INSERT INTO receipts (date, total, tax, discount, text_hash, ocr_path)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                data.get("date"),
                data.get("total"),
                data.get("tax"),
                data.get("discount"),
                text_hash,
                ocr_path,
            ),
        )
        receipt_id = cur.lastrowid

        # درج آیتم‌ها
        for name, item in data.get("items", {}).items():
            cur.execute(
                """
                INSERT INTO items (receipt_id, name, price, count, category)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    receipt_id,
                    name,
                    item.get("price"),
                    item.get("count"),
                    item.get("category"),
                ),
            )
        self.conn.commit()
        return receipt_id
