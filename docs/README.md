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

---New request
Booking Requested

