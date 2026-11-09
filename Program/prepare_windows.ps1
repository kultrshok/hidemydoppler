<#
  Scrubgnome - Prepare System (Windows)
  Installs everything Scrubgnome needs on a bare Windows 10/11 box:
    Python 3 (python.org installer, all users, on PATH), numpy + scipy, ffmpeg.
  No winget or Python required. Works in Windows PowerShell 5.1+.

  Normally started by double-clicking "Prepare System.cmd".
    -AutoRun          start preparing immediately (used after the UAC relaunch)
    -NoGui            console-only mode
    -Worker -LogFile  internal: does the work in a background process while the
                      GUI tails LogFile and stays responsive
#>
param([switch]$AutoRun, [switch]$NoGui, [switch]$Worker, [string]$LogFile)

# 'Continue' on purpose: in PS 5.1, native stderr (pip warnings) under 'Stop' becomes a
# terminating error. Cmdlets that must fail hard get -ErrorAction Stop explicitly.
$ErrorActionPreference = 'Continue'
$ProgressPreference    = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$Here       = Split-Path -Parent $MyInvocation.MyCommand.Path
$FallbackPy = '3.12.10'
$FfmpegZip  = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'
$FfmpegDir  = Join-Path $env:ProgramFiles 'ffmpeg'
$Tmp        = Join-Path $env:TEMP 'hmd_prepare'
$Steps      = 4

function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    (New-Object Security.Principal.WindowsPrincipal $id).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
}

# ---------- output: log lines + status records ----------
function Emit([string]$line) {
    if ($LogFile) { [IO.File]::AppendAllText($LogFile, $line + "`r`n", [Text.Encoding]::UTF8) }
    elseif (-not $line.StartsWith('##')) { Write-Host $line }
}
function Log([string]$msg) { Emit $msg }
# pct: 0-100, or -1 for "busy, unknown duration"
function Status([int]$step, [string]$text, [int]$pct = -1) {
    Emit "##S|$step|$pct|$text"
    if (-not $LogFile -and $pct -lt 0) { Write-Host "-- [$step/$Steps] $text" -ForegroundColor Cyan }
}

function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                [Environment]::GetEnvironmentVariable('Path', 'User')
}

function Get-File([string]$url, [string]$dest, [int]$step, [string]$label) {
    # Streamed download with progress reported to the status bar.
    $req = [Net.HttpWebRequest]::Create($url)
    $req.UserAgent = 'Scrubgnome-prepare'
    $resp = $req.GetResponse()
    $total = $resp.ContentLength
    $in = $resp.GetResponseStream()
    $out = [IO.File]::Create($dest)
    try {
        $buf = New-Object byte[] 262144; $done = 0; $last = [DateTime]::MinValue
        while (($n = $in.Read($buf, 0, $buf.Length)) -gt 0) {
            $out.Write($buf, 0, $n); $done += $n
            if (([DateTime]::Now - $last).TotalMilliseconds -gt 400) {
                $mb = '{0:N1}' -f ($done / 1MB)
                if ($total -gt 0) {
                    $p = [int](100 * $done / $total)
                    Status $step ("$label  $mb / {0:N1} MB" -f ($total / 1MB)) $p
                } else { Status $step "$label  $mb MB" -1 }
                $last = [DateTime]::Now
            }
        }
    } finally { $out.Close(); $in.Close(); $resp.Close() }
}

function Wait-Proc($proc, [int]$step, [string]$label) {
    $t0 = Get-Date
    while (-not $proc.HasExited) {
        Status $step ("$label  ({0:N0}s)" -f ((Get-Date) - $t0).TotalSeconds) -1
        Start-Sleep -Milliseconds 1000
    }
    $proc.ExitCode
}

# ---------- Python ----------
function Get-PythonCmd {
    Refresh-Path
    foreach ($c in @(@('py', '-3'), @('python'), @('python3'))) {
        $cmd = Get-Command $c[0] -ErrorAction SilentlyContinue
        if (-not $cmd) { continue }
        if ($cmd.Source -like '*\WindowsApps\*') { continue }   # Microsoft Store stub
        try {
            $extra = @($c | Select-Object -Skip 1)
            $v = & $cmd.Source @extra -c "import sys;print('%d.%d'%sys.version_info[:2])" 2>$null
            if ($v -and [version]$v -ge [version]'3.9') { return @($cmd.Source) + $extra }
        } catch {}
    }
    return $null
}

function Install-Python {
    $arch = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { 'arm64' } else { 'amd64' }
    $ver = $null
    try {
        Status 1 'Looking up the latest Python 3 release...'
        $page = (Invoke-WebRequest 'https://www.python.org/downloads/windows/' -UseBasicParsing -ErrorAction Stop).Content
        $m = [regex]::Match($page, "python/(3\.\d+\.\d+)/python-\1-$arch\.exe")
        if ($m.Success) { $ver = $m.Groups[1].Value }
    } catch { Log "  (lookup failed: $($_.Exception.Message))" }
    foreach ($v in @($ver, $FallbackPy) | Where-Object { $_ } | Select-Object -Unique) {
        $url = "https://www.python.org/ftp/python/$v/python-$v-$arch.exe"
        $exe = Join-Path $Tmp "python-$v-$arch.exe"
        try {
            Log "  Downloading Python $v"
            Get-File $url $exe 1 "Downloading Python $v"
            Log '  Installing (silent, all users, adds to PATH)...'
            $p = Start-Process $exe -PassThru -ErrorAction Stop -ArgumentList @(
                '/quiet', 'InstallAllUsers=1', 'PrependPath=1', 'Include_launcher=1',
                'Include_pip=1', 'Include_test=0')
            $code = Wait-Proc $p 1 "Installing Python $v (usually 1-3 min)"
            if ($code -eq 0) { return $true }
            Log "  Installer exit code $code"
        } catch { Log "  Failed: $($_.Exception.Message)" }
    }
    return $false
}

# ---------- ffmpeg ----------
function Test-Ffmpeg {
    Refresh-Path
    [bool](Get-Command ffmpeg -ErrorAction SilentlyContinue) -and
    [bool](Get-Command ffprobe -ErrorAction SilentlyContinue)
}

function Install-Ffmpeg {
    $zip = Join-Path $Tmp 'ffmpeg.zip'
    $out = Join-Path $Tmp 'ffmpeg'
    Log '  Downloading ffmpeg (gyan.dev release essentials)'
    Get-File $FfmpegZip $zip 3 'Downloading ffmpeg'
    Status 3 'Extracting ffmpeg...'
    if (Test-Path $out) { Remove-Item $out -Recurse -Force }
    Expand-Archive $zip -DestinationPath $out -Force -ErrorAction Stop
    $bin = Get-ChildItem $out -Recurse -Filter ffmpeg.exe | Select-Object -First 1
    if (-not $bin) { throw 'ffmpeg.exe not found in archive' }
    $dest = Join-Path $FfmpegDir 'bin'
    New-Item -ItemType Directory -Force -Path $dest -ErrorAction Stop | Out-Null
    Copy-Item (Join-Path $bin.DirectoryName '*') $dest -Force -ErrorAction Stop
    $mp = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    if (($mp -split ';') -notcontains $dest) {
        [Environment]::SetEnvironmentVariable('Path', ($mp.TrimEnd(';') + ';' + $dest), 'Machine')
        Log "  Added $dest to the system PATH."
    }
    return (Test-Ffmpeg)
}

# ---------- main sequence ----------
function Invoke-Prepare {
    New-Item -ItemType Directory -Force -Path $Tmp | Out-Null
    $ok = $true
    Log '== Scrubgnome: Prepare System =='
    Log ''
    Log '[1/4] Python 3.9+'
    Status 1 'Checking for Python...'
    $py = Get-PythonCmd
    if ($py) { Log "  Found: $($py -join ' ')" }
    else {
        if (Install-Python) { $py = Get-PythonCmd }
        if ($py) { Log "  Installed: $($py -join ' ')" }
        else { Log '  !! Python install failed.'; return @{ ok = $false; py = $null } }
    }
    $pyExe = $py[0]; $pyArgs = @($py | Select-Object -Skip 1)

    Log ''
    Log '[2/4] numpy + scipy'
    Status 2 'Installing numpy + scipy with pip (can take a minute)...'
    & $pyExe @pyArgs -m pip install --upgrade --disable-pip-version-check --no-input numpy scipy 2>&1 |
        ForEach-Object {
            $l = "$_"
            if ($l -match '^(Collecting|Downloading|Installing)') { Status 2 ("pip: " + $l.Trim()) -1 }
            if ($l -match 'Successfully|already satisfied|ERROR') { Log "  $l" }
        }
    & $pyExe @pyArgs -c "import numpy, scipy" 2>$null
    if ($LASTEXITCODE -eq 0) { Log '  OK' } else { Log '  !! numpy/scipy not importable.'; $ok = $false }

    Log ''
    Log '[3/4] ffmpeg + ffprobe'
    Status 3 'Checking for ffmpeg...'
    if (Test-Ffmpeg) { Log "  Found: $((Get-Command ffmpeg).Source)" }
    else {
        try { if (Install-Ffmpeg) { Log '  Installed.' } else { Log '  !! ffmpeg still not found.'; $ok = $false } }
        catch { Log "  !! ffmpeg install failed: $($_.Exception.Message)"; $ok = $false }
    }

    Log ''
    Log '[4/4] Final check (setup_check.py)'
    Status 4 'Running final check...'
    $sc = Join-Path $Here 'setup_check.py'
    if (Test-Path $sc) {
        & $pyExe @pyArgs $sc --check 2>&1 | ForEach-Object { Log "  $_" }
        if ($LASTEXITCODE -ne 0) { $ok = $false }
    } else { Log '  (setup_check.py not found next to this script; skipped)' }

    Remove-Item $Tmp -Recurse -Force -ErrorAction SilentlyContinue
    Log ''
    Log $(if ($ok) { 'All set. Click "Launch Scrubgnome".' } else { 'Finished with problems - see above.' })
    return @{ ok = $ok; py = $py }
}

# ---------- worker mode (background process for the GUI) ----------
if ($Worker) {
    try { $r = Invoke-Prepare }
    catch { Log "!! $($_.Exception.Message)"; $r = @{ ok = $false; py = $null } }
    $pyStr = if ($r.py) { $r.py -join '|' } else { '' }
    Emit "##DONE|$([int][bool]$r.ok)|$pyStr"
    exit ([int](-not $r.ok))
}

function Restart-Elevated {
    $relArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"", '-AutoRun')
    if ($NoGui) { $relArgs += '-NoGui' }
    Start-Process powershell.exe -Verb RunAs -ArgumentList $relArgs
}

# ---------- console mode ----------
if ($NoGui) {
    if (-not (Test-Admin)) { Restart-Elevated; exit }
    $r = Invoke-Prepare
    Read-Host 'Press Enter to close'
    exit ([int](-not $r.ok))
}

# ---------- GUI ----------
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()
$bg = [Drawing.Color]::FromArgb(15, 17, 21); $panelC = [Drawing.Color]::FromArgb(23, 26, 33)
$fg = [Drawing.Color]::FromArgb(216, 221, 230); $acc = [Drawing.Color]::FromArgb(95, 179, 255)
$mute = [Drawing.Color]::FromArgb(133, 144, 162); $ink = [Drawing.Color]::FromArgb(8, 19, 32)
$okC = [Drawing.Color]::FromArgb(76, 195, 138); $badC = [Drawing.Color]::FromArgb(239, 107, 107)

$f = New-Object Windows.Forms.Form
$f.Text = 'Scrubgnome'; $f.ClientSize = New-Object Drawing.Size(680, 540)
$f.StartPosition = 'CenterScreen'; $f.BackColor = $bg; $f.ForeColor = $fg
$f.Font = New-Object Drawing.Font('Segoe UI', 10); $f.FormBorderStyle = 'FixedSingle'; $f.MaximizeBox = $false

$title = New-Object Windows.Forms.Label
$title.Text = 'Scrubgnome'; $title.Font = New-Object Drawing.Font('Segoe UI Semibold', 16)
$title.AutoSize = $true; $title.Location = New-Object Drawing.Point(22, 16)
$sub = New-Object Windows.Forms.Label
$sub.Text = 'Checks for Python, numpy, scipy and ffmpeg, installs anything missing, then launches the app. Windows will ask for admin rights.'
$sub.ForeColor = $mute; $sub.AutoSize = $true; $sub.Location = New-Object Drawing.Point(24, 52)

function New-Btn($text, $x, $primary) {
    $b = New-Object Windows.Forms.Button
    $b.Text = $text; $b.Size = New-Object Drawing.Size(220, 44); $b.Location = New-Object Drawing.Point($x, 84)
    $b.FlatStyle = 'Flat'; $b.Font = New-Object Drawing.Font('Segoe UI Semibold', 11)
    if ($primary) { $b.BackColor = $acc; $b.ForeColor = $ink; $b.FlatAppearance.BorderColor = $acc }
    else { $b.BackColor = [Drawing.Color]::FromArgb(34, 40, 53); $b.ForeColor = $fg
           $b.FlatAppearance.BorderColor = [Drawing.Color]::FromArgb(50, 58, 74) }
    $b
}
$btn = New-Btn 'Check + launch' 24 $true
if (-not (Test-Admin)) { $btn.Text = 'Check + launch  (admin)' }
$launch = New-Btn 'Launch Scrubgnome' 256 $false; $launch.Enabled = $false

$box = New-Object Windows.Forms.TextBox
$box.Multiline = $true; $box.ReadOnly = $true; $box.ScrollBars = 'Vertical'
$box.Location = New-Object Drawing.Point(24, 142); $box.Size = New-Object Drawing.Size(632, 318)
$box.BackColor = [Drawing.Color]::FromArgb(11, 13, 17); $box.ForeColor = $fg; $box.BorderStyle = 'FixedSingle'
$box.Font = New-Object Drawing.Font('Consolas', 9.5)
$box.Text = 'Click "Prepare system" to begin.'

# --- status bar (custom panel so it stays dark) ---
$bar = New-Object Windows.Forms.Panel
$bar.Dock = 'Bottom'; $bar.Height = 64; $bar.BackColor = $panelC
$stepL = New-Object Windows.Forms.Label
$stepL.Text = 'Idle'; $stepL.AutoSize = $false; $stepL.Size = New-Object Drawing.Size(90, 20)
$stepL.Location = New-Object Drawing.Point(24, 10); $stepL.ForeColor = $acc
$stepL.Font = New-Object Drawing.Font('Segoe UI Semibold', 9.5)
$msgL = New-Object Windows.Forms.Label
$msgL.Text = 'Ready.'; $msgL.AutoSize = $false; $msgL.AutoEllipsis = $true
$msgL.Size = New-Object Drawing.Size(460, 20); $msgL.Location = New-Object Drawing.Point(114, 10)
$msgL.ForeColor = $fg; $msgL.Font = New-Object Drawing.Font('Segoe UI', 9.5)
$timeL = New-Object Windows.Forms.Label
$timeL.Text = ''; $timeL.AutoSize = $false; $timeL.TextAlign = 'TopRight'
$timeL.Size = New-Object Drawing.Size(80, 20); $timeL.Location = New-Object Drawing.Point(576, 10)
$timeL.ForeColor = $mute; $timeL.Font = New-Object Drawing.Font('Segoe UI', 9.5)
$pb = New-Object Windows.Forms.ProgressBar
$pb.Location = New-Object Drawing.Point(24, 36); $pb.Size = New-Object Drawing.Size(632, 14)
$pb.Minimum = 0; $pb.Maximum = 100; $pb.Style = 'Continuous'; $pb.MarqueeAnimationSpeed = 30
$bar.Controls.AddRange(@($stepL, $msgL, $timeL, $pb))

$script:pos = 0; $script:frag = ''; $script:t0 = $null; $script:proc = $null; $script:PyCmd = $null

function Set-Status([int]$step, [int]$pct, [string]$text) {
    $stepL.Text = "Step $step/$Steps"; $msgL.Text = $text
    if ($pct -lt 0) { if ($pb.Style -ne 'Marquee') { $pb.Style = 'Marquee' } }
    else {
        if ($pb.Style -ne 'Continuous') { $pb.Style = 'Continuous' }
        # overall progress: each step is a quarter, pct fills inside it
        $pb.Value = [Math]::Min(100, [int](25 * ($step - 1) + $pct / 4))
    }
}

function Start-Hmd {
    if (-not $script:PyCmd) { return $false }
    $exe = $script:PyCmd[0]; $a = @($script:PyCmd | Select-Object -Skip 1) + @('ui.py', '--launched-from-prep')
    Start-Process $exe -ArgumentList $a -WorkingDirectory $Here
    return $true
}

function Finish([bool]$ok, [string]$pyStr) {
    $timer.Stop()
    if ($pyStr) { $script:PyCmd = $pyStr -split '\|' }
    $pb.Style = 'Continuous'; $pb.Value = 100
    $stepL.ForeColor = if ($ok) { $okC } else { $badC }
    Remove-Item $script:logPath -Force -ErrorAction SilentlyContinue
    if ($ok -and $script:PyCmd) {
        # Success: launch the app and close this window (this is the whole point).
        $stepL.Text = 'Done'; $msgL.Text = 'Launching Scrubgnome...'
        [System.Windows.Forms.Application]::DoEvents()
        Start-Sleep -Milliseconds 600
        Start-Hmd | Out-Null
        $f.Close()
        return
    }
    $stepL.Text = 'Problems'
    $msgL.Text = 'Finished with problems - see the log. Fix, then Run again.'
    $btn.Enabled = $true; $btn.Text = 'Run again'
    $launch.Enabled = [bool]$script:PyCmd
    if ($script:PyCmd) {
        $launch.BackColor = $acc; $launch.ForeColor = $ink; $launch.FlatAppearance.BorderColor = $acc
        $msgL.Text = 'Finished with problems - you can Launch anyway, or Run again.'
    }
}

$timer = New-Object Windows.Forms.Timer
$timer.Interval = 400
$timer.Add_Tick({
    if ($script:t0) { $timeL.Text = '{0:mm\:ss}' -f ((Get-Date) - $script:t0) }
    if (-not (Test-Path $script:logPath)) { return }
    try {
        $fs = [IO.File]::Open($script:logPath, 'Open', 'Read', 'ReadWrite')
        $fs.Seek($script:pos, 'Begin') | Out-Null
        $sr = New-Object IO.StreamReader($fs, [Text.Encoding]::UTF8)
        $chunk = $sr.ReadToEnd(); $script:pos = $fs.Position; $sr.Close()
    } catch { return }
    if (-not $chunk) {
        if ($script:proc -and $script:proc.HasExited -and -not $script:doneSeen) {
            Finish $false ''; $box.AppendText("`r`n!! Worker exited unexpectedly (code $($script:proc.ExitCode)).`r`n")
        }
        return
    }
    $text = ($script:frag + $chunk).TrimStart([char]0xFEFF)
    $lines = $text -split "`r?`n"
    $script:frag = $lines[-1]
    if ($lines.Count -lt 2) { return }
    foreach ($l in $lines[0..($lines.Count - 2)]) {
        if ($l.StartsWith('##S|')) {
            $p = $l.Split('|', 4); Set-Status ([int]$p[1]) ([int]$p[2]) $p[3]
        } elseif ($l.StartsWith('##DONE|')) {
            $p = $l.Split('|', 3); $script:doneSeen = $true; Finish ($p[1] -eq '1') $p[2]
        } else { $box.AppendText($l + "`r`n") }
    }
})

$btn.Add_Click({
    if (-not (Test-Admin)) { Restart-Elevated; $f.Close(); return }
    $btn.Enabled = $false; $launch.Enabled = $false; $box.Clear()
    $stepL.ForeColor = $acc; Set-Status 1 -1 'Starting...'
    $script:logPath = Join-Path $env:TEMP ("hmd_prepare_{0}.log" -f [guid]::NewGuid().ToString('N'))
    New-Item -ItemType File -Path $script:logPath -Force | Out-Null
    $script:pos = 0; $script:frag = ''; $script:doneSeen = $false; $script:t0 = Get-Date
    $script:proc = Start-Process powershell.exe -WindowStyle Hidden -PassThru -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"",
        '-Worker', '-LogFile', "`"$($script:logPath)`"")
    $timer.Start()
})
$launch.Add_Click({ Start-Hmd | Out-Null; $f.Close() })
$f.Add_FormClosing({
    if ($script:proc -and -not $script:proc.HasExited) {
        $r = [Windows.Forms.MessageBox]::Show('Setup is still running. Stop it and close?',
                                               'Scrubgnome', 'YesNo', 'Warning')
        if ($r -ne 'Yes') { $_.Cancel = $true; return }
        try { $script:proc.Kill() } catch {}
    }
})
if ($AutoRun) { $f.Add_Shown({ $btn.PerformClick() }) }

$f.Controls.AddRange(@($title, $sub, $btn, $launch, $box, $bar))
[void]$f.ShowDialog()
