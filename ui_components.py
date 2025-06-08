from typing import Optional
import time
from functools import lru_cache
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import logging  # Add this import
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


# Rate limiting for login attempts
LOGIN_ATTEMPT_LIMIT = 5
login_attempts = {}

def check_rate_limit(username: str) -> bool:
    current_time = time.time()
    if username in login_attempts:
        attempts = [t for t in login_attempts[username] if current_time - t < 3600]
        login_attempts[username] = attempts
        return len(attempts) < LOGIN_ATTEMPT_LIMIT
    return True

@lru_cache(maxsize=100)
def get_cached_receipt_data(receipt_id: int) -> Optional[dict]:
    # ...cache receipt data...
    pass

# ---- فرم ورود/ثبت‌نام ----
def render_login(db):
    st.title("🔐 Login or Sign up")
    
    # Initialize session state
    if "login_submitted" not in st.session_state:
        st.session_state.login_submitted = False
    
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
        
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("Login", use_container_width=True, key="login_button"):
                st.session_state.login_submitted = True
                
        if st.session_state.login_submitted:
            if not check_rate_limit(username):
                st.error("Too many login attempts. Please try again later.")
                st.session_state.login_submitted = False
                return
                
            uid = db.authenticate_user(username, password)
            if uid:
                user_obj = db.get_user(uid)
                st.session_state.is_admin = user_obj.is_admin if user_obj else False

                st.success("Login successful! Redirecting...")
                # Update session state
                st.session_state.logged_in = True
                st.session_state.user_id = uid
                st.session_state.username = username
                st.session_state.current_page = "dashboard"
                login_attempts.pop(username, None)
                
                # Clear login submission flag
                st.session_state.login_submitted = False
                
                # Force rerun
                st.rerun()
            else:
                if username in login_attempts:
                    login_attempts[username].append(time.time())
                else:
                    login_attempts[username] = [time.time()]
                st.error("Invalid username or password.")
                st.session_state.login_submitted = False

# ---- دکمه‌ی خروج ----
def render_logout():
    if st.sidebar.button("Logout"):
        st.session_state.pop("user_id", None)
        st.session_state.pop("username", None)
        st.experimental_rerun()

# ---- آپلود فایل ----
def render_upload():
    return st.file_uploader("Upload Receipt Image", type=["png","jpg","jpeg"])



# ---- داشبورد هزینه‌ها ----
def render_dashboard(db, user_id):

    try:
        receipts = db.get_receipts_by_user(user_id)
        if not receipts:
            st.info("No receipts found.")
            return

        min_date = min(r.date for r in receipts)
        max_date = max(r.date for r in receipts)

        years = sorted(set(r.date.year for r in receipts), reverse=True)
        selected_year = st.selectbox("انتخاب سال", options=years, index=0)

        show_all = st.button("نمایش همه رسیدها (تمام سال‌ها)")

        if show_all:
            start_date = min_date
            end_date = max_date
            st.success(f"تمام رسیدها از {start_date.date()} تا {end_date.date()} نمایش داده می‌شود.")
        else:
            year_receipts = [r for r in receipts if r.date.year == selected_year]
            year_min = min(r.date for r in year_receipts)
            year_max = max(r.date for r in year_receipts)
            date_range = st.date_input(
                "انتخاب بازه تاریخی",
                value=(year_min.date(), year_max.date()),
                min_value=year_min.date(),
                max_value=year_max.date(),
                format="YYYY-MM-DD"
            )
            start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])

        filtered_receipts = [r for r in receipts if start_date <= r.date <= end_date]
        if not filtered_receipts:
            st.warning("در این بازه تاریخی رسیدی ثبت نشده.")
            return

        st.write("Debug: Getting items...")
        all_items = db.get_all_items_by_user(user_id)
        st.write(f"Debug: Got {len(all_items)} items")

        filtered_items = [
            item for item in all_items
            if any(item['receipt_id'] == r.id for r in filtered_receipts)
        ]
        st.write(f"Debug: Filtered to {len(filtered_items)} items")

        # آمار کارت‌ها
        total_spent = sum(r.total_amount or 0 for r in filtered_receipts)
        num_receipts = len(filtered_receipts)
        total_items = sum(float(item.get('quantity', 1)) for item in filtered_items)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(
                f"""
                <div style="background:#f0f2f6;padding:32px 10px;border-radius:16px;text-align:center;box-shadow:0 2px 6px #0001">
                    <h4>هزینه کل این بازه</h4>
                    <span style="font-size:2rem;color:#166534;font-weight:bold;">{total_spent:,.2f} $</span>
                </div>
                """, unsafe_allow_html=True
            )
        with col2:
            st.markdown(
                f"""
                <div style="background:#f0f2f6;padding:32px 10px;border-radius:16px;text-align:center;box-shadow:0 2px 6px #0001">
                    <h4>تعداد رسید</h4>
                    <span style="font-size:2rem;color:#334155;font-weight:bold;">{num_receipts}</span>
                </div>
                """, unsafe_allow_html=True
            )
        with col3:
            st.markdown(
                f"""
                <div style="background:#f0f2f6;padding:32px 10px;border-radius:16px;text-align:center;box-shadow:0 2px 6px #0001">
                    <h4>تعداد آیتم‌های خریداری‌شده</h4>
                    <span style="font-size:2rem;color:#7c3aed;font-weight:bold;">{total_items}</span>
                </div>
                """, unsafe_allow_html=True
            )

        # گران‌ترین رسید این بازه
        if filtered_receipts:
            max_receipt = max(filtered_receipts, key=lambda r: r.total_amount or 0)
            st.markdown(
                f"""
                <div style="background:#e0f2fe;padding:18px 10px;border-radius:16px;text-align:center;box-shadow:0 2px 6px #0002;margin-bottom:14px">
                    <h5 style="margin-bottom:6px;">گران‌ترین رسید این بازه</h5>
                    <span style="font-size:1.5rem;color:#be185d;font-weight:bold;">{max_receipt.total_amount:,.2f} $</span>
                    <br>
                    <span style="color:#334155;">
                        {max_receipt.store.name if hasattr(max_receipt, 'store') and max_receipt.store else '—'} | 
                        {max_receipt.date.strftime('%Y-%m-%d')}
                    </span>
                </div>
                """, unsafe_allow_html=True
            )

        # سه آیتم گران این بازه
        if filtered_items:
            items_sorted = sorted(
                filtered_items,
                key=lambda it: (float(it.get('price', 0)) * float(it.get('quantity', 1))),
                reverse=True
            )
            top_items = items_sorted[:3]
            st.markdown(
                """
                <div style="background:#ede9fe;padding:14px 10px 4px 10px;border-radius:16px;text-align:center;box-shadow:0 2px 6px #7c3aed22;margin-bottom:14px">
                    <h5 style="margin-bottom:2px;">سه آیتم گران این بازه</h5>
                </div>
                """, unsafe_allow_html=True
            )
            cols = st.columns(3)
            for i, item in enumerate(top_items):
                total_price = float(item.get('price', 0)) * float(item.get('quantity', 1))
                with cols[i]:
                    st.markdown(
                        f"""
                        <div style="background:#fff7ed;padding:20px 6px;border-radius:14px;text-align:center;box-shadow:0 1px 4px #be185d11;margin:7px 0;">
                            <b style="color:#be185d">{item.get('item_name', item.get('name'))}</b><br>
                            <span style="font-size:1.1rem;color:#7c3aed">{item.get('price', 0):,.2f} $ × {item.get('quantity', 1)}</span><br>
                            <span style="color:#334155;">جمع: <b style="color:#166534">{total_price:,.2f} $</b></span>
                        </div>
                        """, unsafe_allow_html=True
                    )

        # پرخرج‌ترین فروشگاه این بازه
        if filtered_receipts:
            df_store = pd.DataFrame([{
                "store": r.store.name if hasattr(r, 'store') and r.store else '—',
                "total": r.total_amount or 0
            } for r in filtered_receipts])
            store_summary = df_store.groupby("store")["total"].sum().reset_index()
            store_summary = store_summary.sort_values("total", ascending=False)
            if not store_summary.empty and store_summary.iloc[0]["store"] != "—":
                best_store = store_summary.iloc[0]
                st.markdown(
                    f"""
                    <div style="background:#ecfdf5;padding:18px 10px;border-radius:16px;text-align:center;box-shadow:0 2px 6px #10b98122;margin-bottom:14px">
                        <h5 style="margin-bottom:6px;">پرخرج‌ترین فروشگاه این بازه</h5>
                        <span style="font-size:1.5rem;color:#10b981;font-weight:bold;">{best_store['store']}</span>
                        <br>
                        <span style="color:#334155;">
                            جمع کل خرید: <b style="color:#be185d">{best_store['total']:,.2f} $</b>
                        </span>
                    </div>
                    """, unsafe_allow_html=True
                )

        # روند هزینه ماهانه (Line Chart)
        if filtered_receipts:
            df_months = pd.DataFrame([{
                "month": r.date.strftime("%Y-%m"),
                "total": r.total_amount or 0
            } for r in filtered_receipts])
            month_summary = df_months.groupby("month")["total"].sum().reset_index()
            month_summary = month_summary.sort_values("month")
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=month_summary["month"],
                y=month_summary["total"],
                mode='lines+markers',
                line=dict(width=3, color='#2563eb'),
                marker=dict(size=10, color='#f59e42'),
                hovertemplate='ماه: %{x}<br>هزینه: %{y:,.2f} $<extra></extra>'
            ))
            fig.update_layout(
                title="روند هزینه ماهانه",
                xaxis_title="ماه",
                yaxis_title="جمع هزینه (دلار)",
                xaxis=dict(tickangle=0),
                margin=dict(l=10, r=10, t=60, b=10),
                plot_bgcolor="#fff"
            )
            st.plotly_chart(fig, use_container_width=True)

        # نمودارها و مقایسه دسته‌بندی
        if filtered_items:
            df = pd.DataFrame([{
                "category": item.get('category', 'Unknown'),
                "amount": float(item.get('price', 0)) * float(item.get('quantity', 1))
            } for item in filtered_items])
            summary = df.groupby("category")["amount"].sum().reset_index()
            summary = summary.sort_values("amount", ascending=False)
            all_cats = list(df["category"].unique())
            if all_cats:
                cat1 = st.selectbox("دسته اول برای مقایسه", all_cats, index=0)
                cat2 = st.selectbox("دسته دوم برای مقایسه", all_cats, index=1 if len(all_cats) > 1 else 0)
                cat_summary = df.groupby("category")["amount"].sum()
                val1 = cat_summary.get(cat1, 0)
                val2 = cat_summary.get(cat2, 0)
                fig_comp = go.Figure(data=[
                    go.Bar(name=cat1, x=[cat1], y=[val1], marker_color="#ea580c", text=f"{val1:,.2f} $", textposition="auto"),
                    go.Bar(name=cat2, x=[cat2], y=[val2], marker_color="#65a30d", text=f"{val2:,.2f} $", textposition="auto"),
                ])
                fig_comp.update_layout(
                    title="مقایسه مجموع هزینه",
                    yaxis_title="جمع هزینه (دلار)",
                    xaxis_title="دسته‌بندی",
                    showlegend=False,
                    height=300,
                    margin=dict(l=10, r=10, t=50, b=10),
                    plot_bgcolor="#fff"
                )
                st.plotly_chart(fig_comp, use_container_width=True)
                # Pie Chart
                fig, ax = plt.subplots(figsize=(6, 6))
                wedges, texts, autotexts = ax.pie(
                    summary["amount"],
                    labels=summary["category"],
                    autopct='%1.1f%%',
                    startangle=140,
                    wedgeprops=dict(width=0.4, edgecolor='w'),
                    pctdistance=0.85,
                    textprops={'fontsize': 11}
                )
                centre_circle = plt.Circle((0, 0), 0.60, fc='white')
                fig.gca().add_artist(centre_circle)
                ax.set_title("Each Category", fontsize=15)
                plt.tight_layout()
                st.pyplot(fig)
            else:
                st.info("هیچ دسته‌بندی برای نمایش وجود ندارد.")
        else:
            st.info("داده‌ای برای نمایش نمودارها وجود ندارد.")

    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        logging.error(f"Dashboard error: {e}", exc_info=True)

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

def render_receipt_history(db, user_id, classifier):
    """Read and display user receipts from database in table format"""
    try:
        st.subheader("📜 Receipt History")
        
        # Get receipts
        receipts_df = db.get_receipts_by_user_df(user_id)
        
        if receipts_df is None or receipts_df.empty:
            st.info("No receipts found.")
            return

        # Convert numeric columns
        numeric_cols = ['total_amount', 'subtotal', 'tax', 'discount']
        for col in numeric_cols:
            if col in receipts_df.columns:
                receipts_df[col] = pd.to_numeric(receipts_df[col], errors='coerce').fillna(0.0)

        # Display table
        st.dataframe(
            receipts_df,
            column_config={
                "date": st.column_config.DateColumn(format="YYYY-MM-DD"),
                "total_amount": st.column_config.NumberColumn(format="$%.2f"),
                "tax": st.column_config.NumberColumn(format="$%.2f"),
                "discount": st.column_config.NumberColumn(format="$%.2f")
            },
            hide_index=True
        )

        if len(receipts_df) > 0:
            selected_id = st.selectbox(
                "Select receipt to view details:",
                options=receipts_df['id'].tolist(),
                format_func=lambda x: f"Receipt #{x} - {receipts_df[receipts_df['id']==x]['store_name'].iloc[0]} ({receipts_df[receipts_df['id']==x]['date'].iloc[0].strftime('%Y-%m-%d')})"
            )
            
            if selected_id:
                render_receipt_items_editable(db, selected_id, classifier.categories)

    except Exception as e:
        st.error(f"Error loading receipt history: {str(e)}")
        logging.error(f"Receipt history error: {e}")

def render_receipt_items_editable(db, receipt_id, categories):
    """
    An editable table for receipt items based on categories
    """
    items = db.get_items_by_receipt(receipt_id)
    st.write("📝 Edit Categories (Save to retrain your model!)")
    updates = []
    for it in items:
        # مقدار فعلی category رو به عنوان مقدار پیش‌فرض بذار
        new_cat = st.selectbox(
            f"{it.item_name} ({it.price}$)",
            categories,
            index=categories.index(it.category) if it.category in categories else 0,
            key=f"{receipt_id}_{it.id}"
        )
        updates.append({
            "id": it.id,
            "item_name": it.item_name,
            "price": it.price,
            "old_category": it.category,
            "new_category": new_cat,
        })
    if st.button("💾 Save Category Corrections"):
        for u in updates:
            if u["new_category"] != u["old_category"]:
                db.update_item_category(u["id"], u["new_category"])
                # ذخیره تغییرات در CSV مخصوص آموزش مدل:
                with open("Corrected_training_data.csv", "a", encoding="utf-8") as f:
                    f.write(f"{u['item_name']},{u['new_category']}\n")
        st.success("Categories updated!")

def render_admin_panel(db):
    st.title("🛠️ Admin Panel")
    
    try:
        users = db.get_all_users()
        if not users:
            st.warning("هیچ کاربری وجود ندارد.")
            return

        st.markdown("## 📋 لیست تمام رسیدهای کاربران")

        # جمع‌آوری داده‌ها
        data = []
        for user in users:
            receipts = db.get_receipts_by_user(user.id)
            for r in receipts:
                data.append({
                    "user": user.username,
                    "email": user.email,
                    "receipt_id": r.id,
                    "date": r.date.strftime("%Y-%m-%d %H:%M"),
                    "store": r.store.name if r.store else "—",
                    "total": r.total_amount or 0.0,
                })

        if not data:
            st.info("هیچ رسیدی ثبت نشده.")
            return

        df = pd.DataFrame(data)
        df = df.sort_values("date", ascending=False)
        df["ردیف"] = range(1, len(df) + 1)
        df = df[["ردیف", "date", "store", "total", "user", "receipt_id"]]  # ترتیب ستون‌ها
        df = df.rename(columns={
            "date": "تاریخ و ساعت",
            "store": "فروشگاه",
            "total": "مبلغ کل",
            "user": "نام کاربر",
            "receipt_id": "جزئیات رسید"
        })

        st.dataframe(df, use_container_width=True, hide_index=True)

        # انتخاب رسید برای مشاهده
        selected_id = st.selectbox(
            "🔍 انتخاب رسید برای مشاهده جزئیات:",
            options=df["جزئیات رسید"].tolist(),
            format_func=lambda x: f"رسید #{x}"
        )
        if selected_id:
            st.subheader(f"📋 جزئیات رسید #{selected_id}")
            render_single_receipt_view(db, selected_id)
    except Exception as e:
        st.error(f"خطا در بارگذاری رسیدها: {str(e)}")

def render_single_receipt_view(db, receipt_id: int):
    """نمایش جزئیات فقط یک رسید برای استفاده در پنل ادمین"""
    receipt = db.get_receipt_by_id(receipt_id)
    if not receipt:
        st.warning("رسید یافت نشد.")
        return

    store_name = receipt.store.name if receipt.store else "Unknown Store"
    date_str = receipt.date.strftime('%Y-%m-%d %H:%M') if receipt.date else "Unknown Date"
    total_amount = float(receipt.total_amount or 0)

    st.markdown(f"### 🧾 {store_name} | {date_str} | ${total_amount:.2f}")

    try:
        if not receipt.items or receipt.items.strip() in ("", "[]"):
            st.warning("هیچ آیتمی برای این رسید ثبت نشده.")
            return

        items = json.loads(receipt.items)

        df_items = pd.DataFrame([{
            "نام آیتم": item.get("name", "—"),
            "تعداد": item.get("count", 1),
            "قیمت": item.get("price", 0.0),
            "دسته": item.get("category", "—"),
            "مجموع": item.get("price", 0.0) * item.get("count", 1)
        } for item in items])

        st.dataframe(df_items, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"خطا در بارگذاری آیتم‌ها از JSON: {str(e)}")