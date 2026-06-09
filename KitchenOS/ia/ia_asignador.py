import requests
import time

URL_BACKEND = "http://localhost:8000"
URL_BOT = "http://localhost:3000/api/enviar"

def analizar_y_asignar():
    print("👨‍🍳 [IA ASIGNADOR] Iniciando análisis de disponibilidad...")
    
    while True:
        try:
            # 1. Obtener Token de acceso (Chef)
            auth = requests.post(f"{URL_BACKEND}/token", data={"username":"demian_chef","password":"tesi123"}).json()
            headers = {"Authorization": f"Bearer {auth['access_token']}"}

            # 2. Consultar inventario real y lista de recetas
            stock_data = requests.get(f"{URL_BACKEND}/api/dashboard/mapeado", headers=headers).json()
            recetas = requests.get(f"{URL_BACKEND}/api/recetas", headers=headers).json()

            # Mapear stock actual por nombre de producto
            inventario = {item['nombre']: item['peso'] for item in stock_data['inventario']}
            
            disponibles = []

            # 3. Lógica de Inteligencia: Comparar ingredientes vs básculas
            for receta in recetas:
                ingredientes_necesarios = receta['ingredientes_json']
                es_posible = True
                
                for nombre_ing, cant_requerida in ingredientes_necesarios.items():
                    peso_actual = inventario.get(nombre_ing, 0)
                    if peso_actual < cant_requerida:
                        es_posible = False
                        break
                
                if es_posible:
                    disponibles.append(receta['nombre'])

            # 4. Enviar al GRUPO DE COCINA si hay opciones
            if disponibles:
                num_recetas = len(disponibles)
                lista_texto = "\n- ".join(disponibles)
                
                mensaje_whatsapp = (
                    f"👨‍🍳 *IA ASIGNADOR K-OS*\n"
                    f"Atención equipo, hay insumos para preparar *{num_recetas} recetas* ahora mismo:\n\n"
                    f"- {lista_texto}\n\n"
                    f"¿Quién toma alguna? Respondan con el nombre de la receta o *YO*."
                )

                # Se envía con tipo 'propuesta' para que el bot lo mande al ID del grupo
                requests.post(URL_BOT, json={
                    "tipo": "propuesta", 
                    "mensaje": mensaje_whatsapp
                })
                print(f"✅ Propuesta de {num_recetas} recetas enviada al grupo.")

        except Exception as e:
            print(f"❌ Error en IA Asignador: {e}")
            
        time.sleep(300) # Analiza la disponibilidad cada 5 minutos

if __name__ == "__main__":
    analizar_y_asignar()