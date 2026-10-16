# ==============================================================================
# MÓDULO DE MONITORAMENTO DE POSIÇÕES ATIVAS (TRACKER DIÁRIO)
# ==============================================================================

import json
from datetime import datetime

# Exemplo de função para carregar e checar suas operações abertas
def checar_posicoes_ativas():
    print("🔄 Verificando posições abertas na carteira...")
    
    # Se o arquivo posicoes.json existir no repositório, ele faz a leitura
    if not os.path.exists("posicoes.json"):
        print("ℹ️ Nenhum arquivo 'posicoes.json' encontrado para monitorar.")
        return

    with open("posicoes.json", "r") as f:
        posicoes = json.load(f)

    alertas_manejo = []
    hoje = datetime.now()

    for pos in posicoes:
        try:
            ticker = pos["ativo"] + ".SA"
            data_venc = datetime.strptime(pos["data_vencimento"], "%Y-%m-%d")
            data_mora = data_venc - timedelta(days=25) # Janela ideal de 25 dias
            
            # Contagem regressiva de dias
            dias_para_vencimento = (data_venc - hoje).days
            dias_para_manejo = (data_mora - hoje).days

            # Puxa preço atual do ativo na B3
            dados = yf.download(ticker, period="5d", interval="1d", progress=False)
            if dados.empty:
                continue
            
            if isinstance(dados.columns, pd.MultiIndex):
                dados.columns = dados.columns.get_level_values(0)

            preco_atual = float(dados['Close'].iloc[-1])
            strike_v = pos.get("strike_vendida", 0)
            premio_inicial = pos.get("premio_recebido", 1.0)
            alvo_pct = pos.get("alvo_lucro_pct", 70.0) # Padrão de 70% de lucro

            # Estimativa de proteção/distância do strike vendida em Travas de Put
            distancia_strike_pct = ((preco_atual - strike_v) / preco_atual) * 100 if strike_v > 0 else 0

            # CONDIÇÃO 1: Faltam 25 a 21 dias ou menos para o vencimento (Alerta de Tempo)
            alerta_tempo = False
            if dias_para_vencimento <= 25:
                alerta_tempo = True

            # CONDIÇÃO 2: Distância do strike muito favorável (Preço subiu bem e o prêmio derreteu > 70%)
            alerta_lucro = False
            if distancia_strike_pct > 6.0 and dias_para_vencimento <= 30:
                alerta_lucro = True

            # Monta a mensagem se atingir a janela de tempo OU a meta de lucro
            if alerta_tempo or alerta_lucro:
                motivo = "⏳ *JANELA DE 25 DIAS ATINGIDA!*" if alerta_tempo else "💰 *META DE LUCRO ESTIMADA (60%-75%)!*"
                
                alertas_manejo.append(
                    f"🔔 *ALERTA DE MANEJO / ENCERRAMENTO - [{pos['ativo']}]*\n"
                    f"• {motivo}\n"
                    f"• Preço Atual: R$ {preco_atual:.2f} (Distância do Strike: +{distancia_strike_pct:.1f}%)\n"
                    f"📅 *Dias Restantes para Vencimento:* `{dias_para_vencimento} dias`\n"
                    f"🎯 *Recomendação:* Verificar no Home Broker para encerrar/zerar a trava e colocar a gordura no bolso!\n"
                )

        except Exception as e:
            print(f"Erro ao processar posição de {pos.get('ativo')}: {e}")

    if alertas_manejo:
        msg_carteira = "📢 *ACOMPANHAMENTO DIÁRIO DE POSIÇÕES ATIVAS* 📢\n\n" + "\n".join(alertas_manejo)
        enviar_telegram(msg_carteira)
