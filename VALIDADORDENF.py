import pandas as pd
import streamlit as st
import unicodedata
import difflib

# Função para normalizar nomes de colunas (remove acentos, deixa minúsculo, tira espaços extras)
def normalizar_texto(texto):
    if not isinstance(texto, str):
        return ""
    texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('utf-8')
    return texto.strip().lower()

# Configuração do Streamlit
st.set_page_config(page_title="Leitor de CSV Inteligente", layout="centered")
st.title("🔍 Leitor de CSV Inteligente - Busca de Coluna")

# Upload do arquivo
uploaded_file = st.file_uploader("Selecione o arquivo CSV", type=["csv"], help="Arraste ou selecione o arquivo CSV")

# Nome da coluna que queremos encontrar (forma original)
coluna_procurada_original = "Nota Fiscal Ent/Saída"
coluna_procurada_norm = normalizar_texto(coluna_procurada_original)

if uploaded_file is not None:
    try:
        # Leitura do CSV com separador ; e remoção do BOM
        df = pd.read_csv(uploaded_file, sep=";", encoding="utf-8-sig")

        # Mostra colunas detectadas
        st.subheader("📑 Colunas detectadas no arquivo:")
        colunas_originais = list(df.columns)
        st.write(colunas_originais)

        # Normaliza colunas para comparação
        colunas_normalizadas = {normalizar_texto(c): c for c in colunas_originais}

        if coluna_procurada_norm in colunas_normalizadas:
            st.success(f"✅ Coluna '{coluna_procurada_original}' encontrada como '{colunas_normalizadas[coluna_procurada_norm]}'")
        else:
            # Busca coluna mais parecida
            coluna_mais_parecida = difflib.get_close_matches(coluna_procurada_norm, colunas_normalizadas.keys(), n=1, cutoff=0.6)
            if coluna_mais_parecida:
                nome_real = colunas_normalizadas[coluna_mais_parecida[0]]
                st.warning(f"⚠️ Coluna '{coluna_procurada_original}' não encontrada exatamente, mas encontramos algo parecido: '{nome_real}'")
            else:
                st.error(f"❌ Nenhuma coluna parecida com '{coluna_procurada_original}' foi encontrada.")

    except pd.errors.ParserError:
        st.error("⚠️ Erro ao ler o CSV. Verifique se o separador está correto e se o arquivo não está corrompido.")
    except Exception as e:
        st.error(f"⚠️ Ocorreu um erro inesperado: {str(e)}")
else:
    st.info("📌 Envie um arquivo CSV para iniciar a análise.")
