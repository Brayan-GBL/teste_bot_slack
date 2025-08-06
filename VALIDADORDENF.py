import streamlit as st
import pandas as pd
import io

st.title("🔍 Leitor de CSV - Teste de Coluna Específica")

coluna_desejada = "Nota Fiscal Ent/Saída"

# Upload de um arquivo CSV
uploaded_file = st.file_uploader(
    "Selecione o arquivo CSV",
    type=["csv"]
)

if uploaded_file:
    try:
        # Tentativa com separador ponto e vírgula
        try:
            df = pd.read_csv(uploaded_file, sep=";", encoding="utf-8", engine="python")
        except:
            df = pd.read_csv(uploaded_file, sep=",", encoding="utf-8", engine="python")

        if coluna_desejada in df.columns:
            df_filtrado = df[[coluna_desejada]]
            
            st.subheader(f"📋 Dados da coluna: {coluna_desejada}")
            st.dataframe(df_filtrado)

            # Botão de download
            output = io.BytesIO()
            df_filtrado.to_excel(output, index=False)
            output.seek(0)

            st.download_button(
                label="📥 Baixar coluna filtrada",
                data=output,
                file_name="coluna_filtrada.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.error(f"A coluna '{coluna_desejada}' não foi encontrada no arquivo.")

    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {e}")
