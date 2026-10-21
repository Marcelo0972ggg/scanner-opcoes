# ==============================================================================
# MASTER TRADER BOT - SCANNER DE OPÇÕES (TRAVAS DE ALTA COM PUT)
# ==============================================================================

import os
import requests
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 1. Leitura das Credenciais dos Secrets do GitHub
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Tickers monitorados para operações de PCS
TICKERS = [
    "BOVA11.SA", "PETR4.SA", "VALE3.SA", "ITUB4.SA", 
    "BBDC4.SA", "BBAS3.SA", "WEGE3.SA", "ABEV3.SA", 
    "PRIO3.SA", "SUZB3.SA"
]

def enviar_mensagem_telegram(texto):
    """Envia a mensagem formatada para o chat do Telegram."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Erro: TELEGRAM_TOKEN ou TELEGRAM_CHAT_ID não configurados nos Secrets.")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": texto,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Erro ao enviar mensagem no Telegram: {e}")
        return False

def analisar_mercado():
    """Realiza a varredura dos ativos e gera o relatório."""
    hoje = datetime.now().strftime("%d/%m/%Y")
    relatorio = f"🚨 <b>Oportunidades Encontradas (Trava de Alta com Put)</b>\n<i>Data: {hoje}</i>\n\n"
    oportunidades_encontradas = 0

    for ticker in TICKERS:
        try:
            ativo = yf.Ticker(ticker)
            hist = ativo.history(period="1y")
            
            if hist.empty:
                continue
                
            preco_atual = hist['Close'].iloc[-1]
            
            # Cálculo de Médias Móveis (SMA 21 e 50)
            mma21 = hist['Close'].rolling(window=21).mean().iloc[-1]
            mma50 = hist['Close'].rolling(window=50).mean().iloc[-1]
            
            # Regra de Segurança: Ativo precisa estar acima da MMA21 ou suporte relevante
            if preco_atual >= mma21 * 0.98: # Margem de tolerância próxima à média
                # Strike de referência OTM (aproximadamente 9% a 12% abaixo do preço atual)
                strike_ref = round(preco_atual * 0.90, 2)
                nome_ativo = ticker.replace(".SA", "")
                
                relatorio += f"🟢 <b>{nome_ativo}</b> | Preço: R$ {preco_atual:.2f} | Strike Ref: R$ {strike_ref:.2f}\n"
                oportunidades_encontradas += 1
                
        except Exception as e:
            print(f"Erro ao processar {ticker}: {e}")
            continue

    if oportunidades_encontradas == 0:
        relatorio += "⚠️ Nenhuma oportunidade dentro dos critérios de segurança encontrada hoje."

    return relatorio

if __name__ == "__main__":
    print("Iniciando varredura do mercado de opções...")
    mensagem = analisar_mercado()
    
    print("Enviando resultado para o Telegram...")
    sucesso = enviar_mensagem_telegram(mensagem)
    
    if sucesso:
        print("Relatório enviado com sucesso!")
    else:
        print("Falha no envio da mensagem.")
