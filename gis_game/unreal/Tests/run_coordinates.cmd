@echo off
setlocal
set "TEST_DIR=%~dp0"
set "VCVARS=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
if not exist "%VCVARS%" (
  echo MSVC Build Tools 2022 are required for this standalone coordinate test. 1>&2
  exit /b 2
)
set "SDK_READY="
for /d %%V in ("C:\Program Files (x86)\Windows Kits\10\Include\*") do if exist "%%~fV\ucrt\crtdbg.h" set "SDK_READY=1"
if not defined SDK_READY (
  echo A Windows SDK with UCRT headers is required for this standalone coordinate test. 1>&2
  exit /b 2
)
if not exist "%TEST_DIR%build" mkdir "%TEST_DIR%build"
call "%VCVARS%" >nul 2>nul
if errorlevel 1 exit /b 2
cl /nologo /std:c++17 /EHsc /W4 /permissive- /Fe:"%TEST_DIR%build\CoordinatesTests.exe" "%TEST_DIR%coordinates_test.cpp"
if errorlevel 1 exit /b 1
"%TEST_DIR%build\CoordinatesTests.exe"
exit /b %errorlevel%
