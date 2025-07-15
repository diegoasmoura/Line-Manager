##booking_adjustments.py
 
import streamlit as st
import pandas as pd
from database import get_merged_data, get_database_connection
from sqlalchemy import text
from datetime import datetime, timedelta
 
def format_column_name(col_name):
    """Formata o nome da coluna para um formato mais amigável."""
    column_map = {
        "Sales Quantity of Containers": "Quantidade de Containers",
        "Sales Port of Loading POL": "Porto de Origem (POL)",
        "Sales Port of Delivery POD": "Porto de Destino (POD)",
        "Sales Place of Receipt": "Local de Recebimento",
        "Sales Final Destination": "Destino Final",
        "Split": "Split de Embarque",
        "Carrier": "Transportadora",
        "Requested Cut off Start Date": "Data Inicial de Cut-off",
        "Requested Cut off End Date": "Data Final de Cut-off",
        "Required Arrival Date": "Data de Chegada Requerida"
    }
    return column_map.get(col_name, col_name)

def format_value(value):
    """Formata o valor para exibição mais amigável."""
    if pd.isna(value) or value == "" or value is None:
        return "Não informado"
    return str(value)

def exibir_adjustments():
    st.title("📋 Adjustment Request Management")

    # Carrega os dados dos ajustes
    df_original = get_merged_data()

    if df_original.empty:
        st.info("No adjustment requests found.")
        return

    # Trata valores nulos nas colunas de filtro
    df_original['status'] = df_original['status'].fillna("Pending")
    df_original['area'] = df_original['area'].fillna("Not Specified")
    df_original['stage'] = df_original['stage'].fillna("Not Specified")

    # Seção de Filtros
    with st.expander("🔍 Search Filters", expanded=True):
        # Primeira linha: Period e Search
        col1, col2 = st.columns(2)
        
        with col1:
            # Filtro por período
            st.subheader("Period")
            periodo_opcoes = {
                "Today": 0,
                "Last 7 days": 7,
                "Last 30 days": 30,
                "All": -1
            }
            periodo_selecionado = st.radio("", list(periodo_opcoes.keys()), horizontal=True)
        
        with col2:
            # Campo de busca
            st.subheader("Search by Farol Reference")
            st.text_input("", key="busca", label_visibility="collapsed")

        # Linha separadora
        
        # Segunda linha: Status, Area e Stage
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.subheader("Status")
            status_opcoes = ["All"] + sorted(df_original['status'].unique().tolist())
            status_selecionado = st.selectbox("", status_opcoes, label_visibility="collapsed")
        
        with col2:
            st.subheader("Area")
            area_opcoes = ["All"] + sorted(df_original['area'].unique().tolist())
            area_selecionada = st.selectbox("", area_opcoes, label_visibility="collapsed")
        
        with col3:
            st.subheader("Stage")
            stage_opcoes = ["All"] + sorted(df_original['stage'].unique().tolist())
            stage_selecionado = st.selectbox("", stage_opcoes, label_visibility="collapsed")

    # Aplica os filtros
    if periodo_opcoes[periodo_selecionado] >= 0:
        data_limite = datetime.now() - timedelta(days=periodo_opcoes[periodo_selecionado])
        df_original = df_original[df_original['row_inserted_date'] >= data_limite]
    
    if status_selecionado != "All":
        df_original = df_original[df_original['status'] == status_selecionado]
    
    if area_selecionada != "All":
        df_original = df_original[df_original['area'] == area_selecionada]
    
    if stage_selecionado != "All":
        df_original = df_original[df_original['stage'] == stage_selecionado]
    
    if st.session_state.busca:
        df_original = df_original[df_original['farol_reference'].str.contains(st.session_state.busca, case=False)]

    # Ordena o DataFrame por adjustment_id e row_inserted_date
    df_original = df_original.sort_values(['adjustment_id', 'row_inserted_date'], ascending=[True, False])
    
    # Agrupa apenas para obter adjustment_ids únicos
    unique_adjustments = df_original['adjustment_id'].unique()

    # Mostra contadores em cards


    col1, col2, col3 = st.columns(3)
    with col1:
        with st.container():
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("📊 Total Adjustments", len(df_original))
            st.markdown('</div>', unsafe_allow_html=True)
    with col2:
        with st.container():
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.metric("📦 Unique Requests", len(unique_adjustments))
            st.markdown('</div>', unsafe_allow_html=True)
    with col3:
        with st.container():
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            pending_count = len(df_original[df_original['status'] == 'Pending'])
            st.metric("⏳ Pending Adjustments", pending_count)
            st.markdown('</div>', unsafe_allow_html=True)

    # Tabs para diferentes visualizações
    tab1, tab2 = st.tabs(["📦 Grouped View", "📋 List View"])
    
    with tab1:
        # Visão agrupada por Adjustment ID
        for adj_id in unique_adjustments:
            # Filtra ajustes para este Adjustment ID
            df_adjustment = df_original[df_original['adjustment_id'] == adj_id].copy()
            
            # Pega a primeira linha para informações gerais
            first_row = df_adjustment.iloc[0]
            
            # Ordena o DataFrame pelo Farol Reference
            def sort_farol_reference(x):
                try:
                    base, seq = x.rsplit('.', 1)
                    return (base, float(seq))
                except ValueError:
                    return (x, 0)
            
            df_adjustment = df_adjustment.sort_values('farol_reference', key=lambda x: [sort_farol_reference(str(val)) for val in x])

            # Cria um expander para cada Adjustment ID
            with st.expander(f"📦 Affected Farol References: {', '.join(df_adjustment['farol_reference'].unique())}", expanded=False):
                # Mostra informações resumidas
                st.markdown(f"""
                **Area:** {first_row['area']}  
                **Stage:** {first_row['stage']}  
                **Reason:** {first_row['request_reason']}  
                **Adjustment Owner:** {first_row['adjustments_owner']}  
                **Request Date:** {first_row['row_inserted_date'].strftime('%d/%m/%Y %H:%M')}  
                **Number of Adjustments:** {len(df_adjustment)}
                """)

                # Adiciona indicadores visuais de status
                status_colors = {
                    "Pending": "🟡",
                    "Approved": "🟢",
                    "Rejected": "🔴"
                }
                
                # Formata os detalhes do ajuste para cada linha
                df_adjustment['detalhes_formatados'] = df_adjustment.apply(
                    lambda row: f"""
                    📝 Changed Field: {format_column_name(row['column_name'])}
                    ⬅️ Previous Value: {format_value(row['previous_value'])}
                    ➡️ New Value: {format_value(row['new_value'])}
                    """,
                    axis=1
                )

                # Configuração do editor de dados para este Adjustment ID
                edited_df = st.data_editor(
                    df_adjustment,
                    column_config={
                        "farol_reference": st.column_config.TextColumn(
                            "Farol Reference",
                            width="dynamic",
                            disabled=True
                        ),
                        "status": st.column_config.SelectboxColumn(
                            "Status",
                            width="dynamic",
                            options=["Pending", "Approved", "Rejected"]
                        ),
                        "detalhes_formatados": st.column_config.TextColumn(
                            "Adjustment Details",
                            width="dynamic",
                            disabled=True,
                            help="Details of the requested changes in this adjustment"
                        )
                    },
                    hide_index=True,
                    column_order=[
                        "farol_reference", "status", "detalhes_formatados"
                    ],
                    use_container_width=True
                )

                # Detecta mudanças no Status para este Adjustment ID
                if not df_adjustment.equals(edited_df):
                    changes = []
                    for i, row in edited_df.iterrows():
                        if row['status'] != df_adjustment.loc[i, 'status']:
                            changes.append({
                                "farol_reference": row['farol_reference'],
                                "adjustment_id": row['adjustment_id'],
                                "new_status": row['status'],
                                "confirmation_date": datetime.now() if row['status'] in ["Approved", "Rejected"] else None,
                                "stage": row['stage']
                            })
                    
                    if changes:
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button(f"✅ Confirm Changes - {adj_id[:8]}"):
                                try:
                                    conn = get_database_connection()
                                    transaction = conn.begin()
                                    
                                    for change in changes:
                                        # Atualiza o status na tabela de log
                                        update_log_query = text("""
                                            UPDATE LogTransp.F_CON_Adjustments_Log
                                            SET status = :new_status,
                                                confirmation_date = :confirmation_date
                                            WHERE farol_reference = :farol_reference
                                            AND adjustment_id = :adjustment_id
                                        """)
                                        
                                        conn.execute(update_log_query, change)
                                        
                                        # Se aprovado, atualiza as tabelas principais
                                        if change["new_status"] == "Approved":
                                            if change["stage"] == "Sales Data":
                                                update_sales_query = text("""
                                                    UPDATE LogTransp.F_CON_SALES_DATA
                                                    SET s_shipment_status = 'Approved'
                                                    WHERE s_farol_reference = :farol_reference
                                                """)
                                                conn.execute(update_sales_query, {"farol_reference": change["farol_reference"]})
                                                
                                            elif change["stage"] == "Booking Management":
                                                update_booking_query = text("""
                                                    UPDATE LogTransp.F_CON_BOOKING_MANAGEMENT
                                                    SET b_booking_status = 'Approved'
                                                    WHERE b_farol_reference = :farol_reference
                                                """)
                                                conn.execute(update_booking_query, {"farol_reference": change["farol_reference"]})
                                                
                                            elif change["stage"] == "Container Delivery at Port":
                                                update_loading_query = text("""
                                                    UPDATE LogTransp.F_CON_CARGO_LOADING_CONTAINER_RELEASE
                                                    SET l_truck_loading_status = 'Approved'
                                                    WHERE l_farol_reference = :farol_reference
                                                """)
                                                conn.execute(update_loading_query, {"farol_reference": change["farol_reference"]})
                                    
                                    transaction.commit()
                                    st.success(f"✅ Changes for request {adj_id[:8]} saved successfully!")
                                    st.rerun()
                                    
                                except Exception as e:
                                    if 'transaction' in locals():
                                        transaction.rollback()
                                    st.error(f"Error saving changes: {str(e)}")
                                finally:
                                    if 'conn' in locals():
                                        conn.close()
                        
                        with col2:
                            if st.button(f"🗑️ Discard Changes - {adj_id[:8]}"):
                                st.rerun()
    
    with tab2:
        # Visão em lista
        st.dataframe(
            df_original,
            column_config={
                "farol_reference": "Referência Farol",
                "status": "Status",
                "column_name": "Campo Alterado",
                "previous_value": "Valor Anterior",
                "new_value": "Novo Valor"
            },
            use_container_width=True
        )

    # Botão para voltar para Home
    if st.button("🔙 Back to Shipments"):
        st.session_state["current_page"] = "main"
        st.rerun()

if __name__ == "__main__":
    exibir_adjustments()
 