import streamlit as st
import pandas as pd
from sqlalchemy import text
import traceback
from datetime import datetime, timedelta
import json

from database import get_database_connection, update_booking_from_voyage
from ellox_sync_functions import get_sync_logs, get_sync_statistics
from auth.login import has_access_level

def get_voyage_data_for_update():
    """
    Busca o último registro de cada combinação e conta as Farol References associadas.
    """
    try:
        with get_database_connection() as conn:
            query = text("""
                WITH latest_monitoring AS (
                    SELECT
                        m.ID, m.NAVIO, m.VIAGEM, m.TERMINAL, m.DATA_ESTIMATIVA_SAIDA,
                        m.DATA_ESTIMATIVA_CHEGADA, m.DATA_DEADLINE, m.DATA_DRAFT_DEADLINE,
                        m.DATA_ABERTURA_GATE, m.DATA_ATRACACAO, m.DATA_PARTIDA, m.DATA_CHEGADA,
                        m.DATA_ESTIMATIVA_ATRACACAO, m.B_DATA_CONFIRMACAO_EMBARQUE, 
                        m.B_DATA_ESTIMADA_TRANSBORDO_ETD, m.B_DATA_TRANSBORDO_ATD,
                        m.B_DATA_CHEGADA_DESTINO_ETA, m.B_DATA_CHEGADA_DESTINO_ATA,
                        ROW_NUMBER() OVER (
                            PARTITION BY UPPER(m.NAVIO), UPPER(m.VIAGEM), UPPER(m.TERMINAL)
                            ORDER BY NVL(m.DATA_ATUALIZACAO, m.ROW_INSERTED_DATE) DESC
                        ) as rn
                    FROM LogTransp.F_ELLOX_TERMINAL_MONITORINGS m
                )
                SELECT
                    lm.ID, lm.NAVIO, lm.VIAGEM, lm.TERMINAL, lm.DATA_ESTIMATIVA_SAIDA,
                    lm.DATA_ESTIMATIVA_CHEGADA, lm.DATA_DEADLINE, lm.DATA_DRAFT_DEADLINE,
                    lm.DATA_ABERTURA_GATE, lm.DATA_ATRACACAO, lm.DATA_PARTIDA, lm.DATA_CHEGADA,
                    lm.DATA_ESTIMATIVA_ATRACACAO, lm.B_DATA_CONFIRMACAO_EMBARQUE, 
                    lm.B_DATA_ESTIMADA_TRANSBORDO_ETD, lm.B_DATA_TRANSBORDO_ATD,
                    lm.B_DATA_CHEGADA_DESTINO_ETA, lm.B_DATA_CHEGADA_DESTINO_ATA,
                    LISTAGG(DISTINCT r.FAROL_REFERENCE, ', ') WITHIN GROUP (ORDER BY r.FAROL_REFERENCE) as "farol_references_list",
                    COUNT(DISTINCT r.FAROL_REFERENCE) as "farol_references_count"
                FROM latest_monitoring lm
                INNER JOIN LogTransp.F_CON_RETURN_CARRIERS r ON (
                    UPPER(lm.NAVIO) = UPPER(r.B_VESSEL_NAME)
                    AND UPPER(lm.VIAGEM) = UPPER(r.B_VOYAGE_CODE)
                    AND UPPER(lm.TERMINAL) = UPPER(r.B_TERMINAL)
                    AND r.FAROL_REFERENCE IS NOT NULL
                )
                WHERE lm.rn = 1
                GROUP BY
                    lm.ID, lm.NAVIO, lm.VIAGEM, lm.TERMINAL, lm.DATA_ESTIMATIVA_SAIDA,
                    lm.DATA_ESTIMATIVA_CHEGADA, lm.DATA_DEADLINE, lm.DATA_DRAFT_DEADLINE,
                    lm.DATA_ABERTURA_GATE, lm.DATA_ATRACACAO, lm.DATA_PARTIDA, lm.DATA_CHEGADA,
                    lm.DATA_ESTIMATIVA_ATRACACAO, lm.B_DATA_CONFIRMACAO_EMBARQUE, 
                    lm.B_DATA_ESTIMADA_TRANSBORDO_ETD, lm.B_DATA_TRANSBORDO_ATD,
                    lm.B_DATA_CHEGADA_DESTINO_ETA, lm.B_DATA_CHEGADA_DESTINO_ATA
                ORDER BY lm.NAVIO, lm.VIAGEM
            """)
            df = pd.read_sql(query, conn)

            date_columns = [col for col in df.columns if 'data' in col.lower()]
            for col in date_columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')

            return df
    except Exception as e:
        st.error(f"❌ Erro ao buscar dados de monitoramento: {str(e)}")
        return pd.DataFrame()

def get_farol_references_details(vessel_name, voyage_code, terminal):
    """Busca o detalhe mais recente de cada Farol Reference, incluindo datas da tabela principal."""
    try:
        with get_database_connection() as conn:
            query = text("""
                WITH ranked_references AS (
                    SELECT 
                        r.FAROL_REFERENCE, r.B_BOOKING_REFERENCE, r.B_BOOKING_STATUS, 
                        r.P_STATUS, r.B_VESSEL_NAME, r.B_VOYAGE_CODE, r.B_TERMINAL,
                        r.B_DATA_ESTIMATIVA_SAIDA_ETD, r.B_DATA_ESTIMATIVA_CHEGADA_ETA, r.ROW_INSERTED_DATE,
                        s.S_CREATION_OF_SHIPMENT, s.B_CREATION_OF_BOOKING, s.B_BOOKING_REQUEST_DATE,
                        ROW_NUMBER() OVER(PARTITION BY r.FAROL_REFERENCE ORDER BY r.ROW_INSERTED_DATE DESC) as rn
                    FROM LogTransp.F_CON_RETURN_CARRIERS r
                    LEFT JOIN LogTransp.F_CON_SALES_BOOKING_DATA s ON r.FAROL_REFERENCE = s.FAROL_REFERENCE
                    WHERE UPPER(TRIM(r.B_VESSEL_NAME)) = UPPER(TRIM(:vessel_name))
                    AND UPPER(TRIM(r.B_VOYAGE_CODE)) = UPPER(TRIM(:voyage_code))
                    AND UPPER(TRIM(r.B_TERMINAL)) = UPPER(TRIM(:terminal))
                    AND r.FAROL_REFERENCE IS NOT NULL
                )
                SELECT
                    FAROL_REFERENCE, B_BOOKING_REFERENCE, B_BOOKING_STATUS, 
                    P_STATUS, B_VESSEL_NAME, B_VOYAGE_CODE, B_TERMINAL,
                    B_DATA_ESTIMATIVA_SAIDA_ETD, B_DATA_ESTIMATIVA_CHEGADA_ETA, ROW_INSERTED_DATE,
                    S_CREATION_OF_SHIPMENT, B_CREATION_OF_BOOKING, B_BOOKING_REQUEST_DATE
                FROM ranked_references
                WHERE rn = 1
                ORDER BY FAROL_REFERENCE
            """)
            params = {'vessel_name': vessel_name, 'voyage_code': voyage_code, 'terminal': terminal}
            df = pd.read_sql(query, conn, params=params)
            return df
    except Exception as e:
        st.error(f"Erro ao buscar detalhes dos Farol References: {str(e)}")
        return pd.DataFrame()

def get_voyage_history(vessel_name, voyage_code, terminal):
    """Busca o histórico completo de monitoramento para uma viagem específica."""
    try:
        with get_database_connection() as conn:
            query = text("""
                SELECT
                    ID, NAVIO, VIAGEM, TERMINAL, DATA_SOURCE,
                    DATA_ESTIMATIVA_SAIDA, DATA_ESTIMATIVA_CHEGADA, DATA_DEADLINE,
                    DATA_DRAFT_DEADLINE, DATA_ABERTURA_GATE, DATA_ABERTURA_GATE_REEFER,
                    DATA_ATRACACAO, DATA_PARTIDA, DATA_CHEGADA, DATA_ESTIMATIVA_ATRACACAO,
                    B_DATA_CONFIRMACAO_EMBARQUE, B_DATA_ESTIMADA_TRANSBORDO_ETD, B_DATA_TRANSBORDO_ATD,
                    B_DATA_CHEGADA_DESTINO_ETA, B_DATA_CHEGADA_DESTINO_ATA,
                    ROW_INSERTED_DATE, DATA_ATUALIZACAO
                FROM LogTransp.F_ELLOX_TERMINAL_MONITORINGS
                WHERE UPPER(TRIM(NAVIO)) = UPPER(TRIM(:vessel_name))
                AND UPPER(TRIM(VIAGEM)) = UPPER(TRIM(:voyage_code))
                AND UPPER(TRIM(TERMINAL)) = UPPER(TRIM(:terminal))
                ORDER BY NVL(DATA_ATUALIZACAO, ROW_INSERTED_DATE) DESC
            """)
            params = {'vessel_name': vessel_name, 'voyage_code': voyage_code, 'terminal': terminal}
            df = pd.read_sql(query, conn, params=params)
            
            # Converte todas as colunas de data (exceto data_source)
            date_columns = [col for col in df.columns if 'data' in col.lower() and col != 'data_source']
            for col in date_columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')

            return df
    except Exception as e:
        st.error(f"❌ Erro ao buscar histórico da viagem: {str(e)}")
        return pd.DataFrame()

def exibir_tracking():
    """
    Exibe a página de tracking com abas para atualização manual e logs de sincronização.
    """
    st.title("🚢 Tracking de Viagens")
    
    # Verifica se usuário tem acesso de admin para ver logs de sincronização
    show_sync_logs = has_access_level('ADMIN')
    
    if show_sync_logs:
        # Abas para admin
        tab1, tab2 = st.tabs(["📊 Atualização Manual", "🔄 Sync Logs"])
        
        with tab1:
            exibir_atualizacao_manual()
        
        with tab2:
            exibir_sync_logs()
    else:
        # Apenas atualização manual para usuários não-admin
        exibir_atualizacao_manual()


def exibir_atualizacao_manual():
    """
    Exibe a página para atualização manual de datas de viagem.
    """
    # Inicializa a chave do editor se não existir
    if 'voyage_editor_key_suffix' not in st.session_state:
        st.session_state.voyage_editor_key_suffix = 0

    # Se foi solicitado descarte de alterações, incrementa a chave do editor para forçar a recriação
    if st.session_state.get('tracking_discard_changes'):
        st.session_state.pop('tracking_discard_changes', None)
        st.session_state.voyage_editor_key_suffix += 1
        st.rerun()

    if "page_flash_message" in st.session_state:
        flash = st.session_state.pop("page_flash_message")
        st.success(flash["message"])

    st.subheader("📊 Atualização Manual de Datas de Viagem")

    with st.spinner("Carregando dados de viagens..."):
        df_original = get_voyage_data_for_update()

    if df_original.empty:
        st.info("Nenhum dado de viagem encontrado para atualização.")
        return

    st.subheader("🔍 Filtros")
    col1, col2 = st.columns(2)
    with col1:
        vessel_filter = st.multiselect("Filtrar por Navio", options=sorted(df_original["navio"].dropna().unique().tolist()))
    with col2:
        terminal_filter = st.multiselect("Filtrar por Terminal", options=sorted(df_original["terminal"].dropna().unique().tolist()))

    df_filtered = df_original.copy()
    if vessel_filter:
        df_filtered = df_filtered[df_filtered["navio"].isin(vessel_filter)]
    if terminal_filter:
        df_filtered = df_filtered[df_filtered["terminal"].isin(terminal_filter)]

    st.info("Edite as datas diretamente na grade. As alterações serão destacadas. Clique em 'Salvar Alterações' para confirmar.")

    df_display = df_filtered.copy()
    df_display["Selecionar"] = False

    # Restaura a seleção se ela existir na session_state, para que não se perca ao descartar alterações
    if 'tracking_selected_voyage' in st.session_state:
        voyage_key = st.session_state['tracking_selected_voyage']
        selected_row_indices = df_display[
            (df_display['navio'] == voyage_key[0]) &
            (df_display['viagem'] == voyage_key[1]) &
            (df_display['terminal'] == voyage_key[2])
        ].index
        
        if not selected_row_indices.empty:
            df_display.loc[selected_row_indices, 'Selecionar'] = True

    column_config = {
        "id": None, "rn": None, "farol_references_list": None,
        "navio": st.column_config.TextColumn("Vessel Name", disabled=True),
        "viagem": st.column_config.TextColumn("Voyage Code", disabled=True),
        "terminal": st.column_config.TextColumn("Port Terminal City", disabled=True),
        "farol_references_count": st.column_config.NumberColumn("Refs", help="Número de Farol References associadas", disabled=True),
        "data_estimativa_saida": st.column_config.DatetimeColumn("ETD", format="DD/MM/YYYY HH:mm"),
        "data_estimativa_chegada": st.column_config.DatetimeColumn("ETA", format="DD/MM/YYYY HH:mm"),
        "data_deadline": st.column_config.DatetimeColumn("Deadline", format="DD/MM/YYYY HH:mm"),
        "data_draft_deadline": st.column_config.DatetimeColumn("Draft Deadline", format="DD/MM/YYYY HH:mm"),
        "data_abertura_gate": st.column_config.DatetimeColumn("Abertura Gate", format="DD/MM/YYYY HH:mm"),
        "data_atracacao": st.column_config.DatetimeColumn("Atracação (ATB)", format="DD/MM/YYYY HH:mm"),
        "data_partida": st.column_config.DatetimeColumn("Partida (ATD)", format="DD/MM/YYYY HH:mm"),
        "data_chegada": st.column_config.DatetimeColumn("Chegada (ATA)", format="DD/MM/YYYY HH:mm"),
        "data_estimativa_atracacao": st.column_config.DatetimeColumn("Estimativa Atracação (ETB)", format="DD/MM/YYYY HH:mm"),
        "b_data_confirmacao_embarque": st.column_config.DatetimeColumn("Confirmação Embarque", format="DD/MM/YYYY HH:mm"),
        "b_data_estimada_transbordo_etd": st.column_config.DatetimeColumn("Estimativa Transbordo (ETD)", format="DD/MM/YYYY HH:mm"),
        "b_data_transbordo_atd": st.column_config.DatetimeColumn("Transbordo (ATD)", format="DD/MM/YYYY HH:mm"),
        "b_data_chegada_destino_eta": st.column_config.DatetimeColumn("Estimativa Chegada Destino (ETA)", format="DD/MM/YYYY HH:mm"),
        "b_data_chegada_destino_ata": st.column_config.DatetimeColumn("Chegada no Destino (ATA)", format="DD/MM/YYYY HH:mm"),
        "Selecionar": st.column_config.CheckboxColumn("Select", help="Selecione uma linha para ver as opções")
    }
    
    # Ordem das colunas seguindo o padrão do history.py Voyage Timeline
    display_order_preferred = [
        "Selecionar", "navio", "viagem", "terminal", "farol_references_count",
        "data_deadline", "data_draft_deadline", "data_abertura_gate", "data_abertura_gate_reefer",
        "data_estimativa_saida", "data_estimativa_chegada", "data_estimativa_atracacao",
        "data_atracacao", "data_partida", "data_chegada",
        "b_data_confirmacao_embarque", "b_data_estimada_transbordo_etd", "b_data_transbordo_atd",
        "b_data_chegada_destino_eta", "b_data_chegada_destino_ata"
    ] + [col for col in df_display.columns if col not in [
        "Selecionar", "navio", "viagem", "terminal", "farol_references_count",
        "data_deadline", "data_draft_deadline", "data_abertura_gate", "data_abertura_gate_reefer",
        "data_estimativa_saida", "data_estimativa_chegada", "data_estimativa_atracacao",
        "data_atracacao", "data_partida", "data_chegada",
        "b_data_confirmacao_embarque", "b_data_estimada_transbordo_etd", "b_data_transbordo_atd",
        "b_data_chegada_destino_eta", "b_data_chegada_destino_ata",
        "id", "rn", "farol_references_list"
    ]]
    display_order_safe = [col for col in display_order_preferred if col in df_display.columns]

    edited_df = st.data_editor(
        df_display[display_order_safe],
        column_config=column_config, use_container_width=True, num_rows="fixed", key=f"voyage_editor_{st.session_state.voyage_editor_key_suffix}", hide_index=True
    )

    selected_rows = edited_df[edited_df["Selecionar"] == True]

    # Verifica se houve alterações na grade (comparando com dados originais)
    df_original_for_comparison = df_filtered[edited_df.columns.drop('Selecionar')]
    edited_for_comparison = edited_df.drop(columns=['Selecionar'])
    
    # Detecta se há mudanças nos dados
    has_changes = not df_original_for_comparison.reset_index(drop=True).equals(edited_for_comparison.reset_index(drop=True))
    
    # Limpa a escolha se a seleção mudar, desaparecer ou se houver alterações na grade
    if len(selected_rows) != 1 or has_changes:
        if 'tracking_selected_voyage' in st.session_state:
            del st.session_state['tracking_selected_voyage']
        if 'tracking_view_choice' in st.session_state:
            del st.session_state['tracking_view_choice']
    
    if len(selected_rows) > 1:
        st.warning("⚠️ Por favor, selecione apenas uma linha por vez.")
    elif len(selected_rows) == 1:
        st.divider()
        selected_row = selected_rows.iloc[0]
        voyage_key = (selected_row['navio'], selected_row['viagem'], selected_row['terminal'])

        # Se a seleção mudou, reseta a escolha de visualização
        if st.session_state.get('tracking_selected_voyage') != voyage_key:
            st.session_state['tracking_view_choice'] = None
        
        st.session_state['tracking_selected_voyage'] = voyage_key

        col1, col2, _ = st.columns([2, 2, 5])
        with col1:
            if st.button("🔗 Associated Farol References", key=f"btn_req_{voyage_key}"):
                # Limpa alterações pendentes ao clicar no botão
                st.session_state['tracking_view_choice'] = 'requests'
                st.session_state['tracking_discard_changes'] = True
                st.rerun()
        with col2:
            if st.button("📜 Voyage Records", key=f"btn_hist_{voyage_key}"):
                # Limpa alterações pendentes ao clicar no botão
                st.session_state['tracking_view_choice'] = 'history'
                st.session_state['tracking_discard_changes'] = True
                st.rerun()

        # Exibe o conteúdo com base na escolha
        if st.session_state.get('tracking_view_choice') == 'requests':
            st.subheader(f"Farol References para: {selected_row['navio']} - {selected_row['viagem']}")
            with st.spinner("Buscando requests..."):
                details_df = get_farol_references_details(selected_row['navio'], selected_row['viagem'], selected_row['terminal'])
                if not details_df.empty:
                    # Formata as colunas de data para o padrão DD-MM-YYYY HH:MM
                    date_cols_to_format = [col for col in details_df.columns if 'data' in col.lower() or 'date' in col.lower() or 'creation' in col.lower()]
                    for col in date_cols_to_format:
                        details_df[col] = pd.to_datetime(details_df[col], errors='coerce')
                        details_df[col] = details_df[col].dt.strftime('%d-%m-%Y %H:%M').replace({pd.NaT: 'N/A'})

                    rename_map = {
                        'farol_reference': 'Farol Reference', 'b_booking_reference': 'Booking Ref',
                        'b_booking_status': 'Booking Status', 'p_status': 'P Status',
                        'row_inserted_date': 'Latest Update', 's_creation_of_shipment': 'Shipment Requested Date',
                        'b_creation_of_booking': 'Booking Registered Date', 'b_booking_request_date': 'Booking Requested Date',
                        'b_data_estimativa_saida_etd': 'ETD', 'b_data_estimativa_chegada_eta': 'ETA'
                    }
                    display_df_details = details_df.rename(columns=rename_map)
                    display_cols = [
                        'Farol Reference', 'Booking Ref', 'Booking Status', 'P Status', 'Latest Update',
                        'Shipment Requested Date', 'Booking Registered Date', 'Booking Requested Date', 'ETD', 'ETA'
                    ]
                    final_cols = [col for col in display_cols if col in display_df_details.columns]
                    st.dataframe(display_df_details[final_cols], hide_index=True, use_container_width=True)
                else:
                    st.info("Nenhuma Farol Reference encontrada para esta viagem.")

        elif st.session_state.get('tracking_view_choice') == 'history':
            st.subheader(f"Histórico da Viagem: {selected_row['navio']} - {selected_row['viagem']}")
            with st.spinner("Buscando histórico..."):
                history_df = get_voyage_history(selected_row['navio'], selected_row['viagem'], selected_row['terminal'])
                if not history_df.empty:

                    # Formata as colunas de data para o padrão DD/MM/YYYY HH:MM (igual ao history.py)
                    date_cols_to_format = [col for col in history_df.columns if ('data' in col or 'date' in col) and col != 'data_source']
                    for col in date_cols_to_format:
                        history_df[col] = pd.to_datetime(history_df[col], errors='coerce')
                        # Aplica a formatação de data, preservando valores nulos (NaT),
                        # que o Streamlit renderiza como células vazias.
                        history_df[col] = history_df[col].dt.strftime('%d/%m/%Y %H:%M')

                    # Oculta a coluna ID e renomeia as outras para exibição (padrão history.py)
                    display_df = history_df.drop(columns=['id'], errors='ignore')
                    
                    rename_map = {
                        'navio': 'Vessel Name',
                        'viagem': 'Voyage Code',
                        'terminal': 'Port Terminal City',
                        'data_source': 'Source',
                        'data_estimativa_saida': 'ETD',
                        'data_estimativa_chegada': 'ETA',
                        'data_deadline': 'Deadline',
                        'data_draft_deadline': 'Draft Deadline',
                        'data_abertura_gate': 'Abertura Gate',
                        'data_abertura_gate_reefer': 'Abertura Gate Reefer',
                        'data_atracacao': 'Atracação (ATB)',
                        'data_partida': 'Partida (ATD)',
                        'data_chegada': 'Chegada (ATA)',
                        'data_estimativa_atracacao': 'Estimativa Atracação (ETB)',
                        'b_data_confirmacao_embarque': 'Confirmação Embarque',
                        'b_data_estimada_transbordo_etd': 'Estimativa Transbordo (ETD)',
                        'b_data_transbordo_atd': 'Transbordo (ATD)',
                        'b_data_chegada_destino_eta': 'Estimativa Chegada Destino (ETA)',
                        'b_data_chegada_destino_ata': 'Chegada no Destino (ATA)',
                        'row_inserted_date': 'Inserted Date',
                        'data_atualizacao': 'Data Atualização'
                    }
                    display_df = display_df.rename(columns=rename_map)

                    # Define a ordem de exibição das colunas (padrão history.py)
                    display_order = [
                        'Source', 
                        'Inserted Date',
                        'Vessel Name', 
                        'Voyage Code', 
                        'Port Terminal City', 
                        'Deadline', 
                        'Draft Deadline', 
                        'Abertura Gate', 
                        'Abertura Gate Reefer',
                        'ETD', 
                        'ETA', 
                        'Estimativa Atracação (ETB)', 
                        'Atracação (ATB)', 
                        'Partida (ATD)', 
                        'Chegada (ATA)', 
                        'Confirmação Embarque',
                        'Estimativa Transbordo (ETD)',
                        'Transbordo (ATD)',
                        'Estimativa Chegada Destino (ETA)',
                        'Chegada no Destino (ATA)',
                        'Data Atualização'
                    ]
                    
                    # Filtra a ordem para incluir apenas colunas que existem no dataframe
                    final_order = [col for col in display_order if col in display_df.columns]

                    # Força limpeza de cache para garantir que as mudanças sejam aplicadas (igual ao history.py)
                    st.cache_data.clear()
                    st.dataframe(display_df[final_order], use_container_width=True, hide_index=True)
                else:
                    st.info("Nenhum histórico de monitoramento encontrado para esta viagem.")


    changes = []
    edited_for_comparison = edited_df.drop(columns=['Selecionar'])
    original_for_comparison = df_filtered[edited_for_comparison.columns]

    if not original_for_comparison.reset_index(drop=True).equals(edited_for_comparison.reset_index(drop=True)):
        diff_mask = (original_for_comparison != edited_for_comparison) & ~(original_for_comparison.isnull() & edited_for_comparison.isnull())
        changed_rows_indices = diff_mask.any(axis=1)
        
        if changed_rows_indices.any():
            changed_df = edited_for_comparison[changed_rows_indices]
            original_changed_df = df_original.loc[changed_df.index]

            for index in changed_df.index:
                row_diff = diff_mask.loc[index]
                changed_cols = row_diff[row_diff].index.tolist()
                
                for col in changed_cols:
                    changes.append({
                        "id": original_changed_df.loc[index, "id"],
                        "vessel_name": original_changed_df.loc[index, "navio"],
                        "voyage_code": original_changed_df.loc[index, "viagem"],
                        "terminal": original_changed_df.loc[index, "terminal"],
                        "farol_references": original_changed_df.loc[index, "farol_references_list"],
                        "field_name": col,
                        "old_value": original_changed_df.loc[index, col],
                        "new_value": changed_df.loc[index, col]
                    })

    if changes and has_changes:
        st.subheader("Changes Summary")
        st.warning(f"{len(changes)} changes detected. Please review and save.")
        
        changes_df = pd.DataFrame(changes)
        st.dataframe(changes_df[["vessel_name", "voyage_code", "field_name", "old_value", "new_value"]].rename(
            columns={"vessel_name": "Vessel", "voyage_code": "Voyage", "field_name": "Changed Field", "old_value": "Old Value", "new_value": "New Value"}
        ), use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Save Changes", type="primary"):
                with st.spinner("Saving changes to the database..."):
                    # Iniciar batch para agrupar todas as mudanças
                    from database import begin_change_batch, end_change_batch
                    batch_id = begin_change_batch()
                    
                    try:
                        success, message = update_booking_from_voyage(changes)
                        
                        if success:
                            st.session_state.page_flash_message = {"type": "success", "message": "✅ Changes saved successfully!"}
                            st.rerun()
                        else:
                            st.error(f"❌ Failed to save: {message}")
                    except Exception as e:
                        st.error(f"❌ An unexpected error occurred: {e}")
                    finally:
                        # Encerrar batch
                        end_change_batch()
        with col2:
            if st.button("❌ Cancel"):
                st.session_state['tracking_discard_changes'] = True
                st.rerun()


def exibir_sync_logs():
    """
    Exibe a aba de logs de sincronização automática Ellox.
    """
    st.subheader("🔄 Logs de Sincronização Automática Ellox")
    
    try:
        # Estatísticas gerais
        with st.spinner("Carregando estatísticas..."):
            stats = get_sync_statistics(days=30)
        
        # Cards de métricas
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label="📊 Total de Execuções (30d)",
                value=f"{stats['total_executions']:,}",
                delta=None
            )
        
        with col2:
            st.metric(
                label="✅ Taxa de Sucesso",
                value=f"{stats['success_rate']:.1f}%",
                delta=None
            )
        
        with col3:
            st.metric(
                label="🚢 Viagens Ativas",
                value=f"{stats['active_voyages']:,}",
                delta=None
            )
        
        with col4:
            avg_time = stats['avg_execution_time_ms']
            st.metric(
                label="⏱️ Tempo Médio",
                value=f"{avg_time:.0f}ms",
                delta=None
            )
        
        st.divider()
        
        # Filtros
        st.subheader("🔍 Filtros")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            period = st.selectbox(
                "Período",
                options=["7 dias", "30 dias", "90 dias"],
                index=1
            )
            days = int(period.split()[0])
        
        with col2:
            status_filter = st.selectbox(
                "Status",
                options=["Todos", "SUCCESS", "NO_CHANGES", "API_ERROR", "AUTH_ERROR", "SAVE_ERROR", "ERROR"],
                index=0
            )
        
        with col3:
            vessel_filter = st.text_input("Navio (opcional)", placeholder="Digite parte do nome...")
        
        with col4:
            terminal_filter = st.text_input("Terminal (opcional)", placeholder="Digite parte do nome...")
        
        # Aplicar filtros
        filters = {}
        if days:
            filters['start_date'] = datetime.now() - timedelta(days=days)
        if status_filter != "Todos":
            filters['status'] = status_filter
        if vessel_filter:
            filters['vessel'] = vessel_filter
        if terminal_filter:
            filters['terminal'] = terminal_filter
        
        # Buscar logs
        with st.spinner("Carregando logs..."):
            logs = get_sync_logs(filters=filters, limit=1000)
        
        if not logs:
            st.info("Nenhum log encontrado para os filtros selecionados.")
            return
        
        # Converter para DataFrame
        df_logs = pd.DataFrame(logs)
        
        # Formatar colunas
        if not df_logs.empty:
            df_logs['sync_timestamp'] = pd.to_datetime(df_logs['sync_timestamp'])
            df_logs['execution_time_ms'] = df_logs['execution_time_ms'].round(2)
            
            # Mapear status para ícones
            status_icons = {
                'SUCCESS': '✅',
                'NO_CHANGES': 'ℹ️',
                'API_ERROR': '🔴',
                'AUTH_ERROR': '🔐',
                'SAVE_ERROR': '💾',
                'ERROR': '❌',
                'RETRY': '🔄'
            }
            
            df_logs['status_icon'] = df_logs['status'].map(status_icons).fillna('❓')
            df_logs['status_display'] = df_logs['status_icon'] + ' ' + df_logs['status']
        
        # Exibir tabela
        st.subheader(f"📋 Logs de Sincronização ({len(df_logs)} registros)")
        
        # Configurar colunas para exibição
        display_columns = {
            'sync_timestamp': 'Data/Hora',
            'vessel_name': 'Navio',
            'voyage_code': 'Viagem',
            'terminal': 'Terminal',
            'status_display': 'Status',
            'changes_detected': 'Mudanças',
            'execution_time_ms': 'Tempo (ms)',
            'retry_attempt': 'Tentativa',
            'error_message': 'Erro'
        }
        
        # Filtrar colunas que existem no DataFrame
        available_columns = {k: v for k, v in display_columns.items() if k in df_logs.columns}
        
        # Exibir tabela
        st.dataframe(
            df_logs[list(available_columns.keys())].rename(columns=available_columns),
            use_container_width=True,
            hide_index=True
        )
        
        # Botão de export
        if st.button("📥 Exportar CSV"):
            csv = df_logs.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"sync_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        
        # Resumo por status
        if not df_logs.empty:
            st.subheader("📊 Resumo por Status")
            status_summary = df_logs['status'].value_counts()
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.bar_chart(status_summary)
            
            with col2:
                for status, count in status_summary.items():
                    icon = status_icons.get(status, '❓')
                    percentage = (count / len(df_logs)) * 100
                    st.write(f"{icon} **{status}**: {count} ({percentage:.1f}%)")
    
    except Exception as e:
        st.error(f"❌ Erro ao carregar logs de sincronização: {str(e)}")
        st.error(f"Detalhes: {traceback.format_exc()}")


if __name__ == "__main__":
    st.set_page_config(layout="wide")
    exibir_tracking()
