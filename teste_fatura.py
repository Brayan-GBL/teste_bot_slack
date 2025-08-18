import pandas as pd
import streamlit as st
import re

# --- helpers ---------------------------------------------------------------
def only_digits(s: pd.Series) -> pd.Series:
    """Mantém apenas dígitos (evita .0, espaços, traços etc.)."""
    return s.astype(str).str.replace(r"\D", "", regex=True).str.strip()

def make_key(pallet_series: pd.Series, nf_series: pd.Series) -> pd.Series:
    """Chave padrão: PALLET depois NF? Não! É PALLET + NF (nesta ordem)."""
    return only_digits(pallet_series) + only_digits(nf_series)

# --- core ------------------------------------------------------------------
def processar_analise(cobranca_file, triagem_file):
    # Carregar todas as abas do arquivo
    cobranca_xl = pd.ExcelFile(cobranca_file)
    triagem_xl  = pd.ExcelFile(triagem_file)

    # Tentar encontrar a aba correta ignorando espaços e maiúsculas
    cobranca_sheet = next((s for s in cobranca_xl.sheet_names if "devol"   in s.lower() or "cobran" in s.lower()), None)
    triagem_sheet  = next((s for s in triagem_xl.sheet_names  if "triagem" in s.lower()), None)

    if not cobranca_sheet or not triagem_sheet:
        raise ValueError(f"Abas não encontradas. Disponíveis: {cobranca_xl.sheet_names} e {triagem_xl.sheet_names}")

    # Carregar os dados das abas corretas
    cobranca_df = cobranca_xl.parse(cobranca_sheet)
    triagem_df  = triagem_xl.parse(triagem_sheet)

    # Padronizar nomes de colunas
    cobranca_df.columns = cobranca_df.columns.str.strip().str.upper()
    triagem_df.columns  = triagem_df.columns.str.strip().str.upper()

    # Validar colunas essenciais
    req_cobranca = {"NF", "LOCAL", "QTD UND", "CLIENTE"}
    req_triagem  = {"PALLET", "NOTA FISCAL", "QTDE FÍSICA (BOM)", "QTDE FÍSICA (RUIM)"}
    if not req_cobranca.issubset(cobranca_df.columns) or not req_triagem.issubset(triagem_df.columns):
        raise KeyError("Colunas obrigatórias ausentes. "
                       f"Cobrança precisa de: {sorted(req_cobranca)} | "
                       f"Triagem precisa de: {sorted(req_triagem)}")

    # Remover linhas sem NF/LOCAL
    cobranca_df = cobranca_df.dropna(subset=["NF", "LOCAL"])

    # >>> CHAVE DE VÍNCULO PADRÃO (igual à sua FORMULA: PALLET & NF) <<<
    # Na cobrança usamos LOCAL como 'pallet'
    cobranca_df["CHAVE_PALLET_NF"] = make_key(cobranca_df["LOCAL"], cobranca_df["NF"])
    triagem_df["CHAVE_PALLET_NF"]  = make_key(triagem_df["PALLET"], triagem_df["NOTA FISCAL"])

    # Consolidar quantidades na triagem por CHAVE
    triagem_consolidado = (
        triagem_df
        .groupby("CHAVE_PALLET_NF", as_index=False)
        .agg({
            "QTDE FÍSICA (BOM)": "sum",
            "QTDE FÍSICA (RUIM)": "sum"
        })
    )
    triagem_consolidado["CONCAT_DEV"] = (
        triagem_consolidado["QTDE FÍSICA (BOM)"] + triagem_consolidado["QTDE FÍSICA (RUIM)"]
    )

    # Mesclar usando a CHAVE correta (PALLET+NF)
    resultado_df = cobranca_df.merge(
        triagem_consolidado,
        on="CHAVE_PALLET_NF",
        how="left"
    )

    # Diferença entre o recebido (triagem) e o cobrado (QTD UND)
    resultado_df["CONCAT_DEV"] = resultado_df["CONCAT_DEV"].fillna(0)
    resultado_df["DIFERENÇA"]  = resultado_df["CONCAT_DEV"] - resultado_df["QTD UND"]

    # Classificação
    def classificar_diferenca(row):
        bom = row.get("QTDE FÍSICA (BOM)", 0) or 0
        ruim = row.get("QTDE FÍSICA (RUIM)", 0) or 0
        concat_dev = (bom + ruim)
        qtd_und = row["QTD UND"]

        if concat_dev > qtd_und and concat_dev == row["CONCAT_DEV"]:
            return "Informação incorreta - Devemos pagar mais"
        elif (concat_dev - qtd_und) > 0 and concat_dev < qtd_und:
            return "Cobrança indevida - Quantidade menor recebida"
        elif (concat_dev - qtd_und) > 0:
            return "Sobra cliente"
        elif (concat_dev - qtd_und) < 0:
            return "Digitou errado" if concat_dev > 0 else "Não recebemos nada"
        else:
            return "Correto"

    resultado_df["Observação PSD"] = resultado_df.apply(classificar_diferenca, axis=1)

    # Valores financeiros
    valor_unitario = 2.76
    resultado_df["Valor Unitário"]   = valor_unitario
    resultado_df["Total Nota"]       = resultado_df["QTD UND"]   * valor_unitario
    resultado_df["Total Cobrança"]   = resultado_df["DIFERENÇA"] * valor_unitario

    # Colunas finais
    saida = resultado_df[[
        "NF", "CLIENTE", "LOCAL", "QTD UND",
        "CHAVE_PALLET_NF",
        "QTDE FÍSICA (BOM)", "QTDE FÍSICA (RUIM)", "CONCAT_DEV",
        "DIFERENÇA", "Observação PSD",
        "Valor Unitário", "Total Nota", "Total Cobrança"
    ]].rename(columns={"CHAVE_PALLET_NF": "CHAVE (PALLET+NF)"})

    return saida

# --- Streamlit -------------------------------------------------------------
st.title("FATURA POSIGRAF")

cobranca_file = st.file_uploader("Upload do arquivo COBRANÇA POSIGRAF", type=["xlsx"])
triagem_file  = st.file_uploader("Upload do arquivo CONFERÊNCIA TRIAGEM", type=["xlsx"])

if cobranca_file and triagem_file:
    try:
        df_resultado = processar_analise(cobranca_file, triagem_file)
        st.write("### Resultados da Análise:")
        st.dataframe(df_resultado, use_container_width=True)

        nome_saida = "analise_cobranca_triagem.xlsx"
        df_resultado.to_excel(nome_saida, index=False)
        with open(nome_saida, "rb") as file:
            st.download_button(
                label="Baixar Relatório Consolidado",
                data=file,
                file_name=nome_saida,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    except (ValueError, KeyError) as e:
        st.error(f"Erro: {str(e)}. Verifique se os arquivos contêm as abas e colunas corretas.")
