import streamlit as st
import pandas as pd
from database import (
    get_return_carriers_by_farol, get_return_carriers_recent, load_df_udc, 
    get_database_connection, get_current_status_from_main_table, 
    get_return_carrier_status_by_adjustment_id, get_terminal_monitorings,
    approve_carrier_return, update_record_status,
    history_get_main_table_data,
    history_get_voyage_monitoring_for_reference,
    history_get_available_references_for_relation,
    history_save_attachment,
    history_get_attachments,
    history_delete_attachment,
    history_get_attachment_content,
    history_get_next_linked_reference_number,
    history_get_referenced_line_data,
)
from shipments_mapping import get_column_mapping, process_farol_status_for_display
from sqlalchemy import text
from datetime import datetime
import os
import base64
import mimetypes
import uuid
from pdf_booking_processor import process_pdf_booking, display_pdf_validation_interface, save_pdf_booking_data
from history_components import (
    display_attachments_section as display_attachments_section_component,
    render_metrics_header
)
from history_helpers import (
    format_linked_reference_display, convert_utc_to_brazil_time,
    prepare_main_data_for_display, clear_history_session_state_on_selection_change,
    clear_history_session_state_when_no_selection, prepare_dataframe_for_display,
    generate_tab_labels, initialize_tab_state, handle_tab_change,
    display_flash_messages, initialize_history_state, handle_no_reference_selected,
    handle_empty_dataframe
)

# Carrega dados da UDC para justificativas
df_udc = load_df_udc()
Booking_adj_area = df_udc[df_udc["grupo"] == "Booking Adj Area"]["dado"].dropna().unique().tolist()
Booking_adj_reason = df_udc[df_udc["grupo"] == "Booking Adj Request Reason"]["dado"].dropna().unique().tolist()
Booking_adj_responsibility = df_udc[df_udc["grupo"] == "Booking Adj Responsibility"]["dado"].dropna().unique().tolist()

# Opções específicas para New Adjustment no history.py
Booking_adj_reason_car = df_udc[df_udc["grupo"] == "Booking Adj Request Reason Car"]["dado"].dropna().unique().tolist()
Booking_adj_responsibility_car = df_udc[df_udc["grupo"] == "Booking Adj Responsibility Car"]["dado"].dropna().unique().tolist()

# get_next_linked_reference_number e get_referenced_line_data removidos - agora importados de history_data.py via database.py

# format_linked_reference_display removido - agora importado de history_helpers.py

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

# get_voyage_monitoring_for_reference, get_available_references_for_relation, get_file_type,
# save_attachment_to_db, get_attachments_for_farol, delete_attachment, get_attachment_content,
# format_file_size, get_file_icon, get_main_table_data removidos - agora importados via database.py
# display_attachments_section removido - agora importado de history_components.py

# _display_attachments_section_legacy removido - agora usando display_attachments_section_component de history_components.py

def exibir_history():
    import pandas as pd
    from datetime import datetime
    
    # convert_utc_to_brazil_time removido - agora importado de history_helpers.py
    
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

    # Funções auxiliares (calculate_column_width, generate_dynamic_column_config, process_dataframe,
    # display_tab_content, detect_changes_for_new_adjustment, detect_changes_for_carrier_return,
    # apply_highlight_styling_combined, apply_highlight_styling) foram migradas para history_components.py
    # e são usadas dentro de render_request_timeline. Estas funções não são mais necessárias aqui.

    # Conteúdo da aba unificada "Request Timeline"
    edited_df_unified = None
    if active_tab == unified_label:
        from history_components import render_request_timeline as render_request_timeline_component
        edited_df_unified = render_request_timeline_component(df_unified, farol_reference, df_received_for_approval)

    # Seção de aprovação para PDFs "Received from Carrier" (abaixo da tabela unificada)
    # Usaremos o DataFrame ORIGINAL (antes da reversão) para buscar o Index correto
    df_for_approval = edited_df_unified.copy() if edited_df_unified is not None else None
    
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

    # apply_status_change removida - lógica de aprovação migrada para render_approval_panel_component em history_components.py

    # Atualizar seção de Export CSV para usar apenas o DataFrame unificado
    if edited_df_unified is not None and not edited_df_unified.empty:
        combined_df = edited_df_unified
    else:
        combined_df = pd.DataFrame()

    # Seção de botões de ação (View Attachments, Export, Back)
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        # Toggle de anexos
        view_open = st.session_state.get("history_show_attachments", False)
        if st.button("📎 View Attachments", key="history_view_attachments"):
            st.session_state["history_show_attachments"] = not view_open
            st.rerun()
    with col2:
        # Export CSV
        if not combined_df.empty:
            st.download_button("⬇️ Export CSV", data=combined_df.to_csv(index=False).encode("utf-8"), file_name=f"return_carriers_{farol_reference}.csv", mime="text/csv")
        else:
            st.download_button("⬇️ Export CSV", data="".encode("utf-8"), file_name=f"return_carriers_{farol_reference}.csv", mime="text/csv", disabled=True)
    with col3:
        if st.button("🔙 Back to Shipments"):
            st.session_state["current_page"] = "main"
            st.rerun()

    # Seção de anexos (toggle)
    
    if st.session_state.get("history_show_attachments", False):
        st.markdown("---")
        st.subheader("📎 Attachment Management")
        display_attachments_section_component(farol_reference)
