# 📋 Processo de Gerenciamento de Pedidos de Alteração de Bookings

## Visão Geral

Este documento descreve o novo processo implementado para gerenciar pedidos de alteração de bookings de forma estruturada e controlada.

## 🔄 Fluxo do Processo

### 1. Registro Inicial
- **Local**: Primeira aba - "📋 Pedidos da Empresa"
- **Ação**: Todos os pedidos de alteração feitos pela empresa são lançados nesta aba
- **Status**: Aguarda retorno do armador

### 2. Retorno do Armador
- **Local**: Segunda aba - "📨 Retornos do Armador"
- **Ação**: Armador responde com status "Received from Carrier"
- **Controle**: Sistema aguarda validação antes da aprovação

### 3. Validação e Aprovação
- **Requisito**: Antes de aprovar item "Received from Carrier" para "Booking Approved"
- **Validação**: Usuário deve informar a referência da aba relacionada
- **Controle**: Sistema valida se a referência existe na aba "Pedidos da Empresa"

## 🔗 Sistema de Controle por Referência

### Coluna Linked_Reference
- **Propósito**: Número sequencial de vínculo entre pedidos e retornos
- **Sequência**: 
  - Primeiro booking criado: `Linked_Reference = 1`
  - Cada ajuste/split relacionado: `Linked_Reference = x+1`

### Coluna ID
- **Propósito**: Identificador único para referência cruzada
- **Uso**: Permite relacionar retornos do armador com pedidos da empresa

## 🛠️ Funcionalidades Implementadas

### 1. Funções de Controle
```python
def get_next_linked_reference_number():
    """Obtém o próximo número sequencial para Linked_Reference"""

def get_available_references_for_relation():
    """Busca referências disponíveis na aba 'Other Status' para relacionamento"""
```

### 2. Validação Obrigatória
- **Trigger**: Quando item "Received from Carrier" é aprovado para "Booking Approved"
- **Interface**: Selectbox com opções da aba "Pedidos da Empresa"
- **Validação**: Verifica se ID relacionado existe na aba "Other Status"
- **Feedback**: Mensagens de sucesso/erro para o usuário

### 3. Interface de Duas Abas
- **Aba 1**: "📋 Pedidos da Empresa" - Pedidos iniciais da empresa
- **Aba 2**: "📨 Retornos do Armador" - Retornos com status "Received from Carrier"
- **Informações**: Cada aba possui explicação do seu propósito

## 📊 Colunas Visíveis

### Colunas Principais
- **ID**: Identificador único (formato numérico)
- **Farol Reference**: Referência do Farol
- **Linked Reference**: Número sequencial de vínculo (formato numérico)
- **Farol Status**: Status atual do booking
- **Inserted Date**: Data de inserção

### Colunas de Dados
- **Quantity of Containers**: Quantidade de containers
- **Port of Loading (POL)**: Porto de carregamento
- **Port of Delivery (POD)**: Porto de entrega
- **ETD/ETA**: Datas estimadas
- **Vessel Name**: Nome da embarcação
- **Voyage Code**: Código da viagem

## 🔄 Processo de Aprovação

### Fluxo Normal
1. Usuário seleciona linha na aba "Retornos do Armador"
2. Altera status para "Booking Approved"
3. Sistema solicita referência relacionada
4. Usuário seleciona ID da aba "Pedidos da Empresa"
5. Sistema valida e aprova
6. Dados são propagados para tabela principal

### Validações
- **Existência**: Verifica se ID relacionado existe
- **Status**: Confirma que item relacionado não é "Received from Carrier"
- **Integridade**: Mantém consistência entre abas

## 💾 Persistência de Dados

### Tabela F_CON_RETURN_CARRIERS
- **Linked_Reference**: Atualizado com ID relacionado
- **USER_UPDATE**: Registra usuário que fez a alteração
- **DATE_UPDATE**: Timestamp da alteração

### Tabela F_CON_SALES_BOOKING_DATA
- **Propagação**: Dados aprovados são propagados automaticamente
- **Consistência**: Mantém sincronização com dados aprovados

## 🎯 Benefícios

### 1. Controle de Qualidade
- Validação obrigatória antes da aprovação
- Rastreabilidade completa do processo
- Prevenção de aprovações incorretas

### 2. Organização
- Separação clara entre pedidos e retornos
- Numeração sequencial para controle
- Interface intuitiva e explicativa

### 3. Rastreabilidade
- Histórico completo de alterações
- Vínculo entre pedidos e retornos
- Auditoria de aprovações

## 🚀 Como Usar

### Para Pedidos da Empresa
1. Acesse a aba "📋 Pedidos da Empresa"
2. Registre novos pedidos de alteração
3. Aguarde retorno do armador

### Para Retornos do Armador
1. Acesse a aba "📨 Retornos do Armador"
2. Selecione item com status "Received from Carrier"
3. Altere status para "Booking Approved"
4. Selecione referência relacionada da aba "Pedidos da Empresa"
5. Confirme a aprovação

## ⚠️ Observações Importantes

- **Obrigatório**: Sempre informar referência relacionada para itens "Received from Carrier"
- **Validação**: Sistema impede aprovação sem referência válida
- **Sequência**: Linked_Reference é gerado automaticamente
- **Consistência**: Dados são validados antes da persistência

---

*Este processo garante controle total sobre alterações de bookings, mantendo rastreabilidade e qualidade dos dados.*
