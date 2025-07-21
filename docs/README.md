Farol doc

# 📦 Sistema de Gestão de Embarques de Algodão

Este sistema foi desenvolvido para organizar e rastrear embarques de algodão, permitindo o controle de dados de vendas, solicitações de booking, ajustes e divisão de rotas. É dividido em **stages** (etapas), cada uma com responsabilidades específicas.

---

## 👥 Equipes (Stages)

* Sales
    * Insere os embarques
    * Edita campos básicos
    * Realiza ajustes simples
* Booking Management
    * Solicita bookings para os embarques
    * Realiza alterações críticas (critical adjustments)
    * Gerencia divisões de rotas (splits), que exigem validação posterior
* Container Delivery at Port (em desenvolvimento)
    * Etapa responsável pelo controle logístico até o porto


## 🧭 Funcionalidades disponíveis ao entrar na tela

Ao entrar no módulo Shipments (com o stage Sales Data selecionado por padrão), o usuário tem acesso às seguintes funcionalidades:
1. Incluir novo embarque
2. Editar embarque existente (campos básicos)
3. Solicitar Booking
4. Fazer Ajustes Críticos (Adjustments)

📌 Regras de Exibição dos Botões "New Booking" e "Adjustments"
Na tela de Shipments, a exibição dos botões de ação depende do status original do embarque selecionado na coluna Farol Status:
* Botão "New Booking"É exibido somente quando o embarque selecionado possui o status original "New Request".
* Botão "Adjustments"É exibido somente quando o embarque selecionado possui qualquer status original diferente de "New Request".

	⚠️ Importante:	A lógica de exibição considera sempre o valor original do status armazenado no banco de dados, mesmo que o usuário tente editar o status diretamente na grade.	Isso garante que as ações disponíveis estejam alinhadas com a situação real do embarque, evitando inconsistências e tentativas de burlar o fluxo operacional.

---

## 🧩 Detalhamento das opções

### 1. 🆕 Incluir novo embarque
* Acessa via botão New Shipment
* Preenche os 13 campos obrigatórios
* Ao confirmar:
    * Registro salvo na tabela F_CON_SALES_DATA
    * Status padrão: New Request
---
### 2. ✏️ Editar embarque (Shipments)

* Permite editar campos habilitados diretamente na grade
* Gatilhos:
    * Se alterações forem feitas, a grade Changes Made é exibida
    * Ao confirmar:
        * Registro salvo na tabela F_CON_ADJUSTMENTS_LOG
        * Request Type = Basic, Status = Approved
        * Trigger é ativada, chamando a procedure que atualiza F_CON_SALES_DATA e F_CON_BOOKING_MANAGEMENT
    * Ao descartar:
        * Alterações são desfeitas e a grade some

📌 **Restrições de Edição por Stage:**
* **Campos do Sales Data**: Editáveis apenas no stage "Sales Data"
    * **Type of Shipment**: Somente leitura nos outros stages
    * **Sales Quantity of Containers**: Somente leitura nos outros stages
    * **Container Type**: Somente leitura nos outros stages
    * **Booking Port of Loading POL**: Somente leitura no Booking Management (dados do Sales Data)
    * **Booking Port of Delivery POD**: Somente leitura no Booking Management (dados do Sales Data)
    * **Sales Port of Loading POL**: Somente leitura no Container Delivery at Port
    * **Sales Port of Delivery POD**: Somente leitura no Container Delivery at Port
    * Isso garante integridade dos dados, pois esses campos existem originalmente na tabela Sales Data e são trazidos via JOIN para os outros stages
🟡 Farol Status – Controle e restrições
* Os seguintes status estão disponíveis na coluna Farol Status da tela shipments.py:
    * New Request
    * Booking Requested
    * Received from Carrier
    * Booking Under Review
    * Adjustment Requested
    * Booking Approved
    * Booking Cancelled
    * Booking Rejected
* ⚠️ O status Adjustment Requested é controlado exclusivamente pelo módulo booking_adjustments.py
    * Não deve ser alterado diretamente na tela shipments.py
    * Se o usuário tentar:
        * Alterar de Adjustment Requested para qualquer outro status
        * Alterar para Adjustment Requested a partir de qualquer outro status
* → O sistema não exibirá a grade de alterações (Changes Made) e apresentará o seguinte aviso:⚠️ Status 'Adjustment Requested' não pode ser alterado diretamente. Use o módulo de ajustes para solicitar mudanças.
---

### 3. 📤 Solicitar Booking

Disponível apenas para embarques com status New Request
Acessa via botão New Booking (requer seleção prévia de um embarque)
Campos obrigatórios:
* Carrier
* Freight Forwarder
* Booking Request Date/Time
Ao confirmar:
* Registro é salvo na tabela F_CON_BOOKING_MANAGEMENT
* O status do embarque na F_CON_SALES_DATA é atualizado para Booking Requested
---

### 4. 🛠️ Ajustes Críticos (Adjustments)

Ajustes críticos são realizados via botão Adjustments, disponível na tela principal após a seleção de um embarque. Essa funcionalidade foi criada para:
* Alterar campos não editáveis diretamente na tela de Shipments
* Executar splits (divisão de rota, criando múltiplas linhas)

---

#### 🧭 Como funciona

O campo Split Number define o tipo de ajuste:
* 0 → Ajuste na linha principal
* >0 → Criará novas linhas com base em splits

Campos ajustáveis incluem:
* POL, POD, Carrier, Datas e demais campos não disponíveis para edição direta na tela

Após preenchimento da justificativa e confirmação:
* Registro é salvo na tabela F_CON_ADJUSTMENTS_LOG
* Request Type = Critic, Status = Pending
* O campo Farol Status é atualizado para Adjustment Requested nas tabelas:
    * F_CON_SALES_DATA
    * F_CON_BOOKING_MANAGEMENT
* Splits ficam ocultos na tela até aprovação
* Triggers e procedures não são acionadas neste momento


---

#### 📝 Ajustes normais (sem split)

- As alterações permanecem pendentes até revisão
- Apenas após aprovação na tela `Review Adjustments` é que as mudanças são aplicadas nas tabelas principais F_CON_SALES_DATA
- Toda alteração é rastreada via:

  - Coluna alterada
  - Valor anterior e novo valor
  - Justificativa: área, motivo, responsável e comentários opcionais

#### 🔀 Ajustes com Split

- Splits são criados como **novas linhas** nas tabelas `F_CON_SALES_DATA` e `F_CON_BOOKING_MANAGEMENT`
- Estas novas linhas já possuem os dados ajustados informados pelo usuário
- Porém, **só ficam visíveis na interface** (`Shipments.py`) **após aprovação**

- Isso é controlado por um filtro no código:

  ```python
  df = df[
      ~(
          (df["Type of Shipment"] == "Split") & 
          (df["Farol Status"] == "Adjustment Requested")
      )
  ]

## ✅ Diferença entre ajustes Basic vs Critic

| Ajuste via...                  | Request Type | Status       | Trigger?  | Justificativa?    | Aprovado automático? |
|-----------------------|---------------|-----------|----------|----------------|-------------------------|
| Shipments (edição)     | Basic               | Approved  | Sim         | Não                   | Sim                                  |
| Adjustments (crítico)   | Critic               | Pending     | Não        | Sim                    | Não (depende de validação posterior) |

---

## 📋 Gestão de Aprovações de Ajustes (Booking Adjustments)

O módulo **Booking Adjustments** (`booking_adjustments.py`) é responsável pela revisão e aprovação dos ajustes críticos solicitados através da tela de Adjustments. Esta funcionalidade centraliza o controle de qualidade e validação das mudanças antes que sejam efetivadas no sistema.

### 🎯 Funcionalidades Principais

#### 🔍 **Filtros de Pesquisa**
- **Período**: Hoje, Últimos 7 dias, Últimos 30 dias, Todos
- **Busca por Farol Reference**: Campo de texto para localização rápida
- **Status**: Filtragem por status de aprovação
- **Área**: Filtro por área responsável pelo ajuste
- **Stage**: Filtro por etapa do processo (Sales Data, Booking Management, etc.)

#### 📊 **Interface Simplificada**

**Grade Única de Adjustment Management**
- **Interface direta**: Sem abas - grade principal para agilizar aprovações
- **Dados simulados**: Visualização da `F_CON_SALES_DATA` com ajustes aplicados
- **Colunas consistentes**: Mesmas colunas da tela `shipments_split.py`
- **Edição in-line**: Status editável diretamente na grade via `st.data_editor`
- **Resumo visual**: Coluna "Changes Made" com alterações aplicadas
- **Comentários**: Coluna "Comments" da solicitação original
- **Rastreabilidade**: "Adjustment ID" para controle completo
- **Tratamento de splits**: Linhas separadas para cada split de embarque

### ⚙️ **Sistema de Aprovação**

#### 🎮 **Controles de Status**
O sistema utiliza os status oficiais da tabela UDC (Farol Status):
- **Adjustment Requested**: Aguardando aprovação
- **Booking Approved**: Ajuste aprovado e efetivado
- **Booking Rejected**: Ajuste rejeitado
- **Booking Cancelled**: Ajuste cancelado
- **Received from Carrier**: Recebido do transportador

#### ✅ **Processo de Aprovação**

**1. Seleção do Status**
- Dropdown com opções da UDC para garantir consistência
- Aplicação do status para todos os ajustes da Farol Reference

**2. Atualização em Lote**
- Um clique aprova/rejeita todos os ajustes de uma referência
- Atualização automática nas tabelas principais:
  - `F_CON_SALES_DATA`
  - `F_CON_BOOKING_MANAGEMENT`
  - `F_CON_CARGO_LOADING_CONTAINER_RELEASE`

**3. Rastreabilidade**
- Data de confirmação registrada automaticamente
- Histórico completo na `F_CON_ADJUSTMENTS_LOG`

### 📝 **Resumo de Alterações**

Para cada Farol Reference, o sistema exibe:
- **Splits**: Novas referências criadas com quantidades
- **Alterações de Campos**: Formato "Campo: Valor Anterior → Novo Valor"
- **Detalhes Individuais**: Visualização opcional de cada ajuste específico

### 🔧 **Controles de Interface**

- **Update Status**: Botão principal para aplicar o status selecionado
- **View Details**: Exibe dados ajustados simulados (mesmas colunas da Adjusted Data View)
  - Visualização principal com dados simulados finais
  - Seção adicional com detalhes técnicos dos ajustes individuais
- **Layout Responsivo**: Interface otimizada com colunas balanceadas

### ⚠️ **Regras Importantes**

1. **Aprovação Unificada**: Todos os ajustes de uma Farol Reference são aprovados/rejeitados em conjunto
2. **Consistência UDC**: Apenas status válidos da tabela UDC são utilizados
3. **Visibilidade de Splits**: Splits só ficam visíveis na tela principal após aprovação
4. **Rastreabilidade Completa**: Todas as ações são logadas com data/hora

### 📈 **Métricas Exibidas**

- **Total Adjustments**: Número total de ajustes no filtro atual
- **Farol References**: Quantidade de referências únicas afetadas
- **Pending Adjustments**: Ajustes aguardando aprovação

---

## 🔧 Tela Principal de Adjustment Management

A **interface simplificada** foi implementada para fornecer uma **experiência direta e eficiente** de aprovação de ajustes, mostrando uma **simulação visual** dos dados da `F_CON_SALES_DATA` já com os ajustes aplicados.

### 🎯 **Design Simplificado**

- **Interface Única**: Sem abas - grade principal para agilizar o processo de aprovação
- **Simulação Prévia**: Visualização dos dados já com ajustes aplicados
- **Estrutura Consistente**: Mesmas colunas da tela `shipments_split.py`
- **Aprovação Direta**: Edição de status in-line para decisões rápidas

### 📊 **Estrutura de Colunas**

A visualização apresenta as **mesmas colunas da tela de split**, garantindo familiaridade ao usuário:

| Coluna | Descrição | Editável |
|--------|-----------|----------|
| **Farol Reference** | Referência única do embarque | ❌ |
| **Status** | Status atual do ajuste | ✅ |
| **Quantity** | Quantidade de containers (com splits aplicados) | ❌ |
| **POL** | Porto de Carregamento | ❌ |
| **POD** | Porto de Destino (com ajustes aplicados) | ❌ |
| **Place of Receipt** | Local de Recebimento | ❌ |
| **Final Destination** | Destino Final | ❌ |
| **Carrier** | Transportador | ❌ |
| **Cut-off Start** | Data de Cut-off Início | ❌ |
| **Cut-off End** | Data de Cut-off Fim | ❌ |
| **Required Arrival** | Data de Chegada Requerida | ❌ |
| **Changes Made** | Resumo das alterações aplicadas | ❌ |
| **Comments** | Comentários informados na tela shipments_split.py | ❌ |
| **Adjustment ID** | ID único do ajuste para rastreabilidade | ❌ |

### 🔄 **Processamento de Dados**

#### **1. Busca de Dados Originais**
```python
def get_original_sales_data(farol_reference):
    # Busca dados base da F_CON_SALES_DATA
    # para cada Farol Reference
```

#### **2. Aplicação de Ajustes**
```python
def apply_adjustments_to_data(original_data, adjustments_df):
    # Aplica todos os ajustes (exceto splits) 
    # aos dados originais
```

#### **3. Tratamento de Splits**
- **Splits são exibidos como linhas separadas**
- Cada split mostra a **quantidade dividida**
- Mantém os **dados ajustados** aplicados

#### **4. Resumo de Alterações**
```python
def generate_changes_summary(adjustments_df, farol_ref):
    # Gera resumo no formato:
    # 🔧 Split: X containers
    # 📝 Campo: Valor Anterior → Novo Valor
```

### ⚡ **Funcionalidades Interativas**

#### **🎛️ Status Editável In-Grid**
- **Edição direta**: Status pode ser alterado diretamente na grade
- **Dropdown limpo**: Sem opções vazias ou inválidas
- **Opções válidas**:
  - ✅ **Adjustment Requested** (padrão)
  - ✅ **Booking Approved**
  - ✅ **Booking Rejected** 
  - ✅ **Booking Cancelled**
  - ✅ **Received from Carrier**

#### **🔄 Detecção de Mudanças**
- Sistema detecta automaticamente alterações no Status
- Exibe preview das mudanças antes da aplicação
- Botões **Apply Changes** / **Cancel Changes** para controle total

#### **💾 Atualização em Lote**
- Aplica mudanças de status em **todas as tabelas relevantes**:
  - `F_CON_SALES_DATA`
  - `F_CON_BOOKING_MANAGEMENT`
  - `F_CON_CARGO_LOADING_CONTAINER_RELEASE`
- **Transação atômica**: Sucesso completo ou rollback total

### 📋 **Informações Adicionais**

#### **🎨 Changes Made**
- **Formato amigável**: "📝 Campo: Anterior → Novo"
- **Splits destacados**: "🔧 Split: X containers"
- **Múltiplas alterações**: Separadas por " | "

#### **💬 Comments**
- **Contexto**: Exibe comentários originais informados durante a solicitação
- **Origem**: Dados vindos da tela `shipments_split.py`
- **Fallback**: "Nenhum comentário" quando campo vazio

#### **🔍 Adjustment ID**
- **Rastreabilidade**: UUID único para cada conjunto de ajustes
- **Auditoria**: Facilita localização nos logs
- **Consistência**: Mesmo ID para ajustes da mesma solicitação

### ⚙️ **Validações e Robustez**

#### **🛡️ Normalização de Status**
- **Múltiplas camadas** de validação para eliminar valores vazios
- **Status padrão**: "Adjustment Requested" sempre garantido
- **Fallback seguro**: Lista nunca fica vazia

#### **🔒 Integridade dos Dados**
- **Somente Status editável**: Demais colunas protegidas
- **Validação UDC**: Apenas status válidos da tabela UDC
- **Consistência temporal**: Data de confirmação automática

### 🎯 **Benefícios para o Usuário**

#### **👁️ Visualização Clara**
- **Preview completo**: Ver dados finais antes da aprovação
- **Contexto visual**: Mesma interface familiar do split
- **Comparação fácil**: "Changes Made" mostra o que mudou

#### **⚡ Eficiência**
- **Aprovação rápida**: Status direto na grade
- **Menos cliques**: Sem necessidade de abrir modais
- **Batch processing**: Múltiplas referências de uma vez

#### **🔐 Controle Total**
- **Preview das mudanças**: Ver antes de aplicar
- **Cancelamento seguro**: Voltar atrás se necessário
- **Rastreabilidade**: Histórico completo de ações

### 🔄 **Substituição da List View**

A **Adjusted Data View** substitui completamente a antiga **List View**, oferecendo:

| Funcionalidade | List View Anterior | Adjusted Data View Nova |
|---------------|-------------------|------------------------|
| **Visualização** | Dados brutos da tabela | Dados simulados com ajustes |
| **Interatividade** | Apenas leitura | Status editável |
| **Contexto** | Sem informação de mudanças | Resumo completo das alterações |
| **Splits** | Não mostrava divisões | Exibe splits como linhas separadas |
| **Aprovação** | Processo separado | Integrado na visualização |

---

