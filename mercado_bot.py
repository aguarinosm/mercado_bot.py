import yfinance as yf
import requests
import json
import os
from datetime import datetime

CONFIG_FILE = "config_bot.json"

def cargar_configuracion():
    token = os.environ.get("TELEGRAM_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    fred_key = os.environ.get("FRED_API_KEY", "")

    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            config["telegram_bot_token"] = token
            config["telegram_chat_id"] = chat_id
            config["fred_api_key"] = fred_key
            return config
    else:
        return {
            "telegram_bot_token": token, 
            "telegram_chat_id": chat_id,      
            "fred_api_key": fred_key,
            "activo": True,
            "ultimo_update_id": 0
        }

def guardar_configuracion(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

class MercadoDatos:
    TICKERS = {
        "US10Y": {"simbolo": "^TNX", "nombre": "Bono EE.UU 10 Años", "tipo": "tasa"},
        "VIX": {"simbolo": "^VIX", "nombre": "Índice VIX (Miedo)", "tipo": "indice"},
        "SP500": {"simbolo": "ES=F", "nombre": "S&P 500 Futuros", "tipo": "indice"},
        "EURUSD": {"simbolo": "EURUSD=X", "nombre": "Euro / Dólar", "tipo": "divisa"},
        "BRENT": {"simbolo": "BZ=F", "nombre": "Petróleo Brent", "tipo": "commodity"}
    }

    @staticmethod
    def obtener_metricas():
        resultados = {}
        for clave, info in MercadoDatos.TICKERS.items():
            try:
                ticker = yf.Ticker(info["simbolo"])
                hist = ticker.history(period="2d")
                if len(hist) >= 2:
                    cierre_ayer = hist['Close'].iloc[-2]
                    precio_actual = hist['Close'].iloc[-1]
                    if clave == "US10Y":
                        cierre_ayer = cierre_ayer / 10
                        precio_actual = precio_actual / 10
                        var_pct = (precio_actual - cierre_ayer) * 100
                        unidad = " bps"
                    else:
                        var_pct = ((precio_actual - cierre_ayer) / cierre_ayer) * 100
                        unidad = "%"

                    resultados[clave] = {
                        "nombre": info["nombre"],
                        "precio": round(precio_actual, 4 if clave == "EURUSD" else 2),
                        "variacion": round(var_pct, 2),
                        "unidad": unidad
                    }
            except Exception as e:
                pass
        return resultados

class MacroDatos:
    SERIES = {
        "INFLACION": {"id": "CPIAUCSL", "nombre": "Inflación Anual"},
        "DESEMPLEO": {"id": "UNRATE", "nombre": "Tasa Desempleo"}
    }

    @staticmethod
    def obtener_datos(api_key):
        if not api_key: return {}
        resultados = {}
        for clave, info in MacroDatos.SERIES.items():
            url = f"https://api.stlouisfed.org/fred/series/observations?series_id={info['id']}&api_key={api_key}&file_type=json&sort_order=desc&limit=1"
            try:
                resp = requests.get(url).json()
                valor = float(resp['observations'][0]['value'])
                if clave == "INFLACION":
                    url_pasado = f"https://api.stlouisfed.org/fred/series/observations?series_id={info['id']}&api_key={api_key}&file_type=json&sort_order=desc&limit=13"
                    resp_pasado = requests.get(url_pasado).json()
                    valor_pasado = float(resp_pasado['observations'][12]['value'])
                    valor = round(((valor - valor_pasado) / valor_pasado) * 100, 1)
                resultados[clave] = {"nombre": info["nombre"], "valor": valor}
            except:
                pass
        return resultados

class InterpreteMercado:
    @staticmethod
    def generar_resumen_global(mercados):
        sp500 = mercados.get("SP500", {}).get("variacion", 0)
        vix = mercados.get("VIX", {}).get("variacion", 0)
        
        if sp500 > 0.3 and vix < 0:
            return "☀️ <b>DÍA SOLEADO:</b> Los inversores están optimistas hoy. Las bolsas apuntan a subidas y el 'índice del miedo' (VIX) está bajando. Hay apetito por comprar y el mercado está tranquilo."
        elif sp500 < -0.3 and vix > 2:
            return "⛈️ <b>DÍA TORMENTOSO:</b> Hay nerviosismo general. Las bolsas caen y los inversores están comprando activos seguros para protegerse. Un día para tener precaución."
        elif vix > 10:
            return "⚠️ <b>ALERTA DE VOLATILIDAD:</b> Pánico a corto plazo. El mercado está asustado por noticias recientes y los precios se van a mover de forma muy brusca hoy."
        else:
            return "⛅ <b>DÍA TRANQUILO:</b> Movimientos moderados. Los grandes inversores están a la espera de nuevas noticias sin tomar decisiones precipitadas."

    @staticmethod
    def analizar_mercado(clave, datos):
        var = datos["variacion"]
        alcista = var > 0
        if clave == "US10Y":
            pro = "Repunte de tires. Penaliza duraciones largas." if alcista else "Compresión de tires. Alivio en la tasa de descuento."
            gen = "Sube el interés de la deuda. Encarece préstamos y enfría la bolsa." if alcista else "Cae el interés de la deuda. Dinero más barato."
        elif clave == "SP500":
            pro = "Futuros en verde. Flujos de entrada." if alcista else "Futuros en rojo. Presión vendedora."
            gen = "Wall Street apunta al alza. Optimismo." if alcista else "Wall Street apunta a caídas. Predominan las ventas."
        else:
            pro = f"Variación del {var}{datos['unidad']}."
            gen = f"Movimiento del {var}{datos['unidad']}."
        return pro, gen

def crear_pagina_web(mercados, macro, resumen, fecha):
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Dashboard FEBF</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-50 p-4 md:p-8 font-sans text-slate-800">
    <div class="max-w-4xl mx-auto">
        <header class="text-center mb-8"><h1 class="text-3xl font-bold">Tracker Matutino</h1><p>Actualizado: {fecha}</p></header>
        <div class="bg-white p-6 rounded-xl shadow-sm mb-8 border border-slate-200">
            <h2 class="text-xl font-bold text-indigo-700 mb-2">📝 Resumen "Para Dummies"</h2>
            <p class="text-lg">{resumen.replace('<b>', '').replace('</b>', '')}</p>
        </div>
        <div class="grid md:grid-cols-2 gap-6">
            <div><h2 class="text-xl font-bold mb-4 border-b pb-2">📈 Mercados</h2>
"""
    for c, d in mercados.items():
        color = "text-green-600" if d['variacion'] > 0 else "text-red-600"
        if c in ["US10Y", "VIX"]: color = "text-red-600" if d['variacion'] > 0 else "text-green-600"
        pro, gen = InterpreteMercado.analizar_mercado(c, d)
        html += f"<div class='bg-white p-4 rounded-lg shadow-sm border mb-4'><div class='flex justify-between font-bold mb-2'><span>{d['nombre']}</span><span class='{color}'>{d['precio']} ({d['variacion']}{d['unidad']})</span></div><p class='text-sm mb-1'><b>PRO:</b> {pro}</p><p class='text-sm text-slate-500'><b>GEN:</b> {gen}</p></div>"
    
    html += "</div><div><h2 class='text-xl font-bold mb-4 border-b pb-2'>🇺🇸 Macro</h2>"
    for c, d in macro.items():
        html += f"<div class='bg-white p-4 rounded-lg shadow-sm border mb-4'><div class='flex justify-between font-bold mb-2'><span>{d['nombre']}</span><span class='text-blue-600'>{d['valor']}%</span></div></div>"
        
    html += """</div></div></div></body></html>"""
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

def enviar_telegram(config, mensaje):
    if config["telegram_bot_token"]:
        url = f"https://api.telegram.org/bot{config['telegram_bot_token']}/sendMessage"
        requests.post(url, json={"chat_id": config["telegram_chat_id"], "text": mensaje, "parse_mode": "HTML"})

def main():
    config = cargar_configuracion()
    if not config["activo"]: return
    
    mercados = MercadoDatos.obtener_metricas()
    macro = MacroDatos.obtener_datos(config["fred_api_key"])
    fecha = datetime.now().strftime("%d/%m/%Y")
    resumen = InterpreteMercado.generar_resumen_global(mercados)
    
    crear_pagina_web(mercados, macro, resumen, fecha)
    
    mensaje = f"<b>📊 REPORTE DE MERCADOS | {fecha}</b>\n\n{resumen}\n\n<b>📈 COTIZACIONES</b>\n"
    for c, d in mercados.items():
        emoji = "🔴" if d['variacion'] < 0 else "🟢"
        if c in ["US10Y", "VIX"]: emoji = "🔴" if d['variacion'] > 0 else "🟢"
        pro, gen = InterpreteMercado.analizar_mercado(c, d)
        mensaje += f"{emoji} <b>{d['nombre']}</b>: {d['precio']} ({d['variacion']}{d['unidad']})\n🏛️ <i>{pro}</i>\n💡 <i>{gen}</i>\n\n"
        
    mensaje += f"🌐 <b>Ver Web Completa:</b>\nhttps://{os.environ.get('GITHUB_ACTOR', 'tu-usuario')}.github.io/mercado_bot.py/"
    enviar_telegram(config, mensaje)

if __name__ == "__main__":
    main()
