@echo off
title Remote Design Job Machine - Balogun Olamide
echo =========================================================
echo   Starting Remote Design Job Command Center (FastAPI)
echo   Target: Graphic Design & UI/UX Design (100%% Remote)
echo =========================================================
echo.
echo Opening http://127.0.0.1:8000 in your browser...
start http://127.0.0.1:8000
python -m uvicorn app:app --reload --port 8000
pause
