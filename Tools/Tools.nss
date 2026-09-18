menu(mode="multiple" find='.mkv|.mp4|.webm|.flv|.m4p|.mov|.png|.jpg|.jpeg|.svg|.webp|.bmp|.ico|.gif' title='Tools' image =["\uE0F8"])
{

    item(find='.png|.jpg|.jpeg|.svg|.webp|.bmp|.gif' 
                                                                    title='Upload to Imgur' 
                                                                    cmd='@app.dir\plugins\tools\iMATools.exe' 
                                                                    args='--imgur @sel.path.quote' 
                                                                    image=\uE14F)

    menu(find='.png|.jpg|.jpeg|.bmp|.gif|.tif|.tiff|.jfif|.svg|.webp' title='Reduce Size' image='<svg fill="none" viewBox="0 0 24 24"><path fill="@image.color1" d="M21 15V19H24L20 23L16 19H19V15H21ZM21.0078 3C21.5555 3 21.9999 3.44482 22 3.99316L22.001 13.3418C21.3752 13.1205 20.7015 13 20 13V5H4L4.00098 19L13.293 9.70703C13.6528 9.34601 14.22 9.31813 14.6123 9.62305L14.7061 9.70801L18.252 13.2588C15.7909 14.0071 14 16.2944 14 19C14 19.7015 14.1205 20.3752 14.3418 21.001L2.99219 21C2.44451 21 2.00013 20.5552 2 20.0068V3.99316C2.00013 3.44463 2.45577 3 2.99219 3H21.0078ZM8 7C9.10457 7 10 7.89543 10 9C10 10.1046 9.10457 11 8 11C6.89543 11 6 10.1046 6 9C6 7.89543 6.89543 7 8 7Z"/></svg>')
                                                    {
                                                
                                                    item(type="file" find=".png|.jpg|.jpeg|.bmp|.ico" 
                                                                    title="Keep Original" 
                                                                    invoke="multiple" 
                                                                    cmd='@app.dir\plugins\tools\iMATools.exe' 
                                                                    args='--resize @sel.path.quote' 
                                                                    image=\uE14C)
                                                
                                                    item(type="file" find=".png|.jpg|.jpeg|.bmp|.ico" 
                                                                    title="Overwrite" 
                                                                    invoke="multiple" 
                                                                    cmd='@app.dir\plugins\tools\iMATools.exe' 
                                                                    args='--resize -or @sel.path.quote' 
                                                                    image=\uE14C)
                                                }

    menu(find='.png|.jpg|.jpeg|.bmp|.gif|.tif|.tiff|.jfif|.svg|.webp' title='Enhance Quality' image='<svg fill="none" viewBox="0 0 24 24"><path fill="@image.color1" d="M20.7134 8.12811L20.4668 8.69379C20.2864 9.10792 19.7136 9.10792 19.5331 8.69379L19.2866 8.12811C18.8471 7.11947 18.0555 6.31641 17.0677 5.87708L16.308 5.53922C15.8973 5.35653 15.8973 4.75881 16.308 4.57612L17.0252 4.25714C18.0384 3.80651 18.8442 2.97373 19.2761 1.93083L19.5293 1.31953C19.7058 0.893489 20.2942 0.893489 20.4706 1.31953L20.7238 1.93083C21.1558 2.97373 21.9616 3.80651 22.9748 4.25714L23.6919 4.57612C24.1027 4.75881 24.1027 5.35653 23.6919 5.53922L22.9323 5.87708C21.9445 6.31641 21.1529 7.11947 20.7134 8.12811ZM2.9918 3H14V5H4V19L13.2923 9.70649C13.6828 9.31595 14.3159 9.31591 14.7065 9.70641L20 15.0104V11H22V20.0066C22 20.5552 21.5447 21 21.0082 21H2.9918C2.44405 21 2 20.5551 2 20.0066V3.9934C2 3.44476 2.45531 3 2.9918 3ZM8 11C6.89543 11 6 10.1046 6 9C6 7.89543 6.89543 7 8 7C9.10457 7 10 7.89543 10 9C10 10.1046 9.10457 11 8 11Z"/></svg>')
                                                    {
                                                
                                                    item(type='file' find='.png|.jpg|.jpeg|.bmp|.ico' title='Keep Original' invoke=multiple cmd='@app.dir\plugins\tools\iMATools.exe' args='--enhance @sel.path.quote' image=["\uE14B"])
                                                
                                                    item(type='file' find='.png|.jpg|.jpeg|.bmp|.ico' title='Overwrite' invoke=multiple cmd='@app.dir\plugins\tools\iMATools.exe' args='--enhance -or @sel.path.quote' image=["\uE14B"])
                                                }


    item(find='.png|.jpg|.jpeg|.bmp|.gif|.tif|.tiff|.jfif|.svg|.webp' title='Grid Cutter' cmd='@app.dir\plugins\tools\iMATools.exe' args='--gridcutter @sel.path.quote' image=["\uE097"])

    menu(find='.png|.jpg|.jpeg|.bmp|.gif|.tif|.tiff|.jfif|.svg|.webp' title='Convert Image' image=["\uE150"])
        {
            item(title='Convert...' cmd='@app.dir\plugins\tools\iMATools.exe' args='--convert @sel.path.quote' image=\uE150)
            separator
            item(title='To ICO' cmd='@app.dir\plugins\tools\iMATools.exe' args='--image2ico @sel.path.quote' image=\uE150)
            item(title='To PNG' cmd='@app.dir\plugins\tools\iMATools.exe' args='--image2png @sel.path.quote' image=\uE150)
            item(title='To JPG' cmd='@app.dir\plugins\tools\iMATools.exe' args='--image2jpg @sel.path.quote' image=\uE150)
            item(title='To WEBP' cmd='@app.dir\plugins\tools\iMATools.exe' args='--image2webp @sel.path.quote' image=\uE150)
        }

    item(find='.png|.jpg|.jpeg|.svg|.webp|.bmp|.gif' title='Circle Crop' cmd='@app.dir\plugins\tools\iMATools.exe' args='--circle @sel.path.quote' image='<svg fill="none" viewBox="0 0 24 24"><path fill="@image.color1" d="M23.0283 10.216c-.3959 0-.7785.22-1.0792.6168l-3.7755 4.994c-.625.8275-1.5128 1.3012-2.4355 1.3012h-.0143c-.9236 0-1.8115-.4737-2.4355-1.3012l-3.7754-4.994c-.2998-.3969-.6823-.6168-1.0802-.6168-.3949 0-.7795.22-1.0781.6168l-3.7765 4.994c-.621.8204-1.4996 1.294-2.414 1.3012C3.088 21.186 7.2113 24 12.0004 24 18.6268 24 24 18.6276 24 12.001c0-.4705-.0338-.9308-.086-1.382-.2638-.2598-.5697-.403-.8857-.403m-7.019-2.5972c-.6936 0-1.2542-.5616-1.2542-1.2541s.5606-1.2541 1.2541-1.2541c.6925 0 1.254.5616 1.254 1.254s-.5615 1.2542-1.254 1.2542M12.0005 0C5.3732 0 0 5.3714 0 12.001c0 1.0536.1504 2.0704.406 3.0463.2272.175.4788.2762.7366.2762.3979 0 .7804-.2189 1.0812-.6138l3.7754-4.996c.623-.8285 1.5129-1.3021 2.4335-1.3021.9226 0 1.8095.4736 2.4355 1.3021l3.6323 4.8037.1565.1923c.2997.3939.6812.6107 1.074.6138.3918-.003.7743-.22 1.072-.6138l.1595-.1923 3.6323-4.8037c.624-.8285 1.5118-1.3021 2.4335-1.3021.1462 0 .2935.0163.4367.0388C21.9522 3.5557 17.3922 0 12.0005 0"/></svg>')

menu(type='file' find='.png' mode='multiple' title='Crop Transparency' image=["\uE07B"])
{
    item(title='Overwrite' cmd='@app.dir\plugins\tools\iMATools.exe' args='--trimo @sel(true)' image=["\uE235"])

    item(title='Keep Original' cmd='@app.dir\plugins\tools\iMATools.exe' args='--trimk @sel(true)' image=["\uE235"])
}

}


