"""
track_notes.py -- the Track page in PodBox's liner notes viewer.

For every track with its own English Wikipedia article it writes one file
into the iPod's Artwork\\Tracks folder:

  <Album Artist> - <Track Title>.txt

The page is the article's introduction, under the track's title and a facts
line, with the article credited at the end, as its licence asks. Most tracks
have no article and get no page; the viewer then leaves Track out.

The songs are found from the album ids.py identified, not by searching for
their titles: Wikidata lists an album's songs (its "tracklist", and songs
that say they are "part of" it), and a song counts only when its title
matches one of your tracks. Its introduction must be a real write-up (300
characters or more, not a list of other meanings) and must name the artist
in its opening, so the article about the original of a cover isn't used for
the cover. Many songs' introductions are a sentence or two; those get the
first paragraph of the article's background (or writing, recording…)
section after them, as the Album pages add one from the reception.

Last.fm is asked only where Wikipedia couldn't be (as the Album pages fall
back to it): songs Wikidata knows that have no usable English article
("Airbag" is a redirect to its album's article), and every track on albums
Wikidata doesn't have. It's asked by MusicBrainz recording when ids.py knows
it, and its text is used only when Last.fm puts the track on your album or
by your artist, with the same checks. --no-lastfm leaves Last.fm out.

Requests: about two to Wikidata per album with a Wikidata item, one to
Wikipedia per 20 songs found, and one to Last.fm per track it's asked about
(about 4 a second; around 1,000 tracks, 4-5 minutes, the first time for
Joe's library). What was found is kept, so later runs only
look at new albums, and look again at others after 180 days.

Files you've edited yourself are never overwritten, and nothing is ever
deleted. If the Track page is switched off on the iPod (Settings >
Appearance > Viewers), this does nothing.

Usage:
  python track_notes.py                              the iPod in the settings file
  python track_notes.py --only "Radiohead - OK Computer"
  python track_notes.py --ipod "credits test"        write to a test folder, not the iPod
"""
from __future__ import annotations

import argparse, re, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

try:
    import requests
    import artist_bios as ab
    import ids
    import translate as tr
    from credits import page_on, fold
    from liner_notes import wiki_summaries, wiki_article, sections, paragraphs
except ModuleNotFoundError as e:
    print(f"Missing something: {e}")
    print("Put this file next to ids.py, credits.py, artist_bios.py and translate.py.")
    sys.exit(1)

CACHE = ab.CACHE.parent / "tracks"
WIKIDATA = "https://www.wikidata.org/w/api.php"
WIKIPEDIA = "https://en.wikipedia.org/w/api.php"
RECHECK_DAYS = 180
MIN_CHARS = 300
VERSION = 4           # albums looked up by an older version are looked up again
# sections a short lead is filled out from, in order of preference; never lists or tables
BODY_SECTIONS = (r"background", r"writing|composition|recording|production", r"music|lyrics|theme",
                 r"history|release", r"^(?!.*(track|personnel|chart|certif|reference|note|cover|"
                 r"version|link|further|see also|accolade|single)).*$")
PAGE_SETTING = "track page"


# ---------------------------------------------------------------- Wikidata
def album_songs(album_q, session):
    """Wikidata items for the album's songs: its tracklist (P658) and the
    items that say they are part of it (P361)."""
    found = []
    r = ab.wiki_get(session, WIKIDATA, {"action": "wbgetentities", "ids": album_q, "props": "claims",
                                         "format": "json"})
    if r.ok:
        claims = ((r.json().get("entities") or {}).get(album_q) or {}).get("claims") or {}
        for c in claims.get("P658") or []:
            v = ((c.get("mainsnak") or {}).get("datavalue") or {}).get("value") or {}
            if v.get("id"):
                found.append(v["id"])
    r = ab.wiki_get(session, WIKIDATA, {"action": "query", "list": "search", "srnamespace": 0,
                                         "srsearch": f"haswbstatement:P361={album_q}", "srlimit": 50,
                                         "format": "json"})
    if r.ok:
        found += [h["title"] for h in (r.json().get("query") or {}).get("search") or []
                  if re.fullmatch(r"Q\d+", h.get("title", ""))]
    return list(dict.fromkeys(found))

def english_titles(items, session):
    """{item: (English Wikipedia title or "", English label)}: every song item
    with a name; "" where it has no English article (Last.fm is asked then)."""
    out = {}
    for n in range(0, len(items), 50):
        r = ab.wiki_get(session, WIKIDATA, {"action": "wbgetentities", "ids": "|".join(items[n:n + 50]),
                                             "props": "sitelinks|labels", "sitefilter": "enwiki",
                                             "languages": "en", "format": "json"})
        if not r.ok:
            continue
        for q, e in (r.json().get("entities") or {}).items():
            title = ((e.get("sitelinks") or {}).get("enwiki") or {}).get("title") or ""
            label = ((e.get("labels") or {}).get("en") or {}).get("value", "")
            if title or label:
                out[q] = (title, label)
    return out


# ---------------------------------------------------------------- matching and checking
def bare(title):
    """An article title without its disambiguation: "Lucky (Radiohead song)" -> "Lucky"."""
    return re.sub(r"\s*\([^)]*\)$", "", title or "").strip()

def match_tracks(tracks, songs):
    """{your track's place: article title, or "" for a song with no English
    article} for songs whose title is one of your tracks'."""
    by_title = {}
    for i, (_, _, title) in enumerate(tracks):
        by_title.setdefault(ids.clean_title(title), []).append(i)
    out = {}
    for article, label in sorted(songs.values(), key=lambda s: not s[0]):     # articles first
        for name in (bare(article), label):
            for i in by_title.get(ids.clean_title(name), []) if name else []:
                out.setdefault(i, article)
    return out

def opening(text, chars=200):
    """The start of an introduction, where it says whose song it is. Not cut
    at the first full stop: "…by American rapper Dr. Dre" has one early."""
    return text.strip()[:chars]

def fill_out(lead, article, session):
    """A lead under MIN_CHARS with the first paragraph from the article's
    background (or writing, recording…) section after it, as the Album pages
    add a paragraph from the reception: (text, "excerpts"), or (lead, "introduction")."""
    if len(lead) >= MIN_CHARS:
        return lead, "introduction"
    text, _ = wiki_article(article, session)
    secs = sections(text)[1:] if text else []
    for want in BODY_SECTIONS:
        for head, body in secs:
            if re.search(want, head, re.I):
                paras = paragraphs(body)
                if paras:
                    return lead.rstrip() + "\n" + paras[0], "excerpts"
    return lead, "introduction"

ENSEMBLE = re.compile(r"\s+(trio|quartet|quintet|sextet|band|orchestra|group|ensemble|experience|"
                      r"and his orchestra|& his orchestra)$", re.I)

def usable(intro, artist, need=MIN_CHARS, album=""):
    """Why an introduction can't be used, or "" if it can."""
    if not intro:
        return "no introduction"
    if len(intro) < need:
        return "too short, even with a paragraph from the article"
    if re.search(r"\bmay (also )?refer to\b", intro[:300]):
        return "a list of other meanings"
    names = [fold(a) for a in re.split(r"\s*(?:,|&| and | feat\.? | with )\s*", artist) if a.strip()]
    names += [fold(ENSEMBLE.sub("", artist))]                  # "Vince Guaraldi Trio" -> "Vince Guaraldi"
    lead = fold(opening(intro))
    named = any(n and n in lead for n in names + [fold(artist)])
    # or it names the album (a song "by Madvillain" on Madvillainy, filed under MF DOOM):
    # the song came from the album's own Wikidata item, and the article about the
    # original of a cover doesn't open by naming the cover's album
    on_album = album and fold(ids.plain_album(album)) in lead
    if not (named or on_album):
        return "doesn't name the artist or album first (perhaps the original of a cover)"
    return ""


# ---------------------------------------------------------------- Last.fm
LASTFM = "https://ws.audioscrobbler.com/2.0/"

def lastfm_track(artist, title, album, session, key, mbid=None):
    """(text, why) from Last.fm's write-up of the track: asked by its
    MusicBrainz recording when known, else by artist and title, and used only
    when Last.fm puts it on your album or by your artist (a same-named song by
    someone else is never used)."""
    asks = ([{"mbid": mbid}] if mbid else []) + [{"artist": artist, "track": title}]
    for ask in asks:
        time.sleep(0.25)                                   # Last.fm asks for no more than 5 a second
        try:
            r = session.get(LASTFM, headers=ab.UA, timeout=20,
                            params={"method": "track.getinfo", "api_key": key, "format": "json", **ask})
        except requests.RequestException:
            return "", "Last.fm didn't answer"
        if not r.ok:
            continue
        t = r.json().get("track") or {}
        if not t:
            continue
        theirs_album = fold(((t.get("album") or {}).get("title")) or "")
        theirs_artist = fold(((t.get("artist") or {}).get("name")) or "")
        if not (theirs_artist == fold(artist) or (theirs_album and theirs_album == fold(ids.plain_album(album)))):
            continue
        raw = ((t.get("wiki") or {}).get("content")) or ((t.get("wiki") or {}).get("summary")) or ""
        raw = re.split(r"User-contributed text is available|<a href=\"https?://www\.last\.fm[^>]*>Read more", raw)[0]
        text = "\n".join(p for p in (ab.strip_markup(x) for x in re.split(r"\n+", raw)) if p)
        if text:
            return text, ""
    return "", "no Last.fm write-up"


# ---------------------------------------------------------------- the page
def page_text(title, place, album, intro, article, date, part="introduction", source="wikipedia"):
    """The Track file: "#title", a "#facts" line, the text's paragraphs,
    and "#sources" crediting where it came from."""
    paras = ab.trim_bio(intro).split("\n")
    credit = tr.credit(source, title=article, date=date, part=part)[2:]       # without its "# "
    lines = [f"#title\t{title}", f"#facts\tTrack {place}, {album}", ""]
    lines += [p for p in paras if p]
    lines += ["", f"#sources\t{credit}"]
    return "\n".join(lines) + "\n"

def track_number(album, i):
    disc, num, _ = album["tracks"][i]
    multi = len({t[0] for t in album["tracks"]}) > 1
    return f"{disc}-{num}" if multi else str(num)


# ---------------------------------------------------------------- the run
def main(argv=None):
    conf = ab.settings()
    drive = (conf.get("ipod drive") or "G:").rstrip("\\/")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("music_root", nargs="?", default=conf.get("music folder", "").rstrip("\\/") or f"{drive}\\Music",
                    help="the iPod's music folder (default: from the settings file)")
    ap.add_argument("--ipod", help="the iPod's own folder (default: the folder holding the music folder)")
    ap.add_argument("--only", action="append", default=[], help='"Artist - Album" (can be given more than once)')
    ap.add_argument("--refresh", action="store_true", help="look every album up again")
    ap.add_argument("--no-lastfm", action="store_true",
                    help="Wikipedia only: don't ask Last.fm about tracks without an article")
    args = ap.parse_args(argv)
    lastfm_key = None if args.no_lastfm else (ab.af.load_credentials().lastfm_api_key or None)

    music = Path(args.music_root)
    ipod = Path(args.ipod) if args.ipod else music.resolve().parent
    if not page_on(ipod, PAGE_SETTING):
        print("The Track page is switched off on the iPod, so no track notes are fetched.")
        return 0
    lib = ids.library().get("albums") or {}
    if not lib:
        print("Run ids.py first: it reads your albums and identifies them.")
        return 1
    records = {}
    for path in ids.CACHE.glob("*.json"):
        rec = ab.load_json(path)
        if rec and rec.get("key") in lib:
            records[rec["key"]] = rec
    only = {ab.norm(o) for o in args.only}
    keys = [k for k in sorted(lib) if not only or ab.norm(k) in only or ab.norm(lib[k]["artist"]) in only]
    with_q = [k for k in keys if ((records.get(k) or {}).get("mb") or {}).get("wikidata")]
    print(f"{len(with_q)} albums have a Wikidata item to find their songs on Wikipedia from."
          + (" Last.fm is asked about the other tracks." if lastfm_key else ""))
    if not lastfm_key:
        keys = with_q

    out_dir = ipod / "Artwork" / "Tracks"
    out_dir.mkdir(parents=True, exist_ok=True)
    (CACHE / "albums").mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    counts = {"written": 0, "same": 0, "kept": 0, "albums looked up": 0, "Last.fm asked": 0}
    rejected = []
    try:
        for n, k in enumerate(keys, 1):
            album, q = lib[k], ((records.get(k) or {}).get("mb") or {}).get("wikidata")
            name = ab.safe_name(k)
            if not name:
                continue
            path = CACHE / "albums" / f"{name}.json"
            seen = ab.load_json(path) or {}
            fresh = seen.get("wikidata") == q and seen.get("version") == VERSION and not args.refresh and \
                time.time() - seen.get("checked", 0) < RECHECK_DAYS * 86400
            if not q:
                seen.setdefault("songs", {})
            elif not fresh:
                counts["albums looked up"] += 1
                songs = english_titles(album_songs(q, session), session)
                found = match_tracks(album["tracks"], songs)
                intros = {}
                articles = sorted({a for a in found.values() if a})
                for m in range(0, len(articles), 20):
                    intros.update(wiki_summaries(articles[m:m + 20], session))
                today = time.strftime("%Y-%m-%d")
                seen = {"wikidata": q, "version": VERSION, "checked": int(time.time()), "songs": {}}
                filled = {}
                for i, article in sorted(found.items()):
                    if not article:
                        seen["songs"][str(i)] = {"article": "", "text": "", "why": "no English Wikipedia article",
                                                 "date": today}
                        continue
                    lead = intros.get(article, "")
                    why = usable(lead, album["artist"], need=0, album=album["album"])
                    if not why and article not in filled:
                        filled[article] = fill_out(lead, article, session)
                    text, part = filled.get(article, (lead, "introduction"))
                    why = why or usable(text, album["artist"], album=album["album"])
                    seen["songs"][str(i)] = {"article": article, "text": "" if why else text, "part": part,
                                             "why": why, "date": today}
                ab.save_json(path, seen)
            if lastfm_key:
                looked = seen.setdefault("lastfm", {})
                if time.time() - looked.get("checked", 0) >= RECHECK_DAYS * 86400 or args.refresh:
                    looked.clear()
                    looked["checked"] = int(time.time())
                tracks_mb = ((records.get(k) or {}).get("mb") or {}).get("tracks") or {}
                for i, (_, _, title) in enumerate(album["tracks"]):
                    song = seen["songs"].get(str(i))
                    # Last.fm only where Wikipedia couldn't be: songs Wikidata knows with no
                    # usable article, and every track on albums Wikidata doesn't have
                    wanted = (song is not None and not song.get("text")) if q else True
                    if not wanted or str(i) in looked:
                        continue
                    text, why = lastfm_track(album["artist"], title, album["album"], session, lastfm_key,
                                             (tracks_mb.get(str(i)) or {}).get("recording"))
                    why = why or usable(text, album["artist"], album=album["album"])
                    looked[str(i)] = {"text": "" if why else text, "why": why, "date": time.strftime("%Y-%m-%d")}
                    counts["Last.fm asked"] += 1
                ab.save_json(path, seen)
            pages = []
            for i, song in seen.get("songs", {}).items():
                if song.get("text"):
                    pages.append((i, song["text"], song["article"], song.get("part", "introduction"),
                                  song.get("date"), "wikipedia"))
            for i, song in (seen.get("lastfm") or {}).items():
                if i != "checked" and song.get("text") and not (seen["songs"].get(i) or {}).get("text"):
                    pages.append((i, song["text"], None, "introduction", song.get("date"), "lastfm"))
            for i, song in sorted(seen.get("songs", {}).items(), key=lambda kv: int(kv[0])):
                if song.get("article") and not song.get("text") and \
                        not ((seen.get("lastfm") or {}).get(i) or {}).get("text"):
                    rejected.append(f"{k}: \"{album['tracks'][int(i)][2]}\" ({song['article']}): {song.get('why')}")
            for i, text, article, part, date, source in sorted(pages, key=lambda p: int(p[0])):
                title = album["tracks"][int(i)][2]
                fname = ab.safe_name(f"{album['artist']} - {title}")
                if not fname:
                    continue
                text = page_text(title, track_number(album, int(i)), album["album"],
                                 text, article, date, part, source)
                mp = CACHE / f"{fname}.json"
                meta = ab.load_json(mp) or {"key": f"{album['artist']} - {title}"}
                res = ab.write_if_ours(out_dir / f"{fname}.txt", text.encode("utf-8"), meta, "txt_sha1")
                ab.save_json(mp, meta)
                counts[res] += 1
            print(f"\r  {n}/{len(keys)} albums", end="", flush=True)
    except KeyboardInterrupt:
        print("\nStopped. What was found is kept; run again to carry on.")
    print()
    report = HERE / "Tracks not used.txt"
    report.write_text("Songs with an English Wikipedia article whose introduction wasn't used, and why.\n\n"
                      + "\n".join(rejected) + "\n", encoding="utf-8")
    print(f"Track notes written or updated: {counts['written']}, unchanged: {counts['same']}, "
          f"kept as you left them: {counts['kept']}. Albums looked up: {counts['albums looked up']}, "
          f"Last.fm asked about {counts['Last.fm asked']} tracks. "
          f"Not used: {len(rejected)} (listed in \"{report.name}\").")
    return 0

if __name__ == "__main__":
    sys.exit(main())
