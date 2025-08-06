import streamlit as st
import pandas as pd
import csv
from io import StringIO

st.set_page_config(page_title="📊 Leitor de CSV - Teste de Coluna Específica")

st.title("📊 Leitor de CSV - Teste de Coluna Específica")

uploaded_file = st.file_uploader("Selecione o arquivo CSV", type="csv")

if uploaded_file is not None:
    try:
        # Detectar separador automaticamente
        sample = uploaded_file.read(2048).decode("utf-8", errors="ignore")
        uploaded_file.seek(0)  # Voltar ponteiro para o início

        # Detectar delimitador mais provável
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample)
        sep_detectado = dialect.delimiter

        st.info(f"Separador detectado: `{sep_detectado}`")

        # Tentar carregar com cabeçalho
        df = pd.read_csv(uploaded_file, sep=sep_detectado, encoding="utf-8", header=0)

        st.subheader("Colunas detectadas:")
        st.write(df.columns.tolist())

        coluna_alvo = "Nota Fiscal Ent/Saída"
        if coluna_alvo in df.columns:
            st.success(f"✅ Coluna '{coluna_alvo}' encontrada!")
            st.dataframe(df[[coluna_alvo]])
        else:
            st.error(f"❌ A coluna '{coluna_alvo}' não foi encontrada no arquivo.")

    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {e}")
