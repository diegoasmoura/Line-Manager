## shipments.py
 
# Imports principais
import streamlit as st
import pandas as pd
from sqlalchemy import text
import time
import uuid
 
# Importa funções para interações com banco de dados e UDC
from database import (
    get_data_salesData,           # Carrega os dados dos embarques na tabela de Sales Data
    get_data_bookingData,         # Carrega os dados dos embarques na tabela Booking management
    get_data_loadingData,         # Carrega os dados dos embarques na tabela Container Loading
    load_df_udc,                  # Carrega as opções de UDC (dropdowns)
    insert_adjustments_basics,    #Função para inserir ajustes básicos na tabela de log
    get_actions_count_by_farol_reference,  # Conta ações por Farol Reference
    get_database_connection       # Conexão direta para consultas auxiliares
)
 
# Importa funções auxiliares de mapeamento e formulários
from shipments_mapping import  non_editable_columns, drop_downs
from shipments_new import show_add_form
from shipments_split import show_split_form
from booking_new import show_booking_management_form
from history import exibir_history
 
 
# Função para aplicar filtros avançados interativos no DataFrame
def aplicar_filtros_interativos(df):
    # Inicializa o estado da expansão, se não existir
    if "expander_filtros_aberto" not in st.session_state:
        st.session_state["expander_filtros_aberto"] = False
 
    with st.expander(" Advanced Filters (optional)", expanded=st.session_state["expander_filtros_aberto"]):
 
        colunas_filtradas = st.multiselect(
            "Columns to filter:",
            df.columns.tolist(),
            default=[],
            key="colunas_filtradas_filtros"
        )
        filtros = {}
 
 
        for col in colunas_filtradas:
            col_data = df[col]
 
            if col_data.dtype == "object":
                unique_vals = sorted(col_data.dropna().unique().tolist())
                filtros[col] = st.multiselect(f"Filter {col}", unique_vals, default=unique_vals, key=f"{col}_multiselect")
 
            elif pd.api.types.is_numeric_dtype(col_data):
                min_val, max_val = int(col_data.min()), int(col_data.max())
                filtros[col] = st.slider(f"{col} between", min_val, max_val, (min_val, max_val), key=f"{col}_slider")
 
            elif pd.api.types.is_bool_dtype(col_data):
                filtros[col] = st.radio(f"Include {col}?", ["All", True, False], horizontal=True, key=f"{col}_radio")
 
            elif pd.api.types.is_datetime64_any_dtype(col_data):
                min_date = col_data.min().date()
                max_date = col_data.max().date()
                selected_range = st.date_input(f"Period for {col}", value=(min_date, max_date), key=f"{col}_date")
                if isinstance(selected_range, (tuple, list, pd.DatetimeIndex)):
                    srange = list(selected_range)
                else:
                    srange = [selected_range]
 
                if len(srange) == 0:
                    filtros[col] = None
                elif len(srange) == 1:
                    filtros[col] = ("gte", pd.Timestamp(srange[0]))
                else:
                    filtros[col] = ("range", pd.Timestamp(srange[0]), pd.Timestamp(srange[1]))
 
        # Aplica os filtros no DataFrame
        for col, val in filtros.items():
            if val is None:
                continue
            if isinstance(val, list):
                df = df[df[col].isin(val)]
            elif isinstance(val, tuple):
                if val[0] == "gte":
                    df = df[df[col] >= val[1]]
                elif val[0] == "range":
                    end_of_day = val[2] + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
                    df = df[(df[col] >= val[1]) & (df[col] <= end_of_day)]
            elif isinstance(val, str) and val != "All":
                df = df[df[col] == (val == "True")]
            elif isinstance(val, bool):
                df = df[df[col] == val]
 
    return df
 
 
# Função principal que define qual página do app deve ser exibida
def main():
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "main"
 
    # Direciona para a página correta com base na seleção
    if st.session_state["current_page"] == "main":
        exibir_shipments()
    elif st.session_state["current_page"] == "add":
        show_add_form()
    elif st.session_state["current_page"] == "split":
        show_split_form()
    elif st.session_state["current_page"] == "booking":
        show_booking_management_form()
    elif st.session_state["current_page"] == "history":
        exibir_history()
 
 
# Função para limpar o estado da sessão (usado ao descartar alterações)
def resetar_estado():
    for key in ["shipments_data", "original_data", "changes", "grid_update_key"]:
        if key in st.session_state:
            del st.session_state[key]
    st.session_state["grid_update_key"] = str(time.time())
    st.rerun()
 
 
# Função para exibir a página principal dos embarques
def exibir_shipments():
    st.title("🏗️ Shipments")
    random_uuid = str(uuid.uuid4())
 
    if "grid_update_key" not in st.session_state:
        st.session_state["grid_update_key"] = str(time.time())
 
    choose = st.radio(
        "Choose the stage",
        ["Sales Data", "Booking Management"],
        horizontal=True,
    )
    
    # Salva o stage atual na sessão
    st.session_state["current_stage"] = choose

    if choose == "Sales Data":
        df = get_data_salesData()
    elif choose == "Booking Management":
        df = get_data_bookingData()

    # Padroniza o rótulo exibido para a referência Farol
    rename_map = {}
    if "Sales Farol Reference" in df.columns:
        rename_map["Sales Farol Reference"] = "Farol Reference"
    if "Booking Farol Reference" in df.columns:
        rename_map["Booking Farol Reference"] = "Farol Reference"
    if "Loading Farol Reference" in df.columns:
        rename_map["Loading Farol Reference"] = "Farol Reference"
    if rename_map:
        df.rename(columns=rename_map, inplace=True)
    farol_ref_col = "Farol Reference"

      # Filtro removido - agora todos os splits são visíveis na grade
    # Os splits podem ser gerenciados através do histórico

    # Adiciona coluna com contagem de registros recebidos dos carriers
    def get_carrier_returns_count(refs):
        try:
            conn = get_database_connection()
            placeholders = ",".join([f":r{i}" for i in range(len(refs))])
            params = {f"r{i}": r for i, r in enumerate(refs)}
            params["status"] = "Received from Carrier"
            
            sql = text(f"""
                SELECT farol_reference, COUNT(*) as count
                FROM LogTransp.F_CON_RETURN_CARRIERS
                WHERE UPPER(B_BOOKING_STATUS) = UPPER(:status)
                AND farol_reference IN ({placeholders})
                GROUP BY farol_reference
            """)
            
            result = conn.execute(sql, params).fetchall()
            conn.close()
            
            # Monta dicionário {ref: count}
            return {ref: count for ref, count in result}
        except Exception:
            return {}  # fallback seguro

    # Busca contagens para todas as referências visíveis
    refs = df[farol_ref_col].dropna().astype(str).unique().tolist()
    actions_count = get_carrier_returns_count(refs) if refs else {}

    def branch_count(ref: str) -> int:
        ref = str(ref)
        return int(actions_count.get(ref, 0))

    def format_carrier_returns_status(count: int) -> str:
        """Formata o status de retornos com badges coloridos e quantidade"""
        if count == 0:
            return "🔵 OK (0)"  # Azul - Sem pendências
        else:
            return f"🟡 PENDING ({count})"  # Amarelo - Pendente com quantidade

    df["Carrier Returns"] = df[farol_ref_col].apply(branch_count).astype(int)
    df["Carrier Returns Status"] = df["Carrier Returns"].apply(format_carrier_returns_status)

    previous_stage = st.session_state.get("previous_stage")
    unsaved_changes = st.session_state.get("changes") is not None and not st.session_state["changes"].empty
 
    if previous_stage is not None and choose != previous_stage:
        if unsaved_changes:
            st.warning("Stage changed — unsaved changes were discarded.")
            resetar_estado()
            st.stop()
        else:
            st.session_state["previous_stage"] = choose
    else:
        st.session_state["previous_stage"] = choose
 
    df = aplicar_filtros_interativos(df)

    # KPIs abaixo do título, após filtros e antes da grid
    k1, k2, k3, k4 = st.columns(4)

    if "Farol Status" in df.columns:
        status_series = df["Farol Status"].astype(str).str.strip().str.lower()
        booking_requested = int((status_series == "booking requested").sum())
        # valor base (fallback) a partir da grade
        received_from_carrier = int((status_series == "received from carrier").sum())
        pending_adjustments = int((status_series == "adjustment requested").sum())
    else:
        booking_requested = received_from_carrier = pending_adjustments = 0
    total_visible = int(len(df))

    # Ajuste: contar "Received from Carrier" apenas na F_CON_RETURN_CARRIERS com Status = 'Received from Carrier'
    try:
        refs = df[farol_ref_col].dropna().astype(str).unique().tolist()
        if refs:
            conn = get_database_connection()
            placeholders = ",".join([f":r{i}" for i in range(len(refs))])
            params = {f"r{i}": r for i, r in enumerate(refs)}
            params.update({"status": "Received from Carrier"})
            sql_rc = text(
                f"SELECT COUNT(*) AS c FROM LogTransp.F_CON_RETURN_CARRIERS \n"
                f"WHERE UPPER(B_BOOKING_STATUS) = UPPER(:status) AND farol_reference IN ({placeholders})"
            )
            res = conn.execute(sql_rc, params).fetchone()
            conn.close()
            if res and res[0] is not None:
                received_from_carrier = int(res[0])
    except Exception:
        # mantém o fallback calculado pela grade
        pass

    with k1:
        st.metric("📋 Booking Requested", booking_requested)
    with k2:
        st.metric("📨 Received from Carrier", received_from_carrier)
    with k3:
        st.metric("📦 Total (grid)", total_visible)
    with k4:
        st.metric("⚠️ Pending Adjustments", pending_adjustments)
 
    # Define colunas não editáveis e configurações de dropdowns
    disabled_columns = non_editable_columns(choose)
    # Ajusta nomes das colunas desabilitadas considerando renomeações para "Farol Reference"
    if rename_map:
        disabled_columns = [rename_map.get(col, col) for col in disabled_columns]
    # Garante que Splitted Booking Reference esteja visível porém somente leitura
    if "Splitted Booking Reference" not in disabled_columns:
        disabled_columns.append("Splitted Booking Reference")
    # Garante que Carrier Returns e Carrier Returns Status sejam somente leitura
    if "Carrier Returns" not in disabled_columns:
        disabled_columns.append("Carrier Returns")
    if "Carrier Returns Status" not in disabled_columns:
        disabled_columns.append("Carrier Returns Status")
    df_udc = load_df_udc()
    column_config = drop_downs(df, df_udc)
    # Configuração explícita para exibir como texto somente leitura
    column_config["Splitted Booking Reference"] = st.column_config.TextColumn(
        "Splitted Farol Reference", width="medium", disabled=True
    )
    # Configuração para Booking Reference (verifica ambos os nomes possíveis)
    if "Booking Reference" in df.columns:
        column_config["Booking Reference"] = st.column_config.TextColumn(
            "Booking", width="medium", disabled=False
        )
    elif "b_booking_reference" in df.columns:
        column_config["b_booking_reference"] = st.column_config.TextColumn(
            "Booking", width="medium", disabled=False
        )
    # Alias de exibição para Quantity of Containers mantendo a coluna original
    if "Sales Quantity of Containers" in df.columns:
        column_config["Sales Quantity of Containers"] = st.column_config.NumberColumn(
            "Quantity of Containers", format="%d"
        )
 
    #  Adiciona coluna de seleção
    df["Select"] = False
    column_config["Select"] = st.column_config.CheckboxColumn("Select", help="Select only one line", pinned="left")

    # Garante que a coluna Farol Reference está pinada à esquerda
    column_config[farol_ref_col] = st.column_config.TextColumn(farol_ref_col, pinned="left")
    
    # Configuração da coluna Carrier Returns Status
    column_config["Carrier Returns Status"] = st.column_config.TextColumn(
        "Carrier Returns", 
        help="Status of returns received from carriers (🔵 OK (0) = No pending, 🟡 PENDING (X) = X returns to evaluate)",
        disabled=True
    )

    # Reordena colunas e posiciona "Carrier Returns" após "Farol Status"
    colunas_ordenadas = ["Select", farol_ref_col] + [col for col in df.columns if col not in ["Select", farol_ref_col]]
    
    # Posiciona "Carrier Returns Status" após "Farol Status"
    if "Carrier Returns Status" in colunas_ordenadas and "Farol Status" in colunas_ordenadas:
        colunas_ordenadas.remove("Carrier Returns Status")
        idx_status = colunas_ordenadas.index("Farol Status")
        colunas_ordenadas.insert(idx_status + 1, "Carrier Returns Status")
    
            # Posiciona "Splitted Booking Reference" imediatamente após "Comments Sales"
        if "Splitted Booking Reference" in colunas_ordenadas and "Comments Sales" in colunas_ordenadas:
            # Remove e reinsere antes de Comments Sales (lado esquerdo)
            colunas_ordenadas.remove("Splitted Booking Reference")
            idx_comments = colunas_ordenadas.index("Comments Sales")
            colunas_ordenadas.insert(idx_comments, "Splitted Booking Reference")
        
        # Posiciona "Voyage Code" após "Voyage Carrier" (Booking Management)
        if "Voyage Code" in colunas_ordenadas and "Voyage Carrier" in colunas_ordenadas:
            colunas_ordenadas.remove("Voyage Code")
            idx_carrier = colunas_ordenadas.index("Voyage Carrier")
            colunas_ordenadas.insert(idx_carrier + 1, "Voyage Code")
        
        # Posiciona as novas colunas de datas entre "Data Abertura Gate" e "Data Partida ATD"
        if "Data Abertura Gate" in colunas_ordenadas and "Data Partida ATD" in colunas_ordenadas:
            # Remove as novas colunas se já estiverem na lista
            for col in ["Data Confirmação Embarque", "Data Estimada Transbordo ETD", "Data Transbordo ATD"]:
                if col in colunas_ordenadas:
                    colunas_ordenadas.remove(col)
            
            # Encontra a posição após "Data Abertura Gate"
            idx_gate = colunas_ordenadas.index("Data Abertura Gate")
            
            # Insere as novas colunas na ordem correta (apenas se existirem no DataFrame)
            if "Data Confirmação Embarque" in df.columns:
                colunas_ordenadas.insert(idx_gate + 1, "Data Confirmação Embarque")
                idx_gate += 1  # Ajusta o índice após inserção
            
            # Recalcula a posição de "Data Partida ATD" após inserções
            idx_partida = colunas_ordenadas.index("Data Partida ATD")
            if "Data Estimada Transbordo ETD" in df.columns:
                colunas_ordenadas.insert(idx_partida, "Data Estimada Transbordo ETD")
                idx_partida += 1  # Ajusta o índice após inserção
            
            # Recalcula a posição de "Data Chegada ATA" após inserções
            if "Data Chegada ATA" in colunas_ordenadas and "Data Transbordo ATD" in df.columns:
                idx_chegada = colunas_ordenadas.index("Data Chegada ATA")
                colunas_ordenadas.insert(idx_chegada, "Data Transbordo ATD")

    # Fixar largura da coluna Carrier Returns Status aproximadamente ao tamanho do título
    if "Carrier Returns Status" in colunas_ordenadas:
        idx_returns = colunas_ordenadas.index("Carrier Returns Status") + 1  # nth-child é 1-based
        returns_css = (
            f"[data-testid='stDataEditor'] thead th:nth-child({idx_returns}),"
            f"[data-testid='stDataEditor'] tbody td:nth-child({idx_returns}),"
            f"[data-testid='stDataFrame'] thead th:nth-child({idx_returns}),"
            f"[data-testid='stDataFrame'] tbody td:nth-child({idx_returns}) {{"
            " width: 16ch !important; min-width: 16ch !important; max-width: 16ch !important;"
            " }}"
        )
        st.markdown(f"<style>{returns_css}</style>", unsafe_allow_html=True)

    # Destaque visual: colore colunas editáveis (inclui também colunas iniciadas com B_/b_/Booking)
    editable_cols = []
    for c in colunas_ordenadas:
        if c == "Select":
            continue
        if c not in disabled_columns:
            editable_cols.append(c)
    # Garante inclusão de colunas de Booking por convenção de nome
    for c in colunas_ordenadas:
        if c.startswith(("B_", "b_", "Booking ")) and c not in disabled_columns and c not in editable_cols:
            editable_cols.append(c)
    if editable_cols:
        # nth-child é 1-based e considera apenas colunas visíveis
        editable_idx = [colunas_ordenadas.index(c) + 1 for c in editable_cols]
        selectors = []
        for i in editable_idx:
            selectors += [
                f'[data-testid="stDataEditor"] thead th:nth-child({i})',
                f'[data-testid="stDataEditor"] tbody td:nth-child({i})',
                f'[data-testid="stDataFrame"] thead th:nth-child({i})',
                f'[data-testid="stDataFrame"] tbody td:nth-child({i})',
            ]
        css = ", ".join(selectors) + " { background-color: #FFF8E1 !important; }"
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

    # Removido seletor de espaçamento para manter padrão
 
    # Guarda cópias sem a coluna "Select" para comparação
    df_filtered_original = df.drop(columns=["Select"], errors="ignore").copy()
 
    # Exibe data_editor
    edited_df = st.data_editor(
        df[colunas_ordenadas],
        key=st.session_state["grid_update_key"],
        use_container_width=True,
        num_rows="fixed",
        disabled=disabled_columns,
        column_config=column_config,
        hide_index=True,
    )

    # Contador discreto de registros
    total_records = len(edited_df)
    st.caption(f"Total: {total_records} shipping records")
    
    # Remove "Select" para comparação
    edited_df_clean = edited_df.drop(columns=["Select"], errors="ignore")
 
    # Detecta e registra mudanças
    status_blocked = False
    status_blocked_message = ""
    if not edited_df_clean.equals(df_filtered_original):
        changes = []
        for index, row in edited_df_clean.iterrows():
            original_row = df_filtered_original.loc[index]
            for col in edited_df_clean.columns:
                if pd.isna(original_row[col]) and pd.isna(row[col]):
                    continue
                if original_row[col] != row[col]:
                    # Verifica se a alteração é proibida para 'Farol Status'
                    if col == "Farol Status":
                        from_status = original_row[col]
                        to_status = row[col]
                        if (
                            from_status == "Adjustment Requested" and to_status != "Adjustment Requested"
                        ) or (
                            from_status != "Adjustment Requested" and to_status == "Adjustment Requested"
                        ):
                            status_blocked = True
                            status_blocked_message = "⚠️ Status 'Adjustment Requested' cannot be changed directly. Use the adjustments module to request changes."
                    changes.append({
                        'Farol Reference': row.get(farol_ref_col, index),
                        "Column": col,
                        "Previous Value": original_row[col],
                        "New Value": row[col],
                        "Stage": "Sales Data"
                    })
        if status_blocked:
            st.warning(status_blocked_message)
            st.session_state["changes"] = pd.DataFrame()  # Limpa alterações
        elif changes:
            changes_df = pd.DataFrame(changes)
            st.session_state["changes"] = changes_df
            #st.success(f"{len(changes)} alteração(ões) detectada(s).")
        else:
            st.session_state["changes"] = pd.DataFrame()
    else:
        st.session_state["changes"] = pd.DataFrame()
 
    # Exibe a seção de alterações logo após a mensagem de sucesso
    if "changes" in st.session_state and not st.session_state["changes"].empty:
 
        st.markdown("### ✏️ Changes Made")
        changes_df = st.session_state["changes"].copy()
   
        # Garante que a coluna Comments exista
        if "Comments" not in changes_df.columns:
           
            # Stage único:
            changes_df["Stage"] = "Sales Data"
           
        col_left, col_adjust, col_right  = st.columns([3,1,3])  # Grade e campo de texto lado a lado
   
        with col_left:
 
            st.dataframe(
                changes_df[["Farol Reference", "Column", "Previous Value", "New Value","Stage"]],
                use_container_width=True,
                hide_index=True)
   
        with col_right:
            st.text_area("📌 Additional Information", key="info_complementar")
   
           
        col1, col2, col3, col4  = st.columns([1, 1, 2, 3])
        with col1:
            if st.button("✅ Confirm Changes"):
                comments = st.session_state.get("info_complementar", "").strip()
       
                if comments:
                    success = insert_adjustments_basics(
                        st.session_state["changes"],
                        comments,
                        random_uuid
                    )
                    if success:
                        st.success("✅ Changes successfully registered in the database!")
                        st.session_state["changes"] = pd.DataFrame()
                       
                        #Liberando o cache salvo das consultas
                        st.cache_data.clear()
                        resetar_estado()
                        st.rerun()
                        
                    else:
                        st.error("❌ Error registering adjustments in the database.")
                else:
                    st.error("⚠️ The 'Additional Information' field is required.")
 
        with col2:
            if st.button("❌ Discard Changes"):
 
                st.warning("Changes discarded.")
                st.session_state["changes"] = pd.DataFrame()
                st.session_state["grid_update_key"] = str(time.time())
                st.rerun()
 
    # Verifica se linha foi selecionada
    selected_rows = edited_df[edited_df["Select"] == True]
    selected_farol_ref = None
    original_status = None
    selected_index = None
    
    # Validação para permitir apenas uma seleção
    if len(selected_rows) > 1:
        st.warning("⚠️ Please select only **one** row.")
    
    if len(selected_rows) == 1:
        selected_farol_ref = selected_rows[farol_ref_col].values[0]
        st.session_state["selected_reference"] = selected_farol_ref
        selected_index = selected_rows.index[0]
        if "Farol Status" in df_filtered_original.columns:
            original_status = df_filtered_original.loc[selected_index, "Farol Status"]
    
    st.markdown("---")
    col_new, col_booking, col_history, col_split, _ = st.columns([1, 1, 1, 1, 4])
    with col_new:
        if st.button("🚢 New Shipment"):
            st.session_state["current_page"] = "add"
            st.rerun()
    # Botões sempre visíveis, mas desabilitados se não houver seleção única
    with col_booking:
        new_booking_disabled = True
        if selected_farol_ref and original_status is not None:
            new_booking_disabled = not (str(original_status).strip().lower() == "new request".lower())
        # Se não há seleção única, desabilita
        if len(selected_rows) != 1:
            new_booking_disabled = True
        st.button("📦 New Booking", disabled=new_booking_disabled, key="new_booking_btn")
        if st.session_state.get("new_booking_btn") and not new_booking_disabled:
            st.session_state["current_page"] = "booking"
            st.rerun()
    with col_history:
        history_disabled = True
        if selected_farol_ref and original_status is not None:
            history_disabled = not (str(original_status).strip().lower() != "new request".lower())
        if len(selected_rows) != 1:
            history_disabled = True
        st.button("🎫 Ticket Journey", disabled=history_disabled, key="history_btn")
        if st.session_state.get("history_btn") and not history_disabled:
            st.session_state["selected_reference"] = selected_farol_ref
            st.session_state["current_page"] = "history"
            st.rerun()
    with col_split:
        adjustments_disabled = True
        if selected_farol_ref and original_status is not None:
            adjustments_disabled = not (str(original_status).strip().lower() != "new request".lower())
        # Se não há seleção única, desabilita
        if len(selected_rows) != 1:
            adjustments_disabled = True
        st.button("🛠️ Adjustments", disabled=adjustments_disabled, key="adjustments_btn")
        if st.session_state.get("adjustments_btn") and not adjustments_disabled:
            st.session_state["original_data"] = df
            st.session_state["selected_reference"] = selected_farol_ref
            st.session_state["current_page"] = "split"
            st.rerun()
    # Botão View Attachments sempre visível, toggle, igual tela de ajustes
    with _:
        view_attachments_open = st.session_state.get("show_shipments_attachments", False)
        if st.button("📎 View Attachments", disabled=(len(selected_rows) != 1), key="view_attachments_shipments"):
            if view_attachments_open:
                st.session_state["show_shipments_attachments"] = False
                st.session_state["shipments_attachments_farol_ref"] = None
            else:
                st.session_state["show_shipments_attachments"] = True
                st.session_state["shipments_attachments_farol_ref"] = selected_farol_ref
            st.rerun()
    # Seção de anexos
    if st.session_state.get("show_shipments_attachments", False):
        # Sincroniza referência se seleção mudar
        if selected_farol_ref != st.session_state.get("shipments_attachments_farol_ref"):
            if selected_farol_ref:
                st.session_state["shipments_attachments_farol_ref"] = selected_farol_ref
                st.rerun()
            else:
                st.session_state["show_shipments_attachments"] = False
                st.session_state["shipments_attachments_farol_ref"] = None
                st.rerun()
        st.markdown("---")
        st.markdown("### 📎 Attachment Management")
        farol_ref = st.session_state.get("shipments_attachments_farol_ref")
        if farol_ref:
            from history import display_attachments_section
            display_attachments_section(farol_ref)
        else:
            st.info("Select a row to view attachments.")
 
 
 
       
 
 
# Executa a aplicação
if __name__ == "__main__":
    main()