@echo off
echo ===============================================
echo  Gerando o executavel AutomacaoPrecos.exe
echo ===============================================
 
echo.
echo Instalando dependencias (pyinstaller, selenium, pandas, openpyxl)...
pip install pyinstaller selenium pandas openpyxl
 
echo.
echo Gerando o .exe...
pyinstaller --onefile --windowed --collect-all selenium --name AutomacaoPrecos projeto_automacao.py
 
echo.
echo ===============================================
echo  Pronto! O executavel esta em: dist\AutomacaoPrecos.exe
echo ===============================================
pause