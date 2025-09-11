Farol doc

# 📦 Sistema de Gestão de Embarques de Algodão

Este sistema foi desenvolvido para organizar e rastrear embarques de algodão, permitindo o controle de dados de vendas, solicitações de booking, ajustes e divisão de rotas. É dividido em **stages** (etapas), cada uma com responsabilidades específicas.

#️⃣ Guia de Instalação e Execução

## ✅ Pré‑requisitos

- Python 3.10+
- Acesso a um banco Oracle (Oracle Database ou Oracle XE)
- Pacotes Python do projeto (veja `requirements.txt`)

Observação: a conexão usa o driver python-oracledb em modo thin (não requer Instant Client). Se desejar usar o modo thick, configure o client Oracle no host.

## 📦 Instalação

1) Crie e ative um ambiente virtual:

```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .\.venv\Scripts\activate  # Windows PowerShell
```

2) Instale as dependências:

```bash
pip install -r requirements.txt
```

## 🗄️ Configuração do Banco Oracle

O app espera o schema `LOGTRANSP` com as tabelas, triggers, views e procedures deste repositório.

- Scripts recomendados: use os arquivos em `Tabelas Oracle 0.2/` (ordem: 001 … 019) e os auxiliares:
  - `DATA - INSERT INTO F_CON_DE_PARA_TABELAS.sql`
  - `Preenchendo tabela GLOBAL.sql` (popular UDC/Global Variables)

Exemplo de criação de usuário (ajuste conforme sua instância):

```sql
CREATE USER LOGTRANSP IDENTIFIED BY "<senha>";
GRANT CONNECT, RESOURCE TO LOGTRANSP;
ALTER USER LOGTRANSP QUOTA UNLIMITED ON USERS;
```

Service Name padrão esperado: `ORCLPDB1` (ajuste via variável de ambiente se necessário).

## 🔐 Variáveis de Ambiente

As credenciais podem (e devem) ser definidas por variáveis de ambiente. Defaults atuais estão em `database.py` e são apenas para desenvolvimento local.

- `LOGTRANSP_DB_HOST` (padrão: `127.0.0.1`)
- `LOGTRANSP_DB_PORT` (padrão: `1521`)
- `LOGTRANSP_DB_NAME` (Service Name, padrão: `ORCLPDB1`)
- `LOGTRANSP_DB_USER` (padrão: `LOGTRANSP`)
- `LOGTRANSP_DB_PASSWORD` (sem padrão público; defina no seu ambiente)

Exemplo (macOS/Linux):

```bash
export LOGTRANSP_DB_HOST=127.0.0.1
export LOGTRANSP_DB_PORT=1521
export LOGTRANSP_DB_NAME=ORCLPDB1
export LOGTRANSP_DB_USER=LOGTRANSP
export LOGTRANSP_DB_PASSWORD=***
```

## ▶️ Execução

No diretório `Projeto/`:

```bash
streamlit run app.py
```

O menu lateral navega entre `Shipments`, `Adjustments`, `Op. Control`, `Performance`, `Tracking`, `History` e `Setup`.

## 📄 Template de Upload em Massa (Excel)

A tela "New Sales Record → Excel Upload (Bulk)" exige o arquivo `Projeto/docs/template_embarques.xlsx` com os cabeçalhos obrigatórios abaixo. Caso o arquivo não exista, crie um Excel com estas colunas (ordem livre, nomes exatos):

- HC
- Week
- LIMITE EMBARQUE - PNL
- DTHC
- TIPO EMBARQUE
- POD
- INLAND

Notas:
- A coluna "LIMITE EMBARQUE - PNL" deve ser uma data válida (ou deixar em branco).
- "TIPO EMBARQUE" com valor "Afloat" define `Afloat = Yes`.
- O campo "TERM" (se presente) pode ser usado para mapear `VIP/PNL/RISK`.

## 🔢 UDC (Global Variables) – Listas de Opções

O sistema carrega opções da tabela `F_CON_GLOBAL_VARIABLES` para dropdowns. Garanta que os grupos estejam populados (vide `Preenchendo tabela GLOBAL.sql`). Grupos utilizados incluem, entre outros:

- Porto Origem, Porto Destino, Carrier, DTHC, VIP PNL Risk, Yes No
- Business, Mode, Sku, Farol Status, Type of Shipment, Booking Status
- Truck Loading Status, Status ITAS

## 🧠 Ícones do Farol Status

Consulte o guia de ícones em `docs/farol_status_icons_guide.md` para regras de exibição e limpeza de valores antes de salvar no banco.

## ⚠️ Observações Importantes

- Os módulos `Operation Control`, `Performance Control` e `Tracking` estão como placeholders.
- A tela `History` está totalmente funcional, permitindo visualização do ciclo de vida dos tickets e aprovação de alterações.
- Na tela `Shipments`, o status "Adjustment Requested" não pode ser alterado diretamente; use `Adjustments`.
- Em `Adjustments`, a atualização de status reflete nas três tabelas principais (Sales, Booking, Loading).

## 🧱 Estrutura de Pastas (resumo)

- `Projeto/app.py`: Roteamento e menu lateral (Streamlit).
- `Projeto/database.py`: Conexão Oracle (SQLAlchemy + python-oracledb) e operações SQL.
- `Projeto/shipments*.py`: Tela principal, criação e ajustes/splits.
- `Projeto/booking_adjustments.py`: Revisão/aprovação de ajustes e anexos.
- `Projeto/history.py`: Visualização do ciclo de vida dos tickets e aprovação de alterações.
- `Projeto/docs/`: Este README e guias.
- `Tabelas Oracle 0.2/`: Scripts de criação das tabelas/objetos.

---

## 🧠 Como o sistema funciona

### Arquitetura geral

- Frontend em Streamlit (`app.py`) com um menu lateral que navega entre módulos.
- Camada de dados em `database.py` usando SQLAlchemy + `python-oracledb` para acessar Oracle.
- As telas `shipments.py`, `shipments_new.py`, `shipments_split.py` e `booking_new.py` compõem o fluxo operacional principal; `booking_adjustments.py` orquestra a aprovação dos ajustes e gerencia anexos.
- A tela `history.py` fornece visualização completa do ciclo de vida dos tickets e permite aprovação de alterações com atualização automática das tabelas principais.
- O arquivo `shipments_mapping.py` centraliza o mapeamento entre nomes de colunas do banco e rótulos exibidos na UI, além de configurar colunas editáveis e dropdowns com dados da UDC.

### Tabelas principais

- `F_CON_SALES_DATA` (Sales Data): entrada e base dos embarques.
- `F_CON_BOOKING_MANAGEMENT` (Booking): dados de solicitação/gestão de booking.
- `F_CON_CARGO_LOADING_CONTAINER_RELEASE` (Loading): controle de carregamento/entrega em porto.
- `F_CON_RETURN_CARRIERS` (Return Carriers): histórico de alterações e dados retornados pelos carriers, com campo `ADJUSTMENT_ID` para rastreabilidade.
- `F_CON_ADJUSTMENTS_LOG` (Log): trilha de ajustes básicos e críticos (inclui splits).
- `F_CON_GLOBAL_VARIABLES` (UDC): listas de opções para dropdowns.
- `F_CON_ANEXOS` (Attachments): armazenamento de arquivos por `farol_reference`.

### Fluxo operacional

1) Cadastro (Sales)
- Usuário cria um novo embarque em `shipments_new.py` (manual ou upload Excel).
- Registro é inserido em `F_CON_SALES_DATA` com status inicial "New request".

2) Solicitar Booking
- Em `shipments.py`, com a linha selecionada e status original "New request", o botão "New Booking" habilita a tela `booking_new.py`.
- Ao confirmar, atualiza `F_CON_BOOKING_MANAGEMENT` e sincroniza status "Booking Requested" em Sales e Loading.

3) Ajustes e Splits (críticos)
- Em `shipments.py`, com status original diferente de "New request", o botão "Adjustments" abre `shipments_split.py`.
- O usuário pode:
  - Ajustar campos não editáveis na grade principal (sem split), ou
  - Criar splits (novas referências derivadas `FR_... .N`), definindo quantidades e destinos.
- Ao confirmar, os ajustes são gravados em `F_CON_ADJUSTMENTS_LOG` com `request_type = 'Critic'` e status normalizado para "Adjustment Requested" nas três tabelas (Sales, Booking, Loading). Splits são inseridos como novas linhas com status "Adjustment Requested" e ficam ocultos da listagem até aprovação.

4) Aprovação de Ajustes
- `booking_adjustments.py` exibe uma visão ajustada (simulada) da `F_CON_SALES_DATA` aplicando as mudanças pendentes e exibindo os splits como linhas separadas.
- O aprovador altera o campo "Status" para cada referência e aplica em lote. O sistema atualiza o status nas três tabelas e registra `confirmation_date` no log quando aplicável.

5) Aprovação de Alterações no Histórico
- A tela `History` permite visualizar o ciclo de vida completo dos tickets após a criação do booking.
- Quando uma linha é aprovada (status alterado para "Booking Approved"), o sistema busca automaticamente o `ADJUSTMENT_ID` da linha selecionada.
- Os dados da linha aprovada são utilizados para atualizar a tabela `F_CON_SALES_BOOKING_DATA`, aplicando apenas campos não nulos.
- O vínculo entre as tabelas é feito através do campo `FAROL_REFERENCE`, garantindo consistência dos dados.

6) Anexos
- A seção de anexos está disponível como toggle em `Shipments`, `Adjustments` e `History`.
- Uploads são persistidos em `F_CON_ANEXOS`, com metadados e conteúdo binário. Exclusão é soft delete (marca `process_stage = 'Attachment Deleted'`).

### Regras de negócio essenciais

- "Adjustment Requested" não pode ser editado diretamente em `Shipments`.
- Splits permanecem ocultos até aprovação; a listagem filtra `(Type of Shipment == 'Split' and Farol Status == 'Adjustment Requested')`.
- Aprovação altera o status em Sales, Booking e Loading, independentemente do stage do ajuste.
- Na tela `History`, apenas uma linha pode ser selecionada por vez para evitar inconsistências na aplicação de mudanças.
- Quando uma linha é aprovada no `History` (status "Booking Approved"), apenas campos não nulos são atualizados na tabela `F_CON_SALES_BOOKING_DATA`.
- O campo `ADJUSTMENT_ID` é utilizado para identificar a linha específica que será usada para atualizar os dados, garantindo rastreabilidade completa.
- UDC abastece dropdowns; falta de dados na UDC impacta opções da UI.

### Estado e experiência do usuário

- A navegação e os botões dependem do status ORIGINAL no banco, evitando burlar o fluxo apenas editando a grid.
- Em grids, somente colunas permitidas são editáveis; confirmações pedem comentários quando necessário e fazem commits atômicos.
- Campos de datas são normalizados e, quando não válidos, caem para `None` de forma segura.

## 🧭 Menu Principal e Fluxo de Navegação

O sistema utiliza um menu lateral (sidebar) com as opções:
- Shipments
- Adjustments
- Op. Control
- Performance
- Tracking
- History
- Setup

O fluxo principal é controlado pelo arquivo `app.py`, que direciona para os módulos correspondentes.

---

## 🧩 Funcionalidades e Fluxos Atualizados

- O botão **View Attachments** está disponível em todas as telas principais, sempre visível (toggle), mas desabilitado se nenhuma linha estiver selecionada.
- O layout dos anexos é padronizado em todas as telas, com cards visuais, ícones, informações e botões de download/exclusão.
- Ao aprovar um ajuste na tela de `booking_adjustments.py`, o status é atualizado **sempre** nas três tabelas principais: `F_CON_SALES_DATA`, `F_CON_BOOKING_MANAGEMENT` e `F_CON_CARGO_LOADING_CONTAINER_RELEASE`, independentemente do campo `stage`.
- O campo **Inserted Date** agora é exibido corretamente, com conversão explícita para datetime.
- O formulário de novo embarque (`shipments_new.py`) exibe corretamente todas as opções de DTHC.
- O sistema de anexos está documentado em detalhes no `ANEXOS_README.md`.
- A tela **History** está totalmente funcional, permitindo visualização do ciclo de vida dos tickets e aprovação de alterações com atualização automática da tabela `F_CON_SALES_BOOKING_DATA`. A interface foi aprimorada com detecção automática de mudanças e feedback visual melhorado.
- Os módulos `Operation Control`, `Performance Control` e `Tracking` atualmente exibem apenas um print/placeholder.

---

## 📑 Resumo das Telas

- **Shipments**: Cadastro, edição, ajustes, splits, anexos.
- **Adjustments**: Aprovação/rejeição de ajustes críticos, atualização em lote de status, gestão de anexos.
- **Booking Management**: Solicitação e edição de bookings.
- **History**: Visualização do ciclo de vida dos tickets, aprovação de alterações e rastreabilidade completa via ADJUSTMENT_ID. Interface aprimorada com detecção automática de mudanças e propagação precisa de dados.
- **Operation Control, Performance, Tracking, Setup**: (Placeholders para futuras implementações)

## 📊 Performance Control (estado atual)

O módulo de Performance está em desenvolvimento (placeholder) e, no momento, não possui gráficos nem métricas ativas na interface.

Planejamento (sujeito a mudanças, ainda não implementado):
- Visão de Status (distribuição por Farol Status)
- Timeline de volumes (mensal/semanal, comparação ano a ano)
- Tempo médio entre etapas (KPIs por status)
- Análise por localização (Top POL/POD)
- Performance por Business/SKU

Observação: ao entrar na aba Performance atualmente, será exibida apenas uma indicação de que o módulo está em desenvolvimento.

---

## 🔄 Principais Fluxos

1. **Cadastro de Embarque**: Shipments > New Shipment > Preencher formulário > Confirmar.
2. **Solicitar Booking**: Shipments > Selecionar embarque com status "New Request" > New Booking > Preencher > Confirmar.
3. **Ajuste Crítico/Split**: Shipments > Selecionar embarque > Adjustments > Preencher > Confirmar.
4. **Aprovação de Ajustes**: Adjustments > Filtrar/Selecionar > Editar status > Apply Changes.
5. **Aprovação de Alterações no Histórico**: History > Alterar Farol Status diretamente na grade > Apply Changes > Sistema atualiza automaticamente `F_CON_SALES_BOOKING_DATA` com dados da linha aprovada.
6. **Gestão de Anexos**: Em qualquer tela, selecionar embarque > View Attachments > Upload/Download/Excluir.

---

## 📎 Anexos

Para detalhes completos sobre o sistema de anexos, consulte o arquivo [ANEXOS_README.md](../ANEXOS_README.md).

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

## 📜 Tela de Histórico (Return Carriers History)

A tela de **Histórico** (`history.py`) exibe o ciclo de vida completo dos tickets após a criação do booking, permitindo visualizar e aprovar alterações feitas ao longo do processo. Esta funcionalidade é essencial para o controle de qualidade e rastreabilidade das operações.

### 🎯 **Funcionalidades Principais**

#### 🔍 **Visualização do Ciclo de Vida**
- **Primeira linha**: Registro original do booking
- **Linhas subsequentes**: Alterações e ajustes feitos ao longo do processo
- **Ordenação cronológica**: Registros ordenados por data de inserção (crescente)
- **Rastreabilidade completa**: Cada alteração mantém seu contexto histórico

#### 📊 **Interface da Grade**
- **Detecção automática**: Mudanças detectadas diretamente na coluna "Farol Status" (sem coluna de seleção)
- **Campo visível**: `ADJUSTMENT_ID` exibido para referência e rastreabilidade
- **Colunas editáveis**: Apenas o campo "Farol Status" pode ser alterado
- **Demais campos**: Somente leitura para preservar integridade dos dados

#### 🎮 **Controle de Status**
- **Dropdown de status**: Opções vindas da UDC (Global Variables)
- **Status disponíveis**:
  - Adjustment Requested
  - Booking Requested
  - Booking Approved
  - Booking Rejected
  - Booking Cancelled
  - Received from Carrier

### ⚙️ **Sistema de Aprovação**

#### 🔄 **Processo de Aprovação**
1. **Alteração de Status**: Usuário modifica o "Farol Status" diretamente na grade
2. **Detecção Automática**: Sistema detecta mudanças comparando valores originais vs editados
3. **Aplicação**: Clica em "Apply Changes" para confirmar as alterações
4. **Processamento**: Sistema executa a lógica de aprovação automaticamente

#### ✅ **Lógica de Aprovação Especial**
Quando o status é alterado para **"Booking Approved"**, o sistema executa automaticamente:

**1. Atualização da Tabela Principal**
- Busca os dados da linha aprovada na tabela `F_CON_RETURN_CARRIERS` usando o `ADJUSTMENT_ID`
- Atualiza a tabela `F_CON_SALES_BOOKING_DATA` com os campos não nulos:
  - **Campos S_ (Sales)**: `S_SPLITTED_BOOKING_REFERENCE`, `S_PLACE_OF_RECEIPT`, `S_QUANTITY_OF_CONTAINERS`, `S_PORT_OF_LOADING_POL`, `S_PORT_OF_DELIVERY_POD`, `S_FINAL_DESTINATION`
  - **Campos B_ (Booking)**: `B_TRANSHIPMENT_PORT`, `B_TERMINAL`, `B_VESSEL_NAME`, `B_VOYAGE_CARRIER`, `B_DATA_DRAFT_DEADLINE`, `B_DATA_DEADLINE`, `B_DATA_ESTIMATIVA_SAIDA_ETD`, `B_DATA_ESTIMATIVA_CHEGADA_ETA`, `B_DATA_ABERTURA_GATE`, `B_DATA_PARTIDA_ATD`, `B_DATA_CHEGADA_ATA`, `B_DATA_ESTIMATIVA_ATRACACAO_ETB`, `B_DATA_ATRACACAO_ATB`

**2. Atualização de Status**
- Atualiza o status na tabela `F_CON_RETURN_CARRIERS` **apenas por ADJUSTMENT_ID** (evita afetar múltiplas linhas)
- Atualiza o status nas demais tabelas principais (`F_CON_SALES_BOOKING_DATA`, `F_CON_CARGO_LOADING_CONTAINER_RELEASE`)
- Registra a confirmação no log de ajustes

#### 🔗 **Vínculo entre Tabelas**
- **Ligação principal**: Campo `FAROL_REFERENCE` para conectar as tabelas
- **Identificação específica**: `ADJUSTMENT_ID` para identificar a linha exata aprovada
- **Consistência**: Todas as atualizações são feitas em transação única
- **Precisão**: Atualizações por `ADJUSTMENT_ID` garantem que apenas a linha alterada seja afetada

### 📋 **Campos Exibidos na Grade**

| Campo | Descrição | Editável |
|-------|-----------|----------|
| **Inserted Date** | Data de inserção do registro | ❌ |
| **Farol Reference** | Referência única do embarque | ❌ |
| **Adjustment ID** | ID único do ajuste para rastreabilidade | ❌ |
| **Farol Status** | Status atual (dropdown) | ✅ |
| **Splitted Booking Reference** | Referência do booking dividido | ❌ |
| **Place of Receipt** | Local de recebimento | ❌ |
| **Quantity of Containers** | Quantidade de containers | ❌ |
| **Port of Loading POL** | Porto de carregamento | ❌ |
| **Port of Delivery POD** | Porto de destino | ❌ |
| **Final Destination** | Destino final | ❌ |
| **Transhipment Port** | Porto de transbordo | ❌ |
| **Port Terminal City** | Cidade do terminal portuário | ❌ |
| **Vessel Name** | Nome da embarcação | ❌ |
| **Voyage Carrier** | Transportador da viagem | ❌ |
| **Document Cut Off** | Data limite para documentos | ❌ |
| **Port Cut Off** | Data limite para porto | ❌ |
| **ETD** | Tempo estimado de partida | ❌ |
| **ETA** | Tempo estimado de chegada | ❌ |
| **Gate Opening** | Abertura do portão | ❌ |
| **Status** | Status do processo | ❌ |
| **PDF Name** | Nome do arquivo PDF | ❌ |
| **Inserted By** | Usuário que inseriu | ❌ |

### ⚠️ **Regras de Funcionamento**

#### 🎯 **Detecção de Mudanças**
- **Automática**: Sistema detecta alterações comparando DataFrame original vs editado
- **Precisão**: Apenas linhas com mudanças reais são processadas
- **Feedback**: Mensagens claras sobre sucesso, falha ou nenhuma mudança detectada

#### 🔒 **Proteção de Dados**
- **Campos protegidos**: Apenas o "Farol Status" pode ser alterado
- **Integridade**: Demais campos permanecem somente leitura
- **Validação UDC**: Status válidos apenas da tabela UDC

#### 📊 **Tratamento de Campos Vazios**
- **Atualização seletiva**: Apenas campos com valores não nulos são atualizados
- **Preservação de dados**: Campos vazios não sobrescrevem dados existentes
- **Feedback ao usuário**: Sistema informa quantos campos foram atualizados

### 🔧 **Funcionalidades Adicionais**

#### 📎 **Gestão de Anexos**
- **Toggle de anexos**: Botão para mostrar/ocultar seção de anexos
- **Upload/Download**: Gerenciamento completo de arquivos
- **Integração**: Mesma funcionalidade disponível em outras telas

#### 📤 **Exportação de Dados**
- **Download CSV**: Exporta dados da grade para análise externa
- **Formato padronizado**: Arquivo nomeado com a referência Farol
- **Codificação UTF-8**: Suporte completo a caracteres especiais

#### 🔙 **Navegação**
- **Botão de retorno**: Volta para a tela principal de Shipments
- **Estado persistente**: Mantém contexto da referência selecionada

### 📈 **Métricas e Indicadores**

#### 📊 **Métricas Rápidas**
- **Farol Status**: Status atual do booking
- **Voyage Carrier**: Transportador responsável
- **Quantity of Containers**: Quantidade de containers
- **Inserted Date**: Data de inserção do registro

#### 📋 **Informações de Processamento**
- **Total de registros**: Quantidade de linhas no histórico
- **Status distribuídos**: Contagem por tipo de status
- **Timeline visual**: Ordenação cronológica dos eventos

### 🎯 **Casos de Uso**

#### ✅ **Aprovação de Ajustes**
1. Usuário identifica linha com ajustes pendentes
2. Altera status diretamente na grade para "Booking Approved"
3. Sistema aplica automaticamente os dados da linha aprovada
4. Feedback imediato sobre sucesso da operação

#### 🔍 **Auditoria e Rastreabilidade**
1. Visualização completa do histórico de mudanças
2. Identificação de responsáveis por cada alteração
3. Timeline de eventos para análise de processos
4. Rastreabilidade completa via `ADJUSTMENT_ID`

#### 📊 **Análise de Performance**
1. Identificação de gargalos no processo
2. Tempo médio entre etapas
3. Distribuição de status por período
4. Análise de tendências operacionais

### 🔄 **Integração com Outras Telas**

#### 🔗 **Conexão com Shipments**
- **Navegação bidirecional**: Histórico acessível a partir de Shipments
- **Contexto compartilhado**: Mesma referência Farol em ambas as telas
- **Sincronização**: Mudanças refletem automaticamente em todas as telas

#### 🔗 **Conexão com Adjustments**
- **Complementaridade**: Histórico mostra resultado dos ajustes aprovados
- **Rastreabilidade**: `ADJUSTMENT_ID` conecta ajustes com histórico
- **Fluxo completo**: Do ajuste solicitado à aprovação e implementação

---

## 🛠️ Ajustes Críticos e Splits (Melhorias Implementadas)

### 📝 **Validações Aprimoradas**

#### ⚠️ **Mensagens de Validação**
- **Justificativas obrigatórias**: Mensagem alterada para alerta (`st.warning`) ao invés de erro
- **Campos obrigatórios**: Area, Reason e Responsibility devem ser preenchidos
- **Validação de quantidade**: Splits devem ter quantidade maior que 0

#### 🔄 **Lógica de Validação**
1. **Sempre exigir alteração**: Linha principal deve ter pelo menos uma mudança
2. **Justificativas obrigatórias**: Area, Reason e Responsibility são obrigatórios
3. **Quantidades válidas**: Splits devem ter quantidade > 0 quando aplicável

### 📊 **Novos Campos no Editor**

#### 🆕 **Campos Adicionados**
- **Transhipment Port**: Porto de transbordo (dropdown da UDC)
- **Port Terminal City**: Cidade do terminal portuário (dropdown da UDC)
- **Configuração de coluna**: "Sales Quantity of Containers" configurada como NumberColumn

### 💾 **Persistência de Dados Melhorada**

#### 🔧 **Correção na Função `insert_return_carrier_from_ui`**
- **Mapeamento duplo**: Aceita tanto "Quantity of Containers" quanto "Sales Quantity of Containers"
- **Prevenção de NULL**: Evita gravar valores nulos na quantidade
- **Conversão segura**: Converte para inteiro quando possível

#### 📈 **Fluxo de Persistência**
1. **Confirmação de ajustes**: Processa linha principal e splits
2. **Inserção de snapshot**: Cria registro em `F_CON_RETURN_CARRIERS` para cada linha
3. **Mapeamento correto**: Usa valores exatos do editor para persistência
4. **Tratamento de erros**: Não bloqueia fluxo principal se snapshot falhar

### 🎯 **Casos de Uso Atualizados**

#### ✅ **Ajuste sem Split**
1. Usuário altera campos da linha principal
2. Preenche justificativas obrigatórias
3. Sistema valida alterações e justificativas
4. Persiste ajustes e cria snapshot de retorno

#### 🔀 **Ajuste com Split**
1. Usuário define número de splits (> 0)
2. Altera campos da linha principal e dos splits
3. Define quantidades válidas para cada split
4. Sistema recalcula quantidade original automaticamente
5. Persiste todas as linhas com snapshots individuais

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

