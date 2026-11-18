# Fetches all four Liner Notes pages for the iPod in one go: artist bios,
# album notes, track notes and credits. A page switched off on the iPod
# (Settings > Appearance > Viewers > Liner Notes) is skipped by its script.
# Each script's output is also saved to a log beside this file.

Set-Location $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8   # names with accents and Japanese show correctly
$env:PYTHONUNBUFFERED = "1"   # show progress as it happens, not when each script ends

# the iPod drive and music folder, from iPod Liner Notes settings.txt
$conf = @{}
python -c "import artist_bios; artist_bios.batch_settings()" | ForEach-Object {
    $k, $v = $_ -split "=", 2
    $conf[$k] = $v
}
if (-not $conf["IPOD"] -or -not (Test-Path $conf["MUSIC"])) {
    Write-Host "Can't find the iPod's music folder. Is the iPod plugged in?"
    exit 1
}
$ipod = $conf["IPOD"] + "\"
$music = $conf["MUSIC"]

# A read-only disk check first. Writing to a disk that already has errors can
# spread them, so stop and say how to repair it.
Write-Host "Checking the iPod's disk, read only (about a minute)..."
chkdsk $conf["IPOD"] | Out-Null
if ($LASTEXITCODE -ge 3) {
    Write-Host "The disk check found errors on the iPod, or couldn't run. Nothing has been written to it."
    Write-Host "To repair it: close the Claude app and any Explorer windows on the iPod,"
    Write-Host "open PowerShell as administrator and run:  chkdsk $($conf['IPOD']) /f"
    Write-Host "Then run this again."
    exit 1
}
Write-Host "Disk OK."

Write-Host "== 1 of 4: artist bios"
python artist_bios.py $music --ipod $ipod --retry-not-found 2>&1 | Tee-Object "bios log.txt"
Write-Host "== 2 of 4: album notes"
python liner_notes.py $music --ipod $ipod --retry-not-found 2>&1 | Tee-Object "notes log.txt"
Write-Host "== 3 of 4: track notes"
python track_notes.py $music --ipod $ipod 2>&1 | Tee-Object "track notes log.txt"
Write-Host "== 4 of 4: credits"
python credits.py $music --ipod $ipod 2>&1 | Tee-Object "credits log.txt"
Write-Host "Done. Eject the iPod."
