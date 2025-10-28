import os
import sys
from datetime import datetime
import pandas as pd

# Adiciona o diretório atual ao PATH para que as importações funcionem
sys.path.insert(0, os.path.dirname(__file__))

# Mock Streamlit functions to avoid errors when running outside Streamlit environment
class MockStreamlit:
    def success(self, *args, **kwargs): pass
    def error(self, *args, **kwargs): pass
    def warning(self, *args, **kwargs): pass
    def info(self, *args, **kwargs): pass
    def session_state(self, *args, **kwargs): return {}

    # Mock for st.cache_data decorator
    def cache_data(self, ttl=None):
        def decorator(func):
            return func
        return decorator

sys.modules['streamlit'] = MockStreamlit()

from ellox_api import get_default_api_client
# Import the necessary database functions
from database import get_database_connection, validate_and_collect_voyage_monitoring, _parse_iso_datetime
from sqlalchemy import text

def get_voyage_monitoring_from_db(vessel_name: str, voyage_code: str, terminal_name: str) -> dict:
    """
    Queries the F_ELLOX_TERMINAL_MONITORINGS table for the latest voyage monitoring data.
    """
    conn = None
    try:
        conn = get_database_connection()
        query_str = '''
            SELECT
                NAVIO,
                VIAGEM,
                TERMINAL,
                AGENCIA,
                DATA_DEADLINE,
                DATA_DRAFT_DEADLINE,
                DATA_ABERTURA_GATE,
                DATA_ESTIMATIVA_SAIDA,
                DATA_ESTIMATIVA_CHEGADA,
                DATA_CHEGADA,
                DATA_ESTIMATIVA_ATRACACAO,
                DATA_ATRACACAO,
                DATA_PARTIDA,
                DATA_ATUALIZACAO,
                DATA_SOURCE,
                ROW_INSERTED_DATE
            FROM LogTransp.F_ELLOX_TERMINAL_MONITORINGS
            WHERE UPPER(NAVIO) = UPPER(:vessel_name)
              AND UPPER(VIAGEM) = UPPER(:voyage_code)
              AND UPPER(TERMINAL) = UPPER(:terminal_name)
            ORDER BY NVL(DATA_ATUALIZACAO, ROW_INSERTED_DATE) DESC
            FETCH FIRST 1 ROWS ONLY
        '''
        query = text(query_str)
        
        result = conn.execute(query, {
            "vessel_name": vessel_name,
            "voyage_code": voyage_code,
            "terminal_name": terminal_name
        }).mappings().fetchone()

        if result:
            print(f"DEBUG: Raw DB result: {result}")
            print(f"DEBUG: Keys in DB result: {result.keys()}")
            # Access keys using lowercase as identified from debug output
            formatted_data = {
                "Navio": result["navio"],
                "Viagem": result["viagem"],
                "Terminal": result["terminal"],
                "Origem": result["data_source"],
                "Aprovado": result["row_inserted_date"].strftime("%d/%m/%Y %H:%M") if result["row_inserted_date"] else "N/A",
                "ETD": result["data_estimativa_saida"].strftime("%d/%m/%Y %H:%M") if result["data_estimativa_saida"] else "N/A",
                "ETA": result["data_estimativa_chegada"].strftime("%d/%m/%Y %H:%M") if result["data_estimativa_chegada"] else "N/A",
                "Gate": result["data_abertura_gate"].strftime("%d/%m/%Y %H:%M") if result["data_abertura_gate"] else "N/A",
                "Deadline": result["data_deadline"].strftime("%d/%m/%Y %H:%M") if result["data_deadline"] else "N/A",
                "Atualizado": result["data_atualizacao"].strftime("%d/%m/%Y %H:%M") if result["data_atualizacao"] else "N/A",
            }
            # Simplified Status logic for example. Actual status might be derived from multiple fields.
            if result["data_partida"] and result["data_partida"] < datetime.now():
                formatted_data["Status"] = "✅ Partiu"
            elif result["data_estimativa_saida"] and result["data_estimativa_saida"] > datetime.now(): 
                formatted_data["Status"] = "🟡 Em Atraso" 
            else:
                formatted_data["Status"] = "🚚 Em Trânsito" 

            return {"success": True, "data": formatted_data, "message": "Dados de monitoramento encontrados no banco."}
        else:
            return {"success": False, "data": None, "message": "Dados de monitoramento não encontrados no banco para a viagem especificada."}
    except Exception as e:
        return {"success": False, "data": None, "message": f"Erro ao consultar o banco de dados: {e}"}
    finally:
        if conn:
            conn.close()


print("Attempting to get Ellox API client and test connection...")
try:
    # Test basic API connection first
    client = get_default_api_client()
    connection_result = client.test_connection()
    print(f"Basic API Connection Test Result: {connection_result}")

    # New data from user
    vessel_name = "Cap San Maleas"
    voyage_code = "524E"
    terminal_name = "DPW"

    # First, try to get data directly from the DB, as the user's system likely does.
    print("Attempting to retrieve voyage monitoring data directly from the local database...")
    db_monitoring_data = get_voyage_monitoring_from_db(vessel_name, voyage_code, terminal_name)
    
    if db_monitoring_data.get("success") and db_monitoring_data.get("data"):
        print(f"Voyage Monitoring Data (from DB) for {vessel_name} | {voyage_code} | {terminal_name}:\n{db_monitoring_data["data"]}")
    else:
        print(f"Could not retrieve data from DB initially: {db_monitoring_data["message"]}")
        print("\n--- Attempting to use validate_and_collect_voyage_monitoring (which checks DB then API) ---")
        # If not found in DB, or if we want to confirm API interaction, use the validation function
        # Set save_to_db=True to simulate the user's action of saving the data
        monitoring_data_result = validate_and_collect_voyage_monitoring(
            vessel_name=vessel_name,
            voyage_code=voyage_code,
            terminal=terminal_name,
            save_to_db=True 
        )
        print(f"Voyage Monitoring Data (from validate_and_collect_voyage_monitoring) for {vessel_name} | {voyage_code} | {terminal_name}: {monitoring_data_result}")

        # After saving, try to retrieve from DB again to confirm persistence
        if monitoring_data_result.get("success"):
            print("\n--- Attempting to retrieve data from DB after validate_and_collect_voyage_monitoring ---")
            db_monitoring_data_after_save = get_voyage_monitoring_from_db(vessel_name, voyage_code, terminal_name)
            if db_monitoring_data_after_save.get("success") and db_monitoring_data_after_save.get("data"):
                print(f"Voyage Monitoring Data (from DB after save) for {vessel_name} | {voyage_code} | {terminal_name}:\n{db_monitoring_data_after_save["data"]}")
            else:
                print(f"Could not retrieve data from DB after save: {db_monitoring_data_after_save["message"]}")

except Exception as e:
    print(f"An error occurred during API client initialization or connection test: {e}")