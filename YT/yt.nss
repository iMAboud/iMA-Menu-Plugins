
item(title='Youtube'  image=\uE248 where = '@(str.contains(clipboard.get, "Youtu"))' cmd='@app.dir\plugins\yt\yt.exe')


item(title='X' where = '@(str.contains(clipboard.get, "x.com"))' cmd='@app.dir\plugins\yt\yt.exe'
image='icons\x.png')


item(title='Twitch'  image=\uE241 where = '@(str.contains(clipboard.get, "twitch.tv"))' cmd='@app.dir\plugins\yt\yt.exe')


item(title='Instagram' where = '@(str.contains(clipboard.get, "instagram.com"))' cmd='@app.dir\plugins\yt\yt.exe'
image='@app.dir\plugins\YT\icons\instagram.png')


item(title='TikTok' where = '@(str.contains(clipboard.get, "TikTok.com"))' cmd='@app.dir\plugins\yt\yt.exe'
image='@app.dir\plugins\YT\icons\tiktok.png')


item(title='Reddit'  image=\uE23E where = '@(str.contains(clipboard.get, "redd.it"))' cmd='@app.dir\plugins\yt\yt.exe')


item(title='Facebook' image=\uE244 where='@(str.contains(clipboard.get, "facebook.com", "fb.watch"))' cmd='@app.dir\plugins\yt\yt.exe')


item(title='LinkedIn' image=\uE240 where='@(str.contains(clipboard.get, "linkedin.com"))' cmd='@app.dir\plugins\yt\yt.exe')


item(title='Vimeo' where='@(str.contains(clipboard.get, "vimeo.com"))' cmd='@app.dir\plugins\yt\yt.exe'
image='@app.dir\plugins\YT\icons\vimeo.png')


item(title='Download Video' image=\uE1F9 where='@(str.contains(clipboard.get, "http"))' vis=key.shift() cmd='@app.dir\plugins\yt\yt.exe')
