import streamlit as st
import pandas as pd
from datetime import datetime
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
            # Primeiro tenta busca exata por Vessel + Voyage
            query_exact = """
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
            
            result = conn.execute(text(query_exact), {
                'vessel_name': vessel_name,
                'voyage_code': voyage_code
            })
            rows = result.fetchall()
            
            if rows:
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
            else:
                # Se não encontrar correspondência exata, busca apenas por Voyage Code
                query_voyage = """
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
                WHERE UPPER(TRIM(r.B_VOYAGE_CODE)) = UPPER(TRIM(:voyage_code))
                AND r.FAROL_REFERENCE IS NOT NULL
                ORDER BY r.ROW_INSERTED_DATE DESC
                """
                
                result = conn.execute(text(query_voyage), {
                    'voyage_code': voyage_code
                })
                rows = result.fetchall()
                
                if rows:
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
                else:
                    return pd.DataFrame()
            
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

def get_dropdown_options():
    """Busca opções para dropdowns do banco de dados"""
    try:
        with get_database_connection() as conn:
            # Busca navios únicos da tabela F_ELLOX_SHIPS (convertendo para maiúsculas)
            vessel_query = text("""
                SELECT DISTINCT UPPER(TRIM(NOME)) as NOME
                FROM F_ELLOX_SHIPS 
                WHERE NOME IS NOT NULL AND ATIVO = 'Y'
                ORDER BY UPPER(TRIM(NOME))
            """)
            vessel_result = conn.execute(vessel_query).fetchall()
            vessel_options = [row[0] for row in vessel_result] if vessel_result else []
            
            # Busca terminais únicos da tabela F_ELLOX_TERMINALS (convertendo para maiúsculas)
            terminal_query = text("""
                SELECT DISTINCT UPPER(TRIM(NOME)) as NOME
                FROM F_ELLOX_TERMINALS 
                WHERE NOME IS NOT NULL AND ATIVO = 'Y'
                ORDER BY UPPER(TRIM(NOME))
            """)
            terminal_result = conn.execute(terminal_query).fetchall()
            terminal_options = [row[0] for row in terminal_result] if terminal_result else []
            
            return vessel_options, terminal_options
    except Exception as e:
        st.error(f"Erro ao buscar opções dos dropdowns: {str(e)}")
        return [], []

def generate_column_config(df):
    """Gera configuração de colunas com larguras dinâmicas seguindo o padrão do sistema"""
    
    # Busca opções para dropdowns
    vessel_options, terminal_options = get_dropdown_options()
    
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
        if col in ["VESSEL_NAME", "TERMINAL"]:
            width = None  # Largura automática para Vessel Name e Terminal
        elif col in ["VOYAGE_CODE", "AGENCY"]:
            width = None  # Largura automática baseada no conteúdo
        else:
            width = "medium"
        
        # Configuração específica para dropdowns
        if col == "VESSEL_NAME" and vessel_options:
            config[col] = st.column_config.SelectboxColumn(
                title, 
                options=vessel_options,
                width=width,
                help="Selecione um navio da lista"
            )
        elif col == "TERMINAL" and terminal_options:
            config[col] = st.column_config.SelectboxColumn(
                title, 
                options=terminal_options,
                width=width,
                help="Selecione um terminal da lista"
            )
        elif any(date_keyword in col.lower() for date_keyword in ["data", "date"]):
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
        st.subheader("📋 Ações para Linha Selecionada")
        
        # Processa cada linha selecionada (deve ser apenas uma)
        for idx, row in selected_rows.iterrows():
            vessel_name = row["VESSEL_NAME"]
            voyage_code = row["VOYAGE_CODE"]
            terminal = row["TERMINAL"]
            
            st.markdown(f"**🚢 {vessel_name} | {voyage_code} | {terminal}**")
            
            # Botões de ação
            col1, col2, col3 = st.columns([1, 1, 2])
            
            with col1:
                if st.button("✏️ Editar Dados", key=f"edit_data_{idx}", type="primary"):
                    st.session_state[f"edit_mode_{idx}"] = True
                    st.session_state[f"editing_row_{idx}"] = row.to_dict()
                    st.rerun()
            
            with col2:
                if st.button("📋 Ver Farol References", key=f"view_refs_{idx}"):
                    st.session_state[f"view_refs_mode_{idx}"] = True
                    st.rerun()
            
            # Modo de edição
            if st.session_state.get(f"edit_mode_{idx}", False):
                st.markdown("---")
                # Título e botão de teste da API na mesma linha
                col_title, col_test_api = st.columns([3, 1])
                with col_title:
                    st.subheader("✏️ Editar Dados da Linha")
                with col_test_api:
                    st.markdown("**Teste API**")
                    if st.button("🔍 Testar API Ellox", key=f"test_api_{idx}", help="Testar conectividade com a API Ellox"):
                        with st.spinner("Testando API Ellox..."):
                            try:
                                api_client = get_default_api_client()
                                result = api_client.test_connection()
                                if result.get("success", False):
                                    response_time = result.get("response_time", 0)
                                    st.success(f"✅ API conectada! Tempo de resposta: {response_time:.2f}s")
                                else:
                                    error_msg = result.get("error", "Erro desconhecido")
                                    st.error(f"❌ Erro na API: {error_msg}")
                            except Exception as e:
                                st.error(f"❌ Erro na API: {str(e)}")
                
                # Formulário de edição
                with st.form(f"edit_form_{idx}"):
                    # Função helper para converter datas de forma segura
                    def safe_date_value(date_val):
                        if pd.isna(date_val) or date_val is None:
                            return None
                        try:
                            if hasattr(date_val, 'date'):
                                return date_val.date()
                            elif isinstance(date_val, str):
                                return pd.to_datetime(date_val).date()
                            return date_val
                        except:
                            return None
                    
                    # Função helper para converter datetime de forma segura
                    def safe_datetime_value(datetime_val):
                        if pd.isna(datetime_val) or datetime_val is None:
                            return None
                        try:
                            if hasattr(datetime_val, 'to_pydatetime'):
                                return datetime_val.to_pydatetime()
                            elif isinstance(datetime_val, str):
                                return pd.to_datetime(datetime_val)
                            return datetime_val
                        except:
                            return None
                    
                    # Função helper para converter string datetime para comparação
                    def parse_datetime_string(dt_str):
                        if not dt_str or dt_str.strip() == "":
                            return None
                        try:
                            return pd.to_datetime(dt_str)
                        except:
                            return None
                    
                    # Função helper para comparar datetime strings
                    def compare_datetime_strings(str1, str2):
                        dt1 = parse_datetime_string(str1)
                        dt2 = parse_datetime_string(str2)
                        if dt1 is None and dt2 is None:
                            return True
                        if dt1 is None or dt2 is None:
                            return False
                        return dt1 == dt2
                    
                    # Informações básicas
                    st.subheader("📋 Informações Básicas")
                    
                    # Layout com 3 colunas ocupando toda a largura
                    col_vessel, col_voyage, col_terminal = st.columns([3, 1, 2])
                    with col_vessel:
                        new_vessel = st.text_input("Vessel Name", value=row["VESSEL_NAME"], key=f"edit_vessel_{idx}", help="Nome do navio (pode ser longo)")
                    with col_voyage:
                        new_voyage = st.text_input("Voyage Code", value=row["VOYAGE_CODE"], key=f"edit_voyage_{idx}", help="Código da viagem (geralmente curto)")
                    with col_terminal:
                        new_terminal = st.text_input("Terminal", value=row["TERMINAL"], key=f"edit_terminal_{idx}", help="Nome do terminal")
                    
                    # Segunda linha: Data Atualização, Data Inserção
                    col_data_atualizacao, col_data_insercao = st.columns([1, 1])
                    with col_data_atualizacao:
                        st.markdown("**Data Atualização**")
                        col_atualizacao_date, col_atualizacao_time = st.columns([2, 1])
                        with col_atualizacao_date:
                            st.text_input("Data", value=safe_datetime_value(row.get("DATA_ATUALIZACAO")).strftime("%Y-%m-%d") if safe_datetime_value(row.get("DATA_ATUALIZACAO")) else "", disabled=True, help="Data da última atualização (somente leitura)")
                        with col_atualizacao_time:
                            st.text_input("Hora", value=safe_datetime_value(row.get("DATA_ATUALIZACAO")).strftime("%H:%M") if safe_datetime_value(row.get("DATA_ATUALIZACAO")) else "", disabled=True, help="Hora da última atualização (somente leitura)")
                    with col_data_insercao:
                        st.markdown("**Data Inserção**")
                        col_insercao_date, col_insercao_time = st.columns([2, 1])
                        with col_insercao_date:
                            st.text_input("Data", value=safe_datetime_value(row.get("ROW_INSERTED_DATE")).strftime("%Y-%m-%d") if safe_datetime_value(row.get("ROW_INSERTED_DATE")) else "", disabled=True, help="Data de inserção do registro (somente leitura)")
                        with col_insercao_time:
                            st.text_input("Hora", value=safe_datetime_value(row.get("ROW_INSERTED_DATE")).strftime("%H:%M") if safe_datetime_value(row.get("ROW_INSERTED_DATE")) else "", disabled=True, help="Hora de inserção do registro (somente leitura)")
                    
                    # Campos ocultos para Agency, CNPJ Terminal, Data Atualização e Data Inserção (coletados no background)
                    new_agency = row.get("AGENCY", "")
                    new_cnpj = row.get("CNPJ_TERMINAL", "")
                    new_data_atualizacao = safe_datetime_value(row.get("DATA_ATUALIZACAO"))
                    new_row_inserted = safe_datetime_value(row.get("ROW_INSERTED_DATE"))
                    
                    # Datas importantes
                    st.subheader("📅 Datas Importantes")
                    
                    # Primeira linha: Data Deadline e Data Draft Deadline
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**Data Deadline**")
                        col_deadline_date, col_deadline_time = st.columns([2, 1])
                        with col_deadline_date:
                            new_deadline_date = st.date_input("Data", value=safe_datetime_value(row.get("DATA_DEADLINE")).date() if safe_datetime_value(row.get("DATA_DEADLINE")) else None, key=f"edit_deadline_date_{idx}", help="Data limite para entrega de documentos")
                        with col_deadline_time:
                            new_deadline_time = st.time_input("Hora", value=safe_datetime_value(row.get("DATA_DEADLINE")).time() if safe_datetime_value(row.get("DATA_DEADLINE")) else None, key=f"edit_deadline_time_{idx}", help="Hora limite para entrega de documentos")
                    
                    with col2:
                        st.markdown("**Data Draft Deadline**")
                        col_draft_date, col_draft_time = st.columns([2, 1])
                        with col_draft_date:
                            new_draft_date = st.date_input("Data", value=safe_datetime_value(row.get("DATA_DRAFT_DEADLINE")).date() if safe_datetime_value(row.get("DATA_DRAFT_DEADLINE")) else None, key=f"edit_draft_date_{idx}", help="Data limite para entrega do draft")
                        with col_draft_time:
                            new_draft_time = st.time_input("Hora", value=safe_datetime_value(row.get("DATA_DRAFT_DEADLINE")).time() if safe_datetime_value(row.get("DATA_DRAFT_DEADLINE")) else None, key=f"edit_draft_time_{idx}", help="Hora limite para entrega do draft")
                    
                    # Segunda linha: Data Abertura Gate e Data Abertura Gate Reefer
                    col4, col5 = st.columns(2)
                    
                    with col4:
                        st.markdown("**Data Abertura Gate**")
                        col_gate_date, col_gate_time = st.columns([2, 1])
                        with col_gate_date:
                            new_gate_date = st.date_input("Data", value=safe_datetime_value(row.get("DATA_ABERTURA_GATE")).date() if safe_datetime_value(row.get("DATA_ABERTURA_GATE")) else None, key=f"edit_gate_date_{idx}", help="Data de abertura do gate para recebimento de cargas")
                        with col_gate_time:
                            new_gate_time = st.time_input("Hora", value=safe_datetime_value(row.get("DATA_ABERTURA_GATE")).time() if safe_datetime_value(row.get("DATA_ABERTURA_GATE")) else None, key=f"edit_gate_time_{idx}", help="Hora de abertura do gate para recebimento de cargas")
                    
                    with col5:
                        st.markdown("**Data Abertura Gate Reefer**")
                        col_reefer_date, col_reefer_time = st.columns([2, 1])
                        with col_reefer_date:
                            new_reefer_date = st.date_input("Data", value=safe_datetime_value(row.get("DATA_ABERTURA_GATE_REEFER")).date() if safe_datetime_value(row.get("DATA_ABERTURA_GATE_REEFER")) else None, key=f"edit_reefer_date_{idx}", help="Data de abertura do gate para cargas refrigeradas")
                        with col_reefer_time:
                            new_reefer_time = st.time_input("Hora", value=safe_datetime_value(row.get("DATA_ABERTURA_GATE_REEFER")).time() if safe_datetime_value(row.get("DATA_ABERTURA_GATE_REEFER")) else None, key=f"edit_reefer_time_{idx}", help="Hora de abertura do gate para cargas refrigeradas")
                    
                    # Datas de navegação
                    st.subheader("🚢 Datas de Navegação")
                    
                    # Primeira linha: ETD e ETA
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**Data Estimativa Saída (ETD)**")
                        col_etd_date, col_etd_time = st.columns([2, 1])
                        with col_etd_date:
                            new_etd_date = st.date_input("Data", value=safe_datetime_value(row.get("DATA_ESTIMATIVA_SAIDA")).date() if safe_datetime_value(row.get("DATA_ESTIMATIVA_SAIDA")) else None, key=f"edit_etd_date_{idx}", help="Data estimada de saída do porto")
                        with col_etd_time:
                            new_etd_time = st.time_input("Hora", value=safe_datetime_value(row.get("DATA_ESTIMATIVA_SAIDA")).time() if safe_datetime_value(row.get("DATA_ESTIMATIVA_SAIDA")) else None, key=f"edit_etd_time_{idx}", help="Hora estimada de saída do porto")
                    
                    with col2:
                        st.markdown("**Data Estimativa Chegada (ETA)**")
                        col_eta_date, col_eta_time = st.columns([2, 1])
                        with col_eta_date:
                            new_eta_date = st.date_input("Data", value=safe_datetime_value(row.get("DATA_ESTIMATIVA_CHEGADA")).date() if safe_datetime_value(row.get("DATA_ESTIMATIVA_CHEGADA")) else None, key=f"edit_eta_date_{idx}", help="Data estimada de chegada ao porto")
                        with col_eta_time:
                            new_eta_time = st.time_input("Hora", value=safe_datetime_value(row.get("DATA_ESTIMATIVA_CHEGADA")).time() if safe_datetime_value(row.get("DATA_ESTIMATIVA_CHEGADA")) else None, key=f"edit_eta_time_{idx}", help="Hora estimada de chegada ao porto")
                    
                    # Segunda linha: ETB e ATB
                    col4, col5 = st.columns(2)
                    
                    with col4:
                        st.markdown("**Data Estimativa Atracação (ETB)**")
                        col_etb_date, col_etb_time = st.columns([2, 1])
                        with col_etb_date:
                            new_etb_date = st.date_input("Data", value=safe_datetime_value(row.get("DATA_ESTIMATIVA_ATRACACAO")).date() if safe_datetime_value(row.get("DATA_ESTIMATIVA_ATRACACAO")) else None, key=f"edit_etb_date_{idx}", help="Data estimada de atracação no cais")
                        with col_etb_time:
                            new_etb_time = st.time_input("Hora", value=safe_datetime_value(row.get("DATA_ESTIMATIVA_ATRACACAO")).time() if safe_datetime_value(row.get("DATA_ESTIMATIVA_ATRACACAO")) else None, key=f"edit_etb_time_{idx}", help="Hora estimada de atracação no cais")
                    
                    with col5:
                        st.markdown("**Data Atracação (ATB)**")
                        col_atb_date, col_atb_time = st.columns([2, 1])
                        with col_atb_date:
                            new_atb_date = st.date_input("Data", value=safe_datetime_value(row.get("DATA_ATRACACAO")).date() if safe_datetime_value(row.get("DATA_ATRACACAO")) else None, key=f"edit_atb_date_{idx}", help="Data real de atracação no cais")
                        with col_atb_time:
                            new_atb_time = st.time_input("Hora", value=safe_datetime_value(row.get("DATA_ATRACACAO")).time() if safe_datetime_value(row.get("DATA_ATRACACAO")) else None, key=f"edit_atb_time_{idx}", help="Hora real de atracação no cais")
                    
                    # Chegada e Partida
                    st.subheader("🚢 Chegada e Partida")
                    
                    # Layout com 2 colunas (sem colunas vazias)
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**Data Chegada (ATA)**")
                        col_ata_date, col_ata_time = st.columns([2, 1])
                        with col_ata_date:
                            new_ata_date = st.date_input("Data", value=safe_datetime_value(row.get("DATA_CHEGADA")).date() if safe_datetime_value(row.get("DATA_CHEGADA")) else None, key=f"edit_ata_date_{idx}", help="Data real de chegada ao porto")
                        with col_ata_time:
                            new_ata_time = st.time_input("Hora", value=safe_datetime_value(row.get("DATA_CHEGADA")).time() if safe_datetime_value(row.get("DATA_CHEGADA")) else None, key=f"edit_ata_time_{idx}", help="Hora real de chegada ao porto")
                    
                    with col2:
                        st.markdown("**Data Partida (ATD)**")
                        col_atd_date, col_atd_time = st.columns([2, 1])
                        with col_atd_date:
                            new_atd_date = st.date_input("Data", value=safe_datetime_value(row.get("DATA_PARTIDA")).date() if safe_datetime_value(row.get("DATA_PARTIDA")) else None, key=f"edit_atd_date_{idx}", help="Data real de partida do porto")
                        with col_atd_time:
                            new_atd_time = st.time_input("Hora", value=safe_datetime_value(row.get("DATA_PARTIDA")).time() if safe_datetime_value(row.get("DATA_PARTIDA")) else None, key=f"edit_atd_time_{idx}", help="Hora real de partida do porto")
                    
                    # Dicas das siglas (no final)
                    st.info("""
                    💡 **Dicas das Siglas:**
                    - **ETD/ETA**: Datas estimadas (Estimated)
                    - **ATB/ATA/ATD**: Datas reais (Actual)
                    - **ETB**: Atracação estimada no cais
                    - **ATB**: Atracação real no cais
                    """)
                    
                    # Botões do formulário
                    col1, col2, col3 = st.columns([1, 1, 2])
                    
                    with col1:
                        save_clicked = st.form_submit_button("💾 Salvar", type="primary")
                    
                    with col2:
                        cancel_clicked = st.form_submit_button("❌ Cancelar")
                    
                    # Processa ações do formulário
                    if save_clicked:
                        # Prepara dados para atualização
                        updates = {}
                        
                        # Informações básicas
                        if new_vessel != row["VESSEL_NAME"]:
                            updates["VESSEL_NAME"] = new_vessel
                        if new_voyage != row["VOYAGE_CODE"]:
                            updates["VOYAGE_CODE"] = new_voyage
                        if new_terminal != row["TERMINAL"]:
                            updates["TERMINAL"] = new_terminal
                        if new_agency != row.get("AGENCY", ""):
                            updates["AGENCY"] = new_agency
                        if new_cnpj != row.get("CNPJ_TERMINAL", ""):
                            updates["CNPJ_TERMINAL"] = new_cnpj
                        
                        # Datas importantes (campos separados)
                        if new_deadline_date or new_deadline_time:
                            new_deadline_dt = datetime.combine(new_deadline_date, new_deadline_time) if new_deadline_date and new_deadline_time else None
                            current_deadline = safe_datetime_value(row.get("DATA_DEADLINE"))
                            if new_deadline_dt != current_deadline:
                                updates["DATA_DEADLINE"] = new_deadline_dt
                        
                        if new_draft_date or new_draft_time:
                            new_draft_dt = datetime.combine(new_draft_date, new_draft_time) if new_draft_date and new_draft_time else None
                            current_draft = safe_datetime_value(row.get("DATA_DRAFT_DEADLINE"))
                            if new_draft_dt != current_draft:
                                updates["DATA_DRAFT_DEADLINE"] = new_draft_dt
                        
                        if new_gate_date or new_gate_time:
                            new_gate_dt = datetime.combine(new_gate_date, new_gate_time) if new_gate_date and new_gate_time else None
                            current_gate = safe_datetime_value(row.get("DATA_ABERTURA_GATE"))
                            if new_gate_dt != current_gate:
                                updates["DATA_ABERTURA_GATE"] = new_gate_dt
                        
                        if new_reefer_date or new_reefer_time:
                            new_reefer_dt = datetime.combine(new_reefer_date, new_reefer_time) if new_reefer_date and new_reefer_time else None
                            current_reefer = safe_datetime_value(row.get("DATA_ABERTURA_GATE_REEFER"))
                            if new_reefer_dt != current_reefer:
                                updates["DATA_ABERTURA_GATE_REEFER"] = new_reefer_dt
                        
                        # Datas e horas de navio (campos separados)
                        if new_etd_date and new_etd_time:
                            new_etd_datetime = datetime.combine(new_etd_date, new_etd_time)
                            current_etd = safe_datetime_value(row.get("DATA_ESTIMATIVA_SAIDA"))
                            if new_etd_datetime != current_etd:
                                updates["DATA_ESTIMATIVA_SAIDA"] = new_etd_datetime
                        
                        if new_eta_date and new_eta_time:
                            new_eta_datetime = datetime.combine(new_eta_date, new_eta_time)
                            current_eta = safe_datetime_value(row.get("DATA_ESTIMATIVA_CHEGADA"))
                            if new_eta_datetime != current_eta:
                                updates["DATA_ESTIMATIVA_CHEGADA"] = new_eta_datetime
                        
                        if new_etb_date and new_etb_time:
                            new_etb_datetime = datetime.combine(new_etb_date, new_etb_time)
                            current_etb = safe_datetime_value(row.get("DATA_ESTIMATIVA_ATRACACAO"))
                            if new_etb_datetime != current_etb:
                                updates["DATA_ESTIMATIVA_ATRACACAO"] = new_etb_datetime
                        
                        if new_atb_date and new_atb_time:
                            new_atb_datetime = datetime.combine(new_atb_date, new_atb_time)
                            current_atb = safe_datetime_value(row.get("DATA_ATRACACAO"))
                            if new_atb_datetime != current_atb:
                                updates["DATA_ATRACACAO"] = new_atb_datetime
                        
                        # Datas de chegada e partida (campos separados)
                        if new_ata_date and new_ata_time:
                            new_ata_datetime = datetime.combine(new_ata_date, new_ata_time)
                            current_ata = safe_datetime_value(row.get("DATA_CHEGADA"))
                            if new_ata_datetime != current_ata:
                                updates["DATA_CHEGADA"] = new_ata_datetime
                        
                        if new_atd_date and new_atd_time:
                            new_atd_datetime = datetime.combine(new_atd_date, new_atd_time)
                            current_atd = safe_datetime_value(row.get("DATA_PARTIDA"))
                            if new_atd_datetime != current_atd:
                                updates["DATA_PARTIDA"] = new_atd_datetime
                        
                        # Datas de sistema não são editáveis (mantidas como estão)
                        
                        if updates:
                            if update_voyage_monitoring_data(row["ID"], updates):
                                st.success("✅ Dados atualizados com sucesso!")
                                st.session_state[f"edit_mode_{idx}"] = False
                                st.rerun()
                            else:
                                st.error("❌ Erro ao atualizar dados")
                        else:
                            st.warning("⚠️ Nenhuma alteração detectada")
                    
                    if cancel_clicked:
                        st.session_state[f"edit_mode_{idx}"] = False
                        st.rerun()
                
            
            # Modo de visualização de Farol References
            if st.session_state.get(f"view_refs_mode_{idx}", False):
                st.markdown("---")
                st.subheader("📋 Farol References Relacionados")
                
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
                    st.info("💡 **Dica:** Os dados da API Ellox podem estar mais atualizados que os dados históricos de booking. Tente buscar por outros navios com o mesmo código de viagem.")
                
                # Botão para fechar visualização
                if st.button("❌ Fechar", key=f"close_refs_{idx}"):
                    st.session_state[f"view_refs_mode_{idx}"] = False
                    st.rerun()
            
            st.markdown("---")
    
    # Informação sobre seleção
    if selected_rows.empty:
        st.info("💡 **Dica:** Selecione uma linha para editar dados ou visualizar Farol References relacionados.")
