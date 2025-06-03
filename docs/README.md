# App Farol - Sistema de Gestão de Embarques

## 📋 Visão Geral
O App Farol é um sistema de gestão de embarques que automatiza e controla o fluxo logístico de containers. O sistema é dividido em diferentes estágios (stages) que permitem o acompanhamento completo do processo, desde a solicitação inicial até a entrega final.

## 🚢 Principais Funcionalidades

### 1. Stage: Sales Data
- Cadastro inicial de embarques
- Gerenciamento de solicitações de containers
- Controle de datas e portos de embarque/desembarque

#### Campos Obrigatórios:
- Type of Shipment
- Quantity of Containers
- Requested Shipment Week
- DTHC Prepaid
- Afloat
- Port of Delivery (POD)

#### Campos Opcionais:
- Required Arrival Date
- Requested Cut-off Start Date
- Requested Cut-off End Date
- Port of Loading (POL)
- Final Destination
- Comments Sales

### 2. Stage: Booking Management
- Gestão de reservas junto aos armadores
- Controle de agentes de carga
- Acompanhamento de status de bookings

#### Campos Obrigatórios para Novo Booking:
- Carrier (transportadora/armador)
- Freight Forwarder (agente de carga)
- Booking Request Date
- Booking Request Time
- Comments Booking

## 🔄 Fluxo do Processo

1. **Início do Processo**
   - Cadastro na tela shipments.py
   - Atribuição automática do status "New Request"
   - Registro na tabela LOGTRANSP.F_CON_SALES_DATA

2. **Criação de Registros Vinculados**
   - Geração automática de registro na LOGTRANSP.F_CON_BOOKING_MANAGEMENT
   - Replicação de campos-chave entre as tabelas

3. **Gestão de Booking**
   - Visualização de embarques pendentes
   - Processo de reserva junto aos armadores
   - Atualização de status para "Booking Requested"

## ⚙️ Funcionalidades Especiais

### Ajustes e Correções
O sistema permite dois tipos de alterações:

1. **Alterações Básicas**
   - Realizadas diretamente nas grades de interface
   - Registro automático na tabela F_CON_ADJUSTMENTS_LOG
   - Aplicação imediata via trigger

2. **Alterações Críticas (via Tela Adjustment)**
   - Controle específico para mudanças sensíveis
   - Registro detalhado de modificações
   - Gestão de splits de embarques

### Sistema de Split
- Permite divisão de embarques em múltiplos registros
- Numeração sequencial automática (.1, .2, etc.)
- Marcação especial no campo Type of Shipment

## 📊 Estrutura de Dados

### Principais Tabelas
1. LOGTRANSP.F_CON_SALES_DATA
2. LOGTRANSP.F_CON_BOOKING_MANAGEMENT
3. LOGTRANSP.F_CON_ADJUSTMENTS_LOG
4. LOGTRANSP.F_CON_CARGO_LOADING_CONTAINER_RELEASE

### Tabela de Log (F_CON_ADJUSTMENTS_LOG)
Campos principais:
- Id
- Farol_Reference
- Adjustment_id
- Responsible_Name
- Area
- Request_Type
- Request_Reason
- Adjustments_Owner
- Column_Name
- Previous_Value
- New_Value
- Request_Carrier_Date
- Confirmation_Date
- Stage
- Comments
- Trigger_Log
- Status

## 📝 Observações Importantes
- O processo real de reserva ocorre através do Infor Nexus
- Todas as alterações são registradas para auditoria
- O sistema mantém integridade entre diferentes stages do processo

