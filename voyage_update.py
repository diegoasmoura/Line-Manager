
import streamlit as st
import pandas as pd
from sqlalchemy import text
import traceback

from database import get_database_connection, update_booking_from_voyage

@st.cache_data(ttl=300)
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
                        m.DATA_ESTIMATIVA_ATRACACAO,
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
                    lm.DATA_ESTIMATIVA_ATRACACAO,
                    LISTAGG(DISTINCT r.FAROL_REFERENCE, ', ') WITHIN GROUP (ORDER BY r.FAROL_REFERENCE) as "farol_references_list",
                    COUNT(DISTINCT r.FAROL_REFERENCE) as "farol_references_count"
                FROM latest_monitoring lm
                LEFT JOIN LogTransp.F_CON_RETURN_CARRIERS r ON (
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
                    lm.DATA_ESTIMATIVA_ATRACACAO
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

@st.cache_data(ttl=300)
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

def exibir_voyage_update_page():
    """
    Exibe a página para atualização manual de datas de viagem.
    """
    if "page_flash_message" in st.session_state:
        flash = st.session_state.pop("page_flash_message")
        st.success(flash["message"]) # Simplificado para apenas sucesso

    st.title("🚢 Atualização Manual de Datas de Viagem")

    if 'original_voyage_data' not in st.session_state:
        with st.spinner("Carregando dados de viagens..."):
            st.session_state.original_voyage_data = get_voyage_data_for_update()

    df_original = st.session_state.original_voyage_data

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

    column_config = {
        "id": None, "rn": None, "farol_references_list": None,
        "navio": st.column_config.TextColumn("Navio", disabled=True),
        "viagem": st.column_config.TextColumn("Viagem", disabled=True),
        "terminal": st.column_config.TextColumn("Terminal", disabled=True),
        "farol_references_count": st.column_config.NumberColumn("Refs", help="Número de Farol References associadas"),
        "data_estimativa_saida": st.column_config.DatetimeColumn("ETD", format="DD/MM/YYYY HH:mm"),
        "data_estimativa_chegada": st.column_config.DatetimeColumn("ETA", format="DD/MM/YYYY HH:mm"),
        "data_deadline": st.column_config.DatetimeColumn("Deadline", format="DD/MM/YYYY HH:mm"),
        "data_draft_deadline": st.column_config.DatetimeColumn("Draft Deadline", format="DD/MM/YYYY HH:mm"),
        "data_abertura_gate": st.column_config.DatetimeColumn("Abertura Gate", format="DD/MM/YYYY HH:mm"),
        "data_atracacao": st.column_config.DatetimeColumn("Atracação (ATB)", format="DD/MM/YYYY HH:mm"),
        "data_partida": st.column_config.DatetimeColumn("Partida (ATD)", format="DD/MM/YYYY HH:mm"),
        "data_chegada": st.column_config.DatetimeColumn("Chegada (ATA)", format="DD/MM/YYYY HH:mm"),
        "data_estimativa_atracacao": st.column_config.DatetimeColumn("Estimativa Atracação (ETB)", format="DD/MM/YYYY HH:mm"),
        "Selecionar": st.column_config.CheckboxColumn("Ver Refs", help="Selecione para ver as Farol References associadas")
    }
    
    # Reordenar colunas para exibição de forma segura
    display_order_preferred = ["Selecionar", "navio", "viagem", "terminal", "farol_references_count", "data_estimativa_saida", "data_estimativa_chegada", "data_deadline"] + [col for col in df_display.columns if col not in ["Selecionar", "navio", "viagem", "terminal", "farol_references_count", "data_estimativa_saida", "data_estimativa_chegada", "data_deadline", "id", "rn", "farol_references_list"]]
    
    # Filtra a lista de ordenação para garantir que todas as colunas existem no DataFrame
    display_order_safe = [col for col in display_order_preferred if col in df_display.columns]

    edited_df = st.data_editor(
        df_display[display_order_safe],
        column_config=column_config, use_container_width=True, num_rows="fixed", key="voyage_editor", hide_index=True
    )

    # Lógica para exibir detalhes das referências selecionadas
    selected_rows = edited_df[edited_df["Selecionar"] == True]
    if not selected_rows.empty:
        st.divider()
        for idx, row in selected_rows.iterrows():
            st.subheader(f"Farol References para: {row['navio']} - {row['viagem']}")
            details_df = get_farol_references_details(row['navio'], row['viagem'], row['terminal'])
            if not details_df.empty:
                # Renomeia colunas para exibição amigável
                rename_map = {
                    'farol_reference': 'Farol Reference',
                    'b_booking_reference': 'Booking Ref',
                    'b_booking_status': 'Booking Status',
                    'p_status': 'P Status',
                    'row_inserted_date': 'Latest Update',
                    's_creation_of_shipment': 'Shipment Creation',
                    'b_creation_of_booking': 'Booking Creation',
                    'b_booking_request_date': 'Booking Request Date',
                    'b_data_estimativa_saida_etd': 'ETD',
                    'b_data_estimativa_chegada_eta': 'ETA'
                }
                display_df = details_df.rename(columns=rename_map)
                
                # Garante a ordem e a presença das colunas
                display_cols = [
                    'Farol Reference', 'Booking Ref', 'Booking Status', 'P Status', 'Latest Update',
                    'Shipment Creation', 'Booking Creation', 'Booking Request Date', 'ETD', 'ETA'
                ]
                final_cols = [col for col in display_cols if col in display_df.columns]
                
                st.dataframe(display_df[final_cols], hide_index=True, use_container_width=True)
            else:
                st.info("Nenhuma Farol Reference encontrada para esta viagem.")

    # Lógica para detectar alterações
    changes = []

    # Prepara o DataFrame editado, removendo colunas de UI
    edited_for_comparison = edited_df.drop(columns=['Selecionar'])
    # Garante que o DataFrame original tenha exatamente as mesmas colunas e na mesma ordem do editado
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

    if changes:
        st.subheader("Resumo das Alterações")
        st.warning(f"{len(changes)} alterações detectadas. Verifique e clique em salvar.")
        
        changes_df = pd.DataFrame(changes)
        st.dataframe(changes_df[["vessel_name", "voyage_code", "field_name", "old_value", "new_value"]].rename(
            columns={"vessel_name": "Navio", "voyage_code": "Viagem", "field_name": "Campo Alterado", "old_value": "Valor Antigo", "new_value": "Novo Valor"}
        ), use_container_width=True)

        if st.button("💾 Salvar Alterações", type="primary"):
            with st.spinner("Salvando alterações no banco de dados..."):
                try:
                    success, message = update_booking_from_voyage(changes)
                    
                    if success:
                        st.session_state.page_flash_message = {"type": "success", "message": "✅ Alterações salvas com sucesso!"}
                        if 'original_voyage_data' in st.session_state: del st.session_state.original_voyage_data
                        st.rerun()
                    else:
                        st.error(f"❌ Falha ao salvar: {message}")
                except Exception as e:
                    st.error(f"❌ Ocorreu um erro inesperado: {e}")

if __name__ == "__main__":
    st.set_page_config(layout="wide")
    exibir_voyage_update_page()
