"""
logical_reasoner.py — Capa lógica GastroStock
==============================================
Motor de inferencia en Python equivalente a las reglas Prolog
definidas en gastrostock_rules.pl.

Implementa:
  • Cláusulas de Horn
  • Representación clausada
  • Unificación de variables lógicas
  • Resolución SLD (Selective Linear Definite)
  • Operador de corte (!) simulado con retornos tempranos
"""

from typing import Dict, List, Optional


# ============================================================
# MOTOR DE INFERENCIA PRINCIPAL
# ============================================================

def diagnosticar_insumo(
    insumo: str,
    stock_actual: float,
    stock_minimo: float
) -> Dict:
    """
    Motor lógico equivalente a las cláusulas de diagnóstico en Prolog.

    Cláusulas de Horn representadas:
    ─────────────────────────────────
      diagnostico(Insumo, agotado)    :- stock_agotado(Insumo),  !.
      diagnostico(Insumo, bajo_stock) :- stock_bajo(Insumo),     !.
      diagnostico(Insumo, estable)    :- stock_actual > minimo.

    Operador de corte (!):
    ─────────────────────
      Se simula con retornos tempranos (early return).
      En cuanto se encuentra un diagnóstico válido, se
      interrumpe la evaluación de las siguientes reglas,
      equivalente al comportamiento del ! en Prolog.

    Unificación:
    ────────────
      La variable 'Insumo' de Prolog se unifica con el
      parámetro `insumo` de esta función.
    """

    # ── Regla 1: stock_agotado(Insumo) :- stock_actual(Insumo, C), C =< 0.
    # Representación clausada: ¬stock_actual(X,C) ∨ ¬menor_igual(C,0) ∨ stock_agotado(X)
    if stock_actual <= 0:
        return {
            "insumo": insumo,
            "stock_actual": stock_actual,
            "stock_minimo": stock_minimo,
            "diagnostico": "agotado",
            "accion": "compra_urgente",
            "regla_aplicada": "diagnostico(Insumo, agotado) :- stock_agotado(Insumo), !.",
            "clausula_horn": f"stock_agotado({insumo}) :- stock_actual({insumo}, {stock_actual}), {stock_actual} =< 0.",
            "unificacion": f"Insumo = {insumo}, Cantidad = {stock_actual}",
            "uso_corte": True,
            "corte_descripcion": "! aplicado: se detuvo la búsqueda tras encontrar diagnóstico 'agotado'."
        }

    # ── Regla 2: stock_bajo(Insumo) :- stock_actual(Insumo,C), stock_minimo(Insumo,M), C =< M.
    # Representación lógica: stock_actual(X,C) ∧ stock_minimo(X,M) ∧ C <= M → stock_bajo(X)
    # Representación clausada: ¬stock_actual(X,C) ∨ ¬stock_minimo(X,M) ∨ ¬menor_igual(C,M) ∨ stock_bajo(X)
    if stock_actual <= stock_minimo:
        return {
            "insumo": insumo,
            "stock_actual": stock_actual,
            "stock_minimo": stock_minimo,
            "diagnostico": "bajo_stock",
            "accion": "solicitar_reabastecimiento",
            "regla_aplicada": "diagnostico(Insumo, bajo_stock) :- stock_bajo(Insumo), !.",
            "clausula_horn": (
                f"stock_bajo({insumo}) :- "
                f"stock_actual({insumo}, {stock_actual}), "
                f"stock_minimo({insumo}, {stock_minimo}), "
                f"{stock_actual} =< {stock_minimo}."
            ),
            "unificacion": f"Insumo = {insumo}, Cantidad = {stock_actual}, Minimo = {stock_minimo}",
            "uso_corte": True,
            "corte_descripcion": "! aplicado: se detuvo la búsqueda tras encontrar diagnóstico 'bajo_stock'."
        }

    # ── Regla 3: diagnostico(Insumo, estable) — sin corte, regla base
    return {
        "insumo": insumo,
        "stock_actual": stock_actual,
        "stock_minimo": stock_minimo,
        "diagnostico": "estable",
        "accion": "continuar_monitoreo",
        "regla_aplicada": "diagnostico(Insumo, estable) :- stock_actual(Insumo,C), stock_minimo(Insumo,M), C > M.",
        "clausula_horn": (
            f"diagnostico({insumo}, estable) :- "
            f"stock_actual({insumo}, {stock_actual}), "
            f"stock_minimo({insumo}, {stock_minimo}), "
            f"{stock_actual} > {stock_minimo}."
        ),
        "unificacion": f"Insumo = {insumo}, Cantidad = {stock_actual}, Minimo = {stock_minimo}",
        "uso_corte": False,
        "corte_descripcion": "Sin corte: regla base alcanzada sin necesidad de interrumpir backtracking."
    }


# ============================================================
# RESOLUCIÓN SLD
# ============================================================

def construir_resolucion_sld(
    insumo: str,
    stock_actual: float,
    stock_minimo: float
) -> List[str]:
    """
    Devuelve los pasos de resolución SLD (Selective Linear Definite)
    para la consulta: alerta_reabastecimiento(insumo).

    La resolución SLD parte de la meta (goal) y la resuelve hacia atrás
    usando las cláusulas como reglas de inferencia hasta llegar a
    hechos base (vacío de metas).
    """
    if stock_actual <= 0:
        estado = "agotado"
        evidencia = f"stock_actual({insumo}, {stock_actual}) — C ({stock_actual}) =< 0"
        regla = f"diagnostico({insumo}, agotado) :- stock_agotado({insumo}), !."
    elif stock_actual <= stock_minimo:
        estado = "bajo_stock"
        evidencia = f"stock_actual({insumo}, {stock_actual}), stock_minimo({insumo}, {stock_minimo}) — C ({stock_actual}) =< M ({stock_minimo})"
        regla = f"diagnostico({insumo}, bajo_stock) :- stock_bajo({insumo}), !."
    else:
        estado = "estable"
        evidencia = f"stock_actual({insumo}, {stock_actual}), stock_minimo({insumo}, {stock_minimo}) — C ({stock_actual}) > M ({stock_minimo})"
        regla = f"diagnostico({insumo}, estable) :- stock_actual > stock_minimo."

    return [
        f"[1] Meta inicial (goal): ?- alerta_reabastecimiento({insumo}).",
        f"[2] Unificación: variable Insumo = '{insumo}'",
        f"[3] Resolución: alerta_reabastecimiento({insumo}) :- diagnostico({insumo}, Estado).",
        f"[4] Nueva meta: ?- diagnostico({insumo}, Estado).",
        f"[5] Selección de cláusula aplicable: {regla}",
        f"[6] Evaluación de hechos base: {evidencia}",
        f"[7] Resultado: Estado = {estado}",
        f"[8] {'Operador de corte (!) activado — backtracking interrumpido.' if estado != 'estable' else 'Regla base alcanzada — sin corte necesario.'}",
        f"[9] Conclusión: diagnostico({insumo}, {estado}) — PROBADO."
    ]


# ============================================================
# DEMO GENERAL DE LA CAPA LÓGICA
# ============================================================

def demo_diagnostico_logico() -> Dict:
    """
    Demostración completa de la capa lógica con valores de ejemplo
    que reflejan los hechos definidos en gastrostock_rules.pl.
    """
    insumos_demo = [
        {"insumo": "papas",   "stock_actual": 0.30, "stock_minimo": 0.50},
        {"insumo": "pollo",   "stock_actual": 0.00, "stock_minimo": 0.90},
        {"insumo": "carne",   "stock_actual": 1.20, "stock_minimo": 0.80},
        {"insumo": "tomate",  "stock_actual": 0.35, "stock_minimo": 0.40},
        {"insumo": "cebolla", "stock_actual": 0.60, "stock_minimo": 0.30},
        {"insumo": "aceite",  "stock_actual": 0.15, "stock_minimo": 0.20},
    ]

    diagnosticos = [
        diagnosticar_insumo(i["insumo"], i["stock_actual"], i["stock_minimo"])
        for i in insumos_demo
    ]

    alertas = [d for d in diagnosticos if d["diagnostico"] in ("agotado", "bajo_stock")]

    return {
        "modulo": "Capa Lógica GastroStock",
        "lenguaje_logico_representado": "Prolog (SWI-Prolog compatible)",
        "archivo_reglas": "backend/logic/gastrostock_rules.pl",
        "descripcion": (
            "Diagnóstico de inventario mediante hechos, reglas, cláusulas de Horn, "
            "unificación, resolución SLD y operador de corte (!). "
            "Implementado en Python como motor de inferencia equivalente."
        ),
        "consulta_ejemplo": "?- alerta_reabastecimiento(papas).",
        "resultado_consulta": True,
        "clausula_horn": "stock_bajo(X) :- stock_actual(X,C), stock_minimo(X,M), C =< M.",
        "representacion_logica": "stock_actual(X,C) ∧ stock_minimo(X,M) ∧ C ≤ M → stock_bajo(X)",
        "representacion_clausada": "¬stock_actual(X,C) ∨ ¬stock_minimo(X,M) ∨ ¬menor_igual(C,M) ∨ stock_bajo(X)",
        "unificacion": (
            "La variable X (Insumo en Prolog) se unifica con el nombre del producto. "
            "Ejemplo: X = papas → stock_actual(papas, 0.30), stock_minimo(papas, 0.50)."
        ),
        "operador_corte": (
            "El operador ! en Prolog interrumpe el backtracking. "
            "En Python se simula con retornos tempranos: cuando 'agotado' o 'bajo_stock' "
            "se detectan, la función retorna sin evaluar más reglas."
        ),
        "resolucion_sld": construir_resolucion_sld("papas", 0.30, 0.50),
        "total_insumos": len(diagnosticos),
        "total_alertas_logicas": len(alertas),
        "diagnosticos": diagnosticos
    }


# ============================================================
# DIAGNÓSTICO CON DATOS REALES DEL INVENTARIO
# ============================================================

def diagnosticar_desde_inventario(
    inventario: List[Dict],
    configuraciones: List[Dict]
) -> Dict:
    """
    Aplica el motor lógico al inventario real proveniente de MySQL.

    Parámetros:
        inventario:      [{"nombre": "Papas", "peso": 0.3}, ...]
        configuraciones: [{"nombre_producto": "Papas", "stock_minimo": 0.5}, ...]

    Retorna diagnóstico lógico completo con resolución SLD
    para cada insumo monitoreado por los sensores IoT.
    """
    # Unificación de variables: mapa nombre → stock_minimo
    minimos: Dict[str, float] = {
        c["nombre_producto"].lower(): float(c["stock_minimo"])
        for c in configuraciones
    }

    resultados = []
    for item in inventario:
        nombre = item["nombre"]
        peso   = float(item["peso"])
        minimo = minimos.get(nombre.lower(), 0.5)

        diag = diagnosticar_insumo(nombre, peso, minimo)
        diag["resolucion_sld"] = construir_resolucion_sld(nombre, peso, minimo)
        resultados.append(diag)

    alertas = [r for r in resultados if r["diagnostico"] in ("agotado", "bajo_stock")]

    return {
        "fuente": "Inventario real — MySQL (ultima medicion ESP32)",
        "total_insumos": len(resultados),
        "total_alertas_logicas": len(alertas),
        "clausula_horn_principal": "stock_bajo(X) :- stock_actual(X,C), stock_minimo(X,M), C =< M.",
        "representacion_logica": "stock_actual(X,C) ∧ stock_minimo(X,M) ∧ C ≤ M → stock_bajo(X)",
        "diagnosticos": resultados
    }
