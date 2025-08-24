item(title="Reset Network"
     type='taskbar'
     image=\uE11F
     vis=key.shift()
     cmd='cmd.exe'
     args='/c ipconfig /release & timeout /t 4 /nobreak >nul & ipconfig /renew & timeout /t 1 /nobreak >nul & ipconfig /flushdns'
     window=hidden)