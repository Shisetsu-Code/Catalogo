@echo off
setlocal
cd /d "%~dp0"
where cargo >nul 2>nul
if errorlevel 1 (
  echo Rust no esta instalado. Instalalo desde https://rustup.rs/
  pause
  exit /b 1
)
cargo test
if errorlevel 1 (
  echo ERROR en las pruebas.
  pause
  exit /b 1
)
cargo build --release
if errorlevel 1 (
  echo ERROR al compilar.
  pause
  exit /b 1
)
if not exist "dist" mkdir "dist"
copy /Y "target\release\catalogo-proveedores.exe" "dist\catalogo-proveedores.exe" >nul
copy /Y "proveedores.json" "dist\proveedores.json" >nul
echo.
echo Listo: dist\catalogo-proveedores.exe
echo El archivo dist\proveedores.json es editable sin recompilar.
pause
