##shipments_split.py
 
import streamlit as st
import pandas as pd
from database import load_df_udc, insert_adjustments_critic, perform_split_operation, get_split_data_by_farol_reference, fetch_shipments_data_sales
import re
from uuid import uuid4
import time
from datetime import datetime
 
# Carrega dados da UDC
df_udc = load_df_udc()
Booking_adj_area = df_udc[df_udc["grupo"] == "Booking Adj Area"]["dado"].dropna().unique().tolist()
Booking_adj_reason = df_udc[df_udc["grupo"] == "Booking Adj Request Reason"]["dado"].dropna().unique().tolist()
Booking_adj_responsibility = df_udc[df_udc["grupo"] == "Booking Adj Responsibility"]["dado"].dropna().unique().tolist()
 
def resetar_estado():
    keys_to_remove = [
        "selected_farol",
        "original_quantity",
        "split_editor",
        "selected_reference",
        "original_df_selected",
        "editor_key",
        "button_disabled"
    ]
    for key in keys_to_remove:
        st.session_state.pop(key, None)

def show_split_form():
    st.header("🛠️ Adjustments")
 
    # Inicializa estado do botão se necessário
    if "button_disabled" not in st.session_state:
        st.session_state.button_disabled = False

    # Inicializa a chave do editor se não existir
    if "editor_key" not in st.session_state:
        st.session_state.editor_key = "split_editor_0"
 
    if st.session_state.get("show_success"):
        st.success("✅ Ajuste realizado com sucesso!")
        st.session_state["show_success"] = False
 
    if "original_data" not in st.session_state:
        st.error("Erro: Dados ainda não carregados. Volte à página principal (Shipments).")
        st.stop()
 
    df_shipments = st.session_state["original_data"]
    
    # Determina qual coluna de referência usar com base no stage atual
    stage = st.session_state.get("current_stage", "Sales Data")
    if stage == "Sales Data":
        farol_column = "Sales Farol Reference"
    elif stage == "Booking Management":
        farol_column = "Booking Farol Reference"
    elif stage == "Container Delivery at Port":
        farol_column = "Loading Farol Reference"
    else:
        farol_column = "Sales Farol Reference"  # fallback padrão
        
    available_references = df_shipments[farol_column].dropna().unique()
 
    # Seleção da referência Farol com fallback para sessão
    col1, col2, _ = st.columns([1, 1, 3])
    with col1:
        if "selected_reference" in st.session_state:
            selected_farol = st.session_state["selected_reference"]
            st.text_input("Farol Reference", value=selected_farol, disabled=True)
            st.session_state["selected_farol"] = selected_farol
        else:
            if st.button("🔙 Voltar para Home"):
                resetar_estado()
                st.session_state["current_page"] = "main"
                st.rerun()
            st.stop()
 
    with col2:
        num_splits = st.number_input("Split number", min_value=0, max_value=13, value=0, step=1)
 
    def get_next_farol_refs(base_ref: str, num_splits: int) -> list[str]:
        """
        Gera as próximas referências Farol disponíveis para splits.
        
        Args:
            base_ref (str): Referência Farol base (ex: FR_25.01_0001)
            num_splits (int): Número de novas referências necessárias
        
        Returns:
            list[str]: Lista com as novas referências geradas
        """
        # Obtém todas as referências existentes
        df = fetch_shipments_data_sales()
        
        # Encontra todos os splits existentes para esta referência base
        base_pattern = re.escape(base_ref)
        existing_splits = df[df['Sales Farol Reference'].str.match(rf'^{base_pattern}(?:\.(\d+))?$')]
        
        # Se não houver splits existentes, começa do 1
        if existing_splits.empty:
            next_split = 1
        else:
            # Extrai os números dos splits existentes
            def extract_split_number(ref):
                match = re.search(rf'^{base_pattern}\.(\d+)$', ref)
                return int(match.group(1)) if match else 0
            
            split_numbers = [extract_split_number(ref) for ref in existing_splits['Sales Farol Reference']]
            next_split = max(split_numbers) + 1 if split_numbers else 1
        
        # Gera as novas referências
        new_refs = []
        for i in range(num_splits):
            new_refs.append(f"{base_ref}.{next_split + i}")
        
        return new_refs
 
    if selected_farol:
        # Buscar dados específicos do Farol Reference
        split_data = get_split_data_by_farol_reference(selected_farol)
       
        if not split_data:
            st.error("Erro: Dados não encontrados para o Farol Reference selecionado.")
            st.stop()
           
        # Criar DataFrame inicial com os dados obtidos
        df_selected = pd.DataFrame([{
            "Sales Farol Reference": split_data["s_farol_reference"],
            "Sales Quantity of Containers": split_data["s_quantity_of_containers"],
            "Sales Port of Loading POL": split_data["s_port_of_loading_pol"],
            "Sales Port of Delivery POD": split_data["s_port_of_delivery_pod"],
            "Sales Place of Receipt": split_data["s_place_of_receipt"],
            "Sales Final Destination": split_data["s_final_destination"],
            "Carrier": split_data["s_carrier"],
            "Requested Cut off Start Date": split_data["s_requested_deadlines_start_date"],
            "Requested Cut off End Date": split_data["s_requested_deadlines_end_date"],
            "Required Arrival Date": split_data["s_required_arrival_date"]
        }])
       
        new_refs = get_next_farol_refs(selected_farol, num_splits)
 
        # Guarda os dados originais na sessão se ainda não existirem
        if "original_df_selected" not in st.session_state:
            st.session_state["original_df_selected"] = df_selected.copy()
 
        df_split = pd.concat(
            [df_selected] + [df_selected.copy() for _ in range(num_splits)],
            ignore_index=True
        )
       
        for i, ref in enumerate(new_refs, start=1):
            df_split.at[i, "Sales Farol Reference"] = ref
            df_split.at[i, "Sales Quantity of Containers"] = 0
 
        editable_columns = [
            "Sales Farol Reference",
            "Sales Quantity of Containers",
            "Sales Port of Loading POL",
            "Sales Port of Delivery POD",
            "Sales Place of Receipt",
            "Sales Final Destination",
            "Carrier",
            "Requested Cut off Start Date",
            "Requested Cut off End Date",
            "Required Arrival Date"
        ]
 
        df_split_display = df_split[editable_columns].copy()
        st.markdown(f"#### You are splitting the original line into :green[{num_splits}] lines" if num_splits > 0 else "#### The main line will be adjusted")
        
        # Usa a chave dinâmica para o editor
        edited_display = st.data_editor(
            df_split_display,
            num_rows="fixed",
            use_container_width=True,
            key=st.session_state.editor_key
        )
 
        changes = []
        for col in df_split_display.columns:
            old_val = df_split_display.at[0, col]
            new_val = edited_display.at[0, col]
            if pd.isna(old_val) and pd.isna(new_val):
                continue
            if old_val != new_val:
                changes.append({
                    "Farol Reference": df_split.at[0, "Sales Farol Reference"],  # Sempre usar Sales Farol Reference
                    "Coluna": col,
                    "Valor Anterior": str(old_val) if pd.notna(old_val) else "",
                    "Novo Valor": str(new_val) if pd.notna(new_val) else "",
                    "Stage": "Sales Data"
                })
 
        if changes:
            changes_df = pd.DataFrame(changes)
            st.markdown("#### 🔍 Detected Changes (Original line)")
            st.dataframe(changes_df)
 
        # Justificativas
        st.markdown("#### Split Justifications" if num_splits > 0 else "#### Main Adjustment Justification")
        col_a, col_b, col_c = st.columns([1, 1, 1])
        with col_a:
            area = st.selectbox("Booking Adjustment Area", [""] + Booking_adj_area)
        with col_b:
            reason = st.selectbox("Booking Adjustment Request Reason", [""] + Booking_adj_reason)
        with col_c:
            responsibility = st.selectbox("Booking Adjustment Responsibility", [""] + Booking_adj_responsibility)
        col_d, col_e = st.columns([2, 1])
        with col_d:
            comment = st.text_area("Comentários")
 
        if "original_quantity" not in st.session_state:
            st.session_state["original_quantity"] = df_selected["Sales Quantity of Containers"].iloc[0]
 
        col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)
 
        with col_btn1:
            if st.button(
                "✅ Confirm",
                disabled=st.session_state.get("button_disabled", False)
            ):
                if not st.session_state.get("button_disabled", False):
                    # Verifica se houve alterações na linha principal
                    if not changes and num_splits == 0:
                        st.warning("⚠️ Nenhuma alteração detectada no item principal.")
                    elif not area or not reason or not responsibility:
                        st.error("Erro: Preencha todos os campos de justificativa (Area, Reason e Responsibility) antes de confirmar.")
                    else:
                        # Obter as quantidades dos splits antes da verificação
                        split_quantities = edited_display["Sales Quantity of Containers"].iloc[1:]
                        
                        if num_splits > 0 and (split_quantities <= 0).any():
                            st.error("Erro: Todos os splits devem ter quantidade maior que 0.")
                        else:
                            # Desabilita o botão imediatamente
                            st.session_state.button_disabled = True
                            original_quantity = st.session_state["original_quantity"]
                            total_split = split_quantities.sum()

                            edited_display.at[0, "Sales Quantity of Containers"] = original_quantity - total_split
                            df_split.update(edited_display)
 
                            # Gera um único UUID para toda a requisição
                            request_uuid = str(uuid4())
                            try:
                                with st.spinner("Processando ajustes, por favor aguarde..."):
                                    # Processa os ajustes da linha principal
                                    if changes:
                                        success = insert_adjustments_critic(
                                            changes_df=pd.DataFrame(changes),
                                            random_uuid=request_uuid,  # Usa o mesmo UUID
                                            area=area,
                                            reason=reason,
                                            responsibility=responsibility,
                                            comment=comment,
                                        )
 
                                    # Processa os splits apenas se houver splits
                                    if num_splits > 0:
                                        success = perform_split_operation(
                                            farol_ref_original=selected_farol,
                                            edited_display=edited_display,
                                            num_splits=num_splits,
                                            comment=comment,
                                            area=area,
                                            reason=reason,
                                            responsibility=responsibility,
                                            request_uuid=request_uuid  # Passa o UUID para a função
                                        )
                                    else:
                                        # Se não há splits, considera sucesso se os ajustes da linha principal foram processados
                                        success = True if not changes else success
 
                                if success:
                                    st.success("✅ Ajuste realizado com sucesso!")
                                    time.sleep(2)  # Aguarda 2 segundos
                                    # Limpa os estados antes de redirecionar
                                    resetar_estado()
                                    st.session_state["current_page"] = "main"
                                    st.rerun()
                                else:
                                    # Reabilita o botão em caso de erro
                                    st.session_state.button_disabled = False
                                    st.error("Erro ao registrar os ajustes no banco de dados.")
                            except Exception as e:
                                # Reabilita o botão em caso de erro
                                st.session_state.button_disabled = False
                                st.error(f"Erro ao processar os ajustes: {str(e)}")
 
        with col_btn2:
            if st.button("🗑️ Discard Changes"):
                # Gera uma nova chave para forçar a recriação do editor
                st.session_state.editor_key = f"split_editor_{time.time()}"
                st.success("Alterações descartadas com sucesso.")
                st.rerun()
 
        with col_btn3:
            if st.button("🔙 Back to Shipments"):
                st.session_state["current_page"] = "main"
                st.rerun()
 
    else:
        st.info("Select a Farol Reference to start the Adjustment.")
        col_btn1, col_btn2 = st.columns(2)
 
        with col_btn2:
            if st.button("🔙 Back to Shipments"):
                st.session_state["current_page"] = "main"
                st.rerun()
 
if __name__ == "__main__":
    show_split_form()
 
def generate_next_farol_reference():
    # Obtendo df atualizado em tempo real, sem estar em cache
    df = fetch_shipments_data_sales()

    date = datetime.today()
    date_str = date.strftime('%y.%m')  # Formato: 25.01 (ano com 2 dígitos.mês com 2 dígitos)
    prefix = f'FR_{date_str}'

    # Filtra referências do mesmo mês
    same_month_refs = df[df['Sales Farol Reference'].str.startswith(prefix, na=False)]

    if same_month_refs.empty:
        return f'{prefix}_0001'

    # Extrai o número sequencial base (ignorando splits)
    def extract_base_seq(ref):
        try:
            # Divide a referência em partes
            parts = ref.split('_')
            if len(parts) > 1:
                # Pega a última parte e remove qualquer número de split após o ponto
                seq_str = parts[-1].split('.')[0]
                return int(seq_str)
            return 0
        except:
            return 0  # fallback seguro

    # Aplica a função em todas as referências
    same_month_refs['SEQ'] = same_month_refs['Sales Farol Reference'].apply(extract_base_seq)

    # Encontra o maior número sequencial
    max_seq = same_month_refs['SEQ'].max()
    next_seq = max_seq + 1

    return f'{prefix}_{next_seq:04d}'
 
 