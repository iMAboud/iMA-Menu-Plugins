item(type='file|dir|drive|namespace' mode="multiple" title='Upload' vis=@if(key.shift() || key.control(), "hidden", "normal") cmd='@app.dir\plugins\imshare\iMShare.exe' args='--upload ' + sel(true, " ") image=["\uE214"])
item(type='back' title='Download' vis=@if(key.shift() || key.control(), "hidden", "normal") cmd='@app.dir\plugins\imshare\iMShare.exe' args='--download' image=["\uE213"])
