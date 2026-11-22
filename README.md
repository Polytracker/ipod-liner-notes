# iPod Liner Notes

Artist photos, artist bios, album and track notes, and album credits for an
iPod running PodBox.

This carries on from [ipod-artist-photos](https://github.com/Polytracker/ipod-artist-photos),
which only did artist photos and is no longer being developed. Everything it
did is included here, unchanged, alongside the new artist bios and liner notes.

> [!WARNING]
> **Still in development, not ready for public use yet.** This is an
> experimental tool I'm testing on my own iPod. Things may change or break
> between versions, and the Liner Notes viewer it writes for isn't available
> in any official PodBox release. If you just want artist photos, use
> [ipod-artist-photos](https://github.com/Polytracker/ipod-artist-photos)
> instead.

> **Please read first**
>
> - **Forked from PodBox.** `art_fetch.py` is a modified copy of the artwork
>   tool from [PodBox](https://github.com/anthonyfletcher/podbox)
>   ([`tools/art_fetch`](https://github.com/anthonyfletcher/podbox/tree/master/tools/art_fetch),
>   version 3.8). This is an unofficial fork and isn't affiliated with or
>   endorsed by the PodBox project. Please report problems with this tool
>   here, not to PodBox.
> - **Written with AI.** The changes to `art_fetch.py`, and all the other
>   scripts here (`artist_fallback.py`, `ids.py`, `artist_bios.py`,
>   `liner_notes.py`, `track_notes.py`, `credits.py`, `translate.py`,
>   `preview.py`, `link_dryrun.py`, `iPod Liner Notes.bat` and
>   `Run liner notes pages.ps1`), were written with the help of Claude, an AI
>   assistant made by Anthropic, at my direction.
>   I've used them on my own iPod Classic, but they haven't been tested more
>   widely. The text on the pages is never written by AI: it all comes from
>   Wikipedia, Last.fm, Discogs and MusicBrainz, credited on each page.
> - **The pages need a custom PodBox build.** The **Liner Notes** viewer that
>   shows them (its pages are **Bio**, **Album**, **Track** and **Credits**)
>   isn't in PodBox's official releases yet; the Artist Bio part has been
>   proposed to the PodBox developer. Until it is, seeing the pages on the
>   iPod means building PodBox from source with those changes added. On an
>   official PodBox build the bio and notes steps are skipped automatically,
>   and everything else (artist photos, database and art cache) works as
>   normal.
> - **Use at your own risk.** The tool writes picture files into your iPod's
>   music folders and updates its database. Keep a backup of your music.

A Windows tool that fills the **Artist Portraits** menu and the four pages of
the **Liner Notes** viewer on an iPod running [PodBox](https://github.com/anthonyfletcher/podbox), the Rockbox-based
firmware for the iPod Classic and iPod Video.

Between them, its scripts:

1. find a photo of every artist on your iPod, from Last.fm, Deezer,
   fanart.tv and TheAudioDB;
2. use an album cover for any artist with no photo anywhere, so nobody is
   left blank;
3. work out exactly which release each album folder is, so no page is ever
   about a different album with the same name;
4. write a biography and a banner photo for each artist, for the **Bio**
   page (hold Select on Now Playing);
5. write liner notes for each album, with the critics' scores, for the
   **Album** page;
6. write notes for songs that have their own write-up, for the **Track**
   page;
7. list who played on, produced, engineered and wrote each album, for the
   **Credits** page, and which of those people are on other albums you have
   (**Other Appearances**);
8. update the iPod's database and art cache, so the pictures are there as
   soon as you eject it, with nothing to do on the iPod itself.

---

## What you need

- A Windows PC.
- An iPod running PodBox that has been **switched on at least once** since
  PodBox was last installed or updated. (The database tools refuse to run
  until it has.)
- Music on the iPod arranged as `Music\Artist\Album\` folders, as PodBox and
  most sync tools do. Album folders can be named any way you like:
  `OK Computer`, `1997 - OK Computer` and `Radiohead - OK Computer` all work.
  A year in front isn't needed.

---

## Installing

You only need to do this once.

### 1. Install Python

1. Download Python 3 from [python.org/downloads](https://www.python.org/downloads/).
2. Run the installer. On its first screen, **tick "Add python.exe to PATH"**
   before clicking **Install Now**. If you miss this box, the tool can't find
   Python.

To check it worked, open **Command Prompt** (press the Windows key, type
`cmd`, press Enter) and type:

```
python --version
```

It should print something like `Python 3.12.4`.

### 2. Install the libraries the tool uses

In the same Command Prompt window, type:

```
pip install requests pillow mutagen opencv-python
```

Wait for it to finish, then close the window.

### 3. Download this tool

1. At the top of this page, click the green **Code** button, then
   **Download ZIP**.
2. Open your Downloads folder, right-click the ZIP and choose
   **Extract All**. Put it somewhere permanent, for example
   `Documents\iPod Liner Notes`.

You should now have these files in that folder:

| File | What it is |
|---|---|
| `iPod Liner Notes.bat` | The one you double-click: photos, bios, album notes, then the database and art cache. |
| `Run liner notes pages.ps1` | All four Liner Notes pages (bios, album notes, track notes, credits), with a log of each. |
| `art_fetch.py` | Finds artist photos online. |
| `artist_fallback.py` | Uses an album cover when no photo can be found. |
| `ids.py` | Works out which release each album folder is, for all the pages (see [Which album is it](#which-album-is-it)). |
| `artist_bios.py` | Writes each artist's bio and banner for the Bio page. |
| `liner_notes.py` | Writes each album's notes and cover banner for the Album page. |
| `track_notes.py` | Writes notes for songs with their own write-up, for the Track page. |
| `credits.py` | Writes each album's credits for the Credits page. |
| `translate.py` | Translates text for artists who don't work in English, when you add a DeepL key. |
| `preview.py`, `link_dryrun.py` | Checking tools for changing the scripts; you don't need them (see `DEVELOPING.md`). |
| `iPod Liner Notes settings.txt` | Settings for the pages (see [Settings](#settings)). |

Keep them together in the same folder.

### 4. Add your free Last.fm key (recommended)

Last.fm has the most artist photos, but it only answers the tool if you give
it a free API key:

1. Sign in to Last.fm (or create a free account), then go to
   [last.fm/api/account/create](https://www.last.fm/api/account/create). Any
   name and description will do; leave the callback box empty.
2. Copy the **API key** and **Shared secret** it shows you.
3. Optionally, get a free fanart.tv key too, from
   [fanart.tv/get-an-api-key](https://fanart.tv/get-an-api-key/). It adds
   more photos for well-known artists.
4. Open Command Prompt **in the tool's folder** (open the folder in File
   Explorer, click the address bar, type `cmd` and press Enter), then type:

   ```
   python art_fetch.py --install-credentials --prompt-credentials
   ```

   Paste each key when asked, and press Enter to skip any you don't have.

The keys are saved on your PC, in
`%APPDATA%\RockboxArtistArt\artist_art_credentials.json`, not in this folder,
so they aren't shared if you share the folder. Without any keys the tool
still works using Deezer and TheAudioDB, but finds fewer photos.

### 5. Tell it where your iPod is

The tool assumes your iPod shows up as drive **G:** with its music in
`G:\Music`. If yours is different:

1. Plug in the iPod and look in **File Explorer > This PC** to see its drive
   letter.
2. Open `iPod Liner Notes settings.txt` in Notepad.
3. Change the `ipod drive` line to match, for example `ipod drive = E:`. If
   the music isn't in a folder called `Music`, set `music folder` too.

4. Save and close.

---

## Using it

1. Plug in the iPod and wait for it to appear in File Explorer.
2. Double-click **iPod Liner Notes.bat**.
3. Let it run. The first time takes a while, roughly a few seconds per
   artist. You can press **Ctrl+C** to stop at any point; next time it carries
   on where it left off.
4. When it says it has finished, eject the iPod as normal. The pictures are
   in **Artist Portraits** when it restarts.

If Windows shows **"Windows protected your PC"** the first time, click
**More info**, then **Run anyway**. That appears for any downloaded `.bat`
file.

Before writing anything, both the `.bat` and `Run liner notes pages.ps1` run a
read-only disk check of the iPod (about a minute). If it finds errors they
stop with nothing written, and say how to repair the disk: writing to a
damaged disk spreads the damage.

### Track notes and credits

The `.bat` doesn't do the Track and Credits pages yet. For those (and the
bios and album notes again, which are quick when there's nothing new), open
PowerShell in the tool's folder (in File Explorer, click the address bar,
type `powershell` and press Enter) and run:

```
python ids.py
powershell -ExecutionPolicy Bypass -File ".\Run liner notes pages.ps1"
```

`ids.py` identifies your albums; the Track and Credits steps need it to have
run, and stop with **"Run ids.py first"** if it hasn't. Run it again after
adding music. The PowerShell script then fetches the four pages in turn,
showing progress as it goes and saving each step's output as
`bios log.txt`, `notes log.txt`, `track notes log.txt` and
`credits log.txt`. It doesn't touch the database or art cache, which these
pages don't need.

### What each run of the .bat does

| Step | What happens |
|---|---|
| 1. Fetch photos | Looks for a photo of each artist that doesn't have one yet, including artists showing an album cover in place of one. A cover is replaced only when a real photo is found. Artists with a real photo already are skipped. |
| 2. Album cover fallback | Any artist still without a photo gets the cover of their biggest album, squared, instead. |
| 3. Fetch bios | Writes a bio and banner for each artist that doesn't have one yet (see **Artist bios** below). Runs only if the PodBox on your iPod has the Liner Notes viewer. |
| 4. Fetch liner notes | Writes notes for each album that doesn't have them yet (see **Liner notes** below). Runs only if the PodBox on your iPod has the Liner Notes viewer. |
| 5. Update database | Runs PodBox's database tool on the iPod. |
| 6. Update art cache | Runs PodBox's art cache tool, so the new pictures show straight away. |

At the end it prints a summary, and saves these lists in the tool's folder:

- **Artists using album cover.txt**: artists showing an album cover because
  no photo was found.
- **Artists without photos.txt**: artists with no photo and no album art at
  all.
- **Artists without bios.txt**: artists no bio could be found for.
- **Albums without notes.txt**: albums whose page has only the facts line.

`ids.py` also saves **Albums not identified.txt** (each album it couldn't
pin down, the editions it tried and why each was turned down), and
`track_notes.py` saves **Tracks not used.txt** (songs with a Wikipedia
article that didn't get a page, and why).

### After each sync

Run it again whenever you've added music. Artists that are already done are
skipped, so repeat runs are quick. Each artist still on the album-cover list
is looked up again every time, so photos for them appear once Last.fm or
Deezer gets one.

### Running it when you install PodBox

If you install the custom Liner Notes builds of PodBox with their install
script (a PowerShell block you paste in, which unzips the build onto the
iPod), you rarely need to start the `.bat` yourself. After installing, the
script:

1. checks the iPod's disk, read only, and installs nothing if it finds
   errors;
2. unzips the build and checks the version on the iPod is the one expected;
3. checks the iPod's database, and rebuilds it if a file is missing or a
   save was left half done (the old one is kept as `database_broken`);
4. runs **iPod Liner Notes.bat**, but only when the database was just
   rebuilt, there's new music (an artist folder in `Music` is newer than the
   `Artwork\.liner-notes-last-run` marker it leaves on the iPod), or
   `refresh after podbox install = yes` is set in the settings file.
   Otherwise it leaves the photos, pages and database as they are, which
   saves the run's time and the online lookups.

It expects this tool in `Documents\Claude\iPod Liner Notes` and the iPod
on **G:**. It runs only the `.bat`, so the Track and Credits pages still need
the steps in **Track notes and credits** after adding music.

Running the `.bat` yourself always goes through every step (skipping what's
already done), and doesn't update that marker.

### Updating the iPod's database

Steps 5 and 6 use PodBox's own PC tools, which come with PodBox and are
already on your iPod, in `.rockbox\tools\` (`database_pb.exe` and
`artcache_pb.exe`). There is nothing extra to install, and you don't need to
run anything on the iPod.

If either step says **FAILED**, do it on the iPod instead: eject it, then go
to **Settings > General Settings > System > Library Maintenance** and choose
**Update Database**, then **Update Art Cache**.

### Adding a photo yourself

To use your own picture for an artist, save any square-ish JPEG as
`folder.jpg` in that artist's folder on the iPod, replacing the one there,
then run the tool again (or **Update Art Cache** on the iPod). The tool never
replaces a photo you've put there yourself.

PodBox also reads artist pictures from `Artwork\People\<Artist>.jpg` at the
root of the iPod, and a picture there takes priority over the artist
folder's `folder.jpg`. If an artist shows the wrong picture, check there
first.

### Settings

`iPod Liner Notes settings.txt`, beside the scripts, holds the tool's settings. Open it in Notepad, change a value after the `=` and
save; it takes effect on the next run.

| Setting | Default | What it does |
|---|---|---|
| `ipod drive` | `G:` | The iPod's drive letter |
| `music folder` | empty | The music folder, if it isn't `Music` on the iPod's drive |
| `bios` | `auto` | Artist bios: `auto` writes them only if the PodBox on the iPod has the Liner Notes viewer, `yes` always, `no` never |
| `liner notes` | `auto` | The same for the album notes |
| `recheck missing days` | `30` | Days before artists with no bio and albums with no notes are looked for again; `0` never. Ones that have them are left alone |
| `bio recheck days` | `365` | Days before an artist's bio is checked again; `0` never checks. Artists who have died and bands that have split are never checked again |
| `notes recheck days` | `365` | The same for an album's liner notes |
| `banners` | `yes` | Fetch the banner pictures. `no` writes the text only |
| `refresh after podbox install` | `no` | Whether the PodBox install script runs the `.bat` after every install. `no` runs it only when there is new music or the database was rebuilt (see **Running it when you install PodBox**) |
| `discogs token` | empty | Your Discogs personal token, an extra source for both |
| `deepl key` | empty | Your DeepL key, to translate bios and notes for artists who don't work in English (see **Translation**) |

### Which album is it

Every page depends on knowing exactly which release an album folder is, so a
page about another album with the same name never appears. `ids.py` works
this out once per album, from the strongest evidence first: MusicBrainz or
Discogs IDs already in your tags (from Picard, say), then the barcode, ISRCs,
store links, CD disc ID and catalogue number, and only last a search by
artist and title. Every candidate is checked against your files (the
artist, the track titles, the number of tracks and their lengths) and
dropped if they don't line up. A deluxe edition still matches a folder you
trimmed back to the original album, and the pages say which edition their
information is for.

The results are kept on the PC (in `%APPDATA%\RockboxArtistArt\ids`), so
later runs only look at new albums, albums whose tags have changed, and,
after 30 days, ones nothing was found for. It changes none of your files.
`python ids.py --only "Artist - Album"` does one album, `--refresh`
everything again.

### Artist bios

Step 3 writes two files per artist into `Artwork\Bios` at the root of the
iPod, which the **Bio** page reads:

- `<Artist>.txt`: the name, a line of genre, home town and dates (birth to
  death for a person, start to end for a band), then the biography.
- `<Artist>.jpg`: a 320 x 160 banner from the artist's photo, cropped so
  the faces stay in view.

The bio is the introduction of the artist's English Wikipedia article. Where
there is none it comes from Last.fm (with your Last.fm key) or Discogs, then,
for an artist who doesn't work in English, their own language's Wikipedia or
Last.fm, translated (see **Translation**), and failing those a line of facts.
The last line of each bio says where it came from and the date it was
retrieved. Before looking anything up it checks which
artist yours is: when several share the name (a singer called Dijon, and the
city), it picks the one whose albums match your album folders, using the
artist `ids.py` found on your albums when it has run. A very long
bio is swapped for a much shorter one from another source when there is one.

Photos come from TheAudioDB, Deezer, Discogs or Wikipedia. When none has
one, the artist's own `folder.jpg` from step 1 is used, unless it is an album
cover step 2 put there; failing that, the cover of one of their albums. An
artist whose banner is an album cover gets their `folder.jpg` instead as soon
as step 1 finds them a photo, with nothing downloaded again. What was downloaded is kept on
the PC (in `%APPDATA%\RockboxArtistArt\bios`), so a later run only looks up
new artists, plus any active artist whose bio is over a year old (change that
with `bio recheck days` in the settings file). Artists who have died and bands
that have split are left as they are. When a bio is checked again, it is only
replaced if it has really changed, not for a small edit, and the banner photo
stays as it was. If a source is down when a bio is due, the old one is kept.

To write your own bio or banner, edit or replace the file in
`Artwork\Bios`; the tool leaves a file you've changed alone. To look every
artist up again, run `python artist_bios.py "G:\Music" --refresh`, or for one
artist add `--only "Artist Name"`.

The Liner Notes viewer isn't in PodBox's official releases yet, so to see the
bios you need a PodBox build compiled from source with the Liner Notes viewer
added. The `.bat`
checks the iPod and skips this step when its PodBox doesn't have it.
To change that, set `bios` in the settings file: `yes` writes bios whatever
the firmware, `no` never does.

### Liner notes

Step 4 writes two files per album into `Artwork\Notes` at the root of the
iPod, named `<Album Artist> - <Album>`, which the **Album** page reads (hold
Select on Now Playing, or on an album in Music):

- `.txt`: the title, a facts line (artist, year, label, tracks, length), the
  album's notes, then the critics' scores, and where the text came from and
  the date it was retrieved.
- `.jpg`: the album's own cover (`cover.jpg`, `folder.jpg` or the art in the
  files), cropped to a 320 x 160 banner.

Each album is matched by the release `ids.py` found for it, when it has run;
otherwise first among the artist's albums on Wikidata, else on MusicBrainz by
the artist and title, so a song, a single or a video of the
same name can't take its place (a folder of three tracks or fewer is taken to
be a single). Its English Wikipedia article supplies the introduction, the
first paragraph about what critics made of it and the scores from its ratings
box. An album with no English article, by an artist who doesn't work in
English, gets its article in their language, translated. Otherwise the notes
come from Last.fm or Discogs; an album none of them covers still gets a page
with its facts line. The album and artist names come from the files' tags; an
album split into disc folders (`CD1`, `CD2`) is read as one, and a `Singles`
folder or one holding several albums is skipped.

The title on the page is the plain title, without "Deluxe Edition" and the
like. The year is when the album first came out, from Wikidata and
MusicBrainz, then your files' original-date tag, and only then their date tag,
which often holds a reissue's year.

As with bios, a file you've changed is left alone, and notes are checked again
once they're a year old (`notes recheck days` in the settings file) and only
rewritten if they've really changed. To look
an album up again, run
`python liner_notes.py "G:\Music" --only "Artist - Album" --refresh`. The
`liner notes` setting works like `bios`.

### Track notes

`track_notes.py` writes one file per song that has its own English Wikipedia
article, into `Artwork\Tracks`, named `<Album Artist> - <Track Title>.txt`:
the title, a facts line, the article's introduction (with a paragraph of its
background when the introduction is short) and where it came from. Most
songs have no article and get no page; the Track page is then left out for
them.

Songs are found from the album `ids.py` identified, not by searching for
their titles: a song counts only when Wikidata lists it on that album and
its title matches one of your tracks. The article must be a real write-up
and name your artist in its opening, so a cover version never gets the
original's article. Where Wikipedia has nothing, Last.fm's notes are used if
Last.fm puts the track on your album or by your artist; Last.fm text can be
written by fans, and the page says it's from Last.fm. Albums are looked at
again after 180 days. The first run over about 1,000 tracks takes 4 to 5
minutes.

### Credits

`credits.py` writes one file per album into `Artwork\Credits`, named
`<Album Artist> - <Album>.txt`, listing who made it in five groups:
**Musicians**, **Producers**, **Engineers**, **Songwriters** and
**Credited** (everyone else). Each group comes whole from one source, never
mixed: your files' own credit tags if they have any for that group,
otherwise whichever of MusicBrainz and Discogs covers more of your album.
Credits for tracks you don't have are left out, and credits for only some of
your tracks say which ("Drums [2, 5-7]", drawn small and grey on the iPod).
The page names the edition its credits are for.

Pressing Select on the Credits page lists **Other Appearances**: people
credited on this album who are also on other albums or tracks in your
library; choosing one lists those, and opens them. People are matched by
their MusicBrainz or Discogs ID, never by name alone, so two people with the
same name aren't mixed up. A band's own members aren't listed for the band's
other albums, as that would be all of them.

`credits.py` reuses the releases `ids.py` saved, so it makes few requests.
Without a `discogs token` in the settings file, `ids.py` doesn't look on
Discogs, so the credits come from your tags and MusicBrainz only.

### Turning pages off on the iPod

Each page can be switched off on the iPod, under **Settings > Appearance >
Viewers > Liner Notes**, as can the whole viewer. A script whose page is off
fetches nothing. Files already on the iPod are never deleted, whether a page
is on or off; delete them yourself if you want them gone.

### Translation

Most of what is written about Japanese, Korean or Chinese releases, and some
European ones, isn't in English. With a free DeepL key in the settings file
(`deepl key = ...`, from [deepl.com/pro-api](https://www.deepl.com/pro-api),
500,000 characters a month), bios and notes for those artists come from their
own language's Wikipedia or Last.fm, translated into English. The page's last
line then says it was machine-translated.

Translation is used only for artists who work in another language (Wikidata
records their language or country), and only text that really isn't English
is sent. Every translation is kept on the PC, so a later run never pays for
the same text twice. A whole library uses a small part of the free allowance.

---

## Troubleshooting

| Problem | What to do |
|---|---|
| `'python' is not recognized` | Python wasn't added to PATH. Run the Python installer again, choose **Modify**, and tick **Add Python to environment variables**. |
| `No module named requests` (or `PIL`, `mutagen` or `cv2`) | Step 2 of installing didn't finish. Run `pip install requests pillow mutagen opencv-python` again. |
| An artist has the wrong bio | Edit that artist's `.txt` in `Artwork\Bios` on the iPod; the tool leaves a file you've changed alone. Deleting it only brings the same bio back next run. |
| `Can't find G:\Music` | The iPod isn't plugged in, or is on a different drive. See **Tell it where your iPod is**. |
| An artist gets the wrong person's photo | Delete that artist's `folder.jpg` on the iPod and add one yourself (see **Adding a photo yourself**). |
| An artist is never found | Check the artist's name is spelled correctly in your music tags. The tool searches by the name in your tags. |
| Database or art cache step says FAILED | Switch the iPod on once with PodBox, then try again, or run the update on the iPod (see **Updating the iPod's database**). |
| Track notes or credits say **Run ids.py first** | Run `python ids.py` in the tool's folder, then run them again. |
| `running scripts is disabled on this system` | Start the PowerShell script with `powershell -ExecutionPolicy Bypass -File ".\Run liner notes pages.ps1"`, as shown in **Track notes and credits**. |
| The disk check found errors | Close any Explorer windows on the iPod, open PowerShell as administrator and run `chkdsk G: /f` (with your iPod's drive letter), then run the tool again. |
| An album's pages are missing or about the wrong edition | If it's in **Albums not identified.txt**, that says what was tried and why it was turned down. Tagging it in MusicBrainz Picard puts its IDs in the tags, and `ids.py` uses those first. |

---

## Where this comes from

`art_fetch.py` is a modified copy of the artwork tool that comes with PodBox,
[`tools/art_fetch`](https://github.com/anthonyfletcher/podbox/tree/master/tools/art_fetch)
(version 3.8), which downloads artist and album art for a Rockbox-style music
library.

### Why it was forked

The original is a general artwork fetcher. Run against a real iPod library to
fill Artist Portraits, it left many artists with no picture:

- Last.fm often refused its requests or returned image links that no longer
  worked.
- Smaller artists missing from Last.fm, fanart.tv and TheAudioDB got nothing.
- An artist with no photo anywhere was left blank, even when their album
  covers were on the iPod.
- Getting new pictures to show on the iPod took several separate steps,
  some of them on the iPod itself.

### Changes from the original

**`art_fetch.py`**

- **More reliable Last.fm.** Last.fm pages are requested the way a web
  browser asks for them, and when Last.fm refuses (HTTP 403 or 406) two other
  ways are tried, with a pause between, before giving up.
- **Every lookup retries when a site is busy.** A "too many requests" (429) or
  "temporarily unavailable" (5xx) answer from any source is waited out and
  tried again, instead of losing that source for the artist.
- **Broken image links retried** at the other sizes Last.fm offers.
- **Errors are shown** rather than skipped silently.
- **Only the artist's own photos.** Pictures of similar artists are no longer
  picked up from Last.fm pages.
- **New source: Deezer.** Free, needs no key, and covers many smaller
  artists. Several artists can share a name, so a Deezer photo is only used
  when one of that artist's Deezer albums matches one of your album folders
  (ignoring endings such as "- EP" and "(Deluxe)").

**`artist_fallback.py`** (new): for an artist with no photo, squares the cover
of their biggest album (embedded in the tracks, or the album's `folder.jpg` or
`cover.jpg`) into the artist's `folder.jpg`, as a baseline JPEG the iPod can
read. art_fetch replaces these stand-ins only when it finds a real photo.
With `--remove` it takes them away, leaving any picture you've added
yourself.

**`artist_bios.py`** (new): bios and banner photos for PodBox's Bio
page. See **Artist bios** above.

**`ids.py`** (new): which release each album folder is, for all the pages.
See **Which album is it** above.

**`liner_notes.py`** (new): liner notes and cover banners for PodBox's Album
page. See **Liner notes** above.

**`track_notes.py`** and **`credits.py`** (new): the Track and Credits pages.
See **Track notes** and **Credits** above.

**`translate.py`** (new): DeepL translation for the pages. See
**Translation** above.

**`preview.py`** and **`link_dryrun.py`** (new): checking tools for changing
the scripts: pictures of Credits pages drawn with the iPod's own fonts, and a
report of who would link to whom in Other Appearances. Neither writes to the
iPod.

**`iPod Liner Notes.bat`** (new): photos, fallback, bios and album notes in
order, then updates the database and art cache with PodBox's tools.

**`Run liner notes pages.ps1`** (new): bios, album notes, track notes and
credits, with a log of each.

---

## Checking changes

`python -m pytest -q` (after `pip install pytest`) runs about 105 offline
checks of the cases that have tripped real runs: the wrong edition or a song
or video taken for an album, lost quote marks, untidy scores, reissue years,
names too long for the iPod, credit groups and role names, the file formats,
translation credits, the language checks and the iPod's page switches. They
need no network and take about a second. `DEVELOPING.md` has the details for
anyone changing the scripts.

## Licence

`art_fetch.py` comes from PodBox, which is licensed under the GNU General
Public License, version 2. This modified copy is under the same licence; see
`LICENSE`.
