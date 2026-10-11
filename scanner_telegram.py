# ==============================================================================
# SCANNER DE OPÇÕES COM ALERTA AUTOMÁTICO NO TELEGRAM
# ==============================================================================

import os
import requests
import yfinance as yf
import pandas as pd
import numpy as np

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

TICKERS = [
    "BOVA11.SA", "PETR4.SA", "VALE3.SA", "BBAS3.SA", "ITUB4.SA", 
    "BBDC4.SA", "ITSA4.SA", "ABEV3.SA", "WEGE3.SA", "PRIO3.SA"
]

def enviar_telegram(mensagem):
    if not TOKEN or not CHAT_ID:
        print("⚠️ Credenciais do Telegram não configuradas.")
        return
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID, 
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

def rodar_scanner():
    print("🔎 Executando scanner diário de ativos...")
    oportunidades = []
    
    for ticker in TICKERS:
        try:
            dados = yf.download(ticker, period="1y", interval="1d", progress=False)
            if dados.empty or len(dados) < 60:
                continue
            
            if isinstance(dados.columns, pd.MultiIndex):
                dados.columns = dados.columns.get_level_values(0)
            
            df = dados.copy()
            df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
            df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
            df['SMA50'] = df['Close'].rolling(window=50).mean()
            df['RSI14'] = calcular_rsi(df, 14)
            
            ultimo = df.iloc[-1]
            preco_atual = float(ultimo['Close'])
            ema9 = float(ultimo['EMA9'])
            ema21 = float(ultimo['EMA21'])
            sma50 = float(ultimo['SMA50'])
            rsi = float(ultimo['RSI14'])
            
            tendencia_alta = (ema9 >= ema21) and (ema21 >= sma50)
            perto_m9 = (((preco_atual - ema9) / ema9) * 100) <= 2.5
            rsi_comportado = rsi <= 65
            
            if tendencia_alta and perto_m9 and rsi_comportado:
                nome_limpo = ticker.replace(".SA", "")
                strike_ref = round(preco_atual * 0.90, 2)
                oportunidades.append(f"🟢 *{nome_limpo}* | Preço: R$ {preco_atual:.2f} | Strike Ref: R$ {strike_ref}")
        except Exception as e:
            print(f"Erro ao processar {ticker}: {e}")
            continue
            
    if oportunidades:
        texto = "🚨 *Oportunidades Encontradas (Trava de Alta com Put):*\n\n" + "\n".join(oportunidades)
        enviar_telegram(texto)
    else:
        print("🔍 Nenhuma oportunidade encontrada hoje.")

if __name__ == "__main__":
    rodar_scanner()
  
