import io
import re
import csv
import chardet
import streamlit as st

# -------------------------------
# Config
# -------------------------------
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
EXCEL_CELL_LIMIT = 32767  # limite do Excel por célula

# -------------------------------
# Helpers
# -------------------------------
def detect_decode(data: bytes) -> str:
    try:
        return data.decode("latin-1")
    except UnicodeDecodeError:
        enc = (chardet.detect(data).get("encoding") or "utf-8")
        return data.decode(enc, errors="replace")

def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")

def first_field(line: str) -> str:
    i = line.find(";")
    part = line if i < 0 else line[:i]
    part = part.strip()
    if part.startswith('"') and part.endswith('"') and len(part) >= 2:
        part = part[1:-1]
    return part

def is_start(line: str) -> bool:
    s = re.sub(r'^[\uFEFF\s"\'`]+', '', line or '')
    return bool(LOG_START_RX.match(s))

def clean_header_by_name(header: str, filename: str) -> str:
    if re.search(r"sql_SAC_LogDevolucao_CQT", filename, re.I):
        header = header.replace("Análise Realizada - Logística.", "Análise Realizada - Logística")
    if re.search(r"sql_SAC__LogDevolucao_SPE", filename, re.I):
        header = header.replace("Responsável pela entrega .", "Responsável pela entrega")
    return header

def rebuild_records(lines):
    """Concatena as linhas exatamente como vieram (sem inserir/remover caracteres)."""
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

# -------------------------------
# Saídas
# -------------------------------
def build_onecol_csv(final_lines):
    # CSV de 1 coluna; cada string vira uma linha
    buff = io.StringIO()
    w = csv.writer(buff, delimiter=',', quotechar='"', lineterminator='\r\n')
    for line in final_lines:
        w.writerow([line])
    return buff.getvalue().encode("utf-8")

def build_onecol_xlsx_or_none(final_lines):
    """Gera XLSX 1 coluna idêntico. Se alguma célula exceder o limite do Excel, NÃO cria XLSX (retorna None)."""
    try:
        import openpyxl
    except Exception as e:
        st.error(f"openpyxl não disponível: {e}")
        return None

    # verificação prévia de limite: não alteramos dados
    if any(len(s) > EXCEL_CELL_LIMIT for s in final_lines):
        return None  # deixa o usuário com o CSV canônico

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Dados"
    for line in final_lines:
        ws.append([line])

    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()

# -------------------------------
# UI
# -------------------------------
st.set_page_config(page_title="Limpeza CSV SAC (1 coluna)", page_icon="🧹", layout="wide")
st.title("🧹 Limpeza & Reconstrução (1 coluna, sem alterar conteúdo)")

st.markdown("""
**Como funciona:**  
1) Faça upload dos CSVs **crus** (CQT/SPE).  
2) O app **só reconstrói** as linhas (detectando início por “Logística/Logistica”) e corrige o **cabeçalho**.  
3) Entrega **apenas arquivos de 1 coluna**:
   - `*_final_onecol.csv` (canônico — use este em primeiro lugar),
   - `*_final_onecol.xlsx` (idêntico; **só é gerado** se nenhuma linha ultrapassar o limite do Excel).
""")

uploads = st.file_uploader("Envie um ou mais CSVs (crus)", type=["csv"], accept_multiple_files=True)
run = st.button("🚀 Processar", type="primary", use_container_width=True)

if run:
    if not uploads:
        st.error("Envie pelo menos 1 CSV.")
    else:
        for upl in uploads:
            name = upl.name
            data = upl.read()

            # 1) leitura
            text = detect_decode(data)
            lines = [ln.strip() for ln in normalize_newlines(text).split("\n") if ln.strip()]

            # 2) primeiro campo antes de ';'
            if not lines:
                st.warning(f"`{name}` está vazio.")
                continue
            ff = [first_field(ln) for ln in lines]

            header = clean_header_by_name(ff[0], name)
            body = ff[1:]

            # 3) força o cabeçalho final que você definiu
            final_header = FINAL_HEADER

            # 4) reconstrução 100% literal (sem inserir/remover caracteres)
            rebuilt = rebuild_records(body)

            if not rebuilt:
                st.warning(f"`{name}` não gerou registros após reconstrução.")
                continue

            final_lines = [final_header] + rebuilt

            # CSV (sempre)
            csv_bytes = build_onecol_csv(final_lines)
            st.download_button(
                f"⬇️ {name.replace('.csv','')}_final_onecol.csv",
                csv_bytes,
                file_name=f"{name.replace('.csv','')}_final_onecol.csv",
                mime="text/csv",
                use_container_width=True
            )

            # XLSX (só se não estourar o limite do Excel)
            xlsx_bytes = build_onecol_xlsx_or_none(final_lines)
            if xlsx_bytes is not None:
                st.download_button(
                    f"⬇️ {name.replace('.csv','')}_final_onecol.xlsx",
                    xlsx_bytes,
                    file_name=f"{name.replace('.csv','')}_final_onecol.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            else:
                st.info("⚠️ Algumas linhas excedem o limite de 32.767 caracteres do Excel por célula. "
                        "Por isso o **XLSX** não foi gerado para este arquivo. "
                        "Use o **CSV** (é idêntico e sem limite).")
