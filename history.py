import streamlit as st
import pandas as pd
from database import get_return_carriers_by_farol, get_return_carriers_recent
from shipments_mapping import get_column_mapping

def exibir_history():
    st.title("📜 Return Carriers History")

    farol_reference = st.session_state.get("selected_reference")
    if not farol_reference:
        st.info("Selecione uma linha em Shipments para visualizar o histórico.")
        col = st.columns(1)[0]
        with col:
            if st.button("🔙 Back to Shipments"):
                st.session_state["current_page"] = "main"
                st.rerun()
        return

    st.subheader(f"Farol Reference: {farol_reference}")

    df = get_return_carriers_by_farol(farol_reference)
    if df.empty:
        st.info("Nenhum registro para esta referência. Exibindo registros recentes:")
        df = get_return_carriers_recent(limit=200)
        if df.empty:
            st.warning("A tabela F_CON_RETURN_CARRIERS está vazia.")
            col = st.columns(1)[0]
            with col:
                if st.button("🔙 Back to Shipments"):
                    st.session_state["current_page"] = "main"
                    st.rerun()
            return

    # Métricas rápidas
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Status", str(df.iloc[0].get("B_BOOKING_STATUS", "-")))
    with c2:
        st.metric("Voyage Carrier", str(df.iloc[0].get("B_VOYAGE_CARRIER", "-")))
    with c3:
        st.metric("Containers", int(df.iloc[0].get("S_QUANTITY_OF_CONTAINERS", 0) or 0))
    with c4:
        st.metric("Inserted", str(df.iloc[0].get("ROW_INSERTED_DATE", "-")))

    st.markdown("---")

    # Grade principal com colunas relevantes
    display_cols = [
        "FAROL_REFERENCE",
        "B_BOOKING_STATUS",
        "S_SPLITTED_BOOKING_REFERENCE",
        "S_PLACE_OF_RECEIPT",
        "S_QUANTITY_OF_CONTAINERS",
        "S_PORT_OF_LOADING_POL",
        "S_PORT_OF_DELIVERY_POD",
        "S_FINAL_DESTINATION",
        "B_TRANSHIPMENT_PORT",
        "B_PORT_TERMINAL_CITY",
        "B_VESSEL_NAME",
        "B_VOYAGE_CARRIER",
        "B_DOCUMENT_CUT_OFF_DOCCUT",
        "B_PORT_CUT_OFF_PORTCUT",
        "B_ESTIMATED_TIME_OF_DEPARTURE_ETD",
        "B_ESTIMATED_TIME_OF_ARRIVAL_ETA",
        "B_GATE_OPENING",
        "P_STATUS",
        "P_PDF_NAME",
        "ROW_INSERTED_DATE",
        "USER_INSERT",
    ]

    df_show = df[[c for c in display_cols if c in df.columns]].copy()

    # Aplica aliases iguais aos da grade principal quando disponíveis
    mapping_main = get_column_mapping()
    mapping_upper = {k.upper(): v for k, v in mapping_main.items()}

    def prettify(col: str) -> str:
        # Fallback: transforma COL_NAME -> Col Name e normaliza acrônimos
        label = col.replace("_", " ").title()
        # Normaliza acrônimos comuns
        replaces = {
            "Pol": "POL",
            "Pod": "POD",
            "Etd": "ETD",
            "Eta": "ETA",
            "Pdf": "PDF",
            "Id": "ID",
        }
        for k, v in replaces.items():
            label = label.replace(k, v)
        return label

    custom_overrides = {
        "FAROL_REFERENCE": "Farol Reference",
        "B_BOOKING_STATUS": "Booking Status",
        "ROW_INSERTED_DATE": "Inserted Date",
        "USER_INSERT": "Inserted By",
        # Remover prefixos B_/P_ dos rótulos solicitados
        "B_GATE_OPENING": "Gate Opening",
        "P_STATUS": "Status",
        "P_PDF_NAME": "PDF Name",
    }

    rename_map = {}
    for col in df_show.columns:
        rename_map[col] = custom_overrides.get(col, mapping_upper.get(col, prettify(col)))

    df_show.rename(columns=rename_map, inplace=True)
    st.dataframe(df_show, use_container_width=True, hide_index=True)

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔙 Back to Shipments"):
            st.session_state["current_page"] = "main"
            st.rerun()
    with col2:
        st.download_button("⬇️ Export CSV", data=df_show.to_csv(index=False).encode("utf-8"), file_name=f"return_carriers_{farol_reference}.csv", mime="text/csv")