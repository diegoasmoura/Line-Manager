# 🔧 Changelog - Correção de Persistência de Alterações no Shipments

**Data**: Janeiro 2025  
**Versão**: v3.9.9  
**Tipo**: Bug Fix / Enhancement  

## 📋 Resumo

Correção crítica que resolve o problema de persistência de alterações feitas na interface do `shipments.py`. O sistema estava registrando corretamente as mudanças na tabela de auditoria `F_CON_CHANGE_LOG`, mas não estava aplicando as alterações na tabela principal `F_CON_SALES_BOOKING_DATA`.

## 🐛 Problema Identificado

### Sintomas
- Usuários editavam dados na interface do shipments.py
- Sistema mostrava "Changes successfully registered in the database!"
- **MAS** as alterações não eram persistidas na tabela principal
- Erro `ORA-00904: invalid identifier` ao tentar fazer UPDATE

### Causa Raiz
1. **Falta de persistência**: Código apenas auditava, não executava UPDATE
2. **Mapeamento incorreto**: Aliases SQL com prefixos diferentes (`s_`, `b_`) mapeavam para a mesma coluna física
3. **Colisão de nomes**: `"Port of Loading POL"` podia mapear para `B_PORT_OF_LOADING_POL` (inexistente) em vez de `S_PORT_OF_LOADING_POL`

## ✅ Solução Implementada

### 1. Função de Persistência (`database.py`)

```python
def update_field_in_sales_booking_data(conn, farol_reference: str, column_name: str, new_value):
    """
    Atualiza um campo específico na tabela F_CON_SALES_BOOKING_DATA.
    
    Args:
        conn: Conexão com o banco de dados
        farol_reference: Referência Farol do registro
        column_name: Nome técnico da coluna no banco (em UPPER CASE)
        new_value: Novo valor a ser atualizado
    """
    update_sql = text(f"""
        UPDATE LogTransp.F_CON_SALES_BOOKING_DATA
        SET {column_name} = :new_value
        WHERE FAROL_REFERENCE = :farol_reference
    """)
    conn.execute(update_sql, {
        "new_value": new_value,
        "farol_reference": farol_reference
    })
```

### 2. Mapeamento de Aliases SQL (`shipments_mapping.py`)

```python
def get_alias_to_database_column_mapping():
    """
    Mapeamento explícito de aliases SQL para colunas do banco de dados.
    Resolve colisões entre prefixos s_ e b_ que apontam para a mesma coluna física.
    """
    return {
        # Aliases normais
        "s_port_of_loading_pol": "S_PORT_OF_LOADING_POL",
        
        # ⚠️ IMPORTANTE: Aliases com prefixo b_ que na verdade apontam para colunas S_*
        "b_port_of_loading_pol": "S_PORT_OF_LOADING_POL",  # ← Resolve o problema!
        "b_port_of_delivery_pod": "S_PORT_OF_DELIVERY_POD",
        ...
    }

def get_database_column_name(display_name_or_alias: str) -> str:
    """
    Converte nome amigável OU alias SQL para nome real da coluna do banco.
    
    Estratégia em camadas:
    1. Tenta como alias SQL (mais preciso)
    2. Tenta como nome amigável via reverse_mapping
    3. Casos especiais (Farol Status, etc.)
    4. Fallback inteligente
    """
```

### 3. Lógica de Confirmação Corrigida (`shipments.py`)

```python
for _, row in st.session_state["changes"].iterrows():
    # Converter nome da coluna para nome técnico do banco de dados
    db_column_name = get_database_column_name(column)
    
    # Processar tipos de dados especiais
    if column == "Farol Status" or db_column_name == "FAROL_STATUS":
        new_value = process_farol_status_for_database(new_value)
    
    # Converter pandas.Timestamp para datetime nativo
    if hasattr(new_value, 'to_pydatetime'):
        new_value = new_value.to_pydatetime()
    
    # 1. Auditar a mudança (usa nome técnico)
    audit_change(conn, farol_ref, 'F_CON_SALES_BOOKING_DATA', 
                db_column_name, old_value, new_value, 
                'shipments', 'UPDATE', adjustment_id=random_uuid)
    
    # 2. Persistir a mudança na tabela principal (usa nome técnico)
    update_field_in_sales_booking_data(conn, farol_ref, db_column_name, new_value)
```

## 📊 Resultados

### ✅ Problemas Resolvidos

1. **Persistência**: Alterações agora são salvas em `F_CON_SALES_BOOKING_DATA`
2. **Mapeamento**: Aliases SQL convertidos corretamente para nomes do banco
3. **Compatibilidade**: Funciona em todos os stages (Sales Data, Booking Management, General View)
4. **Tipos de dados**: Conversões adequadas para datas, Farol Status, etc.

### 📈 Exemplos de Mapeamento

| Stage | Usuário Edita | Alias no DF | Nome Real no Banco | Resultado |
|-------|--------------|-------------|-------------------|-----------|
| Booking Management | "Port of Loading POL" | `b_port_of_loading_pol` | `S_PORT_OF_LOADING_POL` | ✅ UPDATE correto! |
| Sales Data | "Port of Loading POL" | `s_port_of_loading_pol` | `S_PORT_OF_LOADING_POL` | ✅ UPDATE correto! |
| General View | "Port of Loading POL" | `s_port_of_loading_pol` | `S_PORT_OF_LOADING_POL` | ✅ UPDATE correto! |

### 🎯 Campos Especiais Resolvidos

```python
# Estes aliases com prefixo b_ na verdade apontam para colunas S_*:
"b_port_of_loading_pol" → "S_PORT_OF_LOADING_POL"
"b_port_of_delivery_pod" → "S_PORT_OF_DELIVERY_POD"
"b_place_of_receipt" → "S_PLACE_OF_RECEIPT"
"b_final_destination" → "S_FINAL_DESTINATION"
```

## 🔧 Arquivos Modificados

- **`database.py`**: Função helper `update_field_in_sales_booking_data()` (linha 120)
- **`shipments.py`**: Lógica de confirmação corrigida (linhas 652-683)
- **`shipments_mapping.py`**: Mapeamento de aliases SQL → colunas do banco (linhas 406-542)

## 🧪 Testes Realizados

- ✅ Edição de campos numéricos (Quantity of Containers)
- ✅ Edição de campos de texto (Port of Loading POL, Port of Delivery POD)
- ✅ Edição de campos de data (Requested Shipment Week)
- ✅ Edição de Farol Status (com limpeza de ícones)
- ✅ Teste em todos os stages (Sales Data, Booking Management, General View)
- ✅ Verificação de auditoria em `F_CON_CHANGE_LOG`
- ✅ Verificação de persistência em `F_CON_SALES_BOOKING_DATA`

## 📝 Notas Técnicas

### Tratamento de Tipos de Dados
- **Farol Status**: Limpa ícones antes de salvar via `process_farol_status_for_database()`
- **Datas**: Converte `pandas.Timestamp` para `datetime` nativo
- **Colunas específicas**: Converte para `date` quando necessário
- **Transação**: Mantém atomicidade (tudo ou nada)

### Estratégia de Mapeamento
1. **Primeiro**: Tenta como alias SQL (mais preciso)
2. **Segundo**: Tenta como nome amigável via reverse_mapping
3. **Terceiro**: Casos especiais (Farol Status, etc.)
4. **Fallback**: Conversão inteligente para UPPER CASE

## 🚀 Impacto

- **Usuários**: Agora podem editar dados com confiança de que as alterações serão salvas
- **Sistema**: Persistência robusta e confiável em todos os campos editáveis
- **Auditoria**: Mantida integridade do sistema de auditoria existente
- **Performance**: Sem impacto negativo, apenas adiciona UPDATEs necessários

## ✅ Status

**IMPLEMENTADO E FUNCIONANDO** - O sistema agora persiste corretamente todas as alterações feitas na interface do shipments.py!
