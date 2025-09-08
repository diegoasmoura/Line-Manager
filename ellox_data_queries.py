"""
Consultas e Relatórios dos Dados Ellox
Este módulo fornece funções para consultar os dados extraídos da API Ellox
"""

import pandas as pd
from database import get_database_connection
from sqlalchemy import text
import streamlit as st

class ElloxDataQueries:
    """Classe para consultas dos dados Ellox armazenados"""
    
    def __init__(self):
        """Inicializa a classe de consultas"""
        pass
    
    def get_all_terminals(self):
        """Retorna todos os terminais disponíveis"""
        conn = get_database_connection()
        try:
            query = text("""
                SELECT ID, NOME, CNPJ, CIDADE, 
                       TO_CHAR(DATA_CRIACAO, 'DD/MM/YYYY HH24:MI') as DATA_CRIACAO
                FROM F_ELLOX_TERMINALS 
                WHERE ATIVO = 'Y'
                ORDER BY NOME
            """)
            
            df = pd.read_sql(query, conn)
            return df
            
        finally:
            conn.close()
    
    def get_ships_by_terminal(self, terminal_cnpj=None, carrier=None):
        """Retorna navios filtrados por terminal e/ou carrier"""
        conn = get_database_connection()
        try:
            where_conditions = ["s.ATIVO = 'Y'"]
            params = {}
            
            if terminal_cnpj:
                where_conditions.append("s.TERMINAL_CNPJ = :terminal_cnpj")
                params['terminal_cnpj'] = terminal_cnpj
            
            if carrier:
                where_conditions.append("s.CARRIER = :carrier")
                params['carrier'] = carrier
            
            where_clause = " AND ".join(where_conditions)
            
            query = text(f"""
                SELECT s.ID, s.NOME as NAVIO, s.CARRIER, 
                       t.NOME as TERMINAL, s.TERMINAL_CNPJ,
                       TO_CHAR(s.DATA_CRIACAO, 'DD/MM/YYYY') as DATA_CRIACAO
                FROM F_ELLOX_SHIPS s
                JOIN F_ELLOX_TERMINALS t ON s.TERMINAL_CNPJ = t.CNPJ
                WHERE {where_clause}
                ORDER BY s.NOME
            """)
            
            df = pd.read_sql(query, conn, params=params)
            return df
            
        finally:
            conn.close()
    
    def get_voyages_by_ship(self, ship_name=None, carrier=None):
        """Retorna voyages filtrados por navio e/ou carrier"""
        conn = get_database_connection()
        try:
            where_conditions = ["v.ATIVO = 'Y'"]
            params = {}
            
            if ship_name:
                where_conditions.append("UPPER(v.SHIP_NAME) LIKE UPPER(:ship_name)")
                params['ship_name'] = f"%{ship_name}%"
            
            if carrier:
                where_conditions.append("v.CARRIER = :carrier")
                params['carrier'] = carrier
            
            where_clause = " AND ".join(where_conditions)
            
            query = text(f"""
                SELECT v.ID, v.SHIP_NAME as NAVIO, v.VOYAGE_CODE, v.CARRIER,
                       t.NOME as TERMINAL, v.STATUS,
                       TO_CHAR(v.ETD, 'DD/MM/YYYY') as ETD,
                       TO_CHAR(v.ETA, 'DD/MM/YYYY') as ETA,
                       v.POL, v.POD,
                       TO_CHAR(v.DATA_CRIACAO, 'DD/MM/YYYY') as DATA_CRIACAO
                FROM F_ELLOX_VOYAGES v
                JOIN F_ELLOX_TERMINALS t ON v.TERMINAL_CNPJ = t.CNPJ
                WHERE {where_clause}
                ORDER BY v.SHIP_NAME, v.VOYAGE_CODE
            """)
            
            df = pd.read_sql(query, conn, params=params)
            return df
            
        finally:
            conn.close()
    
    def get_carriers_summary(self):
        """Retorna resumo dos carriers com contadores"""
        conn = get_database_connection()
        try:
            query = text("""
                SELECT c.NOME as CARRIER, c.CODIGO, c.NOME_COMPLETO,
                       COUNT(DISTINCT s.ID) as TOTAL_NAVIOS,
                       COUNT(DISTINCT v.ID) as TOTAL_VOYAGES,
                       COUNT(DISTINCT s.TERMINAL_CNPJ) as TERMINAIS_ATIVOS
                FROM F_ELLOX_CARRIERS c
                LEFT JOIN F_ELLOX_SHIPS s ON c.NOME = s.CARRIER AND s.ATIVO = 'Y'
                LEFT JOIN F_ELLOX_VOYAGES v ON c.NOME = v.CARRIER AND v.ATIVO = 'Y'
                WHERE c.ATIVO = 'Y'
                GROUP BY c.NOME, c.CODIGO, c.NOME_COMPLETO
                ORDER BY TOTAL_NAVIOS DESC
            """)
            
            df = pd.read_sql(query, conn)
            return df
            
        finally:
            conn.close()
    
    def get_terminals_summary(self):
        """Retorna resumo dos terminais com contadores"""
        conn = get_database_connection()
        try:
            query = text("""
                SELECT t.NOME as TERMINAL, t.CNPJ, t.CIDADE,
                       COUNT(DISTINCT s.ID) as TOTAL_NAVIOS,
                       COUNT(DISTINCT v.ID) as TOTAL_VOYAGES,
                       COUNT(DISTINCT s.CARRIER) as CARRIERS_ATIVOS
                FROM F_ELLOX_TERMINALS t
                LEFT JOIN F_ELLOX_SHIPS s ON t.CNPJ = s.TERMINAL_CNPJ AND s.ATIVO = 'Y'
                LEFT JOIN F_ELLOX_VOYAGES v ON t.CNPJ = v.TERMINAL_CNPJ AND v.ATIVO = 'Y'
                WHERE t.ATIVO = 'Y'
                GROUP BY t.NOME, t.CNPJ, t.CIDADE
                ORDER BY TOTAL_NAVIOS DESC
            """)
            
            df = pd.read_sql(query, conn)
            return df
            
        finally:
            conn.close()
    
    def search_ships(self, search_term):
        """Busca navios por nome (busca parcial)"""
        conn = get_database_connection()
        try:
            query = text("""
                SELECT s.NOME as NAVIO, s.CARRIER, t.NOME as TERMINAL,
                       s.TERMINAL_CNPJ, s.IMO, s.MMSI, s.FLAG
                FROM F_ELLOX_SHIPS s
                JOIN F_ELLOX_TERMINALS t ON s.TERMINAL_CNPJ = t.CNPJ
                WHERE s.ATIVO = 'Y' 
                AND UPPER(s.NOME) LIKE UPPER(:search_term)
                ORDER BY s.NOME
            """)
            
            df = pd.read_sql(query, conn, params={'search_term': f"%{search_term}%"})
            return df
            
        finally:
            conn.close()
    
    def get_database_stats(self):
        """Retorna estatísticas gerais do banco de dados"""
        conn = get_database_connection()
        try:
            stats = {}
            
            # Contadores gerais
            result = conn.execute(text("SELECT COUNT(*) FROM F_ELLOX_TERMINALS WHERE ATIVO = 'Y'"))
            stats['terminais'] = result.scalar()
            
            result = conn.execute(text("SELECT COUNT(*) FROM F_ELLOX_SHIPS WHERE ATIVO = 'Y'"))
            stats['navios'] = result.scalar()
            
            result = conn.execute(text("SELECT COUNT(*) FROM F_ELLOX_VOYAGES WHERE ATIVO = 'Y'"))
            stats['voyages'] = result.scalar()
            
            result = conn.execute(text("SELECT COUNT(*) FROM F_ELLOX_CARRIERS WHERE ATIVO = 'Y'"))
            stats['carriers'] = result.scalar()
            
            # Data da última atualização
            result = conn.execute(text("""
                SELECT MAX(DATA_ATUALIZACAO) 
                FROM (
                    SELECT MAX(DATA_ATUALIZACAO) as DATA_ATUALIZACAO FROM F_ELLOX_TERMINALS
                    UNION ALL
                    SELECT MAX(DATA_ATUALIZACAO) FROM F_ELLOX_SHIPS
                    UNION ALL
                    SELECT MAX(DATA_ATUALIZACAO) FROM F_ELLOX_VOYAGES
                    UNION ALL
                    SELECT MAX(DATA_ATUALIZACAO) FROM F_ELLOX_CARRIERS
                )
            """))
            
            last_update = result.scalar()
            stats['ultima_atualizacao'] = last_update.strftime('%d/%m/%Y %H:%M') if last_update else 'N/A'
            
            return stats
            
        finally:
            conn.close()

# Funções para uso no Streamlit
def display_ellox_data_interface():
    """Interface Streamlit para visualizar dados Ellox"""
    
    st.title("📊 Dados da API Ellox")
    st.markdown("**Consulta aos dados extraídos da API Ellox da Comexia**")
    
    queries = ElloxDataQueries()
    
    # Estatísticas gerais
    st.markdown("### 📈 Estatísticas Gerais")
    stats = queries.get_database_stats()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🏢 Terminais", stats['terminais'])
    with col2:
        st.metric("🚢 Navios", stats['navios'])
    with col3:
        st.metric("⛵ Voyages", stats['voyages'])
    with col4:
        st.metric("🏪 Carriers", stats['carriers'])
    
    st.info(f"📅 Última atualização: {stats['ultima_atualizacao']}")
    
    # Tabs para diferentes consultas
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🔍 Busca", "🏢 Terminais", "🚢 Navios", "⛵ Voyages", "📊 Relatórios"
    ])
    
    with tab1:
        st.markdown("### 🔍 Busca de Navios")
        search_term = st.text_input("Digite o nome do navio (busca parcial):")
        
        if search_term:
            with st.spinner("Buscando..."):
                results = queries.search_ships(search_term)
                
                if not results.empty:
                    st.success(f"✅ {len(results)} navios encontrados")
                    st.dataframe(results, use_container_width=True)
                else:
                    st.warning("⚠️ Nenhum navio encontrado")
    
    with tab2:
        st.markdown("### 🏢 Terminais Disponíveis")
        
        # Resumo dos terminais
        terminals_summary = queries.get_terminals_summary()
        st.dataframe(terminals_summary, use_container_width=True)
        
        # Lista completa de terminais
        with st.expander("📋 Lista Completa de Terminais"):
            terminals = queries.get_all_terminals()
            st.dataframe(terminals, use_container_width=True)
    
    with tab3:
        st.markdown("### 🚢 Navios por Terminal/Carrier")
        
        col1, col2 = st.columns(2)
        
        with col1:
            terminals = queries.get_all_terminals()
            terminal_options = ["Todos"] + terminals['NOME'].tolist()
            selected_terminal = st.selectbox("Selecionar Terminal:", terminal_options)
        
        with col2:
            carrier_options = ["Todos", "HAPAG-LLOYD", "MAERSK", "MSC", "CMA CGM", "COSCO", "EVERGREEN", "OOCL", "PIL"]
            selected_carrier = st.selectbox("Selecionar Carrier:", carrier_options)
        
        # Filtrar dados
        terminal_cnpj = None
        if selected_terminal != "Todos":
            terminal_cnpj = terminals[terminals['NOME'] == selected_terminal]['CNPJ'].iloc[0]
        
        carrier = None if selected_carrier == "Todos" else selected_carrier
        
        ships = queries.get_ships_by_terminal(terminal_cnpj, carrier)
        
        if not ships.empty:
            st.success(f"✅ {len(ships)} navios encontrados")
            st.dataframe(ships, use_container_width=True)
        else:
            st.warning("⚠️ Nenhum navio encontrado com os filtros selecionados")
    
    with tab4:
        st.markdown("### ⛵ Voyages por Navio/Carrier")
        
        col1, col2 = st.columns(2)
        
        with col1:
            ship_name = st.text_input("Nome do Navio (opcional):")
        
        with col2:
            carrier_options = ["Todos", "HAPAG-LLOYD", "MAERSK", "MSC", "CMA CGM", "COSCO", "EVERGREEN", "OOCL", "PIL"]
            selected_carrier_v = st.selectbox("Carrier:", carrier_options, key="voyage_carrier")
        
        carrier_v = None if selected_carrier_v == "Todos" else selected_carrier_v
        ship_name_v = ship_name if ship_name else None
        
        if st.button("🔍 Buscar Voyages"):
            with st.spinner("Buscando voyages..."):
                voyages = queries.get_voyages_by_ship(ship_name_v, carrier_v)
                
                if not voyages.empty:
                    st.success(f"✅ {len(voyages)} voyages encontrados")
                    st.dataframe(voyages, use_container_width=True)
                else:
                    st.warning("⚠️ Nenhum voyage encontrado")
    
    with tab5:
        st.markdown("### 📊 Relatórios e Resumos")
        
        # Resumo por Carrier
        st.markdown("#### 🏪 Resumo por Carrier")
        carriers_summary = queries.get_carriers_summary()
        st.dataframe(carriers_summary, use_container_width=True)
        
        # Gráfico de navios por carrier
        if not carriers_summary.empty:
            st.markdown("#### 📈 Navios por Carrier")
            st.bar_chart(carriers_summary.set_index('CARRIER')['TOTAL_NAVIOS'])

def main():
    """Função principal para testar as consultas"""
    queries = ElloxDataQueries()
    
    print("🔄 Testando consultas dos dados Ellox...")
    
    # Testar estatísticas
    stats = queries.get_database_stats()
    print(f"📊 Estatísticas: {stats}")
    
    # Testar busca de navios
    ships = queries.search_ships("MAERSK")
    print(f"🚢 Navios MAERSK encontrados: {len(ships)}")
    
    print("✅ Testes concluídos!")

if __name__ == "__main__":
    main()
