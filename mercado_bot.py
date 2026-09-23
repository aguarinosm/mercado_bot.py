import os
import datetime
import requests
import yfinance as yf

# 1. Configuración de Credenciales
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
FRED_API_KEY = os.getenv("FRED_API_KEY")

# 2. Diccionario de Activos Financieros (El Panel Completo)
TICKERS = {
    "S&P 500": "ES=F",
    "Nasdaq 100": "NQ=F",
    "Russell 2000": "RTY=F",
    "Euro Stoxx 50": "^STOXX50E",
    "IBEX 35": "^IBEX",
    "Bono EE.UU. 10 Años": "^TNX",
    "Bono EE.UU. 2 Años": "ZT=F",
    "Índice Dólar (DXY)": "DX-Y.NYB",
    "EUR / USD": "EURUSD=X",
    "Petróleo Brent": "BZ=F",
    "Oro": "GC=F",
    "Bitcoin": "BTC-USD",
    "Índice VIX": "^VIX"
}

TOP_5_TELEGRAM = ["S&P 500", "Nasdaq 100", "Bono EE.UU. 10 Años", "EUR / USD", "Índice VIX"]

def obtener_datos_mercado():
    resumen = {}
    for nombre, ticker in TICKERS.items():
        try:
            data = yf.Ticker(ticker).history(period="2d")
            if len(data) >= 2:
                cierre_hoy = float(data['Close'].iloc[-1])
                cierre_ayer = float(data['Close'].iloc[-2])
                var_pct = ((cierre_hoy - cierre_ayer) / cierre_ayer) * 100
                
                # Ajuste técnico para el rendimiento del bono a 10 años
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
        "DESEMPLEO": "UNRATE",
        "PIB": "A191RL1Q225SBEA",
        "TIPOS_FED": "FEDFUNDS"
    }
    resultados = {}
    for nombre, series_id in series.items():
        url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={FRED_API_KEY}&file_type=json&sort_order=desc&limit=1"
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            val = float(data['observations'][0]['value'])
            resultados[nombre] = val
        except Exception:
            resultados[nombre] = 0.0
    return resultados

def generar_textos_analiticos(mercados, macro):
    # Variables clave para el motor lógico
    vix = mercados.get("Índice VIX", {}).get("precio", 0)
    sp_var = mercados.get("S&P 500", {}).get("var_pct", 0)
    bono_10y = mercados.get("Bono EE.UU. 10 Años", {}).get("precio", 0)
    inflacion = macro.get("INFLACION", 0)
    tipos = macro.get("TIPOS_FED", 0)

    # Lógica Institucional
    if vix > 20 and sp_var < 0:
        titular = "Jornada de aversión al riesgo y presión en las valoraciones."
        analisis_pro = f"La volatilidad repunta (VIX en {vix}) en un contexto de reajuste de carteras. Con los tipos de la FED en {tipos}% y la inflación persistente, el coste de oportunidad medido por el bono a 10 años ({bono_10y}%) sigue asfixiando los múltiplos de la renta variable tecnológica."
        analisis_dummies = "El mercado está en modo 'tormenta'. Los inversores tienen miedo porque el dinero es más caro de pedir prestado (los tipos de interés están altos). Como cuesta más financiarse, las empresas tienen más difícil crecer, y por eso la gente prefiere vender sus acciones y buscar refugios seguros."
    elif bono_10y > 4.2:
        titular = "Los rendimientos de la deuda soberana marcan la pauta."
        analisis_pro = f"El tensionamiento de la curva de tipos sigue drenando liquidez de los activos de riesgo. Un bono a 10 años en el {bono_10y}% compite directamente con la prima de riesgo de la renta variable, limitando los avances del S&P 500 a pesar de la solidez del crecimiento."
        analisis_dummies = "Imagina que el banco te ofrece un plazo fijo con un interés muy alto y seguro. Mucha gente preferirá dejar su dinero ahí en lugar de arriesgarse a montar un negocio. Eso mismo le pasa hoy a la bolsa: la deuda del gobierno paga tan bien que los inversores prefieren no arriesgar en acciones."
    else:
        titular = "Liquidez sostenida y consolidación de niveles en la renta variable."
        analisis_pro = f"Entorno macroeconómico acomodaticio o asimilado por el consenso. La lectura de inflación ({inflacion}) y un mercado laboral estabilizado permiten que los índices directores extiendan su estructura técnica, con el bono a 10 años estabilizado en {bono_10y}%."
        analisis_dummies = "Día de navegación tranquila. La economía crece a buen ritmo pero sin sobrecalentarse, y la inflación parece controlada. Esto es como ir en barco con el viento a favor: las empresas pueden planificar su futuro y los inversores compran acciones con confianza."

    return titular, analisis_pro, analisis_dummies

def enviar_telegram(mensaje):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    requests.post(url, json=payload, timeout=10)

def crear_pagina_web(mercados, macro, fecha, titular, analisis_pro, analisis_dummies):
    # Construcción de las filas de la tabla de cotizaciones
    filas_html = ""
    for nombre, datos in mercados.items():
        color_var = "text-green-400" if datos['var_pct'] >= 0 else "text-red-400"
        signo = "+" if datos['var_pct'] >= 0 else ""
        filas_html += f"""
        <li class='flex justify-between border-b border-indigo-900 py-3 items-center'>
            <span class='font-semibold'>{nombre}</span> 
            <span class='font-mono {color_var}'>{datos['precio']} ({signo}{datos['var_pct']}%)</span>
        </li>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Terminal Macro-Financiero | {fecha}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body {{ background-color: #1C2459; color: #ffffff; font-family: system-ui, -apple-system, sans-serif; }}
        .bg-custom-yellow {{ background-color: #F5FF67; color: #1C2459; }}
    </style>
</head>
<body class="p-4 md:p-8">
    <div class="max-w-5xl mx-auto space-y-8">
        <!-- CABECERA -->
        <header class="border-b border-indigo-800 pb-4">
            <h1 class="text-4xl font-extrabold text-[#F5FF67]">Briefing de Mercados</h1>
            <p class="text-indigo-300 mt-2 text-sm uppercase tracking-wider">Despliegue Analítico • Fecha: {fecha}</p>
        </header>

        <!-- BLOQUE 1: RESUMEN DUMMIES (AMARILLO GIGANTE) -->
        <section class="bg-custom-yellow p-6 md:p-8 rounded-2xl shadow-xl space-y-3 border-4 border-[#F5FF67]">
            <h2 class="text-2xl font-black uppercase tracking-wide">El mercado en 1 minuto</h2>
            <p class="text-lg font-medium leading-relaxed">
                {analisis_dummies}
            </p>
        </section>

        <!-- BLOQUE 2: MONITOR MACRO -->
        <section class="bg-indigo-950 p-6 md:p-8 rounded-2xl border border-indigo-800 shadow-lg space-y-6">
            <h2 class="text-2xl font-bold text-[#F5FF67]">Monitor Macro & FED</h2>
            <p class="text-indigo-100 leading-relaxed text-lg">
                <strong>Análisis Institucional:</strong> {analisis_pro}
            </p>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6">
                <div class="bg-[#1C2459] p-4 rounded-xl border border-indigo-800 text-center">
                    <div class="text-xs text-indigo-400 uppercase tracking-widest mb-1">Tipos FED</div>
                    <div class="text-3xl font-bold">{macro.get('TIPOS_FED', 0)}%</div>
                </div>
                <div class="bg-[#1C2459] p-4 rounded-xl border border-indigo-800 text-center">
                    <div class="text-xs text-indigo-400 uppercase tracking-widest mb-1">Inflación</div>
                    <div class="text-3xl font-bold">{macro.get('INFLACION', 0)}%</div>
                </div>
                <div class="bg-[#1C2459] p-4 rounded-xl border border-indigo-800 text-center">
                    <div class="text-xs text-indigo-400 uppercase tracking-widest mb-1">Desempleo</div>
                    <div class="text-3xl font-bold">{macro.get('DESEMPLEO', 0)}%</div>
                </div>
                <div class="bg-[#1C2459] p-4 rounded-xl border border-indigo-800 text-center">
                    <div class="text-xs text-indigo-400 uppercase tracking-widest mb-1">Var. PIB</div>
                    <div class="text-3xl font-bold">{macro.get('PIB', 0)}%</div>
                </div>
            </div>
        </section>

        <!-- BLOQUE 3: PANEL DE COTIZACIONES -->
        <section class="bg-indigo-950 p-6 md:p-8 rounded-2xl border border-indigo-800 shadow-lg space-y-4">
            <h2 class="text-2xl font-bold text-[#F5FF67]">Cierre de Activos Clave</h2>
            <ul class="space-y-1 mt-4">
                {filas_html}
            </ul>
        </section>

        <!-- BLOQUE 4: DISCLAIMER LEGAL -->
        <footer class="bg-indigo-950 p-6 rounded-2xl text-xs text-indigo-300 border border-indigo-800 space-y-3 mt-12 shadow-inner">
            <p class="uppercase tracking-widest font-bold text-indigo-400">Fuentes y Responsabilidad Legal</p>
            <p><strong>Orígenes de Datos:</strong> Fundamentales macroeconómicos extraídos en tiempo real vía Federal Reserve Economic Data (FRED) del Banco de la Reserva Federal de St. Louis. Variaciones de activos bursátiles obtenidas a través de la API de Yahoo Finance.</p>
            <p><strong>Aviso Legal (Disclaimer):</strong> El presente terminal y las comunicaciones derivadas son de carácter estrictamente educativo y académico. En ningún caso constituyen una recomendación de inversión, oferta de compraventa de instrumentos financieros, ni asesoramiento fiscal o patrimonial. El análisis se realiza basándose en datos históricos y coyunturales sometidos a alta volatilidad. Las decisiones de inversión basadas en este cuadro de mandos son responsabilidad exclusiva del usuario final.</p>
        </footer>
    </div>
</body>
</html>"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

def main():
    fecha = datetime.date.today().strftime("%d-%m-%Y")
    mercados = obtener_datos_mercado()
    macro = obtener_datos_macro()
    
    titular, analisis_pro, analisis_dummies = generar_textos_analiticos(mercados, macro)
    crear_pagina_web(mercados, macro, fecha, titular, analisis_pro, analisis_dummies)
    
    url_web = "https://aguarinosm.github.io/mercado_bot.py/"
    
    # Construcción del mensaje de Telegram
    mensaje_telegram = f"📊 *REPORTE INSTITUCIONAL* — {fecha}\n"
    mensaje_telegram += f"_{titular}_\n\n"
    
    mensaje_telegram += "⏱️ *TERMÓMETROS VITALES:*\n"
    for activo in TOP_5_TELEGRAM:
        datos = mercados.get(activo, {"precio": 0, "var_pct": 0})
        signo = "+" if datos["var_pct"] >= 0 else ""
        mensaje_telegram += f"• {activo}: {datos['precio']} ({signo}{datos['var_pct']}%)\n"
    
    mensaje_telegram += f"\n🏛️ *ANÁLISIS MACRO:* \n{analisis_pro}\n\n"
    mensaje_telegram += f"💡 *EN RESUMEN:* \n{analisis_dummies}\n\n"
    mensaje_telegram += f"🔗 *ACCEDER AL TERMINAL COMPLETO:*\n{url_web}"
    
    enviar_telegram(mensaje_telegram)

if __name__ == "__main__":
    main()
