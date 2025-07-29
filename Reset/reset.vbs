Set shell = CreateObject("WScript.Shell")
shell.Run "cmd /c ipconfig /release & timeout /t 4 /nobreak >nul & ipconfig /renew & timeout /t 1 /nobreak >nul & ipconfig /flushdns", 0, True
