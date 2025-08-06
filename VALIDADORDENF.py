import streamlit as st
import pandas as pd

st.set_page_config(page_title="📊 Leitor de CSV - Teste de Coluna Específica")

st.title("📊 Leitor de CSV - Teste de Coluna Específica")

uploaded_file = st.file_uploader("Selecione o arquivo CSV", type="csv")

if uploaded_file is not None:
    try:
        # Forçar separador ; e encoding
        df = pd.read_csv(
            uploaded_file,
            sep=";",           # força uso do ponto e vírgula
            encoding="utf-8-sig",  # evita problema com acentos
            quotechar='"'      # garante que campos entre aspas sejam lidos corretamente
        )

        st.subheader("Colunas detectadas:")
        st.write(df.columns.tolist())

        # Nome da coluna que queremos buscar
        coluna_alvo = "Nota Fiscal Ent/Saída"

        # Verificação sem case sensitive nem espaços extras
        colunas_normalizadas = {col.strip().lower(): col for col in df.columns}
        if coluna_alvo.strip().lower() in colunas_normalizadas:
            coluna_real = colunas_normalizadas[coluna_alvo.strip().lower()]
            st.success(f"✅ Coluna '{coluna_real}' encontrada!")
            st.dataframe(df[[coluna_real]])
        else:
            st.error(f"❌ A coluna '{coluna_alvo}' não foi encontrada no arquivo.")

    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {e}")
