import pandas as pd
import streamlit as st
import unicodedata
import difflib
import io

# Função para normalizar texto
def normalizar_texto(texto):
    if not isinstance(texto, str):
        return ""
    texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('utf-8')
    return texto.strip().lower()

# Configuração do Streamlit
st.set_page_config(page_title="Leitor Inteligente de Colunas", layout="centered")
st.title("🔍 Leitor Inteligente - Extração de Coluna")

# Nome da coluna que queremos encontrar
coluna_procurada_original = "Nota Fiscal Ent/Saída"
coluna_procurada_norm = normalizar_texto(coluna_procurada_original)

uploaded_file = st.file_uploader("Selecione o arquivo", type=["csv", "tsv", "txt"])

if uploaded_file is not None:
    try:
        # Ler conteúdo como texto bruto
        conteudo = uploaded_file.read().decode("utf-8-sig")

        # Remover aspas externas e converter para DataFrame
        conteudo_limpo = conteudo.replace('"', '')

        # Usar ponto e vírgula como separador
        df = pd.read_csv(io.StringIO(conteudo_limpo), sep=";", engine="python")

        # Mostrar colunas detectadas
        st.subheader("📑 Colunas detectadas no arquivo:")
        colunas_originais = list(df.columns)
        st.write(colunas_originais)

        # Criar dicionário {normalizado: original}
        colunas_normalizadas = {normalizar_texto(c): c for c in colunas_originais}

        coluna_encontrada = None

        # Busca exata primeiro
        if coluna_procurada_norm in colunas_normalizadas:
            coluna_encontrada = colunas_normalizadas[coluna_procurada_norm]
            st.success(f"✅ Coluna '{coluna_procurada_original}' encontrada como '{coluna_encontrada}'")
        else:
            # Busca aproximada
            coluna_mais_parecida = difflib.get_close_matches(coluna_procurada_norm, colunas_normalizadas.keys(), n=1, cutoff=0.6)
            if coluna_mais_parecida:
                coluna_encontrada = colunas_normalizadas[coluna_mais_parecida[0]]
                st.warning(f"⚠️ Coluna '{coluna_procurada_original}' não foi encontrada exatamente, mas encontramos algo parecido: '{coluna_encontrada}'")
            else:
                st.error(f"❌ Nenhuma coluna parecida com '{coluna_procurada_original}' foi encontrada.")

        # Se encontrou a coluna, permitir download
        if coluna_encontrada:
            df_coluna = df[[coluna_encontrada]]
            csv_bytes = df_coluna.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label=f"📥 Baixar coluna '{coluna_encontrada}'",
                data=csv_bytes,
                file_name=f"{coluna_encontrada}.csv",
                mime="text/csv"
            )

    except Exception as e:
        st.error(f"⚠️ Erro: {str(e)}")
