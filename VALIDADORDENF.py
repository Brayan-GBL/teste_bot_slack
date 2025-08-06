import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="📊 Leitor de CSV - Teste de Coluna Específica")

st.title("📊 Leitor de CSV - Teste de Coluna Específica")

uploaded_file = st.file_uploader("Selecione o arquivo CSV", type="csv")

if uploaded_file is not None:
    try:
        # Lê o arquivo inteiro e garante que o BOM seja removido
        content = uploaded_file.read()
        decoded_content = content.decode("utf-8-sig")  # remove BOM se existir
        df = pd.read_csv(io.StringIO(decoded_content), sep=";")

        st.subheader("Colunas detectadas:")
        st.write(df.columns.tolist())

        coluna_alvo = "Nota Fiscal Ent/Saída"

        # Normaliza para comparação sem case sensitive e sem espaços extras
        colunas_normalizadas = {col.strip().lower(): col for col in df.columns}
        if coluna_alvo.strip().lower() in colunas_normalizadas:
            coluna_real = colunas_normalizadas[coluna_alvo.strip().lower()]
            st.success(f"✅ Coluna '{coluna_real}' encontrada!")
            st.dataframe(df[[coluna_real]])
        else:
            st.error(f"❌ A coluna '{coluna_alvo}' não foi encontrada no arquivo.")

    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {e}")
