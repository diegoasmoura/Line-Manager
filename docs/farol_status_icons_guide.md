# Guia de Implementação: Ícones do Farol Status

## Visão Geral

Este guia explica como usar os ícones visuais do campo "Farol Status" implementados no `shipments_mapping.py`. Os ícones são exibidos apenas no frontend e não são armazenados no banco de dados.

## Ícones Disponíveis

| Status | Ícone | Descrição |
|--------|-------|-----------|
| New request | 🆕 | Nova solicitação |
| Booking Requested | 📋 | Reserva solicitada |
| Received from Carrier | 📨 | Recebido do transportador |
| Booking Under Review | 🔍 | Reserva sob análise |
| Adjustment Requested | ⚠️ | Ajuste solicitado |
| Booking Approved | ✅ | Reserva aprovada |
| Booking Cancelled | ❌ | Reserva cancelada |
| Booking Rejected | 🚫 | Reserva rejeitada |

## Funções Disponíveis

### Funções de Mapeamento
```python
from shipments_mapping import (
    get_farol_status_icons,          # Dicionário status -> ícone
    get_farol_status_with_icons,     # Lista com status formatados para dropdown
    get_display_from_status,         # Adiciona ícone a um status
    get_status_from_display,         # Remove ícone de um status
    get_icon_only                    # Retorna apenas o ícone
)
```

### Funções de Processamento de DataFrame
```python
from shipments_mapping import (
    process_farol_status_for_display,    # Adiciona ícones após carregar do banco
    process_farol_status_for_database,   # Remove ícones antes de salvar no banco
    clean_farol_status_value             # Limpa valor individual
)
```

## Como Integrar no Seu Código

### 1. Ao Carregar Dados do Banco (Ex: database.py)

```python
def get_data_salesData():
    # Sua lógica atual de carregamento
    df = pd.read_sql_query(query, connection)
    
    # Adicione esta linha para mostrar ícones
    df = process_farol_status_for_display(df)
    
    return df
```

### 2. Ao Salvar Dados no Banco (Ex: shipments.py)

```python
# Antes de salvar as alterações
def save_changes_to_database(changes_df):
    # Remove ícones antes de salvar
    clean_df = process_farol_status_for_database(changes_df.copy())
    
    # Sua lógica de salvamento
    for index, row in clean_df.iterrows():
        # Processa cada mudança...
```

### 3. Ao Processar Valores Individuais

```python
# Ao registrar mudanças individuais
new_value = clean_farol_status_value(edited_value)
old_value = clean_farol_status_value(original_value)

# Agora new_value e old_value estão limpos para salvar no banco
```

### 4. Para Exibir Apenas o Ícone

```python
# Em métricas ou indicadores visuais
status = "Booking Approved"
icon = get_icon_only(status)  # Retorna "✅"

st.metric("Status Atual", f"{icon} {status}")
```

## Exemplo Prático de Integração

### No arquivo shipments.py, método de detectar mudanças:

```python
# Linha ~195 do shipments.py (aproximadamente)
for col in edited_df_clean.columns:
    if pd.isna(original_row[col]) and pd.isna(row[col]):
        continue
    if original_row[col] != row[col]:
        # Se for Farol Status, limpe os valores antes de registrar
        if col == "Farol Status":
            old_val = clean_farol_status_value(original_row[col])
            new_val = clean_farol_status_value(row[col])
        else:
            old_val = original_row[col]
            new_val = row[col]
            
        changes.append({
            'Farol Reference': row.get(farol_ref_col, index),
            "Coluna": col,
            "Valor Anterior": old_val,
            "Valor Novo": new_val,
        })
```

## Vantagens desta Implementação

1. **Simples**: Usa emojis nativos, sem dependências externas
2. **Performático**: Não requer carregamento de imagens
3. **Compatível**: Funciona em qualquer browser moderno
4. **Limpo**: Ícones não "poluem" o banco de dados
5. **Flexível**: Fácil de alterar ícones sem afetar dados existentes

## Personalizações Futuras

Para alterar ícones, edite apenas a função `get_farol_status_icons()` no `shipments_mapping.py`:

```python
def get_farol_status_icons():
    return {
        "New request": "🔵",  # Mudou de 🆕 para 🔵
        # ... outros status
    }
```

A alteração será refletida automaticamente em todo o sistema. 