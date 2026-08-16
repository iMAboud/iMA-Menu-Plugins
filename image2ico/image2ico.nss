
item(find='.png|.jpg|.jpeg|.bmp|.gif|.tif|.tiff|.jfif|.svg|.bmp'   
    title='Convert to ICO' cmd='cmd.exe' args='/c echo @sel.path | clip & start "" "@app.dir\plugins\image2ico\image2ico.exe"'   
    image=["\uE148"] window=hidden menu='tools')
