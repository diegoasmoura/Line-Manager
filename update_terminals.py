"""Script para atualizar a tabela F_ELLOX_TERMINALS com dados da API."""
import logging
from ellox_api import get_default_api_client
from ellox_data_extractor import ElloxDataExtractor

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Função principal para atualizar terminais."""
    try:
        # Obter cliente API
        api_client = get_default_api_client()
        
        # Verificar autenticação
        if not api_client.authenticated:
            logger.error("❌ API não autenticada. Verifique as credenciais.")
            return False
            
        # Testar conexão
        api_test = api_client.test_connection()
        if not api_test.get("success"):
            logger.error("❌ API indisponível. Tente novamente mais tarde.")
            return False
            
        # Criar extrator
        extractor = ElloxDataExtractor()
        extractor.client = api_client
        
        # Extrair e salvar terminais
        extractor.extract_terminals()
        
        logger.info("✅ Terminais atualizados com sucesso!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro ao atualizar terminais: {e}")
        return False

if __name__ == "__main__":
    main()
