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
            return "☀️ <b>DÍA SOLEADO:</b> Optimismo en las mesas de inversión. Los índices apuntan al alza y el VIX se comprime, indicando apetito por riesgo."
        elif sp500 < -0.3 and vix > 2:
            return "⛈️ <b>DÍA TORMENTOSO:</b> Aversión al riesgo generalizada. Las bolsas corrigen y los inversores buscan cobertura, disparando el índice del miedo."
        elif vix > 10:
            return "⚠️ <b>ALERTA DE VOLATILIDAD:</b> Pánico a corto plazo. Expectativa de movimientos bruscos debido a eventos macroeconómicos o geopolíticos."
        else:
            return "⛅ <b>DÍA TRANQUILO:</b> Consolidación de niveles. Sesión de transición sin catalizadores claros, a la espera de nuevos datos macro."

    @staticmethod
    def generar_analisis_profesional(mercados, macro):
        inflacion = macro.get("INFLACION", {}).get("valor", "N/A")
        bono = mercados.get("US10Y", {}).get("precio", "N/A")
        
        texto = "<b>🔬 ANÁLISIS MACRO (PROFESIONAL)</b>\n"
        texto += f"El mercado descuenta un escenario complejo. Con la inflación en el {inflacion}%, la Reserva Federal mantiene un tono vigilante. "
        texto += f"El tramo largo de la curva curva, reflejado en el T-Note a 10 años situándose en el {bono}%, presiona el <i>equity risk premium</i>. "
        texto += "Vigilamos de cerca los flujos hacia activos de protección ante posibles disrupciones en la liquidez."
        return texto

    @staticmethod
    def generar_analisis_dummies():
        return """<b>💡 TRADUCCIÓN PARA DUMMIES</b>
Imagina que la economía es un gran barco. La <b>Reserva Federal</b> (el banco central) es el capitán. Si el barco va demasiado rápido y los motores se calientan (inflación alta), el capitán frena subiendo los <b>tipos de interés</b>. Cuando esto pasa, los préstamos para empresas y familias son más caros, lo que suele hacer que la bolsa baje porque hay menos dinero circulando para invertir."""

    @staticmethod
    def analizar_mercado(clave, datos):
        var = datos["variacion"]
        alcista = var > 0
        if clave == "US10Y":
            pro = "Repunte de yields. Ampliación del descuento de flujos (DCF)." if alcista else "Compresión de tires. Alivio en la tasa de descuento."
            gen = "Sube el interés de la deuda. Encarece préstamos." if alcista else "Cae el interés de la deuda. Dinero más barato."
        elif clave == "SP500":
            pro = "Futuros en verde. Flujos de entrada." if alcista else "Futuros en rojo. Presión vendedora."
            gen = "Wall Street apunta al alza. Optimismo." if alcista else "Wall Street apunta a caídas. Predominan las ventas."
        else:
            pro = f"Variación direccional del {var}{datos['unidad']}."
            gen = f"Movimiento del {var}{datos['unidad']}."
        return pro, gen

def crear_pagina_web(mercados, macro, resumen, fecha):
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Informe FEBF - Tracker Diario</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .febf-blue {{ background-color: #1C2459; }}
        .febf-blue-text {{ color: #1C2459; }}
        .febf-yellow {{ background-color: #F5FF67; }}
        .febf-yellow-text {{ color: #D1DB2A; }} /* Tono más oscuro para contraste en texto */
        body {{ font-family: system-ui, -apple-system, sans-serif; background-color: #f4f4f5; }}
    </style>
</head>
<body class="text-slate-800">
    
    <!-- Hero Header -->
    <header class="febf-blue text-white py-12 px-6 shadow-lg">
        <div class="max-w-5xl mx-auto flex flex-col md:flex-row justify-between items-center">
            <div>
                <h1 class="text-4xl font-extrabold tracking-tight mb-2">Monitor de Mercados FEBF</h1>
                <p class="text-lg opacity-90 font-light">Análisis Diario Cuantitativo y Fundamental</p>
            </div>
            <div class="mt-6 md:mt-0 bg-white/10 px-4 py-2 rounded-lg border border-white/20">
                <span class="font-mono text-sm tracking-widest uppercase opacity-80">Fecha de Reporte</span>
                <p class="text-xl font-bold febf-yellow-text">{fecha}</p>
            </div>
        </div>
    </header>

    <main class="max-w-5xl mx-auto p-6 mt-8 space-y-10">

        <!-- Termómetro Diario -->
        <section class="bg-white rounded-2xl shadow-sm border border-slate-200 p-8">
            <h2 class="text-2xl font-bold febf-blue-text mb-4 border-b pb-2">El Termómetro de Hoy</h2>
            <p class="text-lg leading-relaxed text-slate-700">{resumen.replace('<b>', '').replace('</b>', '')}</p>
        </section>

        <!-- Análisis Profundo de Factores Clave -->
        <section class="grid md:grid-cols-2 gap-8">
            
            <div class="bg-white rounded-2xl shadow-sm border border-slate-200 p-8">
                <h3 class="text-xl font-bold febf-blue-text mb-4 flex items-center gap-2">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    Contexto Macroeconómico (FED)
                </h3>
                <p class="text-slate-600 mb-4">El mercado vigila obsesivamente a la Reserva Federal y al Banco Central Europeo. Sus decisiones sobre el coste del dinero determinan la liquidez global.</p>
                <div class="space-y-3">
                    <div class="flex justify-between items-center p-3 bg-slate-50 rounded-lg border border-slate-100">
                        <span class="font-semibold text-slate-700">Inflación (IPC):</span>
                        <span class="text-lg font-mono font-bold febf-blue-text">{macro.get("INFLACION", {}).get("valor", "N/A")}%</span>
                    </div>
                    <div class="flex justify-between items-center p-3 bg-slate-50 rounded-lg border border-slate-100">
                        <span class="font-semibold text-slate-700">Tasa de Desempleo:</span>
                        <span class="text-lg font-mono font-bold febf-blue-text">{macro.get("DESEMPLEO", {}).get("valor", "N/A")}%</span>
                    </div>
                </div>
            </div>

            <div class="bg-white rounded-2xl shadow-sm border border-slate-200 p-8">
                <h3 class="text-xl font-bold febf-blue-text mb-4 flex items-center gap-2">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path></svg>
                    Cotizaciones en Directo
                </h3>
                <div class="space-y-3">
"""
    for c, d in mercados.items():
        es_positivo = d['variacion'] > 0
        if c in ["US10Y", "VIX"]: es_positivo = not es_positivo # Invertir lógica para bonos y VIX
        color_badge = "bg-green-100 text-green-800 border-green-200" if es_positivo else "bg-red-100 text-red-800 border-red-200"
        
        html += f"""
                    <div class="flex justify-between items-center p-3 hover:bg-slate-50 transition-colors border-b border-slate-100 last:border-0">
                        <span class="font-medium text-slate-800">{d['nombre']}</span>
                        <div class="flex items-center gap-3">
                            <span class="font-mono text-slate-600">{d['precio']}</span>
                            <span class="px-2 py-1 rounded text-sm font-bold border {color_badge}">
                                {d['variacion']}{d['unidad']}
                            </span>
                        </div>
                    </div>"""
    
    html += """
                </div>
            </div>
        </section>

        <!-- Conclusión Resumida (Dummies) -->
        <section class="febf-yellow rounded-2xl shadow-md border border-yellow-400/50 p-8 relative overflow-hidden">
            <div class="relative z-10">
                <h2 class="text-2xl font-extrabold text-slate-900 mb-3 flex items-center gap-2">
                    <span>💡</span> ¿Qué significa todo esto? (Resumen Ejecutivo)
                </h2>
                <p class="text-lg text-slate-800 font-medium leading-relaxed">
                    Si eres un inversor a largo plazo, el dato más importante de hoy es la relación entre los <b>Tipos de Interés</b> y la <b>Inflación</b>. 
                    Cuando los precios suben rápido (inflación), los bancos centrales encarecen los préstamos para enfriar la economía. 
                    Esto hace que las empresas ganen menos dinero y la bolsa sufra. Hoy, la bolsa se mueve reaccionando a las pistas que indican 
                    si el dinero será más barato o más caro en los próximos meses.
                </p>
            </div>
            <!-- Decoración gráfica -->
            <div class="absolute -right-10 -bottom-10 opacity-10">
                <svg class="w-64 h-64 febf-blue-text" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/></svg>
            </div>
        </section>

    </main>

    <footer class="bg-slate-900 text-slate-400 py-10 px-6 mt-12 text-sm shadow-inner">
        <div class="max-w-5xl mx-auto space-y-6">
            
            <div class="border-b border-slate-700 pb-6 mb-2">
                <p class="font-bold text-slate-300 mb-2 flex items-center gap-2">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    Fuentes de Información
                </p>
                <ul class="list-disc list-inside space-y-1 text-slate-400">
                    <li>Cotizaciones de mercado: <a href="https://finance.yahoo.com/" target="_blank" class="underline hover:text-white transition-colors">Yahoo Finance API</a> (los datos pueden presentar retraso).</li>
                    <li>Datos macroeconómicos oficiales: <a href="https://fred.stlouisfed.org/" target="_blank" class="underline hover:text-white transition-colors">Federal Reserve Economic Data (FRED)</a>, Banco de la Reserva Federal de St. Louis.</li>
                </ul>
            </div>

            <div>
                <p class="font-bold text-slate-300 mb-2 flex items-center gap-2">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3"></path></svg>
                    Aviso Legal (Disclaimer)
                </p>
                <p class="text-xs leading-relaxed text-slate-500 text-justify">
                    Este panel de control y el bot de Telegram asociado son un proyecto estrictamente académico. La información aquí reflejada tiene un propósito única y exclusivamente <b>educativo e informativo</b>. 
                    Bajo ninguna circunstancia este contenido debe interpretarse como asesoramiento financiero, recomendación de inversión, ni sugerencia de compra o venta de ningún activo o producto financiero. 
                    El mercado de valores conlleva un alto riesgo y es posible perder parte o la totalidad del capital invertido. 
                    Ni el desarrollador de esta herramienta ni instituciones asociadas se hacen responsables de las decisiones de inversión tomadas basadas en los datos proporcionados, los cuales podrían contener errores, inexactitudes o retrasos. 
                    Por favor, consulte siempre a un asesor financiero certificado antes de tomar decisiones de inversión.
                </p>
            </div>

            <div class="text-center pt-6 text-xs font-mono opacity-50 mt-6 border-t border-slate-800">
                &copy; 2026 Proyecto Analítico | Actualizado de forma automatizada mediante GitHub Actions
            </div>
        </div>
    </footer>

</body>
</html>"""
    
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
    analisis_pro = InterpreteMercado.generar_analisis_profesional(mercados, macro)
    analisis_gen = InterpreteMercado.generar_analisis_dummies()
    
    crear_pagina_web(mercados, macro, resumen, fecha)
    
    mensaje = f"<b>📊 REPORTE FEBF | {fecha}</b>\n\n{resumen}\n\n{analisis_pro}\n\n{analisis_gen}\n\n<b>📈 COTIZACIONES</b>\n"
    for c, d in mercados.items():
        emoji = "🔴" if d['variacion'] < 0 else "🟢"
        if c in ["US10Y", "VIX"]: emoji = "🔴" if d['variacion'] > 0 else "🟢"
        pro, gen = InterpreteMercado.analizar_mercado(c, d)
        mensaje += f"{emoji} <b>{d['nombre']}</b>: {d['precio']} ({d['variacion']}{d['unidad']})\n"
        
    mensaje += f"\n🌐 <b>Dashboard Web Completo:</b>\nhttps://{os.environ.get('GITHUB_ACTOR', 'tu-usuario')}.github.io/mercado_bot.py/"
    mensaje += f"\n\n<i>⚠️ Aviso legal: Información con fines puramente académicos y educativos. No constituye recomendación de inversión.</i>"
    enviar_telegram(config, mensaje)

if __name__ == "__main__":
    main()
```
