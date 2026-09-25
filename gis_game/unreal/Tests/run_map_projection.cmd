@echo off
setlocal
set "TEST_DIR=%~dp0"
set "VCVARS=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
if not exist "%VCVARS%" (
  echo MSVC Build Tools 2022 are required for this map projection test. 1>&2
  exit /b 2
)
if not exist "%TEST_DIR%build" mkdir "%TEST_DIR%build"
call "%VCVARS%" >nul 2>nul
if errorlevel 1 exit /b 2
cl /nologo /std:c++17 /EHsc /W4 /permissive- /Fo:"%TEST_DIR%build\map_projection_test.obj" /Fe:"%TEST_DIR%build\MapProjectionTests.exe" "%TEST_DIR%map_projection_test.cpp"
if errorlevel 1 exit /b 1
"%TEST_DIR%build\MapProjectionTests.exe"
exit /b %errorlevel%
