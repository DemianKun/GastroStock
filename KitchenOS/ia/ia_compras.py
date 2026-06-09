import requests
import time

URL_BACKEND = "http://localhost:8000"
URL_BOT = "http://localhost:3000/api/enviar"

def gestionar_abastecimiento():
    print("🛒 [IA COMPRAS] Iniciando monitor de reabastecimiento...")
    
    # Para no spamear al Chef, guardamos cuando avisamos por ultima vez
    ultimos_avisos = {}

    while True:
        try:
            # 1. Login
            auth = requests.post(f"{URL_BACKEND}/token", data={"username":"demian_chef","password":"tesi123"}).json()
            headers = {"Authorization": f"Bearer {auth['access_token']}"}

            # 2. Obtener limites minimos y stock actual
            configs = requests.get(f"{URL_BACKEND}/api/inventario/config", headers=headers).json()
            stock = requests.get(f"{URL_BACKEND}/api/dashboard/mapeado", headers=headers).json()
            inventario = {i['nombre']: i['peso'] for i in stock['inventario']}

            for conf in configs:
                nombre = conf['nombre_producto']
                minimo = conf['stock_minimo']
                peso_actual = inventario.get(nombre, 0)

                # Si el stock es insuficiente pero mayor a 0 (el vigilante se encarga del 0)
                if 0 < peso_actual <= minimo:
                    ahora = time.time()
                    # Solo avisar cada 1 hora por el mismo producto
                    if nombre not in ultimos_avisos or (ahora - ultimos_avisos[nombre]) > 3600:
                        msg_compra = (
                            f"🛒 *IA DE COMPRAS: REABASTECIMIENTO*\n"
                            f"El stock de *{nombre}* es de {peso_actual}kg (Mínimo: {minimo}kg).\n\n"
                            f"¿Deseas pedir mas material al proveedor?\n"
                            f"Responde: *CONFIRMO {nombre}*"
                        )
                        requests.post(URL_BOT, json={"tipo": "alerta_stock", "mensaje": msg_compra})
                        ultimos_avisos[nombre] = ahora
                        print(f"📢 Sugerencia de compra proactiva: {nombre}")

        except Exception as e:
            print(f"❌ Error en IA Compras: {e}")
            
        time.sleep(60) # Revisa cada minuto

if __name__ == "__main__":
    gestionar_abastecimiento()