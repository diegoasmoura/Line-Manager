# 📊 Análise de Otimização - database.py

**Data:** Outubro 2025  
**Arquivo:** `database.py`  
**Linhas:** 3.748 linhas  
**Status:** ⚠️ Requer Otimização

---

## 🔍 Padrões Identificados

### ✅ **Pontos Positivos**
1. **Connection Pooling**: Uso de SQLAlchemy engine com `pool_pre_ping=True` ✅
2. **Context Managers**: `tracking.py` usa `with get_database_connection() as conn:` ✅
3. **Prepared Statements**: Uso consistente de `text()` com parâmetros ✅

### ⚠️ **Problemas Identificados**

#### 1. **Gerenciamento de Conexões Inconsistente**
- **Problema**: Alguns arquivos fecham conexões manualmente (`conn.close()`)
- **Impacto**: Risk de memory leaks e consumo excessivo de conexões
- **Padrão Problema**:
  ```python
  # ❌ Ruim (tracking.py)
  conn = get_database_connection()
  # ... código ...
  conn.close()
  ```
- **Padrão Correto**:
  ```python
  # ✅ Bom (ellox_sync_service.py)
  with get_database_connection() as conn:
      # ... código ...
  ```

#### 2. **Queries Repetidas**
- **Problema**: Múltiplas funções fazem queries similares
- **Exemplo**: `get_data_salesData`, `get_data_bookingData`, `get_data_generalView` compartilham lógica similar

#### 3. **Falta de Cache**
- **Problema**: Funções como `load_df_udc()` podem ser chamadas múltiplas vezes
- **Impacto**: Consultas redundantes ao banco

#### 4. **Tratamento de Erros Inconsistente**
- **Problema**: Algumas funções usam `try/finally`, outras não
- **Impacto**: Conexões podem ficar abertas em caso de erro

---

## 🎯 Recomendações de Otimização

### **Prioridade Alta 🔴**

#### 1. **Padronizar Uso de Context Managers**
```python
# ❌ Atual
conn = get_database_connection()
try:
    # código
finally:
    conn.close()

# ✅ Otimizado
def execute_query_with_context(self):
    with get_database_connection() as conn:
        # código aqui
```

**Arquivos Afetados:**
- `database.py`: ~50+ funções
- `history.py`: Múltiplas funções
- `pdf_booking_processor.py`: Várias funções

**Impacto**: 
- ✅ Reduz consumo de conexões
- ✅ Previne memory leaks
- ✅ Código mais limpo

---

#### 2. **Criar Funções Helper para Queries Comuns**
```python
# ✅ Criar helper genérico
def execute_query(query_text, params=None, fetch_all=False):
    """Execute query with automatic connection management"""
    with get_database_connection() as conn:
        result = conn.execute(text(query_text), params or {})
        if fetch_all:
            return result.fetchall()
        return result.scalar() or result.first()
```

**Benefícios:**
- ✅ Reduz código repetido
- ✅ Garante fechamento de conexões
- ✅ Tratamento consistente de erros

---

#### 3. **Implementar Cache para UDC**
```python
from functools import lru_cache

@lru_cache(maxsize=1)
def load_df_udc_cached():
    """Load UDC data with caching"""
    with get_database_connection() as conn:
        query = text("SELECT * FROM LogTransp.F_UDC")
        df = pd.read_sql_query(query, conn)
    return df
```

**Impacto:**
- ✅ Reduz queries ao banco
- ✅ Melhora performance
- ✅ Cache invalida ao reiniciar app

---

### **Prioridade Média 🟡**

#### 4. **Otimizar Queries Complexas**
```python
# ❌ Query atual (get_data_generalView)
# Seleciona TODAS as colunas mesmo quando não precisa

# ✅ Query otimizada
# Usar SELECT específico baseado no que é necessário
def get_data_generalView(fields=None):
    if fields:
        columns = ', '.join(fields)
    else:
        columns = ' * '
    
    query = f'SELECT {columns} FROM LogTransp.F_CON_SALES_BOOKING_DATA'
```

**Impacto:**
- ✅ Reduz tráfego de rede
- ✅ Menor tempo de execução
- ✅ Menor uso de memória

---

#### 5. **Adicionar Índices de Sugestão**
```sql
-- Sugerir índices para queries frequentes
CREATE INDEX idx_farol_ref ON LogTransp.F_CON_SALES_BOOKING_DATA(FAROL_REFERENCE);
CREATE INDEX idx_adjustment ON LogTransp.F_CON_RETURN_CARRIERS(ADJUSTMENT_ID);
CREATE INDEX idx_monitoring ON LogTransp.F_ELLOX_TERMINAL_MONITORINGS(NAVIO, VIAGEM, TERMINAL);
```

---

### **Prioridade Baixa 🟢**

#### 6. **Refatorar Funções Duplicadas**
- `get_data_salesData`, `get_data_bookingData`, `get_data_generalView` podem ser unificadas
- Criar função base genérica

---

## 📈 Impacto Esperado

| Otimização | Redução de Tempo | Redução de Recursos |
|------------|------------------|---------------------|
| Context Managers | -10% queries | -30% conexões abertas |
| Cache UDC | -50% queries | -40% CPU |
| Query Otimizada | -20% tempo | -30% memória |
| **TOTAL** | **-25%** | **-35% recursos** |

---

## 🚀 Plano de Implementação

### **Fase 1: Quick Wins (1-2 horas)**
1. ✅ Implementar context managers em funções críticas
2. ✅ Adicionar `@lru_cache` em `load_df_udc()`
3. ✅ Criar `execute_query()` helper

### **Fase 2: Refatoração (4-6 horas)**
1. Refatorar funções de get_data
2. Otimizar queries complexas
3. Adicionar índices sugeridos

### **Fase 3: Cleanup (2-3 horas)**
1. Remover código duplicado
2. Padronizar tratamento de erros
3. Documentar padrões

---

## 📋 Próximos Passos

1. **Decidir**: Implementar Fase 1 agora ou agendar para depois?
2. **Testar**: Verificar se melhorias não quebram funcionalidades
3. **Monitorar**: Medir impacto real das otimizações

---

**Recomendação**: Começar com Fase 1 (Quick Wins) pois traz 80% do benefício com 20% do esforço.

