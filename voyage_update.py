import streamlit as st
import pandas as pd
from sqlalchemy import text
import traceback

# Presume que as funções de banco de dados estarão disponíveis
from database import get_database_connection, update_booking_from_voyage

def get_voyage_data_for_update():
    """
    Busca o último registro de cada combinação única (Vessel + Voyage + Terminal)
    e as Farol References associadas para a tela de atualização.
    """
    try:
        with get_database_connection() as conn:
            # A convenção do driver Oracle com pandas retorna colunas em minúsculas
            query = text("""
                WITH latest_monitoring AS (
                    SELECT
                        m.ID,
                        m.NAVIO,
                        m.VIAGEM,
                        m.TERMINAL,
                        m.DATA_ESTIMATIVA_SAIDA,
                        m.DATA_ESTIMATIVA_CHEGADA,
                        m.DATA_DEADLINE,
                        m.DATA_DRAFT_DEADLINE,
                        m.DATA_ABERTURA_GATE,
                        m.DATA_ATRACACAO,
                        m.DATA_PARTIDA,
                        m.DATA_CHEGADA,
                        m.DATA_ESTIMATIVA_ATRACACAO,
                        ROW_NUMBER() OVER (
                            PARTITION BY UPPER(m.NAVIO), UPPER(m.VIAGEM), UPPER(m.TERMINAL)
                            ORDER BY NVL(m.DATA_ATUALIZACAO, m.ROW_INSERTED_DATE) DESC
                        ) as rn
                    FROM LogTransp.F_ELLOX_TERMINAL_MONITORINGS m
                )
                SELECT
                    lm.ID,
                    lm.NAVIO,
                    lm.VIAGEM,
                    lm.TERMINAL,
                    lm.DATA_ESTIMATIVA_SAIDA,
                    lm.DATA_ESTIMATIVA_CHEGADA,
                    lm.DATA_DEADLINE,
                    lm.DATA_DRAFT_DEADLINE,
                    lm.DATA_ABERTURA_GATE,
                    lm.DATA_ATRACACAO,
                    lm.DATA_PARTIDA,
                    lm.DATA_CHEGADA,
                    lm.DATA_ESTIMATIVA_ATRACACAO,
                    LISTAGG(DISTINCT r.FAROL_REFERENCE, ', ') WITHIN GROUP (ORDER BY r.FAROL_REFERENCE) as FAROL_REFERENCES
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

            # O driver retorna colunas em minúsculas. Não é necessário converter para maiúsculas.

            # Converte colunas de data para datetime
            date_columns = [col for col in df.columns if 'data' in col.lower()]
            for col in date_columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')

            return df
    except Exception as e:
        st.error(f"❌ Erro ao buscar dados de monitoramento: {str(e)}")
        st.error(f"Detalhes do erro: {traceback.format_exc()}")
        return pd.DataFrame()

def exibir_voyage_update_page():
    """
    Exibe a página para atualização manual de datas de viagem.
    """
    st.title("🚢 Atualização Manual de Datas de Viagem")

    if 'original_voyage_data' not in st.session_state:
        with st.spinner("Carregando dados de viagens..."):
            st.session_state.original_voyage_data = get_voyage_data_for_update()

    df_original = st.session_state.original_voyage_data

    if df_original.empty:
        st.info("Nenhum dado de viagem encontrado para atualização.")
        return

    # Filtros usando colunas em minúsculas
    st.subheader("🔍 Filtros")
    col1, col2 = st.columns(2)
    with col1:
        vessel_filter = st.multiselect(
            "Filtrar por Navio",
            options=sorted(df_original["navio"].dropna().unique().tolist()),
            key="voyage_update_vessel_filter"
        )
    with col2:
        terminal_filter = st.multiselect(
            "Filtrar por Terminal",
            options=sorted(df_original["terminal"].dropna().unique().tolist()),
            key="voyage_update_terminal_filter"
        )

    df_filtered = df_original.copy()
    if vessel_filter:
        df_filtered = df_filtered[df_filtered["navio"].isin(vessel_filter)]
    if terminal_filter:
        df_filtered = df_filtered[df_filtered["terminal"].isin(terminal_filter)]

    st.info("Edite as datas diretamente na grade. As alterações serão destacadas. Clique em 'Salvar Alterações' para confirmar.")

    # Configuração das colunas do data_editor usando chaves em minúsculas
    column_config = {
        "id": None,
        "rn": None,
        "navio": st.column_config.TextColumn("Navio", disabled=True, help="Nome do Navio"),
        "viagem": st.column_config.TextColumn("Viagem", disabled=True, help="Código da Viagem"),
        "terminal": st.column_config.TextColumn("Terminal", disabled=True, help="Terminal de Operação"),
        "farol_references": st.column_config.TextColumn("Farol References", help="Referências associadas a esta viagem.", disabled=True, width="large"),
        "data_estimativa_saida": st.column_config.DatetimeColumn("ETD", format="DD/MM/YYYY HH:mm"),
        "data_estimativa_chegada": st.column_config.DatetimeColumn("ETA", format="DD/MM/YYYY HH:mm"),
        "data_deadline": st.column_config.DatetimeColumn("Deadline", format="DD/MM/YYYY HH:mm"),
        "data_draft_deadline": st.column_config.DatetimeColumn("Draft Deadline", format="DD/MM/YYYY HH:mm"),
        "data_abertura_gate": st.column_config.DatetimeColumn("Abertura Gate", format="DD/MM/YYYY HH:mm"),
        "data_atracacao": st.column_config.DatetimeColumn("Atracação (ATB)", format="DD/MM/YYYY HH:mm"),
        "data_partida": st.column_config.DatetimeColumn("Partida (ATD)", format="DD/MM/YYYY HH:mm"),
        "data_chegada": st.column_config.DatetimeColumn("Chegada (ATA)", format="DD/MM/YYYY HH:mm"),
        "data_estimativa_atracacao": st.column_config.DatetimeColumn("Estimativa Atracação (ETB)", format="DD/MM/YYYY HH:mm"),
    }

    edited_df = st.data_editor(
        df_filtered,
        column_config=column_config,
        use_container_width=True,
        num_rows="fixed",
        key="voyage_editor",
        hide_index=True
    )

    # Lógica para detectar alterações
    changes = []
    if not df_filtered.reset_index(drop=True).equals(edited_df.reset_index(drop=True)):
        diff_mask = (df_filtered != edited_df) & ~(df_filtered.isnull() & edited_df.isnull())
        changed_rows_indices = diff_mask.any(axis=1)
        
        if changed_rows_indices.any():
            changed_df = edited_df[changed_rows_indices]
            original_changed_df = df_filtered[changed_rows_indices]

            for index in changed_df.index:
                row_diff = diff_mask.loc[index]
                changed_cols = row_diff[row_diff].index.tolist()
                
                for col in changed_cols:
                    changes.append({
                        "id": original_changed_df.loc[index, "id"],
                        "vessel_name": original_changed_df.loc[index, "navio"],
                        "voyage_code": original_changed_df.loc[index, "viagem"],
                        "terminal": original_changed_df.loc[index, "terminal"],
                        "farol_references": original_changed_df.loc[index, "farol_references"],
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
                        st.success("✅ Alterações salvas com sucesso!")
                        del st.session_state.original_voyage_data
                        st.rerun()
                    else:
                        st.error(f"❌ Falha ao salvar: {message}")
                except Exception as e:
                    st.error(f"❌ Ocorreu um erro inesperado: {e}")
                    st.error(f"Detalhes: {traceback.format_exc()}")
    else:
        st.caption("Nenhuma alteração detectada.")

if __name__ == "__main__":
    st.set_page_config(layout="wide")
    exibir_voyage_update_page()