import hashlib
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from dateutil.parser import parse as parse_date
from datetime import datetime

from database import SessionLocal
from models import User, Store, Product, Receipt, Item

class DBHandler:
    """
    مدیریت ارتباط با دیتابیس با SQLAlchemy:
    - ثبت کاربران و احراز هویت با استفاده از SHA-256
    - ثبت فروشگاه‌ها و محصولات
    - ذخیره رسیدها و آیتم‌ها
    """
    def __init__(self):
        self.session: Session = SessionLocal()

    def close(self):
        """بستن session"""
        self.session.close()

    def _hash_password(self, password: str) -> str:
        """هش کردن رمز عبور"""
        return hashlib.sha256(password.encode('utf-8')).hexdigest()

    def create_user(self, username: str, email: str, password: str) -> int:
        """
        ایجاد کاربر جدید با هش کردن رمز عبور
        """
        hashed_password = self._hash_password(password)
        user = User(username=username, email=email, hashed_password=hashed_password)
        self.session.add(user)
        try:
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
        return user.id

    def authenticate_user(self, username: str, password: str) -> int | None:
        """
        بررسی صحت نام‌کاربری و رمز عبور؛ بازگرداندن user.id در صورت موفقیت
        """
        user = self.session.query(User).filter_by(username=username).first()
        if not user:
            return None
        if user.hashed_password != self._hash_password(password):
            return None
        return user.id

    def get_or_create_store(self, name: str, location: str = None) -> Store:
        store = self.session.query(Store).filter_by(name=name).first()
        if store:
            return store
        store = Store(name=name, location=location)
        self.session.add(store)
        self.session.flush()
        return store

    def get_or_create_product(self, name: str, default_category: str = None) -> Product:
        product = self.session.query(Product).filter_by(name=name).first()
        if product:
            return product
        product = Product(name=name, default_category=default_category)
        self.session.add(product)
        self.session.flush()
        return product

    def save_receipt(
        self,
        data: dict,
        ocr_path: str,
        username: str,
        store_name: str,
        store_location: str = None
    ) -> int:
        """
        ذخیره یک رسید همراه با آیتم‌ها:
        - جلوگیری از تکرار با text_hash
        - ایجاد یا واکشی کاربر و فروشگاه
        - درج رکورد Receipt و Item
        """
        # parse purchase_date
        raw_date = data.get("date")
        try:
            purchase_date = parse_date(raw_date) if raw_date and raw_date.lower() != "unknown" else datetime.utcnow()
        except (ValueError, TypeError):
            purchase_date = datetime.utcnow()

        text_hash = data.get("text_hash")
        existing = self.session.query(Receipt).filter_by(text_hash=text_hash).first()
        if existing:
            return existing.id

        # واکشی کاربر
        user = self.session.query(User).filter_by(username=username).first()
        if not user:
            raise ValueError("User not found for saving receipt.")
        store = self.get_or_create_store(store_name, store_location)

        # ایجاد رسید
        receipt = Receipt(
            user_id=user.id,
            store_id=store.id,
            purchase_date=purchase_date,
            total_amount=data.get("total"),
            tax_amount=data.get("tax"),
            discount_amount=data.get("discount"),
            text_hash=text_hash,
            ocr_path=ocr_path
        )
        self.session.add(receipt)
        self.session.flush()

        # درج آیتم‌ها
        for name, item_data in data.get("items", {}).items():
            product = self.get_or_create_product(name, item_data.get("category"))
            item = Item(
                receipt_id=receipt.id,
                product_id=product.id,
                item_name=name,
                quantity=item_data.get("count", 1),
                price=item_data.get("price"),
                category=item_data.get("category")
            )
            self.session.add(item)

        # commit or rollback
        try:
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise

        return receipt.id
