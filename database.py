## database.py

import os
import streamlit as st
from sqlalchemy import create_engine, text
import pandas as pd
from shipments_mapping import get_column_mapping
from datetime import datetime
from shipments_mapping import get_reverse_mapping
import uuid
 
# Data e hora atuais
now = datetime.now()
 
# Configurações do banco de dados (podem ser sobrescritas por variáveis de ambiente)
DB_CONFIG = {
    "host": os.getenv("LOGTRANSP_DB_HOST", "127.0.0.1"),
    "port": os.getenv("LOGTRANSP_DB_PORT", "1521"),
    "name": os.getenv("LOGTRANSP_DB_NAME", "ORCLPDB1"),
    "user": os.getenv("LOGTRANSP_DB_USER", "LOGTRANSP"),
    "password": os.getenv("LOGTRANSP_DB_PASSWORD", "40012330"),
}

# Engine único reutilizável com pre-ping
ENGINE = create_engine(
    f'oracle+oracledb://{DB_CONFIG["user"]}:{DB_CONFIG["password"]}@{DB_CONFIG["host"]}:{DB_CONFIG["port"]}/?service_name={DB_CONFIG["name"]}',
    pool_pre_ping=True,
)

def get_database_connection():
    """Cria e retorna a conexão com o banco de dados (conn deve ser fechado pelo chamador)."""
    return ENGINE.connect()

# --- RETURN CARRIERS ---
def get_return_carriers_by_farol(farol_reference: str) -> pd.DataFrame:
    """Busca dados da F_CON_RETURN_CARRIERS por Farol Reference."""
    conn = get_database_connection()
    try:
        query = text(
            """
            SELECT 
                ID,
                FAROL_REFERENCE,
                B_BOOKING_REFERENCE,
                ADJUSTMENT_ID,
                Linked_Reference,
                B_BOOKING_STATUS,
                P_STATUS,
                P_PDF_NAME,
                S_SPLITTED_BOOKING_REFERENCE,
                S_PLACE_OF_RECEIPT,
                S_QUANTITY_OF_CONTAINERS,
                S_PORT_OF_LOADING_POL,
                S_PORT_OF_DELIVERY_POD,
                S_FINAL_DESTINATION,
                B_TRANSHIPMENT_PORT,
                B_PORT_TERMINAL_CITY,
                B_VESSEL_NAME,
                B_VOYAGE_CARRIER,
                B_VOYAGE_CODE,
                B_DOCUMENT_CUT_OFF_DOCCUT,
                B_PORT_CUT_OFF_PORTCUT,
                B_ESTIMATED_TIME_OF_DEPARTURE_ETD,
                B_ESTIMATED_TIME_OF_ARRIVAL_ETA,
                B_GATE_OPENING,
                USER_INSERT,
                USER_UPDATE,
                DATE_UPDATE,
                ROW_INSERTED_DATE
            FROM LogTransp.F_CON_RETURN_CARRIERS
            WHERE UPPER(FAROL_REFERENCE) = UPPER(:ref)
               OR UPPER(FAROL_REFERENCE) LIKE UPPER(:ref || '.%')
            ORDER BY ROW_INSERTED_DATE DESC
            """
        )
        rows = conn.execute(query, {"ref": farol_reference}).mappings().fetchall()
        df = pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()
        if not df.empty:
            df.columns = [str(c).upper() for c in df.columns]
        return df
    finally:
        conn.close()

def get_return_carriers_recent(limit: int = 200) -> pd.DataFrame:
    """Busca os últimos registros inseridos em F_CON_RETURN_CARRIERS."""
    conn = get_database_connection()
    try:
        query = f"""
            SELECT 
                ID,
                FAROL_REFERENCE,
                B_BOOKING_REFERENCE,
                ADJUSTMENT_ID,
                Linked_Reference,
                B_BOOKING_STATUS,
                P_STATUS,
                P_PDF_NAME,
                S_SPLITTED_BOOKING_REFERENCE,
                S_PLACE_OF_RECEIPT,
                S_QUANTITY_OF_CONTAINERS,
                S_PORT_OF_LOADING_POL,
                S_PORT_OF_DELIVERY_POD,
                S_FINAL_DESTINATION,
                B_TRANSHIPMENT_PORT,
                B_PORT_TERMINAL_CITY,
                B_VESSEL_NAME,
                B_VOYAGE_CARRIER,
                B_VOYAGE_CODE,
                B_DOCUMENT_CUT_OFF_DOCCUT,
                B_PORT_CUT_OFF_PORTCUT,
                B_ESTIMATED_TIME_OF_DEPARTURE_ETD,
                B_ESTIMATED_TIME_OF_ARRIVAL_ETA,
                B_GATE_OPENING,
                USER_INSERT,
                USER_UPDATE,
                DATE_UPDATE,
                ROW_INSERTED_DATE
            FROM LogTransp.F_CON_RETURN_CARRIERS
            ORDER BY ROW_INSERTED_DATE DESC
            FETCH FIRST {int(limit)} ROWS ONLY
        """
        rows = conn.execute(text(query)).mappings().fetchall()
        df = pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()
        if not df.empty:
            df.columns = [str(c).upper() for c in df.columns]
        return df
    finally:
        conn.close()
 
#Obter os dados das tabelas principais Sales
#@st.cache_data(ttl=300)
def get_data_salesData():
    """Executa a consulta SQL, aplica o mapeamento de colunas e retorna um DataFrame formatado."""
    conn = None
 
    # Consulta SQL (tabela unificada) com aliases para manter compatibilidade
    query = '''
    SELECT 
        FAROL_REFERENCE                    AS s_farol_reference,
        FAROL_STATUS                       AS s_farol_status,
        S_SHIPMENT_STATUS                  AS s_shipment_status,
        S_TYPE_OF_SHIPMENT                 AS s_type_of_shipment,
        S_CREATION_OF_SHIPMENT             AS s_creation_of_shipment,
        S_CUSTOMER_PO                      AS s_customer_po,
        S_SALE_ORDER_REFERENCE             AS s_sales_order_reference,
        S_SALE_ORDER_DATE                  AS s_sales_order_date,
        S_BUSINESS                         AS s_business,
        S_CUSTOMER                         AS s_customer,
        S_MODE                             AS s_mode,
        S_INCOTERM                         AS s_incoterm,
        S_SKU                              AS s_sku,
        S_PLANT_OF_ORIGIN                  AS s_plant_of_origin,
        S_SPLITTED_BOOKING_REFERENCE       AS s_splitted_booking_reference,
        S_VOLUME_IN_TONS                   AS s_volume_in_tons,
        S_QUANTITY_OF_CONTAINERS           AS s_quantity_of_containers,
        S_CONTAINER_TYPE                   AS s_container_type,
        S_PORT_OF_LOADING_POL              AS s_port_of_loading_pol,
        S_PORT_OF_DELIVERY_POD             AS s_port_of_delivery_pod,
        S_PLACE_OF_RECEIPT                 AS s_place_of_receipt,
        S_FINAL_DESTINATION                AS s_final_destination,
        S_REQUESTED_SHIPMENT_WEEK          AS s_requested_shipment_week,
        S_DTHC_PREPAID                     AS s_dthc_prepaid,
        S_AFLOAT                           AS s_afloat,
        S_SHIPMENT_PERIOD_START_DATE       AS s_shipment_period_start_date,
        S_SHIPMENT_PERIOD_END_DATE         AS s_shipment_period_end_date,
        S_REQUIRED_ARRIVAL_DATE            AS s_required_arrival_date,
        S_REQUESTED_DEADLINE_START_DATE    AS s_requested_deadlines_start_date,
        S_REQUESTED_DEADLINE_END_DATE      AS s_requested_deadlines_end_date,
        S_PARTIAL_ALLOWED                  AS s_partial_allowed,
        S_VIP_PNL_RISK                     AS s_vip_pnl_risk,
        S_PNL_DESTINATION                  AS s_pnl_destination,
        S_LC_RECEIVED                      AS s_lc_received,
        S_ALLOCATION_DATE                  AS s_allocation_date,
        S_PRODUCER_NOMINATION_DATE         AS s_producer_nomination_date,
        S_SALE_OWNER                       AS s_sales_owner,
        S_COMMENTS                         AS s_comments
    FROM LogTransp.F_CON_SALES_BOOKING_DATA
    ORDER BY FAROL_REFERENCE'''
 
    try:
        conn = get_database_connection()
        df = pd.read_sql_query(text(query), conn)

        print(df)
 
        # Aplicar o mapeamento de colunas antes de retornar os dados
        column_mapping = get_column_mapping()
        df.rename(columns=column_mapping, inplace=True)

        print(df)
        
        #Filtrando as colunas e definindo a ordem de exibição (alinhada entre ratios)
        df = df[[
            # Identificação
            "Sales Farol Reference", "Splitted Booking Reference", "Farol Status", "Type of Shipment", "Shipment Status",
            # Capacidade
            "Sales Quantity of Containers", "Container Type",
            # Rotas (unificado)
            "Port of Loading POL", "Port of Delivery POD", "Place of Receipt", "Final Destination",
            # Datas
            "Creation Of Shipment", "Requested Shipment Week", "Requested Deadline Start Date", "Requested Deadline End Date",
            "Shipment Period Start Date", "Shipment Period End Date", "Required Arrival Date",
            # Pedido e cliente
            "Sales Order Reference", "Sales Order Date", "Business", "Customer", "Mode", "SKU", "Plant of Origin",
            # Condições
            "Sales Incoterm", "DTHC", "Afloat", "VIP PNL Risk", "PNL Destination",
            # Administração
            "Allocation Date", "Producer Nomination Date", "LC Received", "Sales Owner",
            # Observações
            "Comments Sales"
        ]]
 
        return df
    finally:
        if conn:
            conn.close()
 
 #Obter os dados das tabelas principais Booking
#@st.cache_data(ttl=300)
def get_data_bookingData():
    """Executa a consulta SQL, aplica o mapeamento de colunas e retorna um DataFrame formatado."""
    conn = None
 
    # Consulta SQL (tabela unificada) com aliases para manter compatibilidade
    query = '''
    SELECT 
        ID                                  AS b_id,
        FAROL_REFERENCE                      AS b_farol_reference,
        FAROL_STATUS                         AS b_farol_status,
        B_CREATION_OF_BOOKING                AS b_creation_of_booking,
        B_BOOKING_REFERENCE                  AS b_booking_reference,
        B_BOOKING_STATUS                     AS b_booking_status,
        B_BOOKING_OWNER                      AS b_booking_owner,
        B_VOYAGE_CARRIER                     AS b_voyage_carrier,
        B_FREIGHT_FORWARDER                  AS b_freight_forwarder,
        B_BOOKING_REQUEST_DATE               AS b_booking_request_date,
        B_BOOKING_CONFIRMATION_DATE          AS b_booking_confirmation_date,
        B_VESSEL_NAME                        AS b_vessel_name,
        B_VOYAGE_CODE                        AS b_voyage_code,
        B_PORT_TERMINAL_CITY                 AS b_port_terminal_city,
        S_PLACE_OF_RECEIPT                   AS b_place_of_receipt,
        S_FINAL_DESTINATION                  AS b_final_destination,
        B_TRANSHIPMENT_PORT                  AS b_transhipment_port,
        B_POD_COUNTRY                        AS b_pod_country,
        B_POD_COUNTRY_ACRONYM                AS b_pod_country_acronym,
        B_DESTINATION_TRADE_REGION           AS b_destination_trade_region,
        /* Campos de cut-offs/ETAs/ETDs */
        B_DOCUMENT_CUT_OFF_DOCCUT            AS b_document_cut_off_doccut,
        B_PORT_CUT_OFF_PORTCUT               AS b_port_cut_off_portcut,
        B_ESTIMATED_TIME_OF_DEPARTURE_ETD    AS b_estimated_time_of_departure_etd,
        B_ESTIMATED_TIME_OF_ARRIVAL_ETA      AS b_estimated_time_of_arrival_eta,
        /* demais valores */
        B_FREIGHT_RATE_USD                   AS b_freight_rate_usd,
        B_BOGEY_SALE_PRICE_USD               AS b_bogey_sale_price_usd,
        B_FreightPpnl                        AS b_freightppnl,
        B_AWARD_STATUS                       AS b_award_status,
        B_COMMENTS                           AS b_comments,
        ADJUSTMENT_ID                        AS adjustment_id,
        /* Campos de Sales necessários para exibição no Booking */
        S_TYPE_OF_SHIPMENT                   AS s_type_of_shipment,
        S_QUANTITY_OF_CONTAINERS             AS s_quantity_of_containers,
        S_CONTAINER_TYPE                     AS s_container_type,
        S_PORT_OF_LOADING_POL                AS b_port_of_loading_pol,
        S_PORT_OF_DELIVERY_POD               AS b_port_of_delivery_pod
    FROM LogTransp.F_CON_SALES_BOOKING_DATA
    ORDER BY FAROL_REFERENCE'''
 
    try:
        conn = get_database_connection()
        df = pd.read_sql_query(text(query), conn)

        print(df.columns)
 
        # Aplicar o mapeamento de colunas antes de retornar os dados
        column_mapping = get_column_mapping()
        df.rename(columns=column_mapping, inplace=True)
 
        #Filtrando as colunas e definindo a ordem de exibição (alinhada entre ratios)
        df = df[[
            # Identificação
            "Booking Farol Reference", "Farol Status", "Type of Shipment", "Booking Status", "Booking Reference",
            # Capacidade
            "Sales Quantity of Containers", "Container Type",
            # Rotas (unificado)
            "Port of Loading POL", "Port of Delivery POD", "Place of Receipt", "Final Destination",
            # Datas de planejamento
            "Creation Of Booking", "Booking Request Date", "Booking Confirmation Date",
            "Document Cut Off DOCCUT", "Port Cut Off PORTCUT", "Estimated Time Of Departure ETD", "Estimated Time Of Arrival ETA",
            # Armador/viagem
            "Voyage Carrier", "Freight Forwarder", "Vessel Name", "Voyage Code", "Port Terminal City", "Transhipment Port", "POD Country", "POD Country Acronym", "Destination Trade Region",
            # Financeiro
            "Freight Rate USD", "Bogey Sale Price USD", "Freight PNL",
            # Administração
            "Booking Owner",
            # Observações
            "Comments Booking"
        ]]
 
        return df
    finally:
        if conn:
            conn.close()
 
 #Obter os dados das tabelas principais Loading
#@st.cache_data(ttl=300)
def get_data_loadingData():
    """Executa a consulta SQL, aplica o mapeamento de colunas e retorna um DataFrame formatado."""
    conn = None
 
    # Consulta SQL com JOIN para trazer campos do Sales (a partir da tabela unificada)
    query = '''
    SELECT l.*, 
           s.S_TYPE_OF_SHIPMENT         AS s_type_of_shipment,
           s.S_QUANTITY_OF_CONTAINERS   AS s_quantity_of_containers,
           s.S_CONTAINER_TYPE           AS s_container_type,
           s.S_PORT_OF_LOADING_POL      AS s_port_of_loading_pol,
           s.S_PORT_OF_DELIVERY_POD     AS s_port_of_delivery_pod
    FROM LogTransp.F_CON_CARGO_LOADING_CONTAINER_RELEASE l
    LEFT JOIN LogTransp.F_CON_SALES_BOOKING_DATA s ON l.l_farol_reference = s.farol_reference
    ORDER BY l.l_farol_reference'''
 
    try:
        conn = get_database_connection()
        df = pd.read_sql_query(text(query), conn)
 
        # Aplicar o mapeamento de colunas antes de retornar os dados
        column_mapping = get_column_mapping()
        df.rename(columns=column_mapping, inplace=True)
 
        #Filtrando as colunas e definindo a ordem de exibição
        df = df[["Loading Farol Reference","Farol Status","Truck Loading Status", "Type of Shipment", "Sales Quantity of Containers", "Container Type", "Creation Of Cargo Loading", "Logistics Analyst", "Supplier",
            "Port of Loading POL", "Port of Delivery POD", "Stuffing Terminal", "Stuffing Terminal Acceptance", "Drayage Carrier", "Status ITAS", "Truck Loading Farol",
            "Expected Truck Load Start Date", "Expected Truck Load End Date",
            "Quantity Tons Loaded Origin", "Actual Truck Load Date", "Container Release Farol",
            "Expected Container Release Start Date", "Expected Container Release End Date",
            "Actual Container Release Date", "Quantity Containers Released",
            "Container Release Issue Responsibility", "Quantity Containers Released Different Shore",
            "Shore Container Release Different"]]
 
        return df
    finally:
        if conn:
            conn.close()

 
 
def fetch_shipments_data_sales():
    """Executa a consulta SQL, aplica o mapeamento de colunas e retorna um DataFrame formatado."""
    conn = None
 
    # Consulta SQL (tabela unificada) com aliases para manter compatibilidade
    query = '''
    SELECT 
        FAROL_REFERENCE                    AS s_farol_reference,
        FAROL_STATUS                       AS s_farol_status,
        S_SHIPMENT_STATUS                  AS s_shipment_status,
        S_TYPE_OF_SHIPMENT                 AS s_type_of_shipment,
        S_CREATION_OF_SHIPMENT             AS s_creation_of_shipment,
        S_CUSTOMER_PO                      AS s_customer_po,
        S_SALE_ORDER_REFERENCE             AS s_sales_order_reference,
        S_SALE_ORDER_DATE                  AS s_sales_order_date,
        S_BUSINESS                         AS s_business,
        S_CUSTOMER                         AS s_customer,
        S_MODE                             AS s_mode,
        S_INCOTERM                         AS s_incoterm,
        S_SKU                              AS s_sku,
        S_PLANT_OF_ORIGIN                  AS s_plant_of_origin,
        S_SPLITTED_BOOKING_REFERENCE       AS s_splitted_booking_reference,
        S_VOLUME_IN_TONS                   AS s_volume_in_tons,
        S_QUANTITY_OF_CONTAINERS           AS s_quantity_of_containers,
        S_CONTAINER_TYPE                   AS s_container_type,
        S_PORT_OF_LOADING_POL              AS s_port_of_loading_pol,
        S_PORT_OF_DELIVERY_POD             AS s_port_of_delivery_pod,
        S_PLACE_OF_RECEIPT                 AS s_place_of_receipt,
        S_FINAL_DESTINATION                AS s_final_destination,
        S_REQUESTED_SHIPMENT_WEEK          AS s_requested_shipment_week,
        S_DTHC_PREPAID                     AS s_dthc_prepaid,
        S_AFLOAT                           AS s_afloat,
        S_SHIPMENT_PERIOD_START_DATE       AS s_shipment_period_start_date,
        S_SHIPMENT_PERIOD_END_DATE         AS s_shipment_period_end_date,
        S_REQUIRED_ARRIVAL_DATE            AS s_required_arrival_date,
        S_REQUESTED_DEADLINE_START_DATE    AS s_requested_deadlines_start_date,
        S_REQUESTED_DEADLINE_END_DATE      AS s_requested_deadlines_end_date,
        S_PARTIAL_ALLOWED                  AS s_partial_allowed,
        S_VIP_PNL_RISK                     AS s_vip_pnl_risk,
        S_PNL_DESTINATION                  AS s_pnl_destination,
        S_LC_RECEIVED                      AS s_lc_received,
        S_ALLOCATION_DATE                  AS s_allocation_date,
        S_PRODUCER_NOMINATION_DATE         AS s_producer_nomination_date,
        S_SALE_OWNER                       AS s_sales_owner,
        S_COMMENTS                         AS s_comments
    FROM LogTransp.F_CON_SALES_BOOKING_DATA
    ORDER BY FAROL_REFERENCE'''
 
    try:
        conn = get_database_connection()
        df = pd.read_sql_query(text(query), conn)
 
        # Aplicar o mapeamento de colunas antes de retornar os dados
        column_mapping = get_column_mapping()
        df.rename(columns=column_mapping, inplace=True)
 
        return df
    finally:
        if conn:
            conn.close()
 
 
           
### Obtendo os dados da UDC
@st.cache_data(ttl=300)  # Reduzir TTL para 5 minutos para debug
def load_df_udc():
    """Executa a consulta SQL, aplica o mapeamento de colunas e retorna um DataFrame formatado."""
    conn = None
 
    # Consulta SQL
    query = '''
    SELECT *
    FROM LogTransp.F_CON_Global_Variables'''
 
    try:
        conn = get_database_connection()
        df = pd.read_sql_query(text(query), conn)
 
        return df
    finally:
        if conn:
            conn.close()
 
def insert_adjustments_basics(changes_df, comment, random_uuid):
    """
    Insere os ajustes na tabela LogTransp.F_CON_Adjustments_Log.
    :param changes_df: DataFrame com as mudanças feitas pelo usuário.
    :param area: Valor do campo Adjustment Area.
    :param reason: Valor do campo Adjustment Request Reason.
    :param responsibility: Valor do campo Responsibility.
    :param comment: Valor do campo Comment.
    """
    if changes_df is None or changes_df.empty:
        return False
 
    conn = None
    try:
        conn = get_database_connection()
        transaction = conn.begin()
 
 
        # Preparar os dados para inserção
        data_to_insert = [
            {
                "farol_reference": row["Farol Reference"],
                "adjustment_id": random_uuid,
                "responsible_name": None,
                "area": None,
                "request_type": "Basic",
                "request_reason": None,
                "adjustments_owner": None,
                "column_name": row["Column"],
                "previous_value": row["Previous Value"],
                "new_value": row["New Value"],
                "request_carrier_date": None,
                "confirmation_date": None,
                "process_stage": None,
                "stage": row["Stage"],
                "comments": comment,
                "user_insert": None,
                "status": "Approved"
            }
            for _, row in changes_df.iterrows()
        ]
 
        # Query de inserção
        query = text("""
            INSERT INTO LogTransp.F_CON_Adjustments_Log (
                farol_reference, adjustment_id, responsible_name, area, request_type, request_reason, adjustments_owner, column_name,
                previous_value, new_value, request_carrier_date, confirmation_date, stage,
                comments, user_insert
 
            ) VALUES (
                :farol_reference, :adjustment_id, :responsible_name, :area, :request_type, :request_reason, :adjustments_owner, :column_name,
                :previous_value, :new_value, :request_carrier_date, :confirmation_date, :stage,
                :comments, :user_insert
            )
        """)
 
        # Executa inserção em lote
        conn.execute(query, data_to_insert)
        transaction.commit()
        return True
    except Exception as e:
        if conn:
            transaction.rollback()
        print(f"Erro ao inserir ajustes no banco de dados: {e}")
        return False
    finally:
        if conn:
            conn.close()
 
def insert_adjustments_critic(changes_df, comment, random_uuid, area, reason, responsibility, user_insert=None):
    if changes_df is None or changes_df.empty:
        return False

    from datetime import datetime
    conn = None
    try:
        conn = get_database_connection()
        transaction = conn.begin()

        now = datetime.now()
        data_to_insert = [
            {
                "farol_reference": row["Farol Reference"],
                "adjustment_id": random_uuid,
                "responsible_name": None,
                "area": area,
                "request_type": "Critic",
                "request_reason": reason,
                "adjustments_owner": responsibility,
                "column_name": row["Coluna"],
                "previous_value": row["Valor Anterior"],
                "new_value": row["Novo Valor"],
                "request_carrier_date": None,
                "confirmation_date": None,
                "stage": row["Stage"],
                "comments": comment,
                "user_insert": user_insert,
                "row_inserted_date": now
            }
            for _, row in changes_df.iterrows()
        ]

        insert_query = text("""
            INSERT INTO LogTransp.F_CON_Adjustments_Log (
                farol_reference, adjustment_id, responsible_name, area, request_type, request_reason, adjustments_owner, column_name,
                previous_value, new_value, request_carrier_date, confirmation_date, stage,
                comments, user_insert, row_inserted_date
            ) VALUES (
                :farol_reference, :adjustment_id, :responsible_name, :area, :request_type, :request_reason, :adjustments_owner, :column_name,
                :previous_value, :new_value, :request_carrier_date, :confirmation_date, :stage,
                :comments, :user_insert, :row_inserted_date
            )
        """)
        conn.execute(insert_query, data_to_insert)

        farol_reference = changes_df.iloc[0]["Farol Reference"]

        # Atualiza o Farol Status para "Adjustment Requested" na tabela unificada e na tabela de Loading
        update_unified_query = text("""
            UPDATE LogTransp.F_CON_SALES_BOOKING_DATA
            SET FAROL_STATUS = :farol_status
            WHERE FAROL_REFERENCE = :ref
        """)
        update_loading_query = text("""
            UPDATE LogTransp.F_CON_CARGO_LOADING_CONTAINER_RELEASE
            SET l_farol_status = :farol_status
            WHERE l_farol_reference = :ref
        """)

        conn.execute(update_unified_query, {
            "farol_status": "Adjustment Requested",
            "ref": farol_reference
        })
        conn.execute(update_loading_query, {
            "farol_status": "Adjustment Requested",
            "ref": farol_reference
        })

        transaction.commit()
        return True
    except Exception as e:
        if conn:
            transaction.rollback()
        st.error(f"Erro ao inserir ajustes críticos no banco de dados: {e}")
        return False

    finally:
        if conn:
            conn.close()
 
def insert_adjustments_critic_splits(changes_df, comment, random_uuid, area, reason, responsibility, user_insert=None):
    if changes_df is None or changes_df.empty:
        return False

    from datetime import datetime
    conn = None
    try:
        conn = get_database_connection()
        transaction = conn.begin()

        now = datetime.now()
        data_to_insert = [
            {
                "farol_reference": row["Farol Reference"],
                "adjustment_id": random_uuid,
                "responsible_name": None,
                "area": area,
                "request_type": "Critic",
                "request_reason": reason,
                "adjustments_owner": responsibility,
                "column_name": row["Coluna"],
                "previous_value": row["Valor Anterior"],
                "new_value": row["Novo Valor"],
                "request_carrier_date": None,
                "confirmation_date": None,
                "stage": row["Stage"],
                "comments": comment,
                "user_insert": user_insert,
                "row_inserted_date": now
            }
            for _, row in changes_df.iterrows()
        ]

        insert_query = text("""
            INSERT INTO LogTransp.F_CON_Adjustments_Log (
                farol_reference, adjustment_id, responsible_name, area, request_type, request_reason, adjustments_owner, column_name,
                previous_value, new_value, request_carrier_date, confirmation_date, stage,
                comments, user_insert, row_inserted_date
            ) VALUES (
                :farol_reference, :adjustment_id, :responsible_name, :area, :request_type, :request_reason, :adjustments_owner, :column_name,
                :previous_value, :new_value, :request_carrier_date, :confirmation_date, :stage,
                :comments, :user_insert, :row_inserted_date
            )
        """)
        conn.execute(insert_query, data_to_insert)

        transaction.commit()
        return True
    except Exception as e:
        if conn:
            transaction.rollback()
        st.error(f"Erro ao inserir ajustes críticos no banco de dados: {e}")
        return False
 
    finally:
        if conn:
            conn.close()
 
 
 
 
def add_sales_record(form_values):
    conn = None
    try:
        conn = get_database_connection()
        transaction = conn.begin()
 
        # Gerar farol reference
        farol_reference = generate_next_farol_reference()
        form_values["s_farol_reference"] = farol_reference
 
        # Campos padrão para tabela de vendas
        form_values["s_creation_of_shipment"] = datetime.now()
        form_values["s_business"] = "Cotton"
        form_values["s_customer_po"] = "Not used in the cotton business"
        form_values["s_mode"] = "Maritime"
        form_values["s_sku"] = "Cotton"
        form_values["s_plant_of_origin"] = "Not used in the cotton business"
        form_values["s_container_type"] = "40HC"
 
        # --- MAPA PARA TABELA UNIFICADA ---
        unified_map = {
            # chaves de entrada -> colunas unificadas
            "s_farol_reference": "FAROL_REFERENCE",
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
            "s_type_of_shipment": "S_TYPE_OF_SHIPMENT",
            "s_splitted_booking_reference": "S_SPLITTED_BOOKING_REFERENCE",
            "s_volume_in_tons": "S_VOLUME_IN_TONS",
            "s_quantity_of_containers": "S_QUANTITY_OF_CONTAINERS",
            "s_container_type": "S_CONTAINER_TYPE",
            "s_port_of_loading_pol": "S_PORT_OF_LOADING_POL",
            "s_port_of_delivery_pod": "S_PORT_OF_DELIVERY_POD",
            "s_place_of_receipt": "S_PLACE_OF_RECEIPT",
            "s_final_destination": "S_FINAL_DESTINATION",
            "s_requested_shipment_week": "S_REQUESTED_SHIPMENT_WEEK",
            "s_dthc_prepaid": "S_DTHC_PREPAID",
            "s_afloat": "S_AFLOAT",
            "s_shipment_period_start_date": "S_SHIPMENT_PERIOD_START_DATE",
            "s_shipment_period_end_date": "S_SHIPMENT_PERIOD_END_DATE",
            "s_required_arrival_date": "S_REQUIRED_ARRIVAL_DATE",
            "s_requested_deadlines_start_date": "S_REQUESTED_DEADLINE_START_DATE",
            "s_requested_deadlines_end_date": "S_REQUESTED_DEADLINE_END_DATE",
            "s_partial_allowed": "S_PARTIAL_ALLOWED",
            "s_vip_pnl_risk": "S_VIP_PNL_RISK",
            "s_pnl_destination": "S_PNL_DESTINATION",
            "s_lc_received": "S_LC_RECEIVED",
            "s_allocation_date": "S_ALLOCATION_DATE",
            "s_producer_nomination_date": "S_PRODUCER_NOMINATION_DATE",
            "s_sales_owner": "S_SALE_OWNER",
            "s_comments": "S_COMMENTS",
        }

        unified_values = {}
        for k, v in form_values.items():
            col = unified_map.get(k)
            if col:
                unified_values[col] = v
        # valores padrão
        unified_values.setdefault("FAROL_STATUS", "New Request")
        unified_values.setdefault("STAGE", "Sales Data")

        fields = ", ".join(unified_values.keys())
        placeholders = ", ".join([f":{key}" for key in unified_values.keys()])
        insert_query = text(f"""
            INSERT INTO LogTransp.F_CON_SALES_BOOKING_DATA ({fields})
            VALUES ({placeholders})
        """)
        conn.execute(insert_query, unified_values)
 
        # Removido: criação automática de booking e container release
        # Commit final
        transaction.commit()
        return True
 
    except Exception as e:
        if conn:
            transaction.rollback()
        st.error(f"Erro ao inserir no banco de dados: {e}")
        return False
    finally:
        if conn:
            conn.close()
 
 
 
 
 
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

    # Extrai apenas a parte sequencial
    def extract_seq(ref):
        try:
            parts = ref.split('_')
            if len(parts) > 1:
                seq_str = parts[-1].split('.')[0]  # Remove o número da versão se existir
                return int(seq_str)
            return 0
        except:
            return 0  # fallback seguro

    same_month_refs['SEQ'] = same_month_refs['Sales Farol Reference'].apply(extract_seq)

    # Encontra o maior SEQ
    max_seq = same_month_refs['SEQ'].max()
    next_seq = max_seq + 1

    return f'{prefix}_{next_seq:04d}'
 
 
#Adicionando os splits
def perform_split_operation(farol_ref_original, edited_display, num_splits, comment, area, reason, responsibility, user_insert=None, request_uuid=None):
    conn = get_database_connection()
    reverse_map = get_reverse_mapping()
    new_farol_references = []
 
    # Etapa 1: Consultar registros originais uma vez (unificada e loading)
    unified = pd.read_sql(text("SELECT * FROM LogTransp.F_CON_SALES_BOOKING_DATA WHERE FAROL_REFERENCE = :ref"), conn, params={"ref": farol_ref_original})
    loading = pd.read_sql(text("SELECT * FROM LogTransp.F_CON_CARGO_LOADING_CONTAINER_RELEASE WHERE l_farol_reference = :ref"), conn, params={"ref": farol_ref_original})
 
    insert_sales = []
    insert_booking = []
    insert_loading = []
    insert_unified = []
    insert_logs = []
 
    for i, (_, row) in enumerate(edited_display.iterrows()):
        if i == 0:
            continue  # pular linha original
 
        new_ref = row["Farol Reference"]
        new_farol_references.append(new_ref)
 
        # Copiar e modificar os dados
        unified_copy = unified.copy()
        loading_copy = loading.copy()
 
        for df, ref_key, prefix in [
            (unified_copy, "FAROL_REFERENCE", "Sales"),
            (loading_copy, reverse_map.get("Loading Farol Reference", "l_farol_reference"), "Loading"),
        ]:
            df.at[0, ref_key] = new_ref
            for ui_label, value in row.items():
                label = ui_label.replace("Sales", prefix)
                col = reverse_map.get(label)
                if col:
                    # Mapeia colunas de forma case-insensitive para corresponder aos nomes reais do DataFrame
                    actual_col = None
                    lower_target = col.lower()
                    for existing_col in df.columns:
                        if existing_col.lower() == lower_target:
                            actual_col = existing_col
                            break
                    if actual_col is not None:
                        df.at[0, actual_col] = value
 
        # Usa o UUID compartilhado se fornecido, caso contrário gera um novo
        adjustment_id = request_uuid if request_uuid else str(uuid.uuid4())
        # Atualiza apenas se a coluna existir
        if "ADJUSTMENT_ID" in unified_copy.columns:
            unified_copy.at[0, "ADJUSTMENT_ID"] = adjustment_id
        if "adjustment_id" in loading_copy.columns:
            loading_copy.at[0, "adjustment_id"] = adjustment_id
 
        # Atualiza apenas se as colunas existirem
        if "s_creation_of_shipment" in unified_copy.columns:
            unified_copy.at[0, "s_creation_of_shipment"] = datetime.now()
        if "s_type_of_shipment" in unified_copy.columns:
            unified_copy.at[0, "s_type_of_shipment"] = "Split"
        # Preenche referência da linha base usada para o split
        if "s_splitted_booking_reference" in unified_copy.columns:
            unified_copy.at[0, "s_splitted_booking_reference"] = farol_ref_original
        
        # Define o Farol Status como "Adjustment Requested" para os splits
        if "FAROL_STATUS" in unified_copy.columns:
            unified_copy.at[0, "FAROL_STATUS"] = "Adjustment Requested"
        if "l_farol_status" in loading_copy.columns:
            loading_copy.at[0, "l_farol_status"] = "Adjustment Requested"
 
        # Cria dicionários limpos apenas com as colunas necessárias
        unified_dict = {}
        loading_dict = {}
        
        # Copia apenas as colunas necessárias para evitar duplicações
        for col in unified_copy.columns:
            if col not in ['ID']:  # Remove coluna ID
                unified_dict[col] = unified_copy.iloc[0][col]
        

        
        for col in loading_copy.columns:
            if col not in ['l_id']:  # Remove coluna l_id
                loading_dict[col] = loading_copy.iloc[0][col]

        # Garantia extra: define explicitamente o campo de referência do split
        # para evitar qualquer perda durante o mapeamento
        unified_dict["S_SPLITTED_BOOKING_REFERENCE"] = farol_ref_original
 
        insert_sales = []  # não usamos mais, mantido para compatibilidade do fluxo
        insert_booking = []
        insert_unified.append(unified_dict)
        insert_loading.append(loading_dict)
 
        # Captura do valor de containers do split
        quantity_value = row.get("Sales Quantity of Containers", "")
 
        insert_logs.append(pd.DataFrame([{
            "Farol Reference": new_ref,
            "Coluna": "Split",
            "Valor Anterior": 0,
            "Novo Valor": str(quantity_value),
            "Status": "Pendente",
            "Stage": "Sales Data"
        }]))
 
    # Inserções em lote
    for data in insert_unified:
        insert_table("LogTransp.F_CON_SALES_BOOKING_DATA", data, conn)
    for data in insert_loading:
        insert_table("LogTransp.F_CON_CARGO_LOADING_CONTAINER_RELEASE", data, conn)
    for df, data in zip(insert_logs, insert_sales):
        insert_adjustments_critic_splits(df, comment, request_uuid if request_uuid else data.get("adjustment_id"), area, reason, responsibility, user_insert)
 
    # Atualiza o Farol Status da linha original para "Adjustment Requested"
    update_unified_original = text("""
        UPDATE LogTransp.F_CON_SALES_BOOKING_DATA
        SET FAROL_STATUS = :farol_status
        WHERE FAROL_REFERENCE = :ref
    """)
    update_loading_original = text("""
        UPDATE LogTransp.F_CON_CARGO_LOADING_CONTAINER_RELEASE
        SET l_farol_status = :farol_status
        WHERE l_farol_reference = :ref
    """)
 
    conn.execute(update_unified_original, {
        "farol_status": "Adjustment Requested",
        "ref": farol_ref_original
    })
    conn.execute(update_loading_original, {
        "farol_status": "Adjustment Requested",
        "ref": farol_ref_original
    })
 
    conn.commit()
    conn.close()
    return new_farol_references
 
 
 
def insert_table(full_table_name, row_dict, conn):
    """Insere um dicionário em uma tabela, normalizando nomes de colunas e tipos.

    - Remove chaves duplicadas por nome (case-insensitive), mantendo a última ocorrência em MAIÚSCULAS
    - Converte tipos não suportados pelo driver Oracle:
      * numpy.int64/float64/bool_ -> int/float/bool
      * pandas.Timestamp -> datetime
      * NaN/NaT -> None
    """
    cleaned = {}
    # Tenta importar numpy para checagem de tipos; segue sem np se não disponível
    try:
        import numpy as np  # type: ignore
    except Exception:  # pragma: no cover
        np = None  # type: ignore

    for k, v in row_dict.items():
        key = k.upper()
        val = v

        # Normaliza valores nulos do pandas (NaN/NaT)
        try:
            if not isinstance(val, (str, bytes)) and pd.isna(val):
                val = None
        except Exception:
            pass

        # Converte pandas.Timestamp -> datetime
        if isinstance(val, pd.Timestamp):
            val = val.to_pydatetime()

        # Converte numpy escalares para tipos nativos
        if 'np' in locals() and np is not None:
            if isinstance(val, (np.integer,)):
                val = int(val)
            elif isinstance(val, (np.floating,)):
                val = float(val)
            elif isinstance(val, (np.bool_,)):
                val = bool(val)
        # Fallback genérico para objetos com .item()
        if hasattr(val, "item") and not isinstance(val, (bytes, bytearray)):
            try:
                val = val.item()
            except Exception:
                pass

        # Mantém apenas uma ocorrência por coluna (em maiúsculas)
        cleaned[key] = val

    cols = ", ".join(cleaned.keys())
    vals = ", ".join([f":{key}" for key in cleaned.keys()])
    sql = f"INSERT INTO {full_table_name} ({cols}) VALUES ({vals})"
    conn.execute(text(sql), cleaned)
 
 
 
# --- CONSULTA UNIFICADA ---
def get_merged_data():
    query = """
    SELECT 
        farol_reference,
        adjustment_id,
        responsible_name,
        area,
        request_type,
        request_reason,
        adjustments_owner,
        column_name,
        previous_value,
        new_value,
        status,
        request_carrier_date,
        confirmation_date,
        row_inserted_date,
        comments,
        stage
    FROM LogTransp.F_CON_Adjustments_Log
    WHERE request_type = 'Critic'
    ORDER BY row_inserted_date DESC
    """

    with get_database_connection() as conn:
        df = pd.read_sql_query(text(query), conn)
        return df
   
 
#Função utilizada para preencher os dados no formulário para a referência selecionada
def get_booking_data_by_farol_reference(farol_reference): #Utilizada no arquivo booking_new.py
    conn = get_database_connection()
    try:
        query = """
        SELECT 
            B_BOOKING_STATUS      AS b_booking_status,
            B_VOYAGE_CARRIER      AS b_voyage_carrier,
            B_FREIGHT_FORWARDER   AS b_freight_forwarder,
            B_BOOKING_REQUEST_DATE AS b_booking_request_date,
            B_COMMENTS            AS b_comments,
            -- Pré-preenchimento (campos de Sales na unificada)
            S_DTHC_PREPAID                    AS dthc,
            S_REQUESTED_SHIPMENT_WEEK         AS requested_shipment_week,
            S_QUANTITY_OF_CONTAINERS          AS sales_quantity_of_containers,
            S_REQUESTED_DEADLINE_START_DATE   AS requested_cut_off_start_date,
            S_REQUESTED_DEADLINE_END_DATE     AS requested_cut_off_end_date,
            S_PORT_OF_LOADING_POL             AS booking_port_of_loading_pol,
            S_PORT_OF_DELIVERY_POD            AS booking_port_of_delivery_pod,
            S_FINAL_DESTINATION               AS final_destination
        FROM LogTransp.F_CON_SALES_BOOKING_DATA
        WHERE FAROL_REFERENCE = :ref
        """
        result = conn.execute(text(query), {"ref": farol_reference}).mappings().fetchone()
        return result if result else None
    finally:
        conn.close()
 
#Função utilizada para atualizar os dados da tabela de booking
def update_booking_data_by_farol_reference(farol_reference, values):#Utilizada no arquivo booking_new.py
    from datetime import datetime
    # Garante que loading exista
    insert_container_release_if_not_exists(farol_reference, {
        "l_farol_status": "Booking Requested"
    })
    conn = get_database_connection()
    try:
        query = """
        UPDATE LogTransp.F_CON_SALES_BOOKING_DATA
        SET FAROL_STATUS = :farol_status,
            B_VOYAGE_CARRIER = :b_voyage_carrier,
            B_CREATION_OF_BOOKING = :b_creation_of_booking,
            B_FREIGHT_FORWARDER = :b_freight_forwarder,
            B_BOOKING_REQUEST_DATE = :b_booking_request_date,
            B_COMMENTS = :b_comments,
            S_PORT_OF_LOADING_POL = :pol,
            S_PORT_OF_DELIVERY_POD = :pod
        WHERE FAROL_REFERENCE = :ref
        """
        # Atualiza a tabela de Loading
        query_loading = """
        UPDATE LogTransp.F_CON_CARGO_LOADING_CONTAINER_RELEASE
        SET l_farol_status = :farol_status
        WHERE l_farol_reference = :ref
        """
        # Executa ambas as queries
        conn.execute(
            text(query),
            {
                "farol_status": "Booking Requested", #values.get("b_booking_status", "Booking Requested")
                "b_creation_of_booking": datetime.now(),
                "b_voyage_carrier": values["b_voyage_carrier"],
                "b_freight_forwarder": values["b_freight_forwarder"],
                "b_booking_request_date": values["b_booking_request_date"],
                "b_comments": values["b_comments"],
                "pol": values.get("booking_port_of_loading_pol", ""),
                "pod": values.get("booking_port_of_delivery_pod", ""),
                "ref": farol_reference,
            },
        )
        conn.execute(
            text(query_loading),
            {
                "farol_status": "Booking Requested",
                "ref": farol_reference,
            },
        )
   
        conn.commit()
    finally:
        conn.close()
 
 
# Insere ou atualiza linha em F_CON_RETURN_CARRIERS com base na tabela unificada
def upsert_return_carrier_from_unified(farol_reference, user_insert=None):
    conn = get_database_connection()
    try:
        # Busca os dados atuais na tabela unificada
        fetch_sql = text(
            """
            SELECT 
                FAROL_REFERENCE,
                'Booking Requested' AS B_BOOKING_STATUS,
                NULL AS P_STATUS,
                NULL AS P_PDF_NAME,
                S_SPLITTED_BOOKING_REFERENCE,
                S_PLACE_OF_RECEIPT,
                S_QUANTITY_OF_CONTAINERS,
                S_PORT_OF_LOADING_POL,
                S_PORT_OF_DELIVERY_POD,
                S_FINAL_DESTINATION,
                B_TRANSHIPMENT_PORT,
                B_PORT_TERMINAL_CITY,
                B_VESSEL_NAME,
                B_VOYAGE_CARRIER,
                B_DOCUMENT_CUT_OFF_DOCCUT,
                B_PORT_CUT_OFF_PORTCUT,
                B_ESTIMATED_TIME_OF_DEPARTURE_ETD,
                B_ESTIMATED_TIME_OF_ARRIVAL_ETA,
                B_GATE_OPENING
            FROM LogTransp.F_CON_SALES_BOOKING_DATA
            WHERE FAROL_REFERENCE = :ref
            """
        )
        row = conn.execute(fetch_sql, {"ref": farol_reference}).mappings().fetchone()
        if not row:
            return

        # Verifica se já existe na tabela de retorno
        exists = conn.execute(
            text("SELECT COUNT(*) AS ct FROM LogTransp.F_CON_RETURN_CARRIERS WHERE FAROL_REFERENCE = :ref"),
            {"ref": farol_reference},
        ).fetchone()
        # Converte resultado para dicionário e normaliza chaves para MAIÚSCULAS
        row_dict = dict(row)
        data = {k.upper(): v for k, v in row_dict.items()}
        data["USER_INSERT"] = user_insert
        data["USER_UPDATE"] = None
        data["DATE_UPDATE"] = None

        if exists and int(exists[0]) > 0:
            # Atualiza
            update_sql = text(
                """
                UPDATE LogTransp.F_CON_RETURN_CARRIERS
                SET 
                    B_BOOKING_STATUS = :B_BOOKING_STATUS,
                    P_STATUS = :P_STATUS,
                    P_PDF_NAME = :P_PDF_NAME,
                    S_SPLITTED_BOOKING_REFERENCE = :S_SPLITTED_BOOKING_REFERENCE,
                    S_PLACE_OF_RECEIPT = :S_PLACE_OF_RECEIPT,
                    S_QUANTITY_OF_CONTAINERS = :S_QUANTITY_OF_CONTAINERS,
                    S_PORT_OF_LOADING_POL = :S_PORT_OF_LOADING_POL,
                    S_PORT_OF_DELIVERY_POD = :S_PORT_OF_DELIVERY_POD,
                    S_FINAL_DESTINATION = :S_FINAL_DESTINATION,
                    B_TRANSHIPMENT_PORT = :B_TRANSHIPMENT_PORT,
                    B_PORT_TERMINAL_CITY = :B_PORT_TERMINAL_CITY,
                    B_VESSEL_NAME = :B_VESSEL_NAME,
                    B_VOYAGE_CARRIER = :B_VOYAGE_CARRIER,
                    B_DOCUMENT_CUT_OFF_DOCCUT = :B_DOCUMENT_CUT_OFF_DOCCUT,
                    B_PORT_CUT_OFF_PORTCUT = :B_PORT_CUT_OFF_PORTCUT,
                    B_ESTIMATED_TIME_OF_DEPARTURE_ETD = :B_ESTIMATED_TIME_OF_DEPARTURE_ETD,
                    B_ESTIMATED_TIME_OF_ARRIVAL_ETA = :B_ESTIMATED_TIME_OF_ARRIVAL_ETA,
                    B_GATE_OPENING = :B_GATE_OPENING,
                    USER_UPDATE = :USER_INSERT,
                    DATE_UPDATE = SYSDATE
                WHERE FAROL_REFERENCE = :FAROL_REFERENCE
                """
            )
            # Nada a corrigir aqui além de garantir chaves MAIÚSCULAS
            conn.execute(update_sql, data)
        else:
            # Insere
            insert_sql = text(
                """
                INSERT INTO LogTransp.F_CON_RETURN_CARRIERS (
                    FAROL_REFERENCE,
                    B_BOOKING_STATUS,
                    P_STATUS,
                    P_PDF_NAME,
                    S_SPLITTED_BOOKING_REFERENCE,
                    S_PLACE_OF_RECEIPT,
                    S_QUANTITY_OF_CONTAINERS,
                    S_PORT_OF_LOADING_POL,
                    S_PORT_OF_DELIVERY_POD,
                    S_FINAL_DESTINATION,
                    B_TRANSHIPMENT_PORT,
                    B_PORT_TERMINAL_CITY,
                    B_VESSEL_NAME,
                    B_VOYAGE_CARRIER,
                    B_DOCUMENT_CUT_OFF_DOCCUT,
                    B_PORT_CUT_OFF_PORTCUT,
                    B_ESTIMATED_TIME_OF_DEPARTURE_ETD,
                    B_ESTIMATED_TIME_OF_ARRIVAL_ETA,
                    B_GATE_OPENING,
                    USER_INSERT,
                    ADJUSTMENT_ID
                ) VALUES (
                    :FAROL_REFERENCE,
                    :B_BOOKING_STATUS,
                    :P_STATUS,
                    :P_PDF_NAME,
                    :S_SPLITTED_BOOKING_REFERENCE,
                    :S_PLACE_OF_RECEIPT,
                    :S_QUANTITY_OF_CONTAINERS,
                    :S_PORT_OF_LOADING_POL,
                    :S_PORT_OF_DELIVERY_POD,
                    :S_FINAL_DESTINATION,
                    :B_TRANSHIPMENT_PORT,
                    :B_PORT_TERMINAL_CITY,
                    :B_VESSEL_NAME,
                    :B_VOYAGE_CARRIER,
                    :B_DOCUMENT_CUT_OFF_DOCCUT,
                    :B_PORT_CUT_OFF_PORTCUT,
                    :B_ESTIMATED_TIME_OF_DEPARTURE_ETD,
                    :B_ESTIMATED_TIME_OF_ARRIVAL_ETA,
                    :B_GATE_OPENING,
                    :USER_INSERT,
                    :ADJUSTMENT_ID
                )
                """
            )
            data["ADJUSTMENT_ID"] = str(uuid.uuid4())
            conn.execute(insert_sql, data)
        conn.commit()
    finally:
        conn.close()


# Insere SEM verificar existência (snapshot) em F_CON_RETURN_CARRIERS baseado na unificada
def insert_return_carrier_snapshot(farol_reference: str, status_override: str | None = None, user_insert: str | None = None):
    conn = get_database_connection()
    try:
        # Busca dados atuais
        fetch_sql = text(
            """
            SELECT 
                FAROL_REFERENCE,
                FAROL_STATUS,
                S_SPLITTED_BOOKING_REFERENCE,
                S_PLACE_OF_RECEIPT,
                S_QUANTITY_OF_CONTAINERS,
                S_PORT_OF_LOADING_POL,
                S_PORT_OF_DELIVERY_POD,
                S_FINAL_DESTINATION,
                B_TRANSHIPMENT_PORT,
                B_PORT_TERMINAL_CITY,
                B_VESSEL_NAME,
                B_VOYAGE_CARRIER,
                B_DOCUMENT_CUT_OFF_DOCCUT,
                B_PORT_CUT_OFF_PORTCUT,
                B_ESTIMATED_TIME_OF_DEPARTURE_ETD,
                B_ESTIMATED_TIME_OF_ARRIVAL_ETA,
                B_GATE_OPENING
            FROM LogTransp.F_CON_SALES_BOOKING_DATA
            WHERE FAROL_REFERENCE = :ref
            """
        )
        row = conn.execute(fetch_sql, {"ref": farol_reference}).mappings().fetchone()
        if not row:
            return

        rd = {k.upper(): v for k, v in dict(row).items()}
        # Determina status a ser gravado
        b_status = status_override if status_override else rd.get("FAROL_STATUS") or "Adjustment Requested"

        insert_sql = text(
            """
            INSERT INTO LogTransp.F_CON_RETURN_CARRIERS (
                FAROL_REFERENCE,
                B_BOOKING_STATUS,
                P_STATUS,
                P_PDF_NAME,
                S_SPLITTED_BOOKING_REFERENCE,
                S_PLACE_OF_RECEIPT,
                S_QUANTITY_OF_CONTAINERS,
                S_PORT_OF_LOADING_POL,
                S_PORT_OF_DELIVERY_POD,
                S_FINAL_DESTINATION,
                B_TRANSHIPMENT_PORT,
                B_PORT_TERMINAL_CITY,
                B_VESSEL_NAME,
                B_VOYAGE_CARRIER,
                B_DOCUMENT_CUT_OFF_DOCCUT,
                B_PORT_CUT_OFF_PORTCUT,
                B_ESTIMATED_TIME_OF_DEPARTURE_ETD,
                B_ESTIMATED_TIME_OF_ARRIVAL_ETA,
                B_GATE_OPENING,
                USER_INSERT,
                ADJUSTMENT_ID
            ) VALUES (
                :FAROL_REFERENCE,
                :B_BOOKING_STATUS,
                :P_STATUS,
                :P_PDF_NAME,
                :S_SPLITTED_BOOKING_REFERENCE,
                :S_PLACE_OF_RECEIPT,
                :S_QUANTITY_OF_CONTAINERS,
                :S_PORT_OF_LOADING_POL,
                :S_PORT_OF_DELIVERY_POD,
                :S_FINAL_DESTINATION,
                :B_TRANSHIPMENT_PORT,
                :B_PORT_TERMINAL_CITY,
                :B_VESSEL_NAME,
                :B_VOYAGE_CARRIER,
                :B_DOCUMENT_CUT_OFF_DOCCUT,
                :B_PORT_CUT_OFF_PORTCUT,
                :B_ESTIMATED_TIME_OF_DEPARTURE_ETD,
                :B_ESTIMATED_TIME_OF_ARRIVAL_ETA,
                :B_GATE_OPENING,
                :USER_INSERT,
                :ADJUSTMENT_ID
            )
            """
        )

        params = {
            "FAROL_REFERENCE": rd.get("FAROL_REFERENCE"),
            "B_BOOKING_STATUS": b_status,
            "P_STATUS": None,
            "P_PDF_NAME": None,
            "S_SPLITTED_BOOKING_REFERENCE": rd.get("S_SPLITTED_BOOKING_REFERENCE"),
            "S_PLACE_OF_RECEIPT": rd.get("S_PLACE_OF_RECEIPT"),
            "S_QUANTITY_OF_CONTAINERS": rd.get("S_QUANTITY_OF_CONTAINERS"),
            "S_PORT_OF_LOADING_POL": rd.get("S_PORT_OF_LOADING_POL"),
            "S_PORT_OF_DELIVERY_POD": rd.get("S_PORT_OF_DELIVERY_POD"),
            "S_FINAL_DESTINATION": rd.get("S_FINAL_DESTINATION"),
            "B_TRANSHIPMENT_PORT": rd.get("B_TRANSHIPMENT_PORT"),
            "B_PORT_TERMINAL_CITY": rd.get("B_PORT_TERMINAL_CITY"),
            "B_VESSEL_NAME": rd.get("B_VESSEL_NAME"),
            "B_VOYAGE_CARRIER": rd.get("B_VOYAGE_CARRIER"),
            "B_DOCUMENT_CUT_OFF_DOCCUT": rd.get("B_DOCUMENT_CUT_OFF_DOCCUT"),
            "B_PORT_CUT_OFF_PORTCUT": rd.get("B_PORT_CUT_OFF_PORTCUT"),
            "B_ESTIMATED_TIME_OF_DEPARTURE_ETD": rd.get("B_ESTIMATED_TIME_OF_DEPARTURE_ETD"),
            "B_ESTIMATED_TIME_OF_ARRIVAL_ETA": rd.get("B_ESTIMATED_TIME_OF_ARRIVAL_ETA"),
            "B_GATE_OPENING": rd.get("B_GATE_OPENING"),
            "USER_INSERT": user_insert,
            "ADJUSTMENT_ID": str(uuid.uuid4()),
        }

        conn.execute(insert_sql, params)
        conn.commit()
    finally:
        conn.close()


# Insere uma linha em F_CON_RETURN_CARRIERS a partir dos valores editados na UI (split)
def insert_return_carrier_from_ui(ui_row: dict, user_insert: str | None = None, status_override: str | None = None):
    conn = get_database_connection()
    try:
        farol_reference = ui_row.get("Farol Reference")
        # Normalizações de tipos/valores
        def norm(val):
            try:
                import numpy as np  # type: ignore
            except Exception:
                np = None  # type: ignore
            try:
                import pandas as pd  # type: ignore
            except Exception:
                pd = None  # type: ignore
            # Trata NaN/NaT
            if pd is not None:
                try:
                    if not isinstance(val, (str, bytes)) and pd.isna(val):
                        return None
                except Exception:
                    pass
            # Converte numpy escalares
            if np is not None and isinstance(val, (getattr(np, 'integer', ()), getattr(np, 'floating', ()), getattr(np, 'bool_', ()))):
                try:
                    if isinstance(val, getattr(np, 'integer', ())):
                        return int(val)
                    if isinstance(val, getattr(np, 'floating', ())) and not (val != val):
                        return float(val)
                    if isinstance(val, getattr(np, 'bool_', ())) :
                        return bool(val)
                except Exception:
                    pass
            # Converte pandas.Timestamp
            if hasattr(val, 'to_pydatetime'):
                try:
                    return val.to_pydatetime()
                except Exception:
                    pass
            # Fallback .item()
            if hasattr(val, 'item') and not isinstance(val, (bytes, bytearray)):
                try:
                    return val.item()
                except Exception:
                    pass
            return val

        def convert_date_string(date_str):
            """Converte string de data YYYY-MM-DD para datetime"""
            if not date_str or date_str == "":
                return None
            try:
                from datetime import datetime
                # Converte string YYYY-MM-DD para datetime
                return datetime.strptime(date_str, "%Y-%m-%d")
            except:
                return None

        qty_raw = ui_row.get("Quantity of Containers")
        if qty_raw is None:
            qty_raw = ui_row.get("Sales Quantity of Containers")
        try:
            qty = int(qty_raw) if qty_raw is not None and str(qty_raw) != "" else None
        except Exception:
            qty = None

        # Determina se é um split ou linha original
        # Split tem formato: FR_25.08_0001.1, FR_25.08_0001.2, etc.
        # Referência base tem formato: FR_25.08_0001
        # Identifica se é split verificando se o último ponto é seguido por números
        import re
        split_pattern = r'^(.+)\.(\d+)$'  # Padrão: qualquer coisa + ponto + números
        match = re.match(split_pattern, farol_reference)
        
        if match:
            # É um split - extrai a referência base
            base_reference = match.group(1)  # Primeira parte (antes do último ponto)
            splitted_booking_ref = base_reference
        else:
            # Linha original - não tem referência de split
            splitted_booking_ref = None
        
        # Determina o status a ser usado
        booking_status = status_override if status_override else "Adjustment Requested"
        
        params = {
            "FAROL_REFERENCE": farol_reference,
            "B_BOOKING_REFERENCE": norm(ui_row.get("Booking Reference")),
            "ADJUSTMENT_ID": str(uuid.uuid4()),
            "B_BOOKING_STATUS": booking_status,
            "P_STATUS": None,
            "P_PDF_NAME": norm(ui_row.get("PDF Name")),
            "S_SPLITTED_BOOKING_REFERENCE": splitted_booking_ref,
            "S_PLACE_OF_RECEIPT": norm(ui_row.get("Place of Receipt")),
            "S_QUANTITY_OF_CONTAINERS": qty,
            "S_PORT_OF_LOADING_POL": norm(ui_row.get("Port of Loading POL")),
            "S_PORT_OF_DELIVERY_POD": norm(ui_row.get("Port of Delivery POD")),
            "S_FINAL_DESTINATION": norm(ui_row.get("Final Destination")),
            "B_TRANSHIPMENT_PORT": norm(ui_row.get("Transhipment Port")),
            "B_PORT_TERMINAL_CITY": norm(ui_row.get("Port Terminal City")),
            "B_VESSEL_NAME": norm(ui_row.get("Vessel Name")),
            "B_VOYAGE_CODE": norm(ui_row.get("Voyage Code")),
            "B_VOYAGE_CARRIER": norm(ui_row.get("Voyage Carrier")),
            "B_DOCUMENT_CUT_OFF_DOCCUT": convert_date_string(ui_row.get("Requested Deadline Start Date")),
            "B_PORT_CUT_OFF_PORTCUT": convert_date_string(ui_row.get("Requested Deadline End Date")),
            "B_ESTIMATED_TIME_OF_DEPARTURE_ETD": convert_date_string(ui_row.get("Requested Deadline Start Date")),  # ETD
            "B_ESTIMATED_TIME_OF_ARRIVAL_ETA": convert_date_string(ui_row.get("Required Arrival Date")),
            "B_GATE_OPENING": None,
            "USER_INSERT": user_insert,
        }

        insert_sql = text(
            """
            INSERT INTO LogTransp.F_CON_RETURN_CARRIERS (
                FAROL_REFERENCE,
                B_BOOKING_REFERENCE,
                ADJUSTMENT_ID,
                B_BOOKING_STATUS,
                P_STATUS,
                P_PDF_NAME,
                S_SPLITTED_BOOKING_REFERENCE,
                S_PLACE_OF_RECEIPT,
                S_QUANTITY_OF_CONTAINERS,
                S_PORT_OF_LOADING_POL,
                S_PORT_OF_DELIVERY_POD,
                S_FINAL_DESTINATION,
                B_TRANSHIPMENT_PORT,
                B_PORT_TERMINAL_CITY,
                B_VESSEL_NAME,
                B_VOYAGE_CODE,
                B_VOYAGE_CARRIER,
                B_DOCUMENT_CUT_OFF_DOCCUT,
                B_PORT_CUT_OFF_PORTCUT,
                B_ESTIMATED_TIME_OF_DEPARTURE_ETD,
                B_ESTIMATED_TIME_OF_ARRIVAL_ETA,
                B_GATE_OPENING,
                USER_INSERT
            ) VALUES (
                :FAROL_REFERENCE,
                :B_BOOKING_REFERENCE,
                :ADJUSTMENT_ID,
                :B_BOOKING_STATUS,
                :P_STATUS,
                :P_PDF_NAME,
                :S_SPLITTED_BOOKING_REFERENCE,
                :S_PLACE_OF_RECEIPT,
                :S_QUANTITY_OF_CONTAINERS,
                :S_PORT_OF_LOADING_POL,
                :S_PORT_OF_DELIVERY_POD,
                :S_FINAL_DESTINATION,
                :B_TRANSHIPMENT_PORT,
                :B_PORT_TERMINAL_CITY,
                :B_VESSEL_NAME,
                :B_VOYAGE_CODE,
                :B_VOYAGE_CARRIER,
                :B_DOCUMENT_CUT_OFF_DOCCUT,
                :B_PORT_CUT_OFF_PORTCUT,
                :B_ESTIMATED_TIME_OF_DEPARTURE_ETD,
                :B_ESTIMATED_TIME_OF_ARRIVAL_ETA,
                :B_GATE_OPENING,
                :USER_INSERT
            )
            """
        )
        conn.execute(insert_sql, params)
        conn.commit()
        return True  # Retorna True se chegou até aqui sem erro
    except Exception as e:
        conn.rollback()
        raise e  # Re-lança a exceção para ser capturada pela função chamadora
    finally:
        conn.close()

def get_actions_count_by_farol_reference():
    """
    Retorna um dicionário com o número de ações (registros) por FAROL_REFERENCE exato
    na tabela F_CON_RETURN_CARRIERS. A agregação por ramo (base ou split) será feita
    na camada da aplicação (shipments.py), permitindo:
      - Se ref é base (ex.: FR_25.08_0001): contar ele + todos os descendentes (FR_25.08_0001.*)
      - Se ref é split (ex.: FR_25.08_0001.1): contar ele + seus descendentes (FR_25.08_0001.1.*)
    """
    conn = get_database_connection()
    try:
        query = text("""
            SELECT FAROL_REFERENCE, COUNT(*) AS ACTION_COUNT
            FROM LogTransp.F_CON_RETURN_CARRIERS
            GROUP BY FAROL_REFERENCE
        """)
        result = conn.execute(query).fetchall()

        # Converte para dicionário: ref exata -> action_count
        actions_dict = {}
        for row in result:
            actions_dict[row[0]] = row[1]

        return actions_dict
    finally:
        conn.close()

#Função utilizada para preencher os dados no formulário para a referência selecionada
def get_split_data_by_farol_reference(farol_reference):
    """Executa a consulta SQL para obter dados específicos para splits."""
    conn = get_database_connection()
    try:
        query = """
        SELECT
            FAROL_REFERENCE                    AS s_farol_reference,
            S_QUANTITY_OF_CONTAINERS           AS s_quantity_of_containers,
            S_VOLUME_IN_TONS                   AS s_volume_in_tons,
            S_CUSTOMER                         AS s_customer,
            S_SALE_ORDER_REFERENCE             AS s_sales_order_reference,
            S_PORT_OF_LOADING_POL              AS s_port_of_loading_pol,
            S_PORT_OF_DELIVERY_POD             AS s_port_of_delivery_pod,
            S_PLACE_OF_RECEIPT                 AS s_place_of_receipt,
            S_FINAL_DESTINATION                AS s_final_destination,
            S_SHIPMENT_STATUS                  AS s_shipment_status,
            S_REQUESTED_DEADLINE_START_DATE    AS s_requested_deadlines_start_date,
            S_REQUESTED_DEADLINE_END_DATE      AS s_requested_deadlines_end_date,
            S_REQUIRED_ARRIVAL_DATE            AS s_required_arrival_date,
            B_VOYAGE_CARRIER                   AS s_carrier,
            B_VOYAGE_CODE                      AS b_voyage_code,
            B_TRANSHIPMENT_PORT                AS b_transhipment_port,
            B_PORT_TERMINAL_CITY               AS b_port_terminal_city,
            B_BOOKING_REFERENCE                AS b_booking_reference,
            B_VESSEL_NAME                      AS b_vessel_name
        FROM LogTransp.F_CON_SALES_BOOKING_DATA
        WHERE FAROL_REFERENCE = :ref
        """
        result = conn.execute(text(query), {"ref": farol_reference}).mappings().fetchone()
        return result if result else None
    finally:
        conn.close()
 
def insert_booking_if_not_exists(farol_reference, booking_data):
    conn = get_database_connection()
    try:
        # Verifica se já existe
        result = conn.execute(
            text("SELECT COUNT(*) as count FROM LogTransp.F_CON_BOOKING_MANAGEMENT WHERE b_farol_reference = :ref"),
            {"ref": farol_reference}
        ).fetchone()
        if result and result[0] == 0:
            # Insere novo registro
            booking_data["b_farol_reference"] = farol_reference
            booking_fields = ", ".join(booking_data.keys())
            booking_placeholders = ", ".join([f":{key}" for key in booking_data.keys()])
            booking_query = text(f"""
                INSERT INTO LogTransp.F_CON_BOOKING_MANAGEMENT ({booking_fields})
                VALUES ({booking_placeholders})
            """)
            conn.execute(booking_query, booking_data)
            conn.commit()
    finally:
        conn.close()

def insert_container_release_if_not_exists(farol_reference, container_data):
    conn = get_database_connection()
    try:
        # Verifica se já existe
        result = conn.execute(
            text("SELECT COUNT(*) as count FROM LogTransp.F_CON_CARGO_LOADING_CONTAINER_RELEASE WHERE l_farol_reference = :ref"),
            {"ref": farol_reference}
        ).fetchone()
        if result and result[0] == 0:
            # Insere novo registro
            container_data["l_farol_reference"] = farol_reference
            container_fields = ", ".join(container_data.keys())
            container_placeholders = ", ".join([f":{key}" for key in container_data.keys()])
            container_query = text(f"""
                INSERT INTO LogTransp.F_CON_CARGO_LOADING_CONTAINER_RELEASE ({container_fields})
                VALUES ({container_placeholders})
            """)
            conn.execute(container_query, container_data)
            conn.commit()
    finally:
        conn.close()

def get_return_carriers_by_adjustment_id(adjustment_id: str) -> pd.DataFrame:
    """Busca dados da F_CON_RETURN_CARRIERS por ADJUSTMENT_ID."""
    conn = get_database_connection()
    try:
        query = text(
            """
            SELECT 
                ID,
                FAROL_REFERENCE,
                B_BOOKING_REFERENCE,
                ADJUSTMENT_ID,
                Linked_Reference,
                B_BOOKING_STATUS,
                P_STATUS,
                P_PDF_NAME,
                S_SPLITTED_BOOKING_REFERENCE,
                S_PLACE_OF_RECEIPT,
                S_QUANTITY_OF_CONTAINERS,
                S_PORT_OF_LOADING_POL,
                S_PORT_OF_DELIVERY_POD,
                S_FINAL_DESTINATION,
                B_TRANSHIPMENT_PORT,
                B_PORT_TERMINAL_CITY,
                B_VESSEL_NAME,
                B_VOYAGE_CARRIER,
                B_VOYAGE_CODE,
                B_DOCUMENT_CUT_OFF_DOCCUT,
                B_PORT_CUT_OFF_PORTCUT,
                B_ESTIMATED_TIME_OF_DEPARTURE_ETD,
                B_ESTIMATED_TIME_OF_ARRIVAL_ETA,
                B_GATE_OPENING,
                USER_INSERT,
                USER_UPDATE,
                DATE_UPDATE,
                ROW_INSERTED_DATE
            FROM LogTransp.F_CON_RETURN_CARRIERS
            WHERE ADJUSTMENT_ID = :adjustment_id
            """
        )
        rows = conn.execute(query, {"adjustment_id": adjustment_id}).mappings().fetchall()
        df = pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()
        if not df.empty:
            df.columns = [str(c).upper() for c in df.columns]
        return df
    finally:
        conn.close()

def update_sales_booking_from_return_carriers(adjustment_id: str) -> bool:
    """
    Atualiza a tabela F_CON_SALES_BOOKING_DATA com os dados da linha aprovada
    da tabela F_CON_RETURN_CARRIERS, baseado no ADJUSTMENT_ID.
    
    :param adjustment_id: ID do ajuste aprovado
    :return: True se a atualização foi bem-sucedida, False caso contrário
    """
    conn = get_database_connection()
    try:
        # Busca os dados da linha aprovada
        return_carrier_data = get_return_carriers_by_adjustment_id(adjustment_id)
        print(f"DEBUG: get_return_carriers_by_adjustment_id({adjustment_id}) returned {len(return_carrier_data)} rows")
        if return_carrier_data.empty:
            print("DEBUG: return_carrier_data is empty")
            return False
        
        row = return_carrier_data.iloc[0]
        farol_reference = row.get("FAROL_REFERENCE")
        print(f"DEBUG: farol_reference={farol_reference}")
        print(f"DEBUG: row data keys: {list(row.keys())}")
        print(f"DEBUG: S_QUANTITY_OF_CONTAINERS value: '{row.get('S_QUANTITY_OF_CONTAINERS')}' (type: {type(row.get('S_QUANTITY_OF_CONTAINERS'))})")
        
        if not farol_reference:
            print("DEBUG: farol_reference is empty")
            return False
        
        # Prepara os campos para atualização (apenas valores não nulos/nem vazios)
        update_fields = {}

        def add_if_present(field_name):
            val = row.get(field_name)
            try:
                import pandas as _pd
                import numpy as np
                if val is None or (_pd.isna(val)):
                    return
                # Converte tipos numpy para tipos Python nativos para compatibilidade com Oracle
                if isinstance(val, np.integer):
                    val = int(val)
                elif isinstance(val, np.floating):
                    val = float(val)
                elif isinstance(val, np.bool_):
                    val = bool(val)
            except Exception:
                if val is None:
                    return
            # Normaliza strings vazias
            if isinstance(val, str) and val.strip() == "":
                return
            update_fields[field_name] = val

        # Campos S_ (Sales)
        add_if_present("S_SPLITTED_BOOKING_REFERENCE")
        add_if_present("S_PLACE_OF_RECEIPT")
        add_if_present("S_QUANTITY_OF_CONTAINERS")
        add_if_present("S_PORT_OF_LOADING_POL")
        add_if_present("S_PORT_OF_DELIVERY_POD")
        add_if_present("S_FINAL_DESTINATION")
        
        # Campos B_ (Booking)
        add_if_present("B_BOOKING_REFERENCE")
        add_if_present("B_TRANSHIPMENT_PORT")
        add_if_present("B_PORT_TERMINAL_CITY")
        add_if_present("B_VESSEL_NAME")
        add_if_present("B_VOYAGE_CODE")
        add_if_present("B_VOYAGE_CARRIER")
        add_if_present("B_DOCUMENT_CUT_OFF_DOCCUT")
        add_if_present("B_PORT_CUT_OFF_PORTCUT")
        add_if_present("B_ESTIMATED_TIME_OF_DEPARTURE_ETD")
        add_if_present("B_ESTIMATED_TIME_OF_ARRIVAL_ETA")
        add_if_present("B_GATE_OPENING")
        
        # Se não há campos para atualizar, retorna True (não é erro)
        if not update_fields:
            return True
        
        # Constrói a query de atualização dinamicamente
        set_clause = ", ".join([f"{field} = :{field}" for field in update_fields.keys()])
        update_query = text(f"""
            UPDATE LogTransp.F_CON_SALES_BOOKING_DATA
            SET {set_clause}
            WHERE FAROL_REFERENCE = :farol_reference
        """)
        
        # Adiciona o farol_reference aos parâmetros
        update_fields["farol_reference"] = farol_reference
        
        # Executa a atualização
        result = conn.execute(update_query, update_fields)
        conn.commit()
        # Log leve em console para depuração
        print(f"update_sales_booking_from_return_carriers: fields={list(update_fields.keys())}, rowcount={getattr(result,'rowcount',None)}, farol={farol_reference}")
        
        return getattr(result, "rowcount", 0) > 0
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        print(f"Erro ao atualizar F_CON_SALES_BOOKING_DATA: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def update_return_carrier_status(adjustment_id: str, new_status: str) -> bool:
    """
    Atualiza o status da linha na tabela F_CON_RETURN_CARRIERS.
    
    :param adjustment_id: ID do ajuste
    :param new_status: Novo status a ser definido
    :return: True se a atualização foi bem-sucedida, False caso contrário
    """
    conn = get_database_connection()
    try:
        update_query = text("""
            UPDATE LogTransp.F_CON_RETURN_CARRIERS
            SET B_BOOKING_STATUS = :new_status,
                USER_UPDATE = :user_update,
                DATE_UPDATE = SYSDATE
            WHERE ADJUSTMENT_ID = :adjustment_id
        """)
        
        result = conn.execute(update_query, {
            "new_status": new_status,
            "user_update": "System",  # Pode ser parametrizado se necessário
            "adjustment_id": adjustment_id
        })
        
        conn.commit()
        return (getattr(result, "rowcount", 0) > 0)
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
        print(f"Erro ao atualizar status em F_CON_RETURN_CARRIERS: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()


def get_current_status_from_main_table(farol_reference: str) -> str:
    """
    Busca o status atual da tabela principal F_CON_SALES_BOOKING_DATA
    usando o FAROL_REFERENCE
    """
    conn = get_database_connection()
    try:
        query = """
        SELECT FAROL_STATUS
        FROM LogTransp.F_CON_SALES_BOOKING_DATA
        WHERE FAROL_REFERENCE = :farol_reference
        """
        result = conn.execute(text(query), {"farol_reference": farol_reference}).scalar()
        return result if result else "Adjustment Requested"
    finally:
        conn.close()


def get_return_carrier_status_by_adjustment_id(adjustment_id: str):
    """Retorna o B_BOOKING_STATUS da F_CON_RETURN_CARRIERS para o ADJUSTMENT_ID dado."""
    conn = get_database_connection()
    try:
        query = text(
            """
            SELECT B_BOOKING_STATUS
            FROM LogTransp.F_CON_RETURN_CARRIERS
            WHERE ADJUSTMENT_ID = :adjustment_id
            """
        )
        result = conn.execute(query, {"adjustment_id": adjustment_id}).scalar()
        return result
    finally:
        conn.close()