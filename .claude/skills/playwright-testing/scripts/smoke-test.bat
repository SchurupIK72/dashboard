@echo off
REM HTTP smoke check for a local UI stand (Windows).
REM Usage: smoke-test.bat [base_url] [path ...]
REM   base_url defaults to http://127.0.0.1:8000; paths default to "/"
REM   Paths come from arguments (or the scenario's Preconditions) — never hardcoded.
REM Reachability only: a 200 answer does NOT prove the stand's identity.

setlocal
set BASE_URL=%1
if not defined BASE_URL set BASE_URL=http://127.0.0.1:8000
set /a FAILS=0

echo Smoke checks against %BASE_URL%
echo ========================================

shift
if "%~1"=="" call :check "/"
:loop
if "%~1"=="" goto done
call :check "%~1"
shift
goto loop

:done
echo ========================================
echo Smoke checks complete. Failures: %FAILS%
if %FAILS% gtr 0 exit /b 1
exit /b 0

:check
set STATUS=000
for /f %%S in ('curl -s -o nul -w "%%{http_code}" "%BASE_URL%%~1"') do set STATUS=%%S
if "%STATUS%"=="200" (
    set VERDICT=PASS
) else (
    set VERDICT=FAIL
    set /a FAILS+=1
)
echo %VERDICT% %~1 (%STATUS%)
exit /b 0
