@echo off
echo ========================================
echo   Trying Reflex (Streamlit stays safe!)
echo ========================================
echo.

echo Step 1: Installing Reflex...
pip install reflex

echo.
echo Step 2: Setting up Reflex app...
cd reflex_app
reflex init

echo.
echo ========================================
echo   Setup Complete!
echo ========================================
echo.
echo To run BOTH apps simultaneously:
echo.
echo   Terminal 1: streamlit run app.py
echo   Terminal 2: cd reflex_app ^&^& reflex run
echo.
echo Streamlit: http://localhost:8501
echo Reflex:    http://localhost:3000
echo.
pause
