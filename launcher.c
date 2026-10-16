#define UNICODE
#define _UNICODE
#include <windows.h>
#include <shlwapi.h>
#include <stdio.h>

#pragma comment(lib, "shlwapi.lib")

static BOOL FileExists(const wchar_t *path) {
    DWORD dwAttrib = GetFileAttributesW(path);
    return (dwAttrib != INVALID_FILE_ATTRIBUTES && !(dwAttrib & FILE_ATTRIBUTE_DIRECTORY));
}

static BOOL FindPython(wchar_t *outPath, size_t outSize, const wchar_t *appDir) {
    wchar_t candidate[MAX_PATH];

    // 1. Check local python directory: <appDir>\python\pythonw.exe
    _snwprintf(candidate, MAX_PATH, L"%s\\python\\pythonw.exe", appDir);
    if (FileExists(candidate)) {
        wcsncpy(outPath, candidate, outSize);
        return TRUE;
    }

    // 2. Check current user's Python 3.14 standard path
    _snwprintf(candidate, MAX_PATH, L"C:\\Users\\Adam\\AppData\\Local\\Programs\\Python\\Python314\\pythonw.exe");
    if (FileExists(candidate)) {
        wcsncpy(outPath, candidate, outSize);
        return TRUE;
    }

    // 3. Search in system PATH for pythonw.exe
    if (SearchPathW(NULL, L"pythonw.exe", NULL, MAX_PATH, candidate, NULL) > 0) {
        wcsncpy(outPath, candidate, outSize);
        return TRUE;
    }

    // 4. Check registry HKCU\Software\Python\PythonCore\3.14\InstallPath
    HKEY hKey;
    if (RegOpenKeyExW(HKEY_CURRENT_USER, L"Software\\Python\\PythonCore\\3.14\\InstallPath", 0, KEY_READ, &hKey) == ERROR_SUCCESS) {
        wchar_t regPath[MAX_PATH];
        DWORD regSize = sizeof(regPath);
        if (RegQueryValueExW(hKey, L"ExecutablePath", NULL, NULL, (LPBYTE)regPath, &regSize) == ERROR_SUCCESS) {
            // Replace python.exe with pythonw.exe if possible
            wchar_t *p = wcsrchr(regPath, L'\\');
            if (p) {
                *(p + 1) = L'\0';
                _snwprintf(candidate, MAX_PATH, L"%spythonw.exe", regPath);
                if (FileExists(candidate)) {
                    wcsncpy(outPath, candidate, outSize);
                    RegCloseKey(hKey);
                    return TRUE;
                }
            }
        }
        RegCloseKey(hKey);
    }

    // 5. Fallback: Search python.exe in PATH
    if (SearchPathW(NULL, L"python.exe", NULL, MAX_PATH, candidate, NULL) > 0) {
        wcsncpy(outPath, candidate, outSize);
        return TRUE;
    }

    return FALSE;
}

int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, LPSTR lpCmdLine, int nCmdShow) {
    wchar_t exePath[MAX_PATH];
    wchar_t appDir[MAX_PATH];
    wchar_t scriptPath[MAX_PATH];
    wchar_t pythonPath[MAX_PATH];

    if (!GetModuleFileNameW(NULL, exePath, MAX_PATH)) {
        MessageBoxW(NULL, L"Gagal mendeteksi lokasi file executable.", L"XMPP Chat Error", MB_ICONERROR | MB_OK);
        return 1;
    }

    // Get folder containing the executable
    wcsncpy(appDir, exePath, MAX_PATH);
    wchar_t *lastSlash = wcsrchr(appDir, L'\\');
    if (lastSlash) {
        *lastSlash = L'\0';
    } else {
        wcscpy(appDir, L".");
    }

    // Path to xmpp_chat.py
    _snwprintf(scriptPath, MAX_PATH, L"%s\\xmpp_chat.py", appDir);
    if (!FileExists(scriptPath)) {
        wchar_t errMsg[MAX_PATH + 100];
        _snwprintf(errMsg, sizeof(errMsg)/sizeof(wchar_t), L"File xmpp_chat.py tidak ditemukan di:\n%s", scriptPath);
        MessageBoxW(NULL, errMsg, L"XMPP Chat Error", MB_ICONERROR | MB_OK);
        return 1;
    }

    // Find Python
    if (!FindPython(pythonPath, MAX_PATH, appDir)) {
        MessageBoxW(NULL, L"Python (pythonw.exe) tidak ditemukan di sistem.\nPastikan Python telah terpasang.", L"XMPP Chat Error", MB_ICONERROR | MB_OK);
        return 1;
    }

    // Construct command line: "<pythonw>" "<appDir>\xmpp_chat.py"
    wchar_t cmdLine[MAX_PATH * 3];
    _snwprintf(cmdLine, sizeof(cmdLine)/sizeof(wchar_t), L"\"%s\" \"%s\"", pythonPath, scriptPath);

    STARTUPINFOW si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si));
    si.cb = sizeof(si);
    si.dwFlags = STARTF_USESHOWWINDOW;
    si.wShowWindow = SW_HIDE;
    ZeroMemory(&pi, sizeof(pi));

    if (!CreateProcessW(
            NULL,
            cmdLine,
            NULL,
            NULL,
            FALSE,
            CREATE_NO_WINDOW,
            NULL,
            appDir,
            &si,
            &pi)) {
        wchar_t errMsg[512];
        _snwprintf(errMsg, 512, L"Gagal menjalankan aplikasi.\nError code: %lu", GetLastError());
        MessageBoxW(NULL, errMsg, L"XMPP Chat Error", MB_ICONERROR | MB_OK);
        return 1;
    }

    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);
    return 0;
}
