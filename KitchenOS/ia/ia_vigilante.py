import requests
import time

URL_BACKEND = "http://localhost:8000"
URL_BOT = "http://localhost:3000/api/enviar"

def analizar_seguridad():
    print("🕵️ [IA VIGILANTE] Monitoreando vacios y seguridad de red...")
    estado_prev = None
    
    while True:
        try:
            # 1. Autenticacion para obtener acceso
            auth = requests.post(f"{URL_BACKEND}/token", data={"username":"demian_chef","password":"tesi123"}).json()
            token = auth['access_token']
            headers = {"Authorization": f"Bearer {token}"}
            
            # 2. Obtener estado actual del inventario y temperatura
            actual = requests.get(f"{URL_BACKEND}/api/dashboard/mapeado", headers=headers).json()
            
            # Alerta de Temperatura Crítica
            if actual['temperatura'] > 5.0:
                requests.post(URL_BOT, json={
                    "tipo": "alerta_stock", 
                    "mensaje": f"❄️ *ALERTA DE TEMPERATURA*\nCámara a {actual['temperatura']}°C. ¡Riesgo de descomposición!"
                })

            for item in actual['inventario']:
                nombre = item['nombre']
                peso = item['peso']

                # LÓGICA DE VACÍO ABSOLUTO
                if peso <= 0.0:
                    msg_vacio = (
                        f"🚨 *STOCK AGOTADO: {nombre}*\n"
                        f"La báscula detecta 0.0 KG.\n\n"
                        f"¿Chef, solicito este producto al proveedor?\n"
                        f"Responde: *CONFIRMO {nombre}*"
                    )
                    requests.post(URL_BOT, json={"tipo": "alerta_stock", "mensaje": msg_vacio})
                    print(f"⚠️ Alerta de vacio enviada para: {nombre}")

            estado_prev = actual
        except Exception as e:
            print(f"❌ Error en Vigilante: {e}")
            
        time.sleep(30) # Revisa cada 10 segundos

if __name__ == "__main__":
    analizar_seguridad()