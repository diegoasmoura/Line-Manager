## shipments.py
 
# Imports principais
import streamlit as st
import pandas as pd
import time
import uuid
 
# Importa funções para interações com banco de dados e UDC
from database import (
    get_data_salesData,           # Carrega os dados dos embarques na tabela de Sales Data
    get_data_bookingData,         # Carrega os dados dos embarques na tabela Booking management
    get_data_loadingData,         # Carrega os dados dos embarques na tabela Container Loading
    load_df_udc,                  # Carrega as opções de UDC (dropdowns)
    insert_adjustments_basics     #Função para inserir ajustes básicos na tabela de log
)
 
# Importa funções auxiliares de mapeamento e formulários
from shipments_mapping import  non_editable_columns, drop_downs
from shipments_new import show_add_form
from shipments_split import show_split_form
from booking_new import show_booking_management_form
 
 
# Função para aplicar filtros avançados interativos no DataFrame
def aplicar_filtros_interativos(df):
    # Inicializa o estado da expansão, se não existir
    if "expander_filtros_aberto" not in st.session_state:
        st.session_state["expander_filtros_aberto"] = False
 
    with st.expander("🔎 Filtros Avançados (opcional)", expanded=st.session_state["expander_filtros_aberto"]):
 
        colunas_filtradas = st.multiselect(
            "Colunas para aplicar filtro:",
            df.columns.tolist(),
            default=[],
            key="colunas_filtradas_filtros"
        )
        filtros = {}
 
 
        for col in colunas_filtradas:
            col_data = df[col]
 
            if col_data.dtype == "object":
                unique_vals = sorted(col_data.dropna().unique().tolist())
                filtros[col] = st.multiselect(f"Filtrar {col}", unique_vals, default=unique_vals, key=f"{col}_multiselect")
 
            elif pd.api.types.is_numeric_dtype(col_data):
                min_val, max_val = int(col_data.min()), int(col_data.max())
                filtros[col] = st.slider(f"{col} entre", min_val, max_val, (min_val, max_val), key=f"{col}_slider")
 
            elif pd.api.types.is_bool_dtype(col_data):
                filtros[col] = st.radio(f"Incluir {col}?", ["Todos", True, False], horizontal=True, key=f"{col}_radio")
 
            elif pd.api.types.is_datetime64_any_dtype(col_data):
                min_date = col_data.min().date()
                max_date = col_data.max().date()
                selected_range = st.date_input(f"Período para {col}", value=(min_date, max_date), key=f"{col}_date")
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
            elif isinstance(val, str) and val != "Todos":
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
        ["Sales Data", "Booking Management", "Container Delivery at Port"],
        horizontal=True,
    )
    
    # Salva o stage atual na sessão
    st.session_state["current_stage"] = choose

    if choose == "Sales Data":
        farol_ref_col = "Sales Farol Reference"
        df = get_data_salesData()
    elif choose == "Booking Management":
        farol_ref_col = "Booking Farol Reference"
        df = get_data_bookingData()
    elif choose == "Container Delivery at Port":
        farol_ref_col = "Loading Farol Reference"
        df = get_data_loadingData()

   # Aplica filtro para excluir splits pendentes de aprovação
    # Agora todas as tabelas têm acesso ao Type of Shipment via JOIN
    df = df[
        ~(
            (df["Type of Shipment"] == "Split") & 
            (df["Farol Status"] == "Adjustment Requested")
        )
    ]
 
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
 
    # Define colunas não editáveis e configurações de dropdowns
    disabled_columns = non_editable_columns(choose)
    df_udc = load_df_udc()
    column_config = drop_downs(df, df_udc)
 
    # 🔽 Adiciona coluna de seleção
    df["Selecionar"] = False
    column_config["Selecionar"] = st.column_config.CheckboxColumn("Select", help="Select only one line")
 
    # Reordena colunas
    colunas_ordenadas = ["Selecionar"] + [col for col in df.columns if col != "Selecionar"]
 
    # Guarda cópias sem a coluna "Selecionar" para comparação
    df_filtered_original = df.drop(columns=["Selecionar"], errors="ignore").copy()
 
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
 
    # Remove "Selecionar" para comparação
    edited_df_clean = edited_df.drop(columns=["Selecionar"], errors="ignore")
 
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
                            status_blocked_message = "⚠️ Status 'Adjustment Requested' não pode ser alterado diretamente. Use o módulo de ajustes para solicitar mudanças."
                    changes.append({
                        'Farol Reference': row.get(farol_ref_col, index),
                        "Coluna": col,
                        "Valor Anterior": original_row[col],
                        "Novo Valor": row[col],
                        "Stage": choose
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
   
        # Garante que a coluna Comentários exista
        if "Comentários" not in changes_df.columns:
           
            #Adicionando o stage para popular a tabela de log
            changes_df["Stage"] = choose
           
        col_left, col_adjust, col_right  = st.columns([3,1,3])  # Grade e campo de texto lado a lado
   
        with col_left:
 
            st.dataframe(
                changes_df[["Farol Reference", "Coluna", "Valor Anterior", "Novo Valor","Stage"]],
                use_container_width=True,
                hide_index=True)
   
        with col_right:
            st.text_area("📌 Informações Complementares", key="info_complementar")
   
           
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
                        st.success("✅ Alterações registradas com sucesso no banco!")
                        st.session_state["changes"] = pd.DataFrame()
                       
                        #Liberando o cache salvo das consultas
                        st.cache_data.clear()
                        resetar_estado()
                        st.rerun()
                        
                    else:
                        st.error("❌ Erro ao registrar os ajustes no banco.")
                else:
                    st.error("⚠️ O campo 'Informações Complementares' é obrigatório.")
 
        with col2:
            if st.button("❌ Discard Changes"):
 
                st.warning("Alterações descartadas.")
                st.session_state["changes"] = pd.DataFrame()
                st.session_state["grid_update_key"] = str(time.time())
                st.rerun()
 
    # Verifica se linha foi selecionada
    selected_rows = edited_df[edited_df["Selecionar"] == True]
    selected_farol_ref = None
    original_status = None
    selected_index = None
    if len(selected_rows) == 1:
        selected_farol_ref = selected_rows[farol_ref_col].values[0]
        st.session_state["selected_reference"] = selected_farol_ref
        selected_index = selected_rows.index[0]
        if "Farol Status" in df_filtered_original.columns:
            original_status = df_filtered_original.loc[selected_index, "Farol Status"]
    
    st.markdown("---")
    col_new, col_booking, col_split, _ = st.columns([1, 1, 1, 4])
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
 
 
 
       
 
 
# Executa a aplicação
if __name__ == "__main__":
    main()