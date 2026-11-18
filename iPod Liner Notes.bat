@echo off
chcp 65001 >nul
title Update iPod (artist photos, bios, liner notes, database, art cache)

rem Run from the folder this file is in, so it finds the .py files
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"

for %%F in (art_fetch.py artist_fallback.py artist_bios.py liner_notes.py translate.py) do (
    if not exist "%%F" (
        echo Can't find %%F.
        echo Put this file in the same folder as the five .py files it runs.
        echo.
        pause
        exit /b 1
    )
)

rem The drive, music folder and which steps run come from the settings file
if not exist "iPod Liner Notes settings.txt" (
    echo Can't find iPod Liner Notes settings.txt.
    echo Put it in the same folder as this file.
    echo.
    pause
    exit /b 1
)
set "IPOD="
for /f "usebackq delims=" %%L in (`python -c "import artist_bios; artist_bios.batch_settings()"`) do set "%%L"
if not defined IPOD (
    echo Couldn't read iPod Liner Notes settings.txt - see the message above.
    echo.
    pause
    exit /b 1
)
set "TOOLS=%IPOD%\.rockbox\tools"

if not exist "%MUSIC%\" (
    echo Can't find %MUSIC%
    echo Is the iPod plugged in and showing in File Explorer?
    echo If it's on a different drive or folder, open
    echo iPod Liner Notes settings.txt and change ipod drive or music folder.
    echo.
    pause
    exit /b 1
)

rem A read-only disk check first. Writing to a disk that already has errors
rem can spread them, so stop and say how to repair it.
echo Checking the iPod's disk, read only (about a minute)...
chkdsk %IPOD% >nul 2>&1
if errorlevel 3 (
    echo.
    echo The disk check found errors on the iPod, or couldn't run.
    echo Nothing has been written to it.
    echo To repair it: close the Claude app and any Explorer windows on the
    echo iPod, open PowerShell as administrator and run:  chkdsk %IPOD% /f
    echo Then run this file again.
    echo.
    pause
    exit /b 1
)
echo Disk OK.
echo.

echo ============================================================
echo  Step 1 of 6: fetching artist photos online
echo ============================================================
echo Artists that already have a real photo are skipped. Artists showing an
echo album cover are searched for again, and keep the cover if none is found.
echo Artists with no photo found are skipped automatically.
echo Press Ctrl+C at any time to stop.
echo.

python art_fetch.py artist "%MUSIC%" --retry-not-found

echo.
echo ============================================================
echo  Step 2 of 6: using an album cover where no photo was found
echo ============================================================
python artist_fallback.py "%MUSIC%"

echo.
echo ============================================================
echo  Step 3 of 6: fetching artist bios
echo ============================================================
if /i "%BIOS%"=="no" (
    echo Skipped: bios is set to no in the settings file.
    set "BIORESULT=skipped - bios = no"
    goto :bios_done
)
if /i "%BIOS%"=="yes" goto :bios_run
findstr /m /c:"Artwork/Bios" "%IPOD%\.rockbox\rockbox.ipod" >nul 2>&1 && goto :bios_run
findstr /m /c:"No bio for this artist" "%IPOD%\.rockbox\langs\english.lng" >nul 2>&1 && goto :bios_run
echo Skipped: the PodBox on this iPod has no Artist Bio screen.
echo To write bios anyway, set bios = yes in the settings file.
set "BIORESULT=skipped - no Artist Bio screen on this iPod"
goto :bios_done

:bios_run
echo Artists that already have a bio are skipped.
echo.
python artist_bios.py "%MUSIC%" --ipod %IPOD%\
if errorlevel 1 (set "BIORESULT=FAILED - see messages above") else (set "BIORESULT=done")

:bios_done

echo.
echo ============================================================
echo  Step 4 of 6: fetching liner notes
echo ============================================================
if /i "%NOTES%"=="no" (
    echo Skipped: liner notes is set to no in the settings file.
    set "NOTESRESULT=skipped - liner notes = no"
    goto :notes_done
)
if /i "%NOTES%"=="yes" goto :notes_run
findstr /m /c:"Artwork/Notes" "%IPOD%\.rockbox\rockbox.ipod" >nul 2>&1 && goto :notes_run
findstr /m /c:"No liner notes for this album" "%IPOD%\.rockbox\langs\english.lng" >nul 2>&1 && goto :notes_run
echo Skipped: the PodBox on this iPod has no Liner Notes screen.
echo To write liner notes anyway, set liner notes = yes in the settings file.
set "NOTESRESULT=skipped - no Liner Notes screen on this iPod"
goto :notes_done

:notes_run
echo Albums that already have notes are skipped.
echo.
python liner_notes.py "%MUSIC%" --ipod %IPOD%\
if errorlevel 1 (set "NOTESRESULT=FAILED - see messages above") else (set "NOTESRESULT=done")

:notes_done

echo.
echo ============================================================
echo  Step 5 of 6: updating the music database
echo ============================================================
"%TOOLS%\database_pb.exe" %IPOD%\
if errorlevel 1 (set "DBRESULT=FAILED - see messages above") else (set "DBRESULT=done")

echo.
echo ============================================================
echo  Step 6 of 6: updating the art cache
echo ============================================================
"%TOOLS%\artcache_pb.exe" %IPOD%\
if errorlevel 1 (set "ARTRESULT=FAILED - see messages above") else (set "ARTRESULT=done")

echo.
echo ------------------------------------------------------------
echo  Finished.
echo  Artist bios       : %BIORESULT%
echo  Liner notes       : %NOTESRESULT%
echo  Database update   : %DBRESULT%
echo  Art cache update  : %ARTRESULT%
echo.
echo  Lists saved next to this file:
echo    "Artists using album cover.txt"
echo    "Artists without photos.txt"
echo    "Artists without bios.txt"
echo    "Albums without notes.txt"
echo.
echo  Now eject the iPod. It restarts itself to load the changes.
echo  If a step failed or was skipped, run it on the iPod instead:
echo  Settings ^> General Settings ^> System ^> Library Maintenance
echo ------------------------------------------------------------
echo.
pause
