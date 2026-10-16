# ==============================================================================
# MASTER TRADER BOT - COMPLETO (OPÇÕES, FUNDAMENTOS, MANEJO E TRACKER)
# ==============================================================================

import os
import json
import requests
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import google.generativeai as genai

# Credenciais lidas dos Secrets do GitHub
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    ai_model = genai.GenerativeModel('gemini-1.5-flash')
else:
    ai_model = None

TICKERS = [
    "BOVA11.SA", "PETR4.SA", "VALE3.SA", "BBAS3.SA", "ITUB4.SA", 
    "BBDC4.SA", "ITSA4.SA", "ABEV3.SA", "WEGE3.SA", "PRIO3.SA",
    "SUZB3.SA", "RENT3.SA", "GGBR4.SA", "CSAN3.SA", "EMBR3.SA"
]

def enviar_telegram(mensagem):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Credenciais do Telegram não configuradas.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID, 
        "text": mensagem, 
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("✅ Alerta enviado com sucesso para o Telegram!")
        else:
            print(f"⚠️ Erro ao enviar para o Telegram: {response.text}")
    except Exception as e:
        print(f"❌ Erro de conexão ao enviar mensagem: {e}")

def calcular_rsi(df, period=14):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calcular_datas_vencimento():
    hoje = datetime.now()
    data_vencimento_alvo = hoje + timedelta(days=45)
    data_manejo_alvo = data_vencimento_alvo - timedelta(days=25)
    return data_vencimento_alvo.strftime('%d/%m/%Y'), data_manejo_alvo.strftime('%d/%m/%Y')

def gerar_plano_manejo_ia(estrategia, ativo, preco, p_l, div_ebitda, data_manejo):
    if div_ebitda and div_ebitda > 3.5:
        return None, "Descartado: Endividamento elevado (Dívida/EBITDA > 3.5)"
    if p_l and (p_l < 0 or p_l > 35):
        return None, "Descartado: Valuation inadequado ou prejuízo"

    if not ai_model:
        return f"Estratégia: {estrategia} | Data Alvo de Manejo: {data_manejo}", "Aprovado"
    
    prompt = (
        f"Atue como um estrategista sênior de opções na B3. Estratégia: {estrategia}. "
        f"Ativo: {ativo} a R$ {preco:.2f} (P/L: {p_l}, Dívida/EBITDA: {div_ebitda}). "
        f"Data limite para manejo (faltando 25 dias para o vencimento): {data_manejo}. "
        f"Escreva um plano de manejo ultra-curto em 2 tópicos focando na gestão de risco e objetivo de lucro (60% a 75%)."
    )
    try:
        response = ai_model.generate_content(prompt)
        return response.text.strip(), "Aprovado"
    except Exception as e:
        return f"Manejar no dia {data_manejo} buscando zerar com 60% a 75% do lucro máximo.", "Aprovado"

def checar_posicoes_ativas():
    if not os.path.exists("posicoes.json"):
        return

    try:
        with open("posicoes.json", "r") as f:
            posicoes = json.load(f)
    except Exception:
        return

    alertas_manejo = []
    hoje = datetime.now()

    for pos in posicoes:
        try:
            ticker = pos["ativo"] + ".SA"
            data_venc = datetime.strptime(pos["data_vencimento"], "%Y-%m-%d")
            dias_para_vencimento = (data_venc - hoje).days

            dados = yf.download(ticker, period="5d", interval="1d", progress=False)
            if dados.empty:
                continue
            
            if isinstance(dados.columns, pd.MultiIndex):
                dados.columns = dados.columns.get_level_values(0)

            preco_atual = float(dados['Close'].iloc[-1])
            strike_v = pos.get("strike_vendida", 0)
            distancia_strike_pct = ((preco_atual - strike_v) / preco_atual) * 100 if strike_v > 0 else 0

            alerta_tempo = dias_para_vencimento <= 25
            alerta_lucro = distancia_strike_pct > 6.0 and dias_para_vencimento <= 30

            if alerta_tempo or alerta_lucro:
                motivo = "⏳ *JANELA DE 25 DIAS ALCANÇADA!*" if alerta_tempo else "💰 *META DE LUCRO ESTIMADA (60%-75%)!*"
                alertas_manejo.append(
                    f"🔔 *ACOMPANHAMENTO - [{pos['ativo']}]*\n"
                    f"• {motivo}\n"
                    f"• Preço Atual: R$ {preco_atual:.2f} (Distância do Strike: +{distancia_strike_pct:.1f}%)\n"
                    f"📅 *Dias Restantes pro Vencimento:* `{dias_para_vencimento} dias`\n"
                    f"🎯 *Recomendação:* Zerar/encerrar a posição no broker para colocar o lucro no bolso.\n"
                )
        except Exception as e:
            print(f"Erro ao processar posição {pos.get('ativo')}: {e}")

    if alertas_manejo:
        msg_carteira = "📢 *MONITORAMENTO DIÁRIO DE POSIÇÕES ATIVAS* 📢\n\n" + "\n".join(alertas_manejo)
        enviar_telegram(msg_carteira)

def rodar_master_scanner():
    print("🔎 Executando Master Trader Bot...")
    sinais_travas = []
    sinais_calls = []
    sinais_laterais = []

    vencimento_str, manejo_str = calcular_datas_vencimento()
    data_hoje = datetime.now().strftime('%d/%m/%Y')

    for ticker in TICKERS:
        try:
            acao = yf.Ticker(ticker)
            info = acao.info
            p_l = info.get("trailingPE", 0)
            div_ebitda = info.get("debtToEbitda", info.get("enterpriseToEbitda", 1.5))
            if not div_ebitda: 
                div_ebitda = 1.0

            df_diario = yf.download(ticker, period="1y", interval="1d", progress=False)
            if df_diario.empty or len(df_diario) < 60:
                continue

            if isinstance(df_diario.columns, pd.MultiIndex):
                df_diario.columns = df_diario.columns.get_level_values(0)

            df_diario['EMA9'] = df_diario['Close'].ewm(span=9, adjust=False).mean()
            df_diario['EMA21'] = df_diario['Close'].ewm(span=21, adjust=False).mean()
            df_diario['SMA50'] = df_diario['Close'].rolling(window=50).mean()
            df_diario['RSI14'] = calcular_rsi(df_diario, 14)

            df_diario['BB_Mid'] = df_diario['Close'].rolling(window=20).mean()
            df_diario['BB_Std'] = df_diario['Close'].rolling(window=20).std()
            df_diario['BB_Upper'] = df_diario['BB_Mid'] + (df_diario['BB_Std'] * 2)
            df_diario['BB_Lower'] = df_diario['BB_Mid'] - (df_diario['BB_Std'] * 2)

            ultimo_d = df_diario.iloc[-1]
            preco_atual = float(ultimo_d['Close'])
            rsi = float(ultimo_d['RSI14'])
            ema9_d = float(ultimo_d['EMA9'])
            ema21_d = float(ultimo_d['EMA21'])
            sma50_d = float(ultimo_d['SMA50'])
            b_upper = float(ultimo_d['BB_Upper'])
            b_lower = float(ultimo_d['BB_Lower'])

            nome_limpo = ticker.replace(".SA", "")

            # 1. TRAVA A CRÉDITO
            tendencia_alta_d = (ema9_d >= ema21_d) and (ema21_d >= sma50_d)
            perto_m9_d = (((preco_atual - ema9_d) / ema9_d) * 100) <= 2.5
            
            if tendencia_alta_d and perto_m9_d and rsi <= 65:
                plano, status = gerar_plano_manejo_ia(
                    "Trava de Alta com Put", nome_limpo, preco_atual, p_l, div_ebitda, manejo_str
                )
                if status == "Aprovado":
                    s_v = round(preco_atual * 0.91, 2)
                    s_c = round(preco_atual * 0.86, 2)
                    sinais_travas.append(
                        f"🛡️ *[{nome_limpo}] Trava a Crédito (Alta)*\n"
                        f"• Preço Atual ({data_hoje}): R$ {preco_atual:.2f} | P/L: {p_l:.1f}\n"
                        f"• Strikes (Venda/Compra): R$ {s_v} / R$ {s_c}\n"
                        f"📅 *Data Alvo de Manejo (Faltando 25 dias):* `{manejo_str}`\n"
                        f"📋 *Diretriz:* {plano}\n"
                    )

            # 2. COMPRA DE CALL DIRECIONAL (SEMANAL/MACRO)
            df_semanal = yf.download(ticker, period="2y", interval="1wk", progress=False)
            if not df_semanal.empty:
                if isinstance(df_semanal.columns, pd.MultiIndex):
                    df_semanal.columns = df_semanal.columns.get_level_values(0)
                df_semanal['EMA9_W'] = df_semanal['Close'].ewm(span=9, adjust=False).mean()
                df_semanal['EMA21_W'] = df_semanal['Close'].ewm(span=21, adjust=False).mean()
                
                if float(df_semanal['EMA9_W'].iloc[-1]) > float(df_semanal['EMA21_W'].iloc[-1]) and rsi < 68:
                    plano_call, status_call = gerar_plano_manejo_ia(
                        "Compra de CALL Direcional (Macro)", nome_limpo, preco_atual, p_l, div_ebitda, manejo_str
                    )
                    if status_call == "Aprovado":
                        s_call = round(preco_atual * 1.03, 2)
                        sinais_calls.append(
                            f"🚀 *[{nome_limpo}] Compra de CALL Direcional*\n"
                            f"• Preço Atual ({data_hoje}): R$ {preco_atual:.2f} | P/L: {p_l:.1f}\n"
                            f"• Strike Sugerido (Delta ~0.40): R$ {s_call}\n"
                            f"📋 *Diretriz:* {plano_call}\n"
                        )

            # 3. ESTRUTURAS NEUTRAS
            quase_lateral = abs(ema9_d - ema21_d) / preco_atual < 0.015
            quase_nas_pontas = (preco_atual >= b_upper * 0.98) or (preco_atual <= b_lower * 1.02)
            if quase_lateral and quase_nas_pontas:
                sinais_laterais.append(
                    f"🟡 *[{nome_limpo}] Estrutura Neutra (Condor / Borboleta)*\n"
                    f"• Preço Atual ({data_hoje}): R$ {preco_atual:.2f} testando Bandas.\n"
                    f"📅 *Data Alvo de Manejo / Saída:* `{manejo_str}`\n"
                )

        except Exception as e:
            print(f"Erro ao processar {ticker}: {e}")
            continue

    # Envia oportunidades diárias
    msg = f"🎯 *MASTER TRADER - RELATÓRIO ({data_hoje})* 🎯\n\n"
    if sinais_travas:
        msg += "━━━━━━━━━━━━━━━━━━━━━━━\n🟢 *TRAVAS A CRÉDITO*\n━━━━━━━━━━━━━━━━━━━━━━━\n" + "\n".join(sinais_travas) + "\n\n"
    if sinais_calls:
        msg += "━━━━━━━━━━━━━━━━━━━━━━━\n🔵 *COMPRAS DE CALL DIRECIONAL*\n━━━━━━━━━━━━━━━━━━━━━━━\n" + "\n".join(sinais_calls) + "\n\n"
    if sinais_laterais:
        msg += "━━━━━━━━━━━━━━━━━━━━━━━\n🟡 *ESTRUTURAS NEUTRAS*\n━━━━━━━━━━━━━━━━━━━━━━━\n" + "\n".join(sinais_laterais)

    if sinais_travas or sinais_calls or sinais_laterais:
        enviar_telegram(msg)
    else:
        print("🔍 Nenhuma oportunidade alinhada hoje.")

    # Executa o acompanhamento das posições salvas
    checar_posicoes_ativas()

if __name__ == "__main__":
    rodar_master_scanner()
