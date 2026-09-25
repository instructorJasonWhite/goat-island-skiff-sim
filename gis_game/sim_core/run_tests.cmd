@echo off
setlocal
set "SIM_DIR=%~dp0"
if not exist "%SIM_DIR%build" mkdir "%SIM_DIR%build"

set "SIM_ZIG="
if exist "%SIM_DIR%.toolchain\ziglang\zig.exe" set "SIM_ZIG=%SIM_DIR%.toolchain\ziglang\zig.exe"
if not defined SIM_ZIG for %%Z in (zig.exe) do if not "%%~$PATH:Z"=="" set "SIM_ZIG=%%~$PATH:Z"
if defined SIM_ZIG goto zig_build

set "VCVARS=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
if not exist "%VCVARS%" goto missing_toolchain
set "SDK_READY="
for /d %%V in ("C:\Program Files (x86)\Windows Kits\10\Include\*") do if exist "%%~fV\ucrt\math.h" set "SDK_READY=1"
if not defined SDK_READY goto missing_toolchain
call "%VCVARS%" >nul 2>nul
if errorlevel 1 goto missing_toolchain
cl /nologo /std:c++17 /EHsc /W4 /permissive- /Fe:"%SIM_DIR%build\SailingSimTests.exe" "%SIM_DIR%tests.cpp" "%SIM_DIR%SailingSim.cpp"
if errorlevel 1 exit /b 1
goto run_tests

:zig_build
set "ZIG_GLOBAL_CACHE_DIR=%SIM_DIR%build\zig-global"
set "ZIG_LOCAL_CACHE_DIR=%SIM_DIR%build\zig-local"
"%SIM_ZIG%" c++ -std=c++17 -O2 -Wall -Wextra -pedantic "%SIM_DIR%tests.cpp" "%SIM_DIR%SailingSim.cpp" -o "%SIM_DIR%build\SailingSimTests.exe"
if errorlevel 1 exit /b 1
goto run_tests

:run_tests
"%SIM_DIR%build\SailingSimTests.exe"
exit /b %errorlevel%

:missing_toolchain
echo SailingSim tests need Zig 0.14+ on PATH, or MSVC Build Tools with a Windows SDK including UCRT headers. 1>&2
exit /b 2
