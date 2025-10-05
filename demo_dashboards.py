#!/usr/bin/env python3
"""
Demo dos Dashboards de Gestão Marítima - Farol
==============================================

Este arquivo demonstra as funcionalidades dos dashboards implementados:
- Operation Control: Dashboard operacional para gestão de tickets
- Performance Control: Dashboard executivo para análise estratégica

Para executar:
    streamlit run demo_dashboards.py

Funcionalidades Demonstradas:
- KPIs em tempo real
- Visualizações interativas com Altair
- Filtros dinâmicos
- Análise de tendências
- Métricas de performance
"""

import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
import numpy as np

# Configuração da página
st.set_page_config(
    page_title="Demo Dashboards - Farol",
    page_icon="🚢",
    layout="wide"
)

# Paleta de cores Cargill
COLORS = {
    'primary': '#005EB8',
    'success': '#00A651', 
    'warning': '#FF8200',
    'danger': '#E31837',
    'neutral': '#6C757D',
    'light': '#F8F9FA'
}

def create_demo_data():
    """Cria dados de demonstração para os dashboards"""
    np.random.seed(42)
    
    # Dados de demonstração para Operation Control
    n_bookings = 150
    carriers = ['MAERSK', 'MSC', 'CMA CGM', 'COSCO', 'HAPAG-LLOYD', 'ONE', 'EVERGREEN']
    statuses = ['Shipment Requested', 'Booking Requested', 'Booking Approved', 'Booking Confirmed', 'Cancelled']
    business_units = ['Cotton', 'Food', 'Energy', 'Industrial']
    customers = ['Cargill Inc', 'ADM', 'Bunge', 'Louis Dreyfus', 'COFCO']
    
    # Gerar dados aleatórios
    data = []
    base_date = datetime.now() - timedelta(days=30)
    
    for i in range(n_bookings):
        creation_date = base_date + timedelta(days=np.random.randint(0, 30))
        status = np.random.choice(statuses, p=[0.2, 0.3, 0.35, 0.1, 0.05])
        
        # Calcular datas baseadas no status
        booking_date = creation_date + timedelta(days=np.random.randint(1, 5)) if status in ['Booking Requested', 'Booking Approved', 'Booking Confirmed'] else None
        confirmation_date = booking_date + timedelta(days=np.random.randint(1, 3)) if status in ['Booking Approved', 'Booking Confirmed'] else None
        
        # Deadlines
        draft_deadline = creation_date + timedelta(days=np.random.randint(5, 15))
        deadline = draft_deadline + timedelta(days=np.random.randint(1, 3))
        gate_opening = deadline - timedelta(days=np.random.randint(1, 3))
        
        data.append({
            'FAROL_REFERENCE': f'FR_{i+1:04d}',
            'FAROL_STATUS': status,
            'B_VOYAGE_CARRIER': np.random.choice(carriers),
            'B_DATA_DRAFT_DEADLINE': draft_deadline,
            'B_DATA_DEADLINE': deadline,
            'B_DATA_ABERTURA_GATE': gate_opening,
            'USER_LOGIN_BOOKING_CREATED': f'operator_{np.random.randint(1, 6)}',
            'USER_LOGIN_SALES_CREATED': f'sales_{np.random.randint(1, 4)}',
            'S_CUSTOMER': np.random.choice(customers),
            'S_BUSINESS': np.random.choice(business_units),
            'S_QUANTITY_OF_CONTAINERS': np.random.randint(1, 50),
            'S_VOLUME_IN_TONS': np.random.randint(10, 1000),
            'S_CREATION_OF_SHIPMENT': creation_date,
            'B_CREATION_OF_BOOKING': booking_date,
            'B_BOOKING_CONFIRMATION_DATE': confirmation_date,
            'S_PORT_OF_LOADING_POL': np.random.choice(['Santos', 'Paranaguá', 'Rio Grande', 'Itajaí']),
            'S_PORT_OF_DELIVERY_POD': np.random.choice(['Rotterdam', 'Hamburg', 'Antwerp', 'Le Havre', 'Shanghai']),
            'B_DESTINATION_TRADE_REGION': np.random.choice(['Europe', 'Asia', 'North America', 'South America']),
            'B_POD_COUNTRY': np.random.choice(['Netherlands', 'Germany', 'Belgium', 'France', 'China']),
            'B_FREIGHT_RATE_USD': np.random.uniform(800, 2500),
            'B_FREIGHTPPNL': np.random.uniform(600, 2000),
            'B_DATA_ESTIMATIVA_SAIDA_ETD': deadline + timedelta(days=np.random.randint(1, 5)),
            'B_DATA_PARTIDA_ATD': None,  # Será preenchido condicionalmente
            'S_REQUESTED_SHIPMENT_WEEK': creation_date + timedelta(weeks=np.random.randint(1, 8)),
            'S_TYPE_OF_SHIPMENT': np.random.choice(['FCL', 'LCL', 'Bulk'])
        })
    
    # Adicionar algumas datas de partida realistas
    for item in data:
        if item['B_DATA_ESTIMATIVA_SAIDA_ETD']:
            # 80% on-time, 20% atrasado
            if np.random.random() < 0.8:
                item['B_DATA_PARTIDA_ATD'] = item['B_DATA_ESTIMATIVA_SAIDA_ETD'] + timedelta(hours=np.random.randint(-6, 6))
            else:
                item['B_DATA_PARTIDA_ATD'] = item['B_DATA_ESTIMATIVA_SAIDA_ETD'] + timedelta(days=np.random.randint(1, 5))
    
    return pd.DataFrame(data)

def demo_operation_control():
    """Demonstra o dashboard Operation Control"""
    st.title("📊 Operation Control - Demo")
    st.markdown("**Dashboard Operacional para Gestão de Tickets e Prazos**")
    
    # Carregar dados de demonstração
    df = create_demo_data()
    
    # KPIs principais
    st.subheader("📈 KPIs Principais")
    
    col1, col2, col3, col4 = st.columns(4)
    
    total_active = len(df[df['FAROL_STATUS'].isin(['Shipment Requested', 'Booking Requested', 'Booking Approved'])])
    pending = len(df[df['FAROL_STATUS'].isin(['Shipment Requested', 'Booking Requested'])])
    
    # Prazos críticos (< 48h)
    now = datetime.now()
    critical_deadlines = len(df[
        (df['B_DATA_DEADLINE'].notna()) & 
        (df['B_DATA_DEADLINE'] <= now + timedelta(hours=48)) &
        (df['FAROL_STATUS'].isin(['Shipment Requested', 'Booking Requested']))
    ])
    
    # Taxa de resposta hoje
    today = now.date()
    approvals_today = len(df[
        (df['B_BOOKING_CONFIRMATION_DATE'].dt.date == today) &
        (df['FAROL_STATUS'] == 'Booking Approved')
    ])
    response_rate = (approvals_today / max(pending, 1)) * 100
    
    with col1:
        st.metric("Total de Bookings Ativos", total_active)
    with col2:
        st.metric("Bookings Pendentes", pending)
    with col3:
        st.metric("Prazos Críticos (< 48h)", critical_deadlines)
    with col4:
        st.metric("Taxa de Resposta Hoje", f"{response_rate:.1f}%")
    
    # Visualizações
    col1, col2 = st.columns(2)
    
    with col1:
        # Funil de Status
        status_counts = df['FAROL_STATUS'].value_counts()
        chart_data = pd.DataFrame({
            'Status': status_counts.index,
            'Count': status_counts.values
        })
        
        chart = alt.Chart(chart_data).mark_bar().encode(
            x=alt.X('Count:Q', title='Quantidade'),
            y=alt.Y('Status:N', title='Status', sort='-x'),
            color=alt.value(COLORS['primary'])
        ).properties(
            height=300,
            title='Funil de Status de Bookings'
        )
        
        st.altair_chart(chart, use_container_width=True)
    
    with col2:
        # Distribuição por Carrier
        carrier_counts = df['B_VOYAGE_CARRIER'].value_counts().head(5)
        chart_data = pd.DataFrame({
            'Carrier': carrier_counts.index,
            'Bookings': carrier_counts.values
        })
        
        chart = alt.Chart(chart_data).mark_arc(innerRadius=50).encode(
            theta=alt.Theta('Bookings:Q'),
            color=alt.Color('Carrier:N', scale=alt.Scale(scheme='category20'))
        ).properties(
            width=400,
            height=300,
            title='Distribuição por Carrier'
        )
        
        st.altair_chart(chart, use_container_width=True)
    
    # Timeline de Prazos Críticos
    st.subheader("⏰ Prazos Críticos")
    
    critical_df = df[
        (df['B_DATA_DEADLINE'].notna()) & 
        (df['FAROL_STATUS'].isin(['Shipment Requested', 'Booking Requested']))
    ].nlargest(10, 'B_DATA_DEADLINE')
    
    if not critical_df.empty:
        timeline_data = []
        for _, row in critical_df.iterrows():
            hours_to_deadline = (row['B_DATA_DEADLINE'] - now).total_seconds() / 3600
            timeline_data.append({
                'Farol_Reference': row['FAROL_REFERENCE'],
                'Carrier': row['B_VOYAGE_CARRIER'],
                'Hours_Left': hours_to_deadline,
                'Status': 'Critical' if hours_to_deadline < 48 else 'Warning'
            })
        
        timeline_df = pd.DataFrame(timeline_data)
        
        chart = alt.Chart(timeline_df).mark_bar().encode(
            x=alt.X('Hours_Left:Q', title='Horas Restantes'),
            y=alt.Y('Farol_Reference:N', title='Farol Reference', sort='-x'),
            color=alt.condition(
                alt.datum.Hours_Left < 48,
                alt.value(COLORS['danger']),
                alt.value(COLORS['warning'])
            )
        ).properties(
            height=400,
            title='Próximos 10 Bookings com Deadlines Urgentes'
        )
        
        st.altair_chart(chart, use_container_width=True)

def demo_performance_control():
    """Demonstra o dashboard Performance Control"""
    st.title("📈 Performance Control - Demo")
    st.markdown("**Dashboard Executivo para Análise Estratégica**")
    
    # Carregar dados de demonstração
    df = create_demo_data()
    
    # KPIs executivos
    st.subheader("🎯 KPIs Executivos")
    
    col1, col2, col3, col4 = st.columns(4)
    
    current_month = datetime.now().replace(day=1)
    current_month_data = df[df['S_CREATION_OF_SHIPMENT'].dt.to_period('M') == current_month.strftime('%Y-%m')]
    
    total_containers = current_month_data['S_QUANTITY_OF_CONTAINERS'].sum()
    total_volume_tons = current_month_data['S_VOLUME_IN_TONS'].sum()
    
    total_requests = len(df[df['FAROL_STATUS'].isin(['Shipment Requested', 'Booking Requested', 'Booking Approved'])])
    approved_requests = len(df[df['FAROL_STATUS'] == 'Booking Approved'])
    approval_rate = (approved_requests / max(total_requests, 1)) * 100
    
    # Tempo médio de ciclo
    cycle_times = []
    for _, row in df.iterrows():
        if (pd.notna(row['S_CREATION_OF_SHIPMENT']) and 
            pd.notna(row['B_BOOKING_CONFIRMATION_DATE']) and 
            row['FAROL_STATUS'] == 'Booking Approved'):
            cycle_time = (row['B_BOOKING_CONFIRMATION_DATE'] - row['S_CREATION_OF_SHIPMENT']).days
            if cycle_time >= 0:
                cycle_times.append(cycle_time)
    
    avg_cycle_time = np.mean(cycle_times) if cycle_times else 0
    
    with col1:
        st.metric("Containers Embarcados (Mês)", f"{total_containers:,.0f}")
    with col2:
        st.metric("Volume em Toneladas (Mês)", f"{total_volume_tons:,.0f}")
    with col3:
        st.metric("Taxa de Aprovação", f"{approval_rate:.1f}%")
    with col4:
        st.metric("Tempo Médio de Ciclo", f"{avg_cycle_time:.1f} dias")
    
    # Visualizações estratégicas
    col1, col2 = st.columns(2)
    
    with col1:
        # Tendência Mensal
        df['month'] = df['S_CREATION_OF_SHIPMENT'].dt.to_period('M')
        monthly_data = df.groupby('month').agg({
            'FAROL_REFERENCE': 'count',
            'FAROL_STATUS': lambda x: (x == 'Booking Approved').sum()
        }).reset_index()
        
        monthly_data.columns = ['Month', 'Total_Created', 'Approved']
        monthly_data['Month_Str'] = monthly_data['Month'].astype(str)
        
        base = alt.Chart(monthly_data).encode(x=alt.X('Month_Str:N', title='Mês'))
        
        line_chart = base.mark_line(strokeWidth=3).encode(
            y=alt.Y('Total_Created:Q', title='Número de Bookings'),
            color=alt.value(COLORS['primary'])
        )
        
        area_chart = base.mark_area(opacity=0.3).encode(
            y=alt.Y('Approved:Q', title='Aprovados'),
            color=alt.value(COLORS['success'])
        )
        
        chart = (line_chart + area_chart).resolve_scale(y='independent').properties(
            height=400,
            title='Tendência Mensal de Bookings'
        )
        
        st.altair_chart(chart, use_container_width=True)
    
    with col2:
        # Performance por Business Unit
        bu_data = df.groupby('S_BUSINESS').agg({
            'S_QUANTITY_OF_CONTAINERS': 'sum',
            'FAROL_STATUS': lambda x: (x == 'Booking Approved').sum() / len(x) * 100
        }).reset_index()
        
        bu_data.columns = ['Business_Unit', 'Containers', 'Approval_Rate']
        
        chart = alt.Chart(bu_data).mark_bar().encode(
            x=alt.X('Containers:Q', title='Volume de Containers'),
            y=alt.Y('Business_Unit:N', title='Business Unit', sort='-x'),
            color=alt.Color('Approval_Rate:Q', 
                           scale=alt.Scale(domain=[0, 100], range=[COLORS['danger'], COLORS['success']]))
        ).properties(
            height=400,
            title='Performance por Business Unit'
        )
        
        st.altair_chart(chart, use_container_width=True)
    
    # Análise de Freight Rate
    st.subheader("💰 Análise de Freight Rate")
    
    freight_data = df[
        (df['B_FREIGHT_RATE_USD'].notna()) & 
        (df['B_FREIGHTPPNL'].notna()) & 
        (df['S_QUANTITY_OF_CONTAINERS'].notna())
    ].copy()
    
    if not freight_data.empty:
        chart = alt.Chart(freight_data).mark_circle(size=100).encode(
            x=alt.X('B_FREIGHT_RATE_USD:Q', title='Freight Rate (USD)'),
            y=alt.Y('B_FREIGHTPPNL:Q', title='Freight PPNL (USD)'),
            size=alt.Size('S_QUANTITY_OF_CONTAINERS:Q', 
                         scale=alt.Scale(range=[50, 500])),
            color=alt.Color('S_BUSINESS:N', scale=alt.Scale(scheme='category20')),
            tooltip=['FAROL_REFERENCE', 'S_BUSINESS', 'B_FREIGHT_RATE_USD', 'B_FREIGHTPPNL']
        ).properties(
            height=400,
            title='Análise de Freight Rate vs PPNL'
        )
        
        st.altair_chart(chart, use_container_width=True)

def main():
    """Função principal do demo"""
    st.title("🚢 Demo - Dashboards de Gestão Marítima")
    st.markdown("**Demonstração das funcionalidades dos dashboards Farol**")
    
    st.markdown("""
    ### 📋 Sobre os Dashboards
    
    Este demo apresenta duas interfaces especializadas para gestão de embarques marítimos:
    
    **📊 Operation Control**
    - Foco operacional para equipes de tickets
    - Monitoramento de prazos e SLA
    - Distribuição de workload
    - Ações urgentes
    
    **📈 Performance Control**
    - Visão estratégica para gestores
    - Análise de tendências e KPIs
    - Eficiência de carriers
    - Análise de custos e receita
    
    ### 🎯 Funcionalidades Demonstradas
    - KPIs em tempo real
    - Visualizações interativas
    - Filtros dinâmicos
    - Análise de performance
    - Dados de demonstração realistas
    """)
    
    # Tabs para os dashboards
    tab1, tab2 = st.tabs(["📊 Operation Control", "📈 Performance Control"])
    
    with tab1:
        demo_operation_control()
    
    with tab2:
        demo_performance_control()
    
    # Informações técnicas
    st.markdown("---")
    st.subheader("🔧 Informações Técnicas")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **Tecnologias Utilizadas:**
        - Streamlit para interface web
        - Altair para visualizações
        - Pandas para manipulação de dados
        - Oracle Database para persistência
        """)
    
    with col2:
        st.markdown("""
        **Características:**
        - Cache inteligente (10 min)
        - Layout responsivo
        - Paleta Cargill
        - Queries otimizadas
        """)

if __name__ == "__main__":
    main()
