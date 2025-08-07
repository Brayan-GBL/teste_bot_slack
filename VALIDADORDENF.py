import pandas as pd
import streamlit as st
import unicodedata
import difflib
import io
import re

# Função para normalizar texto
def normalizar_texto(texto):
    if not isinstance(texto, str):
        return ""
    texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('utf-8')
    return texto.strip().lower()

# Configuração do Streamlit
st.set_page_config(page_title="Leitor Inteligente de Colunas", layout="centered")
st.title("🔍 Extração de Colunas Múltiplas")

# Lista de colunas que queremos encontrar
colunas_procuradas_originais = [
    "Nota Fiscal Ent/Saída",
    "Data de Emissão",
    "Clien/Fornec",
    "Tipo de Transação",
    "Descrição TM",
    "Tipo Operação",
    "PEG",
    "Descrição Produto",
    "Qtde",
    "Valor Unitário",
    "Valor Total Produtos",
    "Desconto",
    "Valor Líquido dos Produtos",
    "Cliente contribuinte ICMS?",
    "Mov Estoque",
    "Descrição do Segmento",
    "Descr do Tipo de Prod",
    "Coleção",
    "Observação"
]
colunas_procuradas_norm = [normalizar_texto(c) for c in colunas_procuradas_originais]

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

        colunas_encontradas = []
        colunas_nao_encontradas = []

        # Procurar todas as colunas desejadas
        for col_norm, col_original in zip(colunas_procuradas_norm, colunas_procuradas_originais):
            if col_norm in colunas_normalizadas:
                colunas_encontradas.append(colunas_normalizadas[col_norm])
            else:
                # Busca aproximada
                coluna_mais_parecida = difflib.get_close_matches(col_norm, colunas_normalizadas.keys(), n=1, cutoff=0.6)
                if coluna_mais_parecida:
                    colunas_encontradas.append(colunas_normalizadas[coluna_mais_parecida[0]])
                    st.warning(f"⚠️ Coluna '{col_original}' não foi encontrada exatamente, mas encontramos algo parecido: '{colunas_normalizadas[coluna_mais_parecida[0]]}'")
                else:
                    colunas_nao_encontradas.append(col_original)

        if colunas_encontradas:
            st.success(f"✅ Colunas encontradas: {colunas_encontradas}")
            df_colunas = df[colunas_encontradas]

            # Correção da coluna PEG, se existir
            if "PEG" in df_colunas.columns:
                df_colunas["PEG"] = df_colunas["PEG"].astype(str).apply(
                    lambda x: re.sub(r'^0+(\d+)$', r'\1', re.sub(r'^=?"?(\d+)"?$', r'\1', x.strip()))
                )

            # Filtros adicionais
            filtros_tm = [
                "Devolução de venda",
                "Outras Entradas - Dev Remessa Escola",
                "Devolução de Bonificação",
                "Outras Entradas - Devolução Remessa Antecipada"
            ]

            if "Descrição TM" in df_colunas.columns and "Mov Estoque" in df_colunas.columns:
                df_colunas = df_colunas[
                    (df_colunas["Descrição TM"].isin(filtros_tm))
                    
                ]

            # Criar arquivo Excel em memória
            excel_buffer = io.BytesIO()
            df_colunas.to_excel(excel_buffer, index=False, engine="xlsxwriter")
            excel_buffer.seek(0)

            # Botão para baixar Excel
            st.download_button(
                label="📥 Baixar colunas filtradas (Excel)",
                data=excel_buffer,
                file_name="colunas_filtradas.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        if colunas_nao_encontradas:
            st.error(f"❌ Colunas não encontradas: {colunas_nao_encontradas}")

    except Exception as e:
        st.error(f"⚠️ Erro: {str(e)}")
