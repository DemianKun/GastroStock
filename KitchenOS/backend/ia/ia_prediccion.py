"""
ia_prediccion.py — Módulo de predicción de consumo para KitchenOS / GastroStock
--------------------------------------------------------------------------------
Implementa la lógica descrita en los documentos:
  • Regresión lineal simple:   y = β₀ + β₁·x  (inventario vs tiempo)
  • Regresión lineal múltiple: y = β₀ + β₁x₁ + β₂x₂ + ... + βₙxₙ
    Variables: tiempo, platillos vendidos, día de la semana, historial, stock inicial

Expone una función pública `predecir_consumo(producto, historial_pesos, nivel_minimo)`
que devuelve el resultado listo para serializar como JSON en main.py.
"""

import numpy as np
from datetime import datetime
from typing import List, Optional


# ---------------------------------------------------------------------------
# Regresión lineal simple (mínimos cuadrados, sin dependencias externas)
# ---------------------------------------------------------------------------

def _regresion_simple(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    """
    Devuelve (β₀, β₁, R²).
    x : vector de tiempos (índices o segundos desde el inicio)
    y : vector de pesos (kg) correspondientes
    """
    n = len(x)
    if n < 2:
        return float(y[0]) if n == 1 else 0.0, 0.0, 0.0

    x_mean, y_mean = x.mean(), y.mean()
    ss_xy = np.sum((x - x_mean) * (y - y_mean))
    ss_xx = np.sum((x - x_mean) ** 2)

    if ss_xx == 0:
        return float(y_mean), 0.0, 0.0

    beta1 = ss_xy / ss_xx
    beta0 = y_mean - beta1 * x_mean

    # R²
    y_pred = beta0 + beta1 * x
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - y_mean) ** 2)
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot != 0 else 1.0

    return float(beta0), float(beta1), float(r2)


# ---------------------------------------------------------------------------
# Regresión lineal múltiple  (β = (XᵀX)⁻¹ Xᵀy)
# ---------------------------------------------------------------------------

def _regresion_multiple(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, float]:
    """
    X : matriz de diseño  (n × k)  — primera columna debe ser el sesgo (unos)
    y : vector objetivo   (n,)
    Devuelve (betas, R²).
    """
    try:
        betas = np.linalg.lstsq(X, y, rcond=None)[0]
        y_pred = X @ betas
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - y.mean()) ** 2)
        r2 = 1.0 - (ss_res / ss_tot) if ss_tot != 0 else 1.0
        return betas, float(r2)
    except np.linalg.LinAlgError:
        return np.zeros(X.shape[1]), 0.0


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def predecir_consumo(
    producto: str,
    historial_pesos: List[float],        # últimas N lecturas (kg)
    nivel_minimo: float,                 # umbral de alerta (kg)
    timestamps: Optional[List[str]] = None,   # ISO strings; None → índices uniformes
    platillos_vendidos: Optional[List[float]] = None,
    dia_semana: Optional[List[int]] = None,   # 0=lunes … 6=domingo
    horizonte_puntos: int = 10           # cuántos pasos hacia el futuro proyectar
) -> dict:
    """
    Calcula predicción de inventario para `producto`.

    Retorna un dict con:
      modelo_simple   : coeficientes β₀, β₁, R²
      modelo_multiple : coeficientes, R²  (si hay variables extra)
      datos_reales    : lista de {t, peso}
      prediccion      : lista de {t, peso_predicho}  (horizonte)
      nivel_minimo    : float
      alerta          : bool — True si la predicción toca el nivel mínimo
      tiempo_critico  : índice estimado en que se alcanza el mínimo (o null)
      consumo_promedio_por_paso : float (kg/paso)
      mensaje         : texto de alerta legible
    """
    n = len(historial_pesos)
    if n == 0:
        return {"error": "Sin historial para predecir."}

    y = np.array(historial_pesos, dtype=float)

    # Eje temporal — segundos reales o índices sintéticos
    if timestamps and len(timestamps) == n:
        try:
            fechas = [datetime.fromisoformat(t) for t in timestamps]
            t0 = fechas[0]
            x = np.array([(f - t0).total_seconds() / 3600.0 for f in fechas])
            paso_unidad = "horas"
        except Exception:
            x = np.arange(n, dtype=float)
            paso_unidad = "lecturas"
    else:
        x = np.arange(n, dtype=float)
        paso_unidad = "lecturas"

    # ----- Regresión simple -----
    beta0, beta1, r2_simple = _regresion_simple(x, y)
    consumo_por_paso = abs(beta1)   # ritmo de consumo (kg por unidad de paso)

    # ----- Proyección hacia el futuro -----
    paso = (x[-1] - x[0]) / (n - 1) if n > 1 else 1.0
    x_futuro = np.array([x[-1] + paso * (i + 1) for i in range(horizonte_puntos)])
    y_futuro = beta0 + beta1 * x_futuro

    prediccion = [
        {"t": float(x_futuro[i]), "peso_predicho": round(float(y_futuro[i]), 4)}
        for i in range(horizonte_puntos)
    ]

    # ¿Cuándo cruza el nivel mínimo?
    tiempo_critico = None
    if beta1 < 0:                           # tendencia descendente
        # x_critico = (nivel_minimo - β₀) / β₁
        if beta1 != 0:
            x_crit = (nivel_minimo - beta0) / beta1
            if x_crit > x[-1]:
                tiempo_critico = round(float(x_crit), 2)

    alerta = bool(
        any(p["peso_predicho"] <= nivel_minimo for p in prediccion)
        or y[-1] <= nivel_minimo
    )

    # ----- Regresión múltiple (si hay variables adicionales) -----
    resultado_multiple: Optional[dict] = None
    if platillos_vendidos and len(platillos_vendidos) == n:
        pv = np.array(platillos_vendidos, dtype=float)
        ds = np.array(dia_semana, dtype=float) if dia_semana and len(dia_semana) == n else np.zeros(n)

        # Matriz de diseño: [1, x_tiempo, platillos, dia_semana, historial_acumulado]
        hist_acum = np.cumsum(y) / (np.arange(1, n + 1))  # promedio acumulado
        X_mult = np.column_stack([
            np.ones(n),
            x,
            pv,
            ds,
            hist_acum
        ])
        betas_m, r2_m = _regresion_multiple(X_mult, y)
        resultado_multiple = {
            "betas": [round(float(b), 6) for b in betas_m],
            "variables": ["intercepto", "tiempo", "platillos_vendidos", "dia_semana", "historial_promedio"],
            "r2": round(r2_m, 4)
        }

    # ----- Mensaje legible -----
    if alerta:
        if tiempo_critico is not None:
            msg = (
                f"⚠️ {producto}: se estima alcanzar el nivel mínimo ({nivel_minimo} kg) "
                f"en aprox. {round(tiempo_critico - x[-1], 1)} {paso_unidad} más. "
                f"Se recomienda reabastecer."
            )
        else:
            msg = f"⚠️ {producto}: ya está en o por debajo del nivel mínimo ({nivel_minimo} kg)."
    else:
        msg = (
            f"✅ {producto}: stock estable. Consumo promedio: "
            f"{round(consumo_por_paso, 3)} kg/{paso_unidad}."
        )

    return {
        "producto": producto,
        "paso_unidad": paso_unidad,
        "modelo_simple": {
            "beta0": round(beta0, 6),
            "beta1": round(beta1, 6),
            "r2": round(r2_simple, 4),
            "formula": f"y = {round(beta0,3)} + ({round(beta1,3)}) · x"
        },
        "modelo_multiple": resultado_multiple,
        "datos_reales": [
            {"t": round(float(x[i]), 2), "peso": round(float(y[i]), 4)}
            for i in range(n)
        ],
        "prediccion": prediccion,
        "nivel_minimo": nivel_minimo,
        "alerta": alerta,
        "tiempo_critico": tiempo_critico,
        "consumo_promedio_por_paso": round(consumo_por_paso, 4),
        "mensaje": msg
    }
