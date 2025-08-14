import io
import re
import csv
import zipfile
import chardet
import pandas as pd
import streamlit as st
from io import StringIO

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

# aceita "Logística"/"Logistica", ignora BOM/aspas/espaços no início, case-insensitive
LOG_START_RX = re.compile(r'^\s*["`\']*\s*log[íi]stica', re.IGNORECASE)

# Excel costuma ter limite ~32.767 chars por célula; usamos margem
EXCEL_CELL_LIMIT = 32760

# =========================
# Helpers de leitura/parse
# =========================
def detect_decode(data: bytes) -> str:
    """Decodifica bytes tentando latin-1 e caindo para o encoding detectado."""
    try:
        return data.decode("latin-1")
    except UnicodeDecodeError:
        enc = (chardet.detect(data).get("encoding") or "utf-8")
        return data.decode(enc, errors="replace")

def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")

def first_field(line: str) -> str:
    """Retorna o trecho antes do primeiro ';' (onde fica o conteúdo real)."""
    i = line.find(";")
    part = line if i < 0 else line[:i]
    part = part.strip()
    if part.startswith('"') and part.endswith('"') and len(part) >= 2:
        part = part[1:-1]
    return part

def is_start(line: str) -> bool:
    """Detecta início de registro (linha que começa com 'Logística...' ou 'Logistica...')."""
    s = re.sub(r'^[\uFEFF\s"\'`]+', '', line or '')  # remove BOM/aspas/espaços
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
    """Ajustes específicos de cabeçalho conforme o arquivo."""
    if re.search(r"sql_SAC_LogDevolucao_CQT", filename, re.I):
        header = header.replace("Análise Realizada - Logística.", "Análise Realizada - Logística")
    if re.search(r"sql_SAC__LogDevolucao_SPE", filename, re.I):
        header = header.replace("Responsável pela entrega .", "Responsável pela entrega")
    return header

# Parser robusto de linha CSV (respeita aspas, vírgulas internas e aspas escapadas "")
def parse_csv_line(line: str, delim: str = ",", quotechar: str = '"'):
    if line is None:
        return [""]
    reader = csv.reader(StringIO(line), delimiter=delim, quotechar=quotechar, doublequote=True)
    try:
        row = next(reader, [])
    except Exception:
        row = [line]
    return [c.strip() for c in row]

def normalize_row_len(row, header_len):
    """Garante mesmo nº de colunas do cabeçalho: preenche faltantes ou junta excedente na última coluna."""
    if len(row) == header_len:
        return row
    if len(row) < header_len:
        return row + [""] * (header_len - len(row))
    head = row[:header_len-1]
    tail_joined = ",".join(row[header_len-1:])
    return head + [tail_joined]

# =========================
# Builders de saída
# =========================
def build_onecol_csv(final_lines):
    """CSV com 1 coluna (cada item vira uma linha)."""
    buff = io.StringIO()
    w = csv.writer(buff, delimiter=',', quotechar='"', lineterminator='\r\n')
    for line in final_lines:
        w.writerow([line])
    return buff.getvalue().encode("utf-8")

def build_wide_xlsx(rebuilt, header):
    """XLSX com colunas explodidas por vírgula, tolerante a linhas irregulares."""
    header_cols = parse_csv_line(header, ",")
    header_len = len(header_cols)

    rows_norm = []
    bad_counts = {}

    for line in rebuilt:
        cols = parse_csv_line(line, ",")
        if len(cols) != header_len:
            bad_counts[len(cols)] = bad_counts.get(len(cols), 0) + 1
        rows_norm.append(normalize_row_len(cols, header_len))

    if bad_counts:
        st.info(f"Linhas ajustadas para caber no cabeçalho (contagem diferente): {bad_counts}")

    df = pd.DataFrame(rows_norm, columns=header_cols)
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Dados", index=False)
    return bio.getvalue()

def build_onecol_xlsx(final_lines):
    """XLSX 1 coluna; divide linhas acima do limite do Excel em partes __PART_n__."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Dados"
    step = EXCEL_CELL_LIMIT - 12  # margem para o sufixo
    for line in final_lines:
        if len(line) <= EXCEL_CELL_LIMIT:
            ws.append([line])
        else:
            idx, part = 0, 1
            while idx < len(line):
                chunk = line[idx: idx + step]
                ws.append([f"{chunk}__PART_{part}__"])
                idx += step
                part += 1
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()

# =========================
# UI
# =========================
st.set_page_config(page_title="Limpeza CSV SAC", page_icon="🧹", layout="wide")
st.title("🧹 Limpeza & Conversão dos CSVs do SAC")

st.markdown("""
Faça upload dos **CSVs crus** (CQT e SPE).  
O app aplica a tratativa (reconstrução “Logística…”, limpeza de cabeçalho, ordem fixa) e gera:
- **`*_final_onecol.csv`** (1 coluna — ideal p/ Power BI),
- **`*_final_wide.xlsx`** (colunas explodidas via parser CSV real),
- **`*_final_onecol.xlsx`** (1 coluna — divide linhas gigantes em partes seguras).
""")

uploads = st.file_uploader("Selecione os CSVs (um ou mais)", type=["csv"], accept_multiple_files=True)
run = st.button("🚀 Processar", type="primary", use_container_width=True)

if run:
    if not uploads:
        st.error("Envie pelo menos 1 CSV.")
    else:
        results = []
        for upl in uploads:
            name = upl.name
            data = upl.read()
            st.write(f"**Processando**: `{name}`")

            # 1) leitura & normalização
            text = detect_decode(data)
            lines = [ln.strip() for ln in normalize_newlines(text).split("\n") if ln.strip()]

            # 2) primeiro campo antes de ';'
            ff = [first_field(ln) for ln in lines]
            if not ff:
                st.warning(f"`{name}` parece vazio após leitura.")
                continue

            header = clean_header_by_name(ff[0], name)
            body = ff[1:]

            # 3) força cabeçalho final
            final_header = FINAL_HEADER

            # 4) reconstrução
            rebuilt = rebuild_records(body)

            if not rebuilt:
                st.warning(f"`{name}` não gerou registros após reconstrução. Verifique o arquivo de origem.")
                continue

            # 5) saídas
            onecol_csv_bytes  = build_onecol_csv([final_header] + rebuilt)
            wide_xlsx_bytes   = build_wide_xlsx(rebuilt, final_header)
            onecol_xlsx_bytes = build_onecol_xlsx([final_header] + rebuilt)

            base = name.rsplit(".", 1)[0]
            st.download_button(
                f"⬇️ {base}_final_onecol.csv",
                onecol_csv_bytes, file_name=f"{base}_final_onecol.csv",
                mime="text/csv", use_container_width=True
            )
            st.download_button(
                f"⬇️ {base}_final_wide.xlsx",
                wide_xlsx_bytes, file_name=f"{base}_final_wide.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            st.download_button(
                f"⬇️ {base}_final_onecol.xlsx",
                onecol_xlsx_bytes, file_name=f"{base}_final_onecol.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

            results.append((base, onecol_csv_bytes, wide_xlsx_bytes, onecol_xlsx_bytes))

        # ZIP opcional
        if results:
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for base, onecol_csv, wide_xlsx, onecol_xlsx in results:
                    zf.writestr(f"{base}_final_onecol.csv", onecol_csv)
                    zf.writestr(f"{base}_final_wide.xlsx",  wide_xlsx)
                    zf.writestr(f"{base}_final_onecol.xlsx", onecol_xlsx)
            zip_buf.seek(0)
            st.download_button(
                "📦 Baixar tudo em ZIP",
                zip_buf, file_name="saidas_tratadas.zip",
                mime="application/zip", use_container_width=True
            )

st.caption("Dica: para arquivos gigantes (≈600MB), prefira rodar local/servidor próprio por limite de upload do Streamlit Cloud.")
