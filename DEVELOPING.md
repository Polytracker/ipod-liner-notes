# Developing iPod Liner Notes

This is for someone changing the scripts. `README.md` is for someone using them.

The scripts run on a Windows PC with the iPod plugged in as a drive. They look
up artists and albums online and write plain files onto the iPod; PodBox (a
Rockbox fork, [anthonyfletcher/podbox](https://github.com/anthonyfletcher/podbox),
with the Liner Notes viewer from
[Polytracker/podbox](https://github.com/Polytracker/podbox)) reads those files.
The firmware never goes online and never runs these scripts; the files are the
whole interface between the two.

## The scripts

| Script | Writes | Reads first |
| --- | --- | --- |
| `art_fetch.py` | `Music\<Artist>\folder.jpg`, the artist photos | — |
| `artist_fallback.py` | `folder.jpg` from an album cover where no photo was found | — |
| `ids.py` | nothing on the iPod: which MusicBrainz and Discogs release each album folder is, cached on the PC | your files' tags |
| `artist_bios.py` | `Artwork\Bios\<Artist>.txt` and `.jpg` (Bio page) | `ids.py`'s cache |
| `liner_notes.py` | `Artwork\Notes\<Album Artist> - <Album>.txt` and `.jpg` (Album page) | `ids.py`'s cache |
| `track_notes.py` | `Artwork\Tracks\<Album Artist> - <Track Title>.txt` (Track page) | `ids.py`'s cache |
| `credits.py` | `Artwork\Credits\<Album Artist> - <Album>.txt` (Credits page and Other Appearances) | `ids.py`'s cache and saved releases |
| `translate.py` | nothing: DeepL translation, used by the four above | — |
| `preview.py` | PNG pictures of Credits pages, drawn with the iPod's own fonts | the credits files |
| `link_dryrun.py` | a report of who links to whom for Other Appearances, without writing pages | `ids.py`'s cache |

Two front ends run them:

- **`iPod Liner Notes.bat`**: photos, fallback, bios, album notes, then
  PodBox's `database_pb.exe` and `artcache_pb.exe` from the iPod's
  `.rockbox\tools`. The install script in the PodBox project runs it after a
  firmware install when there's new music.
- **`Run liner notes pages.ps1`**: bios, album notes, track notes and credits,
  with live output and a log file each.

Both start with a read-only `chkdsk` of the iPod and stop, writing nothing,
if it reports errors. Writing to a damaged FAT spreads the damage.

`iPod Liner Notes settings.txt` holds the drive, the music folder, recheck
intervals and the keys. `artist_bios.batch_settings()` reads it for the two
front ends, and each script falls back to it for its own defaults.

## Which album is it

Everything after photos depends on `ids.py` getting the release right, so a
page about a different album with the same name never appears. It tries the
strongest evidence first (MusicBrainz and Discogs IDs in the tags, then
barcode, ISRCs, store links, disc ID, catalogue number, and only last a title
search) and checks every candidate against your files: the artist, the track
titles and the track count. Results are cached in
`%APPDATA%\RockboxArtistArt\ids\`, one JSON file per album, so later steps
and later runs make no requests for albums already identified.

Albums split across folders under one album name count as one album
(`merge_folders`), as they do on the iPod.

## Where the text comes from

Each page has an order of sources, first hit wins:

- **Bio:** English Wikipedia's introduction (for an artist who doesn't work
  in English, their own language's article, machine-translated); then
  Last.fm; then Discogs; else a facts line. The artist is
  settled on Wikidata when only one musician or band has the name, otherwise
  on MusicBrainz by matching their albums against yours.
- **Album:** English Wikipedia's introduction plus the first paragraph of its
  critical reception and the scores from its ratings box (the artist's own
  language's article, translated, where they don't work in English); then
  Last.fm; then Discogs; else the facts line alone.
- **Track:** only songs Wikidata lists on the identified album whose titles
  match your tracks. The article must be a real write-up (300 characters or
  more) and name the artist in its opening, so a cover version doesn't get
  the original's article. Then Last.fm where Wikipedia had nothing.
- **Credits:** five groups (Musicians, Producers, Engineers, Songwriters,
  Credited). Each group comes whole from one source, never mixed: your
  files' own credit tags, otherwise whichever of MusicBrainz and Discogs
  covers more of your album in that group. `credits.py --compare` lists where
  that choice changed without writing anything.

Machine-translated text always says so in its last line, and DeepL's
asterisk italics are stripped. Last.fm text can be fan-written; it's kept,
credited as Last.fm.

## The file formats

These are the contract with the firmware. The viewer parses them line by line;
`docs/podbox/artwork-guide.md` in the PodBox repository is the reference.
Text is UTF-8, one paragraph a line.

- **Bio:** the name, a dates line (may be empty), a blank line, then the bio.
  The `.jpg` banner is 320 × 160.
- **Album:** the title, a facts line, the notes, the scores and the source.
  The `.jpg` is the album's cover cropped to a banner.
- **Track and Credits** use marker lines, each a `#` word, a tab and its text:
  `#title`, `#facts`, `#status` and `#sources`; `## ` starts a heading.
  Credits rows are `Name<TAB>Role, Role [track numbers]`; square brackets hold
  track numbers only, which the viewer draws small and grey.
- **Other Appearances** is a `#links` section at the end of a credits file,
  which the page doesn't show:

  ```
  #links
  P<TAB><person><TAB><their role on this album>
  A<TAB><album artist><TAB><album><TAB><how credited there>
  T<TAB><album artist><TAB><album><TAB><track title><TAB><how credited>
  ```

  Album artist and album names are copied exactly from the tags, because the
  firmware opens the album by them. People are matched by their MusicBrainz or
  Discogs ID, never by name alone. Each person gets at most 40 rows, and the
  viewer reads at most 64 people and 256 rows a file.

Facts lines separate their parts with ` · `. Titles are written in full; the
viewer's **Trim Titles** setting does any trimming.

## The iPod's own switches

The Liner Notes menu on the iPod can switch each page off. `ipod_page_on()`
in `artist_bios.py` reads the iPod's `.rockbox\config.cfg` (`liner notes`,
`liner notes artist bio`, `album notes`, `track notes`, `credits`), and each
script skips a page that's off. PodBox writes only settings changed from
their default, so a missing line means on. Files already on the iPod are
never deleted.

## Keys and caches

- **Keys** go in the settings file and stay out of the repository: the
  committed copy has them empty. `discogs token` is a Discogs personal token;
  `deepl key` a DeepL API key (the free tier is enough). Last.fm's key is the
  one `art_fetch.py` saves in `%APPDATA%\RockboxArtistArt\artist_art_credentials.json`.
  Without a key, that source or translation is skipped.
- **Caches** live in `%APPDATA%\RockboxArtistArt\`: `ids\` (release
  identities), `bios\` and the notes cache (downloads), `translations.json`.
  Deleting them only means the next run asks again.
- **Rechecks:** missing pages are looked for again after `recheck missing
  days`; existing ones after a year, and replaced only when the text really
  changed and you haven't edited the file. `--refresh` and `--only` force
  one artist or album.

## Being a good client

- MusicBrainz: at least 1.2 s between requests; a "busy" (503) answer is
  retried after 2, 4, 8, 16 and 32 s before falling back to another source.
- Every request sends a `User-Agent` naming this project, as Wikimedia and
  MusicBrainz ask.
- Discogs and Last.fm requests honour `Retry-After`.

## Tests

```
python -m pytest -q
```

About 105 offline tests in `tests/`, with no network: the release matching,
credit grouping and role names, the file formats, translation credits and
the switches. Add one for any change to what's written onto the iPod.

## Changing a format

A change to what a file says is a change to the firmware's input, so it
needs the matching viewer change in Polytracker/podbox
(`apps-ipod/viewers/artist_bio/`) and `artwork-guide.md` updated in the same
step. `preview.py` draws pages with the viewer's layout numbers (its `LAYOUT`);
change both together.

## Releasing to the PC

There's no installer. The scripts run from a folder on the PC
(`Documents\Claude\iPod Liner Notes` on the owner's machine); copying the
changed `.py` files there is the release. Keep the settings file: it holds
the keys.
