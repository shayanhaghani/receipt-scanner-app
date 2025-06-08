PRAGMA foreign_keys = ON;

-- Drop existing tables if they exist
DROP TABLE IF EXISTS receipts;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS stores;
DROP TABLE IF EXISTS items;

-- Create users table with email field
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Create receipts table
CREATE TABLE IF NOT EXISTS receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    store_name TEXT NOT NULL,
    date DATETIME NOT NULL,
    items TEXT NOT NULL,
    store_address TEXT,
    phone TEXT,
    text_hash TEXT UNIQUE,
    ocr_path TEXT,
    total_amount REAL DEFAULT 0.0,
    subtotal REAL DEFAULT 0.0,
    discount REAL DEFAULT 0.0,
    tax REAL DEFAULT 0.0,
    subtotal_after_discount REAL DEFAULT 0.0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Create stores table
CREATE TABLE IF NOT EXISTS stores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    address TEXT,
    phone TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Create items table
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    price REAL NOT NULL,
    quantity INTEGER DEFAULT 1,
    category TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (receipt_id) REFERENCES receipts(id)
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_receipts_user_id ON receipts(user_id);
CREATE INDEX IF NOT EXISTS idx_receipts_date ON receipts(date);
CREATE INDEX IF NOT EXISTS idx_items_receipt_id ON items(receipt_id);
CREATE INDEX IF NOT EXISTS idx_items_category ON items(category);