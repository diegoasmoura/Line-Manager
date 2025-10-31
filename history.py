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
from history_helpers import format_linked_reference_display, convert_utc_to_brazil_time

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
    try:
        _flash = st.session_state.pop("history_flash", None)
        if _flash:
            level = _flash.get("type", "info")
            msg = _flash.get("msg", "")
            if level == "success":
                st.success(msg)
            elif level == "error":
                st.error(msg)
            elif level == "warning":
                st.warning(msg)
            else:
                st.info(msg)
    except Exception:
        pass
    
    # Espaçamento após o título
    st.markdown("<br>", unsafe_allow_html=True)

    farol_reference = st.session_state.get("selected_reference")
    
    # Initialize approval_step in session_state if not present
    if f"approval_step_{farol_reference}" not in st.session_state:
        st.session_state[f"approval_step_{farol_reference}"] = None

    if not farol_reference:
        st.info("Selecione uma linha em Shipments para visualizar o Ticket Journey.")
        col = st.columns(1)[0]
        with col:
            if st.button("🔙 Back to Shipments"):
                st.session_state["current_page"] = "main"
                st.rerun()
        return

    # Inicialização: ao entrar na tela pela primeira vez (por referência), retrai View Attachments e limpa estados residuais
    init_key = f"history_initialized_{farol_reference}"
    if not st.session_state.get(init_key):
        st.session_state["history_show_attachments"] = False
        # Limpa possíveis estados de processamento/expansão do módulo de anexos
        for k in [
            f"processed_pdf_data_{farol_reference}",
            f"booking_pdf_file_{farol_reference}",
            f"expander_state_{farol_reference}",
            f"attachment_cache_{farol_reference}",
            f"uploader_ver_{farol_reference}",
        ]:
            st.session_state.pop(k, None)
        st.session_state[init_key] = True


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


    
    # Informações organizadas em cards elegantes - consultadas da tabela principal
    main_status = get_current_status_from_main_table(farol_reference) or "-"
    
    # Busca dados da tabela principal F_CON_SALES_BOOKING_DATA em vez do último registro
    main_data = history_get_main_table_data(farol_reference)
    
    if main_data:
        # Dados da tabela principal - usando as chaves corretas (minúsculas)
        voyage_carrier = str(main_data.get("b_voyage_carrier", "-"))
        
        qty = main_data.get("s_quantity_of_containers", 0)
        try:
            qty = int(qty) if qty is not None and not pd.isna(qty) else 0
        except (ValueError, TypeError):
            qty = 0
        
        ins = main_data.get("row_inserted_date", "-")
        try:
            # Se já é datetime object, formata diretamente
            if isinstance(ins, datetime):
                ins = ins.strftime('%Y-%m-%d %H:%M:%S')
            # Se for epoch ms para datetime legível, se for numérico
            elif isinstance(ins, (int, float)):
                ins = datetime.fromtimestamp(ins/1000.0).strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            pass
    else:
        # Fallback para valores do último registro se a tabela principal não tiver dados
        voyage_carrier = str(df.iloc[0].get("B_VOYAGE_CARRIER", "-")) if not df.empty else "-"
        qty = 0
        ins = "-"
    
    # Renderiza cards de métricas usando componente
    render_metrics_header(
        farol_reference=farol_reference,
        main_status=main_status,
        qty=qty,
        voyage_carrier=voyage_carrier,
        inserted=ins
    )

    st.markdown("---")

    # Grade principal com colunas relevantes (ADJUSTMENT_ID oculto mas usado internamente)
    # ID removido da visualização - não é mais necessário para o usuário
    display_cols = [
        "ROW_INSERTED_DATE",
        "FAROL_REFERENCE",
        "FAROL_STATUS",
        "B_BOOKING_REFERENCE",
        "B_VESSEL_NAME",
        "B_VOYAGE_CARRIER",
        "B_VOYAGE_CODE",
        "S_QUANTITY_OF_CONTAINERS",
        "S_PLACE_OF_RECEIPT",
        "S_PORT_OF_LOADING_POL",
        "S_PORT_OF_DELIVERY_POD",
        "S_FINAL_DESTINATION",
        "B_TRANSHIPMENT_PORT",
        "B_TERMINAL",
        "S_REQUIRED_ARRIVAL_DATE_EXPECTED",
        "S_REQUESTED_DEADLINE_START_DATE",
        "S_REQUESTED_DEADLINE_END_DATE",
        "B_DATA_DRAFT_DEADLINE",
        "B_DATA_DEADLINE",
        "B_DATA_ESTIMATIVA_SAIDA_ETD",
        "B_DATA_ESTIMATIVA_CHEGADA_ETA",
        "B_DATA_ABERTURA_GATE",
        "B_DATA_CONFIRMACAO_EMBARQUE",
        "B_DATA_ESTIMADA_TRANSBORDO_ETD",
        "B_DATA_TRANSBORDO_ATD",
        "P_PDF_NAME",
        "PDF_BOOKING_EMISSION_DATE",
        "LINKED_REFERENCE",
        "B_DATA_ESTIMATIVA_ATRACACAO_ETB",
        "B_DATA_ATRACACAO_ATB",
        "B_DATA_PARTIDA_ATD",
        "B_DATA_CHEGADA_ATA",
        "ADJUSTMENTS_OWNER",
    ]

    # Inclui ADJUSTMENT_ID nos dados para funcionalidade interna
    internal_cols = display_cols + ["ADJUSTMENT_ID"]
    
    df_show = df[[c for c in internal_cols if c in df.columns]].copy()
    
    # Força a ordem correta das colunas baseada na lista display_cols
    ordered_cols = [c for c in internal_cols if c in df_show.columns]
    df_show = df_show[ordered_cols]
    
    # Aplica ordenação por Inserted Date antes de separar em abas
    if "ROW_INSERTED_DATE" in df_show.columns:
        # Ordenação primária por data inserida (mais antigo → mais novo)
        # Critério secundário estável: raiz da Farol Reference e sufixo numérico (.1, .2, ...)
        if "FAROL_REFERENCE" in df_show.columns:
            refs_base = df_show["FAROL_REFERENCE"].astype(str)
            df_show["__ref_root"] = refs_base.str.split(".").str[0]
            df_show["__ref_suffix_num"] = (
                refs_base.str.extract(r"\.(\d+)$")[0].fillna("0").astype(str).astype(int)
            )
            df_show = df_show.sort_values(
                by=["ROW_INSERTED_DATE", "__ref_root", "__ref_suffix_num"],
                ascending=[True, True, True],
                kind="mergesort",
            )
            df_show = df_show.drop(columns=["__ref_root", "__ref_suffix_num"])  # limpeza
        else:
            df_show = df_show.sort_values(by=["ROW_INSERTED_DATE"], ascending=[True], kind="mergesort")
    
    # Cria cópia do DataFrame (coluna Index será adicionada na função display_tab_content)
    df_display = df_show.copy()
    
    # DataFrame unificado - todas as linhas juntas
    df_unified = df_display.copy()
    
    # Remove splits informativos (exceto a referência atual) para contagem de rótulos
    df_other_status = df_display[df_display["FAROL_STATUS"] != "Received from Carrier"].copy()
    
    if not df_other_status.empty:
        # Filtrar linhas que são splits EXCETO a referência atual
        has_ref_col = "FAROL_REFERENCE" in df_other_status.columns
        
        if has_ref_col and farol_reference:
            import re
            # Mantém apenas:
            # 1. A referência atual (seja original ou split)
            # 2. Registros que NÃO são splits (não têm padrão .n)
            current_ref = str(farol_reference).strip()
            
            df_other_status = df_other_status[
                # É a referência atual OU não é um split
                (df_other_status["FAROL_REFERENCE"].astype(str) == current_ref) |
                (~df_other_status["FAROL_REFERENCE"].astype(str).str.match(r'.*\.\d+$', na=False))
            ].copy()
    
    # Separar PDFs "Received from Carrier" da referência atual para aprovação
    df_received_count = df_display[df_display["FAROL_STATUS"] == "Received from Carrier"].copy()
    df_received_for_approval = pd.DataFrame()

    try:
        if not df_received_count.empty and "FAROL_REFERENCE" in df_received_count.columns and farol_reference is not None:
            fr_sel = str(farol_reference).strip().upper()
            df_received_for_approval = df_received_count[
                df_received_count["FAROL_REFERENCE"].astype(str).str.upper() == fr_sel
            ].copy()
    except Exception:
        pass
    
    # Rótulos das abas
    unified_label = f"📋 Request Timeline ({len(df_unified)} records)"
    received_label = f"📨 Returns Awaiting Review ({len(df_received_for_approval)} records)"
    
    # Busca dados de monitoramento relacionados aos navios desta referência
    df_voyage_monitoring = history_get_voyage_monitoring_for_reference(farol_reference)

    # Contagem de combinações distintas (Navio + Viagem + Terminal)
    try:
        if df_voyage_monitoring is not None and not df_voyage_monitoring.empty:
            df_tmp_count = df_voyage_monitoring.copy()
            df_tmp_count['navio'] = df_tmp_count['navio'].astype(str)
            df_tmp_count['viagem'] = df_tmp_count['viagem'].astype(str)
            # Alguns datasets usam 'terminal' ou 'port_terminal_city'
            terminal_col = 'terminal' if 'terminal' in df_tmp_count.columns else ('port_terminal_city' if 'port_terminal_city' in df_tmp_count.columns else None)
            if terminal_col:
                df_tmp_count[terminal_col] = df_tmp_count[terminal_col].astype(str)
                distinct_count = df_tmp_count.drop_duplicates(subset=['navio', 'viagem', terminal_col]).shape[0]
            else:
                distinct_count = df_tmp_count.drop_duplicates(subset=['navio', 'viagem']).shape[0]
        else:
            distinct_count = 0
    except Exception:
        distinct_count = len(df_voyage_monitoring) if df_voyage_monitoring is not None else 0

    voyages_label = f"📅 Voyage Timeline ({distinct_count} distinct)"

    # Contagem para aba Audit Trail
    try:
        from sqlalchemy import text as _text_audit
        conn_cnt = get_database_connection()
        cnt_query = _text_audit("""
            SELECT COUNT(*)
            FROM LogTransp.V_FAROL_AUDIT_TRAIL
            WHERE FAROL_REFERENCE = :farol_ref
        """)
        audit_count = conn_cnt.execute(cnt_query, {"farol_ref": farol_reference}).scalar() or 0
        conn_cnt.close()
    except Exception:
        audit_count = 0

    # Label da aba Audit Trail
    audit_label = f"🔍 Audit Trail ({audit_count} records)"

    # Controle de "aba" ativa (segmented control) para detectar troca e limpar seleções da outra
    active_tab_key = f"history_active_tab_{farol_reference}"
    last_active_tab_key = f"history_last_active_tab_{farol_reference}"
    if active_tab_key not in st.session_state:
        st.session_state[active_tab_key] = unified_label
        st.session_state[last_active_tab_key] = unified_label

    active_tab = st.segmented_control(
        "",
        options=[unified_label, voyages_label, audit_label],
        key=active_tab_key
    )

    # Se detectarmos troca de aba, limpamos as seleções das outras abas
    prev_tab = st.session_state.get(last_active_tab_key)
    if prev_tab != active_tab:
        if active_tab == unified_label:
            # Ao entrar na aba unificada, limpar qualquer seleção pendente
            if f"pdf_approval_select_{farol_reference}" in st.session_state:
                del st.session_state[f"pdf_approval_select_{farol_reference}"]
        elif active_tab == audit_label:
            # Limpamos seleção quando entrar na Audit Trail
            if f"pdf_approval_select_{farol_reference}" in st.session_state:
                del st.session_state[f"pdf_approval_select_{farol_reference}"]
        else:  # voyages_label
            # Limpamos seleção ao entrar na aba Voyages
            if f"pdf_approval_select_{farol_reference}" in st.session_state:
                del st.session_state[f"pdf_approval_select_{farol_reference}"]
        # Ao trocar de aba, recolhe a seção de anexos para manter a tela limpa
        st.session_state["history_show_attachments"] = False
        st.session_state[last_active_tab_key] = active_tab

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
        # Obter adjustment_id do PDF selecionado
        current_adjustment_id = st.session_state.get(f"adjustment_id_for_approval_{farol_reference}")
        last_adjustment_id = st.session_state.get(f"last_selected_adjustment_id_{farol_reference}")
        
        if last_adjustment_id is not None and last_adjustment_id != current_adjustment_id:
            # Seleção mudou, limpa status pendente
            if f"pending_status_change_{farol_reference}" in st.session_state:
                del st.session_state[f"pending_status_change_{farol_reference}"]
            # Limpa qualquer gatilho/flag de formulário manual pendente ao trocar a seleção
            if "voyage_manual_entry_required" in st.session_state:
                del st.session_state["voyage_manual_entry_required"]
            # Limpa aviso de sucesso da API
            if "voyage_success_notice" in st.session_state:
                del st.session_state["voyage_success_notice"]
            # Limpa erros de aprovação ou salvamento manual de ações anteriores
            if "approval_error" in st.session_state:
                del st.session_state["approval_error"]
            if "manual_save_error" in st.session_state:
                del st.session_state["manual_save_error"]
            # Limpa possíveis triggers por ajuste anterior
            for k in list(st.session_state.keys()):
                if str(k).startswith("manual_related_ref_value_") or str(k).startswith("manual_trigger_"):
                    try:
                        del st.session_state[k]
                    except Exception:
                        pass
            if "pending_status_change" in st.session_state:
                del st.session_state["pending_status_change"]
            # Ao mudar a seleção, recolhe a seção de anexos
            st.session_state["history_show_attachments"] = False
        
        # Atualiza o ID da seleção atual
        st.session_state[f"last_selected_adjustment_id_{farol_reference}"] = current_adjustment_id
    else:
        # Nenhuma linha selecionada, limpa status e avisos/flags
        if f"pending_status_change_{farol_reference}" in st.session_state:
            del st.session_state[f"pending_status_change_{farol_reference}"]
        if "pending_status_change" in st.session_state:
            del st.session_state["pending_status_change"]
        if f"last_selected_adjustment_id_{farol_reference}" in st.session_state:
            del st.session_state[f"last_selected_adjustment_id_{farol_reference}"]
        if "voyage_manual_entry_required" in st.session_state:
            del st.session_state["voyage_manual_entry_required"]
        if "voyage_success_notice" in st.session_state:
            del st.session_state["voyage_success_notice"]

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
