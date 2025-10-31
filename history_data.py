import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import datetime
import uuid

# Nota: imports de database são feitos dentro das funções (lazy imports) para evitar ciclo de import


def get_next_linked_reference_number(farol_reference=None):
    """
    Obtém o próximo número sequencial para Linked_Reference.
    Se farol_reference for fornecido, gera formato hierárquico: FR_XX.XX_XXXX-R01
    Senão, mantém comportamento atual (global).
    """
    try:
        from database import get_database_connection
        conn = get_database_connection()
        
        if farol_reference:
            query = text("""
                SELECT NVL(MAX(
                    CAST(SUBSTR(Linked_Reference, LENGTH(:farol_ref) + 3) AS NUMBER)
                ), 0) + 1 as next_number
                FROM LogTransp.F_CON_RETURN_CARRIERS
                WHERE Linked_Reference LIKE :pattern
                  AND Linked_Reference NOT IN ('New Adjustment')
            """)
            pattern = f"{farol_reference}-R%"
            result = conn.execute(query, {
                "farol_ref": farol_reference, 
                "pattern": pattern
            }).scalar()
            conn.close()
            next_num = result if result else 1
            return f"{farol_reference}-R{next_num:02d}"
        else:
            query = text("""
                SELECT NVL(MAX(Linked_Reference), 0) + 1 as next_number
                FROM LogTransp.F_CON_RETURN_CARRIERS
                WHERE Linked_Reference IS NOT NULL
                      AND Linked_Reference NOT LIKE '%-R%'
                      AND Linked_Reference != 'New Adjustment'
            """)
            result = conn.execute(query).scalar()
            conn.close()
            return result if result else 1
            
    except Exception as e:
        st.error(f"❌ Erro ao obter próximo número sequencial: {str(e)}")
        return f"{farol_reference}-R01" if farol_reference else 1

def get_referenced_line_data(linked_ref):
    """
    Busca dados da linha referenciada pelo ID do Linked Reference.
    Retorna dicionário com dados da linha ou None se não encontrar.
    """
    if not linked_ref or str(linked_ref).strip() == "" or str(linked_ref).upper() == "NULL":
        return None
    
    linked_ref_str = str(linked_ref)
    
    if linked_ref_str == "New Adjustment":
        return None
    
    if linked_ref_str.isdigit():
        try:
            from database import get_database_connection
            conn = get_database_connection()
            query = text("""
                SELECT ID, ROW_INSERTED_DATE, FAROL_REFERENCE, FAROL_STATUS
                FROM LogTransp.F_CON_RETURN_CARRIERS
                WHERE ID = :line_id
            """)
            result = conn.execute(query, {"line_id": int(linked_ref_str)}).fetchone()
            conn.close()
            
            if result:
                return {
                    'id': result[0],
                    'inserted_date': result[1],
                    'farol_reference': result[2],
                    'status': result[3]
                }
        except Exception as e:
            print(f"Erro ao buscar linha referenciada: {e}")
    
    return None

def update_missing_linked_references():
    """
    Atualiza registros antigos que não têm LINKED_REFERENCE definido.
    """
    try:
        from database import get_database_connection
        conn = get_database_connection()
        
        query = text("""
            SELECT ID, FAROL_REFERENCE 
            FROM LogTransp.F_CON_RETURN_CARRIERS 
            WHERE LINKED_REFERENCE IS NULL 
               OR LINKED_REFERENCE = ''
            ORDER BY FAROL_REFERENCE, ROW_INSERTED_DATE
        """)
        
        records = conn.execute(query).mappings().fetchall()
        
        if not records:
            return 0
        
        updated_count = 0
        for record in records:
            farol_ref = record['FAROL_REFERENCE']
            record_id = record['ID']
            
            new_linked_ref = get_next_linked_reference_number(farol_ref)
            
            update_query = text("""
                UPDATE LogTransp.F_CON_RETURN_CARRIERS 
                SET LINKED_REFERENCE = :linked_ref 
                WHERE ID = :record_id
            """)
            
            conn.execute(update_query, {
                "linked_ref": new_linked_ref,
                "record_id": record_id
            })
            updated_count += 1
        
        conn.commit()
        conn.close()
        return updated_count
        
    except Exception as e:
        st.error(f"❌ Erro ao atualizar Linked References: {str(e)}")
        if 'conn' in locals() and conn.is_connected():
            conn.rollback()
            conn.close()
        return 0

def get_voyage_monitoring_for_reference(farol_reference):
    """Busca dados de monitoramento de viagens relacionados a uma referência Farol"""
    try:
        from database import get_database_connection
        conn = get_database_connection()
        
        vessels_query = text("""
            SELECT DISTINCT B_VESSEL_NAME
            FROM LogTransp.F_CON_RETURN_CARRIERS
            WHERE FAROL_REFERENCE = :ref
              AND B_VESSEL_NAME IS NOT NULL
              AND LENGTH(TRIM(B_VESSEL_NAME)) > 0
        """)
        vessels_result = conn.execute(vessels_query, {"ref": farol_reference}).fetchall()
        
        if not vessels_result:
            conn.close()
            return pd.DataFrame()
        
        vessel_names = [row[0] for row in vessels_result if row[0]]
        
        if not vessel_names:
            conn.close()
            return pd.DataFrame()
        
        placeholders = ", ".join([f":vessel_{i}" for i in range(len(vessel_names))])
        monitoring_query = text(f"""
            WITH ranked_monitoring AS (
                SELECT
                    m.*,
                    r.ROW_INSERTED_DATE as APROVACAO_DATE,
                    ROW_NUMBER() OVER(PARTITION BY m.ID ORDER BY r.ROW_INSERTED_DATE DESC) as rn
                FROM
                    LogTransp.F_ELLOX_TERMINAL_MONITORINGS m
                INNER JOIN
                    LogTransp.F_CON_RETURN_CARRIERS r ON UPPER(m.NAVIO) = UPPER(r.B_VESSEL_NAME)
                                                    AND UPPER(m.VIAGEM) = UPPER(r.B_VOYAGE_CODE)
                                                    AND UPPER(m.TERMINAL) = UPPER(r.B_TERMINAL)
                WHERE
                    r.FAROL_REFERENCE = :farol_ref
                    AND r.FAROL_STATUS IN ('Booking Approved', 'Received from Carrier')
                    AND UPPER(m.NAVIO) IN ({placeholders})
            )
            SELECT *
            FROM ranked_monitoring
            WHERE rn = 1
            ORDER BY NVL(DATA_ATUALIZACAO, APROVACAO_DATE) DESC
        """)
        
        params = {f"vessel_{i}": vessel_name.upper() for i, vessel_name in enumerate(vessel_names)}
        params["farol_ref"] = farol_reference
        
        result = conn.execute(monitoring_query, params).mappings().fetchall()
        conn.close()
        
        return pd.DataFrame([dict(r) for r in result]) if result else pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erro ao buscar dados de monitoramento: {str(e)}")
        if 'conn' in locals() and conn.is_connected():
            conn.close()
        return pd.DataFrame()

def get_available_references_for_relation(farol_reference=None):
    """Busca referências na aba 'Other Status' para relacionamento."""
    # DEBUG 0: Primeiro debug - antes de qualquer coisa
    import streamlit as st
    st.info(f"🔍 DEBUG 0 - Função chamada com farol_reference = '{farol_reference}'")
    
    try:
        # DEBUG 1: Parâmetros recebidos
        st.info(f"🔍 DEBUG 1 - Parâmetro recebido: farol_reference = '{farol_reference}' (tipo: {type(farol_reference)})")
        
        from database import get_database_connection
        conn = get_database_connection()
        # DEBUG 2: Conexão estabelecida
        st.info(f"🔍 DEBUG 2 - Conexão estabelecida: {conn is not None}")
        
        if farol_reference:
            # Query para buscar referências disponíveis, excluindo as que já foram vinculadas
            # Exclui registros cuja data de inserção (formatada como DD-MM-YYYY) já aparece em algum 
            # LINKED_REFERENCE de registros "Received from Carrier" ou "Booking Approved" da mesma referência
            query = text("""
                SELECT r.ID, r.FAROL_REFERENCE, r.FAROL_STATUS, r.P_STATUS, r.ROW_INSERTED_DATE, r.Linked_Reference
                FROM LogTransp.F_CON_RETURN_CARRIERS r
                WHERE r.FAROL_STATUS != 'Received from Carrier'
                  AND UPPER(r.FAROL_REFERENCE) = UPPER(:farol_reference)
                  AND NOT EXISTS (
                      SELECT 1 
                      FROM LogTransp.F_CON_RETURN_CARRIERS linked
                      WHERE (linked.FAROL_STATUS = 'Received from Carrier' OR linked.FAROL_STATUS = 'Booking Approved')
                        AND UPPER(linked.FAROL_REFERENCE) = UPPER(:farol_reference)
                        AND linked.LINKED_REFERENCE IS NOT NULL
                        AND linked.LINKED_REFERENCE != 'New Adjustment'
                        AND linked.LINKED_REFERENCE LIKE '%' || TO_CHAR(r.ROW_INSERTED_DATE, 'DD-MM-YYYY') || '%'
                  )
                ORDER BY r.ROW_INSERTED_DATE ASC
            """)
            params = {"farol_reference": farol_reference}
            st.info(f"🔍 DEBUG 5 - Executando query simplificada com parâmetro: '{farol_reference}'")
            result = conn.execute(query, params).mappings().fetchall()
            
            # DEBUG 6: Quantidade de linhas retornadas
            st.info(f"🔍 DEBUG 6 - Query simplificada retornou {len(result) if result else 0} registro(s)")
            
            # DEBUG 7: Mostrar primeiros registros retornados
            if result:
                st.info(f"🔍 DEBUG 7 - Primeiros registros retornados:")
                for i, row in enumerate(result[:3]):  # Mostrar até 3 primeiros
                    row_dict = dict(row)
                    st.info(f"  Registro {i+1}: {row_dict}")
            else:
                st.warning("🔍 DEBUG 7 - Query simplificada não retornou nenhum registro!")
        else:
            # Comportamento legado: somente originais (não-split) de todas as referências
            query = text("""
                SELECT ID, FAROL_REFERENCE, FAROL_STATUS, P_STATUS, ROW_INSERTED_DATE, Linked_Reference
                FROM LogTransp.F_CON_RETURN_CARRIERS
                WHERE FAROL_STATUS != 'Received from Carrier'
                  AND NVL(S_SPLITTED_BOOKING_REFERENCE, '##NULL##') = '##NULL##' -- apenas originais
                  AND NOT REGEXP_LIKE(FAROL_REFERENCE, '\\.\\d+$')             -- exclui refs com sufixo .n
                ORDER BY ROW_INSERTED_DATE ASC
            """)
            result = conn.execute(query).mappings().fetchall()
        conn.close()
        # DEBUG 8: Processar resultado antes de retornar
        if result:
            # DEBUG 8.1: Verificar chaves do primeiro registro antes da conversão
            if result:
                first_row = dict(result[0])
                st.info(f"🔍 DEBUG 8.1 - Chaves do primeiro registro ANTES da conversão: {list(first_row.keys())}")
            
            processed = [{k.upper(): v for k, v in dict(row).items()} for row in result]
            st.info(f"🔍 DEBUG 8 - Resultado processado: {len(processed)} registro(s) convertido(s)")
            if processed:
                st.info(f"🔍 DEBUG 8.2 - Primeiro registro processado: {processed[0]}")
                st.info(f"🔍 DEBUG 8.2 - Chaves após conversão: {list(processed[0].keys())}")
            return processed
        else:
            st.warning("🔍 DEBUG 8 - Nenhum resultado para processar, retornando lista vazia")
            return []
    except Exception as e:
        import traceback
        # DEBUG 17: Verificar se há erro silencioso sendo capturado
        st.error(f"❌ DEBUG 17 - Erro ao buscar referências disponíveis: {str(e)}")
        st.error(f"❌ DEBUG 17 - Tipo do erro: {type(e).__name__}")
        st.error(f"❌ DEBUG 17 - Traceback completo:\n{traceback.format_exc()}")
        if 'conn' in locals():
            try:
                if hasattr(conn, 'is_connected') and conn.is_connected():
                    conn.close()
            except:
                pass
        return []

def save_attachment_to_db(farol_reference, uploaded_file, user_id="system"):
    """Salva um anexo na tabela F_CON_ANEXOS."""
    try:
        from database import get_database_connection
        conn = get_database_connection()
        file_content = uploaded_file.read()
        file_name = uploaded_file.name
        file_name_without_ext = file_name.rsplit('.', 1)[0] if '.' in file_name else file_name
        file_extension = file_name.rsplit('.', 1)[1].upper() if '.' in file_name else ''
        
        from history_helpers import get_file_type
        file_type = get_file_type(uploaded_file)
        
        insert_query = text("""
            INSERT INTO LogTransp.F_CON_ANEXOS (
                id, farol_reference, adjustment_id, process_stage, type_,
                file_name, file_extension, upload_timestamp, attachment, user_insert
            ) VALUES (
                :id, :farol_reference, :adjustment_id, :process_stage, :type_,
                :file_name, :file_extension, :upload_timestamp, :attachment, :user_insert
            )
        """)
        
        conn.execute(insert_query, {
            "id": None,
            "farol_reference": farol_reference,
            "adjustment_id": str(uuid.uuid4()),
            "process_stage": "Attachment Management",
            "type_": file_type,
            "file_name": file_name_without_ext,
            "file_extension": file_extension,
            "upload_timestamp": datetime.now(),
            "attachment": file_content,
            "user_insert": user_id
        })
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        st.error(f"Erro ao salvar anexo: {str(e)}")
        if 'conn' in locals() and conn.is_connected():
            conn.rollback()
            conn.close()
        return False

def get_attachments_for_farol(farol_reference):
    """Busca todos os anexos para uma referência específica do Farol."""
    try:
        from database import get_database_connection
        conn = get_database_connection()
        query = text("""
            SELECT 
                id, farol_reference, adjustment_id, process_stage, type_ as mime_type,
                file_name, file_extension, upload_timestamp as upload_date, user_insert as uploaded_by
            FROM LogTransp.F_CON_ANEXOS 
            WHERE farol_reference = :farol_reference
              AND (process_stage IS NULL OR process_stage <> 'Attachment Deleted')
            ORDER BY upload_timestamp DESC
        """)
        
        result = conn.execute(query, {"farol_reference": farol_reference}).mappings().fetchall()
        conn.close()
        
        if result:
            df = pd.DataFrame([dict(row) for row in result])
            df['description'] = "Anexo para " + farol_reference
            df['full_file_name'] = df.apply(lambda row: f"{row['file_name']}.{row['file_extension']}" if row['file_extension'] else row['file_name'], axis=1)
            return df
        else:
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"Erro ao buscar anexos: {str(e)}")
        if 'conn' in locals() and conn.is_connected():
            conn.close()
        return pd.DataFrame()

def delete_attachment(attachment_id, deleted_by="system"):
    """Marca um anexo como excluído (soft delete)."""
    try:
        from database import get_database_connection
        conn = get_database_connection()
        query = text("""
            UPDATE LogTransp.F_CON_ANEXOS
               SET process_stage = 'Attachment Deleted',
                   user_update = :user_update,
                   date_update = SYSDATE
             WHERE id = :attachment_id
        """)
        result = conn.execute(query, {"attachment_id": attachment_id, "user_update": deleted_by})
        conn.commit()
        conn.close()
        return result.rowcount > 0
    except Exception as e:
        st.error(f"Erro ao excluir anexo: {str(e)}")
        if 'conn' in locals() and conn.is_connected():
            conn.rollback()
            conn.close()
        return False

def get_attachment_content(attachment_id):
    """Busca o conteúdo de um anexo específico."""
    try:
        from database import get_database_connection
        conn = get_database_connection()
        query = text("""
            SELECT attachment, file_name, file_extension, type_ as mime_type
            FROM LogTransp.F_CON_ANEXOS 
            WHERE id = :attachment_id
        """)
        result = conn.execute(query, {"attachment_id": attachment_id}).mappings().fetchone()
        conn.close()
        
        if result:
            full_file_name = f"{result['file_name']}.{result['file_extension']}" if result['file_extension'] else result['file_name']
            return result['attachment'], full_file_name, result['mime_type']
        else:
            return None, None, None
            
    except Exception as e:
        st.error(f"Erro ao buscar conteúdo do anexo: {str(e)}")
        if 'conn' in locals() and conn.is_connected():
            conn.close()
        return None, None, None

def get_main_table_data(farol_ref):
    """Busca dados específicos da tabela principal F_CON_SALES_BOOKING_DATA"""
    try:
        from database import get_database_connection
        conn = get_database_connection()
        query = text("""
            SELECT 
                S_QUANTITY_OF_CONTAINERS,
                B_VOYAGE_CARRIER,
                S_REQUIRED_ARRIVAL_DATE_EXPECTED,
                ROW_INSERTED_DATE
            FROM LogTransp.F_CON_SALES_BOOKING_DATA
            WHERE FAROL_REFERENCE = :farol_reference
        """)
        result = conn.execute(query, {"farol_reference": farol_ref}).mappings().fetchone()
        conn.close()
        return result
    except Exception as e:
        if 'conn' in locals() and conn.is_connected():
            conn.close()
        st.error(f"❌ Erro na consulta: {str(e)}")
        return None
