from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, joinedload
from config import DATABASE_URL
from models import Base, User, Receipt, Item, Store  # import all models here
from passlib.context import CryptContext
from datetime import datetime


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
            if pwd_context.verify(password, user.hashed_password):
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

    def get_receipts_by_user(self, user_id: int) -> list[Receipt]:
        """
        Return all Receipt ORM objects for a given user (with joined store).
        """
        session = self.get_session()
        try:
            return (
                session.query(Receipt)
                .options(joinedload(Receipt.store))
                .filter_by(user_id=user_id)
                .all()
            )
        finally:
            session.close()

    def get_receipts_by_user_df(self, user_id: int):
        """
        Query receipts for a user (eager-load Store) and return a pandas DataFrame.
        """
        import pandas as pd
        from sqlalchemy.orm import joinedload
        from models import Receipt, Store

        session = self.get_session()
        try:
            # Eagerly load the related Store to avoid lazy loading on detached instances
            receipts = (
                session.query(Receipt)
                       .options(joinedload(Receipt.store))
                       .filter(Receipt.user_id == user_id)
                       .all()
            )
            rows = []
            for r in receipts:
                rows.append({
                    "id": r.id,
                    "store_name": r.store.name,
                    "date": r.purchase_date,
                    "total_amount": r.total_amount,
                })
            return pd.DataFrame(rows)
        finally:
            session.close()

    def get_all_items_by_user(self, user_id: int) -> list[Item]:
        """
        Return all Item ORM objects belonging to a user's receipts.
        """
        session = self.get_session()
        try:
            return (
                session.query(Item)
                .join(Receipt, Item.receipt_id == Receipt.id)
                .filter(Receipt.user_id == user_id)
                .all()
            )
        finally:
            session.close()

    def get_items_by_receipt(self, receipt_id: int) -> list[Item]:
        """
        Fetch all Item ORM objects for a given receipt ID.
        """
        session = self.get_session()
        try:
            return session.query(Item).filter_by(receipt_id=receipt_id).all()
        finally:
            session.close()

    def save_receipt(
        self,
        user_id: int,
        store_name: str,
        purchase_date,
        items: list[dict],
        **kwargs
    ) -> Receipt:
        """
        Save a new Receipt and its Items.
        
        Parameters:
        - user_id: ID of the logged-in User
        - store_name: name of the vendor/store
        - purchase_date: datetime of purchase
        - items: list of dicts, each with keys 'name', 'price', 'count', maybe 'category'
        - **kwargs: store_address, phone, tax_amount, etc. (ignored if not used)
        """
        session = self.get_session()
        try:
            # 1) find or create Store
            store = session.query(Store).filter_by(name=store_name).first()
            if not store:
                store = Store(
                    name=store_name,
                    location=kwargs.get("store_address")
                )
                session.add(store)
                session.commit()
                session.refresh(store)

            # 2) create Receipt (we compute total_amount from items)
            total = sum(
                (itm.get("price") or 0) * (itm.get("count") or 1)
                for itm in items
            )
            receipt = Receipt(
                user_id=user_id,
                store_id=store.id,
                purchase_date=purchase_date,
                total_amount=total,
                # optional fields if your model has them:
                tax_amount=kwargs.get("tax_amount"),
                discount_amount=kwargs.get("discount_amount"),
                text_hash=kwargs.get("text_hash"),
                ocr_path=kwargs.get("ocr_path"),
            )
            session.add(receipt)
            session.commit()
            session.refresh(receipt)

            # 3) save each Item
            for itm in items:
                obj = Item(
                    receipt_id=receipt.id,
                    item_name=itm.get("name"),
                    quantity=itm.get("count", 1),
                    price=itm.get("price"),
                    category=itm.get("category"),
                )
                session.add(obj)
            session.commit()

            return receipt
        finally:
            session.close()

    def create_user(self, username: str, email: str, password: str) -> int:
        """
        - Create a new User with hashed password.
        - Returns the new user's ID.
        """
        session = self.get_session()
        try:
            # hash the plain password
            hashed_pw = pwd_context.hash(password)
            # build the User object
            user = User(
                username=username,
                email=email,
                hashed_password=hashed_pw,
                created_at=datetime.utcnow()
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            return user.id
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