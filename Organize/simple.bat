@echo off
setlocal EnableExtensions EnableDelayedExpansion

if "%~1"=="" (
    echo No files selected.
    exit /b
)

set "parentDir=%~dp1"

set "Images=png jpg jpeg gif bmp webp tif tiff ico heic jfif avif svg psd ai eps raw cr2 nef dng arw orf sr2 heif 3fr erf rw2 tga pbm pgm ppm jp2 j2k xpm pcx"
set "Videos=mp4 mkv mov avi wmv flv webm mpg mpeg m4v 3gp ts m2ts ogv asf wtv dvr-ms divx xvid f4v swf rm rmvb"
set "Audio=mp3 wav flac ogg aac m4a wma opus amr aif aiff mid midi caf weba alac m4b dss ac3 aifc"
set "Documents=pdf doc docx docm rtf txt md markdown csv tsv xls xlsx xlsm xlsb ppt pptx pps ppsx odt ods odp epub mobi azw azw3 chm onenote vsd pub lit ps"
set "Scripts=bat cmd ps1 psd1 psm1 vbs vbe js jse wsf wsh py pyw rb pl php go cs java class c cpp cc cxx h hpp hxx rs kt kts swift lua ts tsx jsx json yml yaml ini cfg toml env reg sql sh bash zsh csh ksh tcl vim html htm css conf properties"
set "Executables=exe msi msp msu appx appxbundle msix msixbundle app com scr cab"
set "Compressed=zip rar 7z tar gz bz2 xz zst tgz tbz tbz2 txz cab iso img bin cue dmg vhd vhdx rar5 udf daa"
set "Fonts=ttf otf woff woff2 eot fon"
set "Subtitles=srt ass vtt sub idx sup"
set "Shortcuts=lnk url webloc"
set "Torrents=torrent"
set "3D Models=obj stl dae fbx 3ds max blend"
set "Geographic=shp kml gpx kmz gdb"
set "Databases=db sql sqlite mdb accdb"
set "Web Assets=xml xsl xsd"
set "Other="

:loop
if "%~1"=="" goto :eof

set "filePath=%~1"
set "fileName=%~n1"
set "fileExt=%~x1"
set "currentDir=%~dp1"

if exist "!filePath!\" (
    shift
    goto loop
)

set "fileExt=!fileExt:.=!"

set "destinationFolder="
for %%F in (Images Videos Audio Documents Scripts Executables Compressed Fonts Subtitles Shortcuts Torrents) do (
    for %%E in (!%%F!) do (
        if /i "!fileExt!"=="%%E" (
            set "destinationFolder=%%F"
            goto :moveFile
        )
    )
)

:moveFile
if not defined destinationFolder set "destinationFolder=Other"

set "fullDestinationPath=%parentDir%!destinationFolder!\"
set "relativeDir=!currentDir:%parentDir%=!"
if not "!relativeDir!"=="" (
    if "!relativeDir:~-1!"=="\" set "relativeDir=!relativeDir:~0,-1!"
    for %%P in (Images Videos Audio Documents Scripts Executables Compressed Fonts Subtitles Shortcuts Torrents Other) do (
        if /i "!relativeDir!"=="%%P" goto :moveFinal
    )
    for %%P in (Images Videos Audio Documents Scripts Executables Compressed Fonts Subtitles Shortcuts Torrents Other) do (
        if /i "!relativeDir:!fileExt!=!"=="%%P\" (
            move /y "!filePath!" "%parentDir%!destinationFolder!\" >nul
            shift
            goto loop
        )
    )
)

:moveFinal
if not exist "%fullDestinationPath%" mkdir "%fullDestinationPath%"

move /y "!filePath!" "%fullDestinationPath%" >nul

shift
goto loop