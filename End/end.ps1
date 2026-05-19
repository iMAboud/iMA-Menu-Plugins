param(
    [string]$Path
)

# Load GUI assemblies
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# 1. Clean, Custom Dark-Themed Fade-out Popup Definition
function Show-DonePopup {
    $form = New-Object System.Windows.Forms.Form
    $form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::None
    $form.StartPosition = [System.Windows.Forms.FormStartPosition]::Manual
    $form.BackColor = [System.Drawing.Color]::FromArgb(32, 32, 32)
    $form.ForeColor = [System.Drawing.Color]::White
    $form.Size = New-Object System.Drawing.Size(180, 50)
    $form.TopMost = $true
    $form.ShowInTaskbar = $false

    $screen = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
    $form.Location = New-Object System.Drawing.Point(
        ($screen.Width - $form.Width) / 2,
        ($screen.Height - $form.Height) / 2
    )

    $form.add_Load({
        $rect = New-Object System.Drawing.Rectangle(0, 0, $this.Width, $this.Height)
        $path = New-Object System.Drawing.Drawing2D.GraphicsPath
        $radius = 12
        $path.AddArc($rect.X, $rect.Y, $radius, $radius, 180, 90)
        $path.AddArc($rect.Right - $radius, $rect.Y, $radius, $radius, 270, 90)
        $path.AddArc($rect.Right - $radius, $rect.Bottom - $radius, $radius, $radius, 0, 90)
        $path.AddArc($rect.X, $rect.Bottom - $radius, $radius, $radius, 90, 90)
        $path.CloseAllFigures()
        $this.Region = New-Object System.Drawing.Region($path)
    })

    $label = New-Object System.Windows.Forms.Label
    $label.Text = [char]0x2714 + "  Done"
    $label.Font = New-Object System.Drawing.Font("Segoe UI", 11, [System.Drawing.FontStyle]::Bold)
    $label.TextAlign = [System.Drawing.ContentAlignment]::MiddleCenter
    $label.Dock = [System.Windows.Forms.DockStyle]::Fill
    $form.Controls.Add($label)

    $timer = New-Object System.Windows.Forms.Timer
    $timer.Interval = 20
    $ticks = 0
    $timer.add_Tick({
        $script:ticks++
        if ($ticks -lt 50) {
            # Keep open
        } elseif ($ticks -lt 75) {
            $form.Opacity = (75 - $ticks) / 25
        } else {
            $timer.Stop()
            $form.Close()
        }
    })

    $form.Opacity = 0.95
    $timer.Start()
    $form.ShowDialog()
}

# 2. Self-Elevation Check & Execution
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    try {
        if ([string]::IsNullOrWhiteSpace($Path)) {
            $Path = Get-Clipboard -Format Text -Raw
        }
        if (-not [string]::IsNullOrWhiteSpace($Path)) {
            $Path = $Path.Trim().Trim('"')
        }
        
        $args = @("-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-File", $PSCommandPath, "-Path", $Path)
        Start-Process powershell.exe -ArgumentList $args -Verb RunAs -WindowStyle Hidden
        [Environment]::Exit(0)
    } catch {
        [System.Windows.Forms.MessageBox]::Show("This tool requires Administrator privileges to unlock files.", "iMA Menu - Privilege Required", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Warning)
        [Environment]::Exit(1)
    }
}

# 3. Get and Validate Path
if ([string]::IsNullOrWhiteSpace($Path)) {
    $Path = Get-Clipboard -Format Text -Raw
}

if ([string]::IsNullOrWhiteSpace($Path)) {
    [System.Windows.Forms.MessageBox]::Show("No file or folder path selected.", "iMA Menu - Error", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Error)
    [Environment]::Exit(1)
}

$Path = $Path.Trim().Trim('"')
if (-not (Test-Path $Path)) {
    [System.Windows.Forms.MessageBox]::Show("Selected path does not exist: $Path", "iMA Menu - Error", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Error)
    [Environment]::Exit(1)
}

# 4. Define Native Restart Manager API
$csharpCode = @'
using System;
using System.Runtime.InteropServices;
using System.Collections.Generic;

public class LockDetector {
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct RM_UNIQUE_PROCESS {
        public int dwProcessId;
        public System.Runtime.InteropServices.ComTypes.FILETIME ProcessStartTime;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct RM_PROCESS_INFO {
        public RM_UNIQUE_PROCESS Process;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 256)]
        public string strAppName;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 64)]
        public string strServiceShortName;
        public int ApplicationType;
        public uint AppStatus;
        public uint TSSessionId;
        [MarshalAs(UnmanagedType.Bool)]
        public bool bRestartable;
    }

    [DllImport("rstrtmgr.dll", CharSet = CharSet.Unicode)]
    private static extern int RmStartSession(out uint pSessionHandle, int dwSessionFlags, string strSessionKey);

    [DllImport("rstrtmgr.dll", CharSet = CharSet.Unicode)]
    private static extern int RmRegisterResources(uint dwSessionHandle, uint nFiles, string[] rgsFiles, uint nApplications, IntPtr rgApplications, uint nServices, IntPtr rgsServiceNames);

    [DllImport("rstrtmgr.dll", CharSet = CharSet.Unicode)]
    private static extern int RmGetList(uint dwSessionHandle, out uint pnProcInfoNeeded, ref uint pnProcInfo, [In, Out] RM_PROCESS_INFO[] rgAffectedApps, ref uint lpdwRebootReasons);

    [DllImport("rstrtmgr.dll")]
    private static extern int RmEndSession(uint dwSessionHandle);

    public static List<int> GetLockingProcessIds(string[] paths) {
        List<int> pids = new List<int>();
        uint handle;
        string key = Guid.NewGuid().ToString();
        
        int res = RmStartSession(out handle, 0, key);
        if (res != 0) return pids;

        try {
            res = RmRegisterResources(handle, (uint)paths.Length, paths, 0, IntPtr.Zero, 0, IntPtr.Zero);
            if (res != 0) return pids;

            uint pnProcInfoNeeded = 0;
            uint pnProcInfo = 0;
            uint lpdwRebootReasons = 0;

            res = RmGetList(handle, out pnProcInfoNeeded, ref pnProcInfo, null, ref lpdwRebootReasons);
            if (res == 234) { // ERROR_MORE_DATA
                RM_PROCESS_INFO[] processInfo = new RM_PROCESS_INFO[pnProcInfoNeeded];
                pnProcInfo = pnProcInfoNeeded;
                res = RmGetList(handle, out pnProcInfoNeeded, ref pnProcInfo, processInfo, ref lpdwRebootReasons);
                if (res == 0) {
                    for (int i = 0; i < pnProcInfo; i++) {
                        pids.Add(processInfo[i].Process.dwProcessId);
                    }
                }
            }
        } finally {
            RmEndSession(handle);
        }
        return pids;
    }
}
'@

try {
    Add-Type -TypeDefinition $csharpCode -ErrorAction Stop
} catch {
    [System.Windows.Forms.MessageBox]::Show("Failed to load native LockDetector API.", "iMA Menu - Fatal Error", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Error)
    [Environment]::Exit(1)
}

# 5. Gather Paths to Scan
$pathsToRegister = [System.Collections.Generic.List[string]]::new()
$pathsToRegister.Add($Path)

if (Test-Path -Path $Path -PathType Container) {
    # Scan files in directory up to 500 to keep it highly responsive and within limits
    $files = Get-ChildItem -Path $Path -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First 500 | ForEach-Object { $_.FullName }
    foreach ($file in $files) {
        $pathsToRegister.Add($file)
    }
}

# 6. Query Locking Processes
$lockingPids = [LockDetector]::GetLockingProcessIds($pathsToRegister.ToArray())

if ($lockingPids.Count -eq 0) {
    Show-DonePopup
    [Environment]::Exit(0)
}

# 7. Retrieve Process Details & Filter
$processesToClose = @()
$hasExplorer = $false

foreach ($pidFound in $lockingPids) {
    if ($pidFound -eq $PID) { continue }
    if ($pidFound -le 4) { continue } # System, Idle
    
    try {
        $proc = Get-Process -Id $pidFound -ErrorAction SilentlyContinue
        if ($proc) {
            $name = $proc.ProcessName
            
            # Skip core system processes
            if ($name -in @("System", "Idle", "svchost", "csrss", "lsass", "wininit", "services", "smss", "dwm")) {
                continue
            }
            
            if ($name -eq "explorer") {
                $hasExplorer = $true
                continue
            }
            
            # Determine if it's a prominent user app (important)
            $isImportant = $false
            if ($proc.MainWindowHandle -ne [IntPtr]::Zero -and -not [string]::IsNullOrEmpty($proc.MainWindowTitle)) {
                $isImportant = $true
            } else {
                $bigPrograms = @("chrome", "msedge", "firefox", "opera", "brave", "devenv", "code", "excel", "winword", "powerpnt", "outlook", "photoshop", "illustrator", "premiere", "discord", "steam", "spotify", "teams", "slack", "vlc")
                if ($name.ToLower() -in $bigPrograms) {
                    $isImportant = $true
                }
            }
            
            $processesToClose += [PSCustomObject]@{
                Id = $pidFound
                Name = $name
                IsImportant = $isImportant
                Object = $proc
            }
        }
    } catch {
        # Process might have closed already or access denied
    }
}

# 8. Check Importance and Warn User if Required
if ($processesToClose.Count -eq 0) {
    if ($hasExplorer) {
        [System.Windows.Forms.MessageBox]::Show("The item is currently held open by Windows Explorer. Please close any File Explorer windows referencing this path and try again.", "iMA Menu - Explorer Locked", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Information)
    } else {
        Show-DonePopup
    }
    [Environment]::Exit(0)
}

$hasImportant = $false
foreach ($p in $processesToClose) {
    if ($p.IsImportant) {
        $hasImportant = $true
        break
    }
}

# Give warning first if an important process needs to be closed
if ($hasImportant) {
    $msg = "The following programs are locking the file/folder and must be terminated to unlock it:`n`n"
    foreach ($p in $processesToClose) {
        $tag = if ($p.IsImportant) { " (Important Application)" } else { "" }
        $msg += " - $($p.Name) [PID: $($p.Id)]$tag`n"
    }
    if ($hasExplorer) {
        $msg += "`n - Windows Explorer is also holding this file. Close its window manually.`n"
    }
    $msg += "`nWARNING: Terminating these applications might cause loss of unsaved changes.`n`nAre you sure you want to end these processes?"
    
    $decision = [System.Windows.Forms.MessageBox]::Show($msg, "iMA Menu - Confirm Process Termination", [System.Windows.Forms.MessageBoxButtons]::YesNo, [System.Windows.Forms.MessageBoxIcon]::Warning)
    if ($decision -ne [System.Windows.Forms.DialogResult]::Yes) {
        [Environment]::Exit(0)
    }
}

# 9. Terminate Processes
$hasErrors = $false
foreach ($p in $processesToClose) {
    try {
        Stop-Process -Id $p.Id -Force -ErrorAction Stop
    } catch {
        $hasErrors = $true
    }
}

if ($hasErrors) {
    [System.Windows.Forms.MessageBox]::Show("Some locking processes could not be closed. Try running again or closing them manually.", "iMA Menu - Incomplete", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Warning)
} else {
    Show-DonePopup
}