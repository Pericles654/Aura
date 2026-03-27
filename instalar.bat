@echo off
echo ========================================
echo   Aura CashFlow - Instalacao Automatica
echo ========================================
echo.

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
pip install flask openpyxl pandas

echo.
echo ========================================
echo   Iniciando servidor na porta 5000
echo   Abra: http://localhost:5000
echo ========================================
echo.
python app.py

pause
