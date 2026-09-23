import os
import datetime
import requests
import yfinance as yf

# 1. Configuración de Credenciales desde las Variables de Entorno (Caja Fuerte de GitHub)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
FRED_API_KEY = os.getenv("FRED_API_KEY")

# 2. Diccionario de Activos Financieros
TICKERS = {
    "S&P 500 Futuros": "ES=F",
    "Nasdaq 100": "NQ=F",
    "Bono 10Y EE.UU.": "^TNX",
    "Índice VIX": "^VIX",
    "Euro / Dólar": "EURUSD=X",
    "Petróleo Brent": "BZ=F",
    "Oro": "GC=F"
}

def obtener_datos_mercado():
    resumen = {}
    for nombre, ticker in TICKERS.items():
        try:
            data = yf.Ticker(ticker).history(period="2d")
            if len(data) >= 2:
                cierre_hoy = float(data['Close'].iloc[-1])
                cierre_ayer = float(data['Close'].iloc[-2])
                var_pct = ((cierre_hoy - cierre_ayer) / cierre_ayer) * 100
                
                if ticker == "^TNX":
                    cierre_hoy = cierre_hoy / 10
                    
                resumen[nombre] = {
                    "precio": round(cierre_hoy, 2),
                    "var_pct": round(var_pct, 2)
                }
        except Exception:
            resumen[nombre] = {"precio": 0.0, "var_pct": 0.0}
    return resumen

def obtener_datos_macro():
    series = {
        "INFLACION": "CPIAUCSL",
        "PIB": "A191RL1Q225SBEA",
        "DESEMPLEO": "UNRATE"
    }
    resultados = {}
    for nombre, series_id in series.items():
        url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={FRED_API_KEY}&file_type=json&sort_order=desc&limit=1"
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            val = float(data['observations'][0]['value'])
            fecha = data['observations'][0]['date']
            resultados[nombre] = {"valor": val, "fecha": fecha}
        except Exception:
            resultados[nombre] = {"valor": 0.0, "fecha": "N/A"}
    return resultados

def enviar_telegram(mensaje):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram no configurado.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Error enviando Telegram: {e}")

def crear_pagina_web(mercados, macro, fecha):
    inf = macro.get("INFLACION", {}).get("valor", 0)
    des = macro.get("DESEMPLEO", {}).get("valor", 0)
    pib = macro.get("PIB", {}).get("valor", 0)

    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard Financiero FEBF - {fecha}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body {{ background-color: #1C2459; color: #ffffff; }}
        .bg-custom-blue {{ background-color: #1C2459; }}
        .bg-custom-yellow {{ background-color: #F5FF67; color: #1C2459; }}
    </style>
</head>
<body class="p-6 md:p-12">
    <div class="max-w-4xl mx-auto space-y-8">
        <header class="border-b border-indigo-800 pb-6">
            <h1 class="text-3xl font-extrabold text-[#F5FF67]">Informe Bursátil Diario & Macro</h1>
            <p class="text-indigo-200 mt-2">Edición Académica FEBF | Fecha: {fecha}</p>
        </header>

        <section class="bg-indigo-950 p-6 rounded-xl border border-indigo-800 shadow-lg space-y-4">
            <h2 class="text-xl font-bold text-[#F5FF67]">1. Análisis de Contexto: La Maquinaria del Mercado</h2>
            <p class="text-gray-300 leading-relaxed">
                Los mercados financieros operan bajo la ley de las expectativas futuras. Hoy el foco principal recae sobre la interacción entre los tipos de interés de la Reserva Federal (FED) y la renta variable. Cuando el bono a 10 años se tensiona, los flujos institucionales abandonan activos de crecimiento y buscan refugio.
            </p>
        </section>

        <section class="bg-indigo-950 p-6 rounded-xl border border-indigo-800 shadow-lg space-y-4">
            <h2 class="text-xl font-bold text-[#F5FF67]">2. Indicadores Macro Clave</h2>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4 text-center">
                <div class="bg-indigo-900 p-4 rounded-lg">
                    <div class="text-sm text-indigo-300">Inflación (IPC Anual)</div>
                    <div class="text-2xl font-bold text-white">{inf}%</div>
                </div>
                <div class="bg-indigo-900 p-4 rounded-lg">
                    <div class="text-sm text-indigo-300">Tasa de Desempleo</div>
                    <div class="text-2xl font-bold text-white">{des}%</div>
                </div>
                <div class="bg-indigo-900 p-4 rounded-lg">
                    <div class="text-sm text-indigo-300">Crecimiento PIB</div>
                    <div class="text-2xl font-bold text-white">{pib}%</div>
                </div>
            </div>
        </section>

        <section class="bg-indigo-950 p-6 rounded-xl border border-indigo-800 shadow-lg space-y-4">
            <h2 class="text-xl font-bold text-[#F5FF67]">3. Cotizaciones en Tiempo Real</h2>
            <ul class="space-y-2">
"""
    for nombre, datos in mercados.items():
        html_content += f"                <li class='flex justify-between border-b border-indigo-900 py-2'><span>{nombre}</span> <span class='font-mono font-bold'>{datos['precio']} ({datos['var_pct']}%)</span></li>\n"

    html_content += f"""            </ul>
        </section>

        <section class="bg-[#F5FF67] text-[#1C2459] p-6 rounded-xl shadow-xl font-medium space-y-2">
            <h2 class="text-2xl font-black uppercase tracking-wide">Resumen Ejecutivo (Para todos los públicos)</h2>
            <p class="leading-relaxed">
                El mercado hoy funciona como una gran balanza entre el miedo a la inflación y las decisiones de los Bancos Centrales. Si la economía va demasiado bien, los precios suben y los tipos de interés se mantienen altos, lo que enfría las bolsas. Este panel recopila los datos oficiales para entender de un vistazo si el dinero fluye con seguridad o si hay tormenta en el horizonte.
            </p>
        </section>

        <footer class="text-xs text-indigo-300 border-t border-indigo-800 pt-6 space-y-2">
            <p><strong>Fuentes oficiales:</strong> Los datos macroeconómicos se obtienen directamente de la Reserva Federal de St. Louis (FRED) y las cotizaciones de mercado proceden de Yahoo Finance.</p>
            <p><strong>Aviso Legal (Disclaimer):</strong> Este documento tiene fines puramente académicos y educativos en el marco de la formación en la FEBF. No constituye asesoramiento financiero, recomendación de compraventa ni oferta de inversión. Los datos reflejan información histórica y de mercado sujeta a volatilidad.</p>
        </footer>
    </div>
</body>
</html>"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

def main():
    fecha = datetime.date.today().strftime("%Y-%m-%d")
    mercados = obtener_datos_mercado()
    macro = obtener_datos_macro()
    
    crear_pagina_web(mercados, macro, fecha)
    
    url_web = f"https://aguarinosm.github.io/mercado_bot.py/"
    
    mensaje = (
        f"📊 *REPORTE MATUTINO FEBF* — *{fecha}*\n\n"
        f"🏛️ *Contexto Profesional:*\n"
        f"Sesión condicionada por la lectura de tipos de interés y la evolución de los rendimientos de los bonos soberanos. "
        f"La inflación se sitúa en el {macro.get('INFLACION', {}).get('valor', 0)}% y el desempleo en el {macro.get('DESEMPLEO', {}).get('valor', 0)}%.\n\n"
        f"💡 *Explicación Sencilla (Para todos):*\n"
        f"Hoy el mercado vigila de cerca cómo se mueve el dinero entre los bancos y las empresas. "
        f"Si los costes de financiación suben, los inversores son más cautos a la hora de comprar acciones.\n\n"
        f"🔗 *Panel de Control Web:*\n"
        f"Consulta el informe completo, las fuentes y el aviso legal en el siguiente enlace:\n{url_web}"
    )
    
    enviar_telegram(mensaje)

if __name__ == "__main__":
    main()
