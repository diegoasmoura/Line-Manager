## database.py
 
import streamlit as st
from sqlalchemy import create_engine, text
import pandas as pd
from shipments_mapping import get_column_mapping
from datetime import datetime
from shipments_mapping import get_reverse_mapping
import uuid
 
# Data e hora atuais
now = datetime.now()
 
# Configurações do banco de dados
DB_CONFIG = {
    "host": "127.0.0.1",  # Ou "127.0.0.1"
    "port": "1521",
    "name": "ORCLPDB1",  # O SERVICE NAME do seu PDB no Docker!
    "user": "ps218125",
    "password": "40012330" # Use a senha que você definiu ao criar PS218125
}
 
def get_database_connection():
    """Cria e retorna a conexão com o banco de dados."""
    engine = create_engine(f'oracle+oracledb://{DB_CONFIG["user"]}:{DB_CONFIG["password"]}@{DB_CONFIG["host"]}:{DB_CONFIG["port"]}/?service_name={DB_CONFIG["name"]}')
    return engine.connect()
 
#Obter os dados das tabelas principais Sales
#@st.cache_data(ttl=300)
def get_data_salesData():
    """Executa a consulta SQL, aplica o mapeamento de colunas e retorna um DataFrame formatado."""
    conn = None
 
    # Consulta SQL
    query = '''
    SELECT *
    FROM LogTransp.F_CON_SALES_DATA
    ORDER BY s_farol_reference'''
 
    try:
        conn = get_database_connection()
        df = pd.read_sql_query(text(query), conn)
 
        # Aplicar o mapeamento de colunas antes de retornar os dados
        column_mapping = get_column_mapping()
        df.rename(columns=column_mapping, inplace=True)
 
        #Filtrando as colunas e definindo a ordem de exibição
        df = df[["Sales Farol Reference","Shipment Status","Type of Shipment","Creation Of Shipment","Business","Customer", "Customer PO", "Sales Order Reference",
            "Sales Order Date", "Mode", "Sales Incoterm", "SKU", "Plant of Origin", "Splitted Booking Reference",
            "Volume in Tons", "Sales Quantity of Containers",
            "Container Type", "Sales Port of Loading POL", "Sales Port of Delivery POD", "Sales Place of Receipt", "Sales Final Destination",
            "Requested Shipment Week","Requested Cut off Start Date", "Requested Cut off End Date", "DTHC Prepaid", "Afloat", "Shipment Period Start Date", "Shipment Period End Date",
            "Partial Allowed", "VIP PNL Risk", "PNL Destination", "Required Arrival Date", "LC Received",
            "Allocation Date", "Producer Nomination Date", "First Vessel ETD", "Comments Sales","Sales Owner"]]
 
        return df
    finally:
        if conn:
            conn.close()
 
 #Obter os dados das tabelas principais Booking
#@st.cache_data(ttl=300)
def get_data_bookingData():
    """Executa a consulta SQL, aplica o mapeamento de colunas e retorna um DataFrame formatado."""
    conn = None
 
    # Consulta SQL
    query = '''
    SELECT *
    FROM LogTransp.F_CON_BOOKING_MANAGEMENT
    ORDER BY b_farol_reference'''
 
    try:
        conn = get_database_connection()
        df = pd.read_sql_query(text(query), conn)
 
        # Aplicar o mapeamento de colunas antes de retornar os dados
        column_mapping = get_column_mapping()
        df.rename(columns=column_mapping, inplace=True)
 
        #Filtrando as colunas e definindo a ordem de exibição
        df = df[["Booking Farol Reference", "Booking Status", "Booking Quantity of Containers","Creation Of Booking", "Booking Reference", "Booking Owner",
            "Carrier", "Freight Forwarder", "Booking Request Date", "Booking Confirmation Date",
            "Booking Port of Loading POL","Booking Port of Delivery POD","Booking Place of Receipt","Booking Final Destination",
            "Vessel Name", "Voyage Carrier", "Port Terminal City", "Transhipment Port", "POD Country",
            "POD Country Acronym", "Destination Trade Region", "First Document Cut Off DOCCUT",
            "First Port Cut Off PORTCUT", "First Estimated Time Of Departure ETD",
            "First Estimated Time Of Arrival ETA", "Voyage Port Terminal", "Current Document Cut Off DOCCUT",
            "Current Port Cut Off PORTCUT", "Current Estimated Time Of Departure ETD",
            "Current Estimated Time Of Arrival ETA", "Freight Rate USD", "Bogey Sale Price USD",
            "Freight PNL", "Award Status", "Comments Booking"]]
 
        return df
    finally:
        if conn:
            conn.close()
 
 #Obter os dados das tabelas principais Loading
#@st.cache_data(ttl=300)
def get_data_loadingData():
    """Executa a consulta SQL, aplica o mapeamento de colunas e retorna um DataFrame formatado."""
    conn = None
 
    # Consulta SQL
    query = '''
    SELECT *
    FROM LogTransp.F_CON_CARGO_LOADING_CONTAINER_RELEASE
    ORDER BY l_farol_reference'''
 
    try:
        conn = get_database_connection()
        df = pd.read_sql_query(text(query), conn)
 
        # Aplicar o mapeamento de colunas antes de retornar os dados
        column_mapping = get_column_mapping()
        df.rename(columns=column_mapping, inplace=True)
 
        #Filtrando as colunas e definindo a ordem de exibição
        df = df[["Loading Farol Reference","Truck Loading Status", "Creation Of Cargo Loading", "Logistics Analyst", "Supplier",
            "Stuffing Terminal", "Stuffing Terminal Acceptance", "Drayage Carrier", "Status ITAS", "Truck Loading Farol",
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
 
    # Consulta SQL
    query = '''
    SELECT *
    FROM LogTransp.F_CON_SALES_DATA
    ORDER BY s_farol_reference'''
 
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
@st.cache_data(ttl=3600)
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
                "column_name": row["Coluna"],
                "previous_value": row["Valor Anterior"],
                "new_value": row["Novo Valor"],
                "request_carrier_date": None,
                "confirmation_date": None,
                "process_stage": None,
                "stage": row["Stage"],
                "comments": comment,
                "user_insert": None
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
 
    conn = None
    try:
        conn = get_database_connection()
        transaction = conn.begin()
 
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
                "user_insert": user_insert
            }
            for _, row in changes_df.iterrows()
        ]
 
        insert_query = text("""
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
        conn.execute(insert_query, data_to_insert)
 
        farol_reference = changes_df.iloc[0]["Farol Reference"]
 
        update_sales_query = text("""
            UPDATE LogTransp.F_CON_SALES_DATA
            SET s_shipment_status = :s_shipment_status
            WHERE s_farol_reference = :ref
        """)
        update_booking_query = text("""
            UPDATE LogTransp.F_CON_BOOKING_MANAGEMENT
            SET b_booking_status = :b_booking_status
            WHERE b_farol_reference = :ref
        """)
 
        conn.execute(update_sales_query, {
            "s_shipment_status": "New adjustment",
            "ref": farol_reference
        })
        conn.execute(update_booking_query, {
            "b_booking_status": "New adjustment",
            "ref": farol_reference
        })
 
        transaction.commit()
        return True
    except Exception as e:
        if conn:
            transaction.rollback()
        print(f"Erro ao inserir ajustes críticos no banco de dados: {e}")
        return False
 
    finally:
        if conn:
            conn.close()
 
def insert_adjustments_critic_splits(changes_df, comment, random_uuid, area, reason, responsibility, user_insert=None):
    if changes_df is None or changes_df.empty:
        return False
 
    conn = None
    try:
        conn = get_database_connection()
        transaction = conn.begin()
 
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
                "user_insert": user_insert
            }
            for _, row in changes_df.iterrows()
        ]
 
        insert_query = text("""
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
        conn.execute(insert_query, data_to_insert)
 
        transaction.commit()
        return True
    except Exception as e:
        if conn:
            transaction.rollback()
        print(f"Erro ao inserir ajustes críticos no banco de dados: {e}")
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
 
        # --- INSERT TABELA DE VENDAS ---
        sales_fields = ", ".join(form_values.keys())
        sales_placeholders = ", ".join([f":{key}" for key in form_values.keys()])
        sales_query = text(f"""
            INSERT INTO LogTransp.F_CON_SALES_DATA ({sales_fields})
            VALUES ({sales_placeholders})
        """)
        conn.execute(sales_query, form_values)
 
        # --- INSERT TABELA BOOKING ---
        booking_values = {
            "b_farol_reference": farol_reference,
            "b_quantity_of_containers": form_values.get("s_quantity_of_containers"),
            "b_port_of_loading_pol": form_values.get("s_port_of_loading_pol"),
            "b_port_of_delivery_pod": form_values.get("s_port_of_delivery_pod"),
            "b_final_destination": form_values.get("s_final_destination"),
            "b_booking_status": "New request",
 
        }
 
        booking_fields = ", ".join(booking_values.keys())
        booking_placeholders = ", ".join([f":{key}" for key in booking_values.keys()])
        booking_query = text(f"""
            INSERT INTO LogTransp.F_CON_BOOKING_MANAGEMENT ({booking_fields})
            VALUES ({booking_placeholders})
        """)
        conn.execute(booking_query, booking_values)
 
        # --- INSERT TABELA CONTAINER RELEASE ---
        cargo_values = {
            "l_farol_reference": farol_reference,
            "l_truck_loading_status": "New request",
 
        }
 
        cargo_fields = ", ".join(cargo_values.keys())
        cargo_placeholders = ", ".join([f":{key}" for key in cargo_values.keys()])
        cargo_query = text(f"""
            INSERT INTO LogTransp.F_CON_CARGO_LOADING_CONTAINER_RELEASE ({cargo_fields})
            VALUES ({cargo_placeholders})
        """)
        conn.execute(cargo_query, cargo_values)
 
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
    date_str = date.strftime('%y%b').upper()  # Formato: 23NOV (ano com 2 dígitos + mês em maiúsculo)
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
                seq_str = parts[-1]  # Pega o último elemento após o split
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
def perform_split_operation(farol_ref_original, edited_display, num_splits, comment, area, reason, responsibility, user_insert=None):
    conn = get_database_connection()
    reverse_map = get_reverse_mapping()
    new_farol_references = []
 
    # Etapa 1: Consultar registros originais uma vez
    sales = pd.read_sql(text("SELECT * FROM LogTransp.F_CON_SALES_DATA WHERE s_farol_reference = :ref"), conn, params={"ref": farol_ref_original})
    booking = pd.read_sql(text("SELECT * FROM LogTransp.F_CON_BOOKING_MANAGEMENT WHERE b_farol_reference = :ref"), conn, params={"ref": farol_ref_original})
    loading = pd.read_sql(text("SELECT * FROM LogTransp.F_CON_CARGO_LOADING_CONTAINER_RELEASE WHERE l_farol_reference = :ref"), conn, params={"ref": farol_ref_original})
 
    insert_sales = []
    insert_booking = []
    insert_loading = []
    insert_logs = []
 
    for i, (_, row) in enumerate(edited_display.iterrows()):
        if i == 0:
            continue  # pular linha original
 
        new_ref = row["Sales Farol Reference"]
        new_farol_references.append(new_ref)
 
        # Copiar e modificar os dados
        sales_copy = sales.copy()
        booking_copy = booking.copy()
        loading_copy = loading.copy()
 
        for df, ref_key, prefix in [
            (sales_copy, reverse_map["Sales Farol Reference"], "Sales"),
            (booking_copy, reverse_map["Booking Farol Reference"], "Booking"),
            (loading_copy, reverse_map["Loading Farol Reference"], "Loading"),
        ]:
            df.at[0, ref_key] = new_ref
            for ui_label, value in row.items():
                label = ui_label.replace("Sales", prefix)
                col = reverse_map.get(label)
                if col and col in df.columns:
                    df.at[0, col] = value
 
        new_adjustment_id = str(uuid.uuid4())
        sales_copy.at[0, "adjustment_id"] = new_adjustment_id
        booking_copy.at[0, "adjustment_id"] = new_adjustment_id
        loading_copy.at[0, "adjustment_id"] = new_adjustment_id
 
        sales_copy.at[0, "s_creation_of_shipment"] = datetime.now()
        booking_copy = booking_copy.drop(columns=["b_creation_of_booking"], errors="ignore")
        sales_copy.at[0, "s_type_of_shipment"] = "Split"
 
        sales_dict = sales_copy.iloc[0].to_dict()
        booking_dict = booking_copy.iloc[0].to_dict()
        loading_dict = loading_copy.iloc[0].to_dict()
 
        sales_dict.pop("s_id", None)
        booking_dict.pop("b_id", None)
        loading_dict.pop("l_id", None)
 
        insert_sales.append(sales_dict)
        insert_booking.append(booking_dict)
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
    for data in insert_sales:
        insert_table("LogTransp.F_CON_SALES_DATA", data, conn)
    for data in insert_booking:
        insert_table("LogTransp.F_CON_BOOKING_MANAGEMENT", data, conn)
    for data in insert_loading:
        insert_table("LogTransp.F_CON_CARGO_LOADING_CONTAINER_RELEASE", data, conn)
    for df, data in zip(insert_logs, insert_sales):
        insert_adjustments_critic_splits(df, comment, data.get("adjustment_id"), area, reason, responsibility, user_insert)
 
    conn.commit()
    conn.close()
    return new_farol_references
 
 
 
def insert_table(full_table_name, row_dict, conn):
    cols = ", ".join(row_dict.keys())
    vals = ", ".join([f":{key}" for key in row_dict])
    sql = f"INSERT INTO {full_table_name} ({cols}) VALUES ({vals})"
    conn.execute(text(sql), row_dict)
 
 
 
# --- CONSULTA UNIFICADA ---
def get_merged_data():
    query = """
SELECT
    s.s_farol_reference,
    s.s_shipment_status,
    s.s_type_of_shipment,
    MAX(a.responsible_name) AS "Responsible Name",
    MAX(a.area) AS "Area",
    MAX(a.status) AS "Status",
    MAX(a.request_carrier_date) AS "Booking Adjustment Request Date",
    MAX(a.confirmation_date) AS "Booking Adjustment Confirmation Date",
    MAX(a.row_inserted_date) AS row_inserted_date,
    LISTAGG(
        'Alterar o campo ' || a.column_name || ' de ' || a.previous_value || ' para ' || a.new_value || '/',
        CHR(10)
    ) WITHIN GROUP (ORDER BY a.column_name) AS ajuste
FROM
    LogTransp.VW_CON_Sales_Booking_Loading_Container s
LEFT JOIN (
    SELECT
        adjustment_id,
        farol_reference,
        responsible_name,
        area,
        column_name,
        previous_value,
        new_value,
        status,
        request_carrier_date,
        confirmation_date,
        row_inserted_date
    FROM
        LogTransp.F_CON_Adjustments_Log
    WHERE
        request_type = 'Critic'
) a
ON s.s_farol_reference = a.farol_reference
GROUP BY
    s.s_farol_reference,
    s.s_shipment_status,
    s.s_type_of_shipment
    """
 
    with get_database_connection() as conn:
        df = pd.read_sql_query(text(query), conn)
        df.rename(columns=get_column_mapping(), inplace=True)
        return df
   
 
#Função utilizada para preencher os dados no formulário para a referência selecionada
def get_booking_data_by_farol_reference(farol_reference): #Utilizada no arquivo booking_new.py
    conn = get_database_connection()
    try:
        query = """
        SELECT b_booking_status, b_carrier, b_freight_forwarder, b_booking_request_date, b_comments
        FROM LogTransp.F_CON_BOOKING_MANAGEMENT
        WHERE b_farol_reference = :ref
        """
        result = conn.execute(text(query), {"ref": farol_reference}).mappings().fetchone()
        return result if result else None
    finally:
        conn.close()
 
#Função utilizada para atualizar os dados da tabela de booking
def update_booking_data_by_farol_reference(farol_reference, values):#Utilizada no arquivo booking_new.py
    conn = get_database_connection()
    try:
        query = """
        UPDATE LogTransp.F_CON_BOOKING_MANAGEMENT
        SET b_booking_status = :b_booking_status,
            b_carrier = :b_carrier,
            b_creation_of_booking = :b_creation_of_booking,
            b_freight_forwarder = :b_freight_forwarder,
            b_booking_request_date = :b_booking_request_date,
            b_comments = :b_comments
        WHERE b_farol_reference = :ref
        """
 
        # Atualiza a tabela de Sales Data
        query_sales = """
        UPDATE LogTransp.F_CON_SALES_DATA
        SET s_shipment_status = :s_shipment_status
        WHERE s_farol_reference = :ref
        """
        # Executa ambas as queries
        conn.execute(
            text(query),
            {
                "b_booking_status": "Booking requested", #values["b_booking_status"]
                "b_creation_of_booking": datetime.now(),
                "b_carrier": values["b_carrier"],
                "b_freight_forwarder": values["b_freight_forwarder"],
                "b_booking_request_date": values["b_booking_request_date"],
                "b_comments": values["b_comments"],
                "ref": farol_reference,
            },
        )
 
        conn.execute(
            text(query_sales),
            {
                "s_shipment_status": "Booking requested",
                "ref": farol_reference,
            },
        )
   
        conn.commit()
    finally:
        conn.close()
 
 
#Função utilizada para preencher os dados no formulário para a referência selecionada
def get_split_data_by_farol_reference(farol_reference):
    """Executa a consulta SQL para obter dados específicos para splits."""
    conn = get_database_connection()
    try:
        query = """
        SELECT
            s.s_farol_reference,
            s.s_quantity_of_containers,
            s.s_volume_in_tons,
            s.s_customer,
            s.s_sales_order_reference,
            s.s_port_of_loading_pol,
            s.s_port_of_delivery_pod,
            s.s_place_of_receipt,
            s.s_final_destination,
            s.s_shipment_status,
            s.s_requested_deadlines_start_date,
            s.s_requested_deadlines_end_date,
            s.s_required_arrival_date,
            s.s_carrier
        FROM LogTransp.F_CON_SALES_DATA s
        WHERE s.s_farol_reference = :ref
        """
        result = conn.execute(text(query), {"ref": farol_reference}).mappings().fetchone()
        return result if result else None
    finally:
        conn.close()
 