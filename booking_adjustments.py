##booking_adjustments.py
 
import streamlit as st
import pandas as pd
from database import get_merged_data
 
def exibir_adjustments():
    st.title("📋 Adjustment Request Management")
 
    df_original = get_merged_data()
 
    if df_original.empty:
        st.info("No adjustment requests found.")
    else:
        st.markdown("### Registered Adjustments")
 
        df_original = df_original.drop(columns=["ID Sales"], errors="ignore")
 
        df_original["Status"] = df_original["Status"].fillna("Pending")
        df_original["Shipment Status"] = df_original["Shipment Status"].fillna("Adjustment requested")
 
        # Cópia para detectar mudanças após edição
        df_before_edit = df_original.copy()
 
        edited_df = st.data_editor(
            df_original,
            column_config={
                "ajuste": st.column_config.TextColumn("Adjustment Details", width="large", disabled=True),
                "row_inserted_date": st.column_config.DateColumn("Request Date", format="DD/MM/YYYY", disabled=True),
                "Status": st.column_config.SelectboxColumn(
                    "Status",
                    options=["Pending", "Completed", "Cancelled"]
                ),
                "Shipment Status": st.column_config.SelectboxColumn(
                    "Shipment Status",
                    options=[
                        "New request",
                        "New adjustment",
                        "Booking requested",
                        "Adjustment requested",
                        "Received from carrier",
                        "Approved",
                        "Cancelled",
                        "Rejected",
                        "Shipped",
                        "Arrived at destination"
                    ]
                ),
                "Booking Adjustment Request Date": st.column_config.DatetimeColumn(
                    "Adjustment Request Date", format="DD/MM/YYYY HH:mm"
                ),
                "Booking Adjustment Confirmation Date": st.column_config.DatetimeColumn(
                    "Adjustment Confirmation Date", format="DD/MM/YYYY HH:mm"
                )
            },
            use_container_width=True,
            hide_index=True
        )
 
        # Aplica as regras com base nas edições
        for i in range(len(edited_df)):
            date_before = df_before_edit.loc[i, "Booking Adjustment Request Date"]
            date_after = edited_df.loc[i, "Booking Adjustment Request Date"]
 
            status_before = df_before_edit.loc[i, "Shipment Status"]
            status_after = edited_df.loc[i, "Shipment Status"]
 
            # Regra 1: Se a data de ajuste foi alterada, muda o status para "Adjustment requested"
            if pd.notna(date_after) and date_before != date_after:
                edited_df.loc[i, "Shipment Status"] = "Adjustment requested"
 
            # Regra 2: Se o status foi alterado para algo diferente de "Adjustment requested", limpa a data
            if status_after != "Adjustment requested" and status_before != status_after:
                edited_df.loc[i, "Booking Adjustment Request Date"] = pd.NaT
 
        # Botões
        col_btn1, col_btn2, col_btn3 = st.columns(3)
 
        with col_btn1:
            st.button("✅ Confirm")
 
        with col_btn2:
            st.button("🗑️ Discard Changes")
 
        with col_btn3:
            st.button("🔙 Back to Home")
 