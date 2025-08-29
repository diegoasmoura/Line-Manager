import streamlit as st
import pandas as pd
from database import get_return_carriers_by_farol, get_return_carriers_recent, load_df_udc, get_database_connection, update_sales_booking_from_return_carriers, update_return_carrier_status, get_current_status_from_main_table
from booking_adjustments import display_attachments_section
from shipments_mapping import get_column_mapping
from sqlalchemy import text
from datetime import datetime

def exibir_history():
    st.title("📜 Return Carriers History")

    farol_reference = st.session_state.get("selected_reference")
    if not farol_reference:
        st.info("Selecione uma linha em Shipments para visualizar o histórico.")
        col = st.columns(1)[0]
        with col:
            if st.button("🔙 Back to Shipments"):
                st.session_state["current_page"] = "main"
                st.rerun()
        return

    st.subheader(f"Farol Reference: {farol_reference}")

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

    # Métricas rápidas
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Farol Status", str(df.iloc[0].get("B_BOOKING_STATUS", "-")))
    with c2:
        st.metric("Voyage Carrier", str(df.iloc[0].get("B_VOYAGE_CARRIER", "-")))
    with c3:
        qty = df.iloc[0].get("S_QUANTITY_OF_CONTAINERS", 0)
        try:
            qty = int(qty) if qty is not None and pd.notna(qty) else 0
        except (ValueError, TypeError):
            qty = 0
        st.metric("Quantity of Containers", qty)
    with c4:
        ins = df.iloc[0].get("ROW_INSERTED_DATE", "-")
        try:
            # Converte epoch ms para datetime legível, se for numérico
            if isinstance(ins, (int, float)):
                ins = datetime.fromtimestamp(ins/1000.0).strftime('%Y-%m-%d %H:%M')
        except Exception:
            pass
        st.metric("Inserted", str(ins))

    st.markdown("---")

    # Grade principal com colunas relevantes (incluindo ADJUSTMENT_ID)
    display_cols = [
        "FAROL_REFERENCE",
        "ADJUSTMENT_ID",  # Campo oculto para identificação
        "B_BOOKING_STATUS",
        "S_SPLITTED_BOOKING_REFERENCE",
        "S_PLACE_OF_RECEIPT",
        "S_QUANTITY_OF_CONTAINERS",
        "S_PORT_OF_LOADING_POL",
        "S_PORT_OF_DELIVERY_POD",
        "S_FINAL_DESTINATION",
        "B_TRANSHIPMENT_PORT",
        "B_PORT_TERMINAL_CITY",
        "B_VESSEL_NAME",
        "B_VOYAGE_CARRIER",
        "B_DOCUMENT_CUT_OFF_DOCCUT",
        "B_PORT_CUT_OFF_PORTCUT",
        "B_ESTIMATED_TIME_OF_DEPARTURE_ETD",
        "B_ESTIMATED_TIME_OF_ARRIVAL_ETA",
        "B_GATE_OPENING",
        "P_STATUS",
        "P_PDF_NAME",
        "ROW_INSERTED_DATE",
        "USER_INSERT",
    ]

    df_show = df[[c for c in display_cols if c in df.columns]].copy()

    # Converte epoch (ms) para datetime para exibição correta na grade
    if "ROW_INSERTED_DATE" in df_show.columns:
        try:
            df_show["ROW_INSERTED_DATE"] = pd.to_datetime(df_show["ROW_INSERTED_DATE"], unit="ms", errors="coerce")
        except Exception:
            pass

    # Aplica aliases iguais aos da grade principal quando disponíveis
    mapping_main = get_column_mapping()
    mapping_upper = {k.upper(): v for k, v in mapping_main.items()}

    def prettify(col: str) -> str:
        # Fallback: transforma COL_NAME -> Col Name e normaliza acrônimos
        label = col.replace("_", " ").title()
        # Normaliza acrônimos comuns
        replaces = {
            "Pol": "POL",
            "Pod": "POD",
            "Etd": "ETD",
            "Eta": "ETA",
            "Pdf": "PDF",
            "Id": "ID",
        }
        for k, v in replaces.items():
            label = label.replace(k, v)
        return label

    custom_overrides = {
        "FAROL_REFERENCE": "Farol Reference",
        "ADJUSTMENT_ID": "Adjustment ID",  # Campo oculto
        "B_BOOKING_STATUS": "Farol Status",
        "ROW_INSERTED_DATE": "Inserted Date",
        "USER_INSERT": "Inserted By",
        # Remover prefixos B_/P_ dos rótulos solicitados
        "B_GATE_OPENING": "Gate Opening",
        "P_STATUS": "Status",
        "P_PDF_NAME": "PDF Name",
        "S_QUANTITY_OF_CONTAINERS": "Quantity of Containers",
    }

    rename_map = {}
    for col in df_show.columns:
        rename_map[col] = custom_overrides.get(col, mapping_upper.get(col, prettify(col)))

    df_show.rename(columns=rename_map, inplace=True)

    # Move "Inserted Date" para a primeira coluna e ordena de forma crescente
    if "Inserted Date" in df_show.columns:
        # Ordena pela data (crescente)
        try:
            df_show = df_show.sort_values("Inserted Date", ascending=True)
        except Exception:
            pass

    # Opções para Farol Status vindas da UDC (mesma lógica da Adjustment Request Management)
    df_udc = load_df_udc()
    farol_status_options = df_udc[df_udc["grupo"] == "Farol Status"]["dado"].dropna().unique().tolist()
    relevant_status = [
        "Booking Approved",
        "Booking Rejected",
        "Booking Cancelled",
        "Adjustment Requested",
    ]
    available_options = [s for s in relevant_status if s in farol_status_options]
    if not available_options:
        available_options = relevant_status
    # Garante "Adjustment Requested" no final
    if "Adjustment Requested" not in available_options:
        available_options.append("Adjustment Requested")
    elif available_options and available_options[-1] != "Adjustment Requested":
        available_options.remove("Adjustment Requested")
        available_options.append("Adjustment Requested")
    # Remove vazios/nulos
    available_options = [opt for opt in available_options if opt and str(opt).strip()]

    column_config = {
        "Farol Status": st.column_config.TextColumn(
            "Farol Status", disabled=True
        )
    }
    # Demais colunas somente leitura
    # Adiciona coluna de seleção e configura
    df_show.insert(0, "Selecionar", False)
    column_config["Selecionar"] = st.column_config.CheckboxColumn(
        "Select", help="Selecione apenas uma linha para aplicar mudanças", pinned="left"
    )
    
    # Reordena colunas - mantém "Selecionar" como primeira coluna
    if "Inserted Date" in df_show.columns:
        other_cols = [c for c in df_show.columns if c not in ["Selecionar", "Inserted Date"]]
        ordered_cols = ["Selecionar", "Inserted Date"] + other_cols
        # Filtra apenas as colunas que existem no DataFrame
        existing_cols = [c for c in ordered_cols if c in df_show.columns]
        df_show = df_show[existing_cols]

    # Configura colunas - ADJUSTMENT_ID fica oculto
    for col in df_show.columns:
        if col == "Farol Status":
            continue
        if col == "Adjustment ID":
            # Campo oculto - não exibido na grade
            continue
        if col == "Selecionar":
            # Coluna de seleção já configurada
            continue
        if col == "Inserted Date":
            column_config[col] = st.column_config.DatetimeColumn("Inserted Date", format="YYYY-MM-DD HH:mm", disabled=True)
        else:
            column_config[col] = st.column_config.TextColumn(col, disabled=True)

    original_df = df_show.copy()
    edited_df = st.data_editor(
        df_show,
        use_container_width=True,
        hide_index=True,
        column_config=column_config,
        disabled=False,
        key="history_return_carriers_editor"
    )

    # Interface de botões de status para linha selecionada
    selected = edited_df[edited_df["Selecionar"] == True]
    if len(selected) > 1:
        st.warning("⚠️ Selecione apenas uma linha para aplicar mudanças.")
    
    # Interface de botões de status para linha selecionada
    if len(selected) == 1:
        st.markdown("---")
        st.markdown("### 🔄 Status Management")
        
        # Obtém informações da linha selecionada (usar diretamente a série selecionada para evitar divergência de índice)
        selected_row = selected.iloc[0]
        farol_ref = selected_row.get("Farol Reference") or selected_row.get("FAROL_REFERENCE")
        adjustment_id = selected_row.get("Adjustment ID")
        
        # Obtém o status da linha selecionada na tabela F_CON_RETURN_CARRIERS
        selected_row_status = selected_row.get("Farol Status", "")
        
        # Obtém o status atual da tabela principal F_CON_SALES_BOOKING_DATA
        current_status = get_current_status_from_main_table(farol_ref)
        
        # Mostra status atual
        col1, col2 = st.columns([2, 1])
        with col1:
            st.info(f"**Current Status:** {current_status}")
        with col2:
            st.info(f"**Farol Reference:** {farol_ref}")
        
        # Verifica se o status da linha selecionada é "Booking Requested" - se for, não permite alterações
        if selected_row_status == "Booking Requested":
            st.warning("⚠️ **Esta etapa não pode ser alterada pelo usuário**")
            st.info(f"📋 O status '{selected_row_status}' é uma etapa protegida do sistema")
            
            # Botão de reset apenas
            if st.button("🔄 Reset Selection", key="reset_selection", use_container_width=True):
                st.rerun()
        else:
            # Botões de status com layout elegante
            st.markdown("#### Select New Status:")
            
            # Todos os botões em uma linha
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if st.button("🟢 Booking Approved", 
                            key="status_booking_approved",
                            use_container_width=True,
                            type="secondary" if current_status == "Booking Approved" else "primary"):
                    if current_status != "Booking Approved":
                        apply_status_change(farol_ref, adjustment_id, "Booking Approved")
            
            with col2:
                if st.button("🔴 Booking Rejected", 
                            key="status_booking_rejected",
                            use_container_width=True,
                            type="secondary" if current_status == "Booking Rejected" else "primary"):
                    if current_status != "Booking Rejected":
                        apply_status_change(farol_ref, adjustment_id, "Booking Rejected")
            
            with col3:
                if st.button("⚫ Booking Cancelled", 
                            key="status_booking_cancelled",
                            use_container_width=True,
                            type="secondary" if current_status == "Booking Cancelled" else "primary"):
                    if current_status != "Booking Cancelled":
                        apply_status_change(farol_ref, adjustment_id, "Booking Cancelled")
            
            with col4:
                if st.button("🟡 Adjustment Requested", 
                            key="status_adjustment_requested",
                            use_container_width=True,
                            type="secondary" if current_status == "Adjustment Requested" else "primary"):
                    if current_status != "Adjustment Requested":
                        apply_status_change(farol_ref, adjustment_id, "Adjustment Requested")
            
            # Botão de reset
            if st.button("🔄 Reset Selection", key="reset_selection", use_container_width=True):
                st.rerun()
    else:
        # Mensagem quando nenhuma linha está selecionada
        st.markdown("---")
        st.info("📋 **Selecione uma linha na grade acima para gerenciar o status**")
        st.markdown("💡 **Dica:** Marque o checkbox de uma linha para ver as opções de status disponíveis")
    
    # Função para aplicar mudanças de status
    def apply_status_change(farol_ref, adjustment_id, new_status):
        try:
            conn = get_database_connection()
            tx = conn.begin()
            
            # Se o status foi alterado para "Booking Approved", executa a lógica de aprovação
            if new_status == "Booking Approved" and adjustment_id:
                # Atualiza a tabela F_CON_SALES_BOOKING_DATA com os dados da linha aprovada
                if update_sales_booking_from_return_carriers(adjustment_id):
                    st.success(f"✅ Dados atualizados na tabela F_CON_SALES_BOOKING_DATA para {farol_ref}")
                else:
                    st.warning(f"⚠️ Nenhum dado foi atualizado para {farol_ref} (todos os campos estavam vazios)")
            
            # Atualiza o status na tabela F_CON_RETURN_CARRIERS
            if update_return_carrier_status(adjustment_id, new_status):
                st.success(f"✅ Status atualizado na tabela F_CON_RETURN_CARRIERS para {farol_ref}")
            
            # Atualiza status no log (se existir)
            update_log_query = text("""
                UPDATE LogTransp.F_CON_Adjustments_Log
                   SET status = :new_status,
                       confirmation_date = :confirmation_date
                 WHERE farol_reference = :farol_reference
            """)
            conn.execute(update_log_query, {
                "new_status": new_status,
                "confirmation_date": datetime.now() if new_status in ["Booking Approved", "Booking Rejected", "Booking Cancelled"] else None,
                "farol_reference": farol_ref
            })

            # Atualiza status nas tabelas principais
            conn.execute(text("""
                UPDATE LogTransp.F_CON_SALES_BOOKING_DATA
                   SET FAROL_STATUS = :farol_status
                 WHERE FAROL_REFERENCE = :farol_reference
            """), {"farol_status": new_status, "farol_reference": farol_ref})

            conn.execute(text("""
                UPDATE LogTransp.F_CON_CARGO_LOADING_CONTAINER_RELEASE
                   SET l_farol_status = :farol_status,
                       l_creation_of_cargo_loading = :creation_date
                 WHERE l_farol_reference = :farol_reference
            """), {"farol_status": new_status, "creation_date": datetime.now(), "farol_reference": farol_ref})

            tx.commit()
            st.success(f"✅ Status atualizado com sucesso para {farol_ref}!")
            st.rerun()
            
        except Exception as e:
            if 'tx' in locals():
                tx.rollback()
            st.error(f"❌ Erro ao atualizar status: {str(e)}")
        finally:
            if 'conn' in locals():
                conn.close()

    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔙 Back to Shipments"):
            st.session_state["current_page"] = "main"
            st.rerun()
    with col2:
        # Toggle de anexos
        view_open = st.session_state.get("history_show_attachments", False)
        if st.button("📎 View Attachments", key="history_view_attachments"):
            st.session_state["history_show_attachments"] = not view_open
            st.rerun()
    with col3:
        st.download_button("⬇️ Export CSV", data=df_show.to_csv(index=False).encode("utf-8"), file_name=f"return_carriers_{farol_reference}.csv", mime="text/csv")

    # Seção de anexos (toggle)
    if st.session_state.get("history_show_attachments", False):
        st.markdown("---")
        st.subheader("📎 Attachment Management")
        display_attachments_section(farol_reference)