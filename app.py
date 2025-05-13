import os
import json
from flask import Flask, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

# 1) Autenticação no Google Sheets
scope = ['https://www.googleapis.com/auth/spreadsheets.readonly']
creds_dict = json.loads(os.environ['GOOGLE_CREDS_JSON'])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
gc = gspread.authorize(creds)

# 2) Abrir a planilha e a aba
#    Defina no Render (ou .env local):
#      SHEET_NAME = HUB_TRANSPORTES
#      SHEET_TAB  = Página1
sheet = gc.open(os.environ['SHEET_NAME']).worksheet(os.environ['SHEET_TAB'])

@app.route('/consulta', methods=['POST'])
def consulta_sac():
    # 3) Pegar o texto enviado pelo Slash Command
    sac = request.form.get('text', '').strip()
    if not sac:
        return jsonify({
            "response_type": "ephemeral",
            "text": "❌ Uso correto: `/consulta <código SAC>`"
        }), 200

    # 4) Buscar todos os registros e encontrar a linha com "Último SAC" == sac
    registros = sheet.get_all_records()
    linha = next((r for r in registros if str(r.get('Último SAC','')).strip() == sac), None)

    if not linha:
        return jsonify({
            "response_type": "ephemeral",
            "text": f"⚠️ SAC *{sac}* não encontrado."
        }), 200

    # 5) Montar a mensagem usando os cabeçalhos exatos da planilha
    msg = (
        f"📦 *SAC:* {linha['Último SAC']}\n"
        f"📅 *Data Sol Coleta:* {linha['Data Sol Coleta']}\n"
        f"⏳ *Prazo Coletar:* {linha['Prazo Coletar']}\n"
        f"📅 *Data Entrega:* {linha['Data Entrega']}\n"
        f"🚚 *Status Devolução:* {linha['Status Devolução']}\n"
        f"🔄 *Status Tracking:* {linha['Status Tracking']}\n"
        f"📝 *Última Ocorrência:* {linha['Ultima_Ocorrencia']}"
    )

    return jsonify({
        "response_type": "in_channel",
        "text": msg
    }), 200

if __name__ == '__main__':
    # Para desenvolvimento local
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
