@echo off
echo ===================================
echo Building JabriX Native C Launcher...
echo ===================================

windres resource.rc -O coff -o resource.res
if %errorlevel% neq 0 (
    echo [ERROR] Gagal kompilasi resource.rc
    pause
    exit /b %errorlevel%
)

clang -O2 -mwindows -s launcher.c resource.res -o JabriX.exe
if %errorlevel% neq 0 (
    echo [ERROR] Gagal kompilasi launcher.c
    del resource.res 2>nul
    pause
    exit /b %errorlevel%
)

copy /y JabriX.exe XMPP_Chat.exe >nul
del resource.res 2>nul

echo [SUCCESS] JabriX.exe berhasil dibangun (Ukuran: ~97 KB)
pause
