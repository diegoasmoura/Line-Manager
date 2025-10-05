import streamlit as st
import pandas as pd
import altair as alt
from database import get_database_connection
from sqlalchemy import text
from datetime import datetime, timedelta
import numpy as np

# Configuração de página é feita no app.py principal

# Paleta de cores Cargill
COLORS = {
    'primary': '#005EB8',
    'success': '#00A651', 
    'warning': '#FF8200',
    'danger': '#E31837',
    'neutral': '#6C757D',
    'light': '#F8F9FA'
}

@st.cache_data(ttl=600)  # Cache de 10 minutos
def load_performance_data(days_back=180, business_unit=None, trade_region=None, country=None):
    """Carrega dados otimizados para o dashboard de performance"""
    conn = get_database_connection()
    try:
        # Query otimizada para Performance Control
        query = """
        SELECT 
            farol_reference,
            farol_status,
            s_business,
            s_quantity_of_containers,
            s_volume_in_tons,
            s_creation_of_shipment,
            b_creation_of_booking,
            b_booking_confirmation_date,
            b_voyage_carrier,
            b_freight_rate_usd,
            b_freightppnl,
            s_port_of_loading_pol,
            s_port_of_delivery_pod,
            b_destination_trade_region,
            b_pod_country,
            b_data_estimativa_saida_etd,
            b_data_partida_atd,
            s_requested_shipment_week,
            s_customer,
            s_type_of_shipment
        FROM LogTransp.F_CON_SALES_BOOKING_DATA
        WHERE s_creation_of_shipment >= SYSTIMESTAMP - :days_back
        """
        
        params = {'days_back': days_back}
        
        # Aplicar filtros
        if business_unit and business_unit != 'Todas':
            query += " AND s_business = :business_unit"
            params['business_unit'] = business_unit
            
        if trade_region and trade_region != 'Todas':
            query += " AND b_destination_trade_region = :trade_region"
            params['trade_region'] = trade_region
            
        if country and country != 'Todos':
            query += " AND b_pod_country = :country"
            params['country'] = country
            
        query += " ORDER BY s_creation_of_shipment DESC"
        
        df = pd.read_sql(query, conn, params=params)
        
        # Processar datas
        date_columns = ['s_creation_of_shipment', 'b_creation_of_booking', 'b_booking_confirmation_date',
                       'b_data_estimativa_saida_etd', 'b_data_partida_atd', 's_requested_shipment_week']
        
        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        return df
        
    except Exception as e:
        st.error(f"Erro ao carregar dados: {str(e)}")
        return pd.DataFrame()
    finally:
        conn.close()

def calculate_executive_kpis(df):
    """Calcula KPIs executivos para o dashboard"""
    current_month = datetime.now().replace(day=1)
    last_month = (current_month - timedelta(days=1)).replace(day=1)
    
    # Filtrar dados do mês atual
    current_month_data = df[df['s_creation_of_shipment'].dt.to_period('M') == current_month.strftime('%Y-%m')]
    
    # Total de Containers Embarcados (mês atual)
    total_containers = current_month_data['s_quantity_of_containers'].sum()
    
    # Volume em Toneladas (mês atual)
    total_volume_tons = current_month_data['s_volume_in_tons'].sum()
    
    # Taxa de Aprovação Geral
    total_requests = len(df[df['farol_status'].isin(['Shipment Requested', 'Booking Requested', 'Booking Approved'])])
    approved_requests = len(df[df['farol_status'] == 'Booking Approved'])
    approval_rate = (approved_requests / max(total_requests, 1)) * 100
    
    # Tempo Médio de Ciclo (Shipment Request → Booking Approved)
    cycle_times = []
    for _, row in df.iterrows():
        if (pd.notna(row['s_creation_of_shipment']) and 
            pd.notna(row['b_booking_confirmation_date']) and 
            row['farol_status'] == 'Booking Approved'):
            cycle_time = (row['b_booking_confirmation_date'] - row['s_creation_of_shipment']).days
            if cycle_time >= 0:
                cycle_times.append(cycle_time)
    
    avg_cycle_time = np.mean(cycle_times) if cycle_times else 0
    
    # Comparativo MoM
    last_month_data = df[df['s_creation_of_shipment'].dt.to_period('M') == last_month.strftime('%Y-%m')]
    last_month_containers = last_month_data['s_quantity_of_containers'].sum()
    containers_delta = total_containers - last_month_containers if last_month_containers > 0 else 0
    
    return {
        'total_containers': total_containers,
        'total_volume_tons': total_volume_tons,
        'approval_rate': approval_rate,
        'avg_cycle_time': avg_cycle_time,
        'containers_delta': containers_delta,
        'total_requests': total_requests,
        'approved_requests': approved_requests
    }

def create_monthly_trend_chart(df):
    """Cria gráfico de tendência mensal de bookings"""
    # Agrupar por mês
    df['month'] = df['s_creation_of_shipment'].dt.to_period('M')
    monthly_data = df.groupby('month').agg({
        'farol_reference': 'count',
        'farol_status': lambda x: (x == 'Booking Approved').sum(),
        's_quantity_of_containers': 'sum'
    }).reset_index()
    
    monthly_data.columns = ['Month', 'Total_Created', 'Approved', 'Containers']
    monthly_data['Cancelled'] = monthly_data['Total_Created'] - monthly_data['Approved']
    monthly_data['Month_Str'] = monthly_data['Month'].astype(str)
    
    # Criar gráfico de linhas + área
    base = alt.Chart(monthly_data).encode(
        x=alt.X('Month_Str:N', title='Mês')
    )
    
    line_chart = base.mark_line(strokeWidth=3).encode(
        y=alt.Y('Total_Created:Q', title='Número de Bookings'),
        color=alt.value(COLORS['primary'])
    )
    
    area_chart = base.mark_area(opacity=0.3).encode(
        y=alt.Y('Approved:Q', title='Aprovados'),
        color=alt.value(COLORS['success'])
    )
    
    chart = (line_chart + area_chart).resolve_scale(
        y='independent'
    ).properties(
        height=400,
        title='Tendência Mensal de Bookings'
    )
    
    return chart

def create_business_unit_performance_chart(df):
    """Cria gráfico de performance por Business Unit"""
    bu_data = df.groupby('s_business').agg({
        's_quantity_of_containers': 'sum',
        'farol_status': lambda x: (x == 'Booking Approved').sum() / len(x) * 100,
        'farol_reference': 'count'
    }).reset_index()
    
    bu_data.columns = ['Business_Unit', 'Containers', 'Approval_Rate', 'Total_Bookings']
    
    chart = alt.Chart(bu_data).mark_bar().encode(
        x=alt.X('Containers:Q', title='Volume de Containers'),
        y=alt.Y('Business_Unit:N', title='Business Unit', sort='-x'),
        color=alt.Color('Approval_Rate:Q', 
                       scale=alt.Scale(domain=[0, 100], range=[COLORS['danger'], COLORS['success']]),
                       legend=alt.Legend(title="Taxa de Aprovação (%)")),
        tooltip=['Business_Unit', 'Containers', 'Approval_Rate', 'Total_Bookings']
    ).properties(
        height=300,
        title='Performance por Business Unit'
    )
    
    return chart

def create_lead_time_analysis(df):
    """Cria análise de lead time"""
    # Calcular lead times
    lead_times = []
    for _, row in df.iterrows():
        if (pd.notna(row['s_creation_of_shipment']) and 
            pd.notna(row['b_creation_of_booking'])):
            lead_time = (row['b_creation_of_booking'] - row['s_creation_of_shipment']).days
            if 0 <= lead_time <= 30:  # Filtrar outliers
                lead_times.append({
                    'Lead_Time_Days': lead_time,
                    'Business_Unit': row['s_business'],
                    'Carrier': row['b_voyage_carrier']
                })
    
    if not lead_times:
        return None
    
    lead_time_df = pd.DataFrame(lead_times)
    
    # Criar box plot
    chart = alt.Chart(lead_time_df).mark_boxplot().encode(
        x=alt.X('Lead_Time_Days:Q', title='Lead Time (dias)'),
        y=alt.Y('Business_Unit:N', title='Business Unit'),
        color=alt.value(COLORS['primary'])
    ).properties(
        height=300,
        title='Análise de Lead Time (Shipment → Booking Request)'
    )
    
    return chart

def create_top_routes_chart(df):
    """Cria gráfico de top rotas"""
    # Criar coluna de rota
    df['Route'] = df['s_port_of_loading_pol'].astype(str) + ' → ' + df['s_port_of_delivery_pod'].astype(str)
    
    route_data = df.groupby('Route').agg({
        's_quantity_of_containers': 'sum',
        'farol_reference': 'count'
    }).reset_index()
    
    route_data.columns = ['Route', 'Containers', 'Bookings']
    route_data = route_data.nlargest(15, 'Containers')
    
    chart = alt.Chart(route_data).mark_bar().encode(
        x=alt.X('Containers:Q', title='Volume de Containers'),
        y=alt.Y('Route:N', title='Rota', sort='-x'),
        color=alt.value(COLORS['primary']),
        tooltip=['Route', 'Containers', 'Bookings']
    ).properties(
        height=500,
        title='Top 15 Rotas por Volume'
    )
    
    return chart

def create_freight_rate_analysis(df):
    """Cria análise de freight rate"""
    # Filtrar dados com freight rate válido
    freight_data = df[
        (df['b_freight_rate_usd'].notna()) & 
        (df['b_freightppnl'].notna()) & 
        (df['s_quantity_of_containers'].notna()) &
        (df['b_freight_rate_usd'] > 0) &
        (df['b_freightppnl'] > 0)
    ].copy()
    
    if freight_data.empty:
        return None
    
    # Criar scatter plot
    chart = alt.Chart(freight_data).mark_circle(size=100).encode(
        x=alt.X('b_freight_rate_usd:Q', title='Freight Rate (USD)'),
        y=alt.Y('b_freightppnl:Q', title='Freight PPNL (USD)'),
        size=alt.Size('s_quantity_of_containers:Q', 
                     scale=alt.Scale(range=[50, 500]),
                     legend=alt.Legend(title="Containers")),
        color=alt.Color('s_business:N', 
                       scale=alt.Scale(scheme='category20'),
                       legend=alt.Legend(title="Business Unit")),
        tooltip=['farol_reference', 's_business', 'b_freight_rate_usd', 'b_freightppnl', 's_quantity_of_containers']
    ).properties(
        height=400,
        title='Análise de Freight Rate vs PPNL'
    )
    
    return chart

def create_carrier_efficiency_table(df):
    """Cria tabela de eficiência de carriers"""
    # Calcular métricas por carrier
    carrier_metrics = []
    
    for carrier in df['b_voyage_carrier'].dropna().unique():
        carrier_data = df[df['b_voyage_carrier'] == carrier]
        
        total_containers = carrier_data['s_quantity_of_containers'].sum()
        total_bookings = len(carrier_data)
        
        # Calcular on-time departure rate
        on_time_data = carrier_data[
            (carrier_data['b_data_estimativa_saida_etd'].notna()) & 
            (carrier_data['b_data_partida_atd'].notna())
        ]
        
        if not on_time_data.empty:
            on_time_rate = (on_time_data['b_data_partida_atd'] <= on_time_data['b_data_estimativa_saida_etd']).mean() * 100
        else:
            on_time_rate = 0
        
        # Calcular score de performance (0-100)
        volume_score = min(total_containers / 1000 * 20, 40)  # Max 40 pontos por volume
        frequency_score = min(total_bookings * 2, 30)  # Max 30 pontos por frequência
        on_time_score = on_time_rate * 0.3  # Max 30 pontos por pontualidade
        
        performance_score = volume_score + frequency_score + on_time_score
        
        carrier_metrics.append({
            'Carrier': carrier,
            'Total_Containers': total_containers,
            'Total_Bookings': total_bookings,
            'On_Time_Rate': on_time_rate,
            'Performance_Score': performance_score
        })
    
    carrier_df = pd.DataFrame(carrier_metrics)
    carrier_df = carrier_df.nlargest(10, 'Performance_Score')
    
    return carrier_df

def create_demand_forecast_chart(df):
    """Cria forecast de demanda"""
    # Agrupar por semana solicitada
    df['requested_week'] = df['s_requested_shipment_week'].dt.to_period('W')
    forecast_data = df.groupby(['requested_week', 's_business']).agg({
        's_quantity_of_containers': 'sum'
    }).reset_index()
    
    forecast_data.columns = ['Week', 'Business_Unit', 'Containers']
    forecast_data['Week_Str'] = forecast_data['Week'].astype(str)
    
    # Pegar próximas 12 semanas
    current_week = datetime.now().to_period('W')
    future_weeks = [current_week + i for i in range(12)]
    forecast_data = forecast_data[forecast_data['Week'].isin(future_weeks)]
    
    if forecast_data.empty:
        return None
    
    chart = alt.Chart(forecast_data).mark_bar().encode(
        x=alt.X('Week_Str:N', title='Semana'),
        y=alt.Y('Containers:Q', title='Volume de Containers'),
        color=alt.Color('Business_Unit:N', 
                       scale=alt.Scale(scheme='category20'),
                       legend=alt.Legend(title="Business Unit")),
        tooltip=['Week', 'Business_Unit', 'Containers']
    ).properties(
        height=400,
        title='Forecast de Demanda - Próximas 12 Semanas'
    )
    
    return chart

def exibir_performance_control():
    """Função principal do dashboard Performance Control"""
    st.title("📈 Performance Control")
    st.markdown("**Dashboard Executivo - Análise Estratégica de Bookings Marítimos**")
    
    # Sidebar com filtros
    st.sidebar.header("🔍 Filtros Executivos")
    
    days_back = st.sidebar.selectbox(
        "Período de Análise",
        [90, 180, 365],
        index=1,
        format_func=lambda x: f"Últimos {x} dias"
    )
    
    # Carregar dados
    df = load_performance_data(days_back)
    
    if df.empty:
        st.warning("Nenhum dado encontrado para o período selecionado.")
        return
    
    # Filtros dinâmicos com verificação de segurança
    business_units = ['Todas']
    if 's_business' in df.columns and not df.empty:
        business_units.extend(sorted(df['s_business'].dropna().unique().tolist()))
    business_unit = st.sidebar.selectbox("Business Unit", business_units)
    
    trade_regions = ['Todas']
    if 'b_destination_trade_region' in df.columns and not df.empty:
        trade_regions.extend(sorted(df['b_destination_trade_region'].dropna().unique().tolist()))
    trade_region = st.sidebar.selectbox("Trade Region", trade_regions)
    
    countries = ['Todos']
    if 'b_pod_country' in df.columns and not df.empty:
        countries.extend(sorted(df['b_pod_country'].dropna().unique().tolist()))
    country = st.sidebar.selectbox("País de Destino", countries)
    
    # Aplicar filtros
    if business_unit != 'Todas' or trade_region != 'Todas' or country != 'Todos':
        df = load_performance_data(days_back, business_unit, trade_region, country)
    
    # Calcular KPIs executivos
    kpis = calculate_executive_kpis(df)
    
    # Exibir KPIs executivos
    st.subheader("🎯 KPIs Executivos")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Containers Embarcados (Mês Atual)",
            value=f"{kpis['total_containers']:,.0f}",
            delta=f"{kpis['containers_delta']:+,.0f}" if kpis['containers_delta'] != 0 else None
        )
    
    with col2:
        st.metric(
            label="Volume em Toneladas (Mês Atual)",
            value=f"{kpis['total_volume_tons']:,.0f}",
            delta=None
        )
    
    with col3:
        st.metric(
            label="Taxa de Aprovação Geral",
            value=f"{kpis['approval_rate']:.1f}%",
            delta=f"{kpis['approved_requests']}/{kpis['total_requests']}"
        )
    
    with col4:
        st.metric(
            label="Tempo Médio de Ciclo",
            value=f"{kpis['avg_cycle_time']:.1f} dias",
            delta=None
        )
    
    st.markdown("---")
    
    # Visualizações estratégicas
    col1, col2 = st.columns(2)
    
    with col1:
        # Tendência Mensal
        st.altair_chart(create_monthly_trend_chart(df), use_container_width=True)
    
    with col2:
        # Performance por Business Unit
        st.altair_chart(create_business_unit_performance_chart(df), use_container_width=True)
    
    # Análise de Lead Time
    st.subheader("⏱️ Análise de Lead Time")
    lead_time_chart = create_lead_time_analysis(df)
    if lead_time_chart:
        st.altair_chart(lead_time_chart, use_container_width=True)
    else:
        st.info("Dados insuficientes para análise de lead time.")
    
    # Top Rotas e Análise de Freight Rate
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🗺️ Top Rotas")
        st.altair_chart(create_top_routes_chart(df), use_container_width=True)
    
    with col2:
        st.subheader("💰 Análise de Freight Rate")
        freight_chart = create_freight_rate_analysis(df)
        if freight_chart:
            st.altair_chart(freight_chart, use_container_width=True)
        else:
            st.info("Dados insuficientes para análise de freight rate.")
    
    # Eficiência de Carriers
    st.subheader("🚢 Eficiência de Carriers")
    carrier_efficiency = create_carrier_efficiency_table(df)
    if not carrier_efficiency.empty:
        st.dataframe(
            carrier_efficiency,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Carrier": "Carrier",
                "Total_Containers": st.column_config.NumberColumn("Containers", format="%d"),
                "Total_Bookings": st.column_config.NumberColumn("Bookings", format="%d"),
                "On_Time_Rate": st.column_config.NumberColumn("On-Time Rate (%)", format="%.1f"),
                "Performance_Score": st.column_config.NumberColumn("Score", format="%.1f")
            }
        )
    else:
        st.info("Dados insuficientes para análise de eficiência de carriers.")
    
    # Forecast de Demanda
    st.subheader("📊 Forecast de Demanda")
    forecast_chart = create_demand_forecast_chart(df)
    if forecast_chart:
        st.altair_chart(forecast_chart, use_container_width=True)
    else:
        st.info("Dados insuficientes para forecast de demanda.")
    
    # Resumo executivo
    st.subheader("📋 Resumo Executivo")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        unique_customers = df['s_customer'].nunique()
        st.metric(
            label="Clientes Únicos",
            value=unique_customers,
            delta=None
        )
    
    with col2:
        avg_freight_rate = df['b_freight_rate_usd'].mean()
        st.metric(
            label="Freight Rate Médio (USD)",
            value=f"${avg_freight_rate:,.0f}",
            delta=None
        )
    
    with col3:
        total_revenue_estimate = (df['b_freight_rate_usd'] * df['s_quantity_of_containers']).sum()
        st.metric(
            label="Receita Estimada (USD)",
            value=f"${total_revenue_estimate:,.0f}",
            delta=None
        )

if __name__ == "__main__":
    exibir_performance_control()