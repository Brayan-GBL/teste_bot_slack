import io
import re
import csv
import zipfile
import chardet
import pandas as pd
import streamlit as st

# =========================
# Config & Constantes
# =========================
FINAL_HEADER = ('Área/Processo envolvido,Responsável SAC,Código da Ocorrência,Assunto,Tipo,Status,'
                'Proprietário do SAC Name,Hora de Criação,Hora da modificação,Encerrado em,'
                'Solução de Ensino,Tipo de Venda,Código SGE,Escola Nome,CNPJ,Razão Social,'
                'Rua de Entrega,Cidade de Entrega,Estado de Entrega,CEP de Entrega,'
                'Contato atualizado,Telefone,Solicitação,Filial de origem,RMA DEV. VENDA,RMA 2,'
                'NF para aplicação de crédito (Financeiro),Nome da transportadora.,'
                'Cliente irá contratar o frete?,"Cliente vai contratar frete, info a transportadora",'
                'Nº do pedido SGE,NF Remessa LNE,Nº da nota de origem,'
                'Qual a flexibilidade de data/horário sugeridas?,Análise Realizada - Logística,'
                'Parecer da Logística,NF DEV.COLETA,NF Faturamento,Material Conforme?,'
                'Motivo Não Conformidade,Observações Logística,NF DEV.VENDA FATURAMENTO.,'
                'NF DEV.LOJA FATURAMENTO,NF DEV. SIMP.FAT,Número contato,'
                'Horário disponível para coleta,Responsável pela entrega,Tem restrição de acesso?')

LOG_START_RX = re.compile(r'^\s*["`\']*\s*log[íi]stica', re.IGNORECASE)
EXCEL_CELL_LIMIT = 32760  # limite seguro por célula no Excel (~32.767)

# =========================
# Helpers de parsing
# =========================
def detect_decode(data: bytes) -> str:
    # tenta latin-1 primeiro; senão detecta com chardet
    try:
        return data.decode("latin-1")
    except UnicodeDecodeError:
        enc = (chardet.detect(data).get("encoding") or "utf-8")
        return data.decode(enc, errors="replace")

def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")

def first_field(line: str) -> str:
    """Retorna o trecho antes do primeiro ';'"""
    i = line.find(";")
    part = line if i < 0 else line[:i]
    part = part.strip()
    if part.startswith('"') and part.endswith('"') and len(part) >= 2:
        part = part[1:-1]
    return part

def is_start(line: str) -> bool:
    # remove BOM/aspas/espaços do começo; aceita Logística/Logistica (case-insensitive)
    s = re.sub(r'^[\uFEFF\s"\'`]+', '', line or '')
    return bool(LOG_START_RX.match(s))

def rebuild_records(lines):
    """Concatena linhas até o próximo início; não ignora nada."""
    out, buf = [], ""
    for ln in lines:
        if is_start(ln):
            if buf:
                out.append(buf)
            buf = ln
        else:
            if not buf:
                buf = ln
            else:
                buf += ln
    if buf:
        out.append(buf)
    return out

def clean_header_by_name(header: str, filename: str) -> str:
    if re.search(r"sql_SAC_LogDevolucao_CQT", filename, re.I):
        header = header.replace("Análise Realizada - Logística.", "Análise Realizada - Logística")
    if re.search(r"sql_SAC__LogDevolucao_SPE", filename, re.I):
        header = header.replace("Responsável pela entrega .", "Responsável pela entrega")
    return header

# divide linha CSV respeitando aspas
def split_csv_line(line: str, delim: str = ","):
    out, cur, inq = [], [], False
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == '"':
            if inq and i + 1 < len(line) and line[i+1] == '"':
                cur.append('"'); i += 2; continue
            inq = not inq; i += 1; continue
        if ch == delim and not inq:
            out.append(''.join(cur).strip()); cur = []; i += 1; continue
        cur.append(ch); i += 1
    out.append(''.join(cur).strip())
    return out

# =========================
# Builders de saída
# =========================
def build_onecol_csv(final_lines):
    """CSV com 1 coluna: cada item vira uma linha (sem limites práticos)."""
    buff = io.StringIO()
    w = csv.writer(buff, delimiter=',', quotechar='"', lineterminator='\r\n')
    for line in final_lines:
        w.writerow([line])
    return buff.getvalue().encode("utf-8")

def build_wide_xlsx(rebuilt, header):
    """XLSX com colunas explodidas por vírgula."""
    rows = [split_csv_line(header)] + [split_csv_line(x) for x in rebuilt]
    df = pd.DataFrame(rows[1:], columns=rows[0])
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Dados", index=False)
    return bio.getvalue()

def build_onecol_xlsx(final_lines):
    """XLSX 1 coluna; divide linha longa em partes __PART_n__ para não estourar o Excel."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Dados"
    for line in final_lines:
        if len(line) <= EXCEL_CELL_LIMIT:
            ws.append([line])
        else:
            idx, part = 0, 1
            step = EXCEL_CELL_LIMIT - 12
            while idx < len(line):
                chunk = line[idx: idx + step]
                ws.append([f"{chunk}__PART_{part}__"])
                idx += step; part += 1
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()

# =========================
# UI
# =========================
st.set_page_config(page_title="Limpeza CSV SAC", page_icon="🧹", layout="wide")
st.title("🧹 Limpeza & Conversão dos CSVs do SAC")

st.markdown("""
Faça upload dos **2 CSVs crus** (CQT e SPE).  
O app aplica a tratativa (reconstrução “Logística…”, limpeza de cabeçalho, ordem fixa) e gera:
- **`*_final_onecol.csv`** (1 coluna A — ideal p/ Power BI),
- **`*_final_wide.xlsx`** (colunas explodidas),
- **`*_final_onecol.xlsx`** (1 coluna A, com divisão segura se exceder o limite do Excel).
""")

files = st.file_uploader("Selecione os CSVs", type=["csv"], accept_multiple_files=True)

col_a, col_b = st.columns([1,1])
with col_a:
    btn = st.button("🚀 Processar", type="primary", use_container_width=True)

logs = st.empty()
results = []

if btn:
    if not files:
        st.error("Envie pelo menos 1 CSV.")
    else:
        for upl in files:
            name = upl.name
            data = upl.read()
            st.write(f"**Processando**: `{name}`")

            # 1) leitura & normalização
            text = detect_decode(data)
            lines = [ln.strip() for ln in normalize_newlines(text).split("\n") if ln.strip()]

            # 2) primeiro campo antes de ';'
            ff = [first_field(ln) for ln in lines]
            header = clean_header_by_name(ff[0], name)
            body = ff[1:]

            # 3) força cabeçalho final
            final_header = FINAL_HEADER

            # 4) reconstrução
            rebuilt = rebuild_records(body)

            # 5) saídas
            onecol_csv_bytes  = build_onecol_csv([final_header] + rebuilt)
            wide_xlsx_bytes   = build_wide_xlsx(rebuilt, final_header)
            onecol_xlsx_bytes = build_onecol_xlsx([final_header] + rebuilt)

            # botões de download individuais
            st.download_button(
                f"⬇️ {name.replace('.csv','')}_final_onecol.csv",
                onecol_csv_bytes, file_name=f"{name.replace('.csv','')}_final_onecol.csv",
                mime="text/csv", use_container_width=True
            )
            st.download_button(
                f"⬇️ {name.replace('.csv','')}_final_wide.xlsx",
                wide_xlsx_bytes, file_name=f"{name.replace('.csv','')}_final_wide.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            st.download_button(
                f"⬇️ {name.replace('.csv','')}_final_onecol.xlsx",
                onecol_xlsx_bytes, file_name=f"{name.replace('.csv','')}_final_onecol.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

            # adiciona ao zip
            results.append((
                name,
                onecol_csv_bytes,
                wide_xlsx_bytes,
                onecol_xlsx_bytes
            ))

        # zip com tudo
        if results:
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for name, onecol_csv, wide_xlsx, onecol_xlsx in results:
                    base = name.rsplit(".", 1)[0]
                    zf.writestr(f"{base}_final_onecol.csv", onecol_csv)
                    zf.writestr(f"{base}_final_wide.xlsx",  wide_xlsx)
                    zf.writestr(f"{base}_final_onecol.xlsx", onecol_xlsx)
            zip_buf.seek(0)
            st.download_button(
                "📦 Baixar tudo em ZIP",
                zip_buf, file_name="saidas_tratadas.zip",
                mime="application/zip",
                use_container_width=True
            )

st.caption("Tudo roda local. Se quiser, depois a gente integra isso a n8n/Drive.")
