import logging, bcrypt, requests, datetime
import numpy as np
from scipy.signal import periodogram
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from jose import jwt
from pydantic import BaseModel
from typing import Optional, Dict

import database
from ia.ia_prediccion import predecir_consumo
from logic.logical_reasoner import (
    diagnosticar_insumo,
    demo_diagnostico_logico,
    diagnosticar_desde_inventario
)

logging.getLogger("passlib").setLevel(logging.ERROR)
SECRET_KEY = "TESI_INGENIERIA_2026"
app = FastAPI(title="KitchenOS")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- CONFIGURACIÓN DE CONTACTOS ---
NUMERO_CHEF = "5529469944" 
NUMERO_PROVEEDOR = "5564543209"
BOT_URL = "http://localhost:3000/api/enviar"

def get_db():
    db = database.SessionLocal()
    try: yield db
    finally: db.close()

# --- MODELOS ---
class UsuarioCreate(BaseModel): username: str; password: str; rol: Optional[str] = "chef"
class DatosESP32(BaseModel): temp_camara: float; peso_b1: float; peso_b2: float; peso_b3: float; peso_b4: float; peso_b5: float; peso_b6: float
class RecetaCreate(BaseModel): nombre: str; descripcion: str; ingredientes_json: Dict[str, float]
class ConfigUpdate(BaseModel): nombre_producto: str; stock_minimo: float
class TareaProponer(BaseModel): receta_nombre: str
class TareaAceptar(BaseModel): empleado_id: int
class WebhookData(BaseModel): numero: str; texto: str

@app.on_event("startup")
def inicializar_configuracion():
    db = database.SessionLocal()
    if db.query(database.ConfiguracionInventario).count() == 0:
        nombres_base = ["Papas", "Carne", "Tomate", "Cebolla", "Pollo", "Aceite"]
        for i in range(1, 7):
            db.add(database.ConfiguracionInventario(id_bascula=f"peso_b{i}", nombre_producto=nombres_base[i-1], stock_minimo=0.5))
        db.commit()
    db.close()

# --- LOGIN Y REGISTRO ---
@app.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    u = db.query(database.Usuario).filter(database.Usuario.username == form_data.username).first()
    if not u or not bcrypt.checkpw(form_data.password.encode('utf-8'), u.password_hash.encode('utf-8')):
        raise HTTPException(status_code=400)
    return {"access_token": jwt.encode({"sub": u.username}, SECRET_KEY, algorithm="HS256"), "token_type": "bearer", "user_id": u.id, "rol": u.rol}

@app.post("/api/registro")
def registrar_usuario(usuario: UsuarioCreate, db: Session = Depends(get_db)):
    existe = db.query(database.Usuario).filter(database.Usuario.username == usuario.username).first()
    if existe: raise HTTPException(status_code=400, detail="El usuario ya existe")
    salt = bcrypt.gensalt(); hashed = bcrypt.hashpw(usuario.password.encode('utf-8'), salt)
    nuevo = database.Usuario(username=usuario.username, password_hash=hashed.decode('utf-8'), rol="cocinero")
    db.add(nuevo); db.commit()
    return {"status": "usuario_creado"}

# --- 1. IA VIGILANTE (Sensores y Alertas) ---
@app.post("/api/sensores")
def recibir_datos(datos: DatosESP32, db: Session = Depends(get_db)):
    ultima_medicion = db.query(database.MedicionReal).order_by(database.MedicionReal.id.desc()).first()
    
    db.add(database.MedicionReal(**datos.model_dump()))
    db.commit()

    configs = db.query(database.ConfiguracionInventario).all()
    mensajes_alerta = []

    if datos.temp_camara > 5.0:
        mensajes_alerta.append(f"❄️ *ALERTA FRÍO*: Temperatura alta ({datos.temp_camara}°C).")

    for config in configs:
        peso_actual = getattr(datos, config.id_bascula)
        peso_anterior = getattr(ultima_medicion, config.id_bascula) if ultima_medicion else peso_actual
        dif = peso_actual - peso_anterior

        # --- Motor lógico: cláusulas de Horn + operador de corte ---
        diag_logico = diagnosticar_insumo(
            insumo=config.nombre_producto,
            stock_actual=float(peso_actual),
            stock_minimo=float(config.stock_minimo)
        )

        if diag_logico["diagnostico"] == "agotado":
            # Regla Prolog: diagnostico(X, agotado) :- stock_agotado(X), !
            mensajes_alerta.append(
                f"❌ *{config.nombre_producto}* VACÍO (0.0 KG). "
                f"Diagnóstico lógico: AGOTADO. "
                f"Regla: {diag_logico['regla_aplicada']}"
            )
        elif diag_logico["diagnostico"] == "bajo_stock":
            # Regla Prolog: diagnostico(X, bajo_stock) :- stock_bajo(X), !
            orden_pendiente = db.query(database.RegistroCompra).filter(
                database.RegistroCompra.producto == config.nombre_producto,
                database.RegistroCompra.estado != "COMPLETADA"
            ).first()
            if not orden_pendiente:
                mensajes_alerta.append(
                    f"⚠️ *{config.nombre_producto}* CASI VACÍO ({peso_actual} KG).\n"
                    f"Diagnóstico lógico: BAJO STOCK.\n"
                    f"Regla: {diag_logico['regla_aplicada']}\n"
                    f"Responde: CONFIRMO {config.nombre_producto}"
                )

        if dif >= 0.5:
            mensajes_alerta.append(f"✅ *{config.nombre_producto}* RELLENADO (+{round(dif,2)} KG).")
            ordenes_abiertas = db.query(database.RegistroCompra).filter(
                database.RegistroCompra.producto == config.nombre_producto,
                database.RegistroCompra.estado != "COMPLETADA"
            ).all()
            for orden in ordenes_abiertas:
                orden.estado = "COMPLETADA"
            if ordenes_abiertas:
                db.commit()
                mensajes_alerta.append(f"📦 Orden de {config.nombre_producto} COMPLETADA automáticamente.")

        elif dif <= -0.5:
            mensajes_alerta.append(f"📉 *CONSUMO ALTO*: Se retiraron {round(abs(dif),2)} KG de {config.nombre_producto}.")

    if mensajes_alerta:
        alertas_unidas = "\n".join(mensajes_alerta)
        try:
            requests.post(BOT_URL, json={
                "tipo": "alerta_stock",
                "mensaje": f"🚨 *VIGILANTE K-OS*\n\n{alertas_unidas}"
            })
        except: pass

    ahora = datetime.datetime.now()
    if ahora.minute == 0:
        resumen = f"📊 *INFORME HORARIO*\nTemp: {datos.temp_camara}°C\n"
        for c in configs: resumen += f"- {c.nombre_producto}: {getattr(datos, c.id_bascula)} KG\n"
        try:
            requests.post(BOT_URL, json={"tipo": "alerta_stock", "mensaje": resumen})
        except: pass

    return {"status": "ok"}

# --- DASHBOARD Y CONFIGURACIÓN ---
@app.get("/api/dashboard/mapeado")
def obtener_dashboard_mapeado(db: Session = Depends(get_db)):
    ultima = db.query(database.MedicionReal).order_by(database.MedicionReal.id.desc()).first()
    configs = db.query(database.ConfiguracionInventario).all()
    mapeo = {c.id_bascula: c.nombre_producto for c in configs}
    if not ultima: return {"temperatura": 0, "inventario": []}
    return {
        "fecha": str(ultima.fecha), "temperatura": ultima.temp_camara,
        "inventario": [{"nombre": mapeo.get(f"peso_b{i}", f"B{i}"), "peso": getattr(ultima, f"peso_b{i}")} for i in range(1, 7)]
    }

@app.get("/api/inventario/config")
def obtener_config_lista(db: Session = Depends(get_db)): return db.query(database.ConfiguracionInventario).all()

@app.put("/api/inventario/config/{id_bascula}")
def actualizar_sensor(id_bascula: str, data: ConfigUpdate, db: Session = Depends(get_db)):
    sensor = db.query(database.ConfiguracionInventario).filter(database.ConfiguracionInventario.id_bascula == id_bascula).first()
    if not sensor: raise HTTPException(404)
    sensor.nombre_producto = data.nombre_producto; sensor.stock_minimo = data.stock_minimo
    db.commit(); return {"status": "actualizado"}

# --- RECETAS ---
@app.get("/api/recetas")
def listar_recetas(db: Session = Depends(get_db)): return db.query(database.Receta).all()

@app.post("/api/recetas")
def guardar_receta(receta: RecetaCreate, db: Session = Depends(get_db)):
    db.add(database.Receta(**receta.model_dump())); db.commit()
    return {"status": "receta_guardada"}

@app.delete("/api/recetas")
def borrar_recetas(db: Session = Depends(get_db)):
    db.query(database.Receta).delete()
    db.commit()
    return {"status": "recetas_borradas"}

@app.delete("/api/historial")
def borrar_historial(db: Session = Depends(get_db)):
    db.query(database.MedicionReal).delete()
    db.query(database.Tarea).delete()
    db.query(database.RegistroCompra).delete()
    db.query(database.Receta).delete()
    db.commit()
    return {"status": "historial_borrado"}

# --- 2. IA DE ASIGNACIÓN (Tareas) ---
@app.get("/api/tareas/propuestas")
def obtener_propuestas(db: Session = Depends(get_db)): return db.query(database.Tarea).filter(database.Tarea.estado == "PROPUESTA").all()

@app.get("/api/tareas/activas")
def obtener_tareas_activas(db: Session = Depends(get_db)):
    tareas = db.query(database.Tarea).filter(database.Tarea.estado.in_(["PENDIENTE", "EN_PROCESO"])).all()
    res = []
    for t in tareas:
        u = db.query(database.Usuario).filter(database.Usuario.id == t.empleado_id).first()
        res.append({"id": t.id, "receta": t.receta_nombre, "estado": t.estado, "cocinero": u.username if u else "---"})
    return res

@app.post("/api/tareas/proponer")
def proponer_tarea(data: TareaProponer, db: Session = Depends(get_db)):
    existe = db.query(database.Tarea).filter(database.Tarea.receta_nombre == data.receta_nombre, database.Tarea.estado.in_(["PROPUESTA", "PENDIENTE", "EN_PROCESO"])).first()
    if existe: return {"status": "ya_existe"}
    
    nueva = database.Tarea(receta_nombre=data.receta_nombre, estado="PROPUESTA", empleado_id=None)
    db.add(nueva); db.commit()
    
    try:
        requests.post(BOT_URL, json={
            "tipo": "propuesta",
            "mensaje": f"👨‍🍳 *COMANDA K-OS*\nHay que preparar: *{data.receta_nombre}*.\n¿Quién la toma? Respondan *YO* o *ACEPTO*."
        })
    except: pass
    return {"status": "propuesta_lanzada", "id": nueva.id}

@app.put("/api/tareas/aceptar/{tarea_id}")
def aceptar_tarea(tarea_id: int, data: TareaAceptar, db: Session = Depends(get_db)):
    tarea = db.query(database.Tarea).filter(database.Tarea.id == tarea_id, database.Tarea.estado == "PROPUESTA").first()
    if not tarea: raise HTTPException(404)
    tarea.empleado_id = data.empleado_id; tarea.estado = "PENDIENTE"; db.commit()
    return {"status": "aceptada"}

@app.put("/api/tareas/completar/{tarea_id}")
def completar_tarea(tarea_id: int, data: TareaAceptar, db: Session = Depends(get_db)):
    tarea = db.query(database.Tarea).filter(database.Tarea.id == tarea_id).first()
    if not tarea: raise HTTPException(404)
    tarea.estado = "COMPLETADA"
    db.commit()
    return {"status": "completada"}

# --- ESTADÍSTICAS DEL EXAMEN (CORREGIDO CON TODAS LAS BÁSCULAS) ---
@app.get("/api/estadisticas/avanzadas")
def obtener_estadisticas_completas(db: Session = Depends(get_db)):
    mediciones = db.query(database.MedicionReal).order_by(database.MedicionReal.id.desc()).limit(20).all()
    mediciones.reverse()
    
    labels_linea = [m.fecha.strftime("%H:%M:%S") for m in mediciones] if mediciones else []
    data_temp = [m.temp_camara for m in mediciones] if mediciones else []
    data_b1 = [m.peso_b1 for m in mediciones] if mediciones else []
    data_b2 = [m.peso_b2 for m in mediciones] if mediciones else []
    data_b3 = [m.peso_b3 for m in mediciones] if mediciones else []
    data_b4 = [m.peso_b4 for m in mediciones] if mediciones else []
    data_b5 = [m.peso_b5 for m in mediciones] if mediciones else []
    data_b6 = [m.peso_b6 for m in mediciones] if mediciones else []

    configs = db.query(database.ConfiguracionInventario).all()
    labels_barras = [c.nombre_producto for c in configs]
    
    if mediciones:
        ultima_med = mediciones[-1]
        data_barras = [getattr(ultima_med, c.id_bascula, 0) for c in configs]
    else:
        data_barras = [0] * len(configs)

    pendientes = db.query(database.Tarea).filter(database.Tarea.estado == "PENDIENTE").count()
    en_proceso = db.query(database.Tarea).filter(database.Tarea.estado == "EN_PROCESO").count()
    propuestas = db.query(database.Tarea).filter(database.Tarea.estado == "PROPUESTA").count()

    historial_completo = db.query(database.MedicionReal.temp_camara).order_by(database.MedicionReal.id.asc()).limit(500).all()
    valores_temp = [m[0] for m in historial_completo]
    
    frecuencias_lista = []
    densidad_lista = []
    
    if len(valores_temp) > 10:
        datos_centrados = np.array(valores_temp) - np.mean(valores_temp)
        f, pxx = periodogram(datos_centrados)
        frecuencias_lista = f.tolist()
        densidad_lista = pxx.tolist()

    return {
        "lineas": {
            "labels": labels_linea, "temp": data_temp,
            "b1": data_b1, "b2": data_b2, "b3": data_b3,
            "b4": data_b4, "b5": data_b5, "b6": data_b6
        },
        "barras": {"labels": labels_barras, "data": data_barras},
        "circular": {"labels": ["Pendientes", "En Proceso", "Propuestas"], "data": [pendientes, en_proceso, propuestas]},
        "espectral": {"frecuencias": frecuencias_lista, "densidad": densidad_lista}
    }

# --- 3. IA DE COMPRAS Y ESCUCHA (Webhook) ---
@app.post("/api/whatsapp/webhook")
def whatsapp_webhook(data: WebhookData, db: Session = Depends(get_db)):
    texto = data.texto.upper().strip()
    
    if texto.startswith("CONFIRMO "):
        producto = texto[9:].strip()
        db.add(database.RegistroCompra(producto=producto, telefono_autoriza=data.numero))
        db.commit()
        try:
            requests.post(BOT_URL, json={
                "tipo": "orden_compra",
                "mensaje": f"🛒 *ORDEN DE COMPRA K-OS*\nEl Chef autorizó reabastecer: *{producto}*.\nFavor confirmar recepción."
            })
        except: pass
        return {"status": "comprado"}
        
    elif texto in ["ACEPTO", "YO"]:
        print(f"👨‍🍳 Cocinero desde {data.numero} aceptó la tarea vía WhatsApp.")
        return {"status": "cocinero_aviso"}

    return {"status": "recibido"}

# --- 4. PREDICCIÓN DE INVENTARIO (Regresión lineal simple y múltiple) ---
# Documentado en: Prediccion_GastroStock.docx y Regresion_GastroStock.docx
#
# Endpoint 1: predicción por producto individual
#   GET /api/prediccion/{nombre_producto}?n=50
#   Toma las últimas `n` mediciones del sensor correspondiente,
#   aplica regresión lineal simple (y = β₀ + β₁·x) y devuelve:
#     - coeficientes β₀ y β₁, R²
#     - datos reales de las últimas lecturas
#     - proyección a 10 pasos futuros
#     - alerta si la predicción cruza el nivel mínimo configurado
#     - tiempo estimado en que se alcanza el nivel mínimo

@app.get("/api/prediccion/{nombre_producto}")
def predecir_producto(
    nombre_producto: str,
    n: int = 50,                    # cantidad de lecturas históricas a usar
    db: Session = Depends(get_db)
):
    # Buscar qué báscula corresponde a este producto
    config = db.query(database.ConfiguracionInventario).filter(
        database.ConfiguracionInventario.nombre_producto == nombre_producto
    ).first()
    if not config:
        raise HTTPException(status_code=404, detail=f"Producto '{nombre_producto}' no encontrado en config.")

    # Obtener últimas N mediciones ordenadas de más antigua a más reciente
    mediciones = (
        db.query(database.MedicionReal)
        .order_by(database.MedicionReal.id.desc())
        .limit(n)
        .all()
    )
    mediciones.reverse()   # cronológico ascendente

    if not mediciones:
        raise HTTPException(status_code=404, detail="Sin mediciones en la base de datos.")

    pesos = [getattr(m, config.id_bascula) for m in mediciones]
    timestamps = [m.fecha.isoformat() for m in mediciones]

    return predecir_consumo(
        producto=nombre_producto,
        historial_pesos=pesos,
        nivel_minimo=config.stock_minimo,
        timestamps=timestamps
    )


# Endpoint 2: predicción de TODOS los productos de una sola vez
#   GET /api/prediccion
#   Útil para el dashboard: devuelve el estado predictivo completo
#   en un solo request, incluyendo alertas y tiempos críticos.

@app.get("/api/prediccion")
def predecir_todos(
    n: int = 50,
    db: Session = Depends(get_db)
):
    configs = db.query(database.ConfiguracionInventario).all()
    mediciones = (
        db.query(database.MedicionReal)
        .order_by(database.MedicionReal.id.desc())
        .limit(n)
        .all()
    )
    mediciones.reverse()

    resultados = []
    for config in configs:
        if not mediciones:
            resultados.append({"producto": config.nombre_producto, "error": "Sin datos"})
            continue

        pesos = [getattr(m, config.id_bascula) for m in mediciones]
        timestamps = [m.fecha.isoformat() for m in mediciones]

        resultado = predecir_consumo(
            producto=config.nombre_producto,
            historial_pesos=pesos,
            nivel_minimo=config.stock_minimo,
            timestamps=timestamps
        )
        resultados.append(resultado)

    return {
        "total_productos": len(resultados),
        "alertas_activas": sum(1 for r in resultados if r.get("alerta")),
        "predicciones": resultados
    }



# --- 5. CAPA LÓGICA PROLOG / RAZONAMIENTO SIMBÓLICO ---
# Implementa cláusulas de Horn, unificación, resolución SLD y operador de corte (!)
# El archivo de reglas completo está en: backend/logic/gastrostock_rules.pl

@app.get("/api/logica/diagnostico", tags=["Lógica Prolog"])
def obtener_diagnostico_logico_demo():
    """
    **Capa Lógica GastroStock — Demostración**

    Muestra el motor de inferencia lógica con valores de ejemplo.
    Incluye:
    - Cláusulas de Horn
    - Representación lógica y clausada
    - Unificación de variables
    - Resolución SLD paso a paso
    - Operador de corte (!) simulado

    Archivo de reglas Prolog: `backend/logic/gastrostock_rules.pl`
    """
    return demo_diagnostico_logico()


@app.get("/api/logica/inventario", tags=["Lógica Prolog"])
def diagnostico_logico_inventario_real(db: Session = Depends(get_db)):
    """
    **Diagnóstico Lógico — Inventario Real**

    Aplica el motor de inferencia Prolog al último inventario
    registrado en MySQL por los sensores ESP32.

    Para cada insumo devuelve:
    - Diagnóstico: estable | bajo_stock | agotado
    - Acción recomendada
    - Regla de Horn aplicada
    - Resolución SLD completa
    - Uso del operador de corte (!)
    """
    ultima = db.query(database.MedicionReal).order_by(database.MedicionReal.id.desc()).first()
    configs = db.query(database.ConfiguracionInventario).all()

    if not ultima:
        raise HTTPException(status_code=404, detail="No hay mediciones registradas en la base de datos.")

    inventario = []
    configuraciones = []

    for config in configs:
        inventario.append({
            "nombre": config.nombre_producto,
            "peso":   getattr(ultima, config.id_bascula)
        })
        configuraciones.append({
            "nombre_producto": config.nombre_producto,
            "stock_minimo":    config.stock_minimo
        })

    return diagnosticar_desde_inventario(inventario, configuraciones)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)