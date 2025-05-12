import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext
from dateutil.parser import parse as parse_date
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError

from models import Base, User, Store, Product, Receipt, Item

# پیکربندی اتصال
DB_URL = "sqlite:///receipts.db"
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Context برای هش‌کردن پسورد
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class DBHandler:
    def __init__(self):
        self.session = SessionLocal()

    # ----- User -----
    def create_user(self, username: str, email: str, password: str) -> int | None:
        if self.session.query(User).filter_by(username=username).first():
            return None
        hashed = pwd_context.hash(password)
        user = User(username=username, email=email, hashed_password=hashed)
        self.session.add(user)
        try:
            self.session.commit()
            self.session.refresh(user)
            return user.id
        except SQLAlchemyError:
            self.session.rollback()
            return None

    def authenticate_user(self, username: str, password: str) -> int | None:
        user = self.session.query(User).filter_by(username=username).first()
        if not user:
            return None
        try:
            if pwd_context.verify(password, user.hashed_password):
                return user.id
        except Exception:
            # مهاجرت از هش قدیمی
            if user.hashed_password == password:
                new_hash = pwd_context.hash(password)
                user.hashed_password = new_hash
                self.session.commit()
                return user.id
        return None

    def get_user(self, user_id: int) -> User | None:
        return self.session.query(User).filter_by(id=user_id).first()

    def update_user(self, user_id: int, email: str | None = None, password: str | None = None) -> bool:
        user = self.get_user(user_id)
        if not user:
            return False
        if email:
            user.email = email
        if password:
            user.hashed_password = pwd_context.hash(password)
        try:
            self.session.commit()
            return True
        except SQLAlchemyError:
            self.session.rollback()
            return False

    # ----- Receipt & Item -----
    def save_receipt(
        self,
        data: dict,
        ocr_path: str,
        user_id: int,
        store_name: str,
        store_location: str | None = None
    ) -> int:
        # تبدیل تاریخ
        raw_date = data.get("date")
        try:
            purchase_date = parse_date(raw_date) if raw_date and raw_date.lower() != "unknown" else datetime.utcnow()
        except Exception:
            purchase_date = datetime.utcnow()

        # جلوگیری از تکرار
        text_hash = data.get("text_hash")
        existing = (
            self.session.query(Receipt)
            .filter_by(text_hash=text_hash, user_id=user_id)
            .first()
        )
        if existing:
            return existing.id

        # ایجاد یا واکشی فروشگاه
        store = self.session.query(Store).filter_by(name=store_name).first()
        if not store:
            store = Store(name=store_name, location=store_location)
            self.session.add(store)
            self.session.flush()

        # درج رسید
        receipt = Receipt(
            user_id=user_id,
            store_id=store.id,
            purchase_date=purchase_date,
            total_amount=data.get("total", 0.0),
            tax_amount=data.get("tax", 0.0),
            discount_amount=data.get("discount", 0.0),
            text_hash=text_hash,
            ocr_path=ocr_path
        )
        self.session.add(receipt)
        self.session.flush()

        # درج آیتم‌ها و محصولات
        for name, item in data.get("items", {}).items():
            product = self.session.query(Product).filter_by(name=name).first()
            if not product:
                product = Product(name=name, default_category=item.get("category", ""))
                self.session.add(product)
                self.session.flush()
            it = Item(
                receipt_id=receipt.id,
                product_id=product.id,
                item_name=name,
                quantity=item.get("count", 1),
                price=item.get("price", 0.0),
                category=item.get("category", "")
            )
            self.session.add(it)

        try:
            self.session.commit()
            return receipt.id
        except SQLAlchemyError:
            self.session.rollback()
            raise

    # ----- متد جدید: خروجی DataFrame برای UI History -----
    def get_receipts_by_user_df(self, user_id: int) -> pd.DataFrame:
        """
        خروجی DataFrame شامل ستون‌های:
        id, purchase_date, store_name, total_amount
        """
        receipts = (
            self.session.query(Receipt)
            .filter_by(user_id=user_id)
            .order_by(Receipt.purchase_date.desc())
            .all()
        )
        data = [
            {
                "id": r.id,
                "purchase_date": r.purchase_date,
                "store_name": r.store.name,
                "total_amount": r.total_amount
            }
            for r in receipts
        ]
        return pd.DataFrame(data)

    def get_items_by_receipt(self, receipt_id: int) -> list[Item]:
        return self.session.query(Item).filter_by(receipt_id=receipt_id).all()

    def get_all_items_by_user(self, user_id: int) -> list[Item]:
        return (
            self.session.query(Item)
            .join(Receipt, Item.receipt_id == Receipt.id)
            .filter(Receipt.user_id == user_id)
            .all()
        )
