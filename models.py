from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Text,
    Index
)
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    receipts = relationship('Receipt', back_populates='user')

class Store(Base):
    __tablename__ = 'stores'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    location = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    receipts = relationship('Receipt', back_populates='store')

class Product(Base):
    __tablename__ = 'products'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    default_category = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    items = relationship('Item', back_populates='product')

class Receipt(Base):
    __tablename__ = 'receipts'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    store_id = Column(Integer, ForeignKey('stores.id'), nullable=False)
    purchase_date = Column(DateTime, nullable=False)
    total_amount = Column(Float)
    tax_amount = Column(Float)
    discount_amount = Column(Float)
    text_hash = Column(String, unique=True, nullable=False)
    ocr_path = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship('User', back_populates='receipts')
    store = relationship('Store', back_populates='receipts')
    items = relationship('Item', back_populates='receipt')

    __table_args__ = (
        Index('idx_receipts_date', 'purchase_date'),
        Index('idx_receipts_store', 'store_id'),
        Index('idx_receipts_user', 'user_id'),
    )

class Item(Base):
    __tablename__ = 'items'
    id = Column(Integer, primary_key=True, index=True)
    receipt_id = Column(Integer, ForeignKey('receipts.id'), nullable=False)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=True)
    item_name = Column(String, nullable=False)
    quantity = Column(Integer, default=1)
    price = Column(Float)
    category = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    receipt = relationship('Receipt', back_populates='items')
    product = relationship('Product', back_populates='items')

    __table_args__ = (
        Index('idx_items_receipt', 'receipt_id'),
        Index('idx_items_category', 'category'),
    )
