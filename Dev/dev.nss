item(find='.cs' title='Compile C#' image=\uE196 cmd='C:\\Windows\\Microsoft.NET\\Framework64\\v4.0.30319\\csc.exe' args='/t:winexe /lib:"C:\\Windows\\Microsoft.NET\\Framework64\\v4.0.30319\\WPF" /r:PresentationCore.dll,PresentationFramework.dll,WindowsBase.dll,System.Web.Extensions.dll,System.Xaml.dll /out:"@(sel.path.title).exe" "@sel.path"' pos=top)

item(title='Import .nss' pos=top type='file' where=path.file.ext(sel.path) =='.nss' cmd=io.file.append(app.cfg, "\nimport '" + sel.path + "'\n") image=[["\uE017"], ["\uE00A"]])

item(type='back|dir' title='Pip install' image=\uE0B5 vis=key.control() cmd='powershell.exe' args='-NoProfile -ExecutionPolicy Bypass -File "@app.dir\plugins\pip\pip.ps1" "@sel.path"')

item(type='back' title='Terminal' vis=key.control() cmd='cmd' arg='/k echo @sel.path' image=["\uE0D6"] pos=3)

item(title='Run py' find='.py|.pyw' vis=@if(key.shift() || key.control(), "hidden", "normal") cmd='cmd.exe' args='/k python @sel.path.quote' dir=@sel.dir pos=0 image=["\uE230"])

item(title='Pyinstaller Build' find='.spec' vis=@if(key.shift() || key.control(), "hidden", "normal") cmd='pyinstaller' args=@sel.path.quote dir=@sel.dir pos=0 image=["\uE230"])

item(type='back' title='npm install' vis=key.control() cmd='cmd' args='/c pushd "@sel.path" && npm install && npm run build && if exist "dist" (echo "@sel.path\dist" | clip && echo Copied dist path to clipboard && firebase init) else (echo No dist folder found)' image='<svg fill="none" viewBox="0 0 24 24"><path fill="@image.color1" d="M20.001 3C20.5533 3 21.001 3.44772 21.001 4V20C21.001 20.5523 20.5533 21 20.001 21H4.00098C3.44869 21 3.00098 20.5523 3.00098 20V4C3.00098 3.44772 3.44869 3 4.00098 3H20.001ZM19.001 5H5.00098V19H19.001V5ZM17.001 7V17H14.501V9.5H12.001V17H7.00098V7H17.001Z"/></svg>')

item(type='back' title='npm Dev' vis=key.control() cmd='cmd' arg='/k pushd "@sel.path" && npm run dev' image=["\uE295"])


item(type='back' title='npm Build' vis=key.control() cmd='cmd' args='/c pushd "@sel.path" && npm run build' image='<svg fill="none" viewBox="0 0 24 24"><path fill="@image.color1" d="M10 10.1111V1L21 7V21H3V7L10 10.1111Z"/></svg>')

item(type='back' title='Firebase Deploy' vis=key.control() cmd='cmd' args='/c pushd "@sel.path" && firebase deploy' image=["\uE15A"])