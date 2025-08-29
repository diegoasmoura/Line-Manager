import streamlit as st
import pandas as pd
from database import get_return_carriers_by_farol, get_return_carriers_recent, load_df_udc, get_database_connection, update_sales_booking_from_return_carriers, update_return_carrier_status, get_current_status_from_main_table, get_return_carrier_status_by_adjustment_id
from booking_adjustments import display_attachments_section
from shipments_mapping import get_column_mapping
from sqlalchemy import text
from datetime import datetime

def exibir_history():
    st.header("📜 Return Carriers History")

    farol_reference = st.session_state.get("selected_reference")
    if not farol_reference:
        st.info("Selecione uma linha em Shipments para visualizar o histórico.")
        col = st.columns(1)[0]
        with col:
            if st.button("🔙 Back to Shipments"):
                st.session_state["current_page"] = "main"
                st.rerun()
        return



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


    
    # Informações organizadas em cards elegantes
    main_status = get_current_status_from_main_table(farol_reference) or "-"
    voyage_carrier = str(df.iloc[0].get("B_VOYAGE_CARRIER", "-"))
    
    qty = df.iloc[0].get("S_QUANTITY_OF_CONTAINERS", 0)
    try:
        qty = int(qty) if qty is not None and pd.notna(qty) else 0
    except (ValueError, TypeError):
        qty = 0
    
    ins = df.iloc[0].get("ROW_INSERTED_DATE", "-")
    try:
        # Converte epoch ms para datetime legível, se for numérico
        if isinstance(ins, (int, float)):
            ins = datetime.fromtimestamp(ins/1000.0).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        pass
    
    # Layout em uma linha com 5 colunas
    col1, col2, col3, col4, col5 = st.columns(5, gap="small")
    
    with col1:
        st.markdown(f"""
        <div style="
            background: white;
            padding: 1rem;
            border-radius: 12px;
            border-left: 4px solid #E91E63;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            text-align: center;
        ">
            <div style="color: #666; font-size: 0.75rem; margin-bottom: 0.3rem; font-weight: 500;">FAROL REFERENCE</div>
            <div style="color: #333; font-size: 1rem; font-weight: 600;">{farol_reference}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div style="
            background: white;
            padding: 1rem;
            border-radius: 12px;
            border-left: 4px solid #4CAF50;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            text-align: center;
        ">
            <div style="color: #666; font-size: 0.75rem; margin-bottom: 0.3rem; font-weight: 500;">FAROL STATUS</div>
            <div style="color: #333; font-size: 1rem; font-weight: 600;">{main_status}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div style="
            background: white;
            padding: 1rem;
            border-radius: 12px;
            border-left: 4px solid #FF9800;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            text-align: center;
        ">
            <div style="color: #666; font-size: 0.75rem; margin-bottom: 0.3rem; font-weight: 500;">QUANTITY OF CONTAINERS</div>
            <div style="color: #333; font-size: 1rem; font-weight: 600;">{qty}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div style="
            background: white;
            padding: 1rem;
            border-radius: 12px;
            border-left: 4px solid #2196F3;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            text-align: center;
        ">
            <div style="color: #666; font-size: 0.75rem; margin-bottom: 0.3rem; font-weight: 500;">VOYAGE CARRIER</div>
            <div style="color: #333; font-size: 1rem; font-weight: 600;">{voyage_carrier}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        st.markdown(f"""
        <div style="
            background: white;
            padding: 1rem;
            border-radius: 12px;
            border-left: 4px solid #9C27B0;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            text-align: center;
        ">
            <div style="color: #666; font-size: 0.75rem; margin-bottom: 0.3rem; font-weight: 500;">INSERTED</div>
            <div style="color: #333; font-size: 1rem; font-weight: 600;">{ins}</div>
        </div>
        """, unsafe_allow_html=True)

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

    # Função para aplicar mudanças de status (declarada antes do uso)
    def apply_status_change(farol_ref, adjustment_id, new_status, selected_row_status=None):
        try:
            conn = get_database_connection()
            tx = conn.begin()
            
            # Resolve ADJUSTMENT_ID (usa o passado ou busca por fallback)
            adj_id = (str(adjustment_id).strip() if adjustment_id is not None else None)
            if not adj_id or adj_id.lower() in ("none", "nan", "null", ""):
                # Fallback: tenta pelo FAROL_REFERENCE e, se informado, pelo status da linha selecionada
                try:
                    if selected_row_status:
                        sql_adj = text("""
                            SELECT ADJUSTMENT_ID
                              FROM LogTransp.F_CON_RETURN_CARRIERS
                             WHERE FAROL_REFERENCE = :farol_reference
                               AND B_BOOKING_STATUS = :status_atual
                          ORDER BY ROW_INSERTED_DATE DESC
                          FETCH FIRST 1 ROWS ONLY
                        """)
                        adj_id = conn.execute(sql_adj, {"farol_reference": farol_ref, "status_atual": selected_row_status}).scalar()
                    if not adj_id:
                        sql_adj_any = text("""
                            SELECT ADJUSTMENT_ID
                              FROM LogTransp.F_CON_RETURN_CARRIERS
                             WHERE FAROL_REFERENCE = :farol_reference
                          ORDER BY ROW_INSERTED_DATE DESC
                          FETCH FIRST 1 ROWS ONLY
                        """)
                        adj_id = conn.execute(sql_adj_any, {"farol_reference": farol_ref}).scalar()
                    if adj_id:
                        adj_id = str(adj_id).strip()
                        st.caption(f"DEBUG: ADJUSTMENT_ID usado={adj_id}")
                except Exception:
                    pass
            
            # Se o status foi alterado para "Booking Approved", executa a lógica de aprovação
            if new_status == "Booking Approved" and adj_id:
                # Atualiza a tabela F_CON_SALES_BOOKING_DATA com os dados da linha aprovada
                if update_sales_booking_from_return_carriers(adj_id):
                    st.success(f"✅ Dados atualizados na tabela F_CON_SALES_BOOKING_DATA para {farol_ref}")
                else:
                    st.warning(f"⚠️ Nenhum dado foi atualizado para {farol_ref} (todos os campos estavam vazios)")

            # Atualiza o status na tabela F_CON_RETURN_CARRIERS SEMPRE (na mesma transação)
            # Sanity check: existe linha com esse ADJUSTMENT_ID?
            try:
                exists_cnt = conn.execute(text("""
                    SELECT COUNT(*) FROM LogTransp.F_CON_RETURN_CARRIERS WHERE ADJUSTMENT_ID = :adjustment_id
                """), {"adjustment_id": adj_id}).scalar()
                st.caption(f"DEBUG: adjustment_id={adj_id}, rows_encontradas={exists_cnt}")
            except Exception:
                exists_cnt = None

            res_rc = conn.execute(text("""
                UPDATE LogTransp.F_CON_RETURN_CARRIERS
                   SET B_BOOKING_STATUS = :new_status,
                       USER_UPDATE = :user_update,
                       DATE_UPDATE = SYSDATE
                 WHERE ADJUSTMENT_ID = :adjustment_id
            """), {
                "new_status": new_status,
                "user_update": "System",
                "adjustment_id": adj_id,
            })
            if getattr(res_rc, "rowcount", 0) > 0:
                st.success(f"✅ Status atualizado em F_CON_RETURN_CARRIERS para {farol_ref}")
            else:
                st.warning("⚠️ Nenhuma linha foi atualizada em F_CON_RETURN_CARRIERS (verifique o ADJUSTMENT_ID)")

            # Regras específicas por status
            if new_status in ["Booking Rejected", "Booking Cancelled", "Adjustment Requested"]:
                # Atualiza SOMENTE a coluna FAROL_STATUS na tabela principal
                conn.execute(text("""
                    UPDATE LogTransp.F_CON_SALES_BOOKING_DATA
                       SET FAROL_STATUS = :farol_status
                     WHERE FAROL_REFERENCE = :farol_reference
                """), {"farol_status": new_status, "farol_reference": farol_ref})
                st.success(f"✅ FAROL_STATUS atualizado em F_CON_SALES_BOOKING_DATA para {farol_ref}")
            else:
                # Demais status (Approved)
                conn.execute(text("""
                    UPDATE LogTransp.F_CON_SALES_BOOKING_DATA
                       SET FAROL_STATUS = :farol_status
                     WHERE FAROL_REFERENCE = :farol_reference
                """), {"farol_status": new_status, "farol_reference": farol_ref})

            # Verificação pós-aprovação: comparar campos entre as duas tabelas
            if new_status == "Booking Approved":
                try:
                    fields = [
                        "S_SPLITTED_BOOKING_REFERENCE","S_PLACE_OF_RECEIPT","S_QUANTITY_OF_CONTAINERS",
                        "S_PORT_OF_LOADING_POL","S_PORT_OF_DELIVERY_POD","S_FINAL_DESTINATION",
                        "B_TRANSHIPMENT_PORT","B_PORT_TERMINAL_CITY","B_VESSEL_NAME","B_VOYAGE_CARRIER",
                        "B_DOCUMENT_CUT_OFF_DOCCUT","B_PORT_CUT_OFF_PORTCUT","B_ESTIMATED_TIME_OF_DEPARTURE_ETD",
                        "B_ESTIMATED_TIME_OF_ARRIVAL_ETA","B_GATE_OPENING"
                    ]
                    cols = ", ".join(fields)
                    # Retorno: pela linha aprovada
                    rc_row = conn.execute(text(f"""
                        SELECT {cols}
                          FROM LogTransp.F_CON_RETURN_CARRIERS
                         WHERE ADJUSTMENT_ID = :adj
                    """), {"adj": adj_id}).mappings().fetchone()
                    # Principal: pela referência
                    sb_row = conn.execute(text(f"""
                        SELECT {cols}
                          FROM LogTransp.F_CON_SALES_BOOKING_DATA
                         WHERE FAROL_REFERENCE = :ref
                    """), {"ref": farol_ref}).mappings().fetchone()
                    if rc_row and sb_row:
                        st.markdown("#### 🔎 Pós-aprovação (comparação de campos)")
                        for f in fields:
                            st.caption(f"{f}: RC='{rc_row.get(f)}' → SB='{sb_row.get(f)}'")
                except Exception as _:
                    pass

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
        
        # Obtém o status da linha selecionada na tabela F_CON_RETURN_CARRIERS (prioriza leitura por UUID)
        selected_row_status = get_return_carrier_status_by_adjustment_id(adjustment_id) or selected_row.get("Farol Status", "")
        
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
            
            # Botões de status com espaçamento reduzido
            col1, col2, col3, col4 = st.columns([1, 1, 1, 1], gap="small")
            
            with col1:
                if st.button("Booking Approved", 
                            key="status_booking_approved",
                            type="secondary"):
                    if current_status != "Booking Approved":
                        st.session_state["pending_status_change"] = "Booking Approved"
                        st.rerun()
            
            with col2:
                if st.button("Booking Rejected", 
                            key="status_booking_rejected",
                            type="secondary"):
                    if current_status != "Booking Rejected":
                        st.session_state["pending_status_change"] = "Booking Rejected"
                        st.rerun()
            
            with col3:
                if st.button("Booking Cancelled", 
                            key="status_booking_cancelled",
                            type="secondary"):
                    if current_status != "Booking Cancelled":
                        st.session_state["pending_status_change"] = "Booking Cancelled"
                        st.rerun()
            
            with col4:
                if st.button("Adjustment Requested", 
                            key="status_adjustment_requested",
                            type="secondary"):
                    if current_status != "Adjustment Requested":
                        st.session_state["pending_status_change"] = "Adjustment Requested"
                        st.rerun()
            
            # Confirmação quando há status pendente
            pending_status = st.session_state.get("pending_status_change")
            if pending_status:
                # Se o status pendente é igual ao status atual, limpa automaticamente
                if pending_status == current_status:
                    st.session_state.pop("pending_status_change", None)
                    st.rerun()
                else:
                    st.markdown("---")
                    st.warning(f"**Confirmar alteração para:** {pending_status}")
                    
                    col1, col2 = st.columns([1, 3])
                    with col1:
                        subcol1, subcol2 = st.columns(2, gap="small")
                        with subcol1:
                            if st.button("✅ Confirmar", 
                                        key="confirm_status_change",
                                        type="primary"):
                                # Executa a mudança de status
                                apply_status_change(farol_ref, adjustment_id, pending_status, selected_row_status)
                                # Limpa o status pendente
                                st.session_state.pop("pending_status_change", None)
                                st.rerun()
                        
                        with subcol2:
                            if st.button("❌ Cancelar", 
                                        key="cancel_status_change",
                                        type="secondary"):
                                # Limpa o status pendente
                                st.session_state.pop("pending_status_change", None)
                                st.rerun()
            

    else:
        # Mensagem quando nenhuma linha está selecionada
        st.markdown("---")
        st.info("📋 **Selecione uma linha na grade acima para gerenciar o status**")
        st.markdown("💡 **Dica:** Marque o checkbox de uma linha para ver as opções de status disponíveis")
    
    # Função para aplicar mudanças de status (versão antiga removida; definida acima)

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