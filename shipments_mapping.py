## shipments_mapping.py
 
import streamlit as st
import pandas as pd
 
def get_column_mapping():
    return {
        # Sales Data
        "s_id": "ID Sales",
        "adjusts_basic" : "Adjusts Basic",
        "adjusts_critic" : "Adjusts Critic",
        "s_shipment_status": "Shipment Status",
        "s_farol_status" : "Farol Status",

        "s_farol_reference": "Sales Farol Reference",
        "s_creation_of_shipment": "Creation Of Shipment",
        "s_customer_po": "Customer PO",
        "s_sales_order_reference": "Sales Order Reference",
        "s_sales_order_date": "data_sales_order",
        "s_business": "Business",
        "s_customer": "Customer",
        "s_mode": "Mode",
        "s_incoterm": "Sales Incoterm",
        "s_sku": "SKU",
        "s_plant_of_origin": "Plant of Origin",
        "s_type_of_shipment": "Type of Shipment",
        "s_splitted_booking_reference": "Splitted Booking Reference",
        "s_volume_in_tons": "Volume in Tons",
        "s_quantity_of_containers": "Sales Quantity of Containers",
        "s_container_type": "Container Type",
        "s_port_of_loading_pol": "Port of Loading POL",
        "s_port_of_delivery_pod": "Port of Delivery POD",
        "s_final_destination": "Final Destination",
        "s_requested_shipment_week": "Requested Shipment Week",
        "s_requested_deadlines_start_date":"data_requested_deadline_start",
        "s_requested_deadlines_end_date":"data_requested_deadline_end",
        "s_dthc_prepaid": "DTHC",
        "s_afloat": "Afloat",
        "s_shipment_period_start_date": "data_shipment_period_start",
        "s_shipment_period_end_date": "data_shipment_period_end",
        "s_required_arrival_date_expected": "data_required_arrival_expected",
        "s_partial_allowed": "Partial Allowed",
        "s_vip_pnl_risk": "VIP PNL Risk",
        "s_pnl_destination": "PNL Destination",
        "s_lc_received": "data_lc_received",
        "s_allocation_date": "data_allocation",
        "s_producer_nomination_date": "data_producer_nomination",
        # "s_first_vessel_etd": "First Vessel ETD",  # coluna removida na unificada
        "s_sales_owner": "Sales Owner",
        "s_comments": "Comments Sales",
        # s_stage não existe mais na unificada; usamos coluna unificada STAGE
        "s_place_of_receipt":"Place of Receipt",
        "s_carrier": "Sales Voyage Carrier",  # Diferente de b_voyage_carrier para evitar duplicação
 
 
        # Booking Management
        "b_id": "ID Booking",
        "b_farol_reference": "Booking Farol Reference",
        "b_creation_of_booking": "Creation Of Booking",
        "b_booking_reference": "Booking Reference",
        "b_booking_status": "Booking Status",
        "b_farol_status" : "Farol Status",

        "b_booking_owner": "Booking Owner",
        "b_voyage_carrier": "Voyage Carrier",
        "b_freight_forwarder": "Freight Forwarder",
        "b_booking_request_date": "data_booking_request",
        "b_booking_confirmation_date": "data_booking_confirmation",
        "b_vessel_name": "Vessel Name",
        "b_voyage_code": "Voyage Code",
        "b_container_type": "Booking Container Type",
        "b_quantity_of_containers": "Booking Quantity of Containers",
        "b_terminal": "Terminal",
        "b_port_of_loading_pol": "Port of Loading POL",
        "b_port_of_delivery_pod": "Port of Delivery POD",
        "b_final_destination": "Final Destination",
        "b_transhipment_port": "Transhipment Port",
        "b_pod_country": "POD Country",
        "b_pod_country_acronym": "POD Country Acronym",
        "b_destination_trade_region": "Destination Trade Region",
        "b_data_draft_deadline": "data_draft_deadline",
        "b_data_deadline": "data_deadline",
        "b_data_estimativa_saida_etd": "data_estimativa_saida",
        "b_data_estimativa_chegada_eta": "data_estimativa_chegada",
        "b_data_abertura_gate": "data_abertura_gate",
        "b_data_confirmacao_embarque": "data_confirmacao_embarque",
        "b_data_partida_atd": "data_partida",
        "b_data_estimada_transbordo_etd": "data_estimada_transbordo",
        "b_data_chegada_ata": "data_chegada",
        "b_data_transbordo_atd": "data_transbordo",
        "b_data_estimativa_atracacao_etb": "data_estimativa_atracacao",
        "b_data_atracacao_atb": "data_atracacao",
        "b_freight_rate_usd": "Freight Rate USD",
        "b_bogey_sale_price_usd": "Bogey Sale Price USD",
        "b_freightppnl": "Freight PNL",
        "b_award_status": "Award Status",
        "b_place_of_receipt":"Place of Receipt",
        "b_comments": "Comments Booking",
 
        # Loading Container
        "l_id": "ID Loading",
        "l_farol_reference": "Loading Farol Reference",
        "l_truck_loading_status": "Truck Loading Status",
        "l_farol_status" : "Farol Status",

        "l_creation_of_cargo_loading": "Creation Of Cargo Loading",
        "l_logistics_analyst": "Logistics Analyst",
        "l_supplier": "Supplier",
        "l_incoterm": "Loading Incoterm",
        "l_stuffing_terminal": "Stuffing Terminal",
        "l_stuffing_terminal_acceptance": "Stuffing Terminal Acceptance",
        "l_drayage_carrier": "Drayage Carrier",
        "l_status_itas": "Status ITAS",
        "l_truck_loading_farol": "Truck Loading Farol",
        "l_expected_truck_load_start_date": "data_expected_truck_load_start",
        "l_expected_truck_load_end_date": "data_expected_truck_load_end",
        "l_quantity_tons_loaded_origin": "Quantity Tons Loaded Origin",
        "l_actual_truck_load_date": "data_actual_truck_load",
        "l_container_release_farol": "Container Release Farol",
        "l_expected_container_release_start_date": "data_expected_container_release_start",
        "l_expected_container_release_end_date": "data_expected_container_release_end",
        "l_actual_container_release_date": "data_actual_container_release",
        "l_quantity_containers_released": "Quantity Containers Released",
        "l_container_release_issue_responsibility": "Container Release Issue Responsibility",
        "l_quantity_containers_released_different_shore": "Quantity Containers Released Different Shore",
        "l_shore_container_release_different": "Shore Container Release Different"
    }
 
 
def non_editable_columns(stage):
 
    if stage == "Sales Data":
        non_editable = ["Sales Farol Reference", "Creation Of Shipment", "Adjusts Basic", "Adjusts Critic"]
    elif stage == "Booking Management":
        non_editable = ["Booking Farol Reference", "Creation Of Booking", "Adjusts Basic", "Adjusts Critic", "Type of Shipment", "Sales Quantity of Containers", "Container Type", "Port of Loading POL", "Port of Delivery POD"]
    elif stage == "Container Delivery at Port":
        non_editable = ["Loading Farol Reference", "Creation Of Cargo Loading", "Adjusts Basic", "Adjusts Critic", "Type of Shipment", "Sales Quantity of Containers", "Container Type", "Port of Loading POL", "Port of Delivery POD"]
    else:
        non_editable = []
 
    return non_editable
 
def drop_downs(data_show, df_udc):
    # Define opções de dropdown com base no grupo do UDC
    dropdown_options = {
        # Sales Data (mantido como está)
        "Partial Allowed": df_udc[df_udc["grupo"] == "Yes No"]["dado"].dropna().unique().tolist(),
        "PNL Destination": df_udc[df_udc["grupo"] == "Yes No"]["dado"].dropna().unique().tolist(),
        "DTHC": df_udc[df_udc["grupo"] == "DTHC"]["dado"].dropna().unique().tolist(),
        "Afloat": df_udc[df_udc["grupo"] == "Yes No"]["dado"].dropna().unique().tolist(),
        "Shipment Status": df_udc[df_udc["grupo"] == "Origin Status"]["dado"].dropna().unique().tolist(),
        "Type of Shipment": df_udc[df_udc["grupo"] == "Type of Shipment"]["dado"].dropna().unique().tolist(),
        "Container Type": df_udc[df_udc["grupo"] == "Container Type"]["dado"].dropna().unique().tolist(),
        "Port of Loading POL": df_udc[df_udc["grupo"] == "Porto Origem"]["dado"].dropna().unique().tolist(),
        "Port of Delivery POD": df_udc[df_udc["grupo"] == "Porto Destino"]["dado"].dropna().unique().tolist(),
        "Business": df_udc[df_udc["grupo"] == "Business"]["dado"].dropna().unique().tolist(),
        "Mode": df_udc[df_udc["grupo"] == "Mode"]["dado"].dropna().unique().tolist(),
        "SKU": df_udc[df_udc["grupo"] == "Sku"]["dado"].dropna().unique().tolist(),
        "VIP PNL Risk": df_udc[df_udc["grupo"] == "VIP PNL Risk"]["dado"].dropna().unique().tolist(),
        "Farol Status": df_udc[df_udc["grupo"] == "Farol Status"]["dado"].dropna().unique().tolist(),

        # Booking Management
        "Booking Status": df_udc[df_udc["grupo"] == "Booking Status"]["dado"].dropna().unique().tolist(),
        "Booking Container Type": df_udc[df_udc["grupo"] == "Container Type"]["dado"].dropna().unique().tolist(),
        "Port of Loading POL": df_udc[df_udc["grupo"] == "Porto Destino"]["dado"].dropna().unique().tolist(),
        "Port of Delivery POD": df_udc[df_udc["grupo"] == "Porto Destino"]["dado"].dropna().unique().tolist(),
        "Voyage Carrier": df_udc[df_udc["grupo"] == "Carrier"]["dado"].dropna().unique().tolist(),
        
        # Container Delivery at Port
        "Truck Loading Status": df_udc[df_udc["grupo"] == "Truck Loading Status"]["dado"].dropna().unique().tolist(),
        "Status ITAS": df_udc[df_udc["grupo"] == "Status ITAS"]["dado"].dropna().unique().tolist(),
    }

    # Tipo de editor para colunas específicas
    column_editors = {
        # Sales Data (mantido como está)
        "Shipment Status": "select",
        "Business": "select",
        "Port of Loading POL": "select",
        "Port of Delivery POD": "select",
        "Mode": "select",
        "SKU": "select",
        "VIP PNL Risk": "select",
        "Partial Allowed": "select",
        "PNL Destination": "select",
        "DTHC": "select",
        "Afloat": "select",
        "Container Type": "select",
        "Type of Shipment": "select",
        "data_sales_order": "date",
        "data_requested_deadline_start": "date",
        "data_requested_deadline_end": "date",
        "data_shipment_period_start": "date",
        "data_shipment_period_end": "date",
        "data_required_arrival_expected": "date",
        "data_lc_received": "date",
        "data_allocation": "date",
        "data_producer_nomination": "date",
        # "First Vessel ETD": "date",  # coluna removida na unificada
        "Volume in Tons": "numeric",
        "Sales Quantity of Containers": "numeric",
        "Requested Shipment Week": "numeric",
        "Farol Status": "select",

        # Booking Management
        "Booking Status": "select",
        "Booking Container Type": "select",
        "Port of Loading POL": "select",
        "Port of Delivery POD": "select",
        "Voyage Carrier": "select",
        "data_booking_request": "date",
        "data_booking_confirmation": "date",
        "data_draft_deadline": "datetime",
        "data_deadline": "datetime",
        "data_estimativa_saida": "datetime",
        "data_estimativa_chegada": "datetime",
        "data_abertura_gate": "datetime",
        "data_confirmacao_embarque": "datetime",
        "data_partida": "datetime",
        "data_estimada_transbordo": "datetime",
        "data_chegada": "datetime",
        "data_transbordo": "datetime",
        "data_estimativa_atracacao": "datetime",
        "data_atracacao": "datetime",
        "Booking Quantity of Containers": "numeric",
        "Freight Rate USD": "numeric",
        "Bogey Sale Price USD": "numeric",
        "Freight PNL": "numeric",

        # Container Delivery at Port
        "Truck Loading Status": "select",
        "Status ITAS": "select",
        "data_expected_truck_load_start": "date",
        "data_expected_truck_load_end": "date",
        "data_actual_truck_load": "date",
        "data_expected_container_release_start": "date",
        "data_expected_container_release_end": "date",
        "data_actual_container_release": "date",
        "Quantity Tons Loaded Origin": "numeric",
        "Quantity Containers Released": "numeric",
        "Quantity Containers Released Different Shore": "numeric"
    }

    # Campos obrigatórios (mantido e expandido)
    campos_obrigatorios = {
        # Sales Data
        "DTHC": True,
        "Afloat": True,
        #"Shipment Status": True,
        "Farol Status": True,
        "Type of Shipment": True,
        "Container Type": True,
        "Port of Delivery POD": True,  # Obrigatório na grade principal (Sales)
        "Business": True,
        "Mode": True,
        "SKU": True,


        # Booking Management
        #"Booking Status": True,
        "Booking Container Type": True,
        "Port of Loading POL": True,
        "Port of Delivery POD": True,

        # Container Delivery at Port
        #"Truck Loading Status": True,
    }

    # Mapeamento de nomes de exibição amigáveis
    display_names = {
        # Sales Data
        "data_sales_order": "Sales Order Date",
        "data_requested_deadline_start": "Requested Deadline Start",
        "data_requested_deadline_end": "Requested Deadline End",
        "data_shipment_period_start": "Shipment Period Start",
        "data_shipment_period_end": "Shipment Period End",
        "data_required_arrival_expected": "Required Arrival Expected",
        "data_lc_received": "LC Received",
        "data_allocation": "Allocation Date",
        "data_producer_nomination": "Producer Nomination",
        
        # Booking Management
        "data_booking_request": "Booking Request Date",
        "data_booking_confirmation": "Booking Confirmation Date",
        "data_draft_deadline": "Draft Deadline",
        "data_deadline": "Deadline",
        "data_estimativa_saida": "ETD",
        "data_estimativa_chegada": "ETA",
        "data_abertura_gate": "Abertura Gate",
        "data_confirmacao_embarque": "Confirmação Embarque",
        "data_partida": "Partida (ATD)",
        "data_estimada_transbordo": "Estimada Transbordo (ETD)",
        "data_chegada": "Chegada (ATA)",
        "data_transbordo": "Transbordo (ATD)",
        "data_estimativa_atracacao": "Estimativa Atracação (ETB)",
        "data_atracacao": "Atracação (ATB)",
        
        # Loading Data
        "data_expected_truck_load_start": "Expected Truck Load Start",
        "data_expected_truck_load_end": "Expected Truck Load End",
        "data_actual_truck_load": "Actual Truck Load",
        "data_expected_container_release_start": "Expected Container Release Start",
        "data_expected_container_release_end": "Expected Container Release End",
        "data_actual_container_release": "Actual Container Release"
    }

    column_config = {}

    for col in data_show.columns:
        editor_type = column_editors.get(col)
        display_name = display_names.get(col, col)  # Usa nome amigável se disponível

        if editor_type == "select" and col in dropdown_options:
            required_field = campos_obrigatorios.get(col, False)
            # Tornar 'Port of Loading POL' obrigatório apenas quando a grade é de Booking
            if col == "Port of Loading POL":
                is_booking_view = (
                    "Booking Status" in data_show.columns
                    or "Booking Reference" in data_show.columns
                    or "Voyage Carrier" in data_show.columns
                )
                required_field = bool(is_booking_view)
            column_config[col] = st.column_config.SelectboxColumn(
                label=display_name,
                options=dropdown_options[col],
                required=required_field
            )
        elif editor_type == "date":
            column_config[col] = st.column_config.DateColumn(
                label=display_name,
                format="DD/MM/YYYY"
            )
        elif editor_type == "datetime":
            column_config[col] = st.column_config.DatetimeColumn(
                label=display_name,
                format="DD/MM/YYYY HH:mm",
                step=60  # Passo de 1 minuto para edição
            )
        elif editor_type == "numeric":
            column_config[col] = st.column_config.NumberColumn(
                label=display_name
            )

    return column_config
 
 
 
#Função utilizada para coletar os dados chaves referente a alterações simples para cada stage
def get_reverse_mapping():
    column_mapping = get_column_mapping()
    return {v: k for k, v in column_mapping.items()}