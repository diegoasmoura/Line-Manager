# 📎 Sistema de Anexos - Adjustment Management

## Visão Geral

O sistema de anexos foi implementado na tela de **Adjustment Request Management** (`booking_adjustments.py`) permitindo que usuários façam upload, visualizem e gerenciem arquivos relacionados a cada **Farol Reference**.

## 🚀 Funcionalidades Implementadas

### ✅ Upload de Arquivos
- **Upload múltiplo**: Permite selecionar e enviar vários arquivos simultaneamente
- **Tipos suportados**: PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX, TXT, CSV, PNG, JPG, JPEG, GIF, ZIP, RAR
- **Validação automática**: Verificação de tipo de arquivo e tamanho
- **Progress bar**: Indicador visual do progresso do upload
- **Confirmação visual**: Efeito de balões quando upload é concluído com sucesso

### 📋 Exibição de Anexos
- **Cards visuais**: Cada anexo é exibido em um card estilizado com:
  - Ícone específico por tipo de arquivo (📕 PDF, 📊 Excel, 🖼️ Imagem, etc.)
  - Nome do arquivo (truncado se muito longo)
  - Tamanho do arquivo formatado (B, KB, MB, GB)
  - Usuário que fez o upload
  - Data e hora do upload
  - Botões de ação (Ver/Baixar, Info)

### 🎯 Funcionalidades de Visualização
- **Prévia de imagens**: Imagens podem ser visualizadas diretamente na tela
- **Download direto**: Outros tipos de arquivo podem ser baixados
- **Informações detalhadas**: Modal com informações completas do arquivo
- **Estatísticas**: Resumo com total de anexos, tamanho total e tipos de arquivo

### 🗄️ Integração com Banco de Dados
- **Tabela F_CON_ANEXOS**: Armazenamento seguro na base Oracle
- **Indexação**: Índices otimizados para consultas por Farol Reference e data
- **Transações seguras**: Operações com commit/rollback automático

## 📊 Estrutura da Tabela F_CON_ANEXOS

**Estrutura Real da Tabela (baseada na verificação MCP):**

```sql
CREATE TABLE LogTransp.F_CON_ANEXOS (
    id NUMBER PRIMARY KEY,                 -- ID numérico sequencial (chave primária)
    attachment_id VARCHAR2(100) NOT NULL,  -- UUID único do anexo
    farol_reference VARCHAR2(100) NOT NULL, -- Referência do Farol
    file_name VARCHAR2(500) NOT NULL,      -- Nome original do arquivo
    file_content BLOB NOT NULL,            -- Conteúdo binário do arquivo
    file_size NUMBER NOT NULL,             -- Tamanho em bytes
    file_type VARCHAR2(200),               -- Tipo MIME do arquivo
    upload_date DATE,                      -- Data/hora do upload
    uploaded_by VARCHAR2(200),             -- Usuário que fez upload
    is_active VARCHAR2(1) DEFAULT 'Y'      -- Flag ativo/inativo (Y/N)
);
```

### Colunas Detalhadas:
- **ID**: Chave primária numérica (NUMBER) - gerada automaticamente
- **ATTACHMENT_ID**: UUID único (VARCHAR2) - usado para operações de arquivo
- **FAROL_REFERENCE**: Referência do Farol (VARCHAR2) - chave de associação
- **FILE_NAME**: Nome original do arquivo (VARCHAR2, até 500 caracteres)
- **FILE_CONTENT**: Conteúdo binário (BLOB) - armazena o arquivo
- **FILE_SIZE**: Tamanho em bytes (NUMBER)
- **FILE_TYPE**: Tipo MIME (VARCHAR2) - ex: 'application/pdf', 'image/jpeg'
- **UPLOAD_DATE**: Data/hora do upload (DATE)
- **UPLOADED_BY**: Usuário que fez upload (VARCHAR2)
- **IS_ACTIVE**: Flag de ativo (VARCHAR2) - 'Y' ou 'N'

## 🛠️ Como Usar

### 1. Configuração Inicial

Execute o script de teste para verificar/criar a tabela:
```bash
python test_attachments_table.py
```

### 2. Acesso às Funcionalidades

Na tela de **Adjustment Request Management**:

1. **Ver Anexos**: Clique no botão "📎 Ver Anexos"
2. **Selecionar Farol Reference**: Use o dropdown para escolher a referência
3. **Upload**: 
   - Expand "📤 Adicionar Novo Anexo"
   - Arraste arquivos ou clique para selecionar
   - Clique "💾 Salvar Anexos"
4. **Visualizar**: Use os cards de anexos para ver/baixar/obter informações

### 3. Cenários de Uso

- **Com ajustes ativos**: Botão "📎 Ver Anexos" aparece junto com outras ações
- **Sem dados ajustados**: Botão disponível para gerenciar anexos de referências existentes  
- **Sem ajustes encontrados**: Permite input manual de Farol Reference via "📎 Adicionar Anexos"

## 🎨 Interface Visual

### Cards de Anexos
- **Hover effects**: Cards se elevam ao passar o mouse
- **Gradientes**: Fundo com gradiente sutil
- **Ícones contextuais**: Diferentes ícones por tipo de arquivo
- **Informações organizadas**: Layout limpo com informações bem estruturadas

### Seção de Upload
- **Área delimitada**: Área visual clara para drop de arquivos
- **Feedback imediato**: Lista de arquivos selecionados com tamanhos
- **Progress tracking**: Barra de progresso durante upload
- **Confirmação visual**: Efeitos visuais de sucesso

### Métricas e Estatísticas
- **Cards de métricas**: Total de anexos, tamanho total, tipos únicos
- **Integração com design**: Uso do mesmo padrão visual das métricas existentes

## 📝 Logs e Debugging

### Mensagens de Erro
- **Conexão**: Problemas de conectividade com banco
- **Upload**: Falhas durante o processo de upload
- **Permissões**: Problemas de acesso à tabela
- **Tamanho**: Arquivos muito grandes (limitação do banco)

### Informações de Debug
- **IDs de anexo**: Mostrados truncados (primeiros 8 caracteres)
- **Timestamps**: Formatação em português (dd/mm/yyyy HH:MM)
- **Tipos MIME**: Detecção automática baseada na extensão

## 🔧 Configurações Ajustáveis

### Tipos de Arquivo Suportados
No `st.file_uploader`, modifique o parâmetro `type`:
```python
type=['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'csv', 'png', 'jpg', 'jpeg', 'gif', 'zip', 'rar']
```

### Ícones de Arquivo
Na função `get_file_icon()`, customize os ícones por tipo MIME:
```python
if mime_type.startswith('image/'):
    return "🖼️"
elif mime_type in ['application/pdf']:
    return "📕"
# ... mais tipos
```

### Layout de Cards
Modifique o CSS customizado na função `exibir_adjustments()`:
```css
.attachment-card {
    border-radius: 10px;
    padding: 20px;
    /* ... outros estilos */
}
```

## ⚠️ Limitações e Considerações

### Tamanho de Arquivos
- **BLOB Oracle**: Limitação do tipo BLOB (até 4GB teoricamente)
- **Streamlit**: Limitação de upload do Streamlit (32MB por padrão)
- **Memória**: Arquivos grandes podem consumir muita memória

### Performance
- **Consultas**: Indexação otimizada para consultas por Farol Reference
- **Upload múltiplo**: Cada arquivo é processado individualmente
- **Transações**: Uma transação por arquivo para segurança

### Segurança
- **Validação de tipo**: Baseada em extensão e MIME type
- **Sanitização**: Nomes de arquivo são mantidos como fornecidos
- **Acesso**: Sem controle de permissão por usuário implementado

## 🆕 Futuras Melhorias Sugeridas

1. **Controle de Permissões**: Implementar controle de acesso por usuário/role
2. **Versionamento**: Permitir múltiplas versões do mesmo arquivo
3. **Preview Avançado**: Preview para PDFs, documentos Office
4. **Busca**: Funcionalidade de busca por nome de arquivo ou conteúdo
5. **Organização**: Pastas/categorias para melhor organização
6. **Notificações**: Alertas quando novos anexos são adicionados
7. **Auditoria**: Log detalhado de todas as operações com anexos

## 📞 Suporte

Para problemas ou dúvidas:

1. **Verifique a tabela**: Execute `test_attachments_table.py`
2. **Logs de erro**: Observe mensagens no Streamlit
3. **Permissões**: Verifique permissões do usuário Oracle
4. **Estrutura**: Compare com a estrutura SQL documentada acima

---

**Desenvolvido com ❤️ usando Streamlit + Oracle Database** 