##booking_adjustments.py
 
import streamlit as st
import pandas as pd
from database import get_merged_data, get_database_connection, load_df_udc
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

    # Carrega os dados da UDC
    df_udc = load_df_udc()
    farol_status_options = df_udc[df_udc["grupo"] == "Farol Status"]["dado"].dropna().unique().tolist()
    
    # Status disponíveis na UDC - Farol Status:
    # ['New request', 'Booking Requested', 'Received from Carrier', 'Booking Under Review', 
    #  'Adjustment Requested', 'Booking Approved', 'Booking Cancelled', 'Booking Rejected']

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
        if periodo_selecionado == "Today":
            hoje = datetime.now().date()
            df_original = df_original[df_original['row_inserted_date'].dt.date == hoje]
        else:
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

    # Ordena o DataFrame por farol_reference e row_inserted_date
    df_original = df_original.sort_values(['farol_reference', 'row_inserted_date'], ascending=[True, False])
    
    # Agrupa por farol_reference
    unique_farol_refs = df_original['farol_reference'].unique()

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
            st.metric("📦 Farol References", len(unique_farol_refs))
            st.markdown('</div>', unsafe_allow_html=True)
    with col3:
        with st.container():
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            pending_count = len(df_original[df_original['status'] == 'Pending'])
            st.metric("⏳ Pending Adjustments", pending_count)
            st.markdown('</div>', unsafe_allow_html=True)

    # Tabs para diferentes visualizações
    tab1, tab2 = st.tabs(["📦 Grouped by Farol Reference", "📋 List View"])
    
    with tab1:
        # Visão agrupada por Farol Reference
        for farol_ref in unique_farol_refs:
            # Filtra ajustes para este Farol Reference
            df_farol = df_original[df_original['farol_reference'] == farol_ref].copy()
            
            # Pega a primeira linha para informações gerais
            first_row = df_farol.iloc[0]
            
            # Verifica se há diferentes status dentro do mesmo Farol Reference
            statuses = df_farol['status'].unique()
            status_info = f"Status: {', '.join(statuses)}"
            
            # Cria um expander para cada Farol Reference
            with st.expander(f"🔧 {farol_ref} - {len(df_farol)} ajustes - {status_info}", expanded=False):
                
                # Mostra informações resumidas
                st.markdown(f"""
                **Area:** {first_row['area']}  
                **Stage:** {first_row['stage']}  
                **Reason:** {first_row['request_reason']}  
                **Adjustment Owner:** {first_row['adjustments_owner']}  
                **Request Date:** {first_row['row_inserted_date'].strftime('%d/%m/%Y %H:%M')}  
                **Comments:** {first_row['comments'] if pd.notna(first_row['comments']) else 'No comments'}
                """)

                # Mostra resumo das alterações
                st.markdown("**📝 Summary of Changes:**")
                
                # Cria um resumo das alterações
                changes_summary = []
                for _, row in df_farol.iterrows():
                    if row['column_name'] == 'Split':
                        changes_summary.append(f"• **Split:** New reference created with {format_value(row['new_value'])} containers")
                    else:
                        changes_summary.append(f"• **{format_column_name(row['column_name'])}:** {format_value(row['previous_value'])} → {format_value(row['new_value'])}")
                
                for change in changes_summary:
                    st.markdown(change)

                # Seleção de status para toda a Farol Reference
                col1, col2, col3 = st.columns([2, 1, 1])
                
                with col1:
                    current_status = statuses[0] if len(statuses) == 1 else "Mixed"
                    # Mapeia os status internos para os status da UDC
                    status_mapping = {
                        "Pending": "Adjustment Requested",
                        "Approved": "Booking Approved", 
                        "Rejected": "Booking Rejected"
                    }
                    
                    # Opções disponíveis do UDC filtradas para os status relevantes de ajustes
                    # Usa os status da UDC que são relevantes para ajustes
                    relevant_status = [
                        "Adjustment Requested",
                        "Booking Approved", 
                        "Booking Rejected",
                        "Booking Cancelled",
                        "Received from Carrier"
                    ]
                    
                    # Filtra apenas os status que existem na UDC
                    available_options = [status for status in relevant_status if status in farol_status_options]
                    
                    # Se nenhum status foi encontrado, usa os valores padrão
                    if not available_options:
                        available_options = relevant_status
                    
                    # Define o index baseado no status atual
                    try:
                        if current_status in available_options:
                            default_index = available_options.index(current_status)
                        elif current_status in status_mapping and status_mapping[current_status] in available_options:
                            default_index = available_options.index(status_mapping[current_status])
                        else:
                            default_index = 0
                    except (ValueError, IndexError):
                        default_index = 0
                    
                    new_status = st.selectbox(
                        "Status for all adjustments:",
                        available_options,
                        index=default_index,
                        key=f"status_{farol_ref}"
                    )
                
                with col2:
                    st.markdown("<br>", unsafe_allow_html=True)  # Espaçamento vertical
                    if st.button(f"✅ Update Status", key=f"update_{farol_ref}", use_container_width=True):
                        try:
                            conn = get_database_connection()
                            transaction = conn.begin()
                            
                            # Atualiza o status de todos os ajustes para esta Farol Reference
                            update_log_query = text("""
                                UPDATE LogTransp.F_CON_Adjustments_Log
                                SET status = :new_status,
                                    confirmation_date = :confirmation_date
                                WHERE farol_reference = :farol_reference
                            """)
                            
                            conn.execute(update_log_query, {
                                "new_status": new_status,
                                "confirmation_date": datetime.now() if new_status in ["Booking Approved", "Booking Rejected", "Booking Cancelled"] else None,
                                "farol_reference": farol_ref
                            })
                            
                            # Atualiza as tabelas principais com o novo status da UDC
                            stages = df_farol['stage'].unique()
                            
                            if "Sales Data" in stages:
                                update_sales_query = text("""
                                    UPDATE LogTransp.F_CON_SALES_DATA
                                    SET farol_status = :farol_status
                                    WHERE s_farol_reference = :farol_reference
                                """)
                                conn.execute(update_sales_query, {
                                    "farol_status": new_status,
                                    "farol_reference": farol_ref
                                })
                            
                            if "Booking Management" in stages:
                                update_booking_query = text("""
                                    UPDATE LogTransp.F_CON_BOOKING_MANAGEMENT
                                    SET farol_status = :farol_status
                                    WHERE b_farol_reference = :farol_reference
                                """)
                                conn.execute(update_booking_query, {
                                    "farol_status": new_status,
                                    "farol_reference": farol_ref
                                })
                            
                            if "Container Delivery at Port" in stages:
                                update_loading_query = text("""
                                    UPDATE LogTransp.F_CON_CARGO_LOADING_CONTAINER_RELEASE
                                    SET farol_status = :farol_status
                                    WHERE l_farol_reference = :farol_reference
                                """)
                                conn.execute(update_loading_query, {
                                    "farol_status": new_status,
                                    "farol_reference": farol_ref
                                })
                            
                            transaction.commit()
                            st.success(f"✅ Status updated successfully for {farol_ref}!")
                            st.rerun()
                            
                        except Exception as e:
                            if 'transaction' in locals():
                                transaction.rollback()
                            st.error(f"Error updating status: {str(e)}")
                        finally:
                            if 'conn' in locals():
                                conn.close()
                
                with col3:
                    st.markdown("<br>", unsafe_allow_html=True)  # Espaçamento vertical
                    if st.button("🔍 View Details", key=f"details_{farol_ref}", use_container_width=True):
                        st.session_state[f"show_details_{farol_ref}"] = not st.session_state.get(f"show_details_{farol_ref}", False)
                
                # Mostra detalhes se solicitado
                if st.session_state.get(f"show_details_{farol_ref}", False):
                    st.markdown("**📋 Individual Adjustments Details:**")
                    st.dataframe(
                        df_farol[['column_name', 'previous_value', 'new_value', 'status', 'stage']],
                        column_config={
                            "column_name": "Field",
                            "previous_value": "Previous Value",
                            "new_value": "New Value",
                            "status": "Status",
                            "stage": "Stage"
                        },
                        use_container_width=True,
                        hide_index=True
                    )
    
    with tab2:
        # Visão em lista
        st.dataframe(
            df_original,
            column_config={
                "farol_reference": "Farol Reference",
                "status": "Status",
                "column_name": "Field Changed",
                "previous_value": "Previous Value",
                "new_value": "New Value",
                "area": "Area",
                "stage": "Stage",
                "request_reason": "Reason",
                "adjustments_owner": "Owner",
                "row_inserted_date": "Request Date"
            },
            use_container_width=True
        )

    # Botão para voltar para Home
    if st.button("🔙 Back to Shipments"):
        st.session_state["navigate_to"] = "Shipments"
        st.rerun()

if __name__ == "__main__":
    exibir_adjustments()
 