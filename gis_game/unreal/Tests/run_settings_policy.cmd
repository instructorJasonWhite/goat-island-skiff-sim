@echo off
setlocal
set "TEST_DIR=%~dp0"
set "VCVARS=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
if not exist "%VCVARS%" exit /b 2
if not exist "%TEST_DIR%build" mkdir "%TEST_DIR%build"
call "%VCVARS%" >nul 2>nul
if errorlevel 1 exit /b 2
cl /nologo /std:c++17 /EHsc /W4 /permissive- /Fe:"%TEST_DIR%build\SettingsPolicyTests.exe" "%TEST_DIR%settings_policy_test.cpp"
if errorlevel 1 exit /b 1
"%TEST_DIR%build\SettingsPolicyTests.exe"
exit /b %errorlevel%
