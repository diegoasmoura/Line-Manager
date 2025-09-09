#!/usr/bin/env python3
"""
Teste dos endpoints de monitoramento da API Ellox
================================================
"""

from ellox_api import get_default_api_client

def test_monitoring_endpoints():
    """Testa os endpoints de monitoramento"""
    
    print("🔔 TESTANDO ENDPOINTS DE MONITORAMENTO")
    print("=" * 45)
    
    try:
        client = get_default_api_client()
        
        if not client.authenticated:
            print("❌ Cliente não autenticado")
            return
        
        print("✅ Cliente autenticado")
        print()
        
        # Dados de teste baseados na documentação
        cnpj_client = "02.003.402/0024-61"
        
        monitoring_requests = [
            {
                "cnpj_terminal": "04.887.625/0001-78",  # BTP
                "nome_navio": "MSC ALBANY",
                "viagem_navio": "MM223A"
            }
        ]
        
        print("📝 TESTE 1: Solicitar Monitoramento")
        print("-" * 35)
        print(f"CNPJ Cliente: {cnpj_client}")
        print(f"Solicitações: {monitoring_requests}")
        print()
        
        result = client.request_vessel_monitoring(cnpj_client, monitoring_requests)
        
        print(f"Resultado: {result.get('success')}")
        print(f"Status Code: {result.get('status_code')}")
        
        if result.get('success'):
            print("✅ SUCESSO!")
            print(f"Mensagem: {result.get('message')}")
            data = result.get('data', [])
            print(f"Dados retornados: {data}")
        else:
            print(f"❌ Erro: {result.get('error')}")
            if result.get('details'):
                print(f"Detalhes: {result.get('details')}")
        
        print()
        print("👁️ TESTE 2: Visualizar Monitoramento")
        print("-" * 35)
        
        # Usar os mesmos dados para visualizar
        view_result = client.view_vessel_monitoring(
            cnpj_client=cnpj_client,
            cnpj_terminal="04.887.625/0001-78",
            nome_navio="MSC ALBANY",
            viagem_navio="MM223A"
        )
        
        print(f"Resultado: {view_result.get('success')}")
        print(f"Status Code: {view_result.get('status_code')}")
        
        if view_result.get('success'):
            print("✅ SUCESSO!")
            print(f"Mensagem: {view_result.get('message')}")
            data = view_result.get('data', {})
            print(f"Dados do monitoramento: {data}")
        else:
            print(f"❌ Erro: {view_result.get('error')}")
            if view_result.get('details'):
                print(f"Detalhes: {view_result.get('details')}")
        
        print()
        print("🎯 TESTE 3: Teste com COSCO SHIPPING DANUBE")
        print("-" * 40)
        
        cosco_requests = [
            {
                "cnpj_terminal": "02.762.121/0001-04",  # Santos Brasil
                "nome_navio": "COSCO SHIPPING DANUBE",
                "viagem_navio": "044E"
            }
        ]
        
        cosco_result = client.request_vessel_monitoring("70.098.822/0001-32", cosco_requests)
        
        print(f"Resultado COSCO: {cosco_result.get('success')}")
        if cosco_result.get('success'):
            print("✅ COSCO monitoramento solicitado!")
            print(f"Dados: {cosco_result.get('data', [])}")
        else:
            print(f"❌ Erro COSCO: {cosco_result.get('error')}")
        
    except Exception as e:
        print(f"❌ Erro geral: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_monitoring_endpoints()
