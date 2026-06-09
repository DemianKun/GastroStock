% ============================================================
% GastroStock — Reglas lógicas tipo Prolog
% Diagnóstico autónomo de inventario con cláusulas de Horn,
% unificación, resolución SLD y operador de corte (!)
% ============================================================

% -----------------------------------------------------------
% HECHOS: insumos monitoreados por los sensores IoT
% -----------------------------------------------------------
insumo(papas).
insumo(carne).
insumo(tomate).
insumo(cebolla).
insumo(pollo).
insumo(aceite).

% -----------------------------------------------------------
% HECHOS: umbral mínimo de stock (en kg) por insumo
% -----------------------------------------------------------
stock_minimo(papas,   0.50).
stock_minimo(carne,   0.80).
stock_minimo(tomate,  0.40).
stock_minimo(cebolla, 0.30).
stock_minimo(pollo,   0.90).
stock_minimo(aceite,  0.20).

% -----------------------------------------------------------
% HECHOS: stock actual (valores de demostración)
% En producción estos valores vienen del sensor ESP32 → MySQL
% -----------------------------------------------------------
stock_actual(papas,   0.30).
stock_actual(carne,   1.20).
stock_actual(tomate,  0.35).
stock_actual(cebolla, 0.60).
stock_actual(pollo,   0.00).
stock_actual(aceite,  0.15).

% -----------------------------------------------------------
% HECHOS: temperatura de cámara de refrigeración
% -----------------------------------------------------------
temperatura_camara(7.0).
temperatura_maxima_segura(5.0).

% ============================================================
% CLÁUSULAS DE HORN
% Forma general: cabeza :- cuerpo.
% Equivalencia lógica: ∀X. cuerpo(X) → cabeza(X)
% ============================================================

% Cláusula de Horn 1: stock agotado
% stock_actual(X,C) ∧ C <= 0 → stock_agotado(X)
stock_agotado(Insumo) :-
    stock_actual(Insumo, Cantidad),
    Cantidad =< 0.

% Cláusula de Horn 2: bajo stock
% stock_actual(X,C) ∧ stock_minimo(X,M) ∧ C <= M → stock_bajo(X)
stock_bajo(Insumo) :-
    stock_actual(Insumo, Cantidad),
    stock_minimo(Insumo, Minimo),
    Cantidad =< Minimo.

% Representación clausada (forma normal conjuntiva):
% ¬stock_actual(X,C) ∨ ¬stock_minimo(X,M) ∨ ¬menor_igual(C,M) ∨ stock_bajo(X)

% Cláusula de Horn 3: temperatura peligrosa
% temperatura_camara(T) ∧ temperatura_maxima_segura(Max) ∧ T > Max → temperatura_peligrosa
temperatura_peligrosa :-
    temperatura_camara(T),
    temperatura_maxima_segura(Max),
    T > Max.

% ============================================================
% DIAGNÓSTICO CON OPERADOR DE CORTE (!)
%
% El operador de corte (!) interrumpe el backtracking cuando
% ya se encontró un diagnóstico válido.
%
% Resolución SLD (Selective Linear Definite):
% Se parte de una consulta meta y se resuelve hacia atrás
% usando las cláusulas como reglas de inferencia.
%
% Prioridad:
%   1. agotado   → mayor urgencia → corte inmediato
%   2. bajo_stock → urgencia media → corte
%   3. estable   → sin alerta
% ============================================================

% Regla 1: Si el insumo está agotado → diagnóstico: agotado
%   El ! evita que Prolog siga buscando otras cláusulas de diagnóstico.
diagnostico(Insumo, agotado) :-
    stock_agotado(Insumo),
    !.

% Regla 2: Si el stock está bajo (pero no agotado) → diagnóstico: bajo_stock
diagnostico(Insumo, bajo_stock) :-
    stock_bajo(Insumo),
    !.

% Regla 3: Si ninguna condición anterior aplica → diagnóstico: estable
diagnostico(Insumo, estable) :-
    stock_actual(Insumo, Cantidad),
    stock_minimo(Insumo, Minimo),
    Cantidad > Minimo.

% -----------------------------------------------------------
% Alerta de reabastecimiento
% -----------------------------------------------------------
alerta_reabastecimiento(Insumo) :-
    diagnostico(Insumo, agotado).

alerta_reabastecimiento(Insumo) :-
    diagnostico(Insumo, bajo_stock).

% -----------------------------------------------------------
% Acción recomendada (también usa !)
% -----------------------------------------------------------
accion_recomendada(Insumo, compra_urgente) :-
    diagnostico(Insumo, agotado),
    !.

accion_recomendada(Insumo, solicitar_reabastecimiento) :-
    diagnostico(Insumo, bajo_stock),
    !.

accion_recomendada(Insumo, continuar_monitoreo) :-
    diagnostico(Insumo, estable).

% -----------------------------------------------------------
% Diagnóstico de cámara
% -----------------------------------------------------------
diagnostico_camara(alerta_temperatura) :-
    temperatura_peligrosa,
    !.

diagnostico_camara(temperatura_estable).

% ============================================================
% CONSULTAS DE EJEMPLO (ejecutar en intérprete Prolog):
%
% ?- diagnostico(papas, Estado).
%    Estado = bajo_stock.
%
% ?- diagnostico(pollo, Estado).
%    Estado = agotado.
%
% ?- diagnostico(carne, Estado).
%    Estado = estable.
%
% ?- alerta_reabastecimiento(papas).
%    true.
%
% ?- accion_recomendada(pollo, Accion).
%    Accion = compra_urgente.
%
% ?- diagnostico_camara(Estado).
%    Estado = alerta_temperatura.
% ============================================================
