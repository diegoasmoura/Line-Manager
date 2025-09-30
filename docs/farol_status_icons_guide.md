# Guia de Implementação: Ícones do Farol Status

## 📜 Visão Geral

Este guia explica como a funcionalidade de ícones visuais para o campo "Farol Status" foi implementada e como deve ser utilizada. O objetivo é melhorar a experiência do usuário sem comprometer a integridade dos dados no banco de dados.

A premissa fundamental é a **separação entre dados e apresentação**:
-   O **banco de dados** armazena apenas o texto puro do status (ex: `Booking Approved`).
-   A **camada de visualização (frontend)** é responsável por adicionar e remover os ícones dinamicamente (ex: `✅ Booking Approved`).

---

## ⚠️ Pontos Críticos e Soluções Implementadas

Durante a implementação, dois problemas principais foram identificados e resolvidos. Compreendê-los é crucial para a manutenção futura.

### Problema 1: `ImportError` (Funções Inexistentes)

-   **Sintoma**: Ocorria o erro `ImportError: cannot import name 'process_farol_status_for_display'`.
-   **Causa**: Este guia foi criado inicialmente como um "plano de implementação". As funções documentadas ainda não existiam no código, causando o erro de importação.
-   **Solução**: As funções (`get_farol_status_icons`, `process_farol_status_for_display`, etc.) foram implementadas no arquivo `shipments_mapping.py`, seguindo o blueprint deste documento.
-   **Prevenção**: Antes de usar uma função de um módulo, verifique se ela de fato existe no arquivo de origem para evitar erros de importação.

### Problema 2: Campo "Farol Status" em Branco na Grade

-   **Sintoma**: Após a formatação dos dados, a coluna `Farol Status` na grade editável (`st.data_editor`) aparecia em branco.
-   **Causa**: O valor nos dados (ex: `"✅ Booking Approved"`) não correspondia a nenhuma das opções no dropdown daquela coluna (que ainda continham apenas o texto puro, ex: `"Booking Approved"`).
-   **Solução**: A função `drop_downs` em `shipments_mapping.py` foi modificada para também formatar as **opções do dropdown** com ícones. Isso garante que os valores nos dados e as opções de seleção sejam idênticos.
-   **Prevenção**: Ao usar `st.column_config.SelectboxColumn`, os valores no DataFrame devem corresponder **exatamente** às strings fornecidas na lista de `options`. Se você formata os dados, deve formatar as opções da mesma maneira.

---

## 🛠️ Funções Disponíveis

Toda a lógica está centralizada em `shipments_mapping.py`.

### Funções de Mapeamento
```python
from shipments_mapping import (
    get_farol_status_icons,      # Dicionário status -> ícone
    get_display_from_status,     # Adiciona ícone a um status
    get_status_from_display,     # Remove ícone de um status (alias: clean_farol_status_value)
    get_icon_only                # Retorna apenas o ícone
)
```

### Funções de Processamento de DataFrame
```python
from shipments_mapping import (
    process_farol_status_for_display,    # Adiciona ícones ao DataFrame para exibição
    process_farol_status_for_database,   # Remove ícones do DataFrame para salvar no banco
)
```

---

## 🔄 Como a Integração Funciona

### 1. Ao Carregar Dados do Banco (`database.py`)

-   **O quê**: As funções `get_data_salesData`, `get_data_bookingData`, etc., chamam `process_farol_status_for_display` antes de retornar os dados.
-   **Por quê**: Para garantir que a interface sempre receba os dados já formatados com ícones.

```python
# Em database.py
def get_data_salesData():
    # ... lógica de busca ...
    df = process_farol_status_for_display(df)
    return df
```

### 2. Ao Configurar o Dropdown de Edição (`shipments_mapping.py`)

-   **O quê**: A função `drop_downs` usa `get_display_from_status` para formatar a lista de opções do dropdown do `Farol Status`.
-   **Por quê**: Para resolver o "Problema 2" e garantir que as opções do dropdown correspondam aos valores exibidos na grade.

```python
# Em shipments_mapping.py
"Farol Status": [get_display_from_status(s) for s in df_udc[...].tolist()],
```

### 3. Ao Salvar Dados no Banco (`shipments.py`)

-   **O quê**: Ao detectar uma edição na coluna `Farol Status`, a função `clean_farol_status_value` (alias de `get_status_from_display`) é chamada para limpar o valor novo e o antigo.
-   **Por quê**: Para garantir que nenhum ícone seja jamais enviado para o banco de dados, mantendo a integridade dos dados.

```python
# Em shipments.py
if col == "Farol Status":
    old_val = clean_farol_status_value(original_row[col])
    new_val = clean_farol_status_value(row[col])
```

---

## 🎨 Ícones e Personalização

Para alterar ou adicionar ícones, edite apenas a função `get_farol_status_icons()` no `shipments_mapping.py`. A mudança será refletida automaticamente em todo o sistema.

| Status | Ícone |
|--------|-------|
| New Request | 🆕 |
| Booking Requested | 📋 |
| Received from Carrier | 📨 |
| Booking Under Review | 🔍 |
| Adjustment Requested | ✏️ |
| Booking Approved | ✅ |
| Booking Cancelled | ❌ |
| Booking Rejected | 🚫 |