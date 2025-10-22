## shipments_mapping.py
 
import streamlit as st
import pandas as pd
 
def get_column_mapping():
    return {
        # Sales Data
        "s_id": "ID Sales",
        "adjusts_basic" : "Adjusts Basic",
        "adjusts_critic" : "Adjusts Critic",
        "s_farol_status" : "Farol Status",

        "s_farol_reference": "Sales Farol Reference",
        "s_creation_of_shipment": "Shipment Requested Date",
        "s_customer_po": "Customer PO",
        "s_sales_order_reference": "Sales Order Reference",
        "s_sales_order_date": "data_sales_order",
        "s_business": "Business",
        "s_customer": "Customer",
        "s_mode": "Mode",
        "s_incoterm": "Incoterm",
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
        "b_creation_of_booking": "Booking Registered Date",
        "b_booking_reference": "Booking Reference",
        "b_transaction_number": "Transaction Number",
        "b_booking_status": "Booking Status",
        "b_farol_status" : "Farol Status",

        "b_booking_owner": "Booking Owner",
        "b_voyage_carrier": "Carrier",
        "b_freight_forwarder": "Freight Forwarder",
        "b_booking_request_date": "Booking Requested Date",
        "b_booking_confirmation_date": "data_booking_confirmation",
        "b_vessel_name": "Vessel Name",
        "b_voyage_code": "Voyage Code",
        "b_container_type": "Booking Container Type",
        "b_quantity_of_containers": "Booking Quantity of Containers",
        "b_terminal": "Port Terminal",
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
        "b_data_chegada_destino_eta": "data_chegada_destino_eta",
        "b_data_chegada_destino_ata": "data_chegada_destino_ata",
        "b_data_estimativa_atracacao_etb": "data_estimativa_atracacao",
        "b_data_atracacao_atb": "data_atracacao",
        "b_freight_rate_usd": "Freight Rate USD",
        "b_bogey_sale_price_usd": "Bogey Sale Price USD",
        "b_freightppnl": "Freight PNL",
        "b_award_status": "Award Status",
        "b_place_of_receipt":"Place of Receipt",
        "b_comments": "Comments Booking",
        "b_deviation_document": "Deviation Document",
        "b_deviation_responsible": "Deviation Responsible",
        "b_deviation_reason": "Deviation Reason",
 
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
        non_editable = ["Sales Farol Reference", "Shipment Requested Date", "Adjusts Basic", "Adjusts Critic", "Sales Owner", "Booking Owner"]
    elif stage == "Booking Management":
        non_editable = ["Booking Farol Reference", "Booking Registered Date", "Adjusts Basic", "Adjusts Critic", "Type of Shipment", "Sales Quantity of Containers", "Container Type", "Port of Loading POL", "Port of Delivery POD", "Sales Owner", "Booking Owner"]
    elif stage == "General View":
        non_editable = list(dict.fromkeys([
            "Sales Farol Reference", "Shipment Requested Date", "Adjusts Basic", "Adjusts Critic",
            "Booking Registered Date", "Type of Shipment", "Sales Quantity of Containers", "Container Type", 
            "Port of Loading POL", "Port of Delivery POD", "Sales Owner", "Booking Owner"
        ]))
    elif stage == "Container Delivery at Port":
        non_editable = ["Loading Farol Reference", "Creation Of Cargo Loading", "Adjusts Basic", "Adjusts Critic", "Type of Shipment", "Sales Quantity of Containers", "Container Type", "Port of Loading POL", "Port of Delivery POD", "Sales Owner", "Booking Owner"]
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
        "Type of Shipment": df_udc[df_udc["grupo"] == "Type of Shipment"]["dado"].dropna().unique().tolist(),
        "Container Type": df_udc[df_udc["grupo"] == "Container Type"]["dado"].dropna().unique().tolist(),
        "Port of Loading POL": df_udc[df_udc["grupo"] == "Porto Origem"]["dado"].dropna().unique().tolist(),
        "Port of Delivery POD": df_udc[df_udc["grupo"] == "Porto Destino"]["dado"].dropna().unique().tolist(),
        "Business": df_udc[df_udc["grupo"] == "Business"]["dado"].dropna().unique().tolist(),
        "Mode": df_udc[df_udc["grupo"] == "Mode"]["dado"].dropna().unique().tolist(),
        "SKU": df_udc[df_udc["grupo"] == "Sku"]["dado"].dropna().unique().tolist(),
        "VIP PNL Risk": df_udc[df_udc["grupo"] == "VIP PNL Risk"]["dado"].dropna().unique().tolist(),
        "Farol Status": [get_display_from_status(s) for s in df_udc[df_udc["grupo"] == "Farol Status"]["dado"].dropna().unique().tolist()],

        # Booking Management
        "Booking Status": df_udc[df_udc["grupo"] == "Booking Status"]["dado"].dropna().unique().tolist(),
        "Booking Container Type": df_udc[df_udc["grupo"] == "Container Type"]["dado"].dropna().unique().tolist(),
        "Port of Loading POL": df_udc[df_udc["grupo"] == "Porto Destino"]["dado"].dropna().unique().tolist(),
        "Port of Delivery POD": df_udc[df_udc["grupo"] == "Porto Destino"]["dado"].dropna().unique().tolist(),
        "Carrier": df_udc[df_udc["grupo"] == "Carrier"]["dado"].dropna().unique().tolist(),
        
        # Deviation Fields
        "Deviation Document": df_udc[df_udc["grupo"] == "Deviation Document"]["dado"].dropna().unique().tolist(),
        "Deviation Responsible": df_udc[df_udc["grupo"] == "Deviation Responsible"]["dado"].dropna().unique().tolist(),
        "Deviation Reason": df_udc[df_udc["grupo"] == "Deviation Reason"]["dado"].dropna().unique().tolist(),
        
        # Container Delivery at Port
        "Truck Loading Status": df_udc[df_udc["grupo"] == "Truck Loading Status"]["dado"].dropna().unique().tolist(),
        "Status ITAS": df_udc[df_udc["grupo"] == "Status ITAS"]["dado"].dropna().unique().tolist(),
    }

    # Tipo de editor para colunas específicas
    column_editors = {
        # Sales Data (mantido como está)
        "Farol Status": "select",
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
        "data_required_sail_date": "date",
        "data_required_arrival_expected": "date",
        "data_lc_received": "date",
        "data_allocation": "date",
        "data_producer_nomination": "date",
        "Shipment Requested Date": "datetime",  # Adiciona coluna de criação como datetime
        # "First Vessel ETD": "date",  # coluna removida na unificada
        "Volume in Tons": "numeric",
        "Sales Quantity of Containers": "numeric",
        "Requested Shipment Week": "numeric",
        

        # Booking Management
        "Booking Status": "select",
        "Booking Container Type": "select",
        "Port of Loading POL": "select",
        "Port of Delivery POD": "select",
        "Carrier": "select",
        "data_booking_request": "date",
        "data_booking_confirmation": "date",
        "Booking Registered Date": "datetime",  # Adiciona coluna de criação como datetime
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
        
        # Deviation Fields
        "Deviation Document": "select",
        "Deviation Responsible": "select",
        "Deviation Reason": "select",

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
        "data_required_sail_date": "Required Sail Date",
        "data_required_arrival_expected": "Required Arrival Date",
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
        "data_chegada_destino_eta": "Estimativa Chegada Destino (ETA)",
        "data_chegada_destino_ata": "Chegada no Destino (ATA)",
        "data_estimativa_atracacao": "Estimativa Atracação (ETB)",
        "data_atracacao": "Atracação (ATB)",
        
        # Loading Data
        "data_expected_truck_load_start": "Expected Truck Load Start",
        "data_expected_truck_load_end": "Expected Truck Load End",
        "data_actual_truck_load": "Actual Truck Load",
        "data_expected_container_release_start": "Expected Container Release Start",
        "data_expected_container_release_end": "Expected Container Release End",
        "data_actual_container_release": "Actual Container Release",
        
        # Deviation Fields
        "Deviation Document": "Deviation Document",
        "Deviation Responsible": "Deviation Responsible",
        "Deviation Reason": "Deviation Reason"
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
                    or "Carrier" in data_show.columns
                )
                required_field = bool(is_booking_view)
            if col == "Farol Status":
                column_config[col] = st.column_config.SelectboxColumn(
                    label=display_name,
                    options=dropdown_options[col],
                    required=required_field,
                    width="medium"
                )
            else:
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

def get_display_names():
    """Retorna o mapeamento de nomes internos para nomes amigáveis de exibição"""
    return {
        # Transaction Number
        "Transaction Number": "Transaction Number",
        "b_transaction_number": "Transaction Number",
        # Sales Data
        "data_sales_order": "Sales Order Date",
        "data_requested_deadline_start": "Requested Deadline Start",
        "data_requested_deadline_end": "Requested Deadline End",
        "data_shipment_period_start": "Shipment Period Start",
        "data_shipment_period_end": "Shipment Period End",
        "data_required_sail_date": "Required Sail Date",
        "data_required_arrival_expected": "Required Arrival Date",
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
        "data_chegada_destino_eta": "Estimativa Chegada Destino (ETA)",
        "data_chegada_destino_ata": "Chegada no Destino (ATA)",
        "data_estimativa_atracacao": "Estimativa Atracação (ETB)",
        "data_atracacao": "Atracação (ATB)",
        
        # Loading Data
        "data_expected_truck_load_start": "Expected Truck Load Start",
        "data_expected_truck_load_end": "Expected Truck Load End",
        "data_actual_truck_load": "Actual Truck Load",
        "data_expected_container_release_start": "Expected Container Release Start",
        "data_expected_container_release_end": "Expected Container Release End",
        "data_actual_container_release": "Actual Container Release",
        
        # Deviation Fields
        "Deviation Document": "Deviation Document",
        "Deviation Responsible": "Deviation Responsible",
        "Deviation Reason": "Deviation Reason"
    }
 
 
 
#Função utilizada para coletar os dados chaves referente a alterações simples para cada stage
def get_reverse_mapping():
    column_mapping = get_column_mapping()
    return {v: k for k, v in column_mapping.items()}

def get_alias_to_database_column_mapping():
    """
    Retorna o mapeamento de alias SQL para nome real da coluna no banco de dados.
    
    Resolve o problema de aliases com prefixos diferentes (s_, b_) que mapeiam 
    para a mesma coluna física (S_*, B_*) em F_CON_SALES_BOOKING_DATA.
    
    Returns:
        dict: {alias_sql: coluna_banco}
    """
    return {
        # Aliases que apontam para colunas S_* (Sales)
        "s_farol_reference": "FAROL_REFERENCE",
        "s_farol_status": "FAROL_STATUS",
        "s_shipment_status": "S_SHIPMENT_STATUS",
        "s_type_of_shipment": "S_TYPE_OF_SHIPMENT",
        "s_creation_of_shipment": "S_CREATION_OF_SHIPMENT",
        "s_customer_po": "S_CUSTOMER_PO",
        "s_sales_order_reference": "S_SALE_ORDER_REFERENCE",
        "s_sales_order_date": "S_SALE_ORDER_DATE",
        "s_business": "S_BUSINESS",
        "s_customer": "S_CUSTOMER",
        "s_mode": "S_MODE",
        "s_incoterm": "S_INCOTERM",
        "s_sku": "S_SKU",
        "s_plant_of_origin": "S_PLANT_OF_ORIGIN",
        "s_splitted_booking_reference": "S_SPLITTED_BOOKING_REFERENCE",
        "s_volume_in_tons": "S_VOLUME_IN_TONS",
        "s_quantity_of_containers": "S_QUANTITY_OF_CONTAINERS",
        "s_container_type": "S_CONTAINER_TYPE",
        "s_port_of_loading_pol": "S_PORT_OF_LOADING_POL",
        "s_port_of_delivery_pod": "S_PORT_OF_DELIVERY_POD",
        "s_place_of_receipt": "S_PLACE_OF_RECEIPT",
        "s_final_destination": "S_FINAL_DESTINATION",
        "s_requested_shipment_week": "S_REQUESTED_SHIPMENT_WEEK",
        "s_requested_deadlines_start_date": "S_REQUESTED_DEADLINE_START_DATE",
        "s_requested_deadlines_end_date": "S_REQUESTED_DEADLINE_END_DATE",
        "s_dthc_prepaid": "S_DTHC_PREPAID",
        "s_afloat": "S_AFLOAT",
        "s_shipment_period_start_date": "S_SHIPMENT_PERIOD_START_DATE",
        "s_shipment_period_end_date": "S_SHIPMENT_PERIOD_END_DATE",
        "s_required_sail_date": "S_REQUIRED_SAIL_DATE",
        "s_required_arrival_date_expected": "S_REQUIRED_ARRIVAL_DATE_EXPECTED",
        "s_partial_allowed": "S_PARTIAL_ALLOWED",
        "s_vip_pnl_risk": "S_VIP_PNL_RISK",
        "s_pnl_destination": "S_PNL_DESTINATION",
        "s_lc_received": "S_LC_RECEIVED",
        "s_allocation_date": "S_ALLOCATION_DATE",
        "s_producer_nomination_date": "S_PRODUCER_NOMINATION_DATE",
        "s_sales_owner": "USER_LOGIN_SALES_CREATED",
        "s_comments": "S_COMMENTS",
        
        # Aliases com prefixo b_ que apontam para colunas B_* (Booking)
        "b_farol_reference": "FAROL_REFERENCE",
        "b_farol_status": "FAROL_STATUS",
        "b_creation_of_booking": "B_CREATION_OF_BOOKING",
        "b_booking_reference": "B_BOOKING_REFERENCE",
        "b_transaction_number": "B_TRANSACTION_NUMBER",
        "b_booking_status": "B_BOOKING_STATUS",
        "b_booking_owner": "USER_LOGIN_BOOKING_CREATED",
        "b_voyage_carrier": "B_VOYAGE_CARRIER",
        "b_freight_forwarder": "B_FREIGHT_FORWARDER",
        "b_booking_request_date": "B_BOOKING_REQUEST_DATE",
        "b_booking_confirmation_date": "B_BOOKING_CONFIRMATION_DATE",
        "b_vessel_name": "B_VESSEL_NAME",
        "b_voyage_code": "B_VOYAGE_CODE",
        "b_terminal": "B_TERMINAL",
        "b_transhipment_port": "B_TRANSHIPMENT_PORT",
        "b_pod_country": "B_POD_COUNTRY",
        "b_pod_country_acronym": "B_POD_COUNTRY_ACRONYM",
        "b_destination_trade_region": "B_DESTINATION_TRADE_REGION",
        "b_data_draft_deadline": "B_DATA_DRAFT_DEADLINE",
        "b_data_deadline": "B_DATA_DEADLINE",
        "b_data_estimativa_saida_etd": "B_DATA_ESTIMATIVA_SAIDA_ETD",
        "b_data_estimativa_chegada_eta": "B_DATA_ESTIMATIVA_CHEGADA_ETA",
        "b_data_abertura_gate": "B_DATA_ABERTURA_GATE",
        "b_data_confirmacao_embarque": "B_DATA_CONFIRMACAO_EMBARQUE",
        "b_data_partida_atd": "B_DATA_PARTIDA_ATD",
        "b_data_estimada_transbordo_etd": "B_DATA_ESTIMADA_TRANSBORDO_ETD",
        "b_data_chegada_ata": "B_DATA_CHEGADA_ATA",
        "b_data_transbordo_atd": "B_DATA_TRANSBORDO_ATD",
        "b_data_chegada_destino_eta": "B_DATA_CHEGADA_DESTINO_ETA",
        "b_data_chegada_destino_ata": "B_DATA_CHEGADA_DESTINO_ATA",
        "b_data_estimativa_atracacao_etb": "B_DATA_ESTIMATIVA_ATRACACAO_ETB",
        "b_data_atracacao_atb": "B_DATA_ATRACACAO_ATB",
        "b_freight_rate_usd": "B_FREIGHT_RATE_USD",
        "b_bogey_sale_price_usd": "B_BOGEY_SALE_PRICE_USD",
        "b_freightppnl": "B_FREIGHTPPNL",
        "b_award_status": "B_AWARD_STATUS",
        "b_comments": "B_COMMENTS",
        "b_deviation_document": "B_DEVIATION_DOCUMENT",
        "b_deviation_responsible": "B_DEVIATION_RESPONSIBLE",
        "b_deviation_reason": "B_DEVIATION_REASON",
        
        # ⚠️ IMPORTANTE: Aliases com b_ que na verdade apontam para colunas S_*
        # (usado em Booking Management para exibir campos de Sales)
        "b_port_of_loading_pol": "S_PORT_OF_LOADING_POL",  # ← Alias b_ mas coluna S_!
        "b_port_of_delivery_pod": "S_PORT_OF_DELIVERY_POD",  # ← Alias b_ mas coluna S_!
        "b_place_of_receipt": "S_PLACE_OF_RECEIPT",
        "b_final_destination": "S_FINAL_DESTINATION",  # General View usa S_FINAL_DESTINATION
    }

def get_database_column_name(display_name_or_alias: str) -> str:
    """
    Converte nome amigável OU alias SQL para nome real da coluna do banco de dados.
    
    Args:
        display_name_or_alias: Nome amigável ("Port of Loading POL") ou alias SQL ("b_port_of_loading_pol")
    
    Returns:
        Nome real da coluna em UPPER CASE ("S_PORT_OF_LOADING_POL")
    """
    # Primeiro tenta como alias SQL (mais preciso)
    alias_mapping = get_alias_to_database_column_mapping()
    lower_input = display_name_or_alias.lower()
    
    if lower_input in alias_mapping:
        return alias_mapping[lower_input]
    
    # Tenta mapeamento reverso completo (nome amigável → alias → coluna)
    reverse_mapping = get_reverse_mapping()
    
    if display_name_or_alias in reverse_mapping:
        alias = reverse_mapping[display_name_or_alias]
        # Converte alias para nome de coluna do banco
        if alias.lower() in alias_mapping:
            return alias_mapping[alias.lower()]
        # Fallback: converte para UPPER CASE
        return alias.upper()
    
    # Casos especiais que não passam pelo mapeamento
    special_cases = {
        "Farol Status": "FAROL_STATUS",
        "Farol Reference": "FAROL_REFERENCE",
        "Select": "SELECT",  # Coluna UI, não existe no banco
        "Transaction Number": "B_TRANSACTION_NUMBER",
        "b_transaction_number": "B_TRANSACTION_NUMBER",
        "Deviation Document": "B_DEVIATION_DOCUMENT",
        "Deviation Responsible": "B_DEVIATION_RESPONSIBLE",
        "Deviation Reason": "B_DEVIATION_REASON",
    }
    
    if display_name_or_alias in special_cases:
        return special_cases[display_name_or_alias]
    
    # Fallback final: assume que o nome já é técnico e converte para UPPER
    return display_name_or_alias.upper().replace(" ", "_")

# --- Bloco de Funções para Ícones do Farol Status ---

def get_farol_status_icons():
    """Retorna o dicionário que mapeia o status do Farol para um ícone."""
    return {
        "New Request": "📦",
        "Booking Requested": "📋",
        "Received from Carrier": "📨",
        "Booking Under Review": "🔍",
        "Adjustment Requested": "✏️",
        "Booking Approved": "✅",
        "Booking Cancelled": "❌",
        "Booking Rejected": "🚫",
    }

def get_icon_only(status: str) -> str:
    """Retorna apenas o ícone para um determinado status."""
    icons = get_farol_status_icons()
    # Limpa o status para garantir a correspondência
    clean_status = get_status_from_display(status)
    return icons.get(clean_status, "⚫")

def get_display_from_status(status: str) -> str:
    """Adiciona o ícone a uma string de status limpa."""
    if not isinstance(status, str) or not status:
        return status
    icon = get_icon_only(status)
    # Evita adicionar ícone se já tiver um
    if not status.startswith(icon):
        return f"{icon} {status}"
    return status

def get_status_from_display(display_status: str) -> str:
    """Remove o ícone de uma string de status formatada."""
    if not isinstance(display_status, str) or not display_status:
        return display_status
    
    icons = get_farol_status_icons()
    # Itera sobre os ícones para encontrar e remover o prefixo
    for icon in icons.values():
        if display_status.startswith(icon):
            return display_status.replace(f"{icon} ", "").strip()
    return display_status

# Alias para consistência com o guia
clean_farol_status_value = get_status_from_display

def get_farol_status_with_icons() -> list:
    """Retorna uma lista de status formatados com ícones."""
    # Esta função agora pode ser usada para popular dropdowns
    icons = get_farol_status_icons()
    return [f"{icon} {status}" for status, icon in icons.items()]

def process_farol_status_for_display(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica a formatação com ícones na coluna 'Farol Status' de um DataFrame."""
    if "Farol Status" in df.columns:
        df["Farol Status"] = df["Farol Status"].apply(get_display_from_status)
    return df

def process_farol_status_for_database(df: pd.DataFrame) -> pd.DataFrame:
    """Remove a formatação com ícones da coluna 'Farol Status' de um DataFrame."""
    if "Farol Status" in df.columns:
        df["Farol Status"] = df["Farol Status"].apply(get_status_from_display)
    return df