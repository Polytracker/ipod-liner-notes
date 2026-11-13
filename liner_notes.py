"""
liner_notes.py -- album notes for PodBox's Liner Notes screen.

For every album folder in the iPod's music folder it finds notes about the
album and writes two files into the iPod's Artwork\\Notes folder, which Liner
Notes (hold Select on Now Playing, or on an album in Music) reads:

  <Album Artist> - <Album>.txt   the title, a facts line, the notes, then the
                                 critics' scores and where the text came from
  <Album Artist> - <Album>.jpg   the album's own cover, cropped to a banner

Which album it is gets settled on MusicBrainz first, by the artist (using the
ID artist_bios.py saved, when there is one) and the title, so another album
of the same name can't slip in. The notes are that album's English Wikipedia
introduction, the first paragraph of its critical reception and the scores
from its ratings box. Without a Wikipedia article they come from Last.fm or
Discogs, and failing those the page is just the facts line: year, label,
tracks and length, read from your own files.

Albums already done are skipped; one whose notes are over a year old is
checked again and only rewritten if the text has really changed. A file you
have edited yourself is never overwritten.

Usage:
  python liner_notes.py "G:\\Music"
  python liner_notes.py "G:\\Music" --only "Radiohead"           one artist
  python liner_notes.py "G:\\Music" --only "Radiohead - OK Computer"
  python liner_notes.py "G:\\Music" --refresh                    fetch all again
"""
from __future__ import annotations

import argparse, html, json, os, re, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

try:
    import requests, mutagen
    import artist_bios as ab
except ModuleNotFoundError as e:
    print(f"Missing something: {e}")
    print("Put this file next to artist_bios.py and art_fetch.py, and run: "
          "pip install requests pillow mutagen opencv-python")
    sys.exit(1)

CACHE = ab.CACHE.parent / "notes"
MISSING_LIST = HERE / "Albums without notes.txt"
WIKI_API = "https://en.wikipedia.org/w/api.php"
MB = "https://musicbrainz.org/ws/2/"
MAX_SCORES = 8
SINGLES = {"singles", "single", "misc", "miscellaneous", "loose tracks"}


# ---------------------------------------------------------------- your files
def tag(f, *keys):
    for k in keys:
        v = (f.tags or {}).get(k) if f and f.tags else None
        if v:
            return str(v[0] if isinstance(v, list) else v).strip()
    return ""

def read_tags(p):
    try:
        return mutagen.File(p, easy=True)
    except Exception:
        return None

def album_info(folder, artist):
    """Album, album artist, year, label and track count, from the first and last
    track's tags -- reading every file on the iPod's disk takes minutes. None for
    a folder that isn't one album (a Singles folder, mixed album tags)."""
    tracks = [p for p in sorted(folder.iterdir()) if p.suffix.lower() in ab.AUDIO]
    if not tracks or folder.name.lower() in SINGLES:
        return None
    first, last = read_tags(tracks[0]), read_tags(tracks[-1])
    album = tag(first, "album")
    if not album or (last is not None and tag(last, "album").casefold() != album.casefold()):
        return None
    return {"album": album,
            "artist": tag(first, "albumartist", "album artist") or tag(first, "artist") or artist,
            "year": ab.year(tag(first, "date", "originaldate", "year")),
            "label": tag(first, "organization", "label", "publisher"),
            "tracks": len(tracks), "minutes": None, "files": tracks}

def add_minutes(info):
    """The album's length, reading every track: only when its notes are fetched."""
    seconds = 0.0
    for p in info["files"]:
        f = read_tags(p)
        seconds += getattr(getattr(f, "info", None), "length", 0) or 0
    info["minutes"] = round(seconds / 60)

def facts_line(info, mb_year=None, mb_label=None):
    n = info["tracks"]
    return " · ".join(x for x in (
        info["artist"], info["year"] or mb_year or "", info["label"] or mb_label or "",
        f"{n} track{'s' if n != 1 else ''}",
        f"{info['minutes']} min" if info["minutes"] else "") if x)


# ---------------------------------------------------------------- which album
def bare_title(t):
    """"OK Computer (Collector's Edition)" -> "okcomputer", for comparing titles."""
    t = re.sub(r"\s*[\(\[][^)\]]*(edition|remaster|deluxe|expanded|anniversary|version|bonus)[^)\]]*[\)\]]",
               "", t or "", flags=re.I)
    return ab.norm(t)

def wd_label(ent, session):
    """The album's first record label, by name, from its Wikidata item."""
    ids = ab.wd_claim_ids(ent, "P264")[:1]
    if not ids:
        return ""
    lab = ab.wd_entities(ids, session, props="labels").get(ids[0]) or {}
    labels = lab.get("labels") or {}
    return ((labels.get("en") or labels.get("mul") or {}).get("value") or "").strip()

def wd_album(info, artist_qid, session):
    """(English Wikipedia title, Wikidata ID, record label) of the album on
    Wikidata: an item whose performer is the artist and whose name is the
    album's. Wikidata answers far more readily than MusicBrainz, so it is asked
    first."""
    want = {bare_title(info["album"]), ab.norm(info["album"])}
    for query in (f"haswbstatement:P175={artist_qid} {info['album']}",
                  f"haswbstatement:P175={artist_qid}"):
        r = ab.wiki_get(session, ab.WD_API, {"action": "query", "list": "search", "srsearch": query,
                                             "srlimit": 50, "srnamespace": 0, "format": "json"})
        if not r.ok:
            return None, None, ""
        ids = [h["title"] for h in (r.json().get("query") or {}).get("search") or []]
        ents = ab.wd_entities(ids[:50], session, props="sitelinks|labels|aliases|claims") if ids else {}
        for q in ids:
            ent = ents.get(q) or {}
            if ab.wd_names(ent) & want:
                label = "" if info.get("label") else wd_label(ent, session)
                return ((ent.get("sitelinks") or {}).get("enwiki") or {}).get("title"), q, label
    return None, None, ""

def release_group(info, artist_mbid, session):
    """The MusicBrainz release group for this album, or None."""
    esc = lambda s: s.replace('"', '\\"')
    who = f"arid:{artist_mbid}" if artist_mbid else f'artist:"{esc(info["artist"])}"'
    j = ab.mb_get(session, MB + "release-group",
                  {"query": f'releasegroup:"{esc(info["album"])}" AND {who}', "fmt": "json", "limit": 15})
    want = bare_title(info["album"])
    hits = [g for g in (j or {}).get("release-groups") or [] if bare_title(g.get("title")) == want]
    if not hits:
        return None
    rank = lambda g: ((g.get("primary-type") not in ("Album", "EP")),
                      (g.get("first-release-date") or "")[:4] != (info["year"] or "x"),
                      -int(g.get("score") or 0))
    return sorted(hits, key=rank)[0]

def rg_wikidata(rgid, session):
    j = ab.mb_get(session, MB + f"release-group/{rgid}", {"inc": "url-rels", "fmt": "json"})
    for rel in (j or {}).get("relations") or []:
        if rel.get("type") == "wikidata":
            m = re.search(r"(Q\d+)$", (rel.get("url") or {}).get("resource", ""))
            if m:
                return m.group(1)
    return None

def wiki_title(info, rg, session):
    """(English Wikipedia title, confirmed) for the album."""
    if rg:
        q = rg_wikidata(rg["id"], session)
        if q:
            ent = ab.wd_entities([q], session, props="sitelinks").get(q) or {}
            t = ((ent.get("sitelinks") or {}).get("enwiki") or {}).get("title")
            if t:
                return t, True
    # by title, then by search: accept only an album article that names the artist.
    # Titles are case-sensitive past the first letter, so a tag's "Hail To the
    # Thief" misses the article the search then finds.
    tries = [f"{info['album']} ({info['artist']} album)", f"{info['album']} (album)",
             f"{info['album']} (EP)", info["album"]]
    r = ab.wiki_get(session, WIKI_API, {"action": "query", "list": "search", "srlimit": 3,
                                        "srsearch": f"{info['album']} {info['artist']} album",
                                        "format": "json"})
    if r.ok:
        tries += [h["title"] for h in (r.json().get("query") or {}).get("search") or []]
    for t in tries:
        lead = ab.wiki_summary(t, session)
        if lead and ab.norm(info["artist"]) in ab.norm(lead[:600]) \
                and bare_title(info["album"]) in ab.norm(lead[:200]) \
                and re.search(r"\b(album|EP|record)\b", lead[:300], re.I):
            return t, False
    return None, False


# ---------------------------------------------------------------- the notes
def wiki_article(title, session):
    """(plain text with == headings ==, wikitext) of the whole article."""
    r = ab.wiki_get(session, WIKI_API, {
        "action": "query", "prop": "extracts|revisions", "explaintext": 1,
        "exsectionformat": "wiki", "rvprop": "content", "rvslots": "main",
        "redirects": 1, "titles": title, "format": "json", "formatversion": 2})
    if not r.ok:
        return "", ""
    pages = (r.json().get("query") or {}).get("pages") or []
    if not pages:
        return "", ""
    p = pages[0]
    rev = (p.get("revisions") or [{}])[0]
    return p.get("extract") or "", ((rev.get("slots") or {}).get("main") or {}).get("content") or ""

def sections(text):
    """[(heading, body)] with the lead as heading ""."""
    parts = re.split(r"\n(={2,4})\s*(.+?)\s*\1\s*\n", "\n" + text)
    out = [("", parts[0])]
    for i in range(1, len(parts) - 2, 3):
        out.append((parts[i + 1], parts[i + 2]))
    return out

def first_para(body):
    for p in re.split(r"\n+", body or ""):
        p = p.strip()
        if len(p) > 80:
            return p
    return ""

def reception(text):
    """The first paragraph about how critics received it."""
    secs = sections(text)
    for want in (r"critical reception", r"^reception$", r"reception", r"critical response"):
        for head, body in secs:
            if re.search(want, head, re.I):
                p = first_para(body)
                if p:
                    return p
    return ""

def unwiki(s):
    s = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    s = re.sub(r"\{\{\s*[Rr]ating\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\}\}", r"\1/\2", s)
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", s)
    s = re.sub(r"\[https?://\S+\s+([^\]]+)\]", r"\1", s)
    s = re.sub(r"'{2,}", "", s)
    s = re.sub(r"<[^>]+>", "", html.unescape(s))
    return re.sub(r"\s+", " ", s).strip()

def scores(wikitext):
    """["Pitchfork 10/10", ...] from the article's Music ratings box."""
    m = re.search(r"\{\{\s*(?:Music|Album) ratings(.*?)\n\}\}", wikitext or "", re.S | re.I)
    if not m:
        return []
    box, out = m.group(1), []
    mc = re.search(r"^\s*\|\s*MC\s*=\s*(.+)$", box, re.M)
    if mc:
        v = re.search(r"\d+", unwiki(mc.group(1)))
        if v:
            out.append(f"Metacritic {v.group(0)}")
    for n, name in re.findall(r"^\s*\|\s*rev(\d+)\s*=\s*(.+)$", box, re.M):
        sc = re.search(rf"^\s*\|\s*rev{n}[Ss]core\s*=\s*(.+)$", box, re.M)
        name, score = unwiki(name), unwiki(sc.group(1)) if sc else ""
        if name and score and len(score) <= 12:
            out.append(f"{name} {score}")
    return out[:MAX_SCORES]

def lastfm_notes(info, session, key):
    r = session.get("https://ws.audioscrobbler.com/2.0/", headers=ab.UA, timeout=20, params={
        "method": "album.getinfo", "api_key": key, "format": "json",
        "artist": info["artist"], "album": info["album"], "autocorrect": 1})
    if not r.ok:
        return ""
    raw = (((r.json().get("album") or {}).get("wiki")) or {}).get("content") or ""
    raw = re.split(r"User-contributed text is available|<a href=\"https?://www\.last\.fm[^>]*>Read more", raw)[0]
    text = "\n".join(p for p in (ab.strip_markup(x) for x in re.split(r"\n+", raw)) if p)
    return text if len(text) > 80 else ""

def discogs_notes(info, session, token):
    h = dict(ab.UA, Authorization=f"Discogs token={token}")
    r = session.get("https://api.discogs.com/database/search", headers=h, timeout=20, params={
        "artist": info["artist"], "release_title": info["album"], "type": "master", "per_page": 5})
    time.sleep(1.1)
    if not r.ok:
        return ""
    for hit in r.json().get("results") or []:
        if bare_title(hit.get("title", "").split(" - ", 1)[-1]) != bare_title(info["album"]):
            continue
        d = session.get(hit["resource_url"], headers=h, timeout=20)
        time.sleep(1.1)
        notes = ab.strip_markup((d.json() if d.ok else {}).get("notes") or "")
        return notes if len(notes) > 80 else ""
    return ""

def find_notes(info, who, session, args):
    """(paragraphs, source, release group) -- paragraphs may be empty, leaving the
    facts line. `who` is the artist's saved IDs from artist_bios.py."""
    rg, title, sure = None, None, False
    if who.get("wikidata"):
        try:
            title, q, label = wd_album(info, who["wikidata"], session)
            sure = bool(q)
            if label:
                info["wd_label"] = label
        except Exception as e:
            print(f"     wikidata: {e}")
    if not title:
        try:
            rg = release_group(info, who.get("mbid"), session)
        except Exception as e:
            print(f"     musicbrainz unavailable ({e})")
    if not title:
        try:
            title, sure = wiki_title(info, rg, session)
        except Exception as e:
            print(f"     wikipedia: {e}")
    if title:
        text, wt = wiki_article(title, session)
        lead = ab.trim_bio(sections(text)[0][1]) if text else ""
        if lead:
            paras = lead.split("\n")
            rec = reception(text)
            if rec:
                paras += ["# Critical reception", ab.clean_bio(rec)]
            sc = scores(wt)
            if sc:
                paras.append("# " + " · ".join(sc))
            paras.append("# From Wikipedia, CC BY-SA")
            return paras, "wikipedia" + ("" if sure else " (not confirmed)"), rg
    for name, fn, cred in (("Last.fm", lastfm_notes, args.lastfm_key),
                           ("Discogs", discogs_notes, args.discogs_token)):
        if not cred:
            continue
        try:
            text = fn(info, session, cred)
        except Exception as e:
            print(f"     {name.lower()}: {e}")
            text = ""
        if text:
            return ab.trim_bio(text).split("\n") + [f"# From {name}"], name.lower(), rg
    return [], "", rg


# ---------------------------------------------------------------- main
def artist_ids(folder_artist):
    """The artist's Wikidata and MusicBrainz IDs, as artist_bios.py confirmed them."""
    p = ab.CACHE / f"{ab.safe_name(folder_artist)}.json"
    try:
        m = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not m.get("identity_verified", True):
        return {}
    return {"wikidata": m.get("wikidata"), "mbid": m.get("mbid")}

def due(meta, days):
    if not days:
        return False
    try:
        age = time.time() - time.mktime(time.strptime(meta.get("fetched", ""), "%Y-%m-%d"))
    except ValueError:
        return True
    return age > days * 86400

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("music_root", help="the iPod's music folder, Artist\\Album folders")
    ap.add_argument("--ipod", help="the iPod's own folder (default: the folder holding the music folder)")
    ap.add_argument("--refresh", action="store_true", help="fetch every album's notes again")
    ap.add_argument("--refresh-after", type=int, default=365, metavar="DAYS",
                    help="check an album's notes again once they are this old (default 365; 0 = never)")
    ap.add_argument("--only", action="append", default=[],
                    help='just this artist, or "Artist - Album" (can be given more than once)')
    ap.add_argument("--no-banners", action="store_true", help="notes only, no covers")
    ap.add_argument("--discogs-token", default=os.environ.get("DISCOGS_TOKEN"),
                    help="Discogs personal token, an extra source (or set DISCOGS_TOKEN)")
    args = ap.parse_args(argv)
    args.lastfm_key = ab.af.load_credentials().lastfm_api_key or None

    music = Path(args.music_root)
    if not music.is_dir():
        print(f"Can't find {music}")
        return 1
    out_dir = Path(args.ipod) / "Artwork" / "Notes" if args.ipod else music.resolve().parent / "Artwork" / "Notes"
    out_dir.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    print(f"Writing liner notes to {out_dir}")
    print("Reading the album folders...")

    only = {ab.norm(o) for o in args.only}
    work = []
    for artist, folders in sorted(ab.scan_library(music).items(), key=lambda kv: kv[0].casefold()):
        if only and not any(o.startswith(ab.norm(artist)) for o in only):
            continue
        for folder in sorted(folders):
            info = album_info(folder, artist)
            if not info:
                continue
            key = f"{info['artist']} - {info['album']}"
            if only and ab.norm(artist) not in only and ab.norm(info["artist"]) not in only \
                    and ab.norm(key) not in only:
                continue
            work.append((artist, folder, info, key))
    print(f"{len(work)} albums\n")

    session = requests.Session()
    counts = {"written": 0, "same": 0, "kept": 0, "facts": 0, "error": 0}
    missing = []
    try:
        for i, (artist, folder, info, key) in enumerate(work, 1):
            name = ab.safe_name(key)
            mp = CACHE / f"{name}.json"
            meta = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else None
            fresh = False
            try:
                if meta is None or args.refresh or due(meta, args.refresh_after):
                    fresh = True
                    print(f"{i:4d}/{len(work)} {key}")
                    add_minutes(info)
                    paras, source, rg = find_notes(info, artist_ids(artist), session, args)
                    mb_year = ((rg or {}).get("first-release-date") or "")[:4] or None
                    new = {"key": key, "facts": facts_line(info, mb_year, info.get("wd_label")), "notes": "\n".join(paras),
                           "source": source, "rg": (rg or {}).get("id"),
                           "fetched": time.strftime("%Y-%m-%d")}
                    if meta:
                        new.update({k: meta[k] for k in ("txt_sha1", "jpg_sha1") if k in meta})
                        if not args.refresh and ab.same_bio(meta.get("notes"), new["notes"]):
                            new["notes"], new["source"] = meta["notes"], meta.get("source", "")
                        if meta.get("notes") and not new["notes"]:
                            new["notes"], new["source"] = meta["notes"], meta.get("source", "")
                    meta = new
                    print(f"     notes: {meta['source'] or 'facts only'}")
                text = f"{info['album']}\n{meta['facts']}\n\n{meta['notes']}\n"
                res = [ab.write_if_ours(out_dir / f"{name}.txt", text.encode("utf-8"), meta, "txt_sha1")]
                jpg = out_dir / f"{name}.jpg"
                if not args.no_banners and (fresh or not jpg.exists()):
                    cover = ab.album_cover([folder])[0]
                    if cover:
                        res.append(ab.write_if_ours(jpg,
                                                    ab.banner_bytes(cover, True), meta, "jpg_sha1"))
                mp.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
                if not meta["notes"]:
                    counts["facts"] += 1
                    missing.append(key)
                counts["written" if "written" in res else "kept" if "kept" in res else "same"] += 1
            except Exception as e:
                counts["error"] += 1
                print(f"  !! {key}: {e}")
    except KeyboardInterrupt:
        print("\nStopped. Run again to carry on where it left off.")

    MISSING_LIST.write_text("\n".join(missing) + ("\n" if missing else ""), encoding="utf-8")
    print(f"\nLiner notes written or updated: {counts['written']}, unchanged: {counts['same']}, "
          f"kept as you left them: {counts['kept']}, facts only: {counts['facts']}"
          + (f", failed: {counts['error']}" if counts["error"] else ""))
    if missing:
        print(f"Albums with only a facts line are listed in \"{MISSING_LIST.name}\".")
    return 0


if __name__ == "__main__":
    sys.exit(main())
