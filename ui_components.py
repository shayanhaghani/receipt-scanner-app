import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from typing import Dict, Any


# ---- فرم ورود/ثبت‌نام ----
def render_login(db):
    st.title("🔐 ورود یا ثبت‌نام")
    mode = st.selectbox("", ["Login", "Sign Up"])
    if mode == "Sign Up":
        username = st.text_input("Username", key="su_user")
        email    = st.text_input("Email",    key="su_email")
        pw1      = st.text_input("Password", type="password", key="su_pw1")
        pw2      = st.text_input("Confirm Password", type="password", key="su_pw2")
        if st.button("Sign Up"):
            if not (username and email and pw1):
                st.error("All fields are required.")
            elif pw1 != pw2:
                st.error("Passwords do not match.")
            else:
                uid = db.create_user(username, email, pw1)
                if uid:
                    st.success("Account created! Please switch to Login.")
                else:
                    st.error("Username already exists.")
    else:
        username = st.text_input("Username", key="li_user")
        password = st.text_input("Password", type="password", key="li_pw")
        if st.button("Login"):
            uid = db.authenticate_user(username, password)
            if uid:
                st.session_state.user_id  = uid
                st.session_state.username = username
                st.experimental_rerun()
            else:
                st.error("Invalid username or password.")

# ---- دکمه‌ی خروج ----
def render_logout():
    if st.sidebar.button("Logout"):
        st.session_state.pop("user_id", None)
        st.session_state.pop("username", None)
        st.experimental_rerun()

# ---- آپلود فایل ----
def render_upload():
    return st.file_uploader("Upload Receipt Image", type=["png","jpg","jpeg"])

# ---- نمایش خلاصه رسید ----
def render_summary(total: float, tax: float, discount: float):
    st.subheader("💰 Summary")
    st.markdown(f"- **Total:** ${total:.2f}")
    st.markdown(f"- **Tax:** ${tax:.2f}")
    st.markdown(f"- **Discount:** ${discount:.2f}")

# ---- تاریخچه رسیدها ----
def render_history(db, user_id: int):
    df = db.get_receipts_by_user_df(user_id)
    if df.empty:
        st.info("هیچ رسیده‌ای موجود نیست.")
    else:
        st.subheader("🕒 Receipt History")
        st.dataframe(df[["id","purchase_date","store_name","total_amount"]])

# ---- داشبورد هزینه‌ها ----
def render_dashboard(db, user_id: int):
    items = db.get_all_items_by_user(user_id)
    if not items:
        st.info("No items to display.")
        return
    df = pd.DataFrame([{
        "category": it.category,
        "amount": it.price * it.quantity
    } for it in items])
    summary = df.groupby("category")["amount"].sum().reset_index()
    fig, ax = plt.subplots()
    ax.bar(summary["category"], summary["amount"])
    ax.set_xlabel("Category")
    ax.set_ylabel("Total Spent")
    ax.set_title("Spending by Category")
    plt.xticks(rotation=45, ha="right")
    st.pyplot(fig)

# ---- مدیریت پروفایل ----
def render_profile(db, user_id: int):
    user = db.get_user(user_id)
    st.subheader("👤 Profile")
    st.write(f"**Username:** {user.username}")
    st.write(f"**Email:** {user.email or '—'}")
    new_email = st.text_input("New Email", value=user.email or "")
    pw1       = st.text_input("New Password", type="password")
    pw2       = st.text_input("Confirm New Password", type="password")
    if st.button("Update Profile"):
        if pw1 and pw1 != pw2:
            st.error("Passwords do not match.")
        else:
            ok = db.update_user(user_id, email=new_email or None, password=pw1 or None)
            if ok:
                st.success("Profile updated successfully.")
            else:
                st.error("Error updating profile.")


def render_items_table(items: Dict[str, Any]) -> None:
  
    df = pd.DataFrame([
        {
            "Item": name,
            "Price": data.get("price", 0.0),
            "Count": data.get("count", 1),
            "Category": data.get("category", "")
        }
        for name, data in items.items()
    ])
    df.index += 1
    st.subheader("📋 Items")
    st.dataframe(df, use_container_width=True)

def render_receipt_history(db, user_id):
    """
    لیست رسیدهای کاربر با user_id را از دیتابیس بخواند
    و در قالب جدول نمایش دهد.
    """
    # فرض می‌کنیم db.get_receipts(user_id) لیستی از دیکشنری‌های {id, date, total, store_name} برمی‌گرداند
    receipts_df = db.get_receipts_by_user_df(user_id)
    if receipts_df.empty:
        st.info("هیچ رسیدی یافت نشد.")
        return

    # تغییر نام ستون‌ها و نمایش دیتافریم
    df = receipts_df.rename(columns={
        "id": "ID",
        "date": "تاریخ",
        "total": "جمع کل",
        "store_name": "فروشگاه"
    })
    st.subheader("📜 تاریخچهٔ رسیدها")
    st.dataframe(df, use_container_width=True)

    # انتخاب یک رسید برای نمایش جزئیات
    sel = st.selectbox("انتخاب رسید برای جزییات", df["ID"])
    items = db.get_items_by_receipt(sel)  # لیست آبجکت‌های Item

    # تبدیل آبجکت Item به دیکشنری
    items_list = [
        {"نام": it.item_name, "قیمت": it.price, "دسته": it.category}
        for it in items
    ]
    st.write("**جزئیات رسید:**")
    st.table(pd.DataFrame(items_list))  