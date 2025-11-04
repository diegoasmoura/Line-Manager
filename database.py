## database.py

import os
import streamlit as st
from sqlalchemy import create_engine, text
import pandas as pd
from shipments_mapping import get_column_mapping, get_reverse_mapping, process_farol_status_for_display
from datetime import datetime
import uuid
 
# Data e hora atuais
now = datetime.now()

def get_brazil_time():
    """Retorna o horário atual no fuso horário do Brasil (UTC-3)"""
    import pytz
    brazil_tz = pytz.timezone('America/Sao_Paulo')
    return datetime.now(brazil_tz)

# ==============================================
# FUNÇÕES DE AUDITORIA E TRILHA DE MUDANÇAS
# ==============================================

def get_current_user_login() -> str:
    """Obtém o usuário logado no app; fallback para variável de ambiente ou 'system'."""
    try:
        u = st.session_state.get("current_user")
        if u and str(u).strip():
            return str(u)[:150]
    except Exception:
        pass
    import os
    return (os.getenv("USER") or "system")[:150]

# Formato ISO para normalizar datas em texto
ISO_FMT = "%Y-%m-%d %H:%M:%S"

def clean_none_values_from_dataframe(df):
    """
    Remove valores "None", "nan", "<NA>", "NaT" de colunas de texto no DataFrame.
    Preserva valores numéricos e datas.
    
    Args:
        df: DataFrame do pandas
        
    Returns:
        DataFrame com valores None substituídos por strings vazias em colunas de texto
    """
    if df.empty:
        return df
    
    df_cleaned = df.copy()
    
    for col in df_cleaned.columns:
        # Verificar se é coluna de data/hora
        if pd.api.types.is_datetime64_any_dtype(df_cleaned[col]):
            # Para colunas de data: converter None/NaT mas manter tipo datetime
            continue  # Não alterar colunas de data, deixar como está
        elif pd.api.types.is_numeric_dtype(df_cleaned[col]):
            # Não alterar colunas numéricas
            continue
        else:
            # Para colunas de texto/objeto: limpar valores None
            df_cleaned[col] = df_cleaned[col].fillna('').astype(str).replace('None', '').replace('nan', '').replace('<NA>', '').replace('NaT', '')
    
    return df_cleaned

def _normalize_value_for_log(value):
    """Converte diferentes tipos (None/NaT/datetime/number) para texto estável."""
    try:
        import pandas as pd
        if value is None or (hasattr(pd, 'isna') and pd.isna(value)):
            return 'NULL'
        # pandas.Timestamp ou datetime
        if hasattr(value, 'to_pydatetime'):
            value = value.to_pydatetime()
        import datetime as _dt
        if isinstance(value, (_dt.datetime,)):
            return value.strftime(ISO_FMT)
        if isinstance(value, (_dt.date,)):
            return f"{value.strftime('%Y-%m-%d')} 00:00:00"
        return str(value)[:1000]
    except Exception:
        return str(value)[:1000] if value is not None else 'NULL'

def begin_change_batch(optional_uuid=None) -> str:
    """Inicia um novo batch de mudanças com UUID único.
    Retorna o UUID do batch (novo ou reutilizado)."""
    import uuid
    if optional_uuid:
        batch_id = str(optional_uuid)
    else:
        batch_id = str(uuid.uuid4())
    
    try:
        st.session_state['change_batch_id'] = batch_id
    except Exception:
        # Fallback se session_state não estiver disponível
        pass
    
    return batch_id

def get_current_change_batch_id() -> str | None:
    """Obtém o ID do batch atual de mudanças."""
    try:
        return st.session_state.get('change_batch_id')
    except Exception:
        return None

def end_change_batch() -> None:
    """Limpa o batch atual de mudanças da sessão."""
    try:
        st.session_state.pop('change_batch_id', None)
    except Exception:
        pass

def audit_change(conn, farol_ref: str, table: str, column: str,
                 old, new, source: str,
                 change_type: str = 'UPDATE',
                 user: str | None = None,
                 adjustment_id: str | None = None,
                 related_ref: str | None = None) -> None:
    """Registra 1 linha por coluna alterada na F_CON_CHANGE_LOG.
    Deve ser chamado dentro da mesma transação do UPDATE/INSERT.
    """
    old_str = _normalize_value_for_log(old)
    new_str = _normalize_value_for_log(new)
    if old_str == new_str:
        return
    user_login = (user or get_current_user_login())[:150]
    
    # Se não foi fornecido adjustment_id, usar o batch atual
    if adjustment_id is None:
        adjustment_id = get_current_change_batch_id()
    
    conn.execute(text(
        """
        INSERT INTO LogTransp.F_CON_CHANGE_LOG
          (FAROL_REFERENCE, TABLE_NAME, COLUMN_NAME, OLD_VALUE, NEW_VALUE,
           USER_LOGIN, CHANGE_SOURCE, CHANGE_TYPE, ADJUSTMENT_ID, RELATED_REFERENCE)
        VALUES (:fr, :tbl, :col, :old, :new, :user, :src, :type, :adj, :rel)
        """
    ), {
        "fr": farol_ref, "tbl": table, "col": column,
        "old": old_str, "new": new_str,
        "user": user_login, "src": source, "type": change_type,
        "adj": adjustment_id, "rel": related_ref,
    })

def update_field_in_sales_booking_data(conn, farol_reference: str, column_name: str, new_value):
    """
    Atualiza um campo específico na tabela F_CON_SALES_BOOKING_DATA.
    Também atualiza automaticamente o Farol Status quando campos específicos são preenchidos.
    
    Args:
        conn: Conexão com o banco de dados
        farol_reference: Referência Farol do registro
        column_name: Nome técnico da coluna no banco (em UPPER CASE, ex: S_QUANTITY_OF_CONTAINERS)
        new_value: Novo valor a ser atualizado
    """
    # Buscar valores atuais antes de atualizar (para verificação de regras automáticas)
    current_values_query = text("""
        SELECT FAROL_STATUS, B_DATA_CONFIRMACAO_EMBARQUE, B_DATA_CHEGADA_DESTINO_ATA
        FROM LogTransp.F_CON_SALES_BOOKING_DATA
        WHERE FAROL_REFERENCE = :farol_ref
    """)
    current_row = conn.execute(current_values_query, {"farol_ref": farol_reference}).fetchone()
    
    old_field_value = None
    old_farol_status = None
    if current_row:
        old_farol_status = current_row[0]
        if column_name == "B_DATA_CONFIRMACAO_EMBARQUE":
            old_field_value = current_row[1]
        elif column_name == "B_DATA_CHEGADA_DESTINO_ATA":
            old_field_value = current_row[2]
    
    # Nome da coluna já deve vir no formato técnico (UPPER CASE)
    # Não precisa de aspas duplas pois não tem espaços
    update_sql = text(f"""
        UPDATE LogTransp.F_CON_SALES_BOOKING_DATA
        SET {column_name} = :new_value
        WHERE FAROL_REFERENCE = :farol_reference
    """)
    conn.execute(update_sql, {
        "new_value": new_value,
        "farol_reference": farol_reference
    })
    
    # Regras automáticas de atualização do Farol Status
    # Verificar se campo estava NULL e agora está preenchido
    field_was_null = old_field_value is None or (hasattr(pd, 'isna') and pd.isna(old_field_value))
    field_is_now_filled = new_value is not None and not (hasattr(pd, 'isna') and pd.isna(new_value))
    
    # Regra de exceção: não atualizar automaticamente se status for inicial
    protected_statuses = ["New Request", "Booking Requested"]
    status_is_protected = old_farol_status is not None and str(old_farol_status).strip() in protected_statuses
    
    # Regra 1: Se B_DATA_CONFIRMACAO_EMBARQUE foi preenchido, atualizar para "Shipped"
    if column_name == "B_DATA_CONFIRMACAO_EMBARQUE" and field_was_null and field_is_now_filled and not status_is_protected:
        new_status = "Shipped"
        if old_farol_status != new_status:
            # Atualizar Farol Status
            status_update_sql = text("""
                UPDATE LogTransp.F_CON_SALES_BOOKING_DATA
                SET FAROL_STATUS = :new_status, DATE_UPDATE = SYSDATE
                WHERE FAROL_REFERENCE = :farol_ref
            """)
            conn.execute(status_update_sql, {
                "new_status": new_status,
                "farol_ref": farol_reference
            })
            # Registrar na auditoria
            audit_change(
                conn, farol_reference, 'F_CON_SALES_BOOKING_DATA', 'FAROL_STATUS',
                old_farol_status, new_status, 'AUTO_STATUS_UPDATE', 'UPDATE'
            )
    
    # Regra 2: Se B_DATA_CHEGADA_DESTINO_ATA foi preenchido, atualizar para "Arrived at destination"
    elif column_name == "B_DATA_CHEGADA_DESTINO_ATA" and field_was_null and field_is_now_filled and not status_is_protected:
        new_status = "Arrived at destination"
        if old_farol_status != new_status:
            # Atualizar Farol Status
            status_update_sql = text("""
                UPDATE LogTransp.F_CON_SALES_BOOKING_DATA
                SET FAROL_STATUS = :new_status, DATE_UPDATE = SYSDATE
                WHERE FAROL_REFERENCE = :farol_ref
            """)
            conn.execute(status_update_sql, {
                "new_status": new_status,
                "farol_ref": farol_reference
            })
            # Registrar na auditoria
            audit_change(
                conn, farol_reference, 'F_CON_SALES_BOOKING_DATA', 'FAROL_STATUS',
                old_farol_status, new_status, 'AUTO_STATUS_UPDATE', 'UPDATE'
            )
 
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

def create_adjustment_requested_timeline_record(conn, farol_ref, user_id):
    """
    Creates a new record in F_CON_RETURN_CARRIERS when the status of a shipment
    is manually changed from 'New Adjustment' to 'Adjustment Requested'.

    Esta função busca os dados da última linha anterior em F_CON_RETURN_CARRIERS
    (não da tabela principal) porque a tabela principal pode não ter os dados mais
    atualizados ainda neste ponto do fluxo.

    Args:
        conn: The database connection object.
        farol_ref (str): The Farol Reference of the shipment.
        user_id (str): The ID of the user performing the action.

    Returns:
        bool: True if the record was created successfully, False otherwise.
    """
    try:
        # 1. Buscar última linha anterior em F_CON_RETURN_CARRIERS
        fetch_query = text("""
            SELECT
                S_QUANTITY_OF_CONTAINERS, S_PORT_OF_LOADING_POL, S_PORT_OF_DELIVERY_POD,
                S_PLACE_OF_RECEIPT, S_FINAL_DESTINATION, B_TERMINAL, B_VOYAGE_CARRIER,
                B_VESSEL_NAME, B_VOYAGE_CODE, B_BOOKING_REFERENCE, B_DATA_DRAFT_DEADLINE,
                B_DATA_DEADLINE, S_REQUESTED_DEADLINE_START_DATE, S_REQUESTED_DEADLINE_END_DATE,
                S_REQUIRED_ARRIVAL_DATE_EXPECTED, B_DATA_ESTIMATIVA_SAIDA_ETD,
                B_DATA_ESTIMATIVA_CHEGADA_ETA, B_DATA_ABERTURA_GATE, B_DATA_CONFIRMACAO_EMBARQUE,
                B_DATA_PARTIDA_ATD, B_DATA_ESTIMADA_TRANSBORDO_ETD, B_DATA_CHEGADA_ATA,
                B_DATA_TRANSBORDO_ATD, B_DATA_CHEGADA_DESTINO_ETA, B_DATA_CHEGADA_DESTINO_ATA,
                B_DATA_ESTIMATIVA_ATRACACAO_ETB, B_DATA_ATRACACAO_ATB,
                B_TRANSHIPMENT_PORT
            FROM LogTransp.F_CON_RETURN_CARRIERS
            WHERE FAROL_REFERENCE = :farol_ref
            ORDER BY ROW_INSERTED_DATE DESC
            FETCH FIRST 1 ROWS ONLY
        """)
        source_data = conn.execute(fetch_query, {"farol_ref": farol_ref}).mappings().fetchone()

        # Fallback: Se não encontrar na F_CON_RETURN_CARRIERS, busca da tabela principal
        if not source_data:
            fetch_query_fallback = text("""
                SELECT
                    S_QUANTITY_OF_CONTAINERS, S_PORT_OF_LOADING_POL, S_PORT_OF_DELIVERY_POD,
                    S_PLACE_OF_RECEIPT, S_FINAL_DESTINATION, B_TERMINAL, B_VOYAGE_CARRIER,
                    B_VESSEL_NAME, B_VOYAGE_CODE, B_BOOKING_REFERENCE, B_DATA_DRAFT_DEADLINE,
                    B_DATA_DEADLINE, S_REQUESTED_DEADLINE_START_DATE, S_REQUESTED_DEADLINE_END_DATE,
                    S_REQUIRED_ARRIVAL_DATE_EXPECTED, B_DATA_ESTIMATIVA_SAIDA_ETD,
                    B_DATA_ESTIMATIVA_CHEGADA_ETA, B_DATA_ABERTURA_GATE, B_DATA_CONFIRMACAO_EMBARQUE,
                    B_DATA_PARTIDA_ATD, B_DATA_ESTIMADA_TRANSBORDO_ETD, B_DATA_CHEGADA_ATA,
                    B_DATA_TRANSBORDO_ATD, B_DATA_CHEGADA_DESTINO_ETA, B_DATA_CHEGADA_DESTINO_ATA,
                    B_DATA_ESTIMATIVA_ATRACACAO_ETB, B_DATA_ATRACACAO_ATB,
                    B_TRANSHIPMENT_PORT
                FROM LogTransp.F_CON_SALES_BOOKING_DATA
                WHERE FAROL_REFERENCE = :farol_ref
            """)
            source_data = conn.execute(fetch_query_fallback, {"farol_ref": farol_ref}).mappings().fetchone()
            
            if not source_data:
                # If no data is found in either table, we cannot proceed.
                return False

        # 2. Prepare the dictionary for the new record
        record_data = {
            "FAROL_REFERENCE": farol_ref,
            "FAROL_STATUS": "Adjustment Requested",
            "P_STATUS": "Manual Adjustment Request",
            "COMMENTS": f"Status changed manually from 'New Adjustment' to 'Adjustment Requested' by {user_id}",
            "USER_INSERT": user_id,
            "ADJUSTMENT_ID": str(uuid.uuid4()),
            "ROW_INSERTED_DATE": get_brazil_time(),
            **source_data
        }

        # 3. Insert the new record into F_CON_RETURN_CARRIERS
        columns = ", ".join(record_data.keys())
        placeholders = ", ".join([f":{col}" for col in record_data.keys()])
        
        insert_sql = text(f"""
            INSERT INTO LogTransp.F_CON_RETURN_CARRIERS ({columns})
            VALUES ({placeholders})
        """)
        
        conn.execute(insert_sql, record_data)
        
        return True

    except Exception as e:
        # Log the error, but don't crash the application
        print(f"Error in create_adjustment_requested_timeline_record: {e}")
        return False


def ensure_ellox_monitoring_id_column(conn):
    """
    Verifica se a coluna ELLOX_MONITORING_ID existe em F_CON_RETURN_CARRIERS e a adiciona se não existir.
    """
    try:
        # Verifica se a coluna já existe
        check_column_query = text("""
            SELECT COUNT(*)
            FROM ALL_TAB_COLUMNS
            WHERE OWNER = UPPER('LOGTRANSP') -- Ou o schema correto se for diferente
              AND TABLE_NAME = UPPER('F_CON_RETURN_CARRIERS')
              AND COLUMN_NAME = UPPER('ELLOX_MONITORING_ID')
        """)
        result = conn.execute(check_column_query).scalar()

        if result == 0:
            # Adiciona a coluna se não existir
            add_column_query = text("""
                ALTER TABLE LogTransp.F_CON_RETURN_CARRIERS
                ADD ELLOX_MONITORING_ID NUMBER(20) NULL
            """)
            conn.execute(add_column_query)
            conn.commit()
            st.success("✅ Coluna ELLOX_MONITORING_ID adicionada a F_CON_RETURN_CARRIERS.")
        # else:
            # st.info("Coluna ELLOX_MONITORING_ID já existe em F_CON_RETURN_CARRIERS.")
    except Exception as e:
        st.error(f"❌ Erro ao verificar/adicionar coluna ELLOX_MONITORING_ID: {str(e)}")
        conn.rollback() # Rollback any pending changes if an error occurs

def check_for_existing_monitoring(conn, vessel_name: str, voyage_code: str, terminal: str) -> int | None:
    """
    Verifica se já existe um registro de monitoramento em F_ELLOX_TERMINAL_MONITORINGS
    com base no navio, viagem e terminal.
    Retorna o ID do registro se encontrado, ou None.
    """
    try:
        query = text("""
            SELECT ID
            FROM LogTransp.F_ELLOX_TERMINAL_MONITORINGS
            WHERE UPPER(NAVIO) = UPPER(:vessel_name)
              AND UPPER(VIAGEM) = UPPER(:voyage_code)
              AND UPPER(TERMINAL) = UPPER(:terminal)
            ORDER BY ROW_INSERTED_DATE DESC -- Pega o mais recente se houver múltiplos
            FETCH FIRST 1 ROWS ONLY
        """)
        result = conn.execute(query, {
            "vessel_name": vessel_name,
            "voyage_code": voyage_code,
            "terminal": terminal
        }).scalar()
        return result
    except Exception as e:
        st.error(f"❌ Erro ao verificar monitoramento existente: {str(e)}")
        return None

def update_return_carrier_monitoring_id(conn, adjustment_id: str, monitoring_id: int) -> bool:
    """
    Atualiza a coluna ELLOX_MONITORING_ID na tabela F_CON_RETURN_CARRIERS
    para vincular o registro de retorno ao monitoramento de viagem.
    
    Args:
        conn: Conexão com o banco de dados
        adjustment_id: ID do ajuste na F_CON_RETURN_CARRIERS
        monitoring_id: ID do registro em F_ELLOX_TERMINAL_MONITORINGS
        
    Returns:
        bool: True se a atualização foi bem-sucedida, False caso contrário
    """
    import time
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            print(f"🔍 DEBUG: update_return_carrier_monitoring_id - attempt {attempt + 1}/{max_retries} - adjustment_id: {adjustment_id}, monitoring_id: {monitoring_id}")
            update_query = text("""
                UPDATE LogTransp.F_CON_RETURN_CARRIERS
                SET ELLOX_MONITORING_ID = :monitoring_id,
                    USER_UPDATE = 'System',
                    DATE_UPDATE = SYSDATE
                WHERE ADJUSTMENT_ID = :adjustment_id
            """)
            
            print(f"🔍 DEBUG: Executando query de update...")
            result = conn.execute(update_query, {
                "monitoring_id": monitoring_id,
                "adjustment_id": adjustment_id
            })
            print(f"🔍 DEBUG: Query executada com sucesso, rowcount: {result.rowcount}")
            
            # Verifica se a atualização afetou alguma linha
            if result.rowcount > 0:
                print(f"🔍 DEBUG: Update bem-sucedido, retornando True")
                return True
            else:
                print(f"🔍 DEBUG: Nenhum registro encontrado, retornando False")
                st.warning(f"⚠️ Nenhum registro encontrado com ADJUSTMENT_ID: {adjustment_id}")
                return False
                
        except Exception as e:
            print(f"🔍 DEBUG: Erro na tentativa {attempt + 1}: {str(e)}")
            if attempt < max_retries - 1:
                print(f"🔍 DEBUG: Aguardando {retry_delay} segundos antes da próxima tentativa...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                print(f"🔍 DEBUG: Todas as tentativas falharam")
                st.error(f"❌ Erro ao vincular monitoramento de viagem após {max_retries} tentativas: {str(e)}")
                return False

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
                            FAROL_STATUS,
                            P_STATUS,
                            P_PDF_NAME,
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
                            B_DATA_CONFIRMACAO_EMBARQUE,
                            B_DATA_PARTIDA_ATD,
                            B_DATA_ESTIMADA_TRANSBORDO_ETD,
                            B_DATA_CHEGADA_ATA,
                            B_DATA_TRANSBORDO_ATD,
                            B_DATA_CHEGADA_DESTINO_ETA,
                            B_DATA_CHEGADA_DESTINO_ATA,
                            B_DATA_ESTIMATIVA_ATRACACAO_ETB,
                            B_DATA_ATRACACAO_ATB,
                            USER_INSERT,
                            USER_UPDATE,
                            DATE_UPDATE,
                            ROW_INSERTED_DATE,
                            PDF_BOOKING_EMISSION_DATE,
                            AREA,
                            REQUEST_REASON,
                            ADJUSTMENTS_OWNER,
                            COMMENTS,
                            ELLOX_MONITORING_ID
                        FROM LogTransp.F_CON_RETURN_CARRIERS
            WHERE UPPER(FAROL_REFERENCE) = UPPER(:ref)
            ORDER BY ROW_INSERTED_DATE DESC
            """
        )
        rows = conn.execute(query, {"ref": farol_reference}).mappings().fetchall()
        df = pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()
        if not df.empty:
            df.columns = [str(c).upper() for c in df.columns]
            
            # Converter colunas de data/hora para datetime
            datetime_columns = [
                'B_DATA_DRAFT_DEADLINE', 'B_DATA_DEADLINE', 'B_DATA_ESTIMATIVA_SAIDA_ETD', 
                'B_DATA_ESTIMATIVA_CHEGADA_ETA', 'B_DATA_ABERTURA_GATE', 'B_DATA_CONFIRMACAO_EMBARQUE',
                'B_DATA_PARTIDA_ATD', 'B_DATA_ESTIMADA_TRANSBORDO_ETD', 'B_DATA_CHEGADA_ATA', 
                'B_DATA_TRANSBORDO_ATD', 'B_DATA_CHEGADA_DESTINO_ETA', 'B_DATA_CHEGADA_DESTINO_ATA',
                'B_DATA_ESTIMATIVA_ATRACACAO_ETB', 'B_DATA_ATRACACAO_ATB',
                'S_REQUESTED_DEADLINE_START_DATE', 'S_REQUESTED_DEADLINE_END_DATE', 
                'S_REQUIRED_ARRIVAL_DATE_EXPECTED', 'ROW_INSERTED_DATE', 'PDF_BOOKING_EMISSION_DATE'
            ]
            
            for col in datetime_columns:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')
                    
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
                FAROL_STATUS,
                P_STATUS,
                P_PDF_NAME,
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
                B_DATA_CONFIRMACAO_EMBARQUE,
                B_DATA_PARTIDA_ATD,
                B_DATA_ESTIMADA_TRANSBORDO_ETD,
                B_DATA_CHEGADA_ATA,
                B_DATA_TRANSBORDO_ATD,
                B_DATA_ESTIMATIVA_ATRACACAO_ETB,
                B_DATA_ATRACACAO_ATB,
                USER_INSERT,
                USER_UPDATE,
                DATE_UPDATE,
                ROW_INSERTED_DATE,
                PDF_BOOKING_EMISSION_DATE,
                ADJUSTMENTS_OWNER,
                ELLOX_MONITORING_ID
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

# --- HISTORY WRAPPERS (centraliza ponto de acesso) ---
# Nota: enquanto as queries específicas do History permanecem em history_data.py,
# disponibilizamos wrappers aqui para padronizar o consumo a partir de database.py
# sem alterar o comportamento atual da aplicação.
try:
    # Import local para evitar ciclos de import no carregamento inicial
    from history_data import (
        get_main_table_data as _history_get_main_table_data,
        get_voyage_monitoring_for_reference as _history_get_voyage_monitoring_for_reference,
        get_available_references_for_relation as _history_get_available_references_for_relation,
        save_attachment_to_db as _history_save_attachment_to_db,
        get_attachments_for_farol as _history_get_attachments_for_farol,
        delete_attachment as _history_delete_attachment,
        get_attachment_content as _history_get_attachment_content,
        get_next_linked_reference_number as _history_get_next_linked_reference_number,
        get_referenced_line_data as _history_get_referenced_line_data,
    )
except Exception as e:
    # Em contextos de import parcial (linters/tests), ignorar falhas transitórias
    _history_get_main_table_data = None
    _history_get_voyage_monitoring_for_reference = None
    _history_get_available_references_for_relation = None
    _history_save_attachment_to_db = None
    _history_get_attachments_for_farol = None
    _history_delete_attachment = None
    _history_get_attachment_content = None
    _history_get_next_linked_reference_number = None
    _history_get_referenced_line_data = None


def history_get_main_table_data(farol_ref):
    return _history_get_main_table_data(farol_ref) if _history_get_main_table_data else None


def history_get_voyage_monitoring_for_reference(farol_reference):
    return (
        _history_get_voyage_monitoring_for_reference(farol_reference)
        if _history_get_voyage_monitoring_for_reference
        else pd.DataFrame()
    )


def history_get_available_references_for_relation(farol_reference=None):
    if _history_get_available_references_for_relation is None:
        return []
    try:
        return _history_get_available_references_for_relation(farol_reference)
    except Exception as e:
        return []


def history_save_attachment(farol_reference, uploaded_file, user_id="system"):
    return (
        _history_save_attachment_to_db(farol_reference, uploaded_file, user_id)
        if _history_save_attachment_to_db
        else False
    )


def history_get_attachments(farol_reference):
    return (
        _history_get_attachments_for_farol(farol_reference)
        if _history_get_attachments_for_farol
        else pd.DataFrame()
    )


def history_delete_attachment(attachment_id, deleted_by="system"):
    return (
        _history_delete_attachment(attachment_id, deleted_by)
        if _history_delete_attachment
        else False
    )


def history_get_attachment_content(attachment_id):
    return (
        _history_get_attachment_content(attachment_id)
        if _history_get_attachment_content
        else (None, None, None)
    )


def history_get_next_linked_reference_number(farol_reference=None):
    return (
        _history_get_next_linked_reference_number(farol_reference)
        if _history_get_next_linked_reference_number
        else (f"{farol_reference}-R01" if farol_reference else 1)
    )


def history_get_referenced_line_data(linked_ref):
    return _history_get_referenced_line_data(linked_ref) if _history_get_referenced_line_data else None
 
#Obter os dados das tabelas principais Sales
#@st.cache_data(ttl=300)
def get_data_salesData(page_number: int = 1, page_size: int = 25, all_rows: bool = False):
    """Executa a consulta SQL com paginação, aplica o mapeamento de colunas e retorna um DataFrame formatado e o total de registros."""
    conn = None
    offset = (page_number - 1) * page_size

    # Consulta SQL (com ou sem paginação), ordenada pelos mais recentes
    base_query = '''
    SELECT 
        FAROL_REFERENCE                    AS s_farol_reference,
        COALESCE(FAROL_STATUS, 'New Request') AS s_farol_status,
        FAROL_STATUS                         AS farol_status,
        S_SHIPMENT_STATUS                  AS s_shipment_status,
        S_TYPE_OF_SHIPMENT                 AS s_type_of_shipment,
        S_CREATION_OF_SHIPMENT             AS s_creation_of_shipment,
        B_BOOKING_REFERENCE                AS b_booking_reference,
        S_CUSTOMER_PO                      AS s_customer_po,
        S_SALE_ORDER_REFERENCE             AS s_sales_order_reference,
        S_SALE_ORDER_DATE                  AS s_sales_order_date,
        S_BUSINESS                         AS s_business,
        S_CUSTOMER                         AS s_customer,
        S_MODE                             AS s_mode,
        S_INCOTERM                         AS s_incoterm,
        S_SKU                              AS s_sku,
        S_PLANT_OF_ORIGIN                  AS s_plant_of_origin,
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
        S_REQUIRED_SAIL_DATE               AS s_required_sail_date,
        S_REQUIRED_ARRIVAL_DATE_EXPECTED   AS s_required_arrival_date_expected,
        S_REQUESTED_DEADLINE_START_DATE    AS s_requested_deadlines_start_date,
        S_REQUESTED_DEADLINE_END_DATE      AS s_requested_deadlines_end_date,
        S_PARTIAL_ALLOWED                  AS s_partial_allowed,
        S_VIP_PNL_RISK                     AS s_vip_pnl_risk,
        S_PNL_DESTINATION                  AS s_pnl_destination,
        S_LC_RECEIVED                      AS s_lc_received,
        S_ALLOCATION_DATE                  AS s_allocation_date,
        S_PRODUCER_NOMINATION_DATE         AS s_producer_nomination_date,
        USER_LOGIN_SALES_CREATED           AS s_sales_owner,
        S_COMMENTS                         AS s_comments
    FROM LogTransp.F_CON_SALES_BOOKING_DATA
    ORDER BY FAROL_REFERENCE DESC'''

    if all_rows:
        query = base_query
    else:
        query = base_query + f"\nOFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY"

    count_query = 'SELECT COUNT(*) FROM LogTransp.F_CON_SALES_BOOKING_DATA'

    try:
        conn = get_database_connection()
        df = pd.read_sql_query(text(query), conn)
        total_records = conn.execute(text(count_query)).scalar() or 0

        # Aplicar o mapeamento de colunas antes de retornar os dados
        column_mapping = get_column_mapping()
        df.rename(columns=column_mapping, inplace=True)
        
        # Filtrando as colunas e definindo a ordem de exibição (alinhada entre ratios)
        desired_cols_sales = [
            # Identificação
            "Sales Farol Reference", "Farol Status", "Type of Shipment", "Booking Status", "Booking Reference",
            # Capacidade
            "Quantity of Containers", "Container Type",
            # Rotas (unificado)
            "Port of Loading POL", "Port of Delivery POD", "Place of Receipt", "Final Destination",
            # Datas
            "Shipment Requested Date", "Requested Shipment Week", "data_requested_deadline_start", "data_requested_deadline_end",
            "data_shipment_period_start", "data_shipment_period_end", "data_required_sail_date", "data_required_arrival_expected",
            # Pedido e cliente
            "Sales Order Reference", "data_sales_order", "Business", "Customer",
            # Condições
            "Incoterm", "DTHC", "Afloat", "VIP PNL Risk", "PNL Destination",
            # Administração
            "data_allocation", "data_producer_nomination", "data_lc_received", "Sales Owner",
            # Observações
            "Comments Sales"
        ]
        df = df[[c for c in desired_cols_sales if c in df.columns]]
 
        # Adiciona ícones ao Farol Status para exibição
        df = process_farol_status_for_display(df)
        
        # Limpar valores "None", "nan", "<NA>" de colunas de texto
        df = clean_none_values_from_dataframe(df)

        return df, total_records
    finally:
        if conn:
            conn.close()
 
 #Obter os dados das tabelas principais Booking
#@st.cache_data(ttl=300)
def get_data_bookingData(page_number: int = 1, page_size: int = 25, all_rows: bool = False):
    """Executa a consulta SQL com paginação, aplica o mapeamento de colunas e retorna um DataFrame formatado e o total de registros."""
    conn = None
    offset = (page_number - 1) * page_size

    # Consulta SQL (com ou sem paginação), ordenada pelos mais recentes
    base_query = '''
    SELECT 
        ID                                  AS b_id,
        FAROL_REFERENCE                      AS b_farol_reference,
        FAROL_STATUS                         AS b_farol_status,
        FAROL_STATUS                         AS farol_status,
        B_CREATION_OF_BOOKING                AS b_creation_of_booking,
        B_BOOKING_REFERENCE                  AS b_booking_reference,
        B_TRANSACTION_NUMBER                 AS b_transaction_number,
        FAROL_STATUS                     AS b_booking_status,
        USER_LOGIN_BOOKING_CREATED           AS b_booking_owner,
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
        B_DATA_CONFIRMACAO_EMBARQUE          AS b_data_confirmacao_embarque,
        B_DATA_PARTIDA_ATD                   AS b_data_partida_atd,
        B_DATA_ESTIMADA_TRANSBORDO_ETD       AS b_data_estimada_transbordo_etd,
        B_DATA_CHEGADA_ATA                   AS b_data_chegada_ata,
        B_DATA_TRANSBORDO_ATD                AS b_data_transbordo_atd,
        B_DATA_CHEGADA_DESTINO_ETA           AS b_data_chegada_destino_eta,
        B_DATA_CHEGADA_DESTINO_ATA           AS b_data_chegada_destino_ata,
        B_DATA_ESTIMATIVA_ATRACACAO_ETB      AS b_data_estimativa_atracacao_etb,
        B_DATA_ATRACACAO_ATB                 AS b_data_atracacao_atb,
        /* demais valores */
        B_FREIGHT_RATE_USD                   AS b_freight_rate_usd,
        B_BOGEY_SALE_PRICE_USD               AS b_bogey_sale_price_usd,
        B_FreightPpnl                        AS b_freightppnl,
        B_AWARD_STATUS                       AS b_award_status,
        B_COMMENTS                           AS b_comments,
        B_DEVIATION_DOCUMENT                 AS b_deviation_document,
        B_DEVIATION_RESPONSIBLE              AS b_deviation_responsible,
        B_DEVIATION_REASON                   AS b_deviation_reason,
        ADJUSTMENT_ID                        AS adjustment_id,
        /* Campos de Sales necessários para exibição no Booking */
        S_CREATION_OF_SHIPMENT               AS s_creation_of_shipment,
        S_TYPE_OF_SHIPMENT                   AS s_type_of_shipment,
        S_QUANTITY_OF_CONTAINERS             AS s_quantity_of_containers,
        S_CONTAINER_TYPE                     AS s_container_type,
        S_SALE_ORDER_REFERENCE               AS s_sales_order_reference,
        S_SALE_ORDER_DATE                    AS s_sales_order_date,
        S_PORT_OF_LOADING_POL                AS b_port_of_loading_pol,
        S_PORT_OF_DELIVERY_POD               AS b_port_of_delivery_pod
    FROM LogTransp.F_CON_SALES_BOOKING_DATA
    ORDER BY FAROL_REFERENCE DESC'''

    if all_rows:
        query = base_query
    else:
        query = base_query + f"\nOFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY"

    count_query = 'SELECT COUNT(*) FROM LogTransp.F_CON_SALES_BOOKING_DATA'

    try:
        conn = get_database_connection()
        df = pd.read_sql_query(text(query), conn)
        total_records = conn.execute(text(count_query)).scalar() or 0

        # Aplicar o mapeamento de colunas antes de retornar os dados
        column_mapping = get_column_mapping()
        df.rename(columns=column_mapping, inplace=True)
        
        # Converter colunas de data/hora para datetime
        datetime_columns = [
            'data_draft_deadline', 'data_deadline', 'data_estimativa_saida', 
            'data_estimativa_chegada', 'data_abertura_gate', 'data_confirmacao_embarque',
            'data_partida', 'data_estimada_transbordo', 'data_chegada', 
            'data_transbordo', 'data_chegada_destino_eta', 'data_chegada_destino_ata',
            'data_estimativa_atracacao', 'data_atracacao',
            'data_required_sail_date', 'data_required_arrival_expected', 'data_requested_deadline_start', 'data_requested_deadline_end'
        ]
        
        for col in datetime_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
 
        #Filtrando as colunas e definindo a ordem de exibição (alinhada entre ratios)
        df = df[[
            # Identificação
            "Booking Farol Reference", "Farol Status", "Type of Shipment", "Booking Status", "Booking Reference",
            "Transaction Number",
            # Capacidade
            "Quantity of Containers", "Container Type",
            # Rotas (unificado)
            "Port of Loading POL", "Port of Delivery POD", "Place of Receipt", "Final Destination",
            # Datas de planejamento
            "Shipment Requested Date", "Sales Order Reference", "data_sales_order", "Booking Registered Date", "Booking Requested Date", "data_booking_confirmation",
            "data_estimativa_saida", "data_estimativa_chegada", "data_deadline", "data_draft_deadline", "data_abertura_gate",
            "data_confirmacao_embarque", "data_atracacao", "data_partida", "data_chegada", 
            "data_estimativa_atracacao", "data_estimada_transbordo", "data_transbordo",
            "data_chegada_destino_eta", "data_chegada_destino_ata",
            # Armador/viagem
            "Carrier", "Freight Forwarder", "Vessel Name", "Voyage Code", "Terminal", "Transhipment Port", "POD Country", "POD Country Acronym", "Destination Trade Region",
            # Financeiro
            "Freight Rate USD", "Bogey Sale Price USD", "Freight PNL",
            # Justificativa de Desvios
            "Deviation Document", "Deviation Responsible", "Deviation Reason",
            # Administração
            "Booking Owner",
            # Observações
            "Comments Booking"
        ]]
 
        # Adiciona ícones ao Farol Status para exibição
        df = process_farol_status_for_display(df)
        
        # Limpar valores "None", "nan", "<NA>" de colunas de texto
        df = clean_none_values_from_dataframe(df)

        return df, total_records
    finally:
        if conn:
            conn.close()

# Obter os dados da visão geral (todos os campos)
#@st.cache_data(ttl=300)
def get_data_generalView(page_number: int = 1, page_size: int = 25, all_rows: bool = False):
    """Executa a consulta SQL com paginação para a visão geral, retornando todas as colunas das visões de Sales e Booking."""
    conn = None
    offset = (page_number - 1) * page_size

    # Consulta explícita combinando todos os campos necessários para ambas as visões (com ou sem paginação)
    base_query = '''
    SELECT 
        ID                                 AS s_id,
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
        S_REQUIRED_SAIL_DATE               AS s_required_sail_date,
        S_REQUIRED_ARRIVAL_DATE_EXPECTED   AS s_required_arrival_date_expected,
        S_REQUESTED_DEADLINE_START_DATE    AS s_requested_deadlines_start_date,
        S_REQUESTED_DEADLINE_END_DATE      AS s_requested_deadlines_end_date,
        S_PARTIAL_ALLOWED                  AS s_partial_allowed,
        S_VIP_PNL_RISK                     AS s_vip_pnl_risk,
        S_PNL_DESTINATION                  AS s_pnl_destination,
        S_LC_RECEIVED                      AS s_lc_received,
        S_ALLOCATION_DATE                  AS s_allocation_date,
        S_PRODUCER_NOMINATION_DATE         AS s_producer_nomination_date,
        USER_LOGIN_SALES_CREATED           AS s_sales_owner,
        S_COMMENTS                         AS s_comments,
        B_CREATION_OF_BOOKING                AS b_creation_of_booking,
        B_BOOKING_REFERENCE                  AS b_booking_reference,
        B_TRANSACTION_NUMBER                 AS b_transaction_number,
        FAROL_STATUS                         AS farol_status,
        FAROL_STATUS                     AS b_booking_status,
        USER_LOGIN_BOOKING_CREATED           AS b_booking_owner,
        B_VOYAGE_CARRIER                     AS b_voyage_carrier,
        B_FREIGHT_FORWARDER                  AS b_freight_forwarder,
        B_BOOKING_REQUEST_DATE               AS b_booking_request_date,
        B_BOOKING_CONFIRMATION_DATE          AS b_booking_confirmation_date,
        B_VESSEL_NAME                        AS b_vessel_name,
        B_VOYAGE_CODE                        AS b_voyage_code,
        B_TERMINAL                           AS b_terminal,
        B_TRANSHIPMENT_PORT                  AS b_transhipment_port,
        B_POD_COUNTRY                        AS b_pod_country,
        B_POD_COUNTRY_ACRONYM                AS b_pod_country_acronym,
        B_DESTINATION_TRADE_REGION           AS b_destination_trade_region,
        B_DATA_DRAFT_DEADLINE                AS b_data_draft_deadline,
        B_DATA_DEADLINE                      AS b_data_deadline,
        B_DATA_ESTIMATIVA_SAIDA_ETD          AS b_data_estimativa_saida_etd,
        B_DATA_ESTIMATIVA_CHEGADA_ETA        AS b_data_estimativa_chegada_eta,
        B_DATA_ABERTURA_GATE                 AS b_data_abertura_gate,
        B_DATA_CONFIRMACAO_EMBARQUE          AS b_data_confirmacao_embarque,
        B_DATA_PARTIDA_ATD                   AS b_data_partida_atd,
        B_DATA_ESTIMADA_TRANSBORDO_ETD       AS b_data_estimada_transbordo_etd,
        B_DATA_CHEGADA_ATA                   AS b_data_chegada_ata,
        B_DATA_TRANSBORDO_ATD                AS b_data_transbordo_atd,
        B_DATA_CHEGADA_DESTINO_ETA           AS b_data_chegada_destino_eta,
        B_DATA_CHEGADA_DESTINO_ATA           AS b_data_chegada_destino_ata,
        B_DATA_ESTIMATIVA_ATRACACAO_ETB      AS b_data_estimativa_atracacao_etb,
        B_DATA_ATRACACAO_ATB                 AS b_data_atracacao_atb,
        B_FREIGHT_RATE_USD                   AS b_freight_rate_usd,
        B_BOGEY_SALE_PRICE_USD               AS b_bogey_sale_price_usd,
        B_FreightPpnl                        AS b_freightppnl,
        B_AWARD_STATUS                       AS b_award_status,
        B_COMMENTS                           AS b_comments,
        B_DEVIATION_DOCUMENT                 AS b_deviation_document,
        B_DEVIATION_RESPONSIBLE              AS b_deviation_responsible,
        B_DEVIATION_REASON                   AS b_deviation_reason,
        ADJUSTMENT_ID                        AS adjustment_id
    FROM LogTransp.F_CON_SALES_BOOKING_DATA
    ORDER BY FAROL_REFERENCE DESC'''

    if all_rows:
        query = base_query
    else:
        query = base_query + f"\nOFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY"

    count_query = 'SELECT COUNT(*) FROM LogTransp.F_CON_SALES_BOOKING_DATA'

    try:
        conn = get_database_connection()
        df = pd.read_sql_query(text(query), conn)
        total_records = conn.execute(text(count_query)).scalar() or 0

        # Aplicar o mapeamento de colunas para nomes amigáveis
        column_mapping = get_column_mapping()
        df.rename(columns=column_mapping, inplace=True)

        # Converter colunas de data/hora para datetime (igual aos outros ratios)
        datetime_columns = [
            'data_draft_deadline', 'data_deadline', 'data_estimativa_saida', 
            'data_estimativa_chegada', 'data_abertura_gate', 'data_confirmacao_embarque',
            'data_partida', 'data_estimada_transbordo', 'data_chegada', 
            'data_transbordo', 'data_chegada_destino_eta', 'data_chegada_destino_ata',
            'data_estimativa_atracacao', 'data_atracacao',
            'data_required_arrival_expected', 'data_requested_deadline_start', 'data_requested_deadline_end',
            'data_shipment_period_start', 'data_shipment_period_end', 'data_sales_order',
            'data_allocation', 'data_producer_nomination', 'data_lc_received', 'data_booking_confirmation'
        ]
        
        for col in datetime_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')

        # Processar o status do Farol para exibição com ícones
        df = process_farol_status_for_display(df)
        
        # Limpar valores "None", "nan", "<NA>" de colunas de texto
        df = clean_none_values_from_dataframe(df)

        # Lista de colunas seguindo ordem específica solicitada pelo usuário
        combined_cols = [
            # 1. IDENTIFICAÇÃO BÁSICA
            "Sales Farol Reference", "Farol Status", "Carrier Returns Status", "Type of Shipment", "Booking Status",
            "Transaction Number",
            "Quantity of Containers", "Container Type", "Port of Loading POL", "Port of Delivery POD", "Place of Receipt", "Final Destination",
            
            # 2. DATAS INICIAIS
            "Shipment Requested Date", "Booking Registered Date", "Booking Requested Date",
            
            # 3. INFORMAÇÕES DE NAVEGAÇÃO
            "Carrier", "Vessel Name", "Voyage Code", "Terminal", "Freight Forwarder", 
            "Transhipment Port", "POD Country", "POD Country Acronym", "Destination Trade Region",
            
            # 4. PRAZOS E PERÍODOS
            "Requested Shipment Week", "data_requested_deadline_start", "data_requested_deadline_end",
            "data_shipment_period_start", "data_shipment_period_end", "data_required_sail_date", "data_required_arrival_expected",
            
            # 5. PROCESSO DE BOOKING
            "data_booking_confirmation", "data_estimativa_saida", "data_estimativa_chegada", 
            "data_deadline", "data_draft_deadline", "data_abertura_gate", "data_confirmacao_embarque",
            
            # 6. PROCESSO MARÍTIMO (Estimativas vs Real)
            "data_atracacao", "data_partida", "data_chegada", "data_estimativa_atracacao", 
            "data_estimada_transbordo", "data_transbordo", "data_chegada_destino_eta", "data_chegada_destino_ata",
            
            # 7. FRETE
            "Freight Rate USD",
            
            # 8. JUSTIFICATIVA DE DESVIOS
            "Deviation Document", "Deviation Responsible", "Deviation Reason",
            
            # 9. INFORMAÇÕES DE SALES
            "Sales Order Reference", "data_sales_order", "Business", "Customer", "Incoterm", "DTHC", "Afloat", 
            "VIP PNL Risk", "PNL Destination", "data_allocation", "data_producer_nomination", "data_lc_received", 
            "Sales Owner", "Comments Sales",
            
            # 10. INFORMAÇÕES DE BOOKING
            "Booking Status", "Booking Reference", "Booking Owner", "Bogey Sale Price USD", "Freight PNL", "Comments Booking"
        ]

        # Remove duplicatas mantendo a ordem lógica
        seen = set()
        final_combined_cols = [x for x in combined_cols if not (x in seen or seen.add(x))]
        
        # Garante que a coluna de referência seja a de Sales (padrão que definimos na query)
        if "Booking Farol Reference" in final_combined_cols:
            final_combined_cols.remove("Booking Farol Reference")

        # Filtra o DataFrame para conter apenas as colunas da união que realmente existem no DF
        final_cols = [col for col in final_combined_cols if col in df.columns]
        df = df[final_cols]

        return df, total_records
    finally:
        if conn:
            conn.close()

# --- Helpers pontuais para buscar 1 registro por FAROL_REFERENCE ---
def get_sales_record_by_reference(farol_reference: str) -> pd.DataFrame:
    """Retorna um único registro da visão Sales Data para a FAROL_REFERENCE informada."""
    base_query = '''
    SELECT 
        FAROL_REFERENCE                    AS s_farol_reference,
        FAROL_STATUS                       AS s_farol_status,
        S_SHIPMENT_STATUS                  AS s_shipment_status,
        S_TYPE_OF_SHIPMENT                 AS s_type_of_shipment,
        S_CREATION_OF_SHIPMENT             AS s_creation_of_shipment,
        B_BOOKING_REFERENCE                AS b_booking_reference,
        S_CUSTOMER_PO                      AS s_customer_po,
        S_SALE_ORDER_REFERENCE             AS s_sales_order_reference,
        S_SALE_ORDER_DATE                  AS s_sales_order_date,
        S_BUSINESS                         AS s_business,
        S_CUSTOMER                         AS s_customer,
        S_MODE                             AS s_mode,
        S_INCOTERM                         AS s_incoterm,
        S_SKU                              AS s_sku,
        S_PLANT_OF_ORIGIN                  AS s_plant_of_origin,
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
        S_REQUIRED_SAIL_DATE               AS s_required_sail_date,
        S_REQUIRED_ARRIVAL_DATE_EXPECTED   AS s_required_arrival_date_expected,
        S_REQUESTED_DEADLINE_START_DATE    AS s_requested_deadlines_start_date,
        S_REQUESTED_DEADLINE_END_DATE      AS s_requested_deadlines_end_date,
        S_PARTIAL_ALLOWED                  AS s_partial_allowed,
        S_VIP_PNL_RISK                     AS s_vip_pnl_risk,
        S_PNL_DESTINATION                  AS s_pnl_destination,
        S_LC_RECEIVED                      AS s_lc_received,
        S_ALLOCATION_DATE                  AS s_allocation_date,
        S_PRODUCER_NOMINATION_DATE         AS s_producer_nomination_date,
        USER_LOGIN_SALES_CREATED           AS s_sales_owner,
        S_COMMENTS                         AS s_comments
    FROM LogTransp.F_CON_SALES_BOOKING_DATA
    WHERE FAROL_REFERENCE = :ref
    '''
    conn = get_database_connection()
    try:
        df = pd.read_sql_query(text(base_query), conn, params={"ref": farol_reference})
        column_mapping = get_column_mapping()
        df.rename(columns=column_mapping, inplace=True)
        if "Booking Status" not in df.columns:
            df["Booking Status"] = pd.NA
        df = process_farol_status_for_display(df)
        return df
    finally:
        conn.close()

def get_booking_record_by_reference(farol_reference: str) -> pd.DataFrame:
    """Retorna um único registro da visão Booking Management para a FAROL_REFERENCE informada."""
    base_query = '''
    SELECT 
        ID                                  AS b_id,
        FAROL_REFERENCE                      AS b_farol_reference,
        FAROL_STATUS                         AS b_farol_status,
        B_CREATION_OF_BOOKING                AS b_creation_of_booking,
        B_BOOKING_REFERENCE                  AS b_booking_reference,
        B_TRANSACTION_NUMBER                 AS b_transaction_number,
        FAROL_STATUS                     AS b_booking_status,
        USER_LOGIN_BOOKING_CREATED           AS b_booking_owner,
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
        B_DATA_DRAFT_DEADLINE                AS b_data_draft_deadline,
        B_DATA_DEADLINE                      AS b_data_deadline,
        B_DATA_ESTIMATIVA_SAIDA_ETD          AS b_data_estimativa_saida_etd,
        B_DATA_ESTIMATIVA_CHEGADA_ETA        AS b_data_estimativa_chegada_eta,
        B_DATA_ABERTURA_GATE                 AS b_data_abertura_gate,
        B_DATA_CONFIRMACAO_EMBARQUE          AS b_data_confirmacao_embarque,
        B_DATA_PARTIDA_ATD                   AS b_data_partida_atd,
        B_DATA_ESTIMADA_TRANSBORDO_ETD       AS b_data_estimada_transbordo_etd,
        B_DATA_CHEGADA_ATA                   AS b_data_chegada_ata,
        B_DATA_TRANSBORDO_ATD                AS b_data_transbordo_atd,
        B_DATA_CHEGADA_DESTINO_ETA           AS b_data_chegada_destino_eta,
        B_DATA_CHEGADA_DESTINO_ATA           AS b_data_chegada_destino_ata,
        B_DATA_ESTIMATIVA_ATRACACAO_ETB      AS b_data_estimativa_atracacao_etb,
        B_DATA_ATRACACAO_ATB                 AS b_data_atracacao_atb,
        B_FREIGHT_RATE_USD                   AS b_freight_rate_usd,
        B_BOGEY_SALE_PRICE_USD               AS b_bogey_sale_price_usd,
        B_FreightPpnl                        AS b_freightppnl,
        B_AWARD_STATUS                       AS b_award_status,
        B_COMMENTS                           AS b_comments,
        B_DEVIATION_DOCUMENT                 AS b_deviation_document,
        B_DEVIATION_RESPONSIBLE              AS b_deviation_responsible,
        B_DEVIATION_REASON                   AS b_deviation_reason,
        ADJUSTMENT_ID                        AS adjustment_id,
        S_CREATION_OF_SHIPMENT               AS s_creation_of_shipment,
        S_TYPE_OF_SHIPMENT                   AS s_type_of_shipment,
        S_QUANTITY_OF_CONTAINERS             AS s_quantity_of_containers,
        S_CONTAINER_TYPE                     AS s_container_type,
        S_SALE_ORDER_REFERENCE               AS s_sales_order_reference,
        S_SALE_ORDER_DATE                    AS s_sales_order_date,
        S_PORT_OF_LOADING_POL                AS b_port_of_loading_pol,
        S_PORT_OF_DELIVERY_POD               AS b_port_of_delivery_pod
    FROM LogTransp.F_CON_SALES_BOOKING_DATA
    WHERE FAROL_REFERENCE = :ref
    '''
    conn = get_database_connection()
    try:
        df = pd.read_sql_query(text(base_query), conn, params={"ref": farol_reference})
        column_mapping = get_column_mapping()
        df.rename(columns=column_mapping, inplace=True)
        # Converter colunas de data/hora para datetime conforme função principal
        datetime_columns = [
            'data_draft_deadline', 'data_deadline', 'data_estimativa_saida', 
            'data_estimativa_chegada', 'data_abertura_gate', 'data_confirmacao_embarque',
            'data_partida', 'data_estimada_transbordo', 'data_chegada', 
            'data_transbordo', 'data_chegada_destino_eta', 'data_chegada_destino_ata',
            'data_estimativa_atracacao', 'data_atracacao',
            'data_required_arrival_expected', 'data_requested_deadline_start', 'data_requested_deadline_end'
        ]
        for col in datetime_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        df = process_farol_status_for_display(df)
        return df
    finally:
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
        df = df[["Loading Farol Reference","Farol Status","Truck Loading Status", "Type of Shipment", "Quantity of Containers", "Container Type", "Creation Of Cargo Loading", "Logistics Analyst", "Supplier",
            "Port of Loading POL", "Port of Delivery POD", "Stuffing Terminal", "Stuffing Terminal Acceptance", "Drayage Carrier", "Status ITAS", "Truck Loading Farol",
            "Expected Truck Load Start Date", "Expected Truck Load End Date",
            "Quantity Tons Loaded Origin", "Actual Truck Load Date", "Container Release Farol",
            "Expected Container Release Start Date", "Expected Container Release End Date",
            "Actual Container Release Date", "Quantity Containers Released",
            "Container Release Issue Responsibility", "Quantity Containers Released Different Shore",
            "Shore Container Release Different"]]
 
        # Adiciona ícones ao Farol Status para exibição
        df = process_farol_status_for_display(df)

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
        COALESCE(FAROL_STATUS, 'New Request') AS s_farol_status,
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
        S_REQUIRED_ARRIVAL_DATE_EXPECTED            AS s_required_arrival_date_expected,
        S_REQUESTED_DEADLINE_START_DATE    AS s_requested_deadlines_start_date,
        S_REQUESTED_DEADLINE_END_DATE      AS s_requested_deadlines_end_date,
        S_PARTIAL_ALLOWED                  AS s_partial_allowed,
        S_VIP_PNL_RISK                     AS s_vip_pnl_risk,
        S_PNL_DESTINATION                  AS s_pnl_destination,
        S_LC_RECEIVED                      AS s_lc_received,
        S_ALLOCATION_DATE                  AS s_allocation_date,
        S_PRODUCER_NOMINATION_DATE         AS s_producer_nomination_date,
        USER_LOGIN_SALES_CREATED           AS s_sales_owner,
        S_COMMENTS                         AS s_comments
    FROM LogTransp.F_CON_SALES_BOOKING_DATA
    ORDER BY FAROL_REFERENCE'''
 
    try:
        conn = get_database_connection()
        df = pd.read_sql_query(text(query), conn)
 
        # Aplicar o mapeamento de colunas antes de retornar os dados
        column_mapping = get_column_mapping()
        df.rename(columns=column_mapping, inplace=True)
        
        # Limpar valores "None", "nan", "<NA>" de colunas de texto
        df = clean_none_values_from_dataframe(df)
 
        return df
    finally:
        if conn:
            conn.close()
 

           
### Obtendo os dados da UDC
@st.cache_data(ttl=300)  # Cache por 5 minutos para reduzir queries repetidas
def load_df_udc():
    """
    Executa a consulta SQL, aplica o mapeamento de colunas e retorna um DataFrame formatado.
    Cacheado com Streamlit (@st.cache_data) para evitar queries repetidas.
    """
    # Consulta SQL
    query = '''
    SELECT *
    FROM LogTransp.F_CON_Global_Variables'''
 
    with get_database_connection() as conn:
        df = pd.read_sql_query(text(query), conn)
        return df
 
 
 
 
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
            "s_required_arrival_date_expected": "S_REQUIRED_ARRIVAL_DATE_EXPECTED",
            "s_requested_deadlines_start_date": "S_REQUESTED_DEADLINE_START_DATE",
            "s_requested_deadlines_end_date": "S_REQUESTED_DEADLINE_END_DATE",
            "s_partial_allowed": "S_PARTIAL_ALLOWED",
            "s_vip_pnl_risk": "S_VIP_PNL_RISK",
            "s_pnl_destination": "S_PNL_DESTINATION",
            "s_lc_received": "S_LC_RECEIVED",
            "s_allocation_date": "S_ALLOCATION_DATE",
            "s_producer_nomination_date": "S_PRODUCER_NOMINATION_DATE",
            "s_sales_owner": "USER_LOGIN_SALES_CREATED",
            "s_comments": "S_COMMENTS",
            "b_terminal": "B_TERMINAL",
            # Novos campos B_ para o novo template Excel
            "b_voyage_carrier": "B_VOYAGE_CARRIER",
            "b_booking_reference": "B_BOOKING_REFERENCE",
            "b_freight_rate_usd": "B_FREIGHT_RATE_USD",
            "b_bogey_sale_price_usd": "B_BOGEY_SALE_PRICE_USD",
            "b_freightppnl": "B_FREIGHTPPNL",
            "b_bogey_pnl": "B_BOGEY_PNL",
            "b_ml_profit_margin": "B_ML_PROFIT_MARGIN",
            "b_vessel_name": "B_VESSEL_NAME",
            "b_voyage_code": "B_VOYAGE_CODE",
            "b_data_estimativa_saida_etd": "B_DATA_ESTIMATIVA_SAIDA_ETD",
            "b_pod_country_acronym": "B_POD_COUNTRY_ACRONYM",
            "b_destination_trade_region": "B_DESTINATION_TRADE_REGION",
            "b_margin": "B_MARGIN",
            "b_ref_sharepoint": "B_REF_SHAREPOINT",
        }

        unified_values = {}
        for k, v in form_values.items():
            col = unified_map.get(k)
            if col:
                unified_values[col] = v
        # valores padrão
        unified_values.setdefault("FAROL_STATUS", "New Request")
        unified_values.setdefault("STAGE", "Sales Data")

        # Adicionar USER_LOGIN_SALES_CREATED se não estiver presente
        if "USER_LOGIN_SALES_CREATED" not in unified_values:
            unified_values["USER_LOGIN_SALES_CREATED"] = get_current_user_login()
        
        fields = ", ".join(unified_values.keys())
        placeholders = ", ".join([f":{key}" for key in unified_values.keys()])
        insert_query = text(f"""
            INSERT INTO LogTransp.F_CON_SALES_BOOKING_DATA ({fields})
            VALUES ({placeholders})
        """)
        conn.execute(insert_query, unified_values)
        
        # Auditoria para criação de registro Sales - REMOVIDA
        # Não auditar eventos de criação inicial (FAROL_STATUS, USER_LOGIN_SALES_CREATED)
        # A auditoria será ativada apenas quando o usuário editar campos editáveis
 
        # Removido: criação automática de booking e container release
        # Commit final
        transaction.commit()
        
        # Criar snapshot na tabela F_CON_RETURN_CARRIERS para manter as colunas de expectativa interna sincronizadas
        farol_reference = unified_values.get("FAROL_REFERENCE")
        if farol_reference:
            try:
                # Usar o usuário logado para o snapshot (mesmo que criou o registro Sales)
                current_user = unified_values.get("USER_LOGIN_SALES_CREATED") or get_current_user_login()
                upsert_return_carrier_from_unified(farol_reference, user_insert=current_user)
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
                # Para colunas de data específicas, usar o mapeamento direto
                if ui_label in ["Requested Deadline Start Date", "Requested Deadline End Date", "Required Arrival Date Expected"]:
                    col = reverse_map.get(ui_label)
                else:
                    # Para outras colunas, usar o mapeamento com prefixo
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
        
        # Define o Farol Status como "New Adjustment" para os splits
        if "FAROL_STATUS" in unified_copy.columns:
            unified_copy.at[0, "FAROL_STATUS"] = "New Adjustment"
        if "l_farol_status" in loading_copy.columns:
            loading_copy.at[0, "l_farol_status"] = "New Adjustment"
 
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

        insert_sales = []  # não usamos mais, mantido para compatibilidade do fluxo
        insert_booking = []
        insert_unified.append(unified_dict)
        insert_loading.append(loading_dict)
 
        # Captura do valor de containers do split
        quantity_value = row.get("Quantity of Containers", "")
 
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
    # Auditoria já é feita via insert_return_carrier_from_ui em shipments_split.py
    # Não precisa mais gravar em F_CON_ADJUSTMENTS_LOG
 
    # Atualiza o Farol Status da linha original para "New Adjustment"
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
        "farol_status": "New Adjustment",
        "ref": farol_ref_original
    })
    conn.execute(update_loading_original, {
        "farol_status": "New Adjustment",
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
            S_REQUIRED_SAIL_DATE AS s_required_sail_date,
            S_REQUIRED_ARRIVAL_DATE_EXPECTED AS s_required_arrival_date_expected
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
            FAROL_STATUS      AS b_booking_status,
            B_VOYAGE_CARRIER      AS b_voyage_carrier,
            B_FREIGHT_FORWARDER   AS b_freight_forwarder,
            B_BOOKING_REQUEST_DATE AS b_booking_request_date,
            B_COMMENTS            AS b_comments,
            B_TERMINAL            AS b_terminal,
            -- Pré-preenchimento (campos de Sales na unificada)
            S_DTHC_PREPAID                    AS dthc,
            S_REQUESTED_SHIPMENT_WEEK         AS requested_shipment_week,
            S_QUANTITY_OF_CONTAINERS          AS sales_quantity_of_containers,
            S_REQUESTED_DEADLINE_START_DATE   AS requested_cut_off_start_date,
            S_REQUESTED_DEADLINE_END_DATE     AS requested_cut_off_end_date,
            S_REQUIRED_ARRIVAL_DATE_EXPECTED           AS required_arrival_date,
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


def list_terminal_names():
    """Retorna lista de nomes da coluna Nome da F_ELLOX_TERMINALS."""
    conn = get_database_connection()
    try:
        query = text(
            """
            SELECT DISTINCT NOME
            FROM LogTransp.F_ELLOX_TERMINALS
            WHERE NOME IS NOT NULL
            ORDER BY 1
            """
        )
        rows = conn.execute(query).fetchall()
        return [row[0] for row in rows] if rows else []
    finally:
        conn.close()

def list_terminal_names_from_unified():
    """Fallback: retorna DISTINCT de B_TERMINAL da unificada."""
    conn = get_database_connection()
    try:
        query = text(
            """
            SELECT DISTINCT B_TERMINAL, COUNT(*) as cnt
            FROM LogTransp.F_CON_SALES_BOOKING_DATA
            WHERE B_TERMINAL IS NOT NULL
            GROUP BY B_TERMINAL
            ORDER BY cnt DESC
            """
        )
        rows = conn.execute(query).fetchall()
        # Diagnóstico: imprime os primeiros 5 terminais e suas contagens
        if rows:
            print("\nTerminais mais usados na unificada:")
            for row in rows[:5]:
                print(f"- {row[0]}: {row[1]} ocorrências")
        return [row[0] for row in rows] if rows else []
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
        with conn.begin():  # Transação para auditoria
            # Primeiro, buscar valores atuais para auditoria
            current_values_query = text("""
                SELECT S_PORT_OF_LOADING_POL, S_PORT_OF_DELIVERY_POD, S_QUANTITY_OF_CONTAINERS,
                       S_DTHC_PREPAID, S_REQUESTED_SHIPMENT_WEEK, S_FINAL_DESTINATION,
                       USER_LOGIN_BOOKING_CREATED
                FROM LogTransp.F_CON_SALES_BOOKING_DATA
                WHERE FAROL_REFERENCE = :ref
            """)
            current_row = conn.execute(current_values_query, {"ref": farol_reference}).fetchone()
            
            # Preparar novos valores
            new_values = {
                "pol": values.get("booking_port_of_loading_pol", ""),
                "pod": values.get("booking_port_of_delivery_pod", ""),
                "s_quantity_of_containers": values.get("s_quantity_of_containers") if values.get("s_quantity_of_containers") else None,
                "s_dthc_prepaid": values.get("s_dthc_prepaid") if values.get("s_dthc_prepaid") else None,
                "s_requested_shipment_week": values.get("s_requested_shipment_week") if values.get("s_requested_shipment_week") else None,
                "s_final_destination": values.get("s_final_destination") if values.get("s_final_destination") else None,
            }
            
            # Auditoria para campos editáveis - apenas quando há mudanças reais
            if current_row:
                audit_fields = [
                    ("S_PORT_OF_LOADING_POL", current_row[0], new_values["pol"]),
                    ("S_PORT_OF_DELIVERY_POD", current_row[1], new_values["pod"]),
                    ("S_QUANTITY_OF_CONTAINERS", current_row[2], new_values["s_quantity_of_containers"]),
                    ("S_DTHC_PREPAID", current_row[3], new_values["s_dthc_prepaid"]),
                    ("S_REQUESTED_SHIPMENT_WEEK", current_row[4], new_values["s_requested_shipment_week"]),
                    ("S_FINAL_DESTINATION", current_row[5], new_values["s_final_destination"]),
                ]
                
                # Auditar apenas campos que realmente mudaram (não criação inicial)
                for col_name, old_val, new_val in audit_fields:
                    if old_val != new_val:  # Só audita se houve mudança real
                        audit_change(conn, farol_reference, 'F_CON_SALES_BOOKING_DATA', col_name, 
                                   old_val, new_val, 'Criação do Booking', 'UPDATE')
            
            query = """
            UPDATE LogTransp.F_CON_SALES_BOOKING_DATA
            SET FAROL_STATUS = :farol_status,
                B_VOYAGE_CARRIER = :b_voyage_carrier,
                B_CREATION_OF_BOOKING = :b_creation_of_booking,
                B_FREIGHT_FORWARDER = :b_freight_forwarder,
                B_BOOKING_REQUEST_DATE = :b_booking_request_date,
                B_COMMENTS = :b_comments,
                S_PORT_OF_LOADING_POL = :pol,
                S_PORT_OF_DELIVERY_POD = :pod,
                S_QUANTITY_OF_CONTAINERS = :s_quantity_of_containers,
                S_DTHC_PREPAID = :s_dthc_prepaid,
                S_REQUESTED_SHIPMENT_WEEK = :s_requested_shipment_week,
                S_FINAL_DESTINATION = :s_final_destination,
                B_TERMINAL = :b_terminal,
                USER_LOGIN_BOOKING_CREATED = CASE 
                    WHEN USER_LOGIN_BOOKING_CREATED IS NULL THEN :user_login 
                    ELSE USER_LOGIN_BOOKING_CREATED 
                END
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
                    "farol_status": "Booking Requested",
                    "b_creation_of_booking": datetime.now(),
                    "b_voyage_carrier": values["b_voyage_carrier"],
                    "b_freight_forwarder": values["b_freight_forwarder"],
                    "b_booking_request_date": values["b_booking_request_date"],
                    "b_comments": values["b_comments"],
                    "pol": new_values["pol"],
                    "pod": new_values["pod"],
                    "s_quantity_of_containers": new_values["s_quantity_of_containers"],
                    "s_dthc_prepaid": new_values["s_dthc_prepaid"],
                    "s_requested_shipment_week": new_values["s_requested_shipment_week"],
                    "s_final_destination": new_values["s_final_destination"],
                    "b_terminal": values.get("b_terminal", ""),
                    "user_login": get_current_user_login(),
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
                FAROL_STATUS AS FAROL_STATUS,
                CASE 
                    WHEN FAROL_STATUS = 'New Request' THEN 'Shipment Requested'
                    ELSE 'Booking Requested'
                END AS P_STATUS,
                NULL AS P_PDF_NAME,
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

        # Converte resultado para dicionário e normaliza chaves para MAIÚSCULAS
        row_dict = dict(row)
        data = {k.upper(): v for k, v in row_dict.items()}
        
        # Mapeia S_REQUIRED_ARRIVAL_DATE_EXPECTED (unificada) para S_REQUIRED_ARRIVAL_DATE_EXPECTED (carriers)
        if "S_REQUIRED_ARRIVAL_DATE_EXPECTED" in data:
            data["S_REQUIRED_ARRIVAL_DATE_EXPECTED"] = data["S_REQUIRED_ARRIVAL_DATE_EXPECTED"]
        # Garante binds para novos campos mesmo quando não vierem do SELECT
        for k in (
            "B_DATA_PARTIDA_ATD",
            "B_DATA_CHEGADA_ATA",
            "B_DATA_ESTIMATIVA_ATRACACAO_ETB",
            "B_DATA_ATRACACAO_ATB",
            "S_REQUESTED_DEADLINE_START_DATE", 
            "S_REQUESTED_DEADLINE_END_DATE",  
            "S_REQUIRED_ARRIVAL_DATE_EXPECTED",
            "ELLOX_MONITORING_ID"  # Adicionado para evitar erro de bind parameter
        ):
            if k not in data:
                data[k] = None
        data["USER_INSERT"] = user_insert
        data["USER_UPDATE"] = None
        data["DATE_UPDATE"] = None
        
        # Adiciona ROW_INSERTED_DATE com horário local do Brasil
        data["ROW_INSERTED_DATE"] = get_brazil_time()

        # SEMPRE insere um novo registro para manter o histórico completo
        # (comportamento alterado para suportar Request Timeline)
        insert_sql = text(
                            """
                            INSERT INTO LogTransp.F_CON_RETURN_CARRIERS (
                                FAROL_REFERENCE,
                                FAROL_STATUS,
                                P_STATUS,
                                P_PDF_NAME,
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
                                ADJUSTMENT_ID,
                                ELLOX_MONITORING_ID,
                                ROW_INSERTED_DATE
                            ) VALUES (
                                :FAROL_REFERENCE,
                                :FAROL_STATUS,
                                :P_STATUS,
                                :P_PDF_NAME,
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
                                :ADJUSTMENT_ID,
                                NULL, -- Temporariamente definido como NULL
                                :ROW_INSERTED_DATE
                            )
                            """
                        )
        
        data["ADJUSTMENT_ID"] = str(uuid.uuid4())
        conn.execute(insert_sql, data)
        conn.commit()
    finally:
        conn.close()
def insert_return_carrier_snapshot(farol_reference: str, status_override: str | None = None, user_insert: str | None = None):
    conn = get_database_connection()
    try:
        # Busca dados atuais
        fetch_sql = text(
            """
            SELECT 
                FAROL_REFERENCE,
                FAROL_STATUS,
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
        farol_status = status_override if status_override else rd.get("FAROL_STATUS") or "Adjustment Requested"
        db_data = {k: v for k, v in rd.items() if k not in ('ID', 'FAROL_STATUS')}
        db_data["FAROL_REFERENCE"] = farol_reference
        db_data["FAROL_STATUS"] = farol_status

        insert_sql = text(
            """
                        INSERT INTO LogTransp.F_CON_RETURN_CARRIERS (
                            FAROL_REFERENCE,
                            FAROL_STATUS,
                            P_STATUS,
                            P_PDF_NAME,
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
                            ADJUSTMENT_ID,
                            ELLOX_MONITORING_ID,
                            ROW_INSERTED_DATE
                        ) VALUES (
                            :FAROL_REFERENCE,
                            :FAROL_STATUS,
                            :P_STATUS,
                            :P_PDF_NAME,
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
                            :ADJUSTMENT_ID,
                            NULL, -- Temporariamente definido como NULL
                            :ROW_INSERTED_DATE
                        )            """
        )

        params = {
            "FAROL_REFERENCE": rd.get("FAROL_REFERENCE"),
            "FAROL_STATUS": farol_status,
            # Snapshot oriundo do carrier - P_STATUS baseado no status real
            "P_STATUS": "Shipment Requested" if farol_status == "New Request" else "Booking Requested",
            "P_PDF_NAME": None,
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
            "S_REQUIRED_ARRIVAL_DATE_EXPECTED": rd.get("S_REQUIRED_ARRIVAL_DATE_EXPECTED"), 
            "B_DATA_ESTIMATIVA_SAIDA_ETD": rd.get("B_DATA_ESTIMATIVA_SAIDA_ETD"),
            "B_DATA_ESTIMATIVA_CHEGADA_ETA": rd.get("B_DATA_ESTIMATIVA_CHEGADA_ETA"),
            "B_DATA_ABERTURA_GATE": rd.get("B_DATA_ABERTURA_GATE"),
            "USER_INSERT": user_insert,
            "ADJUSTMENT_ID": str(uuid.uuid4()),
            "ELLOX_MONITORING_ID": None,
        }
        
        # Adiciona ROW_INSERTED_DATE com horário local do Brasil
        params["ROW_INSERTED_DATE"] = get_brazil_time()

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

def insert_return_carrier_from_ui(ui_data, user_insert=None, status_override=None, p_status_override=None, area=None, request_reason=None, adjustments_owner=None, comments=None):
    """
    Insere dados na tabela F_CON_RETURN_CARRIERS baseado em dados da interface do usuário.
    Usado para PDFs processados, splits e ajustes.
    
    :param ui_data: Dicionário com dados da UI (com nomes de colunas amigáveis)
    :param user_insert: Usuário que está inserindo os dados
    :param status_override: Status específico a ser definido (ex: "Received from Carrier")
    :param p_status_override: P_STATUS específico a ser definido (ex: "PDF Document - Carrier")
    :param area: Área do ajuste (para casos de split/adjustment)
    :param request_reason: Motivo do ajuste
    :param adjustments_owner: Responsável pelo ajuste
    :param comments: Comentários
    :return: Tupla (bool, str) indicando sucesso e mensagem
    """
    conn = get_database_connection()
    transaction = None
    try:
        transaction = conn.begin()
        # Mapeia campos da UI para campos da tabela
        field_mapping = {
            "Farol Reference": "FAROL_REFERENCE",
            "Booking": "B_BOOKING_REFERENCE",
            "Booking Reference": "B_BOOKING_REFERENCE", 
            "Carrier": "B_VOYAGE_CARRIER",
            "Voyage Carrier": "B_VOYAGE_CARRIER",
            "Voyage Code": "B_VOYAGE_CODE",
            "Vessel Name": "B_VESSEL_NAME",
            "Quantity of Containers": "S_QUANTITY_OF_CONTAINERS",
            "Port of Loading POL": "S_PORT_OF_LOADING_POL",
            "Port of Delivery POD": "S_PORT_OF_DELIVERY_POD",
            "Place of Receipt": "S_PLACE_OF_RECEIPT",
            "Final Destination": "S_FINAL_DESTINATION",
            "Transhipment Port": "B_TRANSHIPMENT_PORT",
            "Terminal": "B_TERMINAL",
            "Port Terminal City": "B_TERMINAL",
            "Requested Deadline Start Date": "S_REQUESTED_DEADLINE_START_DATE",
            "Requested Deadline End Date": "S_REQUESTED_DEADLINE_END_DATE",
            "Required Arrival Date": "S_REQUIRED_ARRIVAL_DATE_EXPECTED",
            "PDF Booking Emission Date": "PDF_BOOKING_EMISSION_DATE",
            "PDF Name": "P_PDF_NAME",
            "B_DATA_DRAFT_DEADLINE": "B_DATA_DRAFT_DEADLINE",
            "B_DATA_DEADLINE": "B_DATA_DEADLINE",
            "B_DATA_ESTIMATIVA_SAIDA_ETD": "B_DATA_ESTIMATIVA_SAIDA_ETD",
            "B_DATA_ESTIMATIVA_CHEGADA_ETA": "B_DATA_ESTIMATIVA_CHEGADA_ETA",
            "B_DATA_ABERTURA_GATE": "B_DATA_ABERTURA_GATE",
            "B_DATA_CONFIRMACAO_EMBARQUE": "B_DATA_CONFIRMACAO_EMBARQUE",
            "B_DATA_PARTIDA_ATD": "B_DATA_PARTIDA_ATD",
            "B_DATA_ESTIMADA_TRANSBORDO_ETD": "B_DATA_ESTIMADA_TRANSBORDO_ETD",
            "B_DATA_CHEGADA_ATA": "B_DATA_CHEGADA_ATA",
            "B_DATA_TRANSBORDO_ATD": "B_DATA_TRANSBORDO_ATD",
            "B_DATA_CHEGADA_DESTINO_ETA": "B_DATA_CHEGADA_DESTINO_ETA",
            "B_DATA_CHEGADA_DESTINO_ATA": "B_DATA_CHEGADA_DESTINO_ATA",
            "B_DATA_ESTIMATIVA_ATRACACAO_ETB": "B_DATA_ESTIMATIVA_ATRACACAO_ETB",
            "B_DATA_ATRACACAO_ATB": "B_DATA_ATRACACAO_ATB",
        }
        
        # PRÉ-PREENCHIMENTO: Buscar datas da tabela principal F_CON_SALES_BOOKING_DATA
        prefill_dates = {}
        if status_override in ["Adjustment Requested", "Received from Carrier", "New Adjustment"] and "Farol Reference" in ui_data:
            farol_ref = ui_data["Farol Reference"]
            try:
                # Buscar dados da tabela principal (última versão atualizada pelo Tracking)
                prefill_query = text("""
                    SELECT 
                        B_DATA_DRAFT_DEADLINE, B_DATA_DEADLINE, 
                        S_REQUESTED_DEADLINE_START_DATE, S_REQUESTED_DEADLINE_END_DATE, S_REQUIRED_ARRIVAL_DATE_EXPECTED,
                        B_DATA_ESTIMATIVA_SAIDA_ETD, B_DATA_ESTIMATIVA_CHEGADA_ETA, B_DATA_ABERTURA_GATE, 
                        B_DATA_CONFIRMACAO_EMBARQUE, B_DATA_PARTIDA_ATD, B_DATA_ESTIMADA_TRANSBORDO_ETD, 
                        B_DATA_CHEGADA_ATA, B_DATA_TRANSBORDO_ATD, B_DATA_CHEGADA_DESTINO_ETA, B_DATA_CHEGADA_DESTINO_ATA, 
                        B_DATA_ESTIMATIVA_ATRACACAO_ETB, B_DATA_ATRACACAO_ATB
                    FROM LogTransp.F_CON_SALES_BOOKING_DATA
                    WHERE FAROL_REFERENCE = :farol_ref
                """)
                result = conn.execute(prefill_query, {"farol_ref": farol_ref}).mappings().fetchone()
                if result:
                    # Mapear campos para pré-preenchimento (14 colunas B_* conforme especificado)
                    date_fields_mapping = {
                        'B_DATA_DRAFT_DEADLINE': 'B_DATA_DRAFT_DEADLINE',
                        'B_DATA_DEADLINE': 'B_DATA_DEADLINE', 
                        'S_REQUESTED_DEADLINE_START_DATE': 'S_REQUESTED_DEADLINE_START_DATE',
                        'S_REQUESTED_DEADLINE_END_DATE': 'S_REQUESTED_DEADLINE_END_DATE',
                        'S_REQUIRED_ARRIVAL_DATE_EXPECTED': 'S_REQUIRED_ARRIVAL_DATE_EXPECTED',
                        'B_DATA_ESTIMATIVA_SAIDA_ETD': 'B_DATA_ESTIMATIVA_SAIDA_ETD',
                        'B_DATA_ESTIMATIVA_CHEGADA_ETA': 'B_DATA_ESTIMATIVA_CHEGADA_ETA',
                        'B_DATA_ABERTURA_GATE': 'B_DATA_ABERTURA_GATE',
                        'B_DATA_CONFIRMACAO_EMBARQUE': 'B_DATA_CONFIRMACAO_EMBARQUE',
                        'B_DATA_PARTIDA_ATD': 'B_DATA_PARTIDA_ATD',
                        'B_DATA_ESTIMADA_TRANSBORDO_ETD': 'B_DATA_ESTIMADA_TRANSBORDO_ETD',
                        'B_DATA_CHEGADA_ATA': 'B_DATA_CHEGADA_ATA',
                        'B_DATA_TRANSBORDO_ATD': 'B_DATA_TRANSBORDO_ATD',
                        'B_DATA_CHEGADA_DESTINO_ETA': 'B_DATA_CHEGADA_DESTINO_ETA',
                        'B_DATA_CHEGADA_DESTINO_ATA': 'B_DATA_CHEGADA_DESTINO_ATA',
                        'B_DATA_ESTIMATIVA_ATRACACAO_ETB': 'B_DATA_ESTIMATIVA_ATRACACAO_ETB',
                        'B_DATA_ATRACACAO_ATB': 'B_DATA_ATRACACAO_ATB'
                    }
                    for src_field, dest_field in date_fields_mapping.items():
                        # Acesso case-insensitive ao resultado do banco
                        src_field_lower = src_field.lower()
                        if src_field_lower in result and result[src_field_lower] is not None:
                            prefill_dates[dest_field] = result[src_field_lower]
            except Exception as e:
                # Se falhar, continua sem pré-preenchimento
                pass

        # Converte dados da UI para formato da tabela
        db_data = {}
        for ui_key, db_key in field_mapping.items():
            # Apenas processa chaves que existem no ui_data
            if ui_key in ui_data:
                value = ui_data[ui_key]
                # Converte valores especiais
                if (db_key.startswith("B_DATA_") or db_key.startswith("S_REQUESTED_") or db_key.startswith("S_REQUIRED_")) and isinstance(value, str) and value.strip():
                    try:
                        # Tenta converter data se for string
                        from datetime import datetime
                        if ":" in value:  # formato com hora
                            db_data[db_key] = datetime.strptime(value, "%Y-%m-%d %H:%M")
                        else:  # formato só data
                            db_data[db_key] = datetime.strptime(value, "%Y-%m-%d")
                    except:
                        db_data[db_key] = None # Define como None se a conversão falhar
                elif db_key == "PDF_BOOKING_EMISSION_DATE" and isinstance(value, str):
                    # Trunca PDF_BOOKING_EMISSION_DATE para máximo 18 caracteres (formato: YYYY-MM-DD HH:MM)
                    if len(value) > 18:
                        try:
                            from datetime import datetime
                            dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
                            db_data[db_key] = dt.strftime("%Y-%m-%d %H:%M")
                        except:
                            db_data[db_key] = value[:18]
                    else:
                        db_data[db_key] = value
                else:
                    if db_key == "P_PDF_NAME" and isinstance(value, str):
                        value = value.strip()
                        if len(value) > 200:
                            value = value[:200]
                    db_data[db_key] = value
        
        # Aplicar pré-preenchimento de datas (apenas se não fornecidas na UI)
        for date_field, date_value in prefill_dates.items():
            current_value = db_data.get(date_field)
            # Aplicar pré-preenchimento se o campo estiver None ou for string vazia
            if current_value is None or (isinstance(current_value, str) and current_value.strip() == ""):
                # Tratar tipos: colunas de destino são DATE, demais são DATETIME
                if date_field in ['B_DATA_CHEGADA_DESTINO_ETA', 'B_DATA_CHEGADA_DESTINO_ATA']:
                    # Converter para date() se for datetime
                    if hasattr(date_value, 'date'):
                        db_data[date_field] = date_value.date()
                    else:
                        db_data[date_field] = date_value
                else:
                    # Manter como datetime para as demais colunas
                    db_data[date_field] = date_value

        # Campos obrigatórios e padrões
        db_data["FAROL_STATUS"] = status_override or "Adjustment Requested"
        db_data["USER_INSERT"] = user_insert
        db_data["ADJUSTMENT_ID"] = str(uuid.uuid4())
        
        # Define P_STATUS com base na origem da solicitação
        db_data["P_STATUS"] = p_status_override or "Other Request - Company"
        
        # Campos de ajuste (se fornecidos)
        if area:
            db_data["AREA"] = area
        if request_reason:
            db_data["REQUEST_REASON"] = request_reason
        if adjustments_owner:
            db_data["ADJUSTMENTS_OWNER"] = adjustments_owner
        if comments:
            db_data["COMMENTS"] = comments
        
        # Adiciona ELLOX_MONITORING_ID ao db_data antes de construir a query
        db_data["ELLOX_MONITORING_ID"] = None # Temporariamente definido como NULL
        
        # Adiciona ROW_INSERTED_DATE com horário local do Brasil
        db_data["ROW_INSERTED_DATE"] = get_brazil_time()
        
        # SQL de inserção
        columns = list(db_data.keys())
        placeholders = [f":{col}" for col in columns]
        
        insert_sql = text(f"""
            INSERT INTO LogTransp.F_CON_RETURN_CARRIERS ({', '.join(columns)})
            VALUES ({', '.join(placeholders)})
        """)
        
        conn.execute(insert_sql, db_data)
        transaction.commit()
        return True, "Success"
        
    except Exception as e:
        if transaction:
            transaction.rollback()
        return False, str(e)
    finally:
        if conn:
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
        
        # Verificar se há dados (qualquer registro para esta combinação)
        existing_query = text("""
            SELECT COUNT(*) as count
            FROM LogTransp.F_ELLOX_TERMINAL_MONITORINGS 
            WHERE UPPER(NAVIO) = UPPER(:vessel_name)
            AND UPPER(VIAGEM) = UPPER(:voyage_code)
            AND UPPER(TERMINAL) = UPPER(:terminal)
        """)
        
        existing_count = conn.execute(existing_query, {
            "vessel_name": vessel_name,
            "voyage_code": voyage_code, 
            "terminal": terminal
        }).scalar()
        
        if existing_count > 0:
            # Buscar os dados existentes do banco
            data_query = text("""
                SELECT * FROM LogTransp.F_ELLOX_TERMINAL_MONITORINGS
                WHERE UPPER(NAVIO) = UPPER(:vessel_name)
                AND UPPER(VIAGEM) = UPPER(:voyage_code)
                AND UPPER(TERMINAL) = UPPER(:terminal)
                ORDER BY NVL(DATA_ATUALIZACAO, ROW_INSERTED_DATE) DESC
                FETCH FIRST 1 ROW ONLY
            """)
            
            # Use the existing 'conn' object
            result = conn.execute(data_query, {
                "vessel_name": vessel_name,
                "voyage_code": voyage_code,
                "terminal": terminal
            }).mappings().fetchone()
            
            # Convert result to dict with column names
            if result:
                existing_data = dict(result)
                
                # Check if any date field columns actually exist
                all_fields_upper = {k.upper() for k in existing_data.keys()}
                expected_date_fields_upper = {
                    "DATA_DEADLINE", "DATA_DRAFT_DEADLINE", "DATA_ABERTURA_GATE",
                    "DATA_ABERTURA_GATE_REEFER", "DATA_ESTIMATIVA_SAIDA",
                    "DATA_ESTIMATIVA_CHEGADA", "DATA_ESTIMATIVA_ATRACACAO",
                    "DATA_ATRACACAO", "DATA_PARTIDA", "DATA_CHEGADA"
                }
                
                # Include all date fields from the record (even if None)
                # Use case-insensitive matching
                api_data = {}
                for field in existing_data.keys():
                    if field.upper() in expected_date_fields_upper:
                        api_data[field] = existing_data[field]
                        
                return {
                    "success": True,
                    "data": api_data,
                    "message": f"🟢 Dados de Voyage Monitoring encontrados no banco para 🚢 {vessel_name} | {voyage_code} | {terminal}",
                    "requires_manual": False
                }
            else:
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
                    FROM LogTransp.F_ELLOX_TERMINALS
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
        
        # Verificar se a consulta foi bem-sucedida
        if not mon_resp.get("success"):
            return {
                "success": False,
                "data": None,
                "message": f"🔵 Voyage Não Encontrada na API\n\n🚢 {vessel_name} | {voyage_code} | {terminal}\n\nEsta viagem não está disponível na base da API Ellox. Isso é normal - nem todas as viagens estão na API.\n\nUse o formulário manual abaixo para inserir os dados de monitoramento.",
                "requires_manual": True,
                "error_type": "voyage_not_found",
                "cnpj_terminal": cnpj_terminal,
                "agencia": ""
            }
        
        # Se success=True mas data está vazio, ainda assim a viagem foi encontrada
        # A API pode retornar success=True com data=None para viagens sem dados de monitoramento
        data_list = mon_resp.get("data", [])
        
        # Se não há dados de monitoramento, mas a viagem foi encontrada, usar formulário manual
        if not data_list or (isinstance(data_list, list) and len(data_list) == 0):
            return {
                "success": False,
                "data": None,
                "message": f"🔵 Viagem Encontrada na API, mas sem Dados de Monitoramento\n\n🚢 {vessel_name} | {voyage_code} | {terminal}\n\nA viagem foi localizada na API Ellox, mas não possui dados de monitoramento disponíveis.\n\nUse o formulário manual abaixo para inserir os dados de monitoramento.",
                "requires_manual": True,
                "error_type": "voyage_found_no_data",
                "cnpj_terminal": cnpj_terminal,
                "agencia": ""
            }
        
        # 5. Processar dados da API (data_list já foi definido acima)
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
                "message": f"🟢 Dados de Voyage Monitoring encontrados na API para 🚢 {vessel_name} | {voyage_code} | {terminal}",
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
            processed_count = upsert_terminal_monitorings_from_dataframe(df_monitoring, data_source='API')
            
            if processed_count > 0:
                return {
                    "success": True,
                    "data": api_data,
                    "message": f"🟢 Dados de Voyage Monitoring encontrados e salvos da API para 🚢 {vessel_name} | {voyage_code} | {terminal}",
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
                # B_DATA_ABERTURA_GATE_REEFER só existe em LogTransp.F_ELLOX_TERMINAL_MONITORINGS, não em F_CON_RETURN_CARRIERS
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
            
            # Para dados manuais, verificar se já existe monitoramento e vincular
            if vessel_name_result:
                vessel_name = vessel_name_result.get("b_vessel_name")
                voyage_code = vessel_name_result.get("b_voyage_code") or ""
                terminal = vessel_name_result.get("b_terminal") or ""
                
                if vessel_name and terminal:
                    existing_monitoring_id = check_for_existing_monitoring(conn, vessel_name, voyage_code, terminal)
                    if existing_monitoring_id:
                        elox_update_values["ELLOX_MONITORING_ID"] = existing_monitoring_id
                        st.success(f"🔗 Vinculado ao monitoramento existente ID: {existing_monitoring_id}")
                    else:
                        st.warning("⚠️ Nenhum monitoramento existente encontrado para vinculação manual.")
                        pass
        
        if vessel_name_result:
            vessel_name = vessel_name_result.get("b_vessel_name")
            voyage_code = vessel_name_result.get("b_voyage_code") or ""
            terminal = vessel_name_result.get("b_terminal") or ""
            
            if vessel_name and terminal and not manual_voyage_data:
                # Dados de voyage monitoring já foram coletados durante o processamento do PDF
                # Apenas buscar dados existentes de F_ELLOX_TERMINAL_MONITORINGS
                
                # Verificar se já existem dados para esta combinação
                existing_monitoring_id = check_for_existing_monitoring(conn, vessel_name, voyage_code, terminal)
                
                # Buscar dados do registro existente para preencher elox_update_values
                if existing_monitoring_id:
                    monitoring_query = text("""
                        SELECT * FROM LogTransp.F_ELLOX_TERMINAL_MONITORINGS
                        WHERE ID = :monitoring_id
                    """)
                    existing_record = conn.execute(monitoring_query, {"monitoring_id": existing_monitoring_id}).mappings().fetchone()
                    
                    if existing_record:
                        column_mapping = {
                            'DATA_DRAFT_DEADLINE': 'B_DATA_DRAFT_DEADLINE', 
                            'DATA_DEADLINE': 'B_DATA_DEADLINE',
                            'DATA_ESTIMATIVA_SAIDA': 'B_DATA_ESTIMATIVA_SAIDA_ETD', 
                            'DATA_ESTIMATIVA_CHEGADA': 'B_DATA_ESTIMATIVA_CHEGADA_ETA',
                            'DATA_ABERTURA_GATE': 'B_DATA_ABERTURA_GATE', 
                            'DATA_PARTIDA': 'B_DATA_PARTIDA_ATD',
                            'DATA_CHEGADA': 'B_DATA_CHEGADA_ATA', 
                            'DATA_ESTIMATIVA_ATRACACAO': 'B_DATA_ESTIMATIVA_ATRACACAO_ETB',
                            'DATA_ATRACACAO': 'B_DATA_ATRACACAO_ATB',
                        }
                        for elox_col, return_col in column_mapping.items():
                            if elox_col.lower() in existing_record and existing_record[elox_col.lower()] is not None:
                                elox_update_values[return_col] = existing_record[elox_col.lower()]
                        
                        elox_update_values["ELLOX_MONITORING_ID"] = existing_monitoring_id

        # 3. Prepare and execute the UPDATE on F_CON_RETURN_CARRIERS
        # Usar o usuário logado para a aprovação
        current_user = get_current_user_login()
        update_params = {"adjustment_id": adjustment_id, "user_update": current_user}
        update_params.update(elox_update_values)

        set_clauses = [f"{col} = :{col}" for col in elox_update_values.keys()]
        set_clauses.append("FAROL_STATUS = 'Booking Approved'")
        set_clauses.append("USER_UPDATE = :user_update")
        set_clauses.append("DATE_UPDATE = SYSDATE")

        if related_reference == "New Adjustment":
            update_params.update(justification)
            set_clauses.extend(["Linked_Reference = 'New Adjustment'", "AREA = :area", "REQUEST_REASON = :request_reason", "ADJUSTMENTS_OWNER = :adjustments_owner", "COMMENTS = :comments"])
        else:
            # Para aprovação de PDF/retorno do carrier, apenas atualizar Linked_Reference
            # Mantém as justificativas originais (se o registro veio de ajuste/split, elas permanecem)
            ref_str = str(related_reference) if related_reference is not None else ''
            # O formato já está montado corretamente em history.py no formato: "Index X | Booking Requested | 29-10-2025"
            # Apenas limitar para evitar overflow em colunas com tamanho restrito
            if len(ref_str) > 100:
                ref_str = ref_str[:100]
            update_params["linked_ref"] = ref_str
            set_clauses.append("Linked_Reference = :linked_ref")

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
        # Primeiro, buscar valores atuais para auditoria
        current_values_query = text("""
            SELECT S_PLACE_OF_RECEIPT, S_QUANTITY_OF_CONTAINERS,
                   S_PORT_OF_LOADING_POL, S_PORT_OF_DELIVERY_POD, S_FINAL_DESTINATION,
                   B_BOOKING_REFERENCE, B_TRANSHIPMENT_PORT, B_TERMINAL, B_VESSEL_NAME,
                   B_VOYAGE_CODE, B_VOYAGE_CARRIER, B_DATA_DRAFT_DEADLINE, B_DATA_DEADLINE,
                   S_REQUESTED_DEADLINE_START_DATE, S_REQUESTED_DEADLINE_END_DATE,
                   B_DATA_ESTIMATIVA_SAIDA_ETD, B_DATA_ESTIMATIVA_CHEGADA_ETA, B_DATA_ABERTURA_GATE,
                   B_DATA_PARTIDA_ATD, B_DATA_CHEGADA_ATA, B_DATA_ESTIMATIVA_ATRACACAO_ETB, B_DATA_ATRACACAO_ATB,
                   S_REQUIRED_ARRIVAL_DATE_EXPECTED, B_BOOKING_CONFIRMATION_DATE, FAROL_STATUS
            FROM LogTransp.F_CON_SALES_BOOKING_DATA
            WHERE FAROL_REFERENCE = :farol_reference
        """)
        # Usar mapeamento por nome para evitar erros de índice e depender menos da ordem das colunas
        current_row = conn.execute(current_values_query, {"farol_reference": farol_reference}).mappings().fetchone()
        if current_row is None:
            raise Exception(f"Farol Reference {farol_reference} not found in F_CON_SALES_BOOKING_DATA.")
        
        main_update_fields = {"farol_reference": farol_reference, "FAROL_STATUS": "Booking Approved"}
        fields_to_propagate = [
            "S_PLACE_OF_RECEIPT", "S_QUANTITY_OF_CONTAINERS",
            "S_PORT_OF_LOADING_POL", "S_PORT_OF_DELIVERY_POD", "S_FINAL_DESTINATION",
            "B_BOOKING_REFERENCE", "B_TRANSHIPMENT_PORT", "B_TERMINAL", "B_VESSEL_NAME",
            "B_VOYAGE_CODE", "B_VOYAGE_CARRIER", "B_DATA_DRAFT_DEADLINE", "B_DATA_DEADLINE",
            "S_REQUESTED_DEADLINE_START_DATE", "S_REQUESTED_DEADLINE_END_DATE",
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
            if field == "B_DATA_DRAFT_DEADLINE":
                # Lógica especial para preservar Draft Deadline manual
                pdf_has_value = False
                if field in row and row[field] is not None:
                    val = _normalize_value(row[field])
                    if val is not None and not (isinstance(val, str) and val.strip() == ""):
                        # PDF tem valor válido - usar ele (prioridade)
                        main_update_fields[field] = val
                        pdf_has_value = True
                
                # Se PDF não tem valor válido, preservar valor manual existente
                if not pdf_has_value:
                    if current_row and field in current_row:
                        existing_value = current_row.get(field, None)
                        if existing_value is not None:
                            # Preservar valor manual existente
                            main_update_fields[field] = existing_value
                    # Se não há valor existente e PDF não tem valor, não adicionar ao update
            else:
                # Para outros campos, comportamento normal
                if field in row and row[field] is not None:
                    val = _normalize_value(row[field])
                    if val is None:
                        continue
                    if isinstance(val, str) and val.strip() == "":
                        continue
                    main_update_fields[field] = val

        # Mapeamento especial: S_REQUIRED_ARRIVAL_DATE_EXPECTED (carriers) -> S_REQUIRED_ARRIVAL_DATE_EXPECTED (principal)
        if "S_REQUIRED_ARRIVAL_DATE_EXPECTED" in row and row["S_REQUIRED_ARRIVAL_DATE_EXPECTED"] is not None:
            val = _normalize_value(row["S_REQUIRED_ARRIVAL_DATE_EXPECTED"])
            if val is not None and not (isinstance(val, str) and val.strip() == ""):
                main_update_fields["S_REQUIRED_ARRIVAL_DATE_EXPECTED"] = val

        # Atualizar FAROL_STATUS na tabela principal
        main_update_fields['FAROL_STATUS'] = 'Booking Approved'
        
        main_set_clause = ", ".join([f"{field} = :{field}" for field in main_update_fields.keys() if field != 'farol_reference'])
        main_update_query = text(f"UPDATE LogTransp.F_CON_SALES_BOOKING_DATA SET {main_set_clause} WHERE FAROL_REFERENCE = :farol_reference")
        conn.execute(main_update_query, main_update_fields)
        
        # Auditoria para campos alterados na aprovação
        if current_row:
            current_values = {
                "S_PLACE_OF_RECEIPT": current_row.get("S_PLACE_OF_RECEIPT"),
                "S_QUANTITY_OF_CONTAINERS": current_row.get("S_QUANTITY_OF_CONTAINERS"),
                "S_PORT_OF_LOADING_POL": current_row.get("S_PORT_OF_LOADING_POL"),
                "S_PORT_OF_DELIVERY_POD": current_row.get("S_PORT_OF_DELIVERY_POD"),
                "S_FINAL_DESTINATION": current_row.get("S_FINAL_DESTINATION"),
                "B_BOOKING_REFERENCE": current_row.get("B_BOOKING_REFERENCE"),
                "B_TRANSHIPMENT_PORT": current_row.get("B_TRANSHIPMENT_PORT"),
                "B_TERMINAL": current_row.get("B_TERMINAL"),
                "B_VESSEL_NAME": current_row.get("B_VESSEL_NAME"),
                "B_VOYAGE_CODE": current_row.get("B_VOYAGE_CODE"),
                "B_VOYAGE_CARRIER": current_row.get("B_VOYAGE_CARRIER"),
                "B_DATA_DRAFT_DEADLINE": current_row.get("B_DATA_DRAFT_DEADLINE"),
                "B_DATA_DEADLINE": current_row.get("B_DATA_DEADLINE"),
                "S_REQUESTED_DEADLINE_START_DATE": current_row.get("S_REQUESTED_DEADLINE_START_DATE"),
                "S_REQUESTED_DEADLINE_END_DATE": current_row.get("S_REQUESTED_DEADLINE_END_DATE"),
                "B_DATA_ESTIMATIVA_SAIDA_ETD": current_row.get("B_DATA_ESTIMATIVA_SAIDA_ETD"),
                "B_DATA_ESTIMATIVA_CHEGADA_ETA": current_row.get("B_DATA_ESTIMATIVA_CHEGADA_ETA"),
                "B_DATA_ABERTURA_GATE": current_row.get("B_DATA_ABERTURA_GATE"),
                "B_DATA_PARTIDA_ATD": current_row.get("B_DATA_PARTIDA_ATD"),
                "B_DATA_CHEGADA_ATA": current_row.get("B_DATA_CHEGADA_ATA"),
                "B_DATA_ESTIMATIVA_ATRACACAO_ETB": current_row.get("B_DATA_ESTIMATIVA_ATRACACAO_ETB"),
                "B_DATA_ATRACACAO_ATB": current_row.get("B_DATA_ATRACACAO_ATB"),
                "S_REQUIRED_ARRIVAL_DATE_EXPECTED": current_row.get("S_REQUIRED_ARRIVAL_DATE_EXPECTED"),
                "B_BOOKING_CONFIRMATION_DATE": current_row.get("B_BOOKING_CONFIRMATION_DATE"),
                "FAROL_STATUS": current_row.get("FAROL_STATUS"),
            }
            
            # Auditar mudança de status
            audit_change(conn, farol_reference, 'F_CON_SALES_BOOKING_DATA', 'FAROL_STATUS', 
                        current_values["FAROL_STATUS"], "Booking Approved", 'history', 'UPDATE', 
                        adjustment_id=adjustment_id, related_ref=related_reference)
            
            # Auditar outros campos que mudaram
            for field in fields_to_propagate:
                if field in main_update_fields and field in current_values:
                    old_val = current_values[field]
                    new_val = main_update_fields[field]
                    if old_val != new_val:
                        audit_change(conn, farol_reference, 'F_CON_SALES_BOOKING_DATA', field, 
                                   old_val, new_val, 'history', 'UPDATE', 
                                   adjustment_id=adjustment_id, related_ref=related_reference)
            
            # Auditar campos especiais
            if "S_REQUIRED_ARRIVAL_DATE_EXPECTED" in main_update_fields:
                old_val = current_values["S_REQUIRED_ARRIVAL_DATE_EXPECTED"]
                new_val = main_update_fields["S_REQUIRED_ARRIVAL_DATE_EXPECTED"]
                if old_val != new_val:
                    audit_change(conn, farol_reference, 'F_CON_SALES_BOOKING_DATA', 'S_REQUIRED_ARRIVAL_DATE_EXPECTED', 
                               old_val, new_val, 'history', 'UPDATE', 
                               adjustment_id=adjustment_id, related_ref=related_reference)
            
            if "B_BOOKING_CONFIRMATION_DATE" in main_update_fields:
                old_val = current_values["B_BOOKING_CONFIRMATION_DATE"]
                new_val = main_update_fields["B_BOOKING_CONFIRMATION_DATE"]
                if old_val != new_val:
                    audit_change(conn, farol_reference, 'F_CON_SALES_BOOKING_DATA', 'B_BOOKING_CONFIRMATION_DATE', 
                               old_val, new_val, 'history', 'UPDATE', 
                               adjustment_id=adjustment_id, related_ref=related_reference)

        # 6. Buscar últimos valores de data e atualizar colunas de expectativa interna no registro existente da tabela carriers
        try:
            # Buscar últimos valores dos campos de data da F_CON_RETURN_CARRIERS
            last_date_values = get_last_date_values_from_carriers(farol_reference)
            
            carrier_update_fields = {}
            
            # Sempre tentar preencher com os últimos valores encontrados
            if last_date_values.get("S_REQUESTED_DEADLINE_START_DATE"):
                carrier_update_fields["S_REQUESTED_DEADLINE_START_DATE"] = last_date_values.get("S_REQUESTED_DEADLINE_START_DATE")
                
            if last_date_values.get("S_REQUESTED_DEADLINE_END_DATE"):
                carrier_update_fields["S_REQUESTED_DEADLINE_END_DATE"] = last_date_values.get("S_REQUESTED_DEADLINE_END_DATE")
                
            if last_date_values.get("S_REQUIRED_ARRIVAL_DATE_EXPECTED"):
                carrier_update_fields["S_REQUIRED_ARRIVAL_DATE_EXPECTED"] = last_date_values.get("S_REQUIRED_ARRIVAL_DATE_EXPECTED")
            
            if carrier_update_fields:
                carrier_set_clause = ", ".join([f"{field} = :{field}" for field in carrier_update_fields.keys()])
                carrier_update_query = text(f"UPDATE LogTransp.F_CON_RETURN_CARRIERS SET {carrier_set_clause} WHERE ADJUSTMENT_ID = :adjustment_id")
                carrier_update_fields["adjustment_id"] = adjustment_id
                
                conn.execute(carrier_update_query, carrier_update_fields)
                # st.info(f"📝 Campos de data pré-preenchidos com últimos valores encontrados para {farol_reference}")
                
        except Exception as e:
            # Log do erro mas não falha toda a operação
            # st.error(f"❌ Erro ao pré-preencher campos: {e}")
            pass

        # 7. Commit transaction
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

def get_last_date_values_from_carriers(farol_reference: str) -> dict:
    """
    Busca os últimos valores dos campos de data da tabela F_CON_RETURN_CARRIERS
    para uma Farol Reference específica, independentemente do status.
    
    :param farol_reference: Referência do Farol para buscar os valores
    :return: Dicionário com os últimos valores dos campos de data
    """
    conn = get_database_connection()
    try:
        query = text("""
            SELECT 
                S_REQUESTED_DEADLINE_START_DATE,
                S_REQUESTED_DEADLINE_END_DATE,
                S_REQUIRED_ARRIVAL_DATE_EXPECTED,
                ROW_INSERTED_DATE,
                FAROL_STATUS,
                ADJUSTMENT_ID
            FROM LogTransp.F_CON_RETURN_CARRIERS
            WHERE UPPER(FAROL_REFERENCE) = UPPER(:farol_ref)
            ORDER BY ROW_INSERTED_DATE DESC
            FETCH FIRST 1 ROWS ONLY
        """)
        
        result = conn.execute(query, {"farol_ref": farol_reference}).mappings().fetchone()
        
        if result:
            return {
                "S_REQUESTED_DEADLINE_START_DATE": result.get("S_REQUESTED_DEADLINE_START_DATE"),
                "S_REQUESTED_DEADLINE_END_DATE": result.get("S_REQUESTED_DEADLINE_END_DATE"),
                "S_REQUIRED_ARRIVAL_DATE_EXPECTED": result.get("S_REQUIRED_ARRIVAL_DATE_EXPECTED")
            }
        else:
            return {}
    except Exception as e:
        return {}
    finally:
        conn.close()

def is_currently_linked_to_voyage(conn, farol_ref, vessel, voyage, terminal):
    """
    Verifica se o Farol Reference está atualmente vinculado a esta viagem.
    Retorna True apenas se for a relação mais recente.
    """
    query = text("""
        SELECT 1 FROM (
            SELECT FAROL_REFERENCE, B_VESSEL_NAME, B_VOYAGE_CODE, B_TERMINAL,
                   ROW_NUMBER() OVER (
                       PARTITION BY FAROL_REFERENCE 
                       ORDER BY ROW_INSERTED_DATE DESC
                   ) as rn
            FROM LogTransp.F_CON_RETURN_CARRIERS
            WHERE FAROL_REFERENCE = :fr
        ) WHERE rn = 1 
          AND UPPER(TRIM(B_VESSEL_NAME)) = UPPER(TRIM(:vessel))
          AND UPPER(TRIM(B_VOYAGE_CODE)) = UPPER(TRIM(:voyage))
          AND UPPER(TRIM(B_TERMINAL)) = UPPER(TRIM(:terminal))
    """)
    
    result = conn.execute(query, {
        'fr': farol_ref,
        'vessel': vessel,
        'voyage': voyage,
        'terminal': terminal
    }).fetchone()
    
    return result is not None

def update_booking_from_voyage(changes: list) -> tuple[bool, str]:
    """
    Processes manual updates from the voyage update screen.
    """
    if not changes:
        return False, "No changes provided."

    conn = get_database_connection()
    transaction = conn.begin()

    COLUMN_MAPPING = {
        "DATA_ESTIMATIVA_SAIDA": "B_DATA_ESTIMATIVA_SAIDA_ETD",
        "DATA_ESTIMATIVA_CHEGADA": "B_DATA_ESTIMATIVA_CHEGADA_ETA",
        "DATA_DEADLINE": "B_DATA_DEADLINE",
        "DATA_DRAFT_DEADLINE": "B_DATA_DRAFT_DEADLINE",
        "DATA_ABERTURA_GATE": "B_DATA_ABERTURA_GATE",
        "DATA_ATRACACAO": "B_DATA_ATRACACAO_ATB",
        "DATA_PARTIDA": "B_DATA_PARTIDA_ATD",
        "DATA_CHEGADA": "B_DATA_CHEGADA_ATA",
        "DATA_ESTIMATIVA_ATRACACAO": "B_DATA_ESTIMATIVA_ATRACACAO_ETB",
        "B_DATA_CONFIRMACAO_EMBARQUE": "B_DATA_CONFIRMACAO_EMBARQUE",
        "B_DATA_ESTIMADA_TRANSBORDO_ETD": "B_DATA_ESTIMADA_TRANSBORDO_ETD",
        "B_DATA_TRANSBORDO_ATD": "B_DATA_TRANSBORDO_ATD",
        "B_DATA_CHEGADA_DESTINO_ETA": "B_DATA_CHEGADA_DESTINO_ETA",
        "B_DATA_CHEGADA_DESTINO_ATA": "B_DATA_CHEGADA_DESTINO_ATA",
    }

    try:
        from collections import defaultdict
        import pandas as pd
        import uuid

        voyage_updates = defaultdict(lambda: {'fields': {}, 'farol_references': None, 'id': None})
        for change in changes:
            voyage_key = (change['vessel_name'], change['voyage_code'], change['terminal'])
            voyage_updates[voyage_key]['fields'][change['field_name']] = {
                'new_value': change['new_value'],
                'old_value': change['old_value']
            }
            voyage_updates[voyage_key]['farol_references'] = change['farol_references']
            voyage_updates[voyage_key]['id'] = change['id']

        for voyage_key, update_data in voyage_updates.items():
            vessel_name, voyage_code, terminal = voyage_key
            changed_fields = update_data['fields']
            farol_references_str = update_data['farol_references']
            original_monitoring_id = int(update_data['id'])

            latest_monitoring_query = text("SELECT * FROM LogTransp.F_ELLOX_TERMINAL_MONITORINGS WHERE ID = :id")
            template_record = conn.execute(latest_monitoring_query, {"id": original_monitoring_id}).mappings().fetchone()

            if not template_record:
                raise Exception(f"Could not find original monitoring record with ID {original_monitoring_id}")

            new_monitoring_record = dict(template_record)
            new_monitoring_record['id'] = uuid.uuid4().int >> 64

            for field_name, values in changed_fields.items():
                new_val = values['new_value']
                if isinstance(new_val, pd.Timestamp):
                    new_val = new_val.to_pydatetime()
                if field_name.lower() in new_monitoring_record:
                    new_monitoring_record[field_name.lower()] = new_val
            
            # FIX: Explicitly set new timestamps for the new record
            now = get_brazil_time()
            new_monitoring_record['data_atualizacao'] = now
            if 'row_inserted_date' in new_monitoring_record:
                new_monitoring_record['row_inserted_date'] = now
            
            # Definir DATA_SOURCE como 'MANUAL' para alterações via Voyage Update
            new_monitoring_record['data_source'] = 'MANUAL'

            monitoring_cols = ", ".join(new_monitoring_record.keys())
            monitoring_placeholders = ", ".join([f":{k}" for k in new_monitoring_record.keys()])
            insert_monitoring_sql = text(f"INSERT INTO LogTransp.F_ELLOX_TERMINAL_MONITORINGS ({monitoring_cols}) VALUES ({monitoring_placeholders})")
            conn.execute(insert_monitoring_sql, new_monitoring_record)

            if not farol_references_str or pd.isna(farol_references_str):
                continue

            farol_references = [ref.strip() for ref in farol_references_str.split(',')]

            for fr in farol_references:
                update_clauses = []
                update_params = {'farol_reference': fr}
                log_entries = []
                
                for field_name, values in changed_fields.items():
                    main_table_col = COLUMN_MAPPING.get(field_name.upper())
                    if main_table_col:
                        update_clauses.append(f"{main_table_col} = :{main_table_col}")
                        new_val = values['new_value']
                        if isinstance(new_val, pd.Timestamp):
                            new_val = new_val.to_pydatetime()
                        
                        # Para colunas de destino (DATE), converter datetime para date
                        if main_table_col in ['B_DATA_CHEGADA_DESTINO_ETA', 'B_DATA_CHEGADA_DESTINO_ATA']:
                            if new_val is not None and hasattr(new_val, 'date'):
                                new_val = new_val.date()
                        
                        update_params[main_table_col] = new_val

                        log_entries.append({
                            "farol_reference": fr,
                            "field_name": main_table_col,
                            "old_value": str(values['old_value']) if values['old_value'] is not None else None,
                            "new_value": str(new_val) if new_val is not None else None,
                            "updated_by": "system"
                        })

                if update_clauses:
                    # Buscar valores atuais para auditoria
                    current_values_query = text("""
                        SELECT B_DATA_ESTIMATIVA_SAIDA_ETD, B_DATA_ESTIMATIVA_CHEGADA_ETA, B_DATA_DEADLINE,
                               B_DATA_DRAFT_DEADLINE, B_DATA_ABERTURA_GATE, B_DATA_ATRACACAO_ATB,
                               B_DATA_PARTIDA_ATD, B_DATA_CHEGADA_ATA, B_DATA_ESTIMATIVA_ATRACACAO_ETB,
                               B_DATA_CONFIRMACAO_EMBARQUE, B_DATA_ESTIMADA_TRANSBORDO_ETD, B_DATA_TRANSBORDO_ATD,
                               B_DATA_CHEGADA_DESTINO_ETA, B_DATA_CHEGADA_DESTINO_ATA
                        FROM LogTransp.F_CON_SALES_BOOKING_DATA
                        WHERE UPPER(TRIM(FAROL_REFERENCE)) = UPPER(TRIM(:farol_reference))
                    """)
                    current_row = conn.execute(current_values_query, {"farol_reference": fr}).fetchone()
                    
                    # Use robust WHERE clause and log changes after successful update
                    update_sql = text(f"UPDATE LogTransp.F_CON_SALES_BOOKING_DATA SET {', '.join(update_clauses)} WHERE UPPER(TRIM(FAROL_REFERENCE)) = UPPER(TRIM(:farol_reference))")
                    result = conn.execute(update_sql, update_params)

                    # Only log if the update was successful (affected rows > 0)
                    if result.rowcount > 0 and log_entries:
                        # Auditoria para cada campo alterado
                        if current_row:
                            current_values = {
                                "B_DATA_ESTIMATIVA_SAIDA_ETD": current_row[0],
                                "B_DATA_ESTIMATIVA_CHEGADA_ETA": current_row[1],
                                "B_DATA_DEADLINE": current_row[2],
                                "B_DATA_DRAFT_DEADLINE": current_row[3],
                                "B_DATA_ABERTURA_GATE": current_row[4],
                                "B_DATA_ATRACACAO_ATB": current_row[5],
                                "B_DATA_PARTIDA_ATD": current_row[6],
                                "B_DATA_CHEGADA_ATA": current_row[7],
                                "B_DATA_ESTIMATIVA_ATRACACAO_ETB": current_row[8],
                                "B_DATA_CONFIRMACAO_EMBARQUE": current_row[9],
                                "B_DATA_ESTIMADA_TRANSBORDO_ETD": current_row[10],
                                "B_DATA_TRANSBORDO_ATD": current_row[11],
                                "B_DATA_CHEGADA_DESTINO_ETA": current_row[12],
                                "B_DATA_CHEGADA_DESTINO_ATA": current_row[13],
                            }
                            
                            for field_name, values in changed_fields.items():
                                main_table_col = COLUMN_MAPPING.get(field_name.upper())
                                if main_table_col and main_table_col in current_values:
                                    old_val = current_values[main_table_col]
                                    new_val = values['new_value']
                                    if isinstance(new_val, pd.Timestamp):
                                        new_val = new_val.to_pydatetime()
                                    
                                    # Para colunas de destino (DATE), converter datetime para date
                                    if main_table_col in ['B_DATA_CHEGADA_DESTINO_ETA', 'B_DATA_CHEGADA_DESTINO_ATA']:
                                        if new_val is not None and hasattr(new_val, 'date'):
                                            new_val = new_val.date()
                                    
                                    # Verificar se FR está atualmente vinculado a esta viagem
                                    if is_currently_linked_to_voyage(conn, fr, 
                                                                      change['vessel_name'], 
                                                                      change['voyage_code'], 
                                                                      change['terminal']):
                                        audit_change(conn, fr, 'F_CON_SALES_BOOKING_DATA', main_table_col, 
                                                   old_val, new_val, 'tracking', 'UPDATE')

        transaction.commit()
        return True, "Changes saved successfully."

    except Exception as e:
        if transaction:
            transaction.rollback()
        return False, str(e)
    finally:
        if conn:
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
            SET FAROL_STATUS = :new_status,
                USER_UPDATE = :user_update,
                DATE_UPDATE = SYSDATE
            WHERE ADJUSTMENT_ID = :adjustment_id
        """)
        
        result = conn.execute(update_query, {
            "new_status": new_status,
            "user_update": get_current_user_login(),
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
                FAROL_STATUS,
                P_STATUS,
                P_PDF_NAME,
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
                B_DATA_CONFIRMACAO_EMBARQUE,
                B_DATA_PARTIDA_ATD,
                B_DATA_ESTIMADA_TRANSBORDO_ETD,
                B_DATA_CHEGADA_ATA,
                B_DATA_TRANSBORDO_ATD,
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
    """Retorna o FAROL_STATUS da F_CON_RETURN_CARRIERS para o ADJUSTMENT_ID dado."""
    conn = get_database_connection()
    try:
        query = text(
            """
            SELECT FAROL_STATUS
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
    """Verifica se a tabela LogTransp.F_ELLOX_TERMINAL_MONITORINGS existe e é acessível."""
    conn = get_database_connection()
    try:
        # Verificar se a tabela existe no LogTransp
        exists = conn.execute(text("""
            SELECT COUNT(*) AS ct
            FROM all_tables
            WHERE owner = 'LOGTRANSP' 
            AND table_name = 'F_ELLOX_TERMINAL_MONITORINGS'
        """)).scalar()

        if int(exists or 0) == 0:
            print("❌ Tabela LogTransp.F_ELLOX_TERMINAL_MONITORINGS não existe")
            print("💡 Execute o script de criação das tabelas primeiro")
            return False
        else:
            print("✅ Tabela LogTransp.F_ELLOX_TERMINAL_MONITORINGS existe e é acessível")
            return True
            
    except Exception as e:
        print(f"❌ Erro ao verificar tabela: {e}")
        return False
def upsert_terminal_monitorings_from_dataframe(df: pd.DataFrame, data_source: str = 'MANUAL') -> int:
    """Realiza upsert (MERGE) em LogTransp.F_ELLOX_TERMINAL_MONITORINGS a partir de um DataFrame.

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
                "ROW_INSERTED_DATE": _datetime.now(),
                "DATA_SOURCE": data_source
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

            # Verificar se já existe um registro com os mesmos dados para evitar duplicatas exatas
            # Mas permitir inserção se não há dados para esta combinação navio/viagem/terminal
            check_existing_sql = text("""
                SELECT COUNT(*) as count
                FROM LogTransp.F_ELLOX_TERMINAL_MONITORINGS
                WHERE UPPER(NAVIO) = UPPER(:NAVIO)
                AND UPPER(VIAGEM) = UPPER(:VIAGEM)
                AND UPPER(TERMINAL) = UPPER(:TERMINAL)
            """)
            
            existing_count = conn.execute(check_existing_sql, {
                "NAVIO": params["NAVIO"],
                "VIAGEM": params["VIAGEM"], 
                "TERMINAL": params["TERMINAL"]
            }).fetchone()[0]
            
            # Verificar duplicata exata apenas se já existem dados para esta combinação
            if existing_count > 0:
                check_duplicate_sql = text("""
                    SELECT COUNT(*) as count
                    FROM LogTransp.F_ELLOX_TERMINAL_MONITORINGS
                    WHERE UPPER(NAVIO) = UPPER(:NAVIO)
                    AND UPPER(VIAGEM) = UPPER(:VIAGEM)
                    AND UPPER(TERMINAL) = UPPER(:TERMINAL)
                    AND NVL(DATA_ATUALIZACAO, ROW_INSERTED_DATE) = :DATA_ATUALIZACAO
                    AND NVL(CNPJ_TERMINAL, 'NULL') = NVL(:CNPJ_TERMINAL, 'NULL')
                    AND NVL(AGENCIA, 'NULL') = NVL(:AGENCIA, 'NULL')
                """)
                
                duplicate_count = conn.execute(check_duplicate_sql, {
                    "NAVIO": params["NAVIO"],
                    "VIAGEM": params["VIAGEM"], 
                    "TERMINAL": params["TERMINAL"],
                    "DATA_ATUALIZACAO": params["DATA_ATUALIZACAO"],
                    "CNPJ_TERMINAL": params["CNPJ_TERMINAL"],
                    "AGENCIA": params["AGENCIA"]
                }).fetchone()[0]
                
                # Se é duplicata exata, não inserir
                if duplicate_count > 0:
                    print(f"⚠️ Duplicata exata encontrada para {params['NAVIO']} - {params['VIAGEM']} - {params['TERMINAL']}, pulando inserção.")
                    continue
            
            # Inserir novo registro (primeira vez ou não é duplicata exata)
            insert_sql = text("""
                INSERT INTO LogTransp.F_ELLOX_TERMINAL_MONITORINGS (
                    ID, NAVIO, VIAGEM, AGENCIA, DATA_DEADLINE, DATA_DRAFT_DEADLINE,
                    DATA_ABERTURA_GATE, DATA_ABERTURA_GATE_REEFER, DATA_ESTIMATIVA_SAIDA,
                    DATA_ESTIMATIVA_CHEGADA, DATA_ATUALIZACAO, TERMINAL, CNPJ_TERMINAL,
                    DATA_CHEGADA, DATA_ESTIMATIVA_ATRACACAO, DATA_ATRACACAO, DATA_PARTIDA, ROW_INSERTED_DATE,
                    DATA_SOURCE
                ) VALUES (
                    :ID, :NAVIO, :VIAGEM, :AGENCIA, :DATA_DEADLINE, :DATA_DRAFT_DEADLINE,
                    :DATA_ABERTURA_GATE, :DATA_ABERTURA_GATE_REEFER, :DATA_ESTIMATIVA_SAIDA,
                    :DATA_ESTIMATIVA_CHEGADA, :DATA_ATUALIZACAO, :TERMINAL, :CNPJ_TERMINAL,
                    :DATA_CHEGADA, :DATA_ESTIMATIVA_ATRACACAO, :DATA_ATRACACAO, :DATA_PARTIDA, :ROW_INSERTED_DATE,
                    :DATA_SOURCE
                )
            """)
            conn.execute(insert_sql, params)
            processed += 1

        conn.commit()
    return processed

def get_terminal_monitorings(limit: int = 200) -> pd.DataFrame:
    """Consulta recentes da LogTransp.F_ELLOX_TERMINAL_MONITORINGS."""
    ensure_table_f_ellox_terminal_monitorings()
    with get_database_connection() as conn:
        rows = conn.execute(text(
            f"""
            SELECT *
            FROM LogTransp.F_ELLOX_TERMINAL_MONITORINGS
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
            SET FAROL_STATUS = :new_status, USER_UPDATE = 'System', DATE_UPDATE = SYSDATE
            WHERE ADJUSTMENT_ID = :adj_id
        """)
        conn.execute(update_return_query, {"new_status": new_status, "adj_id": adjustment_id})

        # 3. Get the old status before updating F_CON_SALES_BOOKING_DATA
        old_status_query = text("SELECT FAROL_STATUS FROM LogTransp.F_CON_SALES_BOOKING_DATA WHERE FAROL_REFERENCE = :farol_ref")
        old_status = conn.execute(old_status_query, {"farol_ref": farol_ref}).scalar()

        # 4. Update the status in F_CON_SALES_BOOKING_DATA
        update_main_query = text("""
            UPDATE LogTransp.F_CON_SALES_BOOKING_DATA
            SET FAROL_STATUS = :new_status
            WHERE FAROL_REFERENCE = :farol_ref
        """)
        conn.execute(update_main_query, {"new_status": new_status, "farol_ref": farol_ref})

        # 5. Audit the change in F_CON_CHANGE_LOG
        from uuid import uuid4
        audit_id = str(uuid4())
        
        # Get current user from session state or use 'System'
        current_user = st.session_state.get('username', 'System')
        
        audit_query = text("""
            INSERT INTO LogTransp.F_CON_CHANGE_LOG 
            (FAROL_REFERENCE, TABLE_NAME, COLUMN_NAME, OLD_VALUE, NEW_VALUE, 
             CHANGE_TYPE, USER_LOGIN, CHANGE_SOURCE, ADJUSTMENT_ID)
            VALUES (:farol_ref, :table_name, :column_name, :old_value, :new_value,
                    :change_type, :user_login, :change_source, :adjustment_id)
        """)
        
        conn.execute(audit_query, {
            "farol_ref": farol_ref,
            "table_name": "F_CON_SALES_BOOKING_DATA",
            "column_name": "FAROL_STATUS",
            "old_value": old_status or "NULL",
            "new_value": new_status,
            "change_type": "UPDATE",
            "user_login": current_user,
            "change_source": "history",
            "adjustment_id": adjustment_id
        })

        # 6. Commit
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

def update_farol_status_main_table(farol_reference: str, new_status: str, user_insert: str = "System") -> bool:
    """
    Atualiza o Farol Status na tabela F_CON_SALES_BOOKING_DATA.
    Usado quando um PDF é processado ou status muda em F_CON_RETURN_CARRIERS.
    
    Args:
        farol_reference: Referência Farol
        new_status: Novo status a ser aplicado
        user_insert: Usuário que fez a alteração
    
    Returns:
        bool: True se atualizado com sucesso
    """
    conn = get_database_connection()
    try:
        with conn.begin():
            # Buscar status atual para auditoria
            old_status_query = text("""
                SELECT FAROL_STATUS 
                FROM LogTransp.F_CON_SALES_BOOKING_DATA 
                WHERE FAROL_REFERENCE = :farol_ref
            """)
            old_status = conn.execute(old_status_query, {"farol_ref": farol_reference}).scalar()
            
            # Atualizar status
            update_query = text("""
                UPDATE LogTransp.F_CON_SALES_BOOKING_DATA
                SET FAROL_STATUS = :new_status,
                    DATE_UPDATE = SYSDATE
                WHERE FAROL_REFERENCE = :farol_ref
            """)
            conn.execute(update_query, {"new_status": new_status, "farol_ref": farol_reference})
            
            # Registrar em auditoria apenas se houve mudança
            if old_status and old_status != new_status:
                audit_query = text("""
                    INSERT INTO LogTransp.F_CON_CHANGE_LOG 
                    (FAROL_REFERENCE, TABLE_NAME, COLUMN_NAME, OLD_VALUE, NEW_VALUE, 
                     CHANGE_TYPE, USER_LOGIN, CHANGE_SOURCE)
                    VALUES (:farol_ref, 'F_CON_SALES_BOOKING_DATA', 'FAROL_STATUS', 
                           :old_status, :new_status, 'UPDATE', :user, 'PDF_PROCESSOR')
                """)
                conn.execute(audit_query, {
                    "farol_ref": farol_reference,
                    "old_status": old_status,
                    "new_status": new_status,
                    "user": user_insert
                })
            
            return True
    except Exception as e:
        print(f"Erro ao atualizar Farol Status: {e}")
        return False
    finally:
        conn.close()

