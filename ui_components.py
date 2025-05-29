import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from typing import Dict, Any


# ---- فرم ورود/ثبت‌نام ----
def render_login(db):
    st.title("🔐 Login or Sign up")
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

    # گرفتن همه رسیدها و آیتم‌ها
    receipts = db.get_receipts_by_user(user_id)
    if not receipts:
        st.info("داده‌ای برای نمایش وجود ندارد.")
        return

    # محاسبه بازه کل رسیدها
    min_date = min(r.purchase_date for r in receipts)
    max_date = max(r.purchase_date for r in receipts)

    # انتخاب سال (لیست سال‌های موجود)
    years = sorted(set(r.purchase_date.year for r in receipts), reverse=True)
    selected_year = st.selectbox(
        "انتخاب سال",
        options=years,
        index=0
    )

    # دکمه نمایش همه سال‌ها (از اولین رسید تا آخرین)
    show_all = st.button("نمایش همه رسیدها (تمام سال‌ها)")

    if show_all:
        start_date = min_date
        end_date = max_date
        st.success(f"تمام رسیدها از {start_date.date()} تا {end_date.date()} نمایش داده می‌شود.")
    else:
        # انتخاب بازه فقط برای سال انتخاب‌شده
        year_receipts = [r for r in receipts if r.purchase_date.year == selected_year]
        year_min = min(r.purchase_date for r in year_receipts)
        year_max = max(r.purchase_date for r in year_receipts)
        date_range = st.date_input(
            "انتخاب بازه تاریخی",
            value=(year_min.date(), year_max.date()),
            min_value=year_min.date(),
            max_value=year_max.date(),
            format="YYYY-MM-DD"
        )
        start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])

    # فیلتر نهایی داده‌ها
    filtered_receipts = [
        r for r in receipts if start_date <= r.purchase_date <= end_date
    ]
    if not filtered_receipts:
        st.warning("در این بازه تاریخی رسیدی ثبت نشده.")
        return

    all_items = db.get_all_items_by_user(user_id)
    filtered_items = [
        it for it in all_items
        if any(it.receipt_id == r.id for r in filtered_receipts)
    ]

    # کارت‌ها با داده‌های فیلترشده
    total_spent = sum(r.total_amount or 0 for r in filtered_receipts)
    num_receipts = len(filtered_receipts)
    total_items = sum(it.quantity or 1 for it in filtered_items)

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

    # --- محاسبه مجموع هزینه هر ماه در بازه انتخاب شده ---

    # فرض: filtered_receipts فقط شامل رسیدهای بازه انتخابی است
    if filtered_receipts:
        df_months = pd.DataFrame([{
            "month": r.purchase_date.strftime("%Y-%m"),
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
    else:
        st.info("داده‌ای برای نمایش روند ماهانه وجود ندارد.")

    # استفاده از filtered_items به جای items
    if not filtered_items:
        st.info("داده‌ای برای نمایش وجود ندارد.")
        return

    df = pd.DataFrame([{
        "category": it.category,
        "amount": it.price * it.quantity
    } for it in filtered_items])

    summary = df.groupby("category")["amount"].sum().reset_index()
    summary = summary.sort_values("amount", ascending=False)

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
                    {max_receipt.purchase_date.strftime('%Y-%m-%d')}
                </span>
            </div>
            """, unsafe_allow_html=True
        )
    else:
        st.info("رسیدی برای نمایش وجود ندارد.")

    if filtered_items:
        # آیتم‌ها را بر اساس مبلغ کل نزولی مرتب کن
        items_sorted = sorted(
            filtered_items,
            key=lambda it: (it.price or 0) * (it.quantity or 1),
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
            total_price = (item.price or 0) * (item.quantity or 1)
            with cols[i]:
                st.markdown(
                    f"""
                    <div style="background:#fff7ed;padding:20px 6px;border-radius:14px;text-align:center;box-shadow:0 1px 4px #be185d11;margin:7px 0;">
                        <b style="color:#be185d">{item.item_name}</b><br>
                        <span style="font-size:1.1rem;color:#7c3aed">{item.price:,.2f} $ × {item.quantity}</span><br>
                        <span style="color:#334155;">جمع: <b style="color:#166534">{total_price:,.2f} $</b></span>
                    </div>
                    """, unsafe_allow_html=True
                )
    else:
        st.info("آیتمی برای نمایش وجود ندارد.")

    if filtered_receipts:
        # جمع هزینه هر فروشگاه
    
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
        else:
            st.info("فروشگاهی برای نمایش وجود ندارد.")

    # دسته‌های مورد نظر
    all_cats = list(df["category"].unique())
    cat1 = st.selectbox("دسته اول برای مقایسه", all_cats, index=all_cats.index("Snacks") if "Snacks" in all_cats else 0)
    cat2 = st.selectbox("دسته دوم برای مقایسه", all_cats, index=all_cats.index("Produce") if "Produce" in all_cats else 1)

    # جمع هزینه هر دسته
    cat_summary = df.groupby("category")["amount"].sum()
    val1 = cat_summary.get(cat1, 0)
    val2 = cat_summary.get(cat2, 0)

    st.markdown(
        f"""
        <div style="background:#fef9c3;padding:18px 10px 4px 10px;border-radius:16px;text-align:center;box-shadow:0 2px 6px #eab30833;margin-bottom:14px">
            <h5 style="margin-bottom:2px;">مقایسه هزینه دو دسته:</h5>
            <b style="color:#ea580c">{cat1}</b> vs <b style="color:#65a30d">{cat2}</b>
        </div>
        """, unsafe_allow_html=True
    )

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

    # (Pie Chart)
    fig, ax = plt.subplots(figsize=(6, 6))
    wedges, texts, autotexts = ax.pie(
        summary["amount"],
        labels=summary["category"],
        autopct='%1.1f%%',
        startangle=140,
        wedgeprops=dict(width=0.4, edgecolor='w'),  # Donut chart
        pctdistance=0.85,
        textprops={'fontsize': 11}
    )

    # Center circle for donut chart
    centre_circle = plt.Circle((0, 0), 0.60, fc='white')
    fig.gca().add_artist(centre_circle)

    # Title and formatting
    ax.set_title("Each Category", fontsize=15)
    plt.tight_layout()

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

def render_receipt_history(db, user_id, classifier):
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
        "date": "Date",
        "total": "Total",
        "store_name": "store_name"
    })
    
    st.subheader("📜 Receipt History")
    st.dataframe(df, use_container_width=True)
    

    # انتخاب یک رسید برای نمایش جزئیات
    sel = st.selectbox("Choose receipt for detail", df["ID"])
    items = db.get_items_by_receipt(sel)  # لیست آبجکت‌های Item

    # تبدیل آبجکت Item به دیکشنری
    items_list = [
        {
            "Product Name": it.item_name,
            "Price": it.price,
            "Saved Category": it.category,
            "Suggested Category": classifier.predict_category(it.item_name)
        }
        for it in items
    ]
    # تبدیل لیست به دیتافریم
    df_items = pd.DataFrame(items_list)
    df_items.insert(0, "Row", range(1, len(df_items) + 1))
    print(df_items.columns)
    

    df_items["Price"] = df_items["Price"].apply(lambda x: f"{x:.2f}")

    st.write("**Receipt Details:**")
    st.table(df_items.to_dict("records"))

    st.write("---")
    CATEGORIES = [
        "Produce", "Groceries", "Snacks", "Drinks", "Dairy",
        "Books/Magazine", "Coffee", "Clothes", "Personal Care", "Household",
        "Baby", "Pet", "Transportation", "Healthcare", "Dining out", "Entertainment",
        "Gift & Flowers", "Alcohol Drinks", "Tobacco", "Electronics", "Home Improvement", "Other"
    ]
    render_receipt_items_editable(db, sel, CATEGORIES)

def render_receipt_items_editable(db, receipt_id, categories):
    """
    یک جدول ویرایش‌پذیر برای آیتم‌های رسید بر اساس دسته‌بندی
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