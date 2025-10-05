# 🔍 Instruções para Teste de VPN vs API Ellox

## 📋 Arquivos Criados

Criei 4 arquivos de teste para diagnosticar o problema de conectividade com a VPN:

1. **`test_vpn_ellox.py`** - Teste completo e detalhado (RECOMENDADO)
2. **`quick_vpn_test.py`** - Teste rápido e simples
3. **`test_ellox_vpn.py`** - Teste intermediário
4. **`test_vpn_connectivity.py`** - Teste avançado com múltiplas configurações

## 🚀 Como Usar

### Passo 1: Configure suas credenciais
Edite qualquer um dos arquivos e substitua:
```python
"email": "seu_email@exemplo.com",  # SUBSTITUA
"senha": "sua_senha"              # SUBSTITUA
```

### Passo 2: Execute o teste
```bash
# Teste recomendado (mais completo)
python test_vpn_ellox.py

# Ou teste rápido
python quick_vpn_test.py
```

### Passo 3: Analise os resultados
O script mostrará:
- ✅ **Sucesso**: API funcionando com VPN
- ❌ **Falha**: Problema identificado com sugestões

## 🔍 O que o Teste Verifica

### 1. Resolução DNS
- Consegue resolver `apidtz.comexia.digital`?
- VPN pode estar bloqueando DNS

### 2. Conectividade de Porta
- Consegue conectar na porta 443 (HTTPS)?
- Firewall/VPN pode estar bloqueando

### 3. Requisição HTTPS
- Consegue fazer requisição HTTP básica?
- Proxy pode estar interferindo

### 4. Autenticação API
- Consegue autenticar na API Ellox?
- Credenciais podem estar incorretas

## 🎯 Cenários de Problema

### Cenário 1: DNS não resolve
```
❌ DNS FALHOU: [Errno 11001] getaddrinfo failed
```
**Solução**: Verificar configurações de DNS da VPN

### Cenário 2: Porta bloqueada
```
❌ Porta 443 inacessível (código: 10060)
```
**Solução**: Verificar firewall/VPN permite HTTPS

### Cenário 3: Timeout
```
⏰ TIMEOUT - API não respondeu em 15s
```
**Solução**: VPN muito lenta ou bloqueando

### Cenário 4: Erro de conexão
```
🔌 ERRO DE CONEXÃO: HTTPSConnectionPool...
```
**Solução**: VPN não permite acesso à API

## 🛠️ Soluções Comuns

### 1. Configurar Proxy
Se a empresa usa proxy, configure:
```python
proxies = {
    "http": "http://proxy:8080",
    "https": "https://proxy:8080"
}
```

### 2. Desabilitar Verificação SSL
```python
verify=False  # Já incluído nos testes
```

### 3. Aumentar Timeout
```python
timeout=30  # Aumentar tempo de espera
```

### 4. Configurar DNS
- Usar DNS público (8.8.8.8, 1.1.1.1)
- Verificar configurações de VPN

## 📊 Interpretando Resultados

### ✅ Tudo Funcionando
```
✅ DNS OK: apidtz.comexia.digital → 123.456.789.0
✅ Porta 443 acessível
✅ Conectou em 1500ms - Status: 200
🎉 AUTENTICAÇÃO BEM-SUCEDIDA!
```
**Conclusão**: API funcionando, problema na aplicação principal

### ❌ Problema de VPN
```
❌ DNS FALHOU: [Errno 11001] getaddrinfo failed
```
**Conclusão**: VPN bloqueando DNS, contatar TI

### ⏰ Timeout
```
⏰ TIMEOUT - API não respondeu em 15s
```
**Conclusão**: VPN lenta ou bloqueando, tentar timeout maior

## 🔧 Próximos Passos

### Se API funcionar:
1. ✅ Verificar configuração da aplicação principal
2. 🔧 Testar com as mesmas configurações
3. 📝 Usar timeout e proxy que funcionaram

### Se API não funcionar:
1. 📞 Contatar TI da empresa
2. 🔄 Tentar desligar VPN temporariamente
3. 🌐 Configurar proxy corporativo
4. 🔧 Ajustar configurações de DNS

## 📞 Suporte

Se precisar de ajuda:
1. Execute o teste e salve o resultado
2. Envie o log completo
3. Informe qual VPN está usando
4. Mencione se funciona sem VPN

## ⚠️ Importante

- **Configure suas credenciais** antes de executar
- **Execute com VPN ligada** para testar o problema
- **Salve os resultados** para análise
- **Teste também sem VPN** para comparar

---

**Criado para diagnosticar problemas de conectividade VPN vs API Ellox**
