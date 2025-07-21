##booking_adjustments.py
# 
# ✅ FUNCIONALIDADE: Adjusted Data View (substituindo List View)
# Esta aba mostra os dados da F_CON_SALES_DATA já com os ajustes aplicados,
# simulando como ficaram após os splits/alterações solicitados no shipments_split.py
# 
# Funcionalidades implementadas:
# - Exibição dos dados ajustados com as mesmas colunas do shipments_split.py
# - Tabela editável (st.data_editor) com coluna "Status" editável diretamente na grade
# - Coluna "Status" posicionada após "Farol Reference" para melhor visibilidade
# - Status padrão "Adjustment Requested" (SEM opção em branco no dropdown)
# - Normalização robusta: Remove opções vazias/None/strings vazias do SelectboxColumn
# - Coluna "Changes Made" com resumo das alterações (📝 campos alterados, 🔧 splits)  
# - Coluna "Comments" exibindo comentários informados na tela shipments_split.py
# - Coluna "Adjustment ID" para rastreabilidade
# - Detecção automática de mudanças no status com confirmação antes de aplicar
# - Opções de status integradas com UDC (SelectboxColumn) sempre com "Adjustment Requested" primeiro
# - Botões "Apply Changes" e "Cancel Changes" para controle das alterações
# - Atualização em lote das tabelas principais (Sales, Booking, Loading)
# - Todas as colunas são read-only exceto "Status" para edição segura
# - View Details na aba Grouped mostra dados ajustados + seção técnica (sem expanders aninhados)
# 
import streamlit as st
import pandas as pd
from database import get_merged_data, get_database_connection, load_df_udc
from sqlalchemy import text
from datetime import datetime, timedelta

def get_original_sales_data(farol_reference):
    """Busca os dados originais da F_CON_SALES_DATA para um farol reference específico."""
    conn = get_database_connection()
    try:
        query = """
        SELECT 
            s_farol_reference,
            s_quantity_of_containers,
            s_port_of_loading_pol,
            s_port_of_delivery_pod,
            s_place_of_receipt,
            s_final_destination,
            s_carrier,
            s_requested_deadlines_start_date,
            s_requested_deadlines_end_date,
            s_required_arrival_date
        FROM LogTransp.F_CON_SALES_DATA
        WHERE s_farol_reference = :ref
        """
        result = conn.execute(text(query), {"ref": farol_reference}).mappings().fetchone()
        return dict(result) if result else None
    finally:
        conn.close()

def apply_adjustments_to_data(original_data, adjustments_df):
    """Aplica os ajustes aos dados originais e retorna os dados ajustados."""
    if original_data is None:
        return None
    
    # Cria uma cópia dos dados originais
    adjusted_data = original_data.copy()
    
    # Mapeia as colunas do log para as colunas da base de dados
    column_mapping = {
        "Sales Quantity of Containers": "s_quantity_of_containers",
        "Sales Port of Loading POL": "s_port_of_loading_pol", 
        "Sales Port of Delivery POD": "s_port_of_delivery_pod",
        "Sales Place of Receipt": "s_place_of_receipt",
        "Sales Final Destination": "s_final_destination",
        "Carrier": "s_carrier",
        "Requested Cut off Start Date": "s_requested_deadlines_start_date",
        "Requested Cut off End Date": "s_requested_deadlines_end_date",
        "Required Arrival Date": "s_required_arrival_date"
    }
    
    # Aplica cada ajuste
    for _, adjustment in adjustments_df.iterrows():
        column_name = adjustment['column_name']
        new_value = adjustment['new_value']
        
        # Mapeia o nome da coluna do log para o nome na base
        db_column = column_mapping.get(column_name)
        if db_column and db_column in adjusted_data:
            # Converte o valor conforme necessário
            if db_column == "s_quantity_of_containers":
                try:
                    adjusted_data[db_column] = int(new_value) if new_value and new_value != "" else 0
                except (ValueError, TypeError):
                    adjusted_data[db_column] = 0
            elif "date" in db_column.lower():
                # Para campos de data, mantém como string ou tenta converter
                adjusted_data[db_column] = new_value
            else:
                adjusted_data[db_column] = new_value
    
    return adjusted_data

def generate_changes_summary(adjustments_df, farol_ref):
    """
    Gera um resumo das alterações feitas para uma referência específica.
    
    Formato de retorno:
    - Para splits: "🔧 Split: X containers"  
    - Para alterações: "📝 Campo: Valor Anterior → Novo Valor"
    - Múltiplas alterações separadas por " | "
    """
    ref_adjustments = adjustments_df[adjustments_df['farol_reference'] == farol_ref]
    
    changes_list = []
    for _, adj in ref_adjustments.iterrows():
        column_name = adj['column_name']
        previous_value = adj['previous_value']
        new_value = adj['new_value']
        
        # Formata o valor anterior e novo
        prev_val = str(previous_value) if pd.notna(previous_value) and previous_value != "" else "Não informado"
        new_val = str(new_value) if pd.notna(new_value) and new_value != "" else "Não informado"
        
        if column_name == 'Split':
            changes_list.append(f"🔧 Split: {new_val} containers")
        else:
            field_name = format_column_name(column_name)
            changes_list.append(f"📝 {field_name}: {prev_val} → {new_val}")
    
    return " | ".join(changes_list) if changes_list else "Nenhuma alteração detectada"

def get_adjusted_sales_data(farol_references, adjustments_df):
    """Busca dados originais e aplica ajustes para múltiplas referências."""
    adjusted_records = []
    
    for farol_ref in farol_references:
        # Busca dados originais
        original_data = get_original_sales_data(farol_ref)
        
        if original_data:
            # Filtra ajustes para esta referência
            ref_adjustments = adjustments_df[adjustments_df['farol_reference'] == farol_ref]
            
            # Pega o adjustment_id (assume que é o mesmo para toda a referência)
            adjustment_id = ref_adjustments['adjustment_id'].iloc[0] if not ref_adjustments.empty else ""
            
            # Pega os comentários da solicitação
            comments = ref_adjustments['comments'].iloc[0] if not ref_adjustments.empty and 'comments' in ref_adjustments.columns else ""
            comments = comments if pd.notna(comments) and comments != "" else "Nenhum comentário"
            
            # Pega o status atual e normaliza para "Adjustment Requested" por padrão
            if not ref_adjustments.empty:
                current_status = ref_adjustments['status'].iloc[0]
                # Normaliza status vazios, nulos ou "Pending" para "Adjustment Requested"
                if pd.isna(current_status) or current_status == "" or current_status == "Pending":
                    current_status = "Adjustment Requested"
            else:
                current_status = "Adjustment Requested"
            
            # Gera resumo das alterações
            changes_summary = generate_changes_summary(adjustments_df, farol_ref)
            
            # Verifica se há splits (ajustes do tipo "Split")
            split_adjustments = ref_adjustments[ref_adjustments['column_name'] == 'Split']
            regular_adjustments = ref_adjustments[ref_adjustments['column_name'] != 'Split']
            
            # Aplica ajustes regulares primeiro
            adjusted_data = apply_adjustments_to_data(original_data, regular_adjustments)
            
            if adjusted_data:
                # Se há splits, cria registros para cada split
                if not split_adjustments.empty:
                    for _, split_adj in split_adjustments.iterrows():
                        split_record = {
                            "Sales Farol Reference": split_adj['farol_reference'],
                            "Status": current_status,
                            "Sales Quantity of Containers": int(split_adj['new_value']) if split_adj['new_value'] else 0,
                            "Sales Port of Loading POL": adjusted_data["s_port_of_loading_pol"],
                            "Sales Port of Delivery POD": adjusted_data["s_port_of_delivery_pod"], 
                            "Sales Place of Receipt": adjusted_data["s_place_of_receipt"],
                            "Sales Final Destination": adjusted_data["s_final_destination"],
                            "Carrier": adjusted_data["s_carrier"],
                            "Requested Cut off Start Date": adjusted_data["s_requested_deadlines_start_date"],
                            "Requested Cut off End Date": adjusted_data["s_requested_deadlines_end_date"],
                            "Required Arrival Date": adjusted_data["s_required_arrival_date"],
                            "Changes Made": changes_summary,
                            "Comments": comments,
                            "Adjustment ID": adjustment_id
                        }
                        adjusted_records.append(split_record)
                else:
                    # Se não há splits, cria registro normal
                    display_record = {
                        "Sales Farol Reference": adjusted_data["s_farol_reference"],
                        "Status": current_status,
                        "Sales Quantity of Containers": adjusted_data["s_quantity_of_containers"],
                        "Sales Port of Loading POL": adjusted_data["s_port_of_loading_pol"],
                        "Sales Port of Delivery POD": adjusted_data["s_port_of_delivery_pod"], 
                        "Sales Place of Receipt": adjusted_data["s_place_of_receipt"],
                        "Sales Final Destination": adjusted_data["s_final_destination"],
                        "Carrier": adjusted_data["s_carrier"],
                        "Requested Cut off Start Date": adjusted_data["s_requested_deadlines_start_date"],
                        "Requested Cut off End Date": adjusted_data["s_requested_deadlines_end_date"],
                        "Required Arrival Date": adjusted_data["s_required_arrival_date"],
                        "Changes Made": changes_summary,
                        "Comments": comments,
                        "Adjustment ID": adjustment_id
                    }
                    adjusted_records.append(display_record)
    
    return pd.DataFrame(adjusted_records) if adjusted_records else pd.DataFrame()

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

    # Trata valores nulos nas colunas de filtro e normaliza status
    df_original['status'] = df_original['status'].fillna("Adjustment Requested")
    # Normaliza qualquer status vazio ou "Pending" para "Adjustment Requested"
    df_original['status'] = df_original['status'].apply(
        lambda x: "Adjustment Requested" if pd.isna(x) or x == "" or x == "Pending" or x is None else x
    )
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

    # Tabs para diferentes visualizações - Adjusted Data View como aba principal
    tab1, tab2 = st.tabs(["🔧 Adjusted Data View", "📦 Grouped by Farol Reference"])
    
    with tab1:
        # Nova aba: Visão de dados ajustados (substituindo List View)
        if not df_original.empty:
            # Gera os dados ajustados
            df_adjusted = get_adjusted_sales_data(unique_farol_refs, df_original)
            
            # Normaliza status vazios no DataFrame final antes de exibir
            if not df_adjusted.empty and 'Status' in df_adjusted.columns:
                df_adjusted['Status'] = df_adjusted['Status'].apply(
                    lambda x: "Adjustment Requested" if pd.isna(x) or x == "" or x is None or str(x).strip() == "" else x
                )
            
            if not df_adjusted.empty:
                # Obtém as opções de status da UDC
                farol_status_options = df_udc[df_udc["grupo"] == "Farol Status"]["dado"].dropna().unique().tolist()
                relevant_status = [
                    "Adjustment Requested",  # Status padrão sempre primeiro
                    "Booking Approved", 
                    "Booking Rejected",
                    "Booking Cancelled",
                    "Received from Carrier"
                ]
                # Filtra apenas os status que existem na UDC, mantendo a ordem
                available_options = [status for status in relevant_status if status in farol_status_options]
                if not available_options:
                    available_options = relevant_status
                
                # Garante que "Adjustment Requested" esteja sempre disponível e seja o primeiro
                if "Adjustment Requested" not in available_options:
                    available_options.insert(0, "Adjustment Requested")
                elif available_options[0] != "Adjustment Requested":
                    # Move "Adjustment Requested" para o início se não estiver
                    available_options.remove("Adjustment Requested")
                    available_options.insert(0, "Adjustment Requested")
                
                # Remove qualquer opção vazia ou None que possa estar na lista - MÚLTIPLAS VERIFICAÇÕES
                available_options = [opt for opt in available_options if opt and str(opt).strip() and opt != "" and opt != " " and not pd.isna(opt) and opt is not None]
                
                # Garante que sempre temos pelo menos "Adjustment Requested" se a lista ficar vazia
                if not available_options:
                    available_options = ["Adjustment Requested"]
                
                # Exibe a tabela editável com os dados ajustados
                edited_df = st.data_editor(
                    df_adjusted,
                    column_config={
                        "Sales Farol Reference": st.column_config.TextColumn("Farol Reference", width="medium", disabled=True),
                        "Status": st.column_config.SelectboxColumn("Status", width="medium", options=available_options, default="Adjustment Requested"),
                        "Sales Quantity of Containers": st.column_config.NumberColumn("Quantity", format="%d", disabled=True),
                        "Sales Port of Loading POL": st.column_config.TextColumn("POL", width="medium", disabled=True),
                        "Sales Port of Delivery POD": st.column_config.TextColumn("POD", width="medium", disabled=True),
                        "Sales Place of Receipt": st.column_config.TextColumn("Place of Receipt", width="medium", disabled=True),
                        "Sales Final Destination": st.column_config.TextColumn("Final Destination", width="medium", disabled=True),
                        "Carrier": st.column_config.TextColumn("Carrier", width="medium", disabled=True),
                        "Requested Cut off Start Date": st.column_config.DateColumn("Cut-off Start", disabled=True),
                        "Requested Cut off End Date": st.column_config.DateColumn("Cut-off End", disabled=True),
                        "Required Arrival Date": st.column_config.DateColumn("Required Arrival", disabled=True),
                        "Changes Made": st.column_config.TextColumn("Changes Made", width="large", disabled=True),
                        "Comments": st.column_config.TextColumn("Comments", width="large", disabled=True),
                        "Adjustment ID": st.column_config.TextColumn("Adjustment ID", width="medium", disabled=True)
                    },
                    use_container_width=True,
                    hide_index=True,
                    key="adjusted_data_editor"
                )
                
                # Detecta mudanças no status e aplica atualizações
                status_changes = []
                for i in range(len(df_adjusted)):
                    original_status = df_adjusted.iloc[i]['Status']
                    new_status = edited_df.iloc[i]['Status']
                    farol_ref = df_adjusted.iloc[i]['Sales Farol Reference']
                    
                    if original_status != new_status:
                        status_changes.append({
                            'farol_reference': farol_ref,
                            'old_status': original_status,
                            'new_status': new_status
                        })
                
                # Aplica as mudanças de status se houver
                if status_changes:
                    st.markdown("---")
                    st.markdown("### 🔄 Status Changes Detected")
                    
                    for change in status_changes:
                        st.info(f"**{change['farol_reference']}**: {change['old_status']} → {change['new_status']}")
                    
                    col1, col2 = st.columns([1, 4])
                    with col1:
                        if st.button("✅ Apply Changes", key="apply_status_changes", use_container_width=True):
                            success_count = 0
                            error_count = 0
                            
                            for change in status_changes:
                                try:
                                    conn = get_database_connection()
                                    transaction = conn.begin()
                                    
                                    # Atualiza o status nos ajustes
                                    update_log_query = text("""
                                        UPDATE LogTransp.F_CON_Adjustments_Log
                                        SET status = :new_status,
                                            confirmation_date = :confirmation_date
                                        WHERE farol_reference = :farol_reference
                                    """)
                                    
                                    conn.execute(update_log_query, {
                                        "new_status": change['new_status'],
                                        "confirmation_date": datetime.now() if change['new_status'] in ["Booking Approved", "Booking Rejected", "Booking Cancelled"] else None,
                                        "farol_reference": change['farol_reference']
                                    })
                                    
                                    # Determina os stages dos ajustes para esta referência
                                    stages_query = text("""
                                        SELECT DISTINCT stage 
                                        FROM LogTransp.F_CON_Adjustments_Log 
                                        WHERE farol_reference = :farol_reference
                                    """)
                                    stages_result = conn.execute(stages_query, {"farol_reference": change['farol_reference']}).fetchall()
                                    stages = [row[0] for row in stages_result]
                                    
                                    # Atualiza o status nas tabelas principais
                                    if "Sales Data" in stages:
                                        update_sales_query = text("""
                                            UPDATE LogTransp.F_CON_SALES_DATA
                                            SET farol_status = :farol_status
                                            WHERE s_farol_reference = :farol_reference
                                        """)
                                        conn.execute(update_sales_query, {
                                            "farol_status": change['new_status'],
                                            "farol_reference": change['farol_reference']
                                        })
                                    
                                    if "Booking Management" in stages:
                                        update_booking_query = text("""
                                            UPDATE LogTransp.F_CON_BOOKING_MANAGEMENT
                                            SET farol_status = :farol_status
                                            WHERE b_farol_reference = :farol_reference
                                        """)
                                        conn.execute(update_booking_query, {
                                            "farol_status": change['new_status'],
                                            "farol_reference": change['farol_reference']
                                        })
                                    
                                    if "Container Delivery at Port" in stages:
                                        update_loading_query = text("""
                                            UPDATE LogTransp.F_CON_CARGO_LOADING_CONTAINER_RELEASE
                                            SET farol_status = :farol_status
                                            WHERE l_farol_reference = :farol_reference
                                        """)
                                        conn.execute(update_loading_query, {
                                            "farol_status": change['new_status'],
                                            "farol_reference": change['farol_reference']
                                        })
                                    
                                    transaction.commit()
                                    success_count += 1
                                    
                                except Exception as e:
                                    if 'transaction' in locals():
                                        transaction.rollback()
                                    st.error(f"Error updating {change['farol_reference']}: {str(e)}")
                                    error_count += 1
                                finally:
                                    if 'conn' in locals():
                                        conn.close()
                            
                            if success_count > 0:
                                st.success(f"✅ Successfully updated {success_count} status(es)!")
                                if error_count == 0:
                                    st.rerun()
                            if error_count > 0:
                                st.error(f"❌ {error_count} update(s) failed!")
                    
                    with col2:
                        if st.button("❌ Cancel Changes", key="cancel_status_changes", use_container_width=True):
                            st.rerun()
            else:
                st.info("Nenhum dado ajustado encontrado. Verifique se há ajustes registrados para as referências filtradas.")
        else:
            st.info("Nenhum ajuste encontrado. Use os filtros acima para localizar ajustes específicos.")
    
    with tab2:
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
                    st.markdown("**📋 Detailed View with Applied Adjustments:**")
                    
                    # Gera os dados ajustados para esta Farol Reference específica
                    df_detail_adjusted = get_adjusted_sales_data([farol_ref], df_original)
                    
                    if not df_detail_adjusted.empty:
                        # Remove a coluna Status para manter como está na aba principal
                        df_display = df_detail_adjusted.drop(columns=['Status'])
                        
                        st.dataframe(
                            df_display,
                            column_config={
                                "Sales Farol Reference": st.column_config.TextColumn("Farol Reference", width="medium"),
                                "Sales Quantity of Containers": st.column_config.NumberColumn("Quantity", format="%d"),
                                "Sales Port of Loading POL": st.column_config.TextColumn("POL", width="medium"),
                                "Sales Port of Delivery POD": st.column_config.TextColumn("POD", width="medium"),
                                "Sales Place of Receipt": st.column_config.TextColumn("Place of Receipt", width="medium"),
                                "Sales Final Destination": st.column_config.TextColumn("Final Destination", width="medium"),
                                "Carrier": st.column_config.TextColumn("Carrier", width="medium"),
                                "Requested Cut off Start Date": st.column_config.DateColumn("Cut-off Start"),
                                "Requested Cut off End Date": st.column_config.DateColumn("Cut-off End"),
                                "Required Arrival Date": st.column_config.DateColumn("Required Arrival"),
                                "Changes Made": st.column_config.TextColumn("Changes Made", width="large"),
                                "Comments": st.column_config.TextColumn("Comments", width="large"),
                                "Adjustment ID": st.column_config.TextColumn("Adjustment ID", width="medium")
                            },
                            use_container_width=True,
                            hide_index=True
                        )
                        
                        # Adiciona seção adicional com informações técnicas dos ajustes individuais
                        st.markdown("---")  # Separador visual
                        st.markdown("**🔧 Technical Adjustment Details**")
                        st.markdown("*Individual field-level adjustments from the adjustment log:*")
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
                    else:
                        st.warning("⚠️ Could not generate adjusted data preview for this Farol Reference.")

    # Botão para voltar para Home
    if st.button("🔙 Back to Shipments"):
        st.session_state["navigate_to"] = "Shipments"
        st.rerun()

if __name__ == "__main__":
    exibir_adjustments()
 