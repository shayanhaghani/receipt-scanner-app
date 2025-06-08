import sys
from pathlib import Path

# اضافه کردن پوشه services به مسیر ماژول‌ها
sys.path.append(str(Path(__file__).resolve().parent / "services"))

from db_handler import DBHandler

def main():
    db = DBHandler()
    username = "admin-shayan"
    email = "haghani.shayan@gmail.com"
    password = "#Shabnam1329"

    user_id = db.create_user(username, email, password, is_admin=True)
    print(f"✅ Admin user created with ID: {user_id}")

if __name__ == "__main__":
    main()
