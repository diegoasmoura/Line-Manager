# 📊 Dashboards de Gestão Marítima - Farol

## Visão Geral

Os dashboards Farol foram desenvolvidos para fornecer visibilidade completa sobre operações de embarques marítimos, atendendo tanto necessidades operacionais quanto estratégicas.

## 🎯 Dashboards Disponíveis

### 1. 📊 Operation Control
**Público-alvo:** Equipes operacionais, analistas de tickets, coordenadores

**Objetivo:** Monitoramento em tempo real de prazos, workload e ações urgentes

#### KPIs Principais
- **Total de Bookings Ativos:** Contagem de bookings em andamento
- **Bookings Pendentes:** Aguardando aprovação ou confirmação
- **Prazos Críticos:** Bookings com deadline < 48 horas
- **Taxa de Resposta Hoje:** Percentual de aprovações no dia

#### Visualizações
- **Funil de Status:** Distribuição de bookings por fase do processo
- **Timeline de Prazos:** Próximos 10 bookings com deadlines urgentes
- **Distribuição de Trabalho:** Carga por operador
- **Bookings por Carrier:** Volume por armador
- **Tabela de Ações Urgentes:** Lista priorizada de ações necessárias

#### Filtros Disponíveis
- Período (7, 15, 30, 60, 90 dias)
- Business Unit
- Status do Booking
- Carrier

### 2. 📈 Performance Control
**Público-alvo:** Gestores, diretores, analistas estratégicos

**Objetivo:** Análise de tendências, eficiência e tomada de decisão estratégica

#### KPIs Executivos
- **Containers Embarcados:** Volume mensal de containers
- **Volume em Toneladas:** Peso total embarcado
- **Taxa de Aprovação Geral:** Percentual de sucesso do processo
- **Tempo Médio de Ciclo:** Shipment Request → Booking Approved

#### Visualizações Estratégicas
- **Tendência Mensal:** Evolução de bookings ao longo do tempo
- **Performance por BU:** Comparativo entre Business Units
- **Análise de Lead Time:** Distribuição de tempos de processamento
- **Top Rotas:** Principais rotas por volume
- **Análise de Freight Rate:** Correlação custo vs receita
- **Eficiência de Carriers:** Ranking de performance
- **Forecast de Demanda:** Projeção para próximas semanas

#### Filtros Executivos
- Período customizável (90, 180, 365 dias)
- Business Unit
- Trade Region
- País de destino

## 🛠️ Implementação Técnica

### Arquitetura
```
operation_control.py     # Dashboard operacional
performance_control.py   # Dashboard executivo
demo_dashboards.py       # Demonstração com dados simulados
```

### Tecnologias
- **Streamlit:** Framework web para dashboards
- **Altair:** Biblioteca de visualizações interativas
- **Pandas:** Manipulação e análise de dados
- **Oracle Database:** Fonte de dados principal
- **SQLAlchemy:** ORM para consultas SQL

### Performance
- **Cache:** 10 minutos para otimização
- **Queries:** Otimizadas com índices específicos
- **Paginação:** Para grandes volumes de dados
- **Filtros:** Aplicados no nível de banco de dados

## 🎨 Design e UX

### Paleta de Cores (Cargill)
- **Primary:** #005EB8 (Azul Cargill)
- **Success:** #00A651 (Verde)
- **Warning:** #FF8200 (Laranja)
- **Danger:** #E31837 (Vermelho)
- **Neutral:** #6C757D (Cinza)

### Layout
- **Responsivo:** Adapta-se a diferentes tamanhos de tela
- **Grid System:** Organização em colunas para melhor aproveitamento
- **Cards:** KPIs destacados em métricas visuais
- **Interatividade:** Gráficos com tooltips e seleção

## 📊 Fontes de Dados

### Tabelas Principais
- **F_CON_SALES_BOOKING_DATA:** Dados unificados de bookings
- **F_CON_RETURN_CARRIERS:** Histórico de alterações
- **F_ELLOX_TERMINAL_MONITORINGS:** Dados de monitoramento

### Campos Utilizados
```sql
-- Operation Control
FAROL_REFERENCE, FAROL_STATUS, B_VOYAGE_CARRIER,
B_DATA_DRAFT_DEADLINE, B_DATA_DEADLINE, B_DATA_ABERTURA_GATE,
USER_LOGIN_BOOKING_CREATED, S_CUSTOMER, S_QUANTITY_OF_CONTAINERS

-- Performance Control  
S_BUSINESS, S_VOLUME_IN_TONS, B_FREIGHT_RATE_USD, B_FREIGHTPPNL,
S_PORT_OF_LOADING_POL, S_PORT_OF_DELIVERY_POD, B_DESTINATION_TRADE_REGION
```

## 🚀 Como Usar

### Acesso aos Dashboards
1. Faça login no sistema Farol
2. No menu lateral, selecione:
   - **"Op. Control"** para dashboard operacional
   - **"Performance"** para dashboard executivo

### Navegação
- **Filtros:** Use a sidebar para refinar os dados
- **Interatividade:** Clique nos gráficos para detalhes
- **Atualização:** Dados são atualizados automaticamente a cada 10 minutos

### Demo
Para testar sem dados reais:
```bash
streamlit run demo_dashboards.py
```

## 📈 Métricas e KPIs

### Operation Control
| Métrica | Descrição | Fórmula |
|---------|-----------|---------|
| Total Ativos | Bookings em andamento | COUNT(status IN ['Requested', 'Approved']) |
| Pendentes | Aguardando aprovação | COUNT(status IN ['Shipment Requested', 'Booking Requested']) |
| Críticos | Deadline < 48h | COUNT(deadline <= NOW + 48h) |
| Taxa Resposta | Aprovações hoje | (aprovados_hoje / pendentes) * 100 |

### Performance Control
| Métrica | Descrição | Fórmula |
|---------|-----------|---------|
| Containers Mês | Volume mensal | SUM(containers WHERE month = current) |
| Volume Tons | Peso total | SUM(volume_tons WHERE month = current) |
| Taxa Aprovação | Sucesso geral | (aprovados / total) * 100 |
| Ciclo Médio | Tempo processamento | AVG(confirmation_date - creation_date) |

## 🔧 Manutenção

### Atualizações de Dados
- **Frequência:** A cada 10 minutos (configurável)
- **Cache:** Limpo automaticamente
- **Performance:** Monitorada via logs

### Troubleshooting
- **Dados não carregam:** Verificar conexão com Oracle
- **Gráficos vazios:** Confirmar filtros aplicados
- **Performance lenta:** Verificar índices do banco

### Customização
- **Novos KPIs:** Adicionar em `calculate_kpis()`
- **Novos gráficos:** Implementar em funções `create_*_chart()`
- **Filtros:** Modificar queries SQL

## 📚 Documentação Adicional

- **README.md:** Documentação geral do sistema
- **database.py:** Funções de acesso a dados
- **app.py:** Configuração do menu principal

## 🎯 Roadmap

### Próximas Funcionalidades
- [ ] Alertas automáticos por email
- [ ] Exportação de relatórios (PDF/Excel)
- [ ] Dashboards mobile otimizados
- [ ] Integração com APIs externas
- [ ] Machine Learning para previsões

### Melhorias Planejadas
- [ ] Temas personalizáveis
- [ ] Widgets arrastáveis
- [ ] Comparativos históricos
- [ ] Análise de correlações
- [ ] Benchmarking de performance

---

**Desenvolvido para Cargill - Sistema Farol v3.9.11**
