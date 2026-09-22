@echo off
echo ===============================================
echo  Gerando o executavel AutomacaoPrecos.exe
echo ===============================================
 
echo.
echo Instalando dependencias (pyinstaller, selenium, pandas, openpyxl, ttkbootstrap)...
python -m pip install --upgrade pip
python -m pip install pyinstaller selenium pandas openpyxl ttkbootstrap
if errorlevel 1 (
    echo.
    echo ERRO ao instalar as dependencias. Verifique se o Python e o pip
    echo estao instalados corretamente e se o comando "python" funciona
    echo no seu terminal.
    pause
    exit /b 1
)
 
echo.
echo Gerando o .exe...
REM Usamos "python -m PyInstaller" em vez de "pyinstaller" direto porque
REM o comando "pyinstaller" isolado depende da pasta Scripts do Python
REM estar no PATH do Windows -- as vezes nao esta, mesmo com o pacote
REM instalado corretamente. "python -m PyInstaller" sempre funciona,
REM pois usa o mesmo Python que acabou de instalar o pacote acima.
REM --collect-all selenium e --collect-all ttkbootstrap: garantem que
REM todos os submodulos e arquivos de tema/estilo dessas bibliotecas
REM sejam incluidos no executavel (senao da erro de "No module named").
python -m PyInstaller --onefile --windowed --collect-all selenium --collect-all ttkbootstrap --name AutomacaoPrecos projeto_automacao.py
if errorlevel 1 (
    echo.
    echo ERRO ao gerar o executavel. Veja a mensagem de erro acima
    echo para saber o motivo exato.
    pause
    exit /b 1
)
 
echo.
echo ===============================================
echo  Pronto! O executavel esta em: dist\AutomacaoPrecos.exe
echo ===============================================
pause