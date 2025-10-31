import streamlit as st
import pandas as pd
from database import (
    get_return_carriers_by_farol, get_return_carriers_recent,
    get_database_connection, get_current_status_from_main_table,
    history_get_main_table_data,
    history_get_voyage_monitoring_for_reference,
    history_get_next_linked_reference_number,
)
from sqlalchemy import text
from history_components import (
    display_attachments_section as display_attachments_section_component,
    render_metrics_header,
    render_action_buttons
)
from history_helpers import (
    format_linked_reference_display, convert_utc_to_brazil_time,
    prepare_main_data_for_display, clear_history_session_state_on_selection_change,
    clear_history_session_state_when_no_selection, prepare_dataframe_for_display,
    generate_tab_labels, initialize_tab_state, handle_tab_change,
    display_flash_messages, initialize_history_state, handle_no_reference_selected,
    handle_empty_dataframe
)

"""
Módulo principal da tela History (Return Carriers History).

Este módulo foi refatorado e modularizado para melhor organização:
- history_components.py: Componentes de UI (cards, tabelas, painéis)
- history_helpers.py: Funções auxiliares (formatação, preparação de dados)
- history_data.py: Queries de banco de dados (acessadas via database.py)
"""

def update_missing_linked_references():
    """
    Atualiza registros antigos que não têm LINKED_REFERENCE definido.
    Gera automaticamente o novo formato hierárquico.
    """
    try:
        conn = get_database_connection()
        
        # Busca registros sem LINKED_REFERENCE
        query = text("""
            SELECT ID, FAROL_REFERENCE 
            FROM LogTransp.F_CON_RETURN_CARRIERS 
            WHERE LINKED_REFERENCE IS NULL 
               OR LINKED_REFERENCE = ''
            ORDER BY FAROL_REFERENCE, ROW_INSERTED_DATE
        """)
        
        records = conn.execute(query).mappings().fetchall()
        
        if not records:
            return 0
        
        updated_count = 0
        for record in records:
            farol_ref = record['FAROL_REFERENCE']
            record_id = record['ID']
            
            # Gera novo Linked Reference (usando wrapper do database.py)
            new_linked_ref = history_get_next_linked_reference_number(farol_ref)
            
            # Atualiza o registro
            update_query = text("""
                UPDATE LogTransp.F_CON_RETURN_CARRIERS 
                SET LINKED_REFERENCE = :linked_ref 
                WHERE ID = :record_id
            """)
            
            conn.execute(update_query, {
                "linked_ref": new_linked_ref,
                "record_id": record_id
            })
            updated_count += 1
        
        conn.commit()
        conn.close()
        return updated_count
        
    except Exception as e:
        st.error(f"❌ Erro ao atualizar Linked References: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return 0


def exibir_history():
    """
    Função principal que exibe a tela History (Return Carriers History).
    
    Esta função orquestra a exibição de todos os componentes:
    - Cards de métricas superiores
    - Tabela unificada de histórico (Request Timeline)
    - Painel de aprovação de PDFs
    - Timeline de viagens
    - Audit Trail
    - Gestão de anexos
    """
    
    st.header("📜 Return Carriers History")
    
    # Exibe mensagens persistentes da última ação (flash)
    display_flash_messages()
    
    # Espaçamento após o título
    st.markdown("<br>", unsafe_allow_html=True)

    farol_reference = st.session_state.get("selected_reference")
    
    # Valida se há referência selecionada
    if not farol_reference:
        if handle_no_reference_selected():
            return

    # Inicializa estados da tela History
    initialize_history_state(farol_reference)

    # Busca dados e trata caso vazio
    df = get_return_carriers_by_farol(farol_reference)
    if df.empty:
        df, should_return = handle_empty_dataframe(farol_reference)
        if should_return:
            return


    
    # Informações organizadas em cards elegantes - consultadas da tabela principal
    main_status = get_current_status_from_main_table(farol_reference) or "-"
    main_data = history_get_main_table_data(farol_reference)
    voyage_carrier, qty, ins = prepare_main_data_for_display(main_data, df)
    
    # Renderiza cards de métricas usando componente
    render_metrics_header(
        farol_reference=farol_reference,
        main_status=main_status,
        qty=qty,
        voyage_carrier=voyage_carrier,
        inserted=ins
    )

    st.markdown("---")

    # Prepara DataFrame para exibição (colunas, ordenação, filtros)
    df_display, df_unified, df_received_for_approval = prepare_dataframe_for_display(df, farol_reference)
    
    # Busca dados de monitoramento relacionados aos navios desta referência
    df_voyage_monitoring = history_get_voyage_monitoring_for_reference(farol_reference)
    
    # Gera rótulos das abas com contagens
    unified_label, voyages_label, audit_label = generate_tab_labels(
        df_unified, df_received_for_approval, df_voyage_monitoring, farol_reference
    )
    
    # Inicializa estado das abas
    initialize_tab_state(farol_reference, unified_label)
    
    # Renderiza controle de abas
    active_tab_key = f"history_active_tab_{farol_reference}"
    active_tab = st.segmented_control(
        "",
        options=[unified_label, voyages_label, audit_label],
        key=active_tab_key
    )
    
    # Gerencia troca de abas (limpa seleções quando necessário)
    handle_tab_change(farol_reference, active_tab, unified_label, voyages_label, audit_label)

    # Renderiza conteúdo das abas usando componentes
    edited_df_unified = None
    if active_tab == unified_label:
        from history_components import render_request_timeline as render_request_timeline_component
        edited_df_unified = render_request_timeline_component(df_unified, farol_reference, df_received_for_approval)

    # Seção de aprovação para PDFs "Received from Carrier"
    # Garantir que df_for_approval seja um DataFrame válido (não None e não vazio) para renderizar o painel
    df_for_approval = None
    if edited_df_unified is not None:
        if not edited_df_unified.empty:
            df_for_approval = edited_df_unified.copy()
        else:
            # Se estiver vazio mas não None, ainda permite renderizar o painel se houver df_received_for_approval
            df_for_approval = edited_df_unified
    
    # Renderiza painel de aprovação usando componente
    if active_tab == unified_label and not df_received_for_approval.empty and df_for_approval is not None:
        from history_components import render_approval_panel as render_approval_panel_component
        render_approval_panel_component(df_received_for_approval, df_for_approval, farol_reference, active_tab, unified_label)

    # Conteúdo da aba "Histórico de Viagens"
    if active_tab == voyages_label:
        from history_components import render_voyages_timeline as render_voyages_timeline_component
        render_voyages_timeline_component(df_voyage_monitoring)

    # Conteúdo da aba "Audit Trail"
    if active_tab == audit_label:
        from history_components import display_audit_trail_tab as display_audit_trail_tab_component
        display_audit_trail_tab_component(farol_reference)

    # Verificar se há PDF selecionado no selectbox
    selected_pdf_option = st.session_state.get(f"pdf_approval_select_{farol_reference}")
    has_pdf_selected = selected_pdf_option and selected_pdf_option != "Selecione um PDF para aprovar..."
    
    # Limpa status pendente quando a seleção muda
    if has_pdf_selected:
        current_adjustment_id = st.session_state.get(f"adjustment_id_for_approval_{farol_reference}")
        last_adjustment_id = st.session_state.get(f"last_selected_adjustment_id_{farol_reference}")
        
        clear_history_session_state_on_selection_change(farol_reference, current_adjustment_id, last_adjustment_id)
        
        # Atualiza o ID da seleção atual
        st.session_state[f"last_selected_adjustment_id_{farol_reference}"] = current_adjustment_id
    else:
        clear_history_session_state_when_no_selection(farol_reference)

    # Prepara DataFrame para exportação CSV
    combined_df = edited_df_unified if (edited_df_unified is not None and not edited_df_unified.empty) else pd.DataFrame()

    # Renderiza botões de ação usando componente
    render_action_buttons(farol_reference, combined_df)

    # Seção de anexos (toggle)
    if st.session_state.get("history_show_attachments", False):
        st.markdown("---")
        st.subheader("📎 Attachment Management")
        display_attachments_section_component(farol_reference)
