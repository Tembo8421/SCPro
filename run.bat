@echo off
setlocal

rem Check if myVenv folder exist.
if not exist myVenv (
    echo Creating virtual environment...
    python -m venv myVenv
)

rem Activate Venv
call .\myVenv\Scripts\activate
rem install dependency
python -m pip install -r requirements.txt
rem RUN PY
python .\scpro.py

endlocal
