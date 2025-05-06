# ui_components.py
import streamlit as st
import pandas as pd
from typing import Dict, Any

def render_items_table(items: Dict[str, Any]):
    df = pd.DataFrame([
        {"Item": k, **v}
        for k, v in items.items()
    ])
    df.index += 1
    st.subheader("📋 Items")
    st.dataframe(df, use_container_width=True)

def render_summary(total: float, tax: float | None, discount: float | None):
    st.subheader("💰 Summary:")
    st.markdown(f"- Total: ${total:.2f}")
    if tax:
        st.markdown(f"- Tax: ${tax:.2f}")
    if discount:
        st.markdown(f"- Discount: ${discount:.2f}")
