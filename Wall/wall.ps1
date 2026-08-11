$ErrorActionPreference = "Stop"

# Pool of curated minimalist/dark tags
$prompts = @("minimalist", "dark", "grey", "monochrome", "abstract", "cyberpunk", "dystopian", "space", "nature")
$tag = $prompts | Get-Random

# Wallhaven API Parameters:
# categories=100 -> General ONLY (0 Anime, 0 People/Girls)
# purity=100     -> SFW ONLY
# ratios=16x9    -> Strict desktop aspect ratio
$apiUrl = "https://wallhaven.cc/api/v1/search?q=$tag&categories=100&purity=100&ratios=16x9&atleast=1920x1080&sorting=random"

$wc = New-Object System.Net.WebClient
$json = $wc.DownloadString($apiUrl) | ConvertFrom-Json

if ($json.data.Count -gt 0) {
    # Pick top random result URL
    $imageUrl = $json.data[0].path
    
    $dir = "$env:TEMP\Wallhaven"
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
    $localFile = "$dir\wallpaper.jpg"

    # Fast download
    $wc.DownloadFile($imageUrl, $localFile)

    # Set Desktop Wallpaper via SystemParametersInfo
    $typeDefinition = @"
    using System.Runtime.InteropServices;
    public class Wallpaper {
        [DllImport("user32.dll", CharSet = CharSet.Auto)]
        public static extern int SystemParametersInfo(int uAction, int uParam, string lpvParam, int fuWinIni);
    }
"@
    Add-Type -TypeDefinition $typeDefinition
    [Wallpaper]::SystemParametersInfo(20, 0, $localFile, 3)
}