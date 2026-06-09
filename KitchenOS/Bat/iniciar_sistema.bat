@echo off
title KitchenOS - Centro de Control Maestro
color 0E

echo ===================================================
echo     Iniciando Ecosistema KitchenOS (K-OS) ...
echo     Ruta raiz: C:\KitchenOS
echo ===================================================
echo.

:: 1. Iniciar el Backend (API Central)
echo [1/6] Levantando Backend (FastAPI)...
start "K-OS Backend" cmd /k "cd /d C:\KitchenOS\backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000"
timeout /t 6 /nobreak >nul

:: 2. Iniciar el Bot de WhatsApp (Mensajeria)
echo [2/6] Despertando Bot Maestro (WhatsApp)...
start "K-OS Bot Maestro" cmd /k "cd /d C:\KitchenOS\bot_maestro && node bot_maestro.js"
timeout /t 3 /nobreak >nul

:: 3. Iniciar IA Vigilante (Stock)
echo [3/6] Activando Agente IA Vigilante...
start "IA Vigilante" cmd /k "cd /d C:\KitchenOS\ia && python ia_vigilante.py"

:: 4. Iniciar IA Asignador (Comandas)
echo [4/6] Activando Agente IA Asignador...
start "IA Asignador" cmd /k "cd /d C:\KitchenOS\ia && python ia_asignador.py"

:: 5. Iniciar IA Compras (Proveedores)
echo [5/6] Activando Agente IA Compras...
start "IA Compras" cmd /k "cd /d C:\KitchenOS\ia && python ia_compras.py"

:: 6. Servir el Frontend (Web Server)
echo [6/6] Sirviendo Interfaz Web en puerto 8080...
start "K-OS Frontend" cmd /k "cd /d C:\KitchenOS\Frontend && python -m http.server 8080"
timeout /t 2 /nobreak >nul

echo.
echo ===================================================
echo  TODO ACTIVO. Abriendo Centro de Mando en Chrome...
echo ===================================================

:: Abre el panel principal
start http://localhost:8080/index.html

echo.
echo No cierres las ventanas negras para mantener el sistema vivo.
pause