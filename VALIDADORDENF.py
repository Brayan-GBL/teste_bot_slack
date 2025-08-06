import pandas as pd
import streamlit as st

# Configuração inicial do Streamlit
st.set_page_config(page_title="Leitor de CSV - Teste de Coluna Específica", layout="centered")
st.title("🔍 Leitor de CSV - Teste de Coluna Específica")

# Upload do arquivo
uploaded_file = st.file_uploader("Selecione o arquivo CSV", type=["csv"], help="Arraste ou selecione o arquivo CSV (máx. 200MB)")

# Nome da coluna que queremos encontrar
coluna_procurada = "Nota Fiscal Ent/Saída"

if uploaded_file is not None:
    try:
        # Leitura do CSV com separador ; e remoção do BOM
        df = pd.read_csv(uploaded_file, sep=";", encoding="utf-8-sig")

        # Mostra colunas detectadas de forma clara
        st.subheader("📑 Colunas detectadas:")
        colunas = list(df.columns)
        st.write(colunas)

        # Verifica se a coluna existe no DataFrame
        if coluna_procurada in df.columns:
            st.success(f"✅ Coluna '{coluna_procurada}' encontrada no arquivo.")
        else:
            st.error(f"❌ A coluna '{coluna_procurada}' não foi encontrada no arquivo.")

    except pd.errors.ParserError:
        st.error("⚠️ Erro ao ler o CSV. Verifique se o separador está correto e se o arquivo não está corrompido.")
    except Exception as e:
        st.error(f"⚠️ Ocorreu um erro inesperado: {str(e)}")
else:
    st.info("📌 Envie um arquivo CSV para iniciar a análise.")
