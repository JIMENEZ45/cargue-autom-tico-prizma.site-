# Arranca AUTO PRIZMA PRO en este equipo SIN pedir login.
#
# Uso:  powershell -ExecutionPolicy Bypass -File scripts\run_local.ps1 [-Usuario <usuario>]
#
# Entra como -Usuario (debe existir y estar activo: scripts\manage_users.py listar).
# Solo vale desde 127.0.0.1: desde otra IP se sigue pidiendo usuario y contraseña.
# Las credenciales de PRIZMA de cada cargue se siguen pidiendo. Nunca usar en un servidor.
param(
    [string]$Usuario = "12345678",
    [int]$Puerto = 8000
)

$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz

$python = Join-Path $raiz ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

$env:AUTO_PRIZMA_SIN_LOGIN = $Usuario
# Evita UnicodeEncodeError del motor cuando la salida no es UTF-8 (ver CLAUDE.md).
$env:PYTHONIOENCODING = "utf-8"

& $python -m uvicorn main:app --reload --host 127.0.0.1 --port $Puerto
