"""
Script para debugar o problema do monitoramento
"""
import streamlit as st

def debug_monitoring_state():
    """Debug do estado do monitoramento"""
    st.title("🔍 Debug - Estado do Monitoramento")
    
    # Verificar se existe a chave no session_state
    if 'monitoring_requests' in st.session_state:
        requests = st.session_state.monitoring_requests
        st.success(f"✅ Lista existe com {len(requests)} itens")
        
        if requests:
            st.markdown("### 📋 Conteúdo da Lista:")
            for i, req in enumerate(requests):
                st.write(f"**Item {i+1}:**")
                st.json(req)
        else:
            st.warning("⚠️ Lista existe mas está vazia")
            
    else:
        st.error("❌ Lista 'monitoring_requests' não existe no session_state")
    
    # Mostrar todo o session_state
    st.markdown("### 🔧 Session State Completo:")
    st.write(dict(st.session_state))
    
    # Botão para limpar tudo
    if st.button("🧹 Limpar Session State Completo"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.success("✅ Session state limpo!")
        st.rerun()
    
    # Botão para inicializar lista
    if st.button("🔄 Inicializar Lista de Monitoramento"):
        st.session_state.monitoring_requests = []
        st.success("✅ Lista inicializada!")
        st.rerun()

if __name__ == "__main__":
    debug_monitoring_state()
