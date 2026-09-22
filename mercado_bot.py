import yfinance as yf
import requests
import json
import os
from datetime import datetime

# Archivo local para guardar configuración y estado del bot (Para el comando /stop)
CONFIG_FILE = "config_bot.json"

def cargar_configuracion():
    """Carga la configuración desde las variables de entorno de GitHub (Seguridad) o archivo local."""
    # Obtenemos las claves secretas desde GitHub Actions
    token = os.environ.get("TELEGRAM_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    fred_key = os.environ.get("FRED_API_KEY", "")

    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            # Actualizamos las claves con las de GitHub
            config["telegram_bot_token"] = token
            config["telegram_chat_id"] = chat_id
            config["fred_api_key"] = fred_key
            return config
    else:
        config_inicial = {
            "telegram_bot_token": token, 
            "telegram_chat_id": chat_id,      
            "fred_api_key": fred_key,
            "activo": True,
            "ultimo_update_id": 0
        }
        return config_inicial

def guardar_configuracion(config):
    """Guarda los cambios en el archivo de configuración."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

class MercadoDatos:
    """Extrae precios y variaciones reales del mercado financiero."""
    
    TICKERS = {
        "US10Y": {"simbolo": "^TNX", "nombre": "Bono EE.UU 10 Años", "tipo": "tasa"},
        "VIX": {"simbolo": "^VIX", "nombre": "Índice VIX (Volatilidad)", "tipo": "indice"},
        "SP500": {"simbolo": "ES=F", "nombre": "Futuros S&P 500", "tipo": "indice"},
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
                        var_pct = (precio_actual - cierre_ayer) * 100 # En puntos básicos
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
                print(f"Error extrayendo {info['nombre']}: {e}")
        return resultados

class MacroDatos:
    """Extrae datos económicos oficiales de la Reserva Federal (FRED)."""
    
    SERIES = {
        "INFLACION": {"id": "CPIAUCSL", "nombre": "Inflación (IPC Anual)"},
        "DESEMPLEO": {"id": "UNRATE", "nombre": "Tasa de Desempleo EE.UU."}
    }

    @staticmethod
    def obtener_datos(api_key):
        if api_key == "TU_CLAVE_FRED_AQUI":
            return {} # Salta si no hay API Key configurada
            
        resultados = {}
        for clave, info in MacroDatos.SERIES.items():
            # Extraemos el último dato de la serie
            url = f"https://api.stlouisfed.org/fred/series/observations?series_id={info['id']}&api_key={api_key}&file_type=json&sort_order=desc&limit=1"
            try:
                respuesta = requests.get(url).json()
                valor = float(respuesta['observations'][0]['value'])
                fecha = respuesta['observations'][0]['date']
                
                # Para el IPC calculamos la variación interanual aproximada
                if clave == "INFLACION":
                    url_ano_pasado = f"https://api.stlouisfed.org/fred/series/observations?series_id={info['id']}&api_key={api_key}&file_type=json&sort_order=desc&limit=13"
                    resp_pasado = requests.get(url_ano_pasado).json()
                    valor_pasado = float(resp_pasado['observations'][12]['value'])
                    valor = round(((valor - valor_pasado) / valor_pasado) * 100, 1)

                resultados[clave] = {
                    "nombre": info["nombre"],
                    "valor": valor,
                    "fecha": fecha
                }
            except Exception as e:
                print(f"Error extrayendo datos macro de {info['nombre']}: {e}")
        return resultados

class InterpreteMercado:
    """Genera las explicaciones Profesionales y Generales (Doble Capa)."""
    
    @staticmethod
    def generar_resumen_global(mercados):
        """Analiza S&P500 y VIX para crear un resumen para todos los públicos."""
        sp500_var = mercados.get("SP500", {}).get("variacion", 0) if "SP500" in mercados else 0
        vix_var = mercados.get("VIX", {}).get("variacion", 0) if "VIX" in mercados else 0
        
        if sp500_var > 0.3 and vix_var < 0:
            return "☀️ <b>DÍA SOLEADO:</b> Los inversores están optimistas hoy. Las bolsas apuntan a subidas y el 'índice del miedo' (VIX) está bajando. Hay apetito por comprar y el mercado está tranquilo."
        elif sp500_var < -0.3 and vix_var > 2:
            return "⛈️ <b>DÍA TORMENTOSO:</b> Hay nerviosismo general. Las bolsas caen y los inversores están comprando activos seguros para protegerse. Un día para tener precaución."
        elif vix_var > 10:
            return "⚠️ <b>ALERTA DE VOLATILIDAD:</b> Pánico a corto plazo. El mercado está asustado por noticias recientes y los precios se van a mover de forma muy brusca hoy."
        else:
            return "⛅ <b>DÍA TRANQUILO:</b> Movimientos moderados. Los grandes inversores están a la espera de nuevas noticias económicas sin tomar decisiones precipitadas."

    @staticmethod
    def analizar_mercado(clave, datos):
        var = datos["variacion"]
        tendencia = "alcista" if var > 0 else "bajista"
        
        analisis = {
            "US10Y": {
                "alcista": (
                    "PRO: Repunte de tires. Descuento de flujos de caja más agresivo, penaliza duraciones largas y Growth.",
                    "GENERAL: Sube el interés de la deuda pública. Los bancos centrales podrían mantener tipos altos, encareciendo préstamos y enfriando la bolsa."
                ),
                "bajista": (
                    "PRO: Compresión de tires. Alivio en la tasa de descuento (WACC). Posible rotación hacia activos de riesgo.",
                    "GENERAL: Cae el interés de la deuda. Dinero más barato para empresas y familias, lo que suele animar a los inversores a comprar acciones."
                )
            },
            "SP500": {
                "alcista": (
                    "PRO: Futuros en verde indicando sesgo intradiario positivo. Flujos de entrada en el pre-market.",
                    "GENERAL: Wall Street apunta a una apertura al alza. Hay optimismo comprador entre los inversores esta mañana."
                ),
                "bajista": (
                    "PRO: Futuros en rojo. Presión vendedora institucional. Vigilar soportes clave en la apertura de contado.",
                    "GENERAL: Wall Street apunta a una apertura con caídas. Predominan las ventas antes de que toque la campana."
                )
            }
        }
        
        if clave in analisis:
            return analisis[clave]["alcista"] if tendencia == "alcista" else analisis[clave]["bajista"]
        else:
            return (f"PRO: Variación del {abs(var)}{datos['unidad']}. Evaluar volumen intradiario.",
                    f"GENERAL: El activo se ha movido un {abs(var)}{datos['unidad']} respecto a su cierre de ayer.")

    @staticmethod
    def analizar_macro(clave, datos):
        valor = datos["valor"]
        
        if clave == "INFLACION":
            pro = f"PRO: Lectura interanual del {valor}%. Confirmación de senda de precios clave para el 'Dot Plot' del FOMC."
            gen = f"GENERAL: El coste de la vida ha subido un {valor}% en el último año. Si baja, el Banco Central podrá recortar tipos pronto."
        elif clave == "DESEMPLEO":
            pro = f"PRO: Tasa de desempleo (U-3) en {valor}%. Termómetro de sobrecalentamiento del mercado laboral."
            gen = f"GENERAL: El paro en EE.UU. se sitúa en el {valor}%. Si sube mucho, hay riesgo de recesión; si es muy bajo, hay riesgo de inflación."
        else:
            pro, gen = "Dato macroeconómico clave publicado.", "Nuevo dato oficial sobre la salud de la economía."
            
        return pro, gen

class GestorTelegram:
    def __init__(self, config):
        self.token = config["telegram_bot_token"]
        self.chat_id = config["telegram_chat_id"]
        self.url_base = f"https://api.telegram.org/bot{self.token}"

    def comprobar_comandos(self, config):
        """Permite al usuario pausar o reanudar el bot enviando /stop o /start en Telegram."""
        if self.token == "TU_TOKEN_TELEGRAM_AQUI":
            return config
            
        try:
            url = f"{self.url_base}/getUpdates?offset={config['ultimo_update_id'] + 1}"
            respuesta = requests.get(url).json()
            
            if respuesta.get("ok") and respuesta.get("result"):
                for mensaje in respuesta["result"]:
                    texto = mensaje.get("message", {}).get("text", "").lower()
                    config["ultimo_update_id"] = mensaje["update_id"]
                    
                    if texto == "/stop":
                        config["activo"] = False
                        self.enviar_mensaje("⏸️ Reporte matutino pausado. Escribe /start para reanudar.")
                    elif texto in ["/start", "/resume"]:
                        config["activo"] = True
                        self.enviar_mensaje("▶️ Reporte matutino activado. Listo para el mercado.")
            return config
        except Exception:
            return config

    def enviar_mensaje(self, texto):
        if self.token == "TU_TOKEN_TELEGRAM_AQUI":
            print("\n--- VISTA PREVIA DEL MENSAJE (Falta configurar Telegram) ---")
            print(texto)
            return

        url = f"{self.url_base}/sendMessage"
        requests.post(url, json={"chat_id": self.chat_id, "text": texto, "parse_mode": "HTML"})

def crear_pagina_web(mercados, macro, resumen, fecha):
    """Genera un archivo HTML con un diseño moderno (Tailwind) usando los datos del día."""
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard Financiero FEBF</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-50 text-slate-800 font-sans p-4 md:p-8">
    <div class="max-w-4xl mx-auto">
        <header class="mb-8 text-center">
            <h1 class="text-3xl font-bold text-slate-900 mb-2">Tracker Matutino de Mercados</h1>
            <p class="text-slate-500">Actualizado: {fecha}</p>
        </header>
        
        <div class="bg-white rounded-xl shadow-sm p-6 mb-8 border border-slate-200">
            <h2 class="text-xl font-bold text-indigo-700 mb-3 flex items-center">📝 Resumen del Mercado</h2>
            <p class="text-lg text-slate-700">{resumen.replace('<b>', '').replace('</b>', '')}</p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
                <h2 class="text-xl font-bold mb-4 border-b pb-2 text-slate-800">📈 Cotizaciones</h2>
"""
    for clave, datos in mercados.items():
        signo = "+" if datos['variacion'] > 0 else ""
        color = "text-green-600" if datos['variacion'] > 0 else "text-red-600"
        if clave in ["US10Y", "VIX"]: color = "text-red-600" if datos['variacion'] > 0 else "text-green-600"
        pro, gen = InterpreteMercado.analizar_mercado(clave, datos)
        
        html += f"""
                <div class="mb-4 bg-white p-4 rounded-lg shadow-sm border border-slate-100">
                    <div class="flex justify-between items-center mb-3">
                        <span class="font-bold text-slate-800">{datos['nombre']}</span>
                        <span class="font-bold {color} bg-slate-50 px-2 py-1 rounded">{datos['precio']} ({signo}{datos['variacion']}{datos['unidad']})</span>
                    </div>
                    <p class="text-sm text-slate-600 mb-2"><span class="font-bold text-slate-800">PRO:</span> {pro.replace('PRO: ', '')}</p>
                    <p class="text-sm text-slate-500 italic"><span class="font-bold text-slate-700">GEN:</span> {gen.replace('GENERAL: ', '')}</p>
                </div>"""
                
    html += """
            </div>
            <div>
                <h2 class="text-xl font-bold mb-4 border-b pb-2 text-slate-800">🇺🇸 Datos Macro (FRED)</h2>
"""
    if macro:
        for clave, datos in macro.items():
            pro, gen = InterpreteMercado.analizar_macro(clave, datos)
            html += f"""
                <div class="mb-4 bg-white p-4 rounded-lg shadow-sm border border-slate-100">
                    <div class="flex justify-between items-center mb-3">
                        <span class="font-bold text-slate-800">{datos['nombre']}</span>
                        <span class="font-bold text-blue-600 bg-blue-50 px-2 py-1 rounded">{datos['valor']}%</span>
                    </div>
                    <p class="text-sm text-slate-600 mb-2"><span class="font-bold text-slate-800">PRO:</span> {pro.replace('PRO: ', '')}</p>
                    <p class="text-sm text-slate-500 italic"><span class="font-bold text-slate-700">GEN:</span> {gen.replace('GENERAL: ', '')}</p>
                </div>"""
    
    html += f"""
            </div>
        </div>
        <footer class="mt-12 text-center text-slate-400 text-sm">
            Creado para la Fundación de Estudios Bursátiles y Financieros (FEBF)
        </footer>
    </div>
</body>
</html>"""
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

def generar_boletin():
    config = cargar_configuracion()
    telegram = GestorTelegram(config)
    
    # 1. Comprobar si has mandado /stop desde el móvil
    config = telegram.comprobar_comandos(config)
    guardar_configuracion(config)
    
    if not config["activo"]:
        print("Bot pausado. Ignorando ejecución.")
        return

    # 2. Descargar datos Reales
    print("Obteniendo cotizaciones en tiempo real...")
    mercados = MercadoDatos.obtener_metricas()
    
    print("Conectando con la base de datos de la Reserva Federal...")
    macro = MacroDatos.obtener_datos(config["fred_api_key"])
    
    # 3. Ensamblar el mensaje HTML y la Web
    fecha_hoy = datetime.now().strftime("%d/%m/%Y")
    
    # Obtenemos el resumen global
    resumen_global = InterpreteMercado.generar_resumen_global(mercados)
    
    # Creamos el archivo HTML de la página web
    crear_pagina_web(mercados, macro, resumen_global, fecha_hoy)
    
    mensaje = f"<b>📊 APERTURA DE MERCADOS | {fecha_hoy}</b>\n\n"
    mensaje += f"{resumen_global}\n\n"
    
    # Bloque Mercados
    mensaje += "<b>📈 DATOS DE COTIZACIÓN</b>\n"
    for clave, datos in mercados.items():
        signo = "+" if datos['variacion'] > 0 else ""
        emoji = "🔴" if datos['variacion'] < 0 else "🟢"
        if clave in ["US10Y", "VIX"]: emoji = "🔴" if datos['variacion'] > 0 else "🟢"
            
        pro, gen = InterpreteMercado.analizar_mercado(clave, datos)
        mensaje += f"{emoji} <b>{datos['nombre']}</b>: {datos['precio']} ({signo}{datos['variacion']}{datos['unidad']})\n"
        mensaje += f"🏛️ <i>{pro}</i>\n💡 <i>{gen}</i>\n\n"
        
    # Bloque Macro (Solo si la API está configurada)
    if macro:
        mensaje += "<b>🇺🇸 AGENDA MACROECONÓMICA</b>\n"
        for clave, datos in macro.items():
            pro, gen = InterpreteMercado.analizar_macro(clave, datos)
            mensaje += f"📌 <b>{datos['nombre']}</b>: {datos['valor']}%\n"
            mensaje += f"🏛️ <i>{pro}</i>\n💡 <i>{gen}</i>\n\n"
            
    mensaje += "<i>Herramienta Analítica - FEBF Master</i>\n\n"
    # Añadimos el enlace a tu futura web
    mensaje += "🌐 <b>Ver Dashboard Web Completo:</b>\nhttps://aguarinosm.github.io/mercado_bot.py/"
    
    # 4. Enviar
    telegram.enviar_mensaje(mensaje)

if __name__ == "__main__":
    generar_boletin()
