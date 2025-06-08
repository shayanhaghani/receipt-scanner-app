from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, joinedload
from config import DATABASE_URL
from models import Base, User, Receipt, Item, Store
from passlib.context import CryptContext
from datetime import datetime
import logging
import json
import pandas as pd  # Add this import


# Password‐hashing context for user authentication
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Create SQLAlchemy engine using DATABASE_URL from config
engine = create_engine(DATABASE_URL, echo=False)

# Session factory for dependency injection / testing
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Create all tables based on the shared Base metadata
Base.metadata.create_all(bind=engine)

class DBHandler:
    """
    Database handler for CRUD operations.
    Accepts a session factory for dependency injection.
    """
    def __init__(self, session_factory: sessionmaker = SessionLocal):
        self._session_factory = session_factory

    def get_session(self) -> Session:
        """Return a new SQLAlchemy Session."""
        return self._session_factory()

    def add(self, obj):
        """
        Generic add: insert an ORM object and commit.
        """
        session = self.get_session()
        try:
            session.add(obj)
            session.commit()
            session.refresh(obj)
            return obj
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def authenticate_user(self, username: str, password: str) -> int | None:
        """
        Verify username & password.
        Returns the user ID if credentials are valid, else None.
        """
        session = self.get_session()
        try:
            user = session.query(User).filter_by(username=username).first()
            if not user:
                return None
            if pwd_context.verify(password, user.password):  # تغییر از hashed_password به password
                return user.id
            return None
        finally:
            session.close()

    def get_user(self, user_id: int):
        """
        Return the User ORM object for a given user_id.
        """
        session = self.get_session()
        try:
            return session.query(User).filter_by(id=user_id).first()
        finally:
            session.close()

    def list_receipts(self) -> list[Receipt]:
        """
        Return all Receipt records.
        """
        session = self.get_session()
        try:
            return session.query(Receipt).all()
        finally:
            session.close()

    def get_receipts_by_user(self, user_id: int) -> list:
        """Get all receipts for a user with store information"""
        session = self.get_session()
        try:
            return (
                session.query(Receipt)
                .options(joinedload(Receipt.store))
                .filter(Receipt.user_id == user_id)
                .all()
            )
        finally:
            session.close()

    def get_receipts_by_user_df(self, user_id: int) -> pd.DataFrame:
        """Get all receipts for a user as a pandas DataFrame"""
        receipts = self.get_receipts_by_user(user_id)
        
        data = [{
            'id': r.id,
            'date': r.date,
            'store_name': r.store.name if r.store else None,
            'total_amount': r.total_amount,
            'subtotal': r.subtotal,
            'tax': r.tax,
            'discount': r.discount
        } for r in receipts]
        
        df = pd.DataFrame(data)
        return df

    def get_all_items_by_user(self, user_id: int) -> list:
        """
        Return all items from user's receipts
        """
        session = self.get_session()
        try:
            receipts = (
                session.query(Receipt)
                .filter(Receipt.user_id == user_id)
                .all()
            )
            
            all_items = []
            for receipt in receipts:
                if receipt.items:  # اگر items خالی نبود
                    try:
                        # تبدیل رشته JSON به لیست دیکشنری
                        items_list = json.loads(receipt.items)
                        for item in items_list:
                            item['receipt_id'] = receipt.id
                            all_items.append(item)
                    except json.JSONDecodeError:
                        logging.error(f"Error decoding items for receipt {receipt.id}")
                        continue
                    
            return all_items
        finally:
            session.close()

    def get_items_by_receipt(self, receipt_id: int) -> list:
        """Get all items for a specific receipt"""
        session = self.get_session()
        try:
            return (
                session.query(Item)
                .filter_by(receipt_id=receipt_id)
                .all()
            )
        finally:
            session.close()

    def save_receipt(
        self,
        user_id: int,
        store_name: str,
        purchase_date: datetime,
        items: list[dict],
        **kwargs
    ):
        session = self.get_session()
        try:
            # پیدا کردن یا ایجاد فروشگاه
            store = session.query(Store).filter_by(name=store_name).first()
            if not store:
                store = Store(
                    name=store_name,
                    address=kwargs.get('store_address'),
                    phone=kwargs.get('phone')
                )
                session.add(store)
                session.flush()  # برای گرفتن store.id

            # ایجاد رسید
            receipt = Receipt(
                user_id=user_id,
                store_id=store.id,
                date=purchase_date,  # تغییر از purchase_date به date
                items=json.dumps(items),
                text_hash=kwargs.get('text_hash'),
                ocr_path=kwargs.get('ocr_path'),
                total_amount=kwargs.get('total_amount', 0.0),
                subtotal=kwargs.get('subtotal', 0.0),
                discount=kwargs.get('discount', 0.0),
                tax=kwargs.get('tax', 0.0),
                subtotal_after_discount=kwargs.get('subtotal_after_discount', 0.0)
            )
            session.add(receipt)
            session.commit()
            return receipt
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()

    def create_user(self, username: str, email: str, password: str, is_admin: bool = False) -> int:
        """
        - ایجاد کاربر جدید با رمز عبور رمزنگاری شده
        - برگرداندن شناسه کاربر جدید
        """
        session = self.get_session()
        try:
            # رمزنگاری رمز عبور
            hashed_pw = pwd_context.hash(password)
            # ایجاد کاربر جدید با نام ستون صحیح (password)
            user = User(
                username=username,
                email=email,
                password=hashed_pw,  # تغییر از password_hash به password
                created_at=datetime.utcnow()
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            return user.id
        except Exception as e:
            logging.error(f"خطا در ایجاد کاربر: {e}")
            raise
        finally:
            session.close()
        


    def update_item_category(self, item_id: int, new_category: str):
        """
        به‌روزرسانی دسته‌بندی (category) یک آیتم بر اساس آی‌دی.
        """
        session = self.get_session()
        try:
            item = session.query(Item).filter_by(id=item_id).first()
            if item:
                item.category = new_category
                session.commit()
        finally:
            session.close()
    
    def get_all_users(self):
        session = self.get_session()
        try:
            return session.query(User).order_by(User.created_at.desc()).all()
        finally:
            session.close()