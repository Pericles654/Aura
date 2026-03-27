@echo off
chcp 65001 >nul 2>&1
echo ========================================
echo   Aura CashFlow - Instalacao Automatica
echo ========================================
echo.

REM === Verificar se Python esta instalado ===
where python >nul 2>&1
if %errorlevel%==0 (
    set PYTHON_CMD=python
    goto :found_python
)

where py >nul 2>&1
if %errorlevel%==0 (
    set PYTHON_CMD=py
    goto :found_python
)

where python3 >nul 2>&1
if %errorlevel%==0 (
    set PYTHON_CMD=python3
    goto :found_python
)

REM Tentar caminhos comuns do Python no Windows
for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "%PROGRAMFILES%\Python313\python.exe"
    "%PROGRAMFILES%\Python312\python.exe"
    "%PROGRAMFILES%\Python311\python.exe"
    "%PROGRAMFILES%\Python310\python.exe"
    "C:\Python313\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Python310\python.exe"
) do (
    if exist %%P (
        set PYTHON_CMD=%%P
        goto :found_python
    )
)

echo.
echo ERRO: Python nao encontrado!
echo.
echo Instale o Python em: https://www.python.org/downloads/
echo IMPORTANTE: Marque a opcao "Add Python to PATH" durante a instalacao.
echo.
pause
exit /b 1

:found_python
echo Python encontrado: %PYTHON_CMD%
%PYTHON_CMD% --version
echo.

REM === Clonar ou atualizar repositorio ===
cd C:\
if exist Aura (
    echo Pasta Aura ja existe, atualizando...
    cd Aura
    git pull origin claude/good-morning-G808G
) else (
    echo Clonando repositorio...
    git clone https://github.com/Pericles654/Aura.git
    cd Aura
)

echo.
echo Mudando para branch correta...
git checkout claude/good-morning-G808G

echo.
echo Instalando dependencias Python...
%PYTHON_CMD% -m pip install flask openpyxl pandas
if %errorlevel% neq 0 (
    echo.
    echo Tentando com --user...
    %PYTHON_CMD% -m pip install --user flask openpyxl pandas
)
if %errorlevel% neq 0 (
    echo.
    echo Tentando ignorar blinker...
    %PYTHON_CMD% -m pip install --ignore-installed blinker flask openpyxl pandas
)

echo.
echo ========================================
echo   Iniciando servidor na porta 5000
echo   Abra no navegador: http://localhost:5000
echo ========================================
echo.
%PYTHON_CMD% app.py

pause
