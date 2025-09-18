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
                B_TERMINAL,
                B_VESSEL_NAME,
                B_VOYAGE_CARRIER,
                B_VOYAGE_CODE,
                B_DATA_DRAFT_DEADLINE,
                B_DATA_DEADLINE,
                S_REQUESTED_DEADLINE_START_DATE,
                S_REQUESTED_DEADLINE_END_DATE,
                S_REQUIRED_ARRIVAL_DATE_EXPECTED,
                B_DATA_ESTIMATIVA_SAIDA_ETD,
                B_DATA_ESTIMATIVA_CHEGADA_ETA,
                B_DATA_ABERTURA_GATE,
                USER_INSERT,
                USER_UPDATE,
                DATE_UPDATE,
                ROW_INSERTED_DATE,
                PDF_BOOKING_EMISSION_DATE
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
                B_TERMINAL,
                B_VESSEL_NAME,
                B_VOYAGE_CARRIER,
                B_VOYAGE_CODE,
                B_DATA_DRAFT_DEADLINE,
                B_DATA_DEADLINE,
                B_DATA_ESTIMATIVA_SAIDA_ETD,
                B_DATA_ESTIMATIVA_CHEGADA_ETA,
                B_DATA_ABERTURA_GATE,
                USER_INSERT,
                USER_UPDATE,
                DATE_UPDATE,
                ROW_INSERTED_DATE,
                PDF_BOOKING_EMISSION_DATE
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
            "Shipment Period Start Date", "Shipment Period End Date", "Required Arrival Date Expected",
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
        B_TERMINAL                           AS b_terminal,
        S_PLACE_OF_RECEIPT                   AS b_place_of_receipt,
        S_FINAL_DESTINATION                  AS b_final_destination,
        B_TRANSHIPMENT_PORT                  AS b_transhipment_port,
        B_POD_COUNTRY                        AS b_pod_country,
        B_POD_COUNTRY_ACRONYM                AS b_pod_country_acronym,
        B_DESTINATION_TRADE_REGION           AS b_destination_trade_region,
        /* Campos de cut-offs/ETAs/ETDs */
        B_DATA_DRAFT_DEADLINE                AS b_data_draft_deadline,
        B_DATA_DEADLINE                      AS b_data_deadline,
        B_DATA_ESTIMATIVA_SAIDA_ETD          AS b_data_estimativa_saida_etd,
        B_DATA_ESTIMATIVA_CHEGADA_ETA        AS b_data_estimativa_chegada_eta,
        B_DATA_ABERTURA_GATE                 AS b_data_abertura_gate,
        B_DATA_PARTIDA_ATD                   AS b_data_partida_atd,
        B_DATA_CHEGADA_ATA                   AS b_data_chegada_ata,
        B_DATA_ESTIMATIVA_ATRACACAO_ETB      AS b_data_estimativa_atracacao_etb,
        B_DATA_ATRACACAO_ATB                 AS b_data_atracacao_atb,
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
        
        # Converter colunas de data/hora para datetime
        datetime_columns = [
            'Data Draft Deadline', 'Data Deadline', 'Data Estimativa Saída ETD', 
            'Data Estimativa Chegada ETA', 'Data Abertura Gate', 'Data Partida ATD', 
            'Data Chegada ATA', 'Data Estimativa Atracação ETB', 'Data Atracação ATB'
        ]
        
        for col in datetime_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
 
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
            "Data Draft Deadline", "Data Deadline", "Data Estimativa Saída ETD", "Data Estimativa Chegada ETA", "Data Abertura Gate",
            "Data Partida ATD", "Data Chegada ATA", "Data Estimativa Atracação ETB", "Data Atracação ATB",
            # Armador/viagem
            "Voyage Carrier", "Freight Forwarder", "Vessel Name", "Voyage Code", "Terminal", "Transhipment Port", "POD Country", "POD Country Acronym", "Destination Trade Region",
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
        
        # Criar snapshot na tabela F_CON_RETURN_CARRIERS para manter as colunas de expectativa interna sincronizadas
        farol_reference = unified_values.get("FAROL_REFERENCE")
        if farol_reference:
            try:
                upsert_return_carrier_from_unified(farol_reference, user_insert=unified_values.get("USER_INSERT", "system"))
            except Exception as e:
                # Log do erro mas não falha toda a operação, pois o registro principal já foi criado
                print(f"Aviso: Erro ao criar snapshot em F_CON_RETURN_CARRIERS: {e}")
        
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
   
 
#Função utilizada para obter dados de split baseados no farol reference
def get_split_data_by_farol_reference(farol_reference):
    """Busca dados unificados da tabela F_CON_SALES_BOOKING_DATA para splits/adjustments."""
    conn = get_database_connection()
    try:
        query = """
        SELECT 
            FAROL_REFERENCE      AS s_farol_reference,
            S_QUANTITY_OF_CONTAINERS AS s_quantity_of_containers,
            S_PORT_OF_LOADING_POL AS s_port_of_loading_pol,
            S_PORT_OF_DELIVERY_POD AS s_port_of_delivery_pod,
            S_PLACE_OF_RECEIPT AS s_place_of_receipt,
            S_FINAL_DESTINATION AS s_final_destination,
            B_TRANSHIPMENT_PORT AS b_transhipment_port,
            B_TERMINAL AS b_terminal,
            B_VOYAGE_CARRIER AS s_carrier,
            B_VOYAGE_CODE AS b_voyage_code,
            B_BOOKING_REFERENCE AS b_booking_reference,
            B_VESSEL_NAME AS b_vessel_name,
            S_REQUESTED_DEADLINE_START_DATE AS s_requested_deadlines_start_date,
            S_REQUESTED_DEADLINE_END_DATE AS s_requested_deadlines_end_date,
            S_REQUIRED_ARRIVAL_DATE AS s_required_arrival_date
        FROM LogTransp.F_CON_SALES_BOOKING_DATA
        WHERE FAROL_REFERENCE = :ref
        """
        result = conn.execute(text(query), {"ref": farol_reference}).mappings().fetchone()
        return result if result else None
    finally:
        conn.close()

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
            S_REQUIRED_ARRIVAL_DATE           AS required_arrival_date,
            S_SHIPMENT_PERIOD_START_DATE      AS shipment_period_start_date,
            S_SHIPMENT_PERIOD_END_DATE        AS shipment_period_end_date,
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
 
def insert_container_release_if_not_exists(farol_reference, default_values=None):
    """Insere um registro na tabela F_CON_CARGO_LOADING_CONTAINER_RELEASE se não existir"""
    if default_values is None:
        default_values = {}
    
    conn = get_database_connection()
    try:
        # Verifica se já existe um registro para este Farol Reference
        check_query = text("""
            SELECT COUNT(*) as count 
            FROM LogTransp.F_CON_CARGO_LOADING_CONTAINER_RELEASE 
            WHERE l_farol_reference = :farol_reference
        """)
        
        result = conn.execute(check_query, {"farol_reference": farol_reference}).fetchone()
        
        if result[0] == 0:  # Se não existe, insere um novo registro
            # Valores padrão para inserção
            insert_data = {
                "l_farol_reference": farol_reference,
                "l_farol_status": default_values.get("l_farol_status", "Booking Requested"),
                "l_expected_container_release_start_date": None,
                "l_expected_container_release_end_date": None,
                "l_actual_container_release_date": None,
                "l_container_release_issue_responsibility": None,
                "l_shore_container_release_different": None,
                "l_container_release_farol": None
            }
            
            # Atualiza com valores fornecidos
            insert_data.update(default_values)
            
            # Insere o registro
            insert_table("LogTransp.F_CON_CARGO_LOADING_CONTAINER_RELEASE", insert_data, conn)
            
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
                'Booking Request - Company' AS P_STATUS,
                NULL AS P_PDF_NAME,
                S_SPLITTED_BOOKING_REFERENCE,
                S_PLACE_OF_RECEIPT,
                S_QUANTITY_OF_CONTAINERS,
                S_PORT_OF_LOADING_POL,
                S_PORT_OF_DELIVERY_POD,
                S_FINAL_DESTINATION,
                B_TRANSHIPMENT_PORT,
                B_TERMINAL,
                B_VESSEL_NAME,
                B_VOYAGE_CARRIER,
                B_DATA_DRAFT_DEADLINE,
                B_DATA_DEADLINE,
                S_REQUESTED_DEADLINE_START_DATE,
                S_REQUESTED_DEADLINE_END_DATE,
                B_DATA_ESTIMATIVA_SAIDA_ETD,
                B_DATA_ESTIMATIVA_CHEGADA_ETA,
                B_DATA_ABERTURA_GATE,
                B_DATA_PARTIDA_ATD,
                B_DATA_CHEGADA_ATA,
                B_DATA_ESTIMATIVA_ATRACACAO_ETB,
                B_DATA_ATRACACAO_ATB
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
        # Garante binds para novos campos mesmo quando não vierem do SELECT
        for k in (
            "B_DATA_PARTIDA_ATD",
            "B_DATA_CHEGADA_ATA",
            "B_DATA_ESTIMATIVA_ATRACACAO_ETB",
            "B_DATA_ATRACACAO_ATB",
        ):
            if k not in data:
                data[k] = None
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
                    B_TERMINAL = :B_TERMINAL,
                    B_VESSEL_NAME = :B_VESSEL_NAME,
                    B_VOYAGE_CARRIER = :B_VOYAGE_CARRIER,
                    B_DATA_DRAFT_DEADLINE = :B_DATA_DRAFT_DEADLINE,
                    B_DATA_DEADLINE = :B_DATA_DEADLINE,
                    S_REQUESTED_DEADLINE_START_DATE = :S_REQUESTED_DEADLINE_START_DATE,
                    S_REQUESTED_DEADLINE_END_DATE = :S_REQUESTED_DEADLINE_END_DATE,
                    B_DATA_ESTIMATIVA_SAIDA_ETD = :B_DATA_ESTIMATIVA_SAIDA_ETD,
                    B_DATA_ESTIMATIVA_CHEGADA_ETA = :B_DATA_ESTIMATIVA_CHEGADA_ETA,
                    B_DATA_ABERTURA_GATE = :B_DATA_ABERTURA_GATE,
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
                    B_TERMINAL,
                    B_VESSEL_NAME,
                    B_VOYAGE_CARRIER,
                    B_DATA_DRAFT_DEADLINE,
                    B_DATA_DEADLINE,
                    S_REQUESTED_DEADLINE_START_DATE,
                    S_REQUESTED_DEADLINE_END_DATE,
                    B_DATA_ESTIMATIVA_SAIDA_ETD,
                    B_DATA_ESTIMATIVA_CHEGADA_ETA,
                    B_DATA_ABERTURA_GATE,
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
                    :B_TERMINAL,
                    :B_VESSEL_NAME,
                    :B_VOYAGE_CARRIER,
                    :B_DATA_DRAFT_DEADLINE,
                    :B_DATA_DEADLINE,
                    :S_REQUESTED_DEADLINE_START_DATE,
                    :S_REQUESTED_DEADLINE_END_DATE,
                    :B_DATA_ESTIMATIVA_SAIDA_ETD,
                    :B_DATA_ESTIMATIVA_CHEGADA_ETA,
                    :B_DATA_ABERTURA_GATE,
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
                B_TERMINAL,
                B_VESSEL_NAME,
                B_VOYAGE_CARRIER,
                B_DATA_DRAFT_DEADLINE,
                B_DATA_DEADLINE,
                S_REQUESTED_DEADLINE_START_DATE,
                S_REQUESTED_DEADLINE_END_DATE,
                S_REQUIRED_ARRIVAL_DATE,
                B_DATA_ESTIMATIVA_SAIDA_ETD,
                B_DATA_ESTIMATIVA_CHEGADA_ETA,
                B_DATA_ABERTURA_GATE,
                B_DATA_PARTIDA_ATD,
                B_DATA_CHEGADA_ATA,
                B_DATA_ESTIMATIVA_ATRACACAO_ETB,
                B_DATA_ATRACACAO_ATB
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
                B_TERMINAL,
                B_VESSEL_NAME,
                B_VOYAGE_CARRIER,
                B_DATA_DRAFT_DEADLINE,
                B_DATA_DEADLINE,
                S_REQUESTED_DEADLINE_START_DATE,
                S_REQUESTED_DEADLINE_END_DATE,
                S_REQUIRED_ARRIVAL_DATE_EXPECTED,
                B_DATA_ESTIMATIVA_SAIDA_ETD,
                B_DATA_ESTIMATIVA_CHEGADA_ETA,
                B_DATA_ABERTURA_GATE,
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
                :B_TERMINAL,
                :B_VESSEL_NAME,
                :B_VOYAGE_CARRIER,
                :B_DATA_DRAFT_DEADLINE,
                :B_DATA_DEADLINE,
                :S_REQUESTED_DEADLINE_START_DATE,
                :S_REQUESTED_DEADLINE_END_DATE,
                :S_REQUIRED_ARRIVAL_DATE_EXPECTED,
                :B_DATA_ESTIMATIVA_SAIDA_ETD,
                :B_DATA_ESTIMATIVA_CHEGADA_ETA,
                :B_DATA_ABERTURA_GATE,
                :USER_INSERT,
                :ADJUSTMENT_ID
            )
            """
        )

        params = {
            "FAROL_REFERENCE": rd.get("FAROL_REFERENCE"),
            "B_BOOKING_STATUS": b_status,
            # Snapshot oriundo do carrier
            "P_STATUS": "Booking Request - Company",
            "P_PDF_NAME": None,
            "S_SPLITTED_BOOKING_REFERENCE": rd.get("S_SPLITTED_BOOKING_REFERENCE"),
            "S_PLACE_OF_RECEIPT": rd.get("S_PLACE_OF_RECEIPT"),
            "S_QUANTITY_OF_CONTAINERS": rd.get("S_QUANTITY_OF_CONTAINERS"),
            "S_PORT_OF_LOADING_POL": rd.get("S_PORT_OF_LOADING_POL"),
            "S_PORT_OF_DELIVERY_POD": rd.get("S_PORT_OF_DELIVERY_POD"),
            "S_FINAL_DESTINATION": rd.get("S_FINAL_DESTINATION"),
            "B_TRANSHIPMENT_PORT": rd.get("B_TRANSHIPMENT_PORT"),
            "B_TERMINAL": rd.get("B_TERMINAL"),
            "B_VESSEL_NAME": rd.get("B_VESSEL_NAME"),
            "B_VOYAGE_CARRIER": rd.get("B_VOYAGE_CARRIER"),
            "B_DATA_DRAFT_DEADLINE": rd.get("B_DATA_DRAFT_DEADLINE"),
            "B_DATA_DEADLINE": rd.get("B_DATA_DEADLINE"),
            "S_REQUESTED_DEADLINE_START_DATE": rd.get("S_REQUESTED_DEADLINE_START_DATE"),
            "S_REQUESTED_DEADLINE_END_DATE": rd.get("S_REQUESTED_DEADLINE_END_DATE"),
            "S_REQUIRED_ARRIVAL_DATE_EXPECTED": rd.get("S_REQUIRED_ARRIVAL_DATE"),
            "B_DATA_ESTIMATIVA_SAIDA_ETD": rd.get("B_DATA_ESTIMATIVA_SAIDA_ETD"),
            "B_DATA_ESTIMATIVA_CHEGADA_ETA": rd.get("B_DATA_ESTIMATIVA_CHEGADA_ETA"),
            "B_DATA_ABERTURA_GATE": rd.get("B_DATA_ABERTURA_GATE"),
            "USER_INSERT": user_insert,
            "ADJUSTMENT_ID": str(uuid.uuid4()),
        }

        # Garante binds quando SELECT não retornar colunas (compatibilidade)
        for k in (
            "B_DATA_PARTIDA_ATD",
            "B_DATA_CHEGADA_ATA",
            "B_DATA_ESTIMATIVA_ATRACACAO_ETB",
            "B_DATA_ATRACACAO_ATB",
        ):
            params.setdefault(k, None)

        conn.execute(insert_sql, params)
        conn.commit()
    finally:
        conn.close()

def insert_return_carrier_from_ui(ui_data, user_insert=None, status_override=None, area=None, request_reason=None, adjustments_owner=None, comments=None):
    """
    Insere dados na tabela F_CON_RETURN_CARRIERS baseado em dados da interface do usuário.
    Usado para PDFs processados, splits e ajustes.
    
    :param ui_data: Dicionário com dados da UI (com nomes de colunas amigáveis)
    :param user_insert: Usuário que está inserindo os dados
    :param status_override: Status específico a ser definido (ex: "Received from Carrier")
    :param area: Área do ajuste (para casos de split/adjustment)
    :param request_reason: Motivo do ajuste
    :param adjustments_owner: Responsável pelo ajuste
    :param comments: Comentários
    :return: True se sucesso, False caso contrário
    """
    conn = get_database_connection()
    try:
        # Mapeia campos da UI para campos da tabela
        field_mapping = {
            "Farol Reference": "FAROL_REFERENCE",
            "Booking Reference": "B_BOOKING_REFERENCE", 
            "Splitted Booking Reference": "S_SPLITTED_BOOKING_REFERENCE",
            "Voyage Carrier": "B_VOYAGE_CARRIER",
            "Voyage Code": "B_VOYAGE_CODE",
            "Vessel Name": "B_VESSEL_NAME",
            "Quantity of Containers": "S_QUANTITY_OF_CONTAINERS",
            "Sales Quantity of Containers": "S_QUANTITY_OF_CONTAINERS",
            "Port of Loading POL": "S_PORT_OF_LOADING_POL",
            "Port of Delivery POD": "S_PORT_OF_DELIVERY_POD",
            "Place of Receipt": "S_PLACE_OF_RECEIPT",
            "Final Destination": "S_FINAL_DESTINATION",
            "Transhipment Port": "B_TRANSHIPMENT_PORT",
            "Terminal": "B_TERMINAL",
            "Port Terminal City": "B_TERMINAL",
            "Requested Deadline Start Date": "B_DATA_ESTIMATIVA_SAIDA_ETD",
            "Requested Deadline End Date": "B_DATA_DRAFT_DEADLINE",
            "Required Arrival Date Expected": "B_DATA_ESTIMATIVA_CHEGADA_ETA",
            "PDF Booking Emission Date": "PDF_BOOKING_EMISSION_DATE",
            "PDF Name": "P_PDF_NAME",
        }
        
        # PRÉ-PREENCHIMENTO: Buscar datas do último registro aprovado para a mesma Farol Reference
        prefill_dates = {}
        if status_override == "Adjustment Requested" and "Farol Reference" in ui_data:
            farol_ref = ui_data["Farol Reference"]
            try:
                # Buscar último registro aprovado da mesma Farol Reference
                prefill_query = text("""
                    SELECT 
                        B_DATA_DRAFT_DEADLINE, B_DATA_DEADLINE, B_DATA_ESTIMATIVA_SAIDA_ETD,
                        B_DATA_ESTIMATIVA_CHEGADA_ETA, B_DATA_ABERTURA_GATE, B_DATA_PARTIDA_ATD,
                        B_DATA_CHEGADA_ATA, B_DATA_ESTIMATIVA_ATRACACAO_ETB, B_DATA_ATRACACAO_ATB
                    FROM LogTransp.F_CON_RETURN_CARRIERS
                    WHERE FAROL_REFERENCE = :farol_ref 
                    AND B_BOOKING_STATUS = 'Booking Approved'
                    ORDER BY ROW_INSERTED_DATE DESC
                    FETCH FIRST 1 ROWS ONLY
                """)
                result = conn.execute(prefill_query, {"farol_ref": farol_ref}).mappings().fetchone()
                if result:
                    # Mapear campos para pré-preenchimento
                    date_fields_mapping = {
                        'B_DATA_DRAFT_DEADLINE': 'B_DATA_DRAFT_DEADLINE',
                        'B_DATA_DEADLINE': 'B_DATA_DEADLINE', 
                        'B_DATA_ESTIMATIVA_SAIDA_ETD': 'B_DATA_ESTIMATIVA_SAIDA_ETD',
                        'B_DATA_ESTIMATIVA_CHEGADA_ETA': 'B_DATA_ESTIMATIVA_CHEGADA_ETA',
                        'B_DATA_ABERTURA_GATE': 'B_DATA_ABERTURA_GATE',
                        'B_DATA_PARTIDA_ATD': 'B_DATA_PARTIDA_ATD',
                        'B_DATA_CHEGADA_ATA': 'B_DATA_CHEGADA_ATA',
                        'B_DATA_ESTIMATIVA_ATRACACAO_ETB': 'B_DATA_ESTIMATIVA_ATRACACAO_ETB',
                        'B_DATA_ATRACACAO_ATB': 'B_DATA_ATRACACAO_ATB'
                    }
                    for src_field, dest_field in date_fields_mapping.items():
                        if src_field.lower() in result and result[src_field.lower()] is not None:
                            prefill_dates[dest_field] = result[src_field.lower()]
            except Exception as e:
                # Se falhar, continua sem pré-preenchimento
                pass

        # Converte dados da UI para formato da tabela
        db_data = {}
        for ui_key, db_key in field_mapping.items():
            if ui_key in ui_data and ui_data[ui_key] is not None:
                value = ui_data[ui_key]
                # Converte valores especiais
                if db_key.startswith("B_DATA_") and isinstance(value, str) and value.strip():
                    try:
                        # Tenta converter data se for string
                        from datetime import datetime
                        if ":" in value:  # formato com hora
                            db_data[db_key] = datetime.strptime(value, "%Y-%m-%d %H:%M")
                        else:  # formato só data
                            db_data[db_key] = datetime.strptime(value, "%Y-%m-%d")
                    except:
                        db_data[db_key] = value
                elif db_key == "PDF_BOOKING_EMISSION_DATE" and isinstance(value, str):
                    # Trunca PDF_BOOKING_EMISSION_DATE para máximo 18 caracteres (formato: YYYY-MM-DD HH:MM)
                    # Remove segundos se existirem para caber no limite da coluna
                    if len(value) > 18:
                        try:
                            from datetime import datetime
                            # Tenta parsear e reformatar sem segundos
                            dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
                            db_data[db_key] = dt.strftime("%Y-%m-%d %H:%M")  # 16 caracteres
                        except:
                            # Se falhar, trunca diretamente para 18 caracteres
                            db_data[db_key] = value[:18]
                    else:
                        db_data[db_key] = value
                else:
                    # Normaliza S_SPLITTED_BOOKING_REFERENCE: só aceita Farol Reference (FR_..). Caso contrário, mantém vazio
                    if db_key == "S_SPLITTED_BOOKING_REFERENCE":
                        try:
                            val_str = str(value).strip()
                            if not val_str or not val_str.startswith("FR_"):
                                value = ""
                        except Exception:
                            value = ""
                    # Trunca PDF Name se necessário (evita ORA-12899)
                    if db_key == "P_PDF_NAME" and isinstance(value, str):
                        value = value.strip()
                        if len(value) > 200:
                            value = value[:200]
                    db_data[db_key] = value
        
        # Aplicar pré-preenchimento de datas do último registro aprovado (apenas se não fornecidas)
        for date_field, date_value in prefill_dates.items():
            if date_field not in db_data or db_data[date_field] is None:
                db_data[date_field] = date_value

        # Campos obrigatórios e padrões
        db_data["B_BOOKING_STATUS"] = status_override or "Adjustment Requested"
        db_data["USER_INSERT"] = user_insert
        db_data["ADJUSTMENT_ID"] = str(uuid.uuid4())
        
        # Definir P_STATUS baseado na origem da solicitação
        if "P_STATUS" not in db_data or db_data.get("P_STATUS") in (None, "", "NULL"):
            if user_insert == "PDF_PROCESSOR":
                # Origem: Processamento de PDF/Documento do carrier
                db_data["P_STATUS"] = "PDF Document - Carrier"
            elif status_override == "Adjustment Requested":
                # Origem: Solicitação de ajuste ou split via shipments_split.py
                db_data["P_STATUS"] = "Adjustment Request - Company"
            else:
                # Fallback para outros casos
                db_data["P_STATUS"] = "Other Request - Company"
        
        # NÃO gerar Linked Reference automaticamente na inserção.
        # Regra de negócio: LINKED_REFERENCE só deve ser preenchido no momento da aprovação.
        # Portanto, removemos qualquer geração automática aqui.
        if "LINKED_REFERENCE" in db_data and (db_data["LINKED_REFERENCE"] is None or str(db_data["LINKED_REFERENCE"]).strip() == ""):
            db_data.pop("LINKED_REFERENCE", None)
        
        # Campos de ajuste (se fornecidos)
        if area:
            db_data["AREA"] = area
        if request_reason:
            db_data["REQUEST_REASON"] = request_reason
        if adjustments_owner:
            db_data["ADJUSTMENTS_OWNER"] = adjustments_owner
        if comments:
            db_data["COMMENTS"] = comments
        
        # SQL de inserção
        columns = list(db_data.keys())
        placeholders = [f":{col}" for col in columns]
        
        insert_sql = text(f"""
            INSERT INTO LogTransp.F_CON_RETURN_CARRIERS ({', '.join(columns)})
            VALUES ({', '.join(placeholders)})
        """)
        
        conn.execute(insert_sql, db_data)
        conn.commit()
        return True
        
    except Exception as e:
        if conn:
            conn.rollback()
        st.error(f"Erro ao inserir dados de retorno do carrier: {e}")
        return False
    finally:
        conn.close()

def _normalize_value(val):
    """Converts pandas/numpy types to native Python types for DB compatibility."""
    try:
        import numpy as np
        import pandas as pd

        if pd.isna(val):
            return None
        if isinstance(val, pd.Timestamp):
            return val.to_pydatetime()
        if isinstance(val, (np.integer, np.int64)):
            return int(val)
        if isinstance(val, (np.floating, np.float64)):
            return float(val)
        if isinstance(val, (np.bool_, np.bool)):
            return bool(val)
    except (ImportError, AttributeError):
        pass
    
    if hasattr(val, 'item'):
        try:
            return val.item()
        except (ValueError, TypeError):
            pass

    return val

def validate_and_collect_voyage_monitoring(vessel_name: str, voyage_code: str, terminal: str, save_to_db: bool = True) -> dict:
    """
    Valida e coleta dados de monitoramento da viagem usando a API Ellox.
    
    Args:
        vessel_name: Nome do navio
        voyage_code: Código da viagem  
        terminal: Nome do terminal
        
    Returns:
        dict: {"success": bool, "data": dict/None, "message": str, "requires_manual": bool}
    """
    try:
        from ellox_api import get_default_api_client
        import pandas as pd
        
        # 1. Verificar se os dados já existem no banco
        conn = get_database_connection()
        
        # Verificar se há dados VÁLIDOS (não apenas registro vazio)
        existing_query = text("""
            SELECT COUNT(*) as count
            FROM F_ELLOX_TERMINAL_MONITORINGS 
            WHERE UPPER(NAVIO) = UPPER(:vessel_name)
            AND UPPER(VIAGEM) = UPPER(:voyage_code)
            AND UPPER(TERMINAL) = UPPER(:terminal)
            AND (DATA_DEADLINE IS NOT NULL 
                OR DATA_ESTIMATIVA_SAIDA IS NOT NULL 
                OR DATA_ESTIMATIVA_CHEGADA IS NOT NULL 
                OR DATA_ABERTURA_GATE IS NOT NULL)
        """)
        
        existing_count = conn.execute(existing_query, {
            "vessel_name": vessel_name,
            "voyage_code": voyage_code, 
            "terminal": terminal
        }).scalar()
        
        conn.close()
        
        if existing_count > 0:
            return {
                "success": True,
                "data": None,
                "message": f"✅ Dados de monitoramento já existem para {vessel_name} - {voyage_code} - {terminal}",
                "requires_manual": False
            }
        
        # 2. Tentar obter dados da API Ellox
        api_client = get_default_api_client()
        
        # Verificar autenticação primeiro
        if not api_client.authenticated:
            return {
                "success": False,
                "data": None,
                "message": "🔴 Falha na Autenticação da API Ellox\n\nAs credenciais da API estão inválidas ou expiraram. Contate o administrador para atualizar as credenciais.",
                "requires_manual": True,
                "error_type": "authentication_failed"
            }
        
        # Testar conexão
        api_test = api_client.test_connection()
        if not api_test.get("success"):
            return {
                "success": False,
                "data": None,
                "message": "🟡 API Ellox Temporariamente Indisponível\n\nNão foi possível conectar com o servidor da API. Tente novamente em alguns minutos.",
                "requires_manual": True,
                "error_type": "connection_failed"
            }
        
        # 3. Resolver CNPJ do terminal (com normalização)
        cnpj_terminal = None
        
        # Aplicar normalização de terminal (como no pdf_booking_processor.py)
        terminal_normalized = terminal.upper().strip()
        
        # Caso especial: Embraport (DP World Santos)
        # Alguns PDFs trazem "Embraport Empresa Brasileira"; na API é reconhecido como DPW/DP WORLD
        if "EMBRAPORT" in terminal_normalized or "EMPRESA BRASILEIRA" in terminal_normalized:
            try:
                conn = get_database_connection()
                query = text("""
                    SELECT CNPJ, NOME
                    FROM F_ELLOX_TERMINALS
                    WHERE UPPER(NOME) LIKE '%DPW%'
                       OR UPPER(NOME) LIKE '%DP WORLD%'
                       OR UPPER(NOME) LIKE '%EMBRAPORT%'
                    FETCH FIRST 1 ROWS ONLY
                """)
                res = conn.execute(query).mappings().fetchone()
                conn.close()
                if res and res.get("cnpj"):
                    cnpj_terminal = res["cnpj"]
            except Exception:
                # mantém fallback se não encontrar
                pass
        
        # Se não encontrou via normalização, buscar na API
        if not cnpj_terminal:
            terms_resp = api_client._make_api_request("/api/terminals")
            if terms_resp.get("success"):
                for term in terms_resp.get("data", []):
                    nome_term = term.get("nome") or term.get("name") or ""
                    if str(nome_term).strip().upper() == str(terminal).strip().upper() or str(terminal).strip().upper() in str(nome_term).strip().upper():
                        cnpj_terminal = term.get("cnpj")
                        break
        
        if not cnpj_terminal:
            return {
                "success": False,
                "data": None,
                "message": f"🟠 Terminal Não Localizado na API\n\nTerminal '{terminal}' não foi encontrado na base da API. Verifique se o nome do terminal está correto.",
                "requires_manual": True,
                "error_type": "terminal_not_found"
            }
        
        # 4. Buscar dados de monitoramento
        cnpj_client = "60.498.706/0001-57"  # CNPJ Cargill padrão
        mon_resp = api_client.view_vessel_monitoring(cnpj_client, cnpj_terminal, vessel_name, voyage_code)
        
        if not mon_resp.get("success") or not mon_resp.get("data"):
            return {
                "success": False,
                "data": None,
                "message": f"🔵 Voyage Não Encontrada na API\n\n🚢 {vessel_name} | {voyage_code} | {terminal} não localizada na base atual. Use o formulário manual abaixo para inserir os dados.",
                "requires_manual": True,
                "error_type": "voyage_not_found",
                "cnpj_terminal": cnpj_terminal,
                "agencia": ""
            }
        
        # 5. Processar dados da API
        data_list = mon_resp.get("data", [])
        
        if isinstance(data_list, list) and len(data_list) > 0:
            payload = data_list[0]
        elif isinstance(data_list, dict):
            payload = data_list
        else:
            return {
                "success": False,
                "data": None,
                "message": "🟡 Formato de Dados Inesperado da API\n\nA API retornou dados em formato não reconhecido. Pode ser necessário atualizar a integração.",
                "requires_manual": True,
                "error_type": "data_format_error"
            }
        
        # 6. Mapear e converter dados
        def get_api_value(key):
            if isinstance(payload, dict):
                for k in payload.keys():
                    if str(k).lower() == key.lower():
                        return payload[k]
            return None
        
        api_data = {}
        mapping = {
            "data_deadline": "DATA_DEADLINE",
            "data_draft_deadline": "DATA_DRAFT_DEADLINE", 
            "data_abertura_gate": "DATA_ABERTURA_GATE",
            "data_abertura_gate_reefer": "DATA_ABERTURA_GATE_REEFER",
            "data_estimativa_saida": "DATA_ESTIMATIVA_SAIDA",
            "etd": "DATA_ESTIMATIVA_SAIDA",
            "data_estimativa_chegada": "DATA_ESTIMATIVA_CHEGADA",
            "eta": "DATA_ESTIMATIVA_CHEGADA",
            "data_estimativa_atracacao": "DATA_ESTIMATIVA_ATRACACAO",
            "etb": "DATA_ESTIMATIVA_ATRACACAO",
            "data_atracacao": "DATA_ATRACACAO",
            "atb": "DATA_ATRACACAO",
            "data_partida": "DATA_PARTIDA",
            "atd": "DATA_PARTIDA",
            "data_chegada": "DATA_CHEGADA",
            "ata": "DATA_CHEGADA",
            "data_atualizacao": "DATA_ATUALIZACAO",
            "last_update": "DATA_ATUALIZACAO",
            "updated_at": "DATA_ATUALIZACAO"
        }
        
        # Processar cada coluna do banco de dados separadamente
        db_columns_processed = set()
        for api_key, db_col in mapping.items():
            if db_col not in db_columns_processed:
                val = get_api_value(api_key)
                if val is not None:
                    try:
                        api_data[db_col] = pd.to_datetime(val)
                        db_columns_processed.add(db_col)
                    except Exception:
                        api_data[db_col] = val
                        db_columns_processed.add(db_col)
        
        if not api_data:
            return {
                "success": False,
                "data": None,
                "message": "⚪ Nenhuma Data Válida Encontrada na API\n\nA API retornou dados, mas nenhuma data de monitoramento válida foi identificada. Use o formulário manual para inserir as datas.",
                "requires_manual": True,
                "error_type": "no_valid_dates"
            }
        
        # 7. Salvar dados no banco (apenas se solicitado)
        if not save_to_db:
            return {
                "success": True,
                "data": api_data,
                "message": f"✅ Dados de monitoramento encontrados na API ({len(api_data)} campos)",
                "requires_manual": False,
                "cnpj_terminal": cnpj_terminal,
                "agencia": payload.get("agencia", "")
            }

        try:
            monitoring_data = {
                "NAVIO": vessel_name,
                "VIAGEM": voyage_code,
                "TERMINAL": terminal,
                "CNPJ_TERMINAL": cnpj_terminal,
                "AGENCIA": payload.get("agencia", ""),
                **api_data
            }
            
            # Usar a função existente para salvar
            df_monitoring = pd.DataFrame([monitoring_data])
            processed_count = upsert_terminal_monitorings_from_dataframe(df_monitoring)
            
            if processed_count > 0:
                return {
                    "success": True,
                    "data": api_data,
                    "message": f"✅ Dados de monitoramento coletados da API e salvos ({len(api_data)} campos)",
                    "requires_manual": False
                }
            else:
                return {
                    "success": False,
                    "data": None,
                    "message": "❌ Erro ao salvar dados de monitoramento",
                    "requires_manual": True
                }
                
        except Exception as e:
            return {
                "success": False,
                "data": None,
                "message": f"❌ Erro ao salvar monitoramento: {str(e)}",
                "requires_manual": True
            }
            
    except Exception as e:
        return {
            "success": False,
            "data": None,
            "message": f"❌ Erro na validação da API: {str(e)}",
            "requires_manual": True
        }

def approve_carrier_return(adjustment_id: str, related_reference: str, justification: dict, manual_voyage_data: dict = None) -> bool:
    """
    Executes the full approval process for a 'Received from Carrier' record within a single transaction.
    This includes fetching Ellox data, updating the return carrier record, and propagating changes to the main sales/booking table.

    :param adjustment_id: The ADJUSTMENT_ID of the F_CON_RETURN_CARRIERS record to approve.
    :param related_reference: The complete selection string (e.g., 'FR_25.09_0001 | Booking Requested | 11/09/2025 19:27') or 'New Adjustment'.
    :param justification: A dict with justification fields for 'New Adjustment' cases.
    :return: True if successful, False otherwise.
    """
    conn = get_database_connection()
    tx = conn.begin()
    try:
        # 1. Lock the target row to prevent race conditions and hangs
        try:
            lock_query = text("SELECT 1 FROM LogTransp.F_CON_RETURN_CARRIERS WHERE ADJUSTMENT_ID = :adj_id FOR UPDATE NOWAIT")
            conn.execute(lock_query, {"adj_id": adjustment_id})
        except Exception as e:
            if "ORA-00054" in str(e):
                st.error("❌ This record is currently locked by another process. Please try again in a moment.")
                tx.rollback()
                return False
            raise # Re-raise other unexpected errors

        # 2. Validar e coletar dados de monitoramento da viagem (usar buffer, se existir)
        vessel_name_result = conn.execute(text("SELECT B_VESSEL_NAME, B_VOYAGE_CODE, B_TERMINAL FROM LogTransp.F_CON_RETURN_CARRIERS WHERE ADJUSTMENT_ID = :adj_id"), {"adj_id": adjustment_id}).mappings().fetchone()
        
        elox_update_values = {}
        voyage_validation_result = None
        
        # Primeiro, verificar se há dados manuais para processar
        if manual_voyage_data:
            st.info("ℹ️ Usando dados de monitoramento inseridos manualmente.")
            column_mapping = {
                'manual_deadline': 'B_DATA_DEADLINE',
                'manual_draft_deadline': 'B_DATA_DRAFT_DEADLINE',
                'manual_gate_opening': 'B_DATA_ABERTURA_GATE',
                # B_DATA_ABERTURA_GATE_REEFER só existe em F_ELLOX_TERMINAL_MONITORINGS, não em F_CON_RETURN_CARRIERS
                'manual_etd': 'B_DATA_ESTIMATIVA_SAIDA_ETD',
                'manual_eta': 'B_DATA_ESTIMATIVA_CHEGADA_ETA',
                'manual_etb': 'B_DATA_ESTIMATIVA_ATRACACAO_ETB',
                'manual_atb': 'B_DATA_ATRACACAO_ATB',
                'manual_atd': 'B_DATA_PARTIDA_ATD',
                'manual_ata': 'B_DATA_CHEGADA_ATA',
            }
            for manual_key, db_col in column_mapping.items():
                if manual_key in manual_voyage_data and manual_voyage_data[manual_key] is not None:
                    elox_update_values[db_col] = manual_voyage_data[manual_key]
        
        if vessel_name_result:
            vessel_name = vessel_name_result.get("b_vessel_name")
            voyage_code = vessel_name_result.get("b_voyage_code") or ""
            terminal = vessel_name_result.get("b_terminal") or ""
            
            if vessel_name and terminal and not manual_voyage_data:
                # Se houver buffer prévio no session_state, utiliza; senão, apenas valida (sem salvar ainda)
                api_buf_key = f"voyage_api_buffer_{adjustment_id}"
                api_buf = st.session_state.get(api_buf_key)
                if not api_buf:
                    voyage_validation_result = validate_and_collect_voyage_monitoring(vessel_name, voyage_code, terminal, save_to_db=False)
                    if voyage_validation_result.get("success"):
                        api_buf = {
                            "NAVIO": vessel_name,
                            "VIAGEM": voyage_code,
                            "TERMINAL": terminal,
                            "CNPJ_TERMINAL": voyage_validation_result.get("cnpj_terminal"),
                            "AGENCIA": voyage_validation_result.get("agencia", ""),
                        }
                        for k, v in (voyage_validation_result.get("data") or {}).items():
                            api_buf[k] = v
                        st.session_state[api_buf_key] = api_buf
                    elif voyage_validation_result.get("requires_manual"):
                        st.warning(voyage_validation_result.get("message", ""))
                        st.session_state["voyage_manual_entry_required"] = {
                            "adjustment_id": adjustment_id,
                            "vessel_name": vessel_name,
                            "voyage_code": voyage_code,
                            "terminal": terminal,
                            "message": voyage_validation_result.get("message", "")
                        }
                    else:
                        st.error(voyage_validation_result.get("message", ""))

                # Se existe buffer, persiste em F_ELLOX_TERMINAL_MONITORINGS agora (no momento da confirmação)
                if api_buf:
                    try:
                        df_monitoring = pd.DataFrame([api_buf])
                        processed_count = upsert_terminal_monitorings_from_dataframe(df_monitoring)
                        if processed_count > 0:
                            st.success("✅ Dados de monitoramento da API salvos no banco.")
                            
                            # Buscar dados mais recentes da tabela (como era feito antes)
                            vessel_name = api_buf.get("NAVIO")
                            if vessel_name:
                                monitoring_query = text("""
                                    SELECT * FROM (
                                        SELECT * FROM F_ELLOX_TERMINAL_MONITORINGS
                                        WHERE UPPER(NAVIO) = UPPER(:vessel_name)
                                        ORDER BY NVL(DATA_ATUALIZACAO, ROW_INSERTED_DATE) DESC
                                    ) WHERE ROWNUM = 1
                                """)
                                latest_monitoring_record = conn.execute(monitoring_query, {"vessel_name": vessel_name}).mappings().fetchone()
                                
                                if latest_monitoring_record:
                                    column_mapping = {
                                        'DATA_DRAFT_DEADLINE': 'B_DATA_DRAFT_DEADLINE', 
                                        'DATA_DEADLINE': 'B_DATA_DEADLINE',
                                        'DATA_ESTIMATIVA_SAIDA': 'B_DATA_ESTIMATIVA_SAIDA_ETD', 
                                        'DATA_ESTIMATIVA_CHEGADA': 'B_DATA_ESTIMATIVA_CHEGADA_ETA',
                                        'DATA_ABERTURA_GATE': 'B_DATA_ABERTURA_GATE', 
                                        # B_DATA_ABERTURA_GATE_REEFER não existe em F_CON_RETURN_CARRIERS
                                        'DATA_PARTIDA': 'B_DATA_PARTIDA_ATD',
                                        'DATA_CHEGADA': 'B_DATA_CHEGADA_ATA', 
                                        'DATA_ESTIMATIVA_ATRACACAO': 'B_DATA_ESTIMATIVA_ATRACACAO_ETB',
                                        'DATA_ATRACACAO': 'B_DATA_ATRACACAO_ATB',
                                    }
                                    for elox_col, return_col in column_mapping.items():
                                        if elox_col.lower() in latest_monitoring_record and latest_monitoring_record[elox_col.lower()] is not None:
                                            elox_update_values[return_col] = latest_monitoring_record[elox_col.lower()]
                        else:
                            st.warning("⚠️ Falha ao salvar dados de monitoramento da API.")
                        
                        # Limpa o buffer após processar
                        st.session_state.pop(api_buf_key, None)
                    except Exception as e:
                        st.error(f"❌ Erro ao persistir dados de monitoramento: {str(e)}")

        # 3. Prepare and execute the UPDATE on F_CON_RETURN_CARRIERS
        update_params = {"adjustment_id": adjustment_id, "user_update": "System"}
        update_params.update(elox_update_values)

        set_clauses = [f"{col} = :{col}" for col in elox_update_values.keys()]
        set_clauses.append("B_BOOKING_STATUS = 'Booking Approved'")
        set_clauses.append("USER_UPDATE = :user_update")
        set_clauses.append("DATE_UPDATE = SYSDATE")

        if related_reference == "New Adjustment":
            update_params.update(justification)
            set_clauses.extend(["Linked_Reference = 'New Adjustment'", "AREA = :area", "REQUEST_REASON = :request_reason", "ADJUSTMENTS_OWNER = :adjustments_owner", "COMMENTS = :comments"])
        else:
            # Para aprovação de PDF/retorno do carrier, limpar campos de justificativa
            # Persistir a chave completa enviada pela UI (sem ícones). Caso ultrapasse 60, truncar com segurança
            ref_str = str(related_reference) if related_reference is not None else ''
            if len(ref_str) > 60:
                ref_str = ref_str[:60]
            update_params["linked_ref"] = ref_str
            # Limpar campos de justificativa para aprovações de PDF
            update_params["area_clear"] = None
            update_params["request_reason_clear"] = None  
            update_params["adjustments_owner_clear"] = None
            update_params["comments_clear"] = None
            set_clauses.extend([
                "Linked_Reference = :linked_ref",
                "AREA = :area_clear", 
                "REQUEST_REASON = :request_reason_clear",
                "ADJUSTMENTS_OWNER = :adjustments_owner_clear", 
                "COMMENTS = :comments_clear"
            ])

        update_query_str = f"UPDATE LogTransp.F_CON_RETURN_CARRIERS SET {', '.join(set_clauses)} WHERE ADJUSTMENT_ID = :adjustment_id"
        conn.execute(text(update_query_str), update_params)

        # 4. Fetch the newly updated data from F_CON_RETURN_CARRIERS to propagate to the main table
        return_carrier_data = get_return_carriers_by_adjustment_id(adjustment_id, conn)
        if return_carrier_data.empty:
            raise Exception("Failed to retrieve return carrier data after update.")

        row = return_carrier_data.iloc[0]
        farol_reference = row.get("FAROL_REFERENCE")
        if not farol_reference:
            raise Exception("Farol Reference not found in return carrier data.")

        # 5. Prepare and execute the UPDATE on F_CON_SALES_BOOKING_DATA
        main_update_fields = {"farol_reference": farol_reference, "FAROL_STATUS": "Booking Approved"}
        fields_to_propagate = [
            "S_SPLITTED_BOOKING_REFERENCE", "S_PLACE_OF_RECEIPT", "S_QUANTITY_OF_CONTAINERS",
            "S_PORT_OF_LOADING_POL", "S_PORT_OF_DELIVERY_POD", "S_FINAL_DESTINATION",
            "B_BOOKING_REFERENCE", "B_TRANSHIPMENT_PORT", "B_TERMINAL", "B_VESSEL_NAME",
            "B_VOYAGE_CODE", "B_VOYAGE_CARRIER", "B_DATA_DRAFT_DEADLINE", "B_DATA_DEADLINE",
            "B_DATA_ESTIMATIVA_SAIDA_ETD", "B_DATA_ESTIMATIVA_CHEGADA_ETA", "B_DATA_ABERTURA_GATE",
            "B_DATA_PARTIDA_ATD", "B_DATA_CHEGADA_ATA", "B_DATA_ESTIMATIVA_ATRACACAO_ETB", "B_DATA_ATRACACAO_ATB"
        ]
        
        # Adicionar B_BOOKING_CONFIRMATION_DATE com valor do PDF_BOOKING_EMISSION_DATE
        if "PDF_BOOKING_EMISSION_DATE" in row and row["PDF_BOOKING_EMISSION_DATE"] is not None:
            pdf_emission_date = row["PDF_BOOKING_EMISSION_DATE"]
            # Converter string para datetime se necessário
            if isinstance(pdf_emission_date, str):
                try:
                    from datetime import datetime
                    # Tenta parsear diferentes formatos de data
                    if ":" in pdf_emission_date:
                        if len(pdf_emission_date) > 16:  # Formato com segundos
                            pdf_emission_date = datetime.strptime(pdf_emission_date, "%Y-%m-%d %H:%M:%S")
                        else:  # Formato sem segundos
                            pdf_emission_date = datetime.strptime(pdf_emission_date, "%Y-%m-%d %H:%M")
                    else:  # Apenas data
                        pdf_emission_date = datetime.strptime(pdf_emission_date, "%Y-%m-%d")
                except:
                    # Se falhar o parse, mantém como string
                    pass
            main_update_fields["B_BOOKING_CONFIRMATION_DATE"] = pdf_emission_date
        for field in fields_to_propagate:
            if field in row and row[field] is not None:
                val = _normalize_value(row[field])
                if val is None:
                    continue
                if isinstance(val, str) and val.strip() == "":
                    continue
                main_update_fields[field] = val

        main_set_clause = ", ".join([f"{field} = :{field}" for field in main_update_fields.keys() if field != 'farol_reference'])
        main_update_query = text(f"UPDATE LogTransp.F_CON_SALES_BOOKING_DATA SET {main_set_clause} WHERE FAROL_REFERENCE = :farol_reference")
        conn.execute(main_update_query, main_update_fields)

        # 6. Commit transaction
        tx.commit()
        st.success(f"✅ Record {farol_reference} approved and updated successfully.")
        return True

    except Exception as e:
        if 'tx' in locals() and tx.is_active:
            tx.rollback()
        st.error(f"❌ A critical error occurred during the approval process: {e}")
        st.session_state["approval_error"] = f"❌ A critical error occurred during the approval process: {e}"
        return False
    finally:
        if 'conn' in locals() and not conn.closed:
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


def get_return_carriers_by_adjustment_id(adjustment_id: str, conn=None) -> pd.DataFrame:
    """Busca dados da F_CON_RETURN_CARRIERS pelo ADJUSTMENT_ID."""
    should_close = conn is None
    if conn is None:
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
                B_TERMINAL,
                B_VESSEL_NAME,
                B_VOYAGE_CARRIER,
                B_VOYAGE_CODE,
                B_DATA_DRAFT_DEADLINE,
                B_DATA_DEADLINE,
                B_DATA_ESTIMATIVA_SAIDA_ETD,
                B_DATA_ESTIMATIVA_CHEGADA_ETA,
                B_DATA_ABERTURA_GATE,
                B_DATA_PARTIDA_ATD,
                B_DATA_CHEGADA_ATA,
                B_DATA_ESTIMATIVA_ATRACACAO_ETB,
                B_DATA_ATRACACAO_ATB,
                AREA,
                REQUEST_REASON,
                ADJUSTMENTS_OWNER,
                COMMENTS,
                USER_INSERT,
                USER_UPDATE,
                DATE_UPDATE,
                ROW_INSERTED_DATE,
                PDF_BOOKING_EMISSION_DATE
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
        if should_close:
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


# ============================
# ELLOX TERMINAL MONITORINGS
# ============================
def _parse_iso_datetime(value):
    """Converte strings ISO ou pandas Timestamp em datetime. Retorna None se inválido."""
    if value is None:
        return None
    
    try:
        import pandas as pd
        from datetime import datetime as _dt
        
        # Se já é um pandas Timestamp válido, converte para datetime nativo
        if isinstance(value, pd.Timestamp):
            if pd.isna(value):
                return None
            return value.to_pydatetime().replace(tzinfo=None)
        
        # Se é NaT (pandas Not a Time), retorna None
        if pd.isna(value):
            return None
        
        # Para strings, processa como antes
        s = str(value).strip()
        if s == "" or s.lower() == 'nat':
            return None
            
        # Normaliza: remove Z e troca T por espaço
        s = s.replace("T", " ").replace("Z", "").strip()
        
        # Tenta formatos comuns
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return _dt.strptime(s, fmt)
            except Exception:
                continue
        return None
    except Exception:
        return None


def ensure_table_f_ellox_terminal_monitorings():
    """Cria a tabela F_ELLOX_TERMINAL_MONITORINGS caso não exista."""
    conn = get_database_connection()
    try:
        exists = conn.execute(text(
            """
            SELECT COUNT(*) AS ct
            FROM user_tables
            WHERE table_name = 'F_ELLOX_TERMINAL_MONITORINGS'
            """
        )).scalar()

        if int(exists or 0) == 0:
            ddl = text(
                """
                CREATE TABLE F_ELLOX_TERMINAL_MONITORINGS (
                    ID                          NUMBER(20)      PRIMARY KEY,
                    NAVIO                       VARCHAR2(100 CHAR),
                    VIAGEM                      VARCHAR2(50 CHAR),
                    AGENCIA                     VARCHAR2(100 CHAR),
                    DATA_DEADLINE               DATE,
                    DATA_DRAFT_DEADLINE         DATE,
                    DATA_ABERTURA_GATE          DATE,
                    DATA_ABERTURA_GATE_REEFER   DATE,
                    DATA_ESTIMATIVA_SAIDA       DATE,
                    DATA_ESTIMATIVA_CHEGADA     DATE,
                    DATA_ATUALIZACAO            DATE,
                    TERMINAL                    VARCHAR2(100 CHAR),
                    CNPJ_TERMINAL               VARCHAR2(20 CHAR),
                    DATA_CHEGADA                DATE,
                    DATA_ESTIMATIVA_ATRACACAO   DATE,
                    DATA_ATRACACAO              DATE,
                    DATA_PARTIDA                DATE,
                    ROW_INSERTED_DATE           DATE DEFAULT SYSDATE
                )
                """
            )
            conn.execute(ddl)
            conn.commit()
    finally:
        conn.close()


def upsert_terminal_monitorings_from_dataframe(df: pd.DataFrame) -> int:
    """Realiza upsert (MERGE) em F_ELLOX_TERMINAL_MONITORINGS a partir de um DataFrame.

    Espera colunas (case-insensitive):
      id, navio, viagem, agencia, data_deadline, data_draft_deadline, data_abertura_gate,
      data_abertura_gate_reefer, data_estimativa_saida, data_estimativa_chegada, data_atualizacao,
      terminal, cnpj_terminal, data_chegada, data_estimativa_atracacao, data_atracacao, data_partida

    Retorna: quantidade de linhas processadas.
    """
    if df is None or df.empty:
        return 0

    ensure_table_f_ellox_terminal_monitorings()

    # Normaliza nomes de colunas para minúsculas para acesso resiliente
    cols_map = {c.lower(): c for c in df.columns}

    required = [
        'id', 'navio', 'viagem', 'agencia', 'data_deadline', 'data_draft_deadline',
        'data_abertura_gate', 'data_abertura_gate_reefer', 'data_estimativa_saida',
        'data_estimativa_chegada', 'data_atualizacao', 'terminal', 'cnpj_terminal',
        'data_chegada', 'data_estimativa_atracacao', 'data_atracacao', 'data_partida'
    ]

    processed = 0
    with get_database_connection() as conn:
        for _, row in df.iterrows():
            def g(key):
                c = cols_map.get(key)
                return row[c] if c in row else None

            from datetime import datetime as _datetime
            params = {
                "ID": int(g('id')) if g('id') is not None and str(g('id')).strip() != '' else None,
                "NAVIO": g('navio'),
                "VIAGEM": g('viagem'),
                "AGENCIA": g('agencia'),
                "DATA_DEADLINE": _parse_iso_datetime(g('data_deadline')),
                "DATA_DRAFT_DEADLINE": _parse_iso_datetime(g('data_draft_deadline')),
                "DATA_ABERTURA_GATE": _parse_iso_datetime(g('data_abertura_gate')),
                "DATA_ABERTURA_GATE_REEFER": _parse_iso_datetime(g('data_abertura_gate_reefer')),
                "DATA_ESTIMATIVA_SAIDA": _parse_iso_datetime(g('data_estimativa_saida')),
                "DATA_ESTIMATIVA_CHEGADA": _parse_iso_datetime(g('data_estimativa_chegada')),
                # Se vier vazio, assume timestamp atual nas entradas manuais
                "DATA_ATUALIZACAO": _parse_iso_datetime(g('data_atualizacao')) or _datetime.now(),
                "TERMINAL": g('terminal'),
                "CNPJ_TERMINAL": g('cnpj_terminal'),
                "DATA_CHEGADA": _parse_iso_datetime(g('data_chegada')),
                "DATA_ESTIMATIVA_ATRACACAO": _parse_iso_datetime(g('data_estimativa_atracacao')),
                "DATA_ATRACACAO": _parse_iso_datetime(g('data_atracacao')),
                "DATA_PARTIDA": _parse_iso_datetime(g('data_partida')),
            }

            # Se não há ID vindo da API, gera ID determinístico a partir de campos-chave
            if params["ID"] is None:
                try:
                    import hashlib
                    seed_parts = [
                        str(params.get("NAVIO") or ""),
                        str(params.get("VIAGEM") or ""),
                        str(params.get("CNPJ_TERMINAL") or params.get("TERMINAL") or ""),
                        str(params.get("DATA_ATUALIZACAO") or params.get("DATA_ESTIMATIVA_SAIDA") or params.get("DATA_DEADLINE") or "")
                    ]
                    seed = "|".join(seed_parts)
                    digest16 = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]
                    params["ID"] = int(digest16, 16)
                except Exception as e:
                    # Se falhar, ainda assim pula para evitar PK nula
                    continue

            merge_sql = text(
                """
                MERGE INTO F_ELLOX_TERMINAL_MONITORINGS t
                USING (SELECT :ID AS ID FROM dual) s
                ON (t.ID = s.ID)
                WHEN MATCHED THEN UPDATE SET
                    NAVIO = :NAVIO,
                    VIAGEM = :VIAGEM,
                    AGENCIA = :AGENCIA,
                    DATA_DEADLINE = :DATA_DEADLINE,
                    DATA_DRAFT_DEADLINE = :DATA_DRAFT_DEADLINE,
                    DATA_ABERTURA_GATE = :DATA_ABERTURA_GATE,
                    DATA_ABERTURA_GATE_REEFER = :DATA_ABERTURA_GATE_REEFER,
                    DATA_ESTIMATIVA_SAIDA = :DATA_ESTIMATIVA_SAIDA,
                    DATA_ESTIMATIVA_CHEGADA = :DATA_ESTIMATIVA_CHEGADA,
                    DATA_ATUALIZACAO = :DATA_ATUALIZACAO,
                    TERMINAL = :TERMINAL,
                    CNPJ_TERMINAL = :CNPJ_TERMINAL,
                    DATA_CHEGADA = :DATA_CHEGADA,
                    DATA_ESTIMATIVA_ATRACACAO = :DATA_ESTIMATIVA_ATRACACAO,
                    DATA_ATRACACAO = :DATA_ATRACACAO,
                    DATA_PARTIDA = :DATA_PARTIDA
                WHEN NOT MATCHED THEN INSERT (
                    ID, NAVIO, VIAGEM, AGENCIA, DATA_DEADLINE, DATA_DRAFT_DEADLINE,
                    DATA_ABERTURA_GATE, DATA_ABERTURA_GATE_REEFER, DATA_ESTIMATIVA_SAIDA,
                    DATA_ESTIMATIVA_CHEGADA, DATA_ATUALIZACAO, TERMINAL, CNPJ_TERMINAL,
                    DATA_CHEGADA, DATA_ESTIMATIVA_ATRACACAO, DATA_ATRACACAO, DATA_PARTIDA
                ) VALUES (
                    :ID, :NAVIO, :VIAGEM, :AGENCIA, :DATA_DEADLINE, :DATA_DRAFT_DEADLINE,
                    :DATA_ABERTURA_GATE, :DATA_ABERTURA_GATE_REEFER, :DATA_ESTIMATIVA_SAIDA,
                    :DATA_ESTIMATIVA_CHEGADA, :DATA_ATUALIZACAO, :TERMINAL, :CNPJ_TERMINAL,
                    :DATA_CHEGADA, :DATA_ESTIMATIVA_ATRACACAO, :DATA_ATRACACAO, :DATA_PARTIDA
                )
                """
            )
            conn.execute(merge_sql, params)
            processed += 1

        conn.commit()
    return processed

def get_terminal_monitorings(limit: int = 200) -> pd.DataFrame:
    """Consulta recentes da F_ELLOX_TERMINAL_MONITORINGS."""
    ensure_table_f_ellox_terminal_monitorings()
    with get_database_connection() as conn:
        rows = conn.execute(text(
            f"""
            SELECT *
            FROM F_ELLOX_TERMINAL_MONITORINGS
            ORDER BY NVL(DATA_ATUALIZACAO, ROW_INSERTED_DATE) DESC
            FETCH FIRST {int(limit)} ROWS ONLY
            """
        )).mappings().fetchall()
        df = pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()
        return df

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

def update_record_status(adjustment_id: str, new_status: str) -> bool:
    """
    Updates the status for a record in both F_CON_RETURN_CARRIERS and F_CON_SALES_BOOKING_DATA.
    Used for simple status changes like Rejected, Cancelled, etc.
    """
    conn = get_database_connection()
    tx = conn.begin()
    try:
        # 1. Get the Farol Reference from the adjustment ID
        farol_ref_query = text("SELECT FAROL_REFERENCE FROM LogTransp.F_CON_RETURN_CARRIERS WHERE ADJUSTMENT_ID = :adj_id")
        farol_ref = conn.execute(farol_ref_query, {"adj_id": adjustment_id}).scalar()

        if not farol_ref:
            raise Exception(f"Could not find Farol Reference for Adjustment ID: {adjustment_id}")

        # 2. Update the status in F_CON_RETURN_CARRIERS
        update_return_query = text("""
            UPDATE LogTransp.F_CON_RETURN_CARRIERS
            SET B_BOOKING_STATUS = :new_status, USER_UPDATE = 'System', DATE_UPDATE = SYSDATE
            WHERE ADJUSTMENT_ID = :adj_id
        """)
        conn.execute(update_return_query, {"new_status": new_status, "adj_id": adjustment_id})

        # 3. Update the status in F_CON_SALES_BOOKING_DATA
        update_main_query = text("""
            UPDATE LogTransp.F_CON_SALES_BOOKING_DATA
            SET FAROL_STATUS = :new_status
            WHERE FAROL_REFERENCE = :farol_ref
        """)
        conn.execute(update_main_query, {"new_status": new_status, "farol_ref": farol_ref})

        # 4. Commit
        tx.commit()
        st.success(f"✅ Status for {farol_ref} successfully updated to '{new_status}'.")
        return True

    except Exception as e:
        if 'tx' in locals() and tx.is_active:
            tx.rollback()
        st.error(f"❌ An error occurred while updating status: {e}")
        return False
    finally:
        if 'conn' in locals() and not conn.closed:
            conn.close()