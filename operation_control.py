import streamlit as st
import pandas as pd
import altair as alt
from database import get_database_connection
from sqlalchemy import text
from datetime import datetime, timedelta
import numpy as np

def ensure_datetime_columns(df, datetime_columns):
    """Garante que as colunas especificadas sejam do tipo datetime"""
    df_copy = df.copy()
    for col in datetime_columns:
        if col in df_copy.columns:
            if not pd.api.types.is_datetime64_any_dtype(df_copy[col]):
                df_copy[col] = pd.to_datetime(df_copy[col], errors='coerce')
    return df_copy

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
def load_operation_data(days_back=30, business_unit=None, status_filter=None, carrier_filter=None):
    """Carrega dados otimizados para o dashboard operacional"""
    conn = get_database_connection()
    try:
        # Query otimizada para Operation Control
        query = """
        SELECT 
            FAROL_REFERENCE,
            FAROL_STATUS,
            B_VOYAGE_CARRIER,
            B_DATA_DRAFT_DEADLINE,
            B_DATA_DEADLINE,
            B_DATA_ABERTURA_GATE,
            USER_LOGIN_BOOKING_CREATED,
            USER_LOGIN_SALES_CREATED,
            S_CUSTOMER,
            S_BUSINESS,
            S_QUANTITY_OF_CONTAINERS,
            S_CREATION_OF_SHIPMENT,
            B_CREATION_OF_BOOKING,
            B_BOOKING_CONFIRMATION_DATE,
            S_PORT_OF_LOADING_POL,
            S_PORT_OF_DELIVERY_POD
        FROM LogTransp.F_CON_SALES_BOOKING_DATA
        WHERE S_CREATION_OF_SHIPMENT >= SYSTIMESTAMP - :days_back
        """
        
        params = {'days_back': days_back}
        
        # Aplicar filtros
        if business_unit and business_unit != 'Todas':
            query += " AND S_BUSINESS = :business_unit"
            params['business_unit'] = business_unit
            
        if status_filter and status_filter != 'Todos':
            query += " AND FAROL_STATUS = :status_filter"
            params['status_filter'] = status_filter
            
        if carrier_filter and carrier_filter != 'Todos':
            query += " AND B_VOYAGE_CARRIER = :carrier_filter"
            params['carrier_filter'] = carrier_filter
            
        query += " ORDER BY B_DATA_DEADLINE ASC NULLS LAST"
        
        df = pd.read_sql(query, conn, params=params)
        
        # Processar datas
        date_columns = ['B_DATA_DRAFT_DEADLINE', 'B_DATA_DEADLINE', 'B_DATA_ABERTURA_GATE', 
                       'S_CREATION_OF_SHIPMENT', 'B_CREATION_OF_BOOKING', 'B_BOOKING_CONFIRMATION_DATE']
        
        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        return df
        
    except Exception as e:
        st.error(f"Erro ao carregar dados: {str(e)}")
        return pd.DataFrame()
    finally:
        conn.close()

def calculate_kpis(df):
    """Calcula KPIs principais para o dashboard"""
    now = datetime.now()
    
    # Garantir que as colunas de data sejam do tipo datetime
    datetime_columns = ['b_data_deadline', 'b_booking_confirmation_date']
    df = ensure_datetime_columns(df, datetime_columns)
    
    # Total de Bookings Ativos
    total_active = len(df[df['farol_status'].isin(['Shipment Requested', 'Booking Requested', 'Booking Approved'])])
    
    # Bookings Pendentes (aguardando aprovação)
    pending = len(df[df['farol_status'].isin(['Shipment Requested', 'Booking Requested'])])
    
    # Prazos Críticos (< 48h até deadline)
    critical_deadlines = 0
    if 'b_data_deadline' in df.columns:
        critical_deadlines = len(df[
            (df['b_data_deadline'].notna()) & 
            (df['b_data_deadline'] <= now + timedelta(hours=48)) &
            (df['farol_status'].isin(['Shipment Requested', 'Booking Requested']))
        ])
    
    # Taxa de Resposta Hoje (aprovações hoje / total pendente)
    today = now.date()
    approvals_today = 0
    if 'b_booking_confirmation_date' in df.columns:
        approvals_today = len(df[
            (df['b_booking_confirmation_date'].dt.date == today) &
            (df['farol_status'] == 'Booking Approved')
        ])
    
    response_rate = (approvals_today / max(pending, 1)) * 100 if pending > 0 else 0
    
    return {
        'total_active': total_active,
        'pending': pending,
        'critical_deadlines': critical_deadlines,
        'response_rate': response_rate,
        'approvals_today': approvals_today
    }

def create_status_funnel_chart(df):
    """Cria gráfico de funil de status"""
    status_counts = df['farol_status'].value_counts()
    
    # Mapear cores por status
    status_colors = {
        'Shipment Requested': COLORS['warning'],
        'Booking Requested': COLORS['primary'],
        'Booking Approved': COLORS['success'],
        'Booking Confirmed': COLORS['success'],
        'Cancelled': COLORS['danger']
    }
    
    chart_data = pd.DataFrame({
        'Status': status_counts.index,
        'Count': status_counts.values
    })
    
    chart_data['Color'] = chart_data['Status'].map(status_colors).fillna(COLORS['neutral'])
    
    chart = alt.Chart(chart_data).mark_bar().add_selection(
        alt.selection_interval()
    ).encode(
        x=alt.X('Count:Q', title='Quantidade de Bookings'),
        y=alt.Y('Status:N', title='Status', sort='-x'),
        color=alt.Color('Color:N', scale=None, legend=None),
        tooltip=['Status', 'Count']
    ).properties(
        height=300,
        title='Funil de Status de Bookings'
    )
    
    return chart

def create_critical_deadlines_timeline(df):
    """Cria timeline de prazos críticos"""
    now = datetime.now()
    
    # Filtrar próximos 10 bookings com deadlines mais urgentes
    critical_df = df[
        (df['b_data_deadline'].notna()) & 
        (df['farol_status'].isin(['Shipment Requested', 'Booking Requested']))
    ].nlargest(10, 'b_data_deadline')
    
    if critical_df.empty:
        return None
    
    # Preparar dados para timeline
    timeline_data = []
    for _, row in critical_df.iterrows():
        hours_to_deadline = (row['b_data_deadline'] - now).total_seconds() / 3600
        
        timeline_data.append({
            'Farol_Reference': row['farol_reference'][:15] + '...',
            'Carrier': row['b_voyage_carrier'] or 'N/A',
            'Deadline': row['b_data_deadline'].strftime('%d/%m %H:%M'),
            'Hours_Left': hours_to_deadline,
            'Status': 'Critical' if hours_to_deadline < 48 else 'Warning',
            'Containers': row['s_quantity_of_containers'] or 0
        })
    
    timeline_df = pd.DataFrame(timeline_data)
    
    # Criar gráfico de barras horizontais
    chart = alt.Chart(timeline_df).mark_bar().encode(
        x=alt.X('Hours_Left:Q', title='Horas Restantes'),
        y=alt.Y('Farol_Reference:N', title='Farol Reference', sort='-x'),
        color=alt.condition(
            alt.datum.Hours_Left < 48,
            alt.value(COLORS['danger']),
            alt.value(COLORS['warning'])
        ),
        tooltip=['Farol_Reference', 'Carrier', 'Deadline', 'Hours_Left', 'Containers']
    ).properties(
        height=400,
        title='Prazos Críticos - Próximos 10 Bookings'
    )
    
    return chart

def create_workload_distribution_chart(df):
    """Cria gráfico de distribuição de trabalho por operador"""
    # Combinar operadores de booking e sales
    operators = []
    for _, row in df.iterrows():
        if pd.notna(row['user_login_booking_created']):
            operators.append(row['user_login_booking_created'])
        if pd.notna(row['user_login_sales_created']):
            operators.append(row['user_login_sales_created'])
    
    operator_counts = pd.Series(operators).value_counts().head(10)
    
    chart_data = pd.DataFrame({
        'Operator': operator_counts.index,
        'Bookings': operator_counts.values
    })
    
    chart = alt.Chart(chart_data).mark_bar().encode(
        x=alt.X('Bookings:Q', title='Número de Bookings'),
        y=alt.Y('Operator:N', title='Operador', sort='-x'),
        color=alt.value(COLORS['primary']),
        tooltip=['Operator', 'Bookings']
    ).properties(
        height=300,
        title='Distribuição de Trabalho por Operador'
    )
    
    return chart

def create_carrier_distribution_chart(df):
    """Cria gráfico de distribuição por carrier"""
    carrier_counts = df['b_voyage_carrier'].value_counts().head(10)
    
    chart_data = pd.DataFrame({
        'Carrier': carrier_counts.index,
        'Bookings': carrier_counts.values
    })
    
    chart = alt.Chart(chart_data).mark_arc(innerRadius=50).encode(
        theta=alt.Theta('Bookings:Q'),
        color=alt.Color('Carrier:N', scale=alt.Scale(scheme='category20')),
        tooltip=['Carrier', 'Bookings']
    ).properties(
        width=400,
        height=400,
        title='Distribuição de Bookings por Carrier'
    )
    
    return chart

def create_urgent_actions_table(df):
    """Cria tabela de ações urgentes"""
    now = datetime.now()
    
    # Garantir que as colunas de data sejam do tipo datetime
    datetime_columns = ['b_data_deadline', 'b_data_draft_deadline']
    df = ensure_datetime_columns(df, datetime_columns)
    
    urgent_df = df[
        (df['farol_status'].isin(['Shipment Requested', 'Booking Requested'])) &
        (
            (df['b_data_deadline'].notna() & (df['b_data_deadline'] <= now + timedelta(days=3))) |
            (df['b_data_draft_deadline'].notna() & (df['b_data_draft_deadline'] <= now + timedelta(days=3)))
        )
    ].head(20)
    
    if urgent_df.empty:
        return None
    
    # Preparar dados para tabela
    table_data = urgent_df[[
        'farol_reference', 's_customer', 'b_voyage_carrier', 
        'b_data_deadline', 'farol_status', 'user_login_booking_created'
    ]].copy()
    
    table_data['b_data_deadline'] = table_data['b_data_deadline'].dt.strftime('%d/%m/%Y %H:%M')
    table_data['Hours_Left'] = (urgent_df['b_data_deadline'] - now).dt.total_seconds() / 3600
    table_data['Hours_Left'] = table_data['Hours_Left'].round(1)
    
    return table_data

def exibir_operation_control():
    """Função principal do dashboard Operation Control"""
    st.title("📊 Operation Control")
    st.markdown("**Dashboard Operacional - Gestão de Bookings Marítimos**")
    
    # Carregar dados (últimos 30 dias por padrão)
    df = load_operation_data(30)
    
    if df.empty:
        st.warning("Nenhum dado encontrado para o período selecionado.")
        return
    
    # Calcular KPIs
    kpis = calculate_kpis(df)
    
    # Exibir KPIs principais
    st.subheader("📈 KPIs Principais")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total de Bookings Ativos",
            value=kpis['total_active'],
            delta=None
        )
    
    with col2:
        st.metric(
            label="Bookings Pendentes",
            value=kpis['pending'],
            delta=None
        )
    
    with col3:
        st.metric(
            label="Prazos Críticos (< 48h)",
            value=kpis['critical_deadlines'],
            delta=None
        )
    
    with col4:
        st.metric(
            label="Taxa de Resposta Hoje",
            value=f"{kpis['response_rate']:.1f}%",
            delta=f"{kpis['approvals_today']} aprovações"
        )
    
    st.markdown("---")
    
    # Visualizações principais
    col1, col2 = st.columns(2)
    
    with col1:
        # Funil de Status
        st.altair_chart(create_status_funnel_chart(df), use_container_width=True)
    
    with col2:
        # Distribuição por Carrier
        st.altair_chart(create_carrier_distribution_chart(df), use_container_width=True)
    
    # Timeline de Prazos Críticos
    st.subheader("⏰ Prazos Críticos")
    critical_chart = create_critical_deadlines_timeline(df)
    if critical_chart:
        st.altair_chart(critical_chart, use_container_width=True)
    else:
        st.info("Nenhum prazo crítico encontrado para os próximos 10 bookings.")
    
    # Distribuição de Trabalho e Tabela de Ações Urgentes
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("👥 Distribuição de Trabalho")
        st.altair_chart(create_workload_distribution_chart(df), use_container_width=True)
    
    with col2:
        st.subheader("🚨 Ações Urgentes")
        urgent_table = create_urgent_actions_table(df)
        if urgent_table is not None and not urgent_table.empty:
            st.dataframe(
                urgent_table,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "farol_reference": "Farol Ref",
                    "s_customer": "Cliente",
                    "b_voyage_carrier": "Carrier",
                    "b_data_deadline": "Deadline",
                    "farol_status": "Status",
                    "user_login_booking_created": "Operador",
                    "Hours_Left": "Horas Restantes"
                }
            )
        else:
            st.info("Nenhuma ação urgente encontrada.")
    
    # Novos gráficos bonitos
    st.subheader("📈 Análises Avançadas")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Gráfico de Timeline de Criação de Bookings
        st.subheader("📅 Timeline de Criação de Bookings")
        timeline_data = df.copy()
        timeline_data = ensure_datetime_columns(timeline_data, ['s_creation_of_shipment'])
        timeline_data['date'] = timeline_data['s_creation_of_shipment'].dt.date
        daily_counts = timeline_data.groupby('date').size().reset_index(name='bookings')
        
        if not daily_counts.empty:
            chart = alt.Chart(daily_counts).mark_area(
                interpolate='monotone',
                color=COLORS['primary']
            ).encode(
                x=alt.X('date:T', title='Data'),
                y=alt.Y('bookings:Q', title='Número de Bookings'),
                tooltip=['date:T', 'bookings:Q']
            ).properties(
                height=300,
                title='Bookings Criados por Dia'
            )
            st.altair_chart(chart, use_container_width=True)
    
    with col2:
        # Gráfico de Bookings Requested sem Resposta do Carrier
        st.subheader("⏳ Bookings sem Resposta do Carrier")
        if not df.empty:
            # Filtrar bookings que estão em "Booking Requested" há mais de 3 dias
            now = datetime.now()
            pending_bookings = df[
                (df['farol_status'] == 'Booking Requested') &
                (df['b_creation_of_booking'].notna())
            ].copy()
            
            if not pending_bookings.empty:
                pending_bookings = ensure_datetime_columns(pending_bookings, ['b_creation_of_booking'])
                pending_bookings['days_waiting'] = (now - pending_bookings['b_creation_of_booking']).dt.days
                pending_bookings = pending_bookings[pending_bookings['days_waiting'] >= 3]
                
                if not pending_bookings.empty:
                    # Agrupar por carrier e mostrar tempo médio de espera
                    carrier_waiting = pending_bookings.groupby('b_voyage_carrier').agg({
                        'farol_reference': 'count',
                        'days_waiting': 'mean'
                    }).reset_index()
                    carrier_waiting.columns = ['carrier', 'bookings', 'avg_days_waiting']
                    carrier_waiting = carrier_waiting.sort_values('avg_days_waiting', ascending=False)
                    
                    chart = alt.Chart(carrier_waiting).mark_bar().encode(
                        x=alt.X('avg_days_waiting:Q', title='Dias Médios de Espera'),
                        y=alt.Y('carrier:N', title='Carrier', sort='-x'),
                        color=alt.condition(
                            alt.datum.avg_days_waiting > 7,
                            alt.value(COLORS['danger']),
                            alt.condition(
                                alt.datum.avg_days_waiting > 5,
                                alt.value(COLORS['warning']),
                                alt.value(COLORS['primary'])
                            )
                        ),
                        tooltip=['carrier', 'bookings', 'avg_days_waiting']
                    ).properties(
                        height=300,
                        title='Carriers com Maior Tempo de Resposta'
                    )
                    st.altair_chart(chart, use_container_width=True)
                else:
                    st.info("✅ Nenhum booking aguardando resposta há mais de 3 dias.")
            else:
                st.info("Nenhum booking em status 'Booking Requested' encontrado.")
    
    # Tabela de Bookings Aguardando Resposta
    st.subheader("📋 Bookings Aguardando Resposta do Carrier")
    if not df.empty:
        now = datetime.now()
        waiting_bookings = df[
            (df['farol_status'] == 'Booking Requested') &
            (df['b_creation_of_booking'].notna())
        ].copy()
        
        if not waiting_bookings.empty:
            waiting_bookings = ensure_datetime_columns(waiting_bookings, ['b_creation_of_booking'])
            waiting_bookings['days_waiting'] = (now - waiting_bookings['b_creation_of_booking']).dt.days
            waiting_bookings = waiting_bookings[waiting_bookings['days_waiting'] >= 3]
            waiting_bookings = waiting_bookings.sort_values('days_waiting', ascending=False)
            
            if not waiting_bookings.empty:
                # Preparar dados para tabela
                table_data = waiting_bookings[[
                    'farol_reference', 's_customer', 'b_voyage_carrier', 
                    'b_creation_of_booking', 'days_waiting', 's_quantity_of_containers'
                ]].copy()
                
                table_data = ensure_datetime_columns(table_data, ['b_creation_of_booking'])
                table_data['b_creation_of_booking'] = table_data['b_creation_of_booking'].dt.strftime('%d/%m/%Y %H:%M')
                
                # Adicionar status visual baseado no tempo de espera
                def get_waiting_status(days):
                    if days >= 10:
                        return "🔴 Crítico"
                    elif days >= 7:
                        return "🟠 Alto"
                    elif days >= 5:
                        return "🟡 Médio"
                    else:
                        return "🟢 Normal"
                
                table_data['status'] = table_data['days_waiting'].apply(get_waiting_status)
                
                st.dataframe(
                    table_data,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "farol_reference": "Farol Ref",
                        "s_customer": "Cliente",
                        "b_voyage_carrier": "Carrier",
                        "b_creation_of_booking": "Data do Booking",
                        "days_waiting": st.column_config.NumberColumn("Dias Esperando", format="%d"),
                        "s_quantity_of_containers": st.column_config.NumberColumn("Containers", format="%d"),
                        "status": "Status"
                    }
                )
            else:
                st.info("✅ Nenhum booking aguardando resposta há mais de 3 dias.")
        else:
            st.info("Nenhum booking em status 'Booking Requested' encontrado.")
    
    # Gráfico de Heatmap de Horários
    st.subheader("⏰ Heatmap de Atividade por Horário")
    if not df.empty:
        df = ensure_datetime_columns(df, ['s_creation_of_shipment'])
        df['hour'] = df['s_creation_of_shipment'].dt.hour
        df['day_of_week'] = df['s_creation_of_shipment'].dt.day_name()
        
        heatmap_data = df.groupby(['day_of_week', 'hour']).size().reset_index(name='bookings')
        
        # Ordenar dias da semana
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        heatmap_data['day_of_week'] = pd.Categorical(heatmap_data['day_of_week'], categories=day_order, ordered=True)
        
        chart = alt.Chart(heatmap_data).mark_rect().encode(
            x=alt.X('hour:O', title='Hora do Dia'),
            y=alt.Y('day_of_week:N', title='Dia da Semana', sort=day_order),
            color=alt.Color('bookings:Q', 
                           scale=alt.Scale(scheme='blues'),
                           legend=alt.Legend(title="Bookings")),
            tooltip=['day_of_week', 'hour', 'bookings']
        ).properties(
            height=400,
            title='Atividade de Criação de Bookings por Horário'
        )
        st.altair_chart(chart, use_container_width=True)
    
    # Gráfico de Performance de Operadores
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("👥 Performance de Operadores")
        if not df.empty:
            # Calcular métricas por operador
            operator_metrics = []
            for operator in df['user_login_booking_created'].dropna().unique():
                op_data = df[df['user_login_booking_created'] == operator]
                total_bookings = len(op_data)
                approved_bookings = len(op_data[op_data['farol_status'] == 'Booking Approved'])
                approval_rate = (approved_bookings / total_bookings * 100) if total_bookings > 0 else 0
                
                operator_metrics.append({
                    'operator': operator,
                    'total_bookings': total_bookings,
                    'approval_rate': approval_rate
                })
            
            if operator_metrics:
                op_df = pd.DataFrame(operator_metrics)
                op_df = op_df.nlargest(10, 'total_bookings')
                
                chart = alt.Chart(op_df).mark_circle(size=200).encode(
                    x=alt.X('total_bookings:Q', title='Total de Bookings'),
                    y=alt.Y('approval_rate:Q', title='Taxa de Aprovação (%)'),
                    size=alt.Size('total_bookings:Q', scale=alt.Scale(range=[50, 500])),
                    color=alt.value(COLORS['success']),
                    tooltip=['operator', 'total_bookings', 'approval_rate']
                ).properties(
                    height=300,
                    title='Performance: Volume vs Taxa de Aprovação'
                )
                st.altair_chart(chart, use_container_width=True)
    
    with col2:
        st.subheader("📊 Distribuição de Containers por Status")
        if not df.empty:
            status_containers = df.groupby('farol_status')['s_quantity_of_containers'].sum().reset_index()
            
            chart = alt.Chart(status_containers).mark_arc(innerRadius=50).encode(
                theta=alt.Theta('s_quantity_of_containers:Q'),
                color=alt.Color('farol_status:N', 
                               scale=alt.Scale(scheme='category20'),
                               legend=alt.Legend(title="Status")),
                tooltip=['farol_status', 's_quantity_of_containers']
            ).properties(
                width=400,
                height=300,
                title='Containers por Status'
            )
            st.altair_chart(chart, use_container_width=True)
    
    # Gráfico de Tendência de Aprovações
    st.subheader("📈 Tendência de Aprovações")
    if not df.empty and 'b_booking_confirmation_date' in df.columns:
        # Filtrar apenas bookings aprovados com data de confirmação
        approved_df = df[df['farol_status'] == 'Booking Approved'].copy()
        if not approved_df.empty:
            approved_df = ensure_datetime_columns(approved_df, ['b_booking_confirmation_date'])
            approved_df['date'] = approved_df['b_booking_confirmation_date'].dt.date
            daily_approvals = approved_df.groupby('date').size().reset_index(name='approvals')
            
            # Calcular média móvel de 7 dias
            daily_approvals['ma_7d'] = daily_approvals['approvals'].rolling(window=7, min_periods=1).mean()
            
            base = alt.Chart(daily_approvals).encode(x=alt.X('date:T', title='Data'))
            
            bars = base.mark_bar(opacity=0.7, color=COLORS['primary']).encode(
                y=alt.Y('approvals:Q', title='Aprovações')
            )
            
            line = base.mark_line(strokeWidth=3, color=COLORS['success']).encode(
                y=alt.Y('ma_7d:Q', title='Média Móvel 7 dias')
            )
            
            chart = (bars + line).resolve_scale(y='independent').properties(
                height=400,
                title='Aprovações Diárias e Tendência'
            )
            st.altair_chart(chart, use_container_width=True)
    
    # Resumo estatístico
    st.subheader("📊 Resumo Estatístico")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="Total de Containers",
            value=f"{df['s_quantity_of_containers'].sum():,.0f}",
            delta=None
        )
    
    with col2:
        avg_containers = df['s_quantity_of_containers'].mean()
        st.metric(
            label="Média de Containers/Booking",
            value=f"{avg_containers:.1f}",
            delta=None
        )
    
    with col3:
        unique_customers = df['s_customer'].nunique()
        st.metric(
            label="Clientes Únicos",
            value=unique_customers,
            delta=None
        )

if __name__ == "__main__":
    exibir_operation_control()