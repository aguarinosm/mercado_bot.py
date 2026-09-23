import yfinance as yf
import requests
import json
import os
from datetime import datetime

CONFIG_FILE = "config_bot.json"

def cargar_configuracion():
    """Carga los tokens desde los secretos de GitHub (Variables de Entorno)."""
    token = os.environ.get("TELEGRAM_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    fred_key = os.environ.get("FRED_API_KEY", "")

    # Mantenemos un archivo local por si se quiere expandir con comandos de pausa en el futuro
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
            "activo": True
        }

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
        """Extrae cotizaciones en tiempo real usando yfinance."""
        resultados = {}
        for clave, info in MercadoDatos.TICKERS.items():
            try:
                ticker = yf.Ticker(info["simbolo"])
                hist = ticker.history(period="2d")
                if len(hist) >= 2:
                    cierre_ayer = hist['Close'].iloc[-2]
                    precio_actual = hist['Close'].iloc[-1]
                    
                    # Ajuste matemático para el Bono a 10 años
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
                resultados[clave] = {"nombre": info["nombre"], "precio": 0, "variacion": 0, "unidad": ""}
        return resultados

class MacroDatos:
    SERIES = {
        "INFLACION": {"id": "CPIAUCSL", "nombre": "Inflación Anual (IPC)"},
        "DESEMPLEO": {"id": "UNRATE", "nombre": "Tasa Desempleo"},
        "PIB": {"id": "A191RL1Q225SBEA", "nombre": "Crecimiento PIB (Trimestral)"}
    }

    @staticmethod
    def obtener_datos(api_key):
        """Se conecta a la base de datos oficial de la Reserva Federal (FRED)."""
        if not api_key: 
            return {}
        
        resultados = {}
        for clave, info in MacroDatos.SERIES.items():
            url = f"https://api.stlouisfed.org/fred/series/observations?series_id={info['id']}&api_key={api_key}&file_type=json&sort_order=desc&limit=1"
            try:
                resp = requests.get(url).json()
                valor = float(resp['observations'][0]['value'])
                fecha = resp['observations'][0]['date']
                
                # Para la inflación, calculamos la variación interanual aproximada
                if clave == "INFLACION":
                    url_pasado = f"https://api.stlouisfed.org/fred/series/observations?series_id={info['id']}&api_key={api_key}&file_type=json&sort_order=desc&limit=13"
                    resp_pasado = requests.get(url_pasado).json()
                    valor_pasado = float(resp_pasado['observations'][12]['value'])
                    valor = round(((valor - valor_pasado) / valor_pasado) * 100, 1)
                    
                resultados[clave] = {"nombre": info["nombre"], "valor": valor, "fecha": fecha}
            except Exception as e:
                resultados[clave] = {"nombre": info["nombre"], "valor": "N/A", "fecha": "N/A"}
        return resultados

class InterpreteMercado:
    @staticmethod
    def generar_analisis_telegram(mercados, macro):
        """Genera el texto principal e informativo para el chat de Telegram."""
        sp500 = mercados.get("SP500", {}).get("variacion", 0)
        vix = mercados.get("VIX", {}).get("variacion", 0)
        bono = mercados.get("US10Y", {}).get("precio", 0)
        inflacion = macro.get("INFLACION", {}).get("valor", "N/A")
        
        texto_profesional = "<b>🏛️ ANÁLISIS MACROECONÓMICO (PROFESIONAL)</b>\n"
        texto_dummies = "<b>💡 TRADUCCIÓN PARA TODOS LOS PÚBLICOS</b>\n"

        if sp500 > 0 and bono < 4.5:
            texto_profesional += f"Sesión marcada por el apetito por el riesgo (Risk-On). Los futuros del S&P apuntan al alza impulsados por una estabilización en la renta fija. Con el T-Note a 10 años en el {bono}%, la presión sobre el coste de capital disminuye, permitiendo una expansión de múltiplos. El mercado asimila una inflación del {inflacion}% esperando posturas monetarias menos restrictivas por parte de los Bancos Centrales.\n"
            texto_dummies += "Hoy es un buen día en los mercados. Como los intereses que cobran los bancos por prestar dinero están estables, las empresas pueden financiarse de forma barata. Esto anima a los inversores a comprar acciones. La inflación parece estar controlada, por lo que no hay pánico a corto plazo.\n"
        elif sp500 < 0 and bono > 4.5:
            texto_profesional += f"Sesión correctiva dominada por la aversión al riesgo (Risk-Off). El repunte del T-Note hasta el {bono}% endurece las condiciones financieras, impactando negativamente en la valoración por flujos de caja descontados (DCF), especialmente en *Growth*. La inflación anclada en {inflacion}% reduce el margen de maniobra de la FED para inyectar liquidez.\n"
            texto_dummies += "Día de caídas en bolsa. Los tipos de interés de la deuda pública están subiendo, lo que significa que el dinero se vuelve más caro. Los inversores prefieren vender sus acciones, que tienen más riesgo, y guardar el dinero en bonos del Estado que pagan buenos intereses de forma segura.\n"
        else:
            texto_profesional += f"Jornada de consolidación y rebalanceo de carteras. Volatilidad contenida con el VIX variando un {vix}%. Los operadores mantienen cautela a la espera de nuevos catalizadores macroeconómicos que definan la senda de tipos de la FED frente a una inflación del {inflacion}%.\n"
            texto_dummies += "Día tranquilo en Wall Street. No hay noticias lo suficientemente fuertes como para provocar grandes subidas o bajadas. Los grandes inversores están esperando a que el gobierno publique nuevos datos sobre empleo o precios antes de tomar decisiones importantes con su dinero.\n"

        return texto_profesional, texto_dummies

def crear_pagina_web(mercados, macro, fecha):
    """Crea un archivo HTML interactivo, profesional y extenso con Disclaimer."""
    
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard FEBF - Mercado y Macro</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .bg-febf-blue {{ background-color: #1C2459; }}
        .text-febf-blue {{ color: #1C2459; }}
        .bg-febf-yellow {{ background-color: #F5FF67; }}
        .text-febf-yellow {{ color: #D1DB2A; }}
        .border-febf-yellow {{ border-color: #F5FF67; }}
        body {{ font-family: system-ui, -apple-system, sans-serif; background-color: #f8fafc; }}
    </style>
</head>
<body class="text-slate-800 antialiased">
    
    <!-- Cabecera -->
    <header class="bg-febf-blue text-white py-12 px-6 shadow-xl border-b-4 border-febf-yellow">
        <div class="max-w-6xl mx-auto flex flex-col md:flex-row justify-between items-center">
            <div>
                <h1 class="text-4xl font-extrabold tracking-tight mb-2">Monitor Institucional de Mercados</h1>
                <p class="text-lg opacity-90 font-light">Análisis Cuantitativo y Entorno Macroeconómico - FEBF</p>
            </div>
            <div class="mt-6 md:mt-0 bg-white/10 px-5 py-3 rounded-lg border border-white/20 text-center">
                <span class="font-mono text-sm tracking-widest uppercase opacity-80 block">Fecha del Reporte</span>
                <span class="text-2xl font-bold text-febf-yellow">{fecha}</span>
            </div>
        </div>
    </header>

    <main class="max-w-6xl mx-auto p-6 mt-8 space-y-10">

        <!-- Explicación Extensa de Factores Condicionantes -->
        <section class="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
            <div class="bg-slate-50 border-b border-slate-200 p-6">
                <h2 class="text-2xl font-bold text-febf-blue flex items-center gap-2">
                    <svg class="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z"></path></svg>
                    El Motor de la Economía: Condicionantes de Hoy
                </h2>
            </div>
            <div class="p-8 space-y-6">
                <p class="text-lg leading-relaxed text-slate-700">El comportamiento de las bolsas mundiales no es aleatorio; es una respuesta matemática a las condiciones de liquidez. Actualmente, el mercado está condicionado por las siguientes dinámicas institucionales:</p>
                
                <div class="grid md:grid-cols-2 gap-8">
                    <!-- Bloque FED -->
                    <div class="p-6 bg-slate-50 rounded-xl border border-slate-100">
                        <h3 class="text-xl font-bold text-slate-800 mb-3">🏦 La Reserva Federal (FED) y los Tipos</h3>
                        <p class="text-slate-600 leading-relaxed text-justify">
                            La FED actúa como el "banco de los bancos". Cuando la inflación es alta, la FED sube los <b>Tipos de Interés</b> (el precio del dinero). Esto encarece los préstamos para empresas (frenando su crecimiento) y para las familias (frenando el consumo). El mercado vigila obsesivamente cada discurso de su presidente, Jerome Powell, buscando pistas. Si insinúan que los tipos seguirán altos, el dinero huye de la bolsa hacia activos más seguros.
                        </p>
                    </div>
                    
                    <!-- Bloque Empleo e Inflación -->
                    <div class="p-6 bg-slate-50 rounded-xl border border-slate-100">
                        <h3 class="text-xl font-bold text-slate-800 mb-3">📉 Empleo, Inflación y Crecimiento</h3>
                        <p class="text-slate-600 leading-relaxed text-justify">
                            Irónicamente, para el mercado financiero, <i>"las buenas noticias a veces son malas noticias"</i>. Si el dato de <b>Tasa de Desempleo ({macro.get('DESEMPLEO', {{}}).get('valor', 'N/A')}%)</b> es muy bajo, significa que la economía está fuerte. Sin embargo, una economía demasiado fuerte puede provocar más <b>Inflación ({macro.get('INFLACION', {{}}).get('valor', 'N/A')}%)</b>, lo que obligaría a la FED a subir más los tipos, asustando a los inversores. Por ello, el mercado busca un equilibrio perfecto: una economía que crezca, pero sin calentarse.
                        </p>
                    </div>
                </div>
            </div>
        </section>

        <!-- Tarjetas de Cotización en Directo -->
        <section>
            <h2 class="text-2xl font-bold text-febf-blue mb-6">Radiografía de Activos en Directo</h2>
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
"""
    for c, d in mercados.items():
        es_positivo = d['variacion'] > 0
        if c in ["US10Y", "VIX"]: es_positivo = not es_positivo # Invertimos lógica para bonos y VIX
        color_bg = "bg-emerald-50 border-emerald-200" if es_positivo else "bg-rose-50 border-rose-200"
        color_txt = "text-emerald-700" if es_positivo else "text-rose-700"
        icono = "📈" if d['variacion'] > 0 else "📉"
        
        html += f"""
                <div class="bg-white rounded-xl shadow-sm border p-6 flex flex-col hover:shadow-md transition-shadow">
                    <span class="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-1">{c}</span>
                    <span class="text-xl font-bold text-slate-800 mb-4">{d['nombre']}</span>
                    <div class="mt-auto flex justify-between items-end">
                        <span class="text-3xl font-mono font-bold text-febf-blue">{d['precio']}</span>
                        <span class="font-semibold text-lg {color_bg} {color_txt} border px-2 py-1 rounded">
                            {icono} {d['variacion']}{d['unidad']}
                        </span>
                    </div>
                </div>
"""
    
    html += """
            </div>
        </section>

        <!-- Conclusión Resumida Gigante -->
        <section class="bg-febf-yellow rounded-2xl shadow-lg border border-yellow-400 p-8 md:p-12 relative overflow-hidden">
            <div class="relative z-10 max-w-4xl mx-auto text-center">
                <span class="bg-slate-900 text-white text-sm font-bold uppercase tracking-widest py-1 px-3 rounded-full mb-6 inline-block">Resumen del Día</span>
                <h2 class="text-3xl md:text-4xl font-extrabold text-slate-900 mb-6 leading-tight">
                    ¿Qué significa todo esto para mí?
                </h2>
                <p class="text-xl md:text-2xl text-slate-800 font-medium leading-relaxed">
                    Si eres un inversor, lo único que debes recordar hoy es que <b>el coste de financiación y la inflación dirigen el barco</b>. 
                    Mientas la inflación se mantenga bajo control, los bancos centrales no subirán agresivamente los intereses. 
                    Esto hace que las empresas sigan ganando dinero y que mantener tu capital invertido en acciones globales siga siendo la mejor defensa contra la pérdida de poder adquisitivo a largo plazo.
                </p>
            </div>
        </section>

    </main>

    <!-- Footer Profesional y Disclaimer -->
    <footer class="bg-slate-900 text-slate-400 py-12 px-6 mt-16 text-sm">
        <div class="max-w-6xl mx-auto grid md:grid-cols-2 gap-10">
            <div>
                <h4 class="text-white font-bold text-lg mb-4 uppercase tracking-wider">Fuentes de Datos Oficiales</h4>
                <ul class="space-y-2">
                    <li class="flex items-center gap-2"><svg class="w-4 h-4 text-febf-yellow" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path></svg> 
                        Datos Macroeconómicos: <a href="https://fred.stlouisfed.org/" target="_blank" class="underline hover:text-white transition">FRED (Federal Reserve Bank of St. Louis)</a>
                    </li>
                    <li class="flex items-center gap-2"><svg class="w-4 h-4 text-febf-yellow" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path></svg> 
                        Cotizaciones de Mercado: <a href="https://finance.yahoo.com/" target="_blank" class="underline hover:text-white transition">Yahoo Finance API</a> (Puede existir retraso).
                    </li>
                </ul>
            </div>
            <div>
                <h4 class="text-white font-bold text-lg mb-4 uppercase tracking-wider">Aviso Legal (Disclaimer)</h4>
                <p class="text-xs leading-relaxed text-slate-500 text-justify">
                    La información proporcionada en este panel tiene un fin estrictamente académico, educativo e informativo, enmarcado en el análisis financiero. 
                    <b>NO constituye asesoramiento financiero</b>, recomendación de inversión, ni solicitud para comprar o vender valores o instrumentos financieros. 
                    El mercado de valores conlleva riesgos significativos, incluyendo la pérdida total del capital. El autor de esta herramienta y las instituciones referenciadas no se responsabilizan de las decisiones tomadas en base a estos datos automáticos.
                </p>
            </div>
        </div>
        <div class="text-center pt-8 mt-8 border-t border-slate-800 font-mono opacity-60">
            Generado automáticamente vía GitHub Actions | Proyecto Analítico Cuantitativo
        </div>
    </footer>
</body>
</html>"""
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

def enviar_telegram(config, mensaje):
    if config.get("telegram_bot_token") and config.get("telegram_chat_id"):
        url = f"https://api.telegram.org/bot{config['telegram_bot_token']}/sendMessage"
        payload = {
            "chat_id": config["telegram_chat_id"], 
            "text": mensaje, 
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
        try:
            requests.post(url, json=payload)
        except Exception as e:
            print(f"Error al enviar Telegram: {e}")

def main():
    config = cargar_configuracion()
    if not config.get("activo", True): 
        print("Bot pausado. Saliendo.")
        return
    
    fecha = datetime.now().strftime("%d/%m/%Y")
    
    # Recolección
    mercados = MercadoDatos.obtener_metricas()
    macro = MacroDatos.obtener_datos(config.get("fred_api_key"))
    
    # Análisis Textual para Telegram
    txt_pro, txt_dum = InterpreteMercado.generar_analisis_telegram(mercados, macro)
    
    # Generación de Web HTML
    crear_pagina_web(mercados, macro, fecha)
    
    # Composición del Mensaje de Telegram
    mensaje = f"📊 <b>REPORTE DE MERCADO FEBF | {fecha}</b>\n\n"
    mensaje += f"{txt_pro}\n{txt_dum}\n"
    
    mensaje += "<b>📈 DATOS DESTACADOS:</b>\n"
    for c, d in mercados.items():
        emoji = "🔴" if d['variacion'] < 0 else "🟢"
        if c in ["US10Y", "VIX"]: emoji = "🔴" if d['variacion'] > 0 else "🟢"
        mensaje += f"{emoji} {d['nombre']}: {d['precio']} ({d['variacion']}{d['unidad']})\n"
        
    # Obtener el nombre del repositorio dinámicamente para el enlace Web
    repo_completo = os.environ.get('GITHUB_REPOSITORY', 'usuario/repo')
    try:
        usuario = repo_completo.split('/')[0]
        nombre_repo = repo_completo.split('/')[1]
    except:
        usuario = "usuario"
        nombre_repo = "repo"
        
    url_web = f"https://{usuario}.github.io/{nombre_repo}/"
    
    mensaje += f"\n🌐 <b>VER DASHBOARD COMPLETO Y EXPLICACIÓN:</b>\n{url_web}"
    mensaje += f"\n\n<i>⚠️ Aviso legal: Información académica. No es consejo de inversión.</i>"
    
    enviar_telegram(config, mensaje)
    print("Ejecución finalizada con éxito.")

if __name__ == "__main__":
    main()
