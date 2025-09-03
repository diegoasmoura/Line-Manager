# 🔄 Processo de Aprovação em Duas Etapas - Retornos do Armador

## 📋 **Visão Geral**

Implementei um processo estruturado de aprovação em duas etapas para gerenciar o fluxo entre pedidos da empresa e retornos do armador, conforme solicitado.

## 🎯 **Estrutura do Processo**

### **Aba 1: 📋 Pedidos da Empresa**
- **Conteúdo**: Registros com status diferente de "Received from Carrier"
- **Função**: Armazena os pedidos de alteração realizados pela empresa
- **Processo**: Após o registro, aguarda o retorno do armador

### **Aba 2: 📨 Retornos do Armador**
- **Conteúdo**: Registros com status "Received from Carrier"
- **Função**: Armazena os retornos recebidos do armador
- **Processo**: Requer aprovação com referência relacionada

## 🔄 **Fluxo de Aprovação**

### **Etapa 1: Registro do Pedido**
1. Empresa registra pedido de alteração
2. Status inicial: "Adjustment Requested" ou similar
3. Registro fica na aba "Pedidos da Empresa"

### **Etapa 2: Retorno do Armador**
1. Armador retorna com informações
2. Status atualizado para "Received from Carrier"
3. Registro move para aba "Retornos do Armador"

### **Etapa 3: Aprovação com Relacionamento**
1. Usuário seleciona item "Received from Carrier"
2. Altera status para "Booking Approved"
3. **Sistema solicita ID relacionado**:
   - Dropdown com IDs das linhas da aba "Pedidos da Empresa"
   - Formato: "ID: [número] | [Farol Reference] | [Status]"
   - Validação automática da existência do ID
   - Campo obrigatório para prosseguir

### **Etapa 4: Validação e Aprovação**
1. Sistema valida se o ID relacionado existe na aba "Pedidos da Empresa"
2. Se válido: atualiza campo `Linked_Reference` com o ID selecionado
3. Se inválido: exibe erro e impede a aprovação
4. Atualiza tabelas principais com os dados aprovados

## 🛠️ **Implementações Técnicas**

### **Funções Adicionadas**

#### `get_available_references_for_relation()`
```python
def get_available_references_for_relation():
    """Busca linhas disponíveis na aba 'Other Status' para relacionamento"""
    # Busca ID, FAROL_REFERENCE, B_BOOKING_STATUS, ROW_INSERTED_DATE
    # Filtra linhas que NÃO são "Received from Carrier"
    # Retorna lista de dicionários com dados completos
```

#### `apply_status_change()` - Modificada
```python
def apply_status_change(farol_ref, adjustment_id, new_status, selected_row_status=None, related_reference=None):
    # Nova lógica para "Received from Carrier" + "Booking Approved"
    if selected_row_status == "Received from Carrier" and related_reference:
        # Valida ID relacionado na aba "Pedidos da Empresa"
        # Atualiza campo Linked_Reference com o ID selecionado
        # Prossegue apenas se válido
```

### **Interface de Usuário**

#### **Seleção de ID Relacionado**
- **Dropdown inteligente**: Lista IDs das linhas da aba "Pedidos da Empresa"
- **Formato claro**: "ID: [número] | [Farol Reference] | [Status]"
- **Validação em tempo real**: Botão "Confirmar" só fica habilitado com ID válido
- **Fallback**: Campo de texto manual para inserir ID diretamente

#### **Mensagens Informativas**
- **Aba "Pedidos da Empresa"**: "Esta aba contém os pedidos de alteração realizados pela empresa. Após o registro, aguarde o retorno do armador."
- **Aba "Retornos do Armador"**: "Esta aba contém os retornos do armador com status 'Received from Carrier'. Para aprovar, será necessário informar a referência relacionada da aba 'Pedidos da Empresa'."

## ✅ **Validações Implementadas**

### **Validação de ID Relacionado**
```sql
SELECT COUNT(*) FROM LogTransp.F_CON_RETURN_CARRIERS 
WHERE ID = :related_id 
AND B_BOOKING_STATUS != 'Received from Carrier'
```

### **Atualização do Linked_Reference**
```sql
UPDATE LogTransp.F_CON_RETURN_CARRIERS
SET Linked_Reference = :linked_ref,
    USER_UPDATE = :user_update,
    DATE_UPDATE = SYSDATE
WHERE ADJUSTMENT_ID = :adjustment_id
```

### **Validação de Interface**
- Campo obrigatório quando status é "Received from Carrier" → "Booking Approved"
- Botão "Confirmar" desabilitado até ID válido ser informado
- Mensagens de erro claras para IDs inválidos
- Exibição da coluna ID em ambas as abas para referência

## 🎯 **Benefícios do Processo**

### **Rastreabilidade Completa**
- Cada retorno do armador é vinculado ao pedido original da empresa via campo `Linked_Reference`
- Histórico completo do fluxo de aprovação com IDs únicos
- Auditoria facilitada com referências numéricas precisas

### **Controle de Qualidade**
- Impede aprovações sem relacionamento adequado
- Validação automática de IDs
- Interface intuitiva e guiada com dropdown formatado

### **Flexibilidade**
- Suporte a IDs manuais quando necessário
- Fallback para casos especiais
- Processo adaptável a diferentes cenários
- Exibição clara dos IDs em ambas as abas

## 🧪 **Como Testar**

### **Cenário 1: Fluxo Normal**
1. Crie um pedido na aba "Pedidos da Empresa" (anote o ID)
2. Simule retorno do armador (status "Received from Carrier")
3. Tente aprovar o retorno
4. Verifique se o sistema solicita ID relacionado
5. Selecione o ID correto no dropdown e confirme
6. Verifique se o campo `Linked_Reference` foi atualizado

### **Cenário 2: ID Inválido**
1. Tente aprovar um retorno com ID inexistente
2. Verifique se o sistema impede a aprovação
3. Confirme se a mensagem de erro é exibida

### **Cenário 3: Sem IDs Disponíveis**
1. Em um ambiente sem pedidos da empresa
2. Tente aprovar um retorno
3. Verifique se o campo de texto manual aparece
4. Teste com ID manual válido

## 📝 **Próximos Passos**

1. **Teste em ambiente de desenvolvimento**
2. **Validação com dados reais**
3. **Ajustes baseados no feedback**
4. **Documentação para usuários finais**

---

**Status**: ✅ Implementado e Pronto para Teste
**Arquivos Modificados**: `history.py`
**Data**: $(date)
