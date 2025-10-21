## shipments.py
 
# Imports principais
import streamlit as st
import pandas as pd
from sqlalchemy import text
import time
import uuid
import io
from datetime import datetime
from auth.login import has_access_level  # NEW: Controle de acesso
 
# Importa funções para interações com banco de dados e UDC
from database import (
    get_data_salesData,           # Carrega os dados dos embarques na tabela de Sales Data
    get_data_bookingData,         # Carrega os dados dos embarques na tabela Booking management
    get_data_generalView,         # Carrega os dados da visão geral
    get_data_loadingData,         # Carrega os dados dos embarques na tabela Container Loading
    load_df_udc,                  # Carrega as opções de UDC (dropdowns)
    get_actions_count_by_farol_reference,  # Conta ações por Farol Reference
    get_database_connection       # Conexão direta para consultas auxiliares
)
 
# Importa funções auxiliares de mapeamento e formulários
from shipments_mapping import  non_editable_columns, drop_downs, clean_farol_status_value, process_farol_status_for_database
from shipments_new import show_add_form
from shipments_split import show_split_form
from booking_new import show_booking_management_form
from history import exibir_history
 
 
# --- NOVA PÁGINA: Formulário detalhado por referência ---
def exibir_formulario():
    st.title("📝 Shipment Form View")
    farol_ref = st.session_state.get("selected_reference")
    if not farol_ref:
        st.warning("Selecione uma linha na grade e clique em 📝 Form View.")
        if st.button("⬅️ Voltar"):
            st.session_state["current_page"] = "main"
            st.rerun()
        return

    st.caption(f"Farol Reference: {farol_ref}")
    
    # Sem CSS personalizado - usando estrutura padrão do Streamlit

    # Carregar dados por referência
    from database import (
        get_sales_record_by_reference,
        get_booking_record_by_reference,
        get_database_connection,
        begin_change_batch,
        end_change_batch,
        audit_change,
        update_field_in_sales_booking_data,
    )
    from shipments_mapping import (
        non_editable_columns,
        drop_downs,
        get_display_names,
        get_database_column_name,
        clean_farol_status_value,
        process_farol_status_for_database,
        get_reverse_mapping,
    )

    df_sales = get_sales_record_by_reference(str(farol_ref))
    df_booking = get_booking_record_by_reference(str(farol_ref))

    # Garantir existência de DF mesmo vazio
    if df_sales is None:
        df_sales = pd.DataFrame()
    if df_booking is None:
        df_booking = pd.DataFrame()

    # UDC e configs
    df_udc = load_df_udc()

    # Sempre manter as duas abas visíveis
    tab_sales, tab_booking = st.tabs(["Sales Data", "Booking Management"])

    # --- SALES TAB (formulário) ---
    with tab_sales:
        stage = "Sales Data"
        disabled_cols = set(non_editable_columns(stage))
        df_s_view = df_sales.copy()
        if not df_s_view.empty and "Sales Farol Reference" in df_s_view.columns:
            df_s_view.rename(columns={"Sales Farol Reference": "Farol Reference"}, inplace=True)
        if "Farol Reference" not in df_s_view.columns:
            df_s_view["Farol Reference"] = farol_ref

        # Fallback: garantir presença de data_required_sail_date no Form View
        # Caso apenas s_required_sail_date exista (vindo da query), cria a coluna normalizada
        if "data_required_sail_date" not in df_s_view.columns:
            if "s_required_sail_date" in df_s_view.columns:
                try:
                    df_s_view["data_required_sail_date"] = df_s_view["s_required_sail_date"]
                except Exception:
                    df_s_view["data_required_sail_date"] = None
            else:
                df_s_view["data_required_sail_date"] = None

        # Extrai linha única de referência
        row_sales = df_s_view.iloc[0] if not df_s_view.empty else pd.Series(dtype=object)

        # Opções UDC
        farol_status_options = sorted(list(set([
            opt for opt in df_udc[df_udc["grupo"] == "Farol Status"]["dado"].dropna().astype(str).tolist()
        ])))
        # Adiciona ícones conforme mapeamento
        from shipments_mapping import get_display_from_status
        farol_status_options = [get_display_from_status(s) for s in farol_status_options]
        type_of_shipment_options = [""
        ] + df_udc[df_udc["grupo"] == "Type of Shipment"]["dado"].dropna().astype(str).unique().tolist()
        container_type_options = [""
        ] + df_udc[df_udc["grupo"] == "Container Type"]["dado"].dropna().astype(str).unique().tolist()
        ports_pol_options = [""
        ] + df_udc[df_udc["grupo"] == "Porto Origem"]["dado"].dropna().astype(str).unique().tolist()
        ports_pod_options = [""
        ] + df_udc[df_udc["grupo"] == "Porto Destino"]["dado"].dropna().astype(str).unique().tolist()
        yes_no_options = ["", "Yes", "No"]
        dthc_options = [""
        ] + df_udc[df_udc["grupo"] == "DTHC"]["dado"].dropna().astype(str).unique().tolist()
        vip_pnl_risk_options = [""
        ] + df_udc[df_udc["grupo"] == "VIP PNL Risk"]["dado"].dropna().astype(str).unique().tolist()
        business_options = [""
        ] + df_udc[df_udc["grupo"] == "Business"]["dado"].dropna().astype(str).unique().tolist()
        mode_options = [""
        ] + df_udc[df_udc["grupo"] == "Mode"]["dado"].dropna().astype(str).unique().tolist()
        sku_options = [""
        ] + df_udc[df_udc["grupo"] == "Sku"]["dado"].dropna().astype(str).unique().tolist()
        incoterm_options = [""
        ] + df_udc[df_udc["grupo"] == "Incoterm"]["dado"].dropna().astype(str).unique().tolist()

        st.subheader("Sales Data")
        with st.form(f"sales_form_{farol_ref}_{st.session_state.get('form_reset_counter', 0)}"):
            # Ordem exata conforme grid
            sales_order = [
                "Sales Farol Reference", "Splitted Booking Reference", "Farol Status", "Type of Shipment", "Booking Status", "Booking Reference",
                "Sales Quantity of Containers", "Container Type",
                "Port of Loading POL", "Port of Delivery POD", "Place of Receipt", "Final Destination",
                "Shipment Requested Date", "Requested Shipment Week", "data_requested_deadline_start", "data_requested_deadline_end",
                "data_shipment_period_start", "data_shipment_period_end", "data_required_sail_date", "data_required_arrival_expected",
                "Sales Order Reference", "data_sales_order", "Business", "Customer",
                "Incoterm", "DTHC", "Afloat", "VIP PNL Risk", "PNL Destination",
                "data_allocation", "data_producer_nomination", "data_lc_received", "Sales Owner",
                "Comments Sales"
            ]

            # Helper para rótulos amigáveis
            from shipments_mapping import get_display_names
            display_names_local = get_display_names()

            # Captura de novos valores para diff
            new_values_sales = {}

            # Layout inteligente baseado no tipo de campo
            def get_field_config(field_name):
                """Retorna configuração de largura e agrupamento para cada campo"""
                # Campos pequenos (1/4 da largura) - códigos, números simples
                small_fields = {
                    "Farol Reference": {"width": 1, "cols": 4},
                    "Farol Status": {"width": 1, "cols": 4},
                    "Container Type": {"width": 1, "cols": 4},
                    "Sales Quantity of Containers": {"width": 1, "cols": 4}, 
                    "DTHC": {"width": 1, "cols": 4},
                    "Afloat": {"width": 1, "cols": 4},
                    "Partial Allowed": {"width": 1, "cols": 4},
                    "VIP PNL Risk": {"width": 1, "cols": 4},
                    "LC Received": {"width": 1, "cols": 4},
                    "Requested Shipment Week": {"width": 1, "cols": 4}
                }
                
                # Campos médios (1/3 da largura) - status, tipos
                medium_fields = {
                    "Type of Shipment": {"width": 1, "cols": 3},
                    "Mode": {"width": 1, "cols": 3},
                    "Incoterm": {"width": 1, "cols": 3},
                    "Business": {"width": 1, "cols": 3},
                    "SKU": {"width": 1, "cols": 3}
                }
                
                # Campos grandes (1/2 da largura) - nomes, locais
                large_fields = {
                    "Customer": {"width": 1, "cols": 2},
                    "Plant of Origin": {"width": 1, "cols": 2},
                    "Port of Loading POL": {"width": 1, "cols": 2},
                    "Port of Delivery POD": {"width": 1, "cols": 2},
                    "Place of Receipt": {"width": 1, "cols": 2},
                    "Final Destination": {"width": 1, "cols": 2},
                    "PNL Destination": {"width": 1, "cols": 2},
                    "Comments Sales": {"width": 1, "cols": 2}
                }
                
                # Campos extra grandes (largura completa) - textos longos
                xl_fields = {
                    "Sales Order Reference": {"width": 1, "cols": 1},
                    "Customer PO": {"width": 1, "cols": 1},
                    "Splitted Booking Reference": {"width": 1, "cols": 1}
                }
                
                if field_name in small_fields:
                    return small_fields[field_name]
                elif field_name in medium_fields:
                    return medium_fields[field_name]
                elif field_name in large_fields:
                    return large_fields[field_name]
                elif field_name in xl_fields:
                    return xl_fields[field_name]
                else:
                    return {"width": 1, "cols": 3}  # padrão médio
            
            # Agrupa campos por configuração de layout
            field_groups = {}
            for col_name in [c for c in sales_order if c in df_s_view.columns or (c == "Sales Farol Reference" and "Farol Reference" in df_s_view.columns)]:
                config = get_field_config(col_name)
                cols_key = config["cols"]
                if cols_key not in field_groups:
                    field_groups[cols_key] = []
                field_groups[cols_key].append(col_name)
            
            # Renderiza campos agrupados por layout com seções organizadas
            sections = {
                "📋 Informações Básicas": ["Sales Farol Reference", "Farol Status", "Type of Shipment"],
                "📦 Produto e Quantidade": ["Sales Order Reference", "Sales Quantity of Containers", "Container Type", "Customer", "SKU"],
                "🏢 Cliente e Negócio": ["Customer PO"],
                "🌍 Portos e Destinos": ["Port of Loading POL", "Port of Delivery POD", "Place of Receipt", "Final Destination", "Incoterm", "Mode"],
                "📅 Datas e Prazos": ["data_sales_order", "Shipment Requested Date", "data_requested_deadline_start", "data_requested_deadline_end", "data_required_sail_date", "data_required_arrival_expected"],
                "⚙️ Configurações": ["DTHC", "Afloat", "Partial Allowed", "VIP PNL Risk", "LC Received"],
                "💬 Observações": ["Comments Sales", "Sales Owner"]
            }
            
            for section_title, section_fields in sections.items():
                # Verifica se a seção tem campos disponíveis
                available_fields = [f for f in section_fields if f in [c for c in sales_order if c in df_s_view.columns or (c == "Sales Farol Reference" and "Farol Reference" in df_s_view.columns)]]
                if not available_fields:
                    continue
                
                if section_title != "📋 Informações Básicas":  # Não adiciona espaço antes da primeira seção
                    st.markdown("---")  # Linha divisória
                st.markdown(f"**{section_title}**")

                # Linha padrão: Farol Reference | Farol Status | Type of Shipment
                if section_title == "📋 Informações Básicas":
                    first_row_fields = ["Sales Farol Reference", "Farol Status", "Type of Shipment"]
                    available_top = [f for f in first_row_fields if f in available_fields]
                    if available_top:
                        # Padronizado: [1,1,1,1,1] (5 colunas iguais) para manter mesmas medidas em todas as abas
                        cols_top = st.columns([1,1,1,1,1])
                        for j, col_name in enumerate(available_top):
                            with cols_top[j]:
                                label = col_name
                                internal_key = col_name
                                if col_name == "Sales Farol Reference":
                                    label = "Farol Reference"
                                    internal_key = "Farol Reference"
                                label_display = display_names_local.get(label, label)

                                # Regra: campos duplicados só editáveis na sua stage-mãe (prefixos s_ e b_)
                                db_col_candidate = get_database_column_name(internal_key)
                                only_sales = db_col_candidate.lower().startswith("s_")
                                only_booking = db_col_candidate.lower().startswith("b_")
                                disabled_flag = (label in disabled_cols) or (label == "Splitted Booking Reference") or only_booking
                                current_val = row_sales.get(internal_key, "")

                                if label == "Farol Status":
                                    try:
                                        default_index = farol_status_options.index(str(current_val))
                                    except Exception:
                                        default_index = 0
                                    new_values_sales[label] = st.selectbox(label, farol_status_options, index=default_index, disabled=disabled_flag, key=f"sales_top_{farol_ref}_{label}")
                                elif label == "Type of Shipment":
                                    try:
                                        default_index = type_of_shipment_options.index(str(current_val))
                                    except Exception:
                                        default_index = 0
                                    new_values_sales[label] = st.selectbox(label, type_of_shipment_options, index=default_index, disabled=disabled_flag, key=f"sales_top_{farol_ref}_{label}")
                                else:
                                    new_values_sales[label] = st.text_input(label, value=str(current_val if current_val is not None else ""), disabled=True, key=f"sales_top_{farol_ref}_{label}")

                        # Remove do restante da seção para não duplicar
                        available_fields = [f for f in available_fields if f not in available_top]
                
                # Linha fixa na seção Cliente e Negócio: Customer | Business | SKU
                if section_title == "🏢 Cliente e Negócio":
                    first_row_fields_cn = ["Customer", "Business"]
                    available_top_cn = [f for f in first_row_fields_cn if f in available_fields]
                    if available_top_cn:
                        # Customer (3), Business (2), espaçador (7)
                        if set(available_top_cn) >= {"Customer", "Business"}:
                            cols_top_cn = st.columns([1,1,2])
                        else:
                            cols_top_cn = st.columns([1]*len(available_top_cn) + [max(1, 5-len(available_top_cn))])
                        for j, col_name in enumerate(available_top_cn):
                            with cols_top_cn[j]:
                                label = col_name
                                internal_key = col_name
                                current_val = row_sales.get(internal_key, "")
                                db_col_candidate = get_database_column_name(internal_key)
                                only_sales = db_col_candidate.lower().startswith("s_")
                                only_booking = db_col_candidate.lower().startswith("b_")
                                disabled_flag = (label in disabled_cols) or only_booking

                                if label in ("Business", "SKU"):
                                    options_map = {"Business": business_options, "SKU": sku_options}
                                    options = options_map[label]
                                    try:
                                        default_index = options.index(str(current_val))
                                    except Exception:
                                        default_index = 0
                                    new_values_sales[label] = st.selectbox(label, options, index=default_index, disabled=disabled_flag, key=f"sales_top_cn_{farol_ref}_{label}")
                                else:
                                    new_values_sales[label] = st.text_input(label, value=str(current_val if current_val is not None else ""), disabled=disabled_flag, key=f"sales_top_cn_{farol_ref}_{label}")

                        # Evita duplicar esses campos no restante da seção
                        available_fields = [f for f in available_fields if f not in available_top_cn]

                # Linha fixa na seção Portos e Destinos: POL | POD | Place of Receipt | Final Destination | Incoterm
                if section_title == "🌍 Portos e Destinos":
                    first_row_fields_log = ["Port of Loading POL", "Port of Delivery POD", "Place of Receipt", "Final Destination", "Incoterm"]
                    available_top_log = [f for f in first_row_fields_log if f in available_fields]
                    if available_top_log:
                        # Padrão: [1,1,1,1,1] (5 colunas iguais)
                        cols_top_log = st.columns([1,1,1,1,1])
                        for idx, col_name in enumerate(["Port of Loading POL", "Port of Delivery POD", "Place of Receipt", "Final Destination", "Incoterm"]):
                            if col_name not in available_top_log:
                                continue
                            with cols_top_log[idx]:
                                label = col_name
                                internal_key = col_name
                                current_val = row_sales.get(internal_key, "")
                                db_col_candidate = get_database_column_name(internal_key)
                                only_sales = db_col_candidate.lower().startswith("s_")
                                only_booking = db_col_candidate.lower().startswith("b_")
                                disabled_flag = (label in disabled_cols) or only_booking

                                if label in ("Port of Loading POL", "Port of Delivery POD"):
                                    options = ports_pol_options if label == "Port of Loading POL" else ports_pod_options
                                    try:
                                        default_index = options.index(str(current_val))
                                    except Exception:
                                        default_index = 0
                                    new_values_sales[label] = st.selectbox(label, options, index=default_index, disabled=disabled_flag, key=f"sales_top_log_{farol_ref}_{label}")
                                elif label == "Incoterm":
                                    try:
                                        default_index = incoterm_options.index(str(current_val))
                                    except Exception:
                                        default_index = 0
                                    new_values_sales[label] = st.selectbox(label, incoterm_options, index=default_index, disabled=disabled_flag, key=f"sales_top_log_{farol_ref}_{label}")
                                else:
                                    new_values_sales[label] = st.text_input(label, value=str(current_val if current_val is not None else ""), disabled=disabled_flag, key=f"sales_top_log_{farol_ref}_{label}")

                        # Evita duplicar esses campos no restante da seção
                        available_fields = [f for f in available_fields if f not in available_top_log]

                # Linha fixa em Configurações: DTHC | Afloat | VIP PNL Risk
                if section_title == "⚙️ Configurações":
                    first_row_fields_cfg = ["DTHC", "Afloat", "VIP PNL Risk"]
                    available_top_cfg = [f for f in first_row_fields_cfg if f in available_fields]
                    if available_top_cfg:
                        cols_top_cfg = st.columns([1, 1, 1, 2])
                        for j, col_name in enumerate(available_top_cfg):
                            with cols_top_cfg[j]:
                                label = col_name
                                internal_key = col_name
                                current_val = row_sales.get(internal_key, "")
                                db_col_candidate = get_database_column_name(internal_key)
                                only_sales = db_col_candidate.lower().startswith("s_")
                                only_booking = db_col_candidate.lower().startswith("b_")
                                disabled_flag = (label in disabled_cols) or only_booking

                                if label == "DTHC":
                                    options = dthc_options
                                elif label == "Afloat":
                                    options = yes_no_options
                                else:
                                    options = vip_pnl_risk_options

                                try:
                                    default_index = options.index(str(current_val))
                                except Exception:
                                    default_index = 0
                                new_values_sales[label] = st.selectbox(label, options, index=default_index, disabled=disabled_flag, key=f"sales_top_cfg_{farol_ref}_{label}")

                        # Evita duplicar esses campos no restante da seção
                        available_fields = [f for f in available_fields if f not in available_top_cfg]

                    # Linha única apenas para Incoterm, com pesos [1,1,1,2] (mesma largura de um campo em POL/POD)
                    if "Incoterm" in available_fields:
                        cols_inc = st.columns([1,1,1,2])
                        with cols_inc[0]:
                            label = "Incoterm"
                            internal_key = "Incoterm"
                            current_val = row_sales.get(internal_key, "")
                            db_col_candidate = get_database_column_name(internal_key)
                            only_sales = db_col_candidate.lower().startswith("s_")
                            only_booking = db_col_candidate.lower().startswith("b_")
                            disabled_flag = (label in disabled_cols) or only_booking
                            try:
                                default_index = incoterm_options.index(str(current_val))
                            except Exception:
                                default_index = 0
                            new_values_sales[label] = st.selectbox(label, incoterm_options, index=default_index, disabled=disabled_flag, key=f"sales_top_inc_{farol_ref}_{label}")

                        # Remove Incoterm do restante da seção
                        available_fields = [f for f in available_fields if f != "Incoterm"]

                # Linha fixa na seção Datas e Prazos: Sales Order Date | Shipment Requested Date | Requested Deadline Start | Requested Deadline End
                if section_title == "📅 Datas e Prazos":
                    first_row_fields_dt = [
                        "data_sales_order", "Shipment Requested Date", "data_requested_deadline_start", "data_requested_deadline_end"
                    ]
                    available_top_dt = [f for f in first_row_fields_dt if f in available_fields]
                    if available_top_dt:
                        cols_top_dt = st.columns([1]*len(available_top_dt) + [max(1, 5-len(available_top_dt))])
                        for j, col_name in enumerate(available_top_dt):
                            with cols_top_dt[j]:
                                label = col_name
                                internal_key = col_name
                                current_val = row_sales.get(internal_key, "")
                                db_col_candidate = get_database_column_name(internal_key)
                                only_sales = db_col_candidate.lower().startswith("s_")
                                only_booking = db_col_candidate.lower().startswith("b_")
                                disabled_flag = (label in disabled_cols) or only_booking
                                # Usa nome amigável para datas
                                disp_label = display_names_local.get(label, label)
                                dt = pd.to_datetime(current_val, errors='coerce')
                                new_values_sales[label] = st.date_input(
                                    disp_label,
                                    value=(dt.date() if pd.notna(dt) else None),
                                    disabled=disabled_flag,
                                    key=f"sales_top_dt_{farol_ref}_{label}"
                                )

                        # Evita duplicar esses campos no restante da seção
                        available_fields = [f for f in available_fields if f not in available_top_dt]

                    # Segunda linha: Required Sail Date | Required Arrival Date
                    second_row_fields_dt = ["data_required_sail_date", "data_required_arrival_expected"]
                    available_second_dt = [f for f in second_row_fields_dt if f in available_fields]
                    if available_second_dt:
                        # Mesma padronização visual da linha acima: 5 colunas com pesos iguais
                        cols_second_dt = st.columns([1,1,1,1,1])
                        for j, col_name in enumerate(available_second_dt):
                            with cols_second_dt[j]:
                                label = col_name
                                internal_key = col_name
                                current_val = row_sales.get(internal_key, "")
                                db_col_candidate = get_database_column_name(internal_key)
                                only_sales = db_col_candidate.lower().startswith("s_")
                                only_booking = db_col_candidate.lower().startswith("b_")
                                disabled_flag = (label in disabled_cols) or only_booking
                                # Usa nome amigável para datas
                                disp_label = display_names_local.get(label, label)
                                dt = pd.to_datetime(current_val, errors='coerce')
                                new_values_sales[label] = st.date_input(
                                    disp_label,
                                    value=(dt.date() if pd.notna(dt) else None),
                                    disabled=disabled_flag,
                                    key=f"sales_second_dt_{farol_ref}_{label}"
                                )

                        # Evita duplicar esses campos no restante da seção
                        available_fields = [f for f in available_fields if f not in available_second_dt]

                # Linha fixa na seção Produto e Quantidade: Sales Order Reference | Sales Quantity of Containers | Container Type | Customer
                if section_title == "📦 Produto e Quantidade":
                    first_row_fields_pq = ["Sales Order Reference", "Sales Quantity of Containers", "Container Type", "Customer"]
                    available_top_pq = [f for f in first_row_fields_pq if f in available_fields]
                    if available_top_pq:
                        # Padrão: [1,1,1,1,1] (5 colunas iguais)
                        cols_top_pq = st.columns([1,1,1,1,1])
                        # Ordem fixa: Sales Order Reference | Sales Quantity of Containers | Container Type | Customer (Customer usa a 4ª coluna se existir)
                        for idx, col_name in enumerate(["Sales Order Reference", "Sales Quantity of Containers", "Container Type", "Customer"]):
                            if col_name not in available_top_pq:
                                continue
                            with cols_top_pq[idx]:
                                label = col_name
                                internal_key = col_name
                                current_val = row_sales.get(internal_key, "")
                                db_col_candidate = get_database_column_name(internal_key)
                                only_sales = db_col_candidate.lower().startswith("s_")
                                only_booking = db_col_candidate.lower().startswith("b_")
                                disabled_flag = (label in disabled_cols) or only_booking

                                if label == "Sales Quantity of Containers":
                                    try:
                                        default_num = int(current_val) if pd.notna(current_val) and str(current_val).strip() != "" else 0
                                    except Exception:
                                        default_num = 0
                                    new_values_sales[label] = st.number_input(label, min_value=0, step=1, value=default_num, disabled=disabled_flag, key=f"sales_top_pq_{farol_ref}_{label}")
                                elif label == "Container Type":
                                    try:
                                        default_index = container_type_options.index(str(current_val))
                                    except Exception:
                                        default_index = 0
                                    new_values_sales[label] = st.selectbox(label, container_type_options, index=default_index, disabled=disabled_flag, key=f"sales_top_pq_{farol_ref}_{label}")
                                else:
                                    new_values_sales[label] = st.text_input(label, value=str(current_val if current_val is not None else ""), disabled=disabled_flag, key=f"sales_top_pq_{farol_ref}_{label}")

                        # Evita duplicar esses campos no restante da seção
                        available_fields = [f for f in available_fields if f not in available_top_pq]
                
                # Observações (Sales): Comments Sales (2 colunas) | 📌 Informações adicionais (2 colunas) | Sales Owner (1 coluna)
                if section_title == "💬 Observações":
                    obs_fields_s = [f for f in ["Comments Sales", "Sales Owner"] if f in available_fields]
                    if obs_fields_s:
                        cols_obs_s = st.columns([3,2,1])
                        # Comments Sales
                        if "Comments Sales" in obs_fields_s:
                            with cols_obs_s[0]:
                                current_val = row_sales.get("Comments Sales", "")
                                new_values_sales["Comments Sales"] = st.text_area(
                                    "Comments Sales",
                                    value=str(current_val if current_val is not None else ""),
                                    height=140,
                                    key=f"sales_obs_{farol_ref}_comments"
                                )
                        # 📌 Reasons for Change (Sales)
                        with cols_obs_s[1]:
                            info_sales = st.text_area(
                                "📌 Reasons for Change (Sales)",
                                key=f"info_sales_{farol_ref}",
                                height=140
                            )
                        # Sales Owner
                        if "Sales Owner" in obs_fields_s:
                            with cols_obs_s[2]:
                                current_val = row_sales.get("Sales Owner", "")
                                new_values_sales["Sales Owner"] = st.text_input(
                                    "Sales Owner",
                                    value=str(current_val if current_val is not None else ""),
                                    key=f"sales_obs_{farol_ref}_sales_owner",
                                    disabled=True
                                )
                        # Evita duplicar no restante
                        available_fields = [f for f in available_fields if f not in ("Comments Sales", "Sales Owner")]

                # Agrupa campos da seção por layout
                section_groups = {}
                for field in available_fields:
                    config = get_field_config(field)
                    cols_key = config["cols"]
                    if cols_key not in section_groups:
                        section_groups[cols_key] = []
                    section_groups[cols_key].append(field)
                
                # Renderiza campos da seção
                for cols_count in [1, 2, 3, 4]:
                    if cols_count not in section_groups:
                        continue
                        
                    fields = section_groups[cols_count]
                    if not fields:
                        continue
                    
                    for i in range(0, len(fields), cols_count):
                        batch = fields[i:i + cols_count]
                        cols = st.columns(cols_count)
                        
                        for j, col_name in enumerate(batch):
                            if j < len(cols):
                                col_container = cols[j]
                            else:
                                break
                            
                            with col_container:
                                label = col_name
                                internal_key = col_name
                                if col_name == "Sales Farol Reference":
                                    label = "Farol Reference"
                                    internal_key = "Farol Reference"
                                label_display = display_names_local.get(label, label)

                                disabled_flag = (label in disabled_cols) or (label == "Splitted Booking Reference")
                                current_val = row_sales.get(internal_key, "")

                                # Seletores e tipos
                                if label == "Farol Status":
                                    try:
                                        default_index = farol_status_options.index(str(current_val))
                                    except Exception:
                                        default_index = 0
                                    new_values_sales[label] = st.selectbox(label, farol_status_options, index=default_index, disabled=disabled_flag, key=f"sales_{farol_ref}_{label}")
                                elif label in ("Type of Shipment", "Container Type"):
                                    options = type_of_shipment_options if label == "Type of Shipment" else container_type_options
                                    try:
                                        default_index = options.index(str(current_val))
                                    except Exception:
                                        default_index = 0
                                    new_values_sales[label] = st.selectbox(label, options, index=default_index, disabled=disabled_flag, key=f"sales_{farol_ref}_{label}")
                                elif label in ("Port of Loading POL", "Port of Delivery POD"):
                                    options = ports_pol_options if label == "Port of Loading POL" else ports_pod_options
                                    try:
                                        default_index = options.index(str(current_val))
                                    except Exception:
                                        default_index = 0
                                    new_values_sales[label] = st.selectbox(label, options, index=default_index, disabled=disabled_flag, key=f"sales_{farol_ref}_{label}")
                                elif label in ("DTHC", "Afloat", "VIP PNL Risk"):
                                    options_map = {"DTHC": dthc_options, "Afloat": yes_no_options, "VIP PNL Risk": vip_pnl_risk_options}
                                    options = options_map[label]
                                    try:
                                        default_index = options.index(str(current_val))
                                    except Exception:
                                        default_index = 0
                                    new_values_sales[label] = st.selectbox(label, options, index=default_index, disabled=disabled_flag, key=f"sales_{farol_ref}_{label}")
                                elif label in ("Business", "Mode", "SKU"):
                                    options_map = {"Business": business_options, "Mode": mode_options, "SKU": sku_options}
                                    options = options_map[label]
                                    try:
                                        default_index = options.index(str(current_val))
                                    except Exception:
                                        default_index = 0
                                    new_values_sales[label] = st.selectbox(label, options, index=default_index, disabled=disabled_flag, key=f"sales_{farol_ref}_{label}")
                                elif label in ("Partial Allowed", "PNL Destination"):
                                    try:
                                        default_index = yes_no_options.index(str(current_val))
                                    except Exception:
                                        default_index = 0
                                    new_values_sales[label] = st.selectbox(label, yes_no_options, index=default_index, disabled=disabled_flag, key=f"sales_{farol_ref}_{label}")
                                elif label in ("Sales Quantity of Containers", "Requested Shipment Week"):
                                    try:
                                        default_num = int(current_val) if pd.notna(current_val) and str(current_val).strip() != "" else 0
                                    except Exception:
                                        default_num = 0
                                    new_values_sales[label] = st.number_input(label, min_value=0, step=1, value=default_num, disabled=disabled_flag, key=f"sales_{farol_ref}_{label}")
                                elif label.startswith("data_") or label in ("Shipment Requested Date",):
                                    dt = pd.to_datetime(current_val, errors='coerce')
                                    new_values_sales[label] = st.date_input(label_display, value=(dt.date() if pd.notna(dt) else None), disabled=disabled_flag, key=f"sales_{farol_ref}_{label}")
                                else:
                                    if label == "Comments Sales":
                                        new_values_sales[label] = st.text_area(
                                            label,
                                            value=str(current_val if current_val is not None else ""),
                                            height=140,  # ~2 linhas a mais
                                            disabled=disabled_flag,
                                            key=f"sales_{farol_ref}_{label}"
                                        )
                                    else:
                                        new_values_sales[label] = st.text_input(label, value=str(current_val if current_val is not None else ""), disabled=disabled_flag or (label == "Farol Reference"), key=f"sales_{farol_ref}_{label}")

            # info_sales agora é definido dentro da seção Observações (Sales)
            
            # Botões dentro do formulário Sales
            col_save_sales, col_discard_sales = st.columns([1, 1])
            with col_save_sales:
                submit_sales = st.form_submit_button("✅ Save Changes")
            with col_discard_sales:
                discard_sales = st.form_submit_button("❌ Discard Changes")

        # (removido) blocos fora do formulário – mantidos dentro do st.form

        # Processa descarte Sales
        if discard_sales:
            # Incrementar contador para forçar recriação do form
            if "form_reset_counter" not in st.session_state:
                st.session_state["form_reset_counter"] = 0
            st.session_state["form_reset_counter"] += 1
            st.warning("Changes discarded.")
            st.rerun()

        # Processa submissão Sales
        if submit_sales:
            if not has_access_level('EDIT'):
                st.warning("⚠️ Você não tem permissão para editar dados (Sales)")
            elif not info_sales.strip():
                st.error("⚠️ O campo de informações adicionais é obrigatório.")
            else:
                # Monta diffs com base nos campos exibidos (em ordem), usando new_values_sales
                changes_sales = []
                def add_change(label, old_val, new_val):
                    if old_val is None and (new_val is None or new_val == ""):
                        return
                    # Normaliza datas para string comparável
                    if hasattr(old_val, 'to_pydatetime'):
                        old_val = old_val.to_pydatetime()
                    if hasattr(new_val, 'to_pydatetime'):
                        new_val = new_val.to_pydatetime()
                    if str(old_val) != str(new_val):
                        changes_sales.append({"Column": label, "Previous Value": old_val, "New Value": new_val})

                from shipments_mapping import get_display_names
                display_names_local2 = get_display_names()
                for label, new_val in new_values_sales.items():
                    if label in ("Farol Reference",):
                        continue  # nunca atualiza referência
                    internal_key = "Farol Reference" if label == "Farol Reference" else label
                    old_val = row_sales.get(internal_key, None)
                    add_change(label, old_val, new_val)

                # Validação de bloqueio para Farol Status
                for ch in changes_sales:
                    if ch["Column"] == "Farol Status":
                        from_status = clean_farol_status_value(ch["Previous Value"]) if ch["Previous Value"] is not None else ""
                        to_status = clean_farol_status_value(ch["New Value"]) if ch["New Value"] is not None else ""
                        if (
                            (from_status == "Adjustment Requested" and to_status != "Adjustment Requested") or
                            (from_status != "Adjustment Requested" and to_status == "Adjustment Requested")
                        ):
                            st.warning("⚠️ Status 'Adjustment Requested' não pode ser alterado diretamente.")
                            changes_sales = []
                            break

                if not changes_sales:
                    st.info("Nenhuma alteração detectada para Sales.")
                else:
                    batch_id = str(uuid.uuid4())
                    begin_change_batch(batch_id)
                    try:
                        conn = get_database_connection()
                        transaction = conn.begin()
                        from shipments_mapping import get_reverse_mapping
                        reverse_map_all = get_reverse_mapping()
                        for ch in changes_sales:
                            # 1) tenta mapear friendly -> alias; 2) alias/display -> coluna DB
                            alias_or_label = reverse_map_all.get(ch["Column"], ch["Column"])  # ex.: 'Sales Quantity of Containers' -> 's_quantity_of_containers'
                            db_col = get_database_column_name(alias_or_label)
                            new_val = ch["New Value"]
                            if db_col == "FAROL_STATUS":
                                new_val = process_farol_status_for_database(new_val)
                            if hasattr(new_val, 'to_pydatetime'):
                                new_val = new_val.to_pydatetime()
                            if db_col in ['B_DATA_CHEGADA_DESTINO_ETA', 'B_DATA_CHEGADA_DESTINO_ATA'] and hasattr(new_val, 'date'):
                                new_val = new_val.date()
                            audit_change(conn, farol_ref, 'F_CON_SALES_BOOKING_DATA', db_col, ch["Previous Value"], new_val, 'shipments', 'UPDATE', adjustment_id=batch_id)
                            update_field_in_sales_booking_data(conn, farol_ref, db_col, new_val)
                        transaction.commit()
                        conn.close()
                        st.success("✅ Alterações de Sales salvas!")
                        st.cache_data.clear()
                        st.session_state["current_page"] = "main"
                        st.rerun()
                    finally:
                        end_change_batch()

    # --- BOOKING TAB (formulário) ---
    with tab_booking:
        stage_b = "Booking Management"
        disabled_cols_b = set(non_editable_columns(stage_b))
        df_b_view = df_booking.copy()
        if not df_b_view.empty and "Booking Farol Reference" in df_b_view.columns:
            df_b_view.rename(columns={"Booking Farol Reference": "Farol Reference"}, inplace=True)
        if "Farol Reference" not in df_b_view.columns:
            df_b_view["Farol Reference"] = farol_ref
        row_booking = df_b_view.iloc[0] if not df_b_view.empty else pd.Series(dtype=object)

        # Opções UDC
        carriers = [""
        ] + df_udc[df_udc["grupo"] == "Carrier"]["dado"].dropna().astype(str).unique().tolist()
        ports_pol_options = [""
        ] + df_udc[df_udc["grupo"] == "Porto Origem"]["dado"].dropna().astype(str).unique().tolist()
        ports_pod_options = [""
        ] + df_udc[df_udc["grupo"] == "Porto Destino"]["dado"].dropna().astype(str).unique().tolist()

        st.subheader("Booking Management")
        with st.form(f"booking_form_{farol_ref}_{st.session_state.get('form_reset_counter', 0)}"):
            # Ordem exata conforme grid
            booking_order = [
                "Booking Farol Reference", "Farol Status", "Type of Shipment", "Booking Status", "Booking Reference",
                "Transaction Number",
                "Sales Quantity of Containers", "Container Type",
                "Port of Loading POL", "Port of Delivery POD", "Place of Receipt", "Final Destination",
                "Shipment Requested Date", "Sales Order Reference", "data_sales_order", "Booking Registered Date", "Booking Requested Date", "data_booking_confirmation",
                "data_estimativa_saida", "data_estimativa_chegada", "data_deadline", "data_draft_deadline", "data_abertura_gate",
                "data_confirmacao_embarque", "data_atracacao", "data_partida", "data_chegada",
                "data_estimativa_atracacao", "data_estimada_transbordo", "data_transbordo",
                "data_chegada_destino_eta", "data_chegada_destino_ata",
                "Carrier", "Freight Forwarder", "Vessel Name", "Voyage Code", "Port Terminal", "Transhipment Port", "POD Country", "POD Country Acronym", "Destination Trade Region",
                "Freight Rate USD", "Bogey Sale Price USD", "Freight PNL",
                "Booking Owner",
                "Comments Booking"
            ]

            # Captura de novos valores para diff
            new_values_booking = {}

            # Layout inteligente para Booking (similar ao Sales)
            def get_booking_field_config(field_name):
                """Retorna configuração de largura para campos de Booking"""
                # Campos pequenos (1/4 da largura)
                small_fields = {
                    "Farol Reference": {"width": 1, "cols": 4},
                    "Farol Status": {"width": 1, "cols": 4},
                    "Container Type": {"width": 1, "cols": 4},
                    "Sales Quantity of Containers": {"width": 1, "cols": 4},
                    "Booking Status": {"width": 1, "cols": 4},
                    "Type of Shipment": {"width": 1, "cols": 4},
                    "POD Country Acronym": {"width": 1, "cols": 4}
                }
                
                # Campos médios (1/3 da largura)
                medium_fields = {
                    "Carrier": {"width": 1, "cols": 3},
                    "Freight Forwarder": {"width": 1, "cols": 3},
                    "Vessel Name": {"width": 1, "cols": 3},
                    "Voyage Code": {"width": 1, "cols": 3},
                    "Port Terminal": {"width": 1, "cols": 3},
                    "POD Country": {"width": 1, "cols": 3},
                    "Destination Trade Region": {"width": 1, "cols": 3},
                    "Award Status": {"width": 1, "cols": 3},
                    "Transaction Number": {"width": 1, "cols": 3}
                }
                
                # Campos grandes (1/2 da largura)
                large_fields = {
                    "Port of Loading POL": {"width": 1, "cols": 2},
                    "Port of Delivery POD": {"width": 1, "cols": 2},
                    "Place of Receipt": {"width": 1, "cols": 2},
                    "Final Destination": {"width": 1, "cols": 2},
                    "Transhipment Port": {"width": 1, "cols": 2},
                    "Sales Order Reference": {"width": 1, "cols": 2},
                    "Freight Rate USD": {"width": 1, "cols": 2},
                    "Bogey Sale Price USD": {"width": 1, "cols": 2},
                    "Freight PNL": {"width": 1, "cols": 2}
                }
                
                # Campos extra grandes (largura completa)
                xl_fields = {
                    # Igualar ao Comments Sales: ocupar 2 colunas e usar text_area
                    "Comments Booking": {"width": 1, "cols": 2},
                    "Booking Reference": {"width": 1, "cols": 1},
                    # Booking Owner segue padrão de coluna simples; manteremos a renderização
                    "Booking Owner": {"width": 1, "cols": 1}
                }
                
                if field_name in small_fields:
                    return small_fields[field_name]
                elif field_name in medium_fields:
                    return medium_fields[field_name]
                elif field_name in large_fields:
                    return large_fields[field_name]
                elif field_name in xl_fields:
                    return xl_fields[field_name]
                else:
                    return {"width": 1, "cols": 3}  # padrão médio
            
            # Agrupa campos de Booking por layout
            booking_field_groups = {}
            for col_name in [c for c in booking_order if c in df_b_view.columns or (c == "Booking Farol Reference" and "Farol Reference" in df_b_view.columns)]:
                config = get_booking_field_config(col_name)
                cols_key = config["cols"]
                if cols_key not in booking_field_groups:
                    booking_field_groups[cols_key] = []
                booking_field_groups[cols_key].append(col_name)
            
            # Renderiza campos de Booking organizados por seções
            booking_sections = {
                "📋 Informações Básicas": ["Booking Farol Reference", "Farol Status", "Type of Shipment", "Booking Status", "Transaction Number"],
                "📦 Produto e Quantidade": ["Sales Order Reference", "Sales Quantity of Containers", "Container Type", "Customer"],
                "🏢 Cliente e Negócio": [],  # mantém ordem consistente com Sales
                "🌍 Portos e Destinos": ["Port of Loading POL", "Port of Delivery POD", "Place of Receipt", "Final Destination", "Transhipment Port", "POD Country", "Destination Trade Region"],
                "📅 Cronograma": ["Booking Registered Date", "Booking Requested Date", "data_booking_confirmation", "data_estimativa_saida", "data_estimativa_chegada"],
                "⚙️ Configurações": [],  # mantém ordem consistente com Sales
                "🚢 Carrier e Vessel": ["Carrier", "Freight Forwarder", "Vessel Name", "Voyage Code", "Port Terminal"],
                "💰 Financeiro": ["Freight Rate USD", "Bogey Sale Price USD", "Freight PNL", "Award Status"],
                "💬 Observações": ["Comments Booking", "Booking Owner"]
            }
            
            for section_title, section_fields in booking_sections.items():
                # Verifica campos disponíveis na seção
                available_fields = [f for f in section_fields if f in [c for c in booking_order if c in df_b_view.columns or (c == "Booking Farol Reference" and "Farol Reference" in df_b_view.columns)]]
                if not available_fields:
                    continue
                
                if section_title != "📋 Informações Básicas":  # Não adiciona espaço antes da primeira seção
                    st.markdown("---")  # Linha divisória
                st.markdown(f"**{section_title}**")

                # Linha fixa na seção Portos e Destinos: POL | POD | Place of Receipt | Final Destination | Transhipment Port
                if section_title == "🌍 Portos e Destinos":
                    # Primeira linha: campos compartilhados com Sales
                    first_row_fields_b_log = ["Port of Loading POL", "Port of Delivery POD", "Place of Receipt", "Final Destination", "Transhipment Port"]
                    available_top_b_log = [f for f in first_row_fields_b_log if f in available_fields]
                    if available_top_b_log:
                        # Padrão: [1,1,1,1,1] (5 colunas iguais)
                        cols_top_b_log = st.columns([1,1,1,1,1])
                        for idx, col_name in enumerate(["Port of Loading POL", "Port of Delivery POD", "Place of Receipt", "Final Destination", "Transhipment Port"]):
                            if col_name not in available_top_b_log:
                                continue
                            with cols_top_b_log[idx]:
                                label = col_name
                                internal_key = col_name
                                current_val = row_booking.get(internal_key, "")
                                disabled_flag = (label in disabled_cols_b)

                                if label in ("Port of Loading POL", "Port of Delivery POD"):
                                    options = ports_pol_options if label == "Port of Loading POL" else ports_pod_options
                                    try:
                                        default_index = options.index(str(current_val))
                                    except Exception:
                                        default_index = 0
                                    new_values_booking[label] = st.selectbox(label, options, index=default_index, disabled=disabled_flag, key=f"booking_top_log_{farol_ref}_{label}")
                                else:
                                    new_values_booking[label] = st.text_input(label, value=str(current_val if current_val is not None else ""), disabled=disabled_flag, key=f"booking_top_log_{farol_ref}_{label}")

                        # Evita duplicar esses campos no restante da seção
                        available_fields = [f for f in available_fields if f not in available_top_b_log]

                    # Segunda linha: POD Country | Destination Trade Region
                    second_row_fields_b_log = ["POD Country", "Destination Trade Region"]
                    available_top_b_log2 = [f for f in second_row_fields_b_log if f in available_fields]
                    if available_top_b_log2:
                        # Padrão: [1,1,1,1,1] (5 colunas iguais)
                        cols_top_b_log2 = st.columns([1,1,1,1,1])
                        for idx, col_name in enumerate(["POD Country", "Destination Trade Region"]):
                            if col_name not in available_top_b_log2:
                                continue
                            with cols_top_b_log2[idx]:
                                label = col_name
                                internal_key = col_name
                                current_val = row_booking.get(internal_key, "")
                                disabled_flag = (label in disabled_cols_b)

                                new_values_booking[label] = st.text_input(
                                    label,
                                    value=str(current_val if current_val is not None else ""),
                                    disabled=disabled_flag,
                                    key=f"booking_top_log2_{farol_ref}_{label}"
                                )

                        # Evita duplicar esses campos no restante da seção
                        available_fields = [f for f in available_fields if f not in available_top_b_log2]

                # Observações (Booking): Comments Booking (2 colunas) | Booking Owner (1 coluna)
                if section_title == "💬 Observações":
                    obs_fields = [f for f in ["Comments Booking", "Booking Owner"] if f in available_fields]
                    if obs_fields:
                        cols_obs = st.columns([3,2,1])
                        # Comments Booking
                        if "Comments Booking" in obs_fields:
                            with cols_obs[0]:
                                current_val = row_booking.get("Comments Booking", "")
                                new_values_booking["Comments Booking"] = st.text_area(
                                    "Comments Booking",
                                    value=str(current_val if current_val is not None else ""),
                                    height=140,
                                    key=f"booking_obs_{farol_ref}_comments"
                                )
                        # 📌 Reasons for Change (Booking)
                        with cols_obs[1]:
                            info_booking = st.text_area(
                                "📌 Reasons for Change (Booking)",
                                key=f"info_booking_{farol_ref}",
                                height=140
                            )
                        # Booking Owner
                        if "Booking Owner" in obs_fields:
                            with cols_obs[2]:
                                current_val = row_booking.get("Booking Owner", "")
                                new_values_booking["Booking Owner"] = st.text_input(
                                    "Booking Owner",
                                    value=str(current_val if current_val is not None else ""),
                                    disabled=True,
                                    key=f"booking_obs_{farol_ref}_owner"
                                )
                        # Evita duplicar no restante
                        available_fields = [f for f in available_fields if f not in ("Comments Booking", "Booking Owner")]

                # Linha fixa no topo (Booking): Farol Reference | Farol Status | Type of Shipment | Booking Status | Transaction Number
                if section_title == "📋 Informações Básicas":
                    first_row_fields_b = ["Booking Farol Reference", "Farol Status", "Type of Shipment", "Booking Status", "Transaction Number"]
                    available_top_b = [f for f in first_row_fields_b if f in available_fields]
                    if available_top_b:
                        # Padronizado: [1,1,1,1,1] (5 colunas iguais) para manter mesmas medidas em todas as abas
                        cols_top_b = st.columns([1,1,1,1,1])
                        for j, col_name in enumerate(available_top_b):
                            with cols_top_b[j]:
                                label = col_name
                                internal_key = col_name
                                if col_name == "Booking Farol Reference":
                                    label = "Farol Reference"
                                    internal_key = "Farol Reference"
                                current_val = row_booking.get(internal_key, "")
                                disabled_flag = (label in disabled_cols_b) or (label == "Booking Registered Date")

                                if label == "Farol Status":
                                    # UDC igual ao Sales: selectbox
                                    try:
                                        default_index = farol_status_options.index(str(current_val))
                                    except Exception:
                                        default_index = 0
                                    new_values_booking[label] = st.selectbox(label, farol_status_options, index=default_index, disabled=disabled_flag, key=f"booking_top_{farol_ref}_{label}")
                                elif label in ("Type of Shipment", "Booking Status"):
                                    # Ambos são UDC na grade principal → usar select quando editável
                                    if label == "Type of Shipment":
                                        options = type_of_shipment_options
                                    else:
                                        options = [""] + df_udc[df_udc["grupo"] == "Booking Status"]["dado"].dropna().astype(str).unique().tolist()
                                    try:
                                        default_index = options.index(str(current_val))
                                    except Exception:
                                        default_index = 0
                                    new_values_booking[label] = st.selectbox(label, options, index=default_index, disabled=disabled_flag, key=f"booking_top_{farol_ref}_{label}")
                                elif label == "Transaction Number":
                                    # Campo editável para Transaction Number
                                    new_values_booking[label] = st.text_input(label, value=str(current_val if current_val is not None else ""), disabled=disabled_flag, key=f"booking_top_{farol_ref}_{label}")
                                else:
                                    new_values_booking[label] = st.text_input(label, value=str(current_val if current_val is not None else ""), disabled=True, key=f"booking_top_{farol_ref}_{label}")

                        # Evita duplicar esses campos no restante da seção
                        available_fields = [f for f in available_fields if f not in available_top_b]

                # Linha fixa em Produto e Quantidade (Booking): Sales Order Reference | Sales Quantity of Containers | Container Type | Customer
                if section_title == "📦 Produto e Quantidade":
                    first_row_fields_bt = ["Sales Order Reference", "Sales Quantity of Containers", "Container Type", "Customer"]
                    available_top_bt = [f for f in first_row_fields_bt if f in available_fields]
                    if available_top_bt:
                        # Padrão: [1,1,1,1,1] (5 colunas iguais)
                        cols_top_bt = st.columns([1,1,1,1,1])
                        # Ordem fixa igual à Sales
                        for idx, col_name in enumerate(["Sales Order Reference", "Sales Quantity of Containers", "Container Type", "Customer"]):
                            if col_name not in available_top_bt:
                                continue
                            with cols_top_bt[idx]:
                                label = col_name
                                internal_key = col_name
                                current_val = row_booking.get(internal_key, "")
                                disabled_flag = (label in disabled_cols_b)

                                if label == "Sales Quantity of Containers":
                                    try:
                                        default_num = int(current_val) if pd.notna(current_val) and str(current_val).strip() != "" else 0
                                    except Exception:
                                        default_num = 0
                                    new_values_booking[label] = st.number_input(label, min_value=0, step=1, value=default_num, disabled=disabled_flag, key=f"booking_top_bt_{farol_ref}_{label}")
                                elif label == "Container Type":
                                    # Reutiliza opções de container type
                                    container_type_options_b = [""] + df_udc[df_udc["grupo"] == "Container Type"]["dado"].dropna().astype(str).unique().tolist()
                                    try:
                                        default_index = container_type_options_b.index(str(current_val))
                                    except Exception:
                                        default_index = 0
                                    new_values_booking[label] = st.selectbox(label, container_type_options_b, index=default_index, disabled=disabled_flag, key=f"booking_top_bt_{farol_ref}_{label}")
                                else:
                                    new_values_booking[label] = st.text_input(label, value=str(current_val if current_val is not None else ""), disabled=disabled_flag, key=f"booking_top_bt_{farol_ref}_{label}")

                        # Evita duplicar esses campos no restante da seção
                        available_fields = [f for f in available_fields if f not in available_top_bt]

                # Linha única em Cronograma (Booking): Registered | Requested | Confirmation | ETD | ETA
                if section_title == "📅 Cronograma":
                    first_row_fields_time = [
                        "Booking Registered Date",
                        "Booking Requested Date",
                        "data_booking_confirmation",
                        "data_estimativa_saida",
                        "data_estimativa_chegada",
                    ]
                    available_top_time = [f for f in first_row_fields_time if f in available_fields]
                    if available_top_time:
                        cols_top_time = st.columns([1]*len(available_top_time) + [max(1, 5-len(available_top_time))])
                        for j, col_name in enumerate(available_top_time):
                            with cols_top_time[j]:
                                label = col_name
                                internal_key = col_name
                                current_val = row_booking.get(internal_key, "")
                                disabled_flag = (label in disabled_cols_b)
                                from shipments_mapping import get_display_names
                                disp = get_display_names().get(label, label)

                                if label == "Booking Registered Date":
                                    # Preserva data+hora conforme solicitado
                                    new_values_booking[label] = st.text_input(disp, value=str(current_val if current_val is not None else ""), disabled=True, key=f"booking_top_time_{farol_ref}_{label}")
                                else:
                                    dt = pd.to_datetime(current_val, errors='coerce')
                                    new_values_booking[label] = st.date_input(disp, value=(dt.date() if pd.notna(dt) else None), disabled=disabled_flag, key=f"booking_top_time_{farol_ref}_{label}")

                        # Evita duplicar esses campos no restante da seção
                        available_fields = [f for f in available_fields if f not in available_top_time]

                # Linha única em Financeiro (Booking): Freight Rate USD | Bogey Sale Price USD | Freight PNL
                if section_title == "💰 Financeiro":
                    first_row_fields_fin = [
                        "Freight Rate USD",
                        "Bogey Sale Price USD",
                        "Freight PNL",
                    ]
                    available_top_fin = [f for f in first_row_fields_fin if f in available_fields]
                    if available_top_fin:
                        cols_top_fin = st.columns([1]*len(available_top_fin) + [max(1, 5-len(available_top_fin))])
                        for j, col_name in enumerate(available_top_fin):
                            with cols_top_fin[j]:
                                label = col_name
                                internal_key = col_name
                                current_val = row_booking.get(internal_key, "")
                                disabled_flag = (label in disabled_cols_b)

                                try:
                                    default_num = float(current_val) if pd.notna(current_val) and str(current_val).strip() != "" else 0.0
                                except Exception:
                                    default_num = 0.0
                                new_values_booking[label] = st.number_input(label, value=default_num, step=0.01, disabled=disabled_flag, key=f"booking_top_fin_{farol_ref}_{label}")

                        # Evita duplicar esses campos no restante da seção
                        available_fields = [f for f in available_fields if f not in available_top_fin]
                
                # Agrupa campos da seção por layout
                section_groups = {}
                for field in available_fields:
                    config = get_booking_field_config(field)
                    cols_key = config["cols"]
                    if cols_key not in section_groups:
                        section_groups[cols_key] = []
                    section_groups[cols_key].append(field)
                
                # Renderiza campos da seção
                for cols_count in [1, 2, 3, 4]:
                    if cols_count not in section_groups:
                        continue
                        
                    fields = section_groups[cols_count]
                    if not fields:
                        continue
                    
                    for i in range(0, len(fields), cols_count):
                        batch = fields[i:i + cols_count]
                        cols_b = st.columns(cols_count)
                        
                        for j, col_name in enumerate(batch):
                            if j < len(cols_b):
                                col_container = cols_b[j]
                            else:
                                break
                            
                            with col_container:
                                label = col_name
                                internal_key = col_name
                                if col_name == "Booking Farol Reference":
                                    label = "Farol Reference"
                                    internal_key = "Farol Reference"
                                current_val = row_booking.get(internal_key, "")
                                disabled_flag = (label in disabled_cols_b) or (label == "Booking Registered Date")

                                if label == "Carrier":
                                    try:
                                        default_index = carriers.index(str(current_val))
                                    except Exception:
                                        default_index = 0
                                    new_values_booking[label] = st.selectbox(label, carriers, index=default_index, disabled=disabled_flag, key=f"booking_{farol_ref}_{label}")
                                elif label in ("Port of Loading POL", "Port of Delivery POD"):
                                    options = ports_pol_options if label == "Port of Loading POL" else ports_pod_options
                                    try:
                                        default_index = options.index(str(current_val))
                                    except Exception:
                                        default_index = 0
                                    new_values_booking[label] = st.selectbox(label, options, index=default_index, disabled=disabled_flag, key=f"booking_{farol_ref}_{label}")
                                elif label in ("Booking Requested Date", "data_booking_confirmation") or label.startswith("data_"):
                                    dt = pd.to_datetime(current_val, errors='coerce')
                                    # Usa nome amigável para labels de data quando existir
                                    from shipments_mapping import get_display_names
                                    disp = get_display_names().get(label, label)
                                    new_values_booking[label] = st.date_input(disp, value=(dt.date() if pd.notna(dt) else None), disabled=disabled_flag, key=f"booking_{farol_ref}_{label}")
                                elif label in ("Sales Quantity of Containers",):
                                    try:
                                        default_num = int(current_val) if pd.notna(current_val) and str(current_val).strip() != "" else 0
                                    except Exception:
                                        default_num = 0
                                    new_values_booking[label] = st.number_input(label, min_value=0, step=1, value=default_num, disabled=disabled_flag, key=f"booking_{farol_ref}_{label}")
                                else:
                                    if label == "Comments Booking":
                                        new_values_booking[label] = st.text_area(
                                            label,
                                            value=str(current_val if current_val is not None else ""),
                                            height=140,  # igual ao Comments Sales
                                            disabled=disabled_flag,
                                            key=f"booking_{farol_ref}_{label}"
                                        )
                                    else:
                                        new_values_booking[label] = st.text_input(label, value=str(current_val if current_val is not None else ""), disabled=disabled_flag or (label == "Farol Reference"), key=f"booking_{farol_ref}_{label}")

            # info_booking agora é definido dentro da seção Observações (Booking)
            
            # Botões dentro do formulário Booking
            col_save_booking, col_discard_booking = st.columns([1, 1])
            with col_save_booking:
                submit_booking = st.form_submit_button("✅ Save Changes")
            with col_discard_booking:
                discard_booking = st.form_submit_button("❌ Discard Changes")

        # (removido) blocos fora do formulário – mantidos dentro do st.form

        # Processa descarte Booking
        if discard_booking:
            # Incrementar contador para forçar recriação do form
            if "form_reset_counter" not in st.session_state:
                st.session_state["form_reset_counter"] = 0
            st.session_state["form_reset_counter"] += 1
            st.warning("Changes discarded.")
            st.rerun()

        # Processa submissão Booking
        if submit_booking:
            if not has_access_level('EDIT'):
                st.warning("⚠️ Você não tem permissão para editar dados (Booking)")
            elif not info_booking.strip():
                st.error("⚠️ O campo de informações adicionais é obrigatório.")
            else:
                # Monta diffs com base nos campos exibidos (em ordem), usando new_values_booking
                changes_booking = []
                def add_change_b(label, old_val, new_val):
                    if old_val is None and (new_val is None or new_val == ""):
                        return
                    if hasattr(old_val, 'to_pydatetime'):
                        old_val = old_val.to_pydatetime()
                    if hasattr(new_val, 'to_pydatetime'):
                        new_val = new_val.to_pydatetime()
                    if str(old_val) != str(new_val):
                        changes_booking.append({"Column": label, "Previous Value": old_val, "New Value": new_val})

                for label, new_val in new_values_booking.items():
                    if label in ("Farol Reference",):
                        continue
                    internal_key = "Farol Reference" if label == "Farol Reference" else label
                    old_val = row_booking.get(internal_key, None)
                    add_change_b(label, old_val, new_val)

                if not changes_booking:
                    st.info("Nenhuma alteração detectada para Booking.")
                else:
                    batch_id = str(uuid.uuid4())
                    begin_change_batch(batch_id)
                    try:
                        conn = get_database_connection()
                        transaction = conn.begin()
                        from shipments_mapping import get_reverse_mapping
                        reverse_map_all_b = get_reverse_mapping()
                        for ch in changes_booking:
                            alias_or_label = reverse_map_all_b.get(ch["Column"], ch["Column"])  # friendly -> alias quando possível
                            db_col = get_database_column_name(alias_or_label)  # nome técnico
                            new_val = ch["New Value"]
                            if db_col == "FAROL_STATUS":
                                new_val = process_farol_status_for_database(new_val)
                            if hasattr(new_val, 'to_pydatetime'):
                                new_val = new_val.to_pydatetime()
                            if db_col in ['B_DATA_CHEGADA_DESTINO_ETA', 'B_DATA_CHEGADA_DESTINO_ATA'] and hasattr(new_val, 'date'):
                                new_val = new_val.date()
                            audit_change(conn, farol_ref, 'F_CON_SALES_BOOKING_DATA', db_col, ch["Previous Value"], new_val, 'shipments', 'UPDATE', adjustment_id=batch_id)
                            update_field_in_sales_booking_data(conn, farol_ref, db_col, new_val)
                        transaction.commit()
                        conn.close()
                        st.success("✅ Alterações de Booking salvas!")
                        st.cache_data.clear()
                        st.session_state["current_page"] = "main"
                        st.rerun()
                    finally:
                        end_change_batch()

    if st.button("🔙 Back to Shipments"):
        st.session_state["current_page"] = "main"
        st.rerun()
# Função para aplicar filtros avançados interativos no DataFrame
def aplicar_filtros_interativos(df, colunas_ordenadas):
    # Inicializa o estado da expansão, se não existir
    if "expander_filtros_aberto" not in st.session_state:
        st.session_state["expander_filtros_aberto"] = False
 
    with st.expander(" Advanced Filters (optional)", expanded=st.session_state["expander_filtros_aberto"]):

        # Remove "Select" e filtros rápidos (já exibidos fora) das opções de filtro
        quick_filter_columns_upper = {
            "FAROL REFERENCE",
            "FAROL STATUS",
            # Booking Status pode ter nomes diferentes por origem
            "BOOKING STATUS", "B_BOOKING_STATUS",
            # Booking Reference pode ter nomes diferentes por origem
            "BOOKING REFERENCE", "B_BOOKING_REFERENCE", "_BOOKING_REFERENCE",
        }
        colunas_disponiveis = [
            col for col in colunas_ordenadas
            if col != "Select" and col.upper() not in quick_filter_columns_upper
        ]
        
        # Importa o mapeamento de nomes de exibição
        from shipments_mapping import get_display_names
        display_names = get_display_names()
        
        # Cria opções com nomes amigáveis para exibição mantendo a ordem da tabela
        opcoes_filtro = []
        for col in colunas_disponiveis:
            nome_amigavel = display_names.get(col, col)
            opcoes_filtro.append((nome_amigavel, col))  # (nome_exibido, nome_interno)
        
        # Mantém a ordem da tabela (não ordena alfabeticamente)
        
        colunas_filtradas = st.multiselect(
            "Columns to filter:",
            options=[opcao[0] for opcao in opcoes_filtro],  # Mostra nomes amigáveis
            default=[],
            key="colunas_filtradas_filtros"
        )
        
        # Converte nomes amigáveis de volta para nomes internos
        nome_para_interno = {opcao[0]: opcao[1] for opcao in opcoes_filtro}
        colunas_filtradas_internas = [nome_para_interno[nome] for nome in colunas_filtradas]
        # Reordena a seleção para seguir a ordem da grade exibida
        colunas_filtradas_internas = sorted(
            colunas_filtradas_internas,
            key=lambda c: colunas_ordenadas.index(c) if c in colunas_ordenadas else 10**9
        )
        # Salva seleção interna no estado para uso na paginação baseada em filtros
        st.session_state["colunas_filtradas_internas"] = colunas_filtradas_internas
        filtros = {}
 
 
        for col in colunas_filtradas_internas:
            col_data = df[col]
            # Obtém o nome amigável para exibição
            nome_amigavel = display_names.get(col, col)
 
            if col_data.dtype == "object":
                unique_vals = sorted(col_data.dropna().unique().tolist())
                filtros[col] = st.multiselect(f"Filter {nome_amigavel}", unique_vals, default=unique_vals, key=f"{col}_multiselect")
 
            elif pd.api.types.is_numeric_dtype(col_data):
                min_val, max_val = int(col_data.min()), int(col_data.max())
                # Evita erro quando min_val = max_val
                if min_val == max_val:
                    st.write(f"**{nome_amigavel}**: {min_val} (valor único)")
                    filtros[col] = (min_val, max_val)
                else:
                    filtros[col] = st.slider(f"{nome_amigavel} between", min_val, max_val, (min_val, max_val), key=f"{col}_slider")
 
            elif pd.api.types.is_bool_dtype(col_data):
                filtros[col] = st.radio(f"Include {nome_amigavel}?", ["All", True, False], horizontal=True, key=f"{col}_radio")
 
            elif pd.api.types.is_datetime64_any_dtype(col_data):
                min_date = col_data.min().date()
                max_date = col_data.max().date()
                selected_range = st.date_input(f"Period for {nome_amigavel}", value=(min_date, max_date), key=f"{col}_date")
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
 
        # Aplica os filtros no DataFrame (nota: também aplicaremos em df_full no nível superior quando ativo)
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
    elif st.session_state["current_page"] == "form":
        exibir_formulario()
 
 
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
        ["Sales Data", "Booking Management", "General View"],
        horizontal=True,
    )
    
    # Salva o stage atual na sessão
    st.session_state["current_stage"] = choose
    
    # Linha separadora após a navegação
    st.markdown("---")

    # --- LÓGICA DE PAGINAÇÃO ---
    if 'shipments_current_page' not in st.session_state:
        st.session_state.shipments_current_page = 1

    page_size = 25  # Tamanho fixo de página

    # Carrega dados (paginados por padrão)
    if choose == "Sales Data":
        df, total_records = get_data_salesData(page_number=st.session_state.shipments_current_page, page_size=page_size)
    elif choose == "Booking Management":
        df, total_records = get_data_bookingData(page_number=st.session_state.shipments_current_page, page_size=page_size)
    elif choose == "General View":
        df, total_records = get_data_generalView(page_number=st.session_state.shipments_current_page, page_size=page_size)

    total_pages = (total_records // page_size) + (1 if total_records % page_size > 0 else 0)

    # --- FIM DA LÓGICA DE PAGINAÇÃO ---


    # Padroniza o rótulo exibido para a referência Farol
    rename_map = {}
    if "Sales Farol Reference" in df.columns:
        rename_map["Sales Farol Reference"] = "Farol Reference"
    if "Booking Farol Reference" in df.columns:
        rename_map["Booking Farol Reference"] = "Farol Reference"
    if "Loading Farol Reference" in df.columns:
        rename_map["Loading Farol Reference"] = "Farol Reference"
    # Adiciona verificação para a coluna original da General View
    if "FAROL_REFERENCE" in df.columns:
        rename_map["FAROL_REFERENCE"] = "Farol Reference"
    if rename_map:
        df.rename(columns=rename_map, inplace=True)
    farol_ref_col = "Farol Reference"

    # Quick Filters serão exibidos após os KPIs — movidos mais abaixo

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
 
    # KPIs abaixo do título, antes da grid
    k1, k2, k3, k4 = st.columns(4)

    if "Farol Status" in df.columns:
        # Limpa os ícones da série de status antes de fazer a contagem
        status_series = df["Farol Status"].astype(str).apply(clean_farol_status_value).str.strip().str.lower()
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
 
    # ------------------------
    # Quick Filters (acima do Advanced Filters)
    # ------------------------
    qf_col1, qf_col2, qf_col3, qf_col4 = st.columns(4)

    # 1) Farol Reference (texto)
    with qf_col1:
        qf_farol_ref = st.text_input(
            "Farol Reference",
            value="",
            placeholder="Digite parte da referência",
            key="qf_farol_reference"
        )

    # 2) Farol Status (lista)
    with qf_col2:
        if "Farol Status" in df.columns:
            status_unique = (
                df["Farol Status"].dropna().astype(str).apply(clean_farol_status_value).str.strip().str.title().unique().tolist()
            )
            status_unique = sorted(list({s for s in status_unique if s}))
            qf_farol_status = st.selectbox(
                "Farol Status",
                options=["Todos"] + status_unique,
                index=0,
                key="qf_farol_status"
            )
        else:
            qf_farol_status = None

    # 3) Booking Status (sempre visível; desabilita se coluna não existir; detecção case-insensitive)
    with qf_col3:
        booking_status_col = None
        df_cols_upper = {c.upper(): c for c in df.columns}
        for candidate in ["BOOKING STATUS", "B_BOOKING_STATUS"]:
            if candidate in df_cols_upper:
                booking_status_col = df_cols_upper[candidate]
                break
        if booking_status_col:
            booking_status_unique = (
                df[booking_status_col].dropna().astype(str).str.strip().unique().tolist()
            )
            booking_status_unique = sorted(list({s for s in booking_status_unique if s}))
            qf_booking_status = st.selectbox(
                "Booking Status",
                options=["Todos"] + booking_status_unique,
                index=0,
                key="qf_booking_status"
            )
        else:
            # Mantém o componente visível e habilitado; sem efeito quando coluna não existe
            qf_booking_status = st.selectbox(
                "Booking Status",
                options=["Todos"],
                index=0,
                key="qf_booking_status"
            )

    # 4) Booking (sempre visível; desabilita se coluna não existir; detecção case-insensitive)
    with qf_col4:
        booking_ref_col = None
        df_cols_upper = {c.upper(): c for c in df.columns}
        for candidate in ["BOOKING REFERENCE", "B_BOOKING_REFERENCE", "_BOOKING_REFERENCE"]:
            if candidate in df_cols_upper:
                booking_ref_col = df_cols_upper[candidate]
                break
        qf_booking_ref = st.text_input(
            "Booking",
            value="",
            placeholder="Digite parte do booking",
            key="qf_booking_reference"
        )

    # Se qualquer filtro rápido foi utilizado, recarrega todos os registros e aplica filtro antes de paginar
    quick_filters_active = bool(
        (qf_farol_ref and len(qf_farol_ref) > 0) or
        (qf_farol_status and qf_farol_status != "Todos") or
        (qf_booking_status and qf_booking_status != "Todos") or
        (qf_booking_ref and len(qf_booking_ref) > 0)
    )

    # Checa filtros avançados ativos
    advanced_cols = st.session_state.get("colunas_filtradas_internas", [])
    advanced_filters_active = bool(advanced_cols)

    if quick_filters_active or advanced_filters_active:
        # Recarrega todos os registros para filtrar no cliente (antes da paginação)
        if choose == "Sales Data":
            df_full, total_records_full = get_data_salesData(page_number=1, page_size=page_size, all_rows=True)
        elif choose == "Booking Management":
            df_full, total_records_full = get_data_bookingData(page_number=1, page_size=page_size, all_rows=True)
        else:
            df_full, total_records_full = get_data_generalView(page_number=1, page_size=page_size, all_rows=True)

        # Aplica os mesmos renomes de Farol Reference para consistência
        if rename_map:
            df_full.rename(columns=rename_map, inplace=True)

        # Aplica filtros rápidos sobre o df_full
        if qf_farol_ref:
            df_full = df_full[df_full[farol_ref_col].astype(str).str.contains(qf_farol_ref, case=False, na=False)]

        if qf_farol_status and qf_farol_status != "Todos" and "Farol Status" in df_full.columns:
            _norm_target = clean_farol_status_value(qf_farol_status).strip().lower()
            _norm_series = df_full["Farol Status"].astype(str).apply(clean_farol_status_value).str.strip().str.lower()
            df_full = df_full[_norm_series == _norm_target]

        if qf_booking_status and qf_booking_status != "Todos" and booking_status_col:
            df_full = df_full[df_full[booking_status_col].astype(str).str.strip().str.lower() == qf_booking_status.strip().lower()]

        if qf_booking_ref and booking_ref_col:
            df_full = df_full[df_full[booking_ref_col].astype(str).str.contains(qf_booking_ref, case=False, na=False)]

        # Aplica filtros avançados no df_full (igual à lógica da função)
        if advanced_filters_active:
            from shipments_mapping import get_display_names
            display_names = get_display_names()
            # Reconstrói mapping amigável->interno para colunas disponíveis no df_full
            nome_para_interno_full = {display_names.get(col, col): col for col in df_full.columns if col != "Select"}
            # Percorre colunas internas selecionadas
            for col in advanced_cols:
                if col not in df_full.columns:
                    continue
                col_data = df_full[col]
                # Recupera o controle pelo mesmo padrão de keys usados acima
                if col_data.dtype == "object":
                    selected_vals = st.session_state.get(f"{col}_multiselect")
                    if selected_vals:
                        df_full = df_full[df_full[col].isin(selected_vals)]
                elif pd.api.types.is_numeric_dtype(col_data):
                    slider_val = st.session_state.get(f"{col}_slider")
                    if slider_val:
                        min_val, max_val = slider_val
                        df_full = df_full[(df_full[col] >= min_val) & (df_full[col] <= max_val)]
                elif pd.api.types.is_bool_dtype(col_data):
                    radio_val = st.session_state.get(f"{col}_radio")
                    if radio_val in [True, False]:
                        df_full = df_full[df_full[col] == radio_val]
                elif pd.api.types.is_datetime64_any_dtype(col_data):
                    date_val = st.session_state.get(f"{col}_date")
                    if date_val:
                        if isinstance(date_val, (tuple, list, pd.DatetimeIndex)):
                            srange = list(date_val)
                        else:
                            srange = [date_val]
                        if len(srange) == 1:
                            df_full = df_full[df_full[col] >= pd.Timestamp(srange[0])]
                        elif len(srange) >= 2:
                            end_of_day = pd.Timestamp(srange[1]) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
                            df_full = df_full[(df_full[col] >= pd.Timestamp(srange[0])) & (df_full[col] <= end_of_day)]

        # Atualiza total_records e aplica paginação no cliente
        total_records = len(df_full)
        total_pages = (total_records // page_size) + (1 if total_records % page_size > 0 else 0)
        start_idx = (st.session_state.shipments_current_page - 1) * page_size
        end_idx = start_idx + page_size
        df = df_full.iloc[start_idx:end_idx].copy()

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
    
    # Oculta "Booking Registered Date" nas visualizações "Booking Management" e "General View"
    if choose in ["Booking Management", "General View"]:
        if "Booking Registered Date" in df.columns:
            df = df.drop(columns=["Booking Registered Date"])
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

    # Remove a coluna de contagem bruta para evitar duplicidade na exibição
    if "Carrier Returns" in colunas_ordenadas:
        colunas_ordenadas.remove("Carrier Returns")
    
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
        
        # Posiciona "Voyage Code" após "Carrier" (Booking Management)
        if "Voyage Code" in colunas_ordenadas and "Carrier" in colunas_ordenadas:
            colunas_ordenadas.remove("Voyage Code")
            idx_carrier = colunas_ordenadas.index("Carrier")
            colunas_ordenadas.insert(idx_carrier + 1, "Voyage Code")
        
        # Função helper para mover uma coluna para antes de outra específica
        def _move_before(df, colunas_list, target_col, before_col, stage):
            # Aplica a reordenação apenas para Booking Management e General View
            if stage not in ["Booking Management", "General View"]:
                return colunas_list
                
            if target_col in colunas_list and before_col in colunas_list:
                # Verifica se a coluna de destino já não está antes da coluna de referência
                target_idx = colunas_list.index(target_col)
                before_idx = colunas_list.index(before_col)
                
                # Se a coluna já está na posição correta ou após a coluna de referência, não faz nada
                if target_idx < before_idx and target_idx == before_idx - 1:
                    # Coluna já está exatamente antes da desejada - não precisa mover
                    return colunas_list
                elif target_idx < before_idx:
                    # Coluna está antes, mas não imediatamente antes - precisa reposicionar
                    colunas_list.remove(target_col)
                    new_idx = colunas_list.index(before_col)
                    colunas_list.insert(new_idx, target_col)
                else:
                    # Coluna está depois da coluna de referência - move para antes
                    colunas_list.remove(target_col)
                    new_idx = colunas_list.index(before_col)
                    colunas_list.insert(new_idx, target_col)
            return colunas_list
        
        # Reordena as colunas seguindo a ordem específica enviada pelo usuário
        # Ordem: Creation Of Booking, Booking Requested Date, Carrier, Vessel Name, Voyage Code, Port Terminal, 
        # Freight Forwarder, Transhipment Port, POD Country, POD Country Acronym, Destination Trade Region,
        # data_booking_confirmation, data_estimativa_saida, data_estimativa_chegada, data_deadline, 
        # data_draft_deadline, data_abertura_gate, data_confirmacao_embarque, data_atracacao, 
        # data_partida, data_chegada, data_estimativa_atracacao, data_estimada_transbordo, data_transbordo,
        # data_chegada_destino_eta, data_chegada_destino_ata, Freight Rate USD
        
        # Lista das colunas na ordem específica solicitada
        specific_order = [
            "Booking Registered Date",
            "Booking Requested Date", 
            "Carrier",
            "Vessel Name", 
            "Voyage Code",
            "Port Terminal",
            "Freight Forwarder",
            "Transhipment Port",
            "POD Country",
            "POD Country Acronym", 
            "Destination Trade Region",
            "data_booking_confirmation",
            "data_estimativa_saida",
            "data_estimativa_chegada", 
            "data_deadline",
            "data_draft_deadline",
            "data_abertura_gate",
            "data_confirmacao_embarque",
            "data_atracacao",
            "data_partida",
            "data_chegada",
            "data_estimativa_atracacao",
            "data_estimada_transbordo",
            "data_transbordo",
            "data_chegada_destino_eta",
            "data_chegada_destino_ata",
            "Freight Rate USD"
        ]
        
        # Remove todas as colunas da ordem específica da lista atual
        for col in specific_order:
            if col in colunas_ordenadas:
                colunas_ordenadas.remove(col)
        
        # Encontra a posição após "Final Destination" para inserir as colunas
        if "Final Destination" in colunas_ordenadas:
            insert_position = colunas_ordenadas.index("Final Destination") + 1
        else:
            insert_position = len(colunas_ordenadas)
        
        # Insere as colunas na ordem específica solicitada
        for i, col in enumerate(specific_order):
            if col in df.columns:
                colunas_ordenadas.insert(insert_position + i, col)
        
        # Reposiciona "Shipment Requested Date" imediatamente antes de "Booking Registered Date"
        # apenas nas visões específicas
        colunas_ordenadas = _move_before(df, colunas_ordenadas, "Shipment Requested Date", "Booking Registered Date", choose)

    # Aplica preferência de colunas fixas no início para todos os stages
    # Ordem desejada (usando nomes internos; alguns possuem exibição amigável depois)
    # Select, Farol Reference, Farol Status, Booking Status, Booking, Sales Order Reference, Sales Order Date
    # Detecta Booking Status e Booking Reference com tolerância a nomes alternativos
    df_cols_upper = {c.upper(): c for c in df.columns}
    booking_status_col = None
    for candidate in ["BOOKING STATUS", "B_BOOKING_STATUS"]:
        if candidate in df_cols_upper:
            booking_status_col = df_cols_upper[candidate]
            break
    booking_ref_col = None
    for candidate in ["BOOKING REFERENCE", "B_BOOKING_REFERENCE", "_BOOKING_REFERENCE"]:
        if candidate in df_cols_upper:
            booking_ref_col = df_cols_upper[candidate]
            break

    preferred_prefix = [
        "Select",
        farol_ref_col,
        "Farol Status",
        booking_status_col if booking_status_col else None,
        booking_ref_col if booking_ref_col else None,
        "Sales Order Reference",
        "data_sales_order",  # será exibida como "Sales Order Date"
    ]
    preferred_prefix = [c for c in preferred_prefix if c and c in df.columns]

    # Remove preferidas da lista atual e reinsere no início na ordem solicitada
    for c in preferred_prefix:
        if c in colunas_ordenadas:
            colunas_ordenadas.remove(c)
    colunas_ordenadas = preferred_prefix + colunas_ordenadas

    # Posiciona "Transaction Number" após "Booking Reference"
    if "Transaction Number" in colunas_ordenadas and booking_ref_col:
        colunas_ordenadas.remove("Transaction Number")
        idx_booking = colunas_ordenadas.index(booking_ref_col)
        colunas_ordenadas.insert(idx_booking + 1, "Transaction Number")

    # Posicionar "Required Sail Date" entre Shipment Period End e Required Arrival Date
    if "data_required_sail_date" in colunas_ordenadas:
        try:
            if "data_shipment_period_end" in colunas_ordenadas:
                colunas_ordenadas.remove("data_required_sail_date")
                idx_end = colunas_ordenadas.index("data_shipment_period_end")
                colunas_ordenadas.insert(idx_end + 1, "data_required_sail_date")
        except Exception:
            pass

    # Aplica filtros avançados APÓS a reordenação das colunas
    df = aplicar_filtros_interativos(df, colunas_ordenadas)

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

    # Remove qualquer CSS forçado para Farol Status; usa width nativa do componente

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
 
    # Aplicar nomes amigáveis para exibição
    from shipments_mapping import get_display_names
    display_names = get_display_names()
    df_display = df[colunas_ordenadas].copy()
    
    # Renomear colunas para nomes amigáveis
    renamed_columns = {}
    for col in df_display.columns:
        if col in display_names:
            renamed_columns[col] = display_names[col]
    if renamed_columns:
        df_display.rename(columns=renamed_columns, inplace=True)
    
    # Criar mapeamento reverso (nome amigável -> nome técnico)
    reverse_mapping = {v: k for k, v in renamed_columns.items()}

    # Guarda cópias sem a coluna "Select" para comparação (com nomes amigáveis)
    df_filtered_original = df_display.drop(columns=["Select"], errors="ignore").copy()

    # Filtra column_config para chaves válidas do DataFrame exibido
    filtered_column_config = {k: v for k, v in column_config.items() if k in df_display.columns}

    # Exibe data_editor (os dados já vêm ordenados do banco por Farol Reference)
    edited_df = st.data_editor(
        df_display,
        key=st.session_state["grid_update_key"],
        use_container_width=True,
        num_rows="fixed",
        disabled=disabled_columns,
        column_config=filtered_column_config,
        hide_index=True,
    )

    # Contador discreto de registros
    st.caption(f"Mostrando {len(edited_df)} de {total_records} registros")

    # --- BOTÕES DE NAVEGAÇÃO DA PAGINAÇÃO ---
    prev_col, mid_col, next_col = st.columns(3) # Three equal columns for main layout
    with prev_col:
        if st.button("⬅️ Previous", disabled=(st.session_state.shipments_current_page <= 1)):
            st.session_state.shipments_current_page -= 1
            st.rerun()
    with mid_col:
        st.markdown(f"<p style='text-align: center; color: #6c757d;'>Page {st.session_state.shipments_current_page} of {total_pages}</p>", unsafe_allow_html=True)
    with next_col:
        # Usa sub-colunas para empurrar o botão para a direita dentro da sua coluna
        # Dando mais espaço para o botão não achatar
        _, button_align_col = st.columns([2, 1]) # Spacer (2/3) then button (1/3) of next_col
        with button_align_col:
            if st.button("Next ➡️", disabled=(st.session_state.shipments_current_page >= total_pages)):
                st.session_state.shipments_current_page += 1
                st.rerun()

    
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
                    old_val = original_row[col]
                    new_val = row[col]
                    
                    # Mapear nome amigável de volta para nome técnico
                    technical_col = reverse_mapping.get(col, col)

                    # Se a coluna for 'Farol Status', limpa os valores antes de registrar a mudança
                    # e realiza a verificação de status bloqueado com os valores limpos.
                    if col == "Farol Status":
                        from_status = clean_farol_status_value(old_val)
                        to_status = clean_farol_status_value(new_val)
                        
                        # Atualiza os valores para registrar a versão limpa
                        old_val = from_status
                        new_val = to_status

                        if (
                            from_status == "Adjustment Requested" and to_status != "Adjustment Requested"
                        ) or (
                            from_status != "Adjustment Requested" and to_status == "Adjustment Requested"
                        ):
                            status_blocked = True
                            status_blocked_message = "⚠️ Status 'Adjustment Requested' cannot be changed directly. Use the adjustments module to request changes."
                    
                    changes.append({
                        'Farol Reference': row.get(farol_ref_col, index),
                        "Column": technical_col,
                        "Previous Value": old_val,
                        "New Value": new_val,
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
            st.text_area("📌 Reasons for Change", key="info_complementar")
   
           
        col1, col2, col3, col4  = st.columns([1, 1, 2, 3])
        with col1:
            if has_access_level('EDIT'):
                if st.button("✅ Save Changes"):
                    comments = st.session_state.get("info_complementar", "").strip()
       
                    if comments:
                        # Iniciar batch para agrupar todas as mudanças
                        from database import begin_change_batch, end_change_batch
                        begin_change_batch(random_uuid)
                        
                        try:
                            # Loop de auditoria (substitui insert_adjustments_basics)
                            conn = get_database_connection()
                            transaction = conn.begin()
                            
                            for _, row in st.session_state["changes"].iterrows():
                                from database import audit_change, update_field_in_sales_booking_data
                                from shipments_mapping import process_farol_status_for_database, get_database_column_name
                                
                                farol_ref = row["Farol Reference"]
                                column = row["Column"]
                                old_value = row["Previous Value"]
                                new_value = row["New Value"]
                                
                                # Converter nome da coluna para nome técnico do banco de dados
                                db_column_name = get_database_column_name(column)
                                
                                # Processar tipos de dados especiais
                                if column == "Farol Status" or db_column_name == "FAROL_STATUS":
                                    new_value = process_farol_status_for_database(new_value)
                                
                                # Converter pandas.Timestamp para datetime nativo
                                if hasattr(new_value, 'to_pydatetime'):
                                    new_value = new_value.to_pydatetime()
                                
                                # Converter para date se for coluna de data específica
                                if db_column_name in ['B_DATA_CHEGADA_DESTINO_ETA', 'B_DATA_CHEGADA_DESTINO_ATA']:
                                    if new_value is not None and hasattr(new_value, 'date'):
                                        new_value = new_value.date()
                                
                                # 1. Auditar a mudança (usa nome técnico)
                                audit_change(conn, farol_ref, 'F_CON_SALES_BOOKING_DATA', 
                                            db_column_name, old_value, new_value, 
                                            'shipments', 'UPDATE', adjustment_id=random_uuid)
                                
                                # 2. Persistir a mudança na tabela principal (usa nome técnico)
                                update_field_in_sales_booking_data(conn, farol_ref, db_column_name, new_value)
                            
                            transaction.commit()
                            conn.close()
                            
                            st.success("✅ Changes successfully registered in the database!")
                            st.session_state["changes"] = pd.DataFrame()
                           
                            #Liberando o cache salvo das consultas
                            st.cache_data.clear()
                            resetar_estado()
                            st.rerun()
                        finally:
                            # Encerrar batch
                            end_change_batch()
                    else:
                        st.error("⚠️ The 'Reasons for Change' field is required.")
            else:
                st.warning("⚠️ Você não tem permissão para editar dados. Nível de acesso: Visualização")
 
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
    
    # Linha separadora entre paginação e botões principais
    st.markdown("---")
    
    # Botões principais com layout condicional baseado na seleção
    if len(selected_rows) == 0:
        # Quando NENHUMA linha está selecionada: apenas 2 botões lado a lado
        col_new, col_export, col_spacer = st.columns([2, 2, 6], gap="small")
        
        with col_new:
            if st.button("🚢 New Shipment", key="new_shipment_btn"):
                st.session_state["current_page"] = "add"
                st.rerun()
        
        with col_export:
            # Botão de exportação XLSX - sempre ativo
            if len(df) > 0:  # Só mostra se houver dados para exportar
                # Preparar dados para exportação
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    # Obter o dataframe com as colunas ordenadas, removendo a coluna "Select"
                    columns_to_export = [col for col in colunas_ordenadas if col != "Select"]
                    df_to_export = df[columns_to_export].copy()
                    
                    # Aplicar nomes amigáveis de exibição às colunas
                    from shipments_mapping import get_display_names
                    display_names = get_display_names()
                    
                    # Renomear as colunas usando os nomes amigáveis
                    renamed_columns = {}
                    for col in df_to_export.columns:
                        if col in display_names:
                            renamed_columns[col] = display_names[col]
                        else:
                            friendly_name = col.replace("data_", "").replace("_", " ").title()
                            renamed_columns[col] = friendly_name
                    
                    df_to_export.rename(columns=renamed_columns, inplace=True)
                    df_to_export.to_excel(writer, index=False, sheet_name='Data')
                
                # Botão de download direto
                st.download_button(
                    label="📊 Export XLSX",
                    data=output.getvalue(),
                    file_name=f"shipments_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="export_btn_no_selection"
                )
    
    else:
        # Quando UMA linha está selecionada: 6 botões (sem New Shipment)
        col_form, col_booking, col_history, col_split, col_attachments, col_export = st.columns([1, 1, 1, 1, 1, 1], gap="medium")
        
        with col_form:
            # Botão Form View na segunda posição
            form_view_disabled = len(selected_rows) != 1
            if st.button("📝 Form View", disabled=form_view_disabled, key="form_view_btn"):
                if not form_view_disabled:
                    st.session_state["current_page"] = "form"
                    st.rerun()
            
        with col_booking:
            new_booking_disabled = True
            if len(selected_rows) == 1 and original_status is not None:
                cleaned_status = clean_farol_status_value(original_status)
                new_booking_disabled = not (cleaned_status.strip().lower() == "new request".lower())
            if st.button("📦 New Booking", disabled=new_booking_disabled, key="new_booking_btn"):
                if not new_booking_disabled:
                    st.session_state["current_page"] = "booking"
                    st.rerun()
            
        with col_history:
            history_disabled = True
            if len(selected_rows) == 1 and original_status is not None:
                cleaned_status = clean_farol_status_value(original_status)
                history_disabled = not (cleaned_status.strip().lower() != "new request".lower())
            if st.button("🎫 Ticket Journey", disabled=history_disabled, key="history_btn"):
                if not history_disabled:
                    st.session_state["selected_reference"] = selected_farol_ref
                    st.session_state["current_page"] = "history"
                    st.rerun()
            
        with col_split:
            adjustments_disabled = True
            if len(selected_rows) == 1 and original_status is not None:
                cleaned_status = clean_farol_status_value(original_status)
                adjustments_disabled = not (cleaned_status.strip().lower() != "new request".lower())
            if st.button("🛠️ Adjustments", disabled=adjustments_disabled, key="adjustments_btn"):
                if not adjustments_disabled:
                    st.session_state["original_data"] = df
                    st.session_state["selected_reference"] = selected_farol_ref
                    st.session_state["current_page"] = "split"
                    st.rerun()
            
        with col_attachments:
            view_attachments_open = st.session_state.get("show_shipments_attachments", False)
            if st.button("📎 View Attachments", disabled=(len(selected_rows) != 1), key="view_attachments_shipments"):
                if view_attachments_open:
                    st.session_state["show_shipments_attachments"] = False
                    st.session_state["shipments_attachments_farol_ref"] = None
                else:
                    st.session_state["show_shipments_attachments"] = True
                    st.session_state["shipments_attachments_farol_ref"] = selected_farol_ref
                st.rerun()
            
        with col_export:
            # Botão de exportação XLSX - sempre ativo
            if len(df) > 0:  # Só mostra se houver dados para exportar
                # Preparar dados para exportação
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    # Obter o dataframe com as colunas ordenadas, removendo a coluna "Select"
                    columns_to_export = [col for col in colunas_ordenadas if col != "Select"]
                    df_to_export = df[columns_to_export].copy()
                    
                    # Aplicar nomes amigáveis de exibição às colunas
                    from shipments_mapping import get_display_names
                    display_names = get_display_names()
                    
                    # Renomear as colunas usando os nomes amigáveis
                    renamed_columns = {}
                    for col in df_to_export.columns:
                        if col in display_names:
                            renamed_columns[col] = display_names[col]
                        else:
                            friendly_name = col.replace("data_", "").replace("_", " ").title()
                            renamed_columns[col] = friendly_name
                    
                    df_to_export.rename(columns=renamed_columns, inplace=True)
                    df_to_export.to_excel(writer, index=False, sheet_name='Data')
                
                # Botão de download direto
                st.download_button(
                    label="📊 Export XLSX",
                    data=output.getvalue(),
                    file_name=f"shipments_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="export_btn_with_selection"
                )
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