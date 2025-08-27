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
        "s_sales_order_date": "Sales Order Date",
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
        "s_port_of_loading_pol": "Sales Port of Loading POL",
        "s_port_of_delivery_pod": "Sales Port of Delivery POD",
        "s_final_destination": "Sales Final Destination",
        "s_requested_shipment_week": "Requested Shipment Week",
        "s_requested_deadlines_start_date":"Requested Cut off Start Date",
        "s_requested_deadlines_end_date":"Requested Cut off End Date",
        "s_dthc_prepaid": "DTHC",
        "s_afloat": "Afloat",
        "s_shipment_period_start_date": "Shipment Period Start Date",
        "s_shipment_period_end_date": "Shipment Period End Date",
        "s_required_arrival_date": "Required Arrival Date",
        "s_partial_allowed": "Partial Allowed",
        "s_vip_pnl_risk": "VIP PNL Risk",
        "s_pnl_destination": "PNL Destination",
        "s_lc_received": "LC Received",
        "s_allocation_date": "Allocation Date",
        "s_producer_nomination_date": "Producer Nomination Date",
        # "s_first_vessel_etd": "First Vessel ETD",  # coluna removida na unificada
        "s_sales_owner": "Sales Owner",
        "s_comments": "Comments Sales",
        # s_stage não existe mais na unificada; usamos coluna unificada STAGE
        "s_place_of_receipt":"Sales Place of Receipt",
 
 
        # Booking Management
        "b_id": "ID Booking",
        "b_farol_reference": "Booking Farol Reference",
        "b_creation_of_booking": "Creation Of Booking",
        "b_booking_reference": "Booking Reference",
        "b_booking_status": "Booking Status",
        "b_farol_status" : "Farol Status",

        "b_booking_owner": "Booking Owner",
        "b_carrier": "Carrier",
        "b_freight_forwarder": "Freight Forwarder",
        "b_booking_request_date": "Booking Request Date",
        "b_booking_confirmation_date": "Booking Confirmation Date",
        "b_vessel_name": "Vessel Name",
        "b_voyage_carrier": "Voyage Carrier",
        "b_container_type": "Booking Container Type",
        "b_quantity_of_containers": "Booking Quantity of Containers",
        "b_port_terminal_city": "Port Terminal City",
        "b_port_of_loading_pol": "Booking Port of Loading POL",
        "b_port_of_delivery_pod": "Booking Port of Delivery POD",
        "b_final_destination": "Booking Final Destination",
        "b_transhipment_port": "Transhipment Port",
        "b_pod_country": "POD Country",
        "b_pod_country_acronym": "POD Country Acronym",
        "b_destination_trade_region": "Destination Trade Region",
        "b_first_document_cut_off_doccut": "First Document Cut Off DOCCUT",
        "b_first_port_cut_off_portcut": "First Port Cut Off PORTCUT",
        "b_first_estimated_time_of_departure_etd": "First Estimated Time Of Departure ETD",
        "b_first_estimated_time_of_arrival_eta": "First Estimated Time Of Arrival ETA",
        "b_voyage_port_terminal": "Voyage Port Terminal",
        "b_current_document_cut_off_doccut": "Current Document Cut Off DOCCUT",
        "b_current_port_cut_off_portcut": "Current Port Cut Off PORTCUT",
        "b_current_estimated_time_of_departure_etd": "Current Estimated Time Of Departure ETD",
        "b_current_estimated_time_of_arrival_eta": "Current Estimated Time Of Arrival ETA",
        "b_freight_rate_usd": "Freight Rate USD",
        "b_bogey_sale_price_usd": "Bogey Sale Price USD",
        "b_freightppnl": "Freight PNL",
        "b_award_status": "Award Status",
        "b_place_of_receipt":"Booking Place of Receipt",
        "b_comments": "Comments Booking",
        "b_place_of_receipt":"Booking Place of Receipt",
 
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
        "l_expected_truck_load_start_date": "Expected Truck Load Start Date",
        "l_expected_truck_load_end_date": "Expected Truck Load End Date",
        "l_quantity_tons_loaded_origin": "Quantity Tons Loaded Origin",
        "l_actual_truck_load_date": "Actual Truck Load Date",
        "l_container_release_farol": "Container Release Farol",
        "l_expected_container_release_start_date": "Expected Container Release Start Date",
        "l_expected_container_release_end_date": "Expected Container Release End Date",
        "l_actual_container_release_date": "Actual Container Release Date",
        "l_quantity_containers_released": "Quantity Containers Released",
        "l_container_release_issue_responsibility": "Container Release Issue Responsibility",
        "l_quantity_containers_released_different_shore": "Quantity Containers Released Different Shore",
        "l_shore_container_release_different": "Shore Container Release Different"
    }
 
 
def non_editable_columns(stage):
 
    if stage == "Sales Data":
        non_editable = ["Sales Farol Reference", "Creation Of Shipment", "Adjusts Basic", "Adjusts Critic"]
    elif stage == "Booking Management":
        non_editable = ["Booking Farol Reference", "Creation Of Booking", "Adjusts Basic", "Adjusts Critic", "Type of Shipment", "Sales Quantity of Containers", "Container Type", "Booking Port of Loading POL", "Booking Port of Delivery POD"]
    elif stage == "Container Delivery at Port":
        non_editable = ["Loading Farol Reference", "Creation Of Cargo Loading", "Adjusts Basic", "Adjusts Critic", "Type of Shipment", "Sales Quantity of Containers", "Container Type", "Sales Port of Loading POL", "Sales Port of Delivery POD"]
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
        "Sales Port of Loading POL": df_udc[df_udc["grupo"] == "Porto Origem"]["dado"].dropna().unique().tolist(),
        "Sales Port of Delivery POD": df_udc[df_udc["grupo"] == "Porto Destino"]["dado"].dropna().unique().tolist(),
        "Business": df_udc[df_udc["grupo"] == "Business"]["dado"].dropna().unique().tolist(),
        "Mode": df_udc[df_udc["grupo"] == "Mode"]["dado"].dropna().unique().tolist(),
        "SKU": df_udc[df_udc["grupo"] == "Sku"]["dado"].dropna().unique().tolist(),
        "VIP PNL Risk": df_udc[df_udc["grupo"] == "VIP PNL Risk"]["dado"].dropna().unique().tolist(),
        "Farol Status": df_udc[df_udc["grupo"] == "Farol Status"]["dado"].dropna().unique().tolist(),

        # Booking Management
        "Booking Status": df_udc[df_udc["grupo"] == "Booking Status"]["dado"].dropna().unique().tolist(),
        "Booking Container Type": df_udc[df_udc["grupo"] == "Container Type"]["dado"].dropna().unique().tolist(),
        "Booking Port of Loading POL": df_udc[df_udc["grupo"] == "Porto Origem"]["dado"].dropna().unique().tolist(),
        "Booking Port of Delivery POD": df_udc[df_udc["grupo"] == "Porto Destino"]["dado"].dropna().unique().tolist(),
        "Carrier": df_udc[df_udc["grupo"] == "Carrier"]["dado"].dropna().unique().tolist(),
        
        # Container Delivery at Port
        "Truck Loading Status": df_udc[df_udc["grupo"] == "Truck Loading Status"]["dado"].dropna().unique().tolist(),
        "Status ITAS": df_udc[df_udc["grupo"] == "Status ITAS"]["dado"].dropna().unique().tolist(),
    }

    # Tipo de editor para colunas específicas
    column_editors = {
        # Sales Data (mantido como está)
        "Shipment Status": "select",
        "Business": "select",
        "Sales Port of Loading POL": "select",
        "Sales Port of Delivery POD": "select",
        "Mode": "select",
        "SKU": "select",
        "VIP PNL Risk": "select",
        "Partial Allowed": "select",
        "PNL Destination": "select",
        "DTHC": "select",
        "Afloat": "select",
        "Container Type": "select",
        "Type of Shipment": "select",
        "Sales Order Date": "date",
        "Requested Cut off Start Date": "date",
        "Requested Cut off End Date": "date",
        "Shipment Period Start Date": "date",
        "Shipment Period End Date": "date",
        "Required Arrival Date": "date",
        "LC Received": "date",
        "Allocation Date": "date",
        "Producer Nomination Date": "date",
        # "First Vessel ETD": "date",  # coluna removida na unificada
        "Volume in Tons": "numeric",
        "Sales Quantity of Containers": "numeric",
        "Requested Shipment Week": "numeric",
        "Farol Status": "select",

        # Booking Management
        "Booking Status": "select",
        "Booking Container Type": "select",
        "Booking Port of Loading POL": "select",
        "Booking Port of Delivery POD": "select",
        "Carrier": "select",
        "Booking Request Date": "date",
        "Booking Confirmation Date": "date",
        "First Document Cut Off DOCCUT": "date",
        "First Port Cut Off PORTCUT": "date",
        "First Estimated Time Of Departure ETD": "date",
        "First Estimated Time Of Arrival ETA": "date",
        "Current Document Cut Off DOCCUT": "datetime",
        "Current Port Cut Off PORTCUT": "datetime",
        "Current Estimated Time Of Departure ETD": "datetime",
        "Current Estimated Time Of Arrival ETA": "datetime",
        "Booking Quantity of Containers": "numeric",
        "Freight Rate USD": "numeric",
        "Bogey Sale Price USD": "numeric",
        "Freight PNL": "numeric",

        # Container Delivery at Port
        "Truck Loading Status": "select",
        "Status ITAS": "select",
        "Expected Truck Load Start Date": "date",
        "Expected Truck Load End Date": "date",
        "Actual Truck Load Date": "date",
        "Expected Container Release Start Date": "date",
        "Expected Container Release End Date": "date",
        "Actual Container Release Date": "date",
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
        "Sales Port of Delivery POD": True,
        "Business": True,
        "Mode": True,
        "SKU": True,


        # Booking Management
        #"Booking Status": True,
        "Booking Container Type": True,
        "Booking Port of Loading POL": True,
        "Booking Port of Delivery POD": True,

        # Container Delivery at Port
        #"Truck Loading Status": True,
    }

    column_config = {}

    for col in data_show.columns:
        editor_type = column_editors.get(col)

        if editor_type == "select" and col in dropdown_options:
            required_field = campos_obrigatorios.get(col, False)
            column_config[col] = st.column_config.SelectboxColumn(
                label=col,
                options=dropdown_options[col],
                required=required_field
            )
        elif editor_type == "date":
            column_config[col] = st.column_config.DateColumn(
                label=col,
                format="DD/MM/YYYY"
            )
        elif editor_type == "datetime":
            column_config[col] = st.column_config.DatetimeColumn(
                label=col,
                format="DD/MM/YYYY HH:mm"
            )
        elif editor_type == "numeric":
            column_config[col] = st.column_config.NumberColumn(
                label=col
            )

    return column_config
 
 
 
#Função utilizada para coletar os dados chaves referente a alterações simples para cada stage
def get_reverse_mapping():
    column_mapping = get_column_mapping()
    return {v: k for k, v in column_mapping.items()}