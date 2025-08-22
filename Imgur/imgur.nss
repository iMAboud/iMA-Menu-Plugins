menu(mode="multiple" find='.mkv|.mp4|.webm|.flv|.m4p|.mov|.png|.jpg|.jpeg|.svg|.webp|.bmp|.ico|.gif' title='Tools' image =\uE0F8)
{
    item(find='.png|.jpg|.jpeg|.svg|.webp|.bmp|.gif' 
    title='Upload to imgur' cmd='cmd.exe' args='/c echo @sel.path | clip & start "" "@app.dir\plugins\imgur\imgur.exe"' image=\uE14F)

}