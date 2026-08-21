item(find='.cs' title='Compile' image=\uE196 cmd='C:\\Windows\\Microsoft.NET\\Framework64\\v4.0.30319\\csc.exe' args='/t:winexe /lib:"C:\\Windows\\Microsoft.NET\\Framework64\\v4.0.30319\\WPF" /r:PresentationCore.dll,PresentationFramework.dll,WindowsBase.dll,System.Web.Extensions.dll,System.Xaml.dll /out:"@(sel.path.title).exe" "@sel.path"' pos=top)

item(title='Import' pos=top type='file' where=path.file.ext(sel.path) =='.nss' cmd=io.file.append(app.cfg, "\nimport '" + sel.path + "'\n") image=[["\uE017"], ["\uE00A"]])

item
(
	type='back.dir'
	title='Pip'
	image=\uE0B5
        vis=key.control()
	cmd='powershell.exe'
	args='-NoProfile -ExecutionPolicy Bypass -File "@app.dir\plugins\pip\pip.ps1" "@sel.path"'
)

item(type='back' title='Terminal' vis=key.control() cmd='cmd' arg='/k echo @sel.path' image=["\uE0D6"] menu='' pos=3)

item(title='Run py' find='.py|.pyw' 
vis=@if(key.shift() || key.control(), "hidden", "normal") 
cmd='cmd.exe' args='/k python @sel.path.quote' dir='@sel.dir' 
pos=0 image=["\uE230"])

item(title='Build' find='.spec' 
vis=@if(key.shift() || key.control(), "hidden", "normal") 
cmd='pyinstaller' args='@sel.path.quote' dir='@sel.dir' 
pos=0 image=["\uE230"])

item(type='back' title='npm install' vis=key.control() cmd='cmd' args='/c pushd "@sel.path" && npm install && npm run build && if exist "dist" (echo "@sel.path\dist" | clip && echo Copied dist path to clipboard && firebase init) else (echo No dist folder found)' image='@app.dir\imports\icons\node_439a901a_54922f.png' menu='')

item(type='back' title='Dev' vis=key.control() 
cmd='cmd' arg='/k pushd "@sel.path" && npm run dev' 
image=["\uE295"])


item(type='back' title='Build' vis=key.control() cmd='cmd' args='/c pushd "@sel.path" && npm run build' image='@app.dir\imports\icons\1CgDvBqQ4AJczq1ov_AgkYA_537167a1_54922f.png' menu='')

item(type='back' title='Deploy' vis=key.control() cmd='cmd' args='/c pushd "@sel.path" && firebase deploy' image='@app.dir\imports\icons\1CgDvBqQ4AJczq1ov_AgkYA_537167a1_54922f.png' menu='')

item(mode=single type='file|dir|back' title='Antigravity' cmd='"C:\Users\iMA\AppData\Local\Programs\Antigravity IDE\Antigravity IDE.exe"' args='"@sel.path"' vis=key.control() image=image.res('C:/Users/iMA/AppData/Local/Programs/Antigravity IDE/Antigravity IDE.exe') menu='' pos=2)
