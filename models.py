from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Float,
    ForeignKey
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
from sqlalchemy import Boolean

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)  # اضافه کردن فیلد email
    is_admin = Column(Boolean, default=False)
    password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    receipts = relationship("Receipt", back_populates="user")

class Store(Base):
    __tablename__ = "stores"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    address = Column(String)
    phone = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    receipts = relationship("Receipt", back_populates="store")

class Receipt(Base):
    __tablename__ = "receipts"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    store_id = Column(Integer, ForeignKey('stores.id'))
    date = Column(DateTime, nullable=False)
    items = Column(String)  # JSON string of items
    text_hash = Column(String, unique=True)
    ocr_path = Column(String)
    total_amount = Column(Float, default=0.0)
    subtotal = Column(Float, default=0.0)
    discount = Column(Float, default=0.0)
    tax = Column(Float, default=0.0)
    subtotal_after_discount = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    store = relationship("Store", back_populates="receipts")
    user = relationship("User", back_populates="receipts")
    items_rel = relationship("Item", back_populates="receipt")

class Item(Base):
    __tablename__ = "items"
    
    id = Column(Integer, primary_key=True)
    receipt_id = Column(Integer, ForeignKey('receipts.id'), nullable=False)
    name = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    quantity = Column(Integer, default=1)
    category = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    receipt = relationship("Receipt", back_populates="items_rel")
