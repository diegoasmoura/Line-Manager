import streamlit as st
import pandas as pd
from database import get_database_connection
from sqlalchemy import text
import traceback

def get_voyage_monitoring_with_farol_references():
    """
    Busca os 10 registros mais recentes e atualizados de monitoramento da Ellox com Farol References associados.
    Retorna DataFrame com colunas de monitoramento + Farol References relacionados.
    """
    try:
        conn = get_database_connection()
        
        # Query principal que busca os 10 registros mais recentes e atualizados
        query = text("""
            SELECT DISTINCT
                m.ID,
                m.NAVIO as Vessel_Name,
                m.VIAGEM as Voyage_Code,
                m.TERMINAL as Terminal,
                m.AGENCIA as Agency,
                m.DATA_DEADLINE as Data_Deadline,
                m.DATA_DRAFT_DEADLINE as Data_Draft_Deadline,
                m.DATA_ABERTURA_GATE as Data_Abertura_Gate,
                m.DATA_ABERTURA_GATE_REEFER as Data_Abertura_Gate_Reefer,
                m.DATA_ESTIMATIVA_SAIDA as Data_Estimativa_Saida,
                m.DATA_ESTIMATIVA_CHEGADA as Data_Estimativa_Chegada,
                m.DATA_ATUALIZACAO as Data_Atualizacao,
                m.CNPJ_TERMINAL as CNPJ_Terminal,
                m.DATA_CHEGADA as Data_Chegada,
                m.DATA_ESTIMATIVA_ATRACACAO as Data_Estimativa_Atracacao,
                m.DATA_ATRACACAO as Data_Atracacao,
                m.DATA_PARTIDA as Data_Partida,
                m.ROW_INSERTED_DATE as Row_Inserted_Date,
                LISTAGG(DISTINCT r.FAROL_REFERENCE, ', ') WITHIN GROUP (ORDER BY r.FAROL_REFERENCE) as Farol_References
            FROM F_ELLOX_TERMINAL_MONITORINGS m
            LEFT JOIN LogTransp.F_CON_RETURN_CARRIERS r ON (
                UPPER(m.NAVIO) = UPPER(r.B_VESSEL_NAME) 
                AND UPPER(m.VIAGEM) = UPPER(r.B_VOYAGE_CODE)
                AND UPPER(m.TERMINAL) = UPPER(r.B_TERMINAL)
                AND r.FAROL_REFERENCE IS NOT NULL
            )
            WHERE m.DATA_ATUALIZACAO IS NOT NULL  -- Apenas registros que foram atualizados pela API
            GROUP BY 
                m.ID, m.NAVIO, m.VIAGEM, m.TERMINAL, m.AGENCIA,
                m.DATA_DEADLINE, m.DATA_DRAFT_DEADLINE, m.DATA_ABERTURA_GATE,
                m.DATA_ABERTURA_GATE_REEFER, m.DATA_ESTIMATIVA_SAIDA,
                m.DATA_ESTIMATIVA_CHEGADA, m.DATA_ATUALIZACAO, m.CNPJ_TERMINAL,
                m.DATA_CHEGADA, m.DATA_ESTIMATIVA_ATRACACAO, m.DATA_ATRACACAO,
                m.DATA_PARTIDA, m.ROW_INSERTED_DATE
            ORDER BY m.DATA_ATUALIZACAO DESC
            FETCH FIRST 10 ROWS ONLY
        """)
        
        result = conn.execute(query).mappings().fetchall()
        conn.close()
        
        df = pd.DataFrame([dict(r) for r in result]) if result else pd.DataFrame()
        
        # Normaliza nomes das colunas para maiúsculas
        if not df.empty:
            df.columns = [str(c).upper() for c in df.columns]
        
        # Converte colunas de data para datetime
        date_columns = [
            'DATA_DEADLINE', 'DATA_DRAFT_DEADLINE', 'DATA_ABERTURA_GATE',
            'DATA_ABERTURA_GATE_REEFER', 'DATA_ESTIMATIVA_SAIDA', 'DATA_ESTIMATIVA_CHEGADA',
            'DATA_ATUALIZACAO', 'DATA_CHEGADA', 'DATA_ESTIMATIVA_ATRACACAO',
            'DATA_ATRACACAO', 'DATA_PARTIDA', 'ROW_INSERTED_DATE'
        ]
        
        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        return df
        
    except Exception as e:
        st.error(f"❌ Erro ao buscar dados de monitoramento: {str(e)}")
        st.error(f"Detalhes: {traceback.format_exc()}")
        return pd.DataFrame()

def update_voyage_monitoring_data(monitoring_id, updates):
    """
    Atualiza dados de monitoramento na tabela F_ELLOX_TERMINAL_MONITORINGS.
    
    Args:
        monitoring_id: ID do registro a ser atualizado
        updates: Dict com as colunas e valores a serem atualizados
    """
    try:
        conn = get_database_connection()
        
        # Monta a query de UPDATE dinamicamente
        set_clauses = []
        params = {"monitoring_id": monitoring_id}
        
        for column, value in updates.items():
            if value is not None and value != "":
                set_clauses.append(f"{column} = :{column}")
                params[column] = value
            else:
                set_clauses.append(f"{column} = NULL")
        
        if not set_clauses:
            st.warning("⚠️ Nenhuma alteração foi feita.")
            return False
        
        # Adiciona timestamp de atualização
        set_clauses.append("DATA_ATUALIZACAO = SYSDATE")
        
        update_query = text(f"""
            UPDATE F_ELLOX_TERMINAL_MONITORINGS 
            SET {', '.join(set_clauses)}
            WHERE ID = :monitoring_id
        """)
        
        result = conn.execute(update_query, params)
        conn.commit()
        conn.close()
        
        if result.rowcount > 0:
            st.success(f"✅ Dados atualizados com sucesso para o registro ID {monitoring_id}")
            return True
        else:
            st.error(f"❌ Nenhum registro foi atualizado para o ID {monitoring_id}")
            return False
            
    except Exception as e:
        st.error(f"❌ Erro ao atualizar dados: {str(e)}")
        st.error(f"Detalhes: {traceback.format_exc()}")
        return False

def calculate_column_width(df, column_name):
    """Calcula largura dinâmica baseada no conteúdo e título da coluna"""
    if column_name not in df.columns:
        return "small"
    
    title_length = len(column_name)
    sample_size = min(10, len(df))
    
    if sample_size > 0:
        content_lengths = df[column_name].dropna().astype(str).str.len()
        max_content_length = content_lengths.max() if len(content_lengths) > 0 else 0
    else:
        max_content_length = 0
    
    total_length = max(title_length, max_content_length)
    
    if total_length <= 12:
        return "small"
    elif total_length <= 20:
        return "medium"
    else:
        return "large"

def generate_column_config(df):
    """Gera configuração de colunas com larguras dinâmicas"""
    config = {
        "ID": None,  # Sempre oculta
        "Selecionar": st.column_config.CheckboxColumn("Select", help="Selecione uma linha para editar", pinned="left"),
    }
    
    for col in df.columns:
        if col in config:
            continue
        
        # Larguras específicas para colunas específicas
        if col == "VESSEL_NAME":
            width = "large"
        elif col == "VOYAGE_CODE":
            width = "medium"
        elif col == "TERMINAL":
            width = "large"
        elif col == "FAROL_REFERENCES":
            width = "large"
        elif any(date_keyword in col.lower() for date_keyword in ["data", "date"]):
            width = "medium"
        else:
            width = calculate_column_width(df, col)
        
        if any(date_keyword in col.lower() for date_keyword in ["data", "date"]):
            config[col] = st.column_config.DatetimeColumn(col, width=width)
        else:
            config[col] = st.column_config.TextColumn(col, width=width)
    
    return config

def exibir_voyage_monitoring():
    """Exibe a interface principal de gerenciamento de monitoramento de viagens"""
    st.title("🚢 Voyage Monitoring Management")
    
    st.markdown("""
    <div style="background-color: #f8f9fa; border-left: 4px solid #007bff; padding: 1rem; margin-bottom: 1.5rem; border-radius: 0 8px 8px 0;">
        <h4 style="margin: 0 0 0.5rem 0; color: #007bff;">📊 Dados de Monitoramento Mais Recentes (API Ellox)</h4>
        <p style="margin: 0; color: #6c757d; font-size: 0.9em;">
            Esta tela exibe os <strong>10 registros mais recentes e atualizados</strong> coletados com sucesso da API Ellox. 
            Aqui você pode visualizar e editar informações de navios, viagens e terminais, incluindo os Farol References associados.
            <br><br>
            <strong>✅ Apenas dados efetivamente coletados pela API são exibidos.</strong>
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Carrega os dados
    with st.spinner("🔄 Carregando dados de monitoramento..."):
        df = get_voyage_monitoring_with_farol_references()
    
    if df.empty:
        st.info("📋 Nenhum registro de monitoramento atualizado pela API Ellox encontrado. Os dados aparecerão aqui quando a API for executada com sucesso.")
        return
    
    st.subheader(f"📊 Últimos 10 Registros Atualizados pela API Ellox ({len(df)} registros)")
    
    # Configuração das colunas
    column_config = generate_column_config(df)
    
    # Data editor
    edited_df = st.data_editor(
        df,
        column_config=column_config,
        use_container_width=True,
        num_rows="dynamic",
        key="voyage_monitoring_editor"
    )
    
    # Verifica se há alterações
    if not edited_df.equals(df):
        # Identifica linhas alteradas
        changed_rows = edited_df[~edited_df.index.isin(df.index) | ~edited_df.equals(df)]
        
        if not changed_rows.empty:
            st.subheader("📝 Alterações Detectadas")
            
            # Mostra apenas as linhas alteradas
            st.dataframe(changed_rows, use_container_width=True)
            
            # Botão para salvar alterações
            col1, col2, col3 = st.columns([1, 1, 2])
            
            with col1:
                if st.button("💾 Salvar Alterações", type="primary"):
                    success_count = 0
                    total_changes = 0
                    
                    for idx, row in changed_rows.iterrows():
                        if idx in df.index:  # Linha existente sendo editada
                            original_row = df.loc[idx]
                            updates = {}
                            
                            # Compara cada coluna para identificar mudanças
                            for col in df.columns:
                                if col not in ["ID", "SELECIONAR", "FAROL_REFERENCES"]:  # Exclui colunas não editáveis
                                    if pd.isna(original_row[col]) and pd.isna(row[col]):
                                        continue
                                    elif original_row[col] != row[col]:
                                        updates[col] = row[col]
                            
                            if updates:
                                total_changes += 1
                                if update_voyage_monitoring_data(row["ID"], updates):
                                    success_count += 1
                    
                    if total_changes > 0:
                        st.success(f"✅ {success_count}/{total_changes} alterações salvas com sucesso!")
                        st.rerun()
                    else:
                        st.warning("⚠️ Nenhuma alteração válida foi detectada.")
            
            with col2:
                if st.button("🔄 Cancelar"):
                    st.rerun()
    
    # Estatísticas
    st.subheader("📈 Estatísticas")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total de Navios", len(df["VESSEL_NAME"].unique()))
    
    with col2:
        st.metric("Total de Viagens", len(df["VOYAGE_CODE"].unique()))
    
    with col3:
        st.metric("Total de Terminais", len(df["TERMINAL"].unique()))
    
    with col4:
        total_farol_refs = df["FAROL_REFERENCES"].str.count(",").sum() + len(df[df["FAROL_REFERENCES"].notna()])
        st.metric("Total de Farol References", int(total_farol_refs))
    
    # Filtros
    st.subheader("🔍 Filtros")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        vessel_filter = st.selectbox(
            "Filtrar por Navio",
            ["Todos"] + sorted(df["VESSEL_NAME"].dropna().unique().tolist())
        )
    
    with col2:
        terminal_filter = st.selectbox(
            "Filtrar por Terminal",
            ["Todos"] + sorted(df["TERMINAL"].dropna().unique().tolist())
        )
    
    with col3:
        has_farol_refs = st.selectbox(
            "Farol References",
            ["Todos", "Com Referências", "Sem Referências"]
        )
    
    # Aplica filtros
    filtered_df = df.copy()
    
    if vessel_filter != "Todos":
        filtered_df = filtered_df[filtered_df["VESSEL_NAME"] == vessel_filter]
    
    if terminal_filter != "Todos":
        filtered_df = filtered_df[filtered_df["TERMINAL"] == terminal_filter]
    
    if has_farol_refs == "Com Referências":
        filtered_df = filtered_df[filtered_df["FAROL_REFERENCES"].notna()]
    elif has_farol_refs == "Sem Referências":
        filtered_df = filtered_df[filtered_df["FAROL_REFERENCES"].isna()]
    
    if len(filtered_df) != len(df):
        st.subheader(f"📊 Resultados Filtrados ({len(filtered_df)} registros)")
        st.dataframe(filtered_df, use_container_width=True)
