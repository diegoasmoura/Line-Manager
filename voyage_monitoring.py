import streamlit as st
import pandas as pd
from database import get_database_connection
from sqlalchemy import text
import traceback
from ellox_api import get_default_api_client

def get_api_status_indicator():
    """
    Retorna indicador visual do status da API para exibição
    
    Returns:
        Tuple com (status_text, status_color, status_icon)
    """
    # Inicializar cliente com credenciais padrão
    client = get_default_api_client()
    
    if not client.authenticated:
        return ("API Desconectada", "red", "🔴")
    
    # Testar conexão
    try:
        test_result = client.test_connection()
        
        if test_result.get("success"):
            response_time = test_result.get("response_time", 0)
            if response_time < 1.0:
                return (f"API Online ({response_time:.2f}s)", "green", "🟢")
            else:
                return (f"API Lenta ({response_time:.2f}s)", "orange", "🟡")
        else:
            error = test_result.get("error", "Erro desconhecido")
            return (f"API Erro: {error}", "red", "🔴")
            
    except Exception as e:
        return (f"Erro no Teste: {str(e)}", "red", "🔴")

def display_api_status_inline():
    """Exibe indicador de status da API inline (para ficar na mesma linha do título)"""
    status_text, status_color, status_icon = get_api_status_indicator()
    
    # Botão de status da API compacto
    if st.button(
        f"{status_icon} {status_text}",
        help="Clique para ver detalhes da API Ellox",
        type="secondary" if status_color == "green" else "primary",
        key="api_status_inline"
    ):
        # Abrir modal/expander com detalhes
        st.session_state.show_api_details = True
    
    # Mostrar detalhes se solicitado
    if st.session_state.get("show_api_details", False):
        display_api_details_modal()

def display_api_status():
    """Exibe indicador de status da API no canto superior direito"""
    status_text, status_color, status_icon = get_api_status_indicator()
    
    # Criar um container no topo da página para o botão
    col1, col2, col3 = st.columns([6, 2, 1])
    
    with col3:
        # Botão de status da API
        if st.button(
            f"{status_icon} {status_text}",
            help="Clique para ver detalhes da API Ellox",
            type="secondary" if status_color == "green" else "primary"
        ):
            # Abrir modal/expander com detalhes
            st.session_state.show_api_details = True
    
    # Mostrar detalhes se solicitado
    if st.session_state.get("show_api_details", False):
        display_api_details_modal()

def display_api_details_modal():
    """Exibe modal com detalhes da API e configurações"""
    st.markdown("---")
    
    with st.expander("🔧 Status da API Ellox", expanded=True):
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("### 📋 Status Detalhado")
            
            # Obter status atual
            client = get_default_api_client()
            
            # Informações básicas
            st.info(f"**URL Base:** `{client.base_url}`")
            st.info(f"**Email:** `{client.email}`")
            st.info(f"**Senha:** `{'*' * len(client.password) if client.password else 'Não configurada'}`")
            
            # Status de autenticação
            if client.authenticated:
                st.success("✅ **Autenticado com sucesso**")
                if client.api_key:
                    st.code(f"Token: {client.api_key[:20]}...")
            else:
                st.error("❌ **Falha na autenticação**")
            
            # Teste de conectividade
            if st.button("🔄 Testar Conectividade"):
                with st.spinner("Testando..."):
                    test_result = client.test_connection()
                    
                    if test_result.get("success"):
                        st.success(f"✅ **Conectado!** Tempo: {test_result.get('response_time', 0):.2f}s")
                    else:
                        st.error(f"❌ **Erro:** {test_result.get('error', 'Desconhecido')}")
        
        with col2:
            st.markdown("### 📊 Estatísticas")
            
            # Estatísticas da API
            try:
                # Teste rápido para obter estatísticas
                test_result = client.test_connection()
                if test_result.get("success"):
                    response_time = test_result.get("response_time", 0)
                    st.metric("Tempo de Resposta", f"{response_time:.2f}s")
                    
                    if response_time < 1.0:
                        st.success("🟢 Excelente")
                    elif response_time < 3.0:
                        st.warning("🟡 Aceitável")
                    else:
                        st.error("🔴 Lento")
                else:
                    st.error("❌ Indisponível")
            except:
                st.error("❌ Erro no teste")
        
        # Botão para fechar
        if st.button("❌ Fechar Detalhes"):
            st.session_state.show_api_details = False
            st.rerun()

def get_farol_references_details(vessel_name, voyage_code, terminal):
    """Busca detalhes dos Farol References para uma combinação específica"""
    try:
        with get_database_connection() as conn:
            # Query para buscar Farol References por Vessel + Voyage (sem filtro de Terminal)
            query = """
            SELECT 
                r.FAROL_REFERENCE,
                r.B_BOOKING_REFERENCE,
                r.B_BOOKING_STATUS,
                r.P_STATUS,
                r.B_VESSEL_NAME,
                r.B_VOYAGE_CODE,
                r.B_TERMINAL,
                r.B_DATA_ESTIMATIVA_SAIDA_ETD,
                r.B_DATA_ESTIMATIVA_CHEGADA_ETA,
                r.ROW_INSERTED_DATE
            FROM LogTransp.F_CON_RETURN_CARRIERS r
            WHERE UPPER(TRIM(r.B_VESSEL_NAME)) = UPPER(TRIM(:vessel_name))
            AND UPPER(TRIM(r.B_VOYAGE_CODE)) = UPPER(TRIM(:voyage_code))
            AND r.FAROL_REFERENCE IS NOT NULL
            ORDER BY r.ROW_INSERTED_DATE DESC
            """
            
            result = conn.execute(text(query), {
                'vessel_name': vessel_name,
                'voyage_code': voyage_code
            })
            rows = result.fetchall()
            
            if not rows:
                return pd.DataFrame()
            
            # Converte para DataFrame
            df = pd.DataFrame(rows)
            
            # Normaliza nomes das colunas para maiúsculas
            df.columns = [col.upper() for col in df.columns]
            
            # Converte colunas de data para datetime
            date_columns = [col for col in df.columns if 'DATA' in col or 'DATE' in col]
            for col in date_columns:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')
            
            return df
            
    except Exception as e:
        st.error(f"Erro ao buscar detalhes dos Farol References: {str(e)}")
        return pd.DataFrame()

def get_voyage_monitoring_with_farol_references():
    """
    Busca o último registro de cada combinação única (Vessel + Voyage + Terminal) de monitoramento da Ellox.
    Se não houver dados da API, mostra apenas as 3 primeiras colunas preenchidas e as outras vazias.
    Retorna DataFrame com colunas de monitoramento + Farol References relacionados.
    """
    try:
        conn = get_database_connection()
        
        # Query principal que busca o último registro de cada combinação única
        query = text("""
            WITH latest_monitoring AS (
                SELECT 
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
                    ROW_NUMBER() OVER (
                        PARTITION BY UPPER(m.NAVIO), UPPER(m.VIAGEM), UPPER(m.TERMINAL) 
                        ORDER BY NVL(m.DATA_ATUALIZACAO, m.ROW_INSERTED_DATE) DESC
                    ) as rn
                FROM F_ELLOX_TERMINAL_MONITORINGS m
            )
            SELECT 
                lm.ID,
                lm.Vessel_Name,
                lm.Voyage_Code,
                lm.Terminal,
                lm.Agency,
                lm.Data_Deadline,
                lm.Data_Draft_Deadline,
                lm.Data_Abertura_Gate,
                lm.Data_Abertura_Gate_Reefer,
                lm.Data_Estimativa_Saida,
                lm.Data_Estimativa_Chegada,
                lm.Data_Atualizacao,
                lm.CNPJ_Terminal,
                lm.Data_Chegada,
                lm.Data_Estimativa_Atracacao,
                lm.Data_Atracacao,
                lm.Data_Partida,
                lm.Row_Inserted_Date,
                LISTAGG(DISTINCT r.FAROL_REFERENCE, ', ') WITHIN GROUP (ORDER BY r.FAROL_REFERENCE) as Farol_References
            FROM latest_monitoring lm
            LEFT JOIN LogTransp.F_CON_RETURN_CARRIERS r ON (
                UPPER(lm.Vessel_Name) = UPPER(r.B_VESSEL_NAME) 
                AND UPPER(lm.Voyage_Code) = UPPER(r.B_VOYAGE_CODE)
                AND UPPER(lm.Terminal) = UPPER(r.B_TERMINAL)
                AND r.FAROL_REFERENCE IS NOT NULL
            )
            WHERE lm.rn = 1  -- Apenas o último registro de cada combinação
            GROUP BY 
                lm.ID, lm.Vessel_Name, lm.Voyage_Code, lm.Terminal, lm.Agency,
                lm.Data_Deadline, lm.Data_Draft_Deadline, lm.Data_Abertura_Gate,
                lm.Data_Abertura_Gate_Reefer, lm.Data_Estimativa_Saida,
                lm.Data_Estimativa_Chegada, lm.Data_Atualizacao, lm.CNPJ_Terminal,
                lm.Data_Chegada, lm.Data_Estimativa_Atracacao, lm.Data_Atracacao,
                lm.Data_Partida, lm.Row_Inserted_Date
            ORDER BY NVL(lm.Data_Atualizacao, lm.Row_Inserted_Date) DESC
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

def format_farol_references(farol_refs):
    """Formata Farol References para exibição expandida"""
    if not farol_refs or pd.isna(farol_refs) or str(farol_refs).strip() == "":
        return "📋 Nenhuma referência"
    
    # Divide as referências por vírgula e formata cada uma
    refs_list = [ref.strip() for ref in str(farol_refs).split(',') if ref.strip()]
    
    if len(refs_list) == 1:
        return f"📋 {refs_list[0]}"
    else:
        # Formata múltiplas referências com quebras de linha
        formatted_refs = []
        for i, ref in enumerate(refs_list, 1):
            formatted_refs.append(f"📋 {i}. {ref}")
        return "\n".join(formatted_refs)

def generate_column_config(df):
    """Gera configuração de colunas com larguras dinâmicas seguindo o padrão do sistema"""
    
    # Mapeamento de colunas para títulos em português (seguindo padrão do sistema)
    column_titles = {
        "VESSEL_NAME": "Vessel Name",
        "VOYAGE_CODE": "Voyage Code", 
        "TERMINAL": "Terminal",
        "AGENCY": "Agency",
        "DATA_DEADLINE": "Data Deadline",
        "DATA_DRAFT_DEADLINE": "Data Draft Deadline",
        "DATA_ABERTURA_GATE": "Data Abertura Gate",
        "DATA_ABERTURA_GATE_REEFER": "Data Abertura Gate Reefer",
        "DATA_ESTIMATIVA_SAIDA": "Data Estimativa Saída",
        "DATA_ESTIMATIVA_CHEGADA": "Data Estimativa Chegada",
        "DATA_ATUALIZACAO": "Data Atualização",
        "CNPJ_TERMINAL": "CNPJ Terminal",
        "DATA_CHEGADA": "Data Chegada",
        "DATA_ESTIMATIVA_ATRACACAO": "Data Estimativa Atracação",
        "DATA_ATRACACAO": "Data Atracação",
        "DATA_PARTIDA": "Data Partida",
        "ROW_INSERTED_DATE": "Row Inserted Date",
        "FAROL_REFERENCES": "Farol References"
    }
    
    config = {
        "ID": None,  # Sempre oculta
        "FAROL_REFERENCES": None,  # Ocultar coluna Farol References
        "Selecionar": st.column_config.CheckboxColumn("Select", help="Selecione uma linha para ver detalhes dos Farol References", pinned="left"),
    }
    
    for col in df.columns:
        if col in config:
            continue
        
        # Obtém o título em português ou usa o nome da coluna
        title = column_titles.get(col, col.replace("_", " ").title())
        
        # Larguras específicas para colunas específicas
        if col in ["VESSEL_NAME", "VOYAGE_CODE", "TERMINAL", "AGENCY"]:
            width = None  # Largura automática baseada no conteúdo
        else:
            width = "medium"
        
        if any(date_keyword in col.lower() for date_keyword in ["data", "date"]):
            config[col] = st.column_config.DatetimeColumn(title, width=width)
        else:
            config[col] = st.column_config.TextColumn(title, width=width)
    
    return config

def exibir_voyage_monitoring():
    """Exibe a interface principal de gerenciamento de monitoramento de viagens"""
    # Layout com título e botão de status da API na mesma linha
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.title("🚢 Voyage Monitoring Management")
    
    with col2:
        # Exibir indicador de status da API na mesma linha do título
        st.markdown("<br>", unsafe_allow_html=True)  # Espaçamento para alinhar com o título
        display_api_status_inline()
    
    
    # Carrega os dados
    with st.spinner("🔄 Carregando dados de monitoramento..."):
        df = get_voyage_monitoring_with_farol_references()
    
    if df.empty:
        st.info("📋 Nenhuma combinação única de navio, viagem e terminal encontrada. Os dados aparecerão aqui quando houver registros de monitoramento.")
        return
    
    # Estatísticas em colunas - PARTE SUPERIOR
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
    
    # Filtros - PARTE SUPERIOR
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
    
    # Exibe dados filtrados
    if len(filtered_df) != len(df):
        st.subheader(f"📊 Resultados Filtrados ({len(filtered_df)} registros)")
        display_df = filtered_df
    else:
        st.subheader(f"📊 Último Registro por Combinação ({len(df)} combinações únicas)")
        display_df = df
    
    # Formatação removida - coluna FAROL_REFERENCES não é mais exibida
    
    # Adiciona coluna de seleção se não existir
    if "Selecionar" not in display_df.columns:
        display_df["Selecionar"] = False
    
    # Configuração das colunas
    column_config = generate_column_config(display_df)
    
    # Data editor
    edited_df = st.data_editor(
        display_df,
        column_config=column_config,
        use_container_width=True,
        num_rows="fixed",
        hide_index=True,
        key="voyage_monitoring_editor"
    )
    
    # Verifica se há linhas selecionadas
    selected_rows = edited_df[edited_df["Selecionar"] == True]
    
    if not selected_rows.empty:
        st.divider()
        st.subheader("📋 Detalhes dos Farol References Selecionados")
        
        # Processa cada linha selecionada
        for idx, row in selected_rows.iterrows():
            vessel_name = row["VESSEL_NAME"]
            voyage_code = row["VOYAGE_CODE"]
            terminal = row["TERMINAL"]
            
            st.markdown(f"**🚢 {vessel_name} | {voyage_code} | {terminal}**")
            
            # Busca detalhes dos Farol References
            details_df = get_farol_references_details(vessel_name, voyage_code, terminal)
            
            if not details_df.empty:
                # Formata os dados para exibição
                display_details = details_df.copy()
                
                # Mapeia colunas para títulos em português
                column_mapping = {
                    "FAROL_REFERENCE": "Farol Reference",
                    "B_BOOKING_REFERENCE": "Booking Reference",
                    "B_BOOKING_STATUS": "Booking Status",
                    "P_STATUS": "Status",
                    "B_DATA_ESTIMATIVA_SAIDA_ETD": "ETD",
                    "B_DATA_ESTIMATIVA_CHEGADA_ETA": "ETA",
                    "ROW_INSERTED_DATE": "Data Inserção"
                }
                
                # Renomeia colunas
                display_details = display_details.rename(columns=column_mapping)
                
                # Seleciona apenas as colunas mapeadas
                display_columns = list(column_mapping.values())
                display_details = display_details[display_columns]
                
                # Configuração das colunas para exibição
                details_config = {}
                for col in display_details.columns:
                    if col in ["ETD", "ETA", "Data Inserção"]:
                        details_config[col] = st.column_config.DatetimeColumn(col, width="medium")
                    else:
                        details_config[col] = st.column_config.TextColumn(col, width="medium")
                
                # Exibe a tabela de detalhes
                st.dataframe(
                    display_details,
                    column_config=details_config,
                    use_container_width=True,
                    hide_index=True
                )
                
                st.info(f"📊 **Total de Farol References:** {len(display_details)}")
            else:
                st.warning("⚠️ Nenhum Farol Reference encontrado para esta combinação.")
            
            st.markdown("---")
    
    # Verifica se há alterações
    # Compara apenas as colunas editáveis (excluindo a coluna de seleção)
    editable_columns = [col for col in edited_df.columns if col != "Selecionar"]
    edited_df_editable = edited_df[editable_columns]
    df_editable = df[editable_columns]
    
    # Verifica se há alterações comparando valores das colunas editáveis
    has_changes = False
    changed_rows = []
    
    for idx in edited_df_editable.index:
        if idx in df_editable.index:
            # Compara linha por linha
            edited_row = edited_df_editable.loc[idx]
            original_row = df_editable.loc[idx]
            
            # Verifica se há diferenças (ignorando NaN)
            if not edited_row.equals(original_row):
                has_changes = True
                changed_rows.append((idx, edited_row))
    
    if has_changes:
        st.subheader("📝 Alterações Detectadas")
        st.info(f"🔍 {len(changed_rows)} linha(s) com alterações detectadas")
        
        # Botão para salvar alterações
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            if st.button("💾 Salvar Alterações", type="primary"):
                success_count = 0
                total_changes = 0
                
                for idx, row in changed_rows:
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
