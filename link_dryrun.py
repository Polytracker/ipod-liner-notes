"""
link_dryrun.py -- a test run for the Credits page's "on other records" list.

Which people credited on your albums also appear on other albums in your
library, and can we be sure they're the same person?

It reads what ids.py worked out for each album, and the releases it saved,
then, as the Credits page would, sorts each album's credits into Musicians,
Producers, Engineers, Songwriters and Credited (everything else), taking each
group from whichever site, MusicBrainz or Discogs, credits more people in it.
People are matched by their ID on the site, never by name alone. Someone
credited under the same name on the two sites counts as one person only when
MusicBrainz links that artist to the same Discogs artist. It also looks up
the bands in your library on MusicBrainz, so a credited person who is a
member of one of them links to that band's albums.

It writes nothing to the iPod and changes none of your files. Artist lookups
are kept with the saved releases (ids\\releases), so a second run is quick.
Results go to "Link dry run report.txt" beside this file.

Usage:
  python ids.py            first, if it hasn't been run
  python link_dryrun.py
"""
from __future__ import annotations

import re, statistics, sys, threading, time, unicodedata
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:
    import ids
    import artist_bios as ab
except ModuleNotFoundError as e:
    print(f"Missing something: {e}")
    print("Put this file next to ids.py and artist_bios.py.")
    sys.exit(1)

REPORT = HERE / "Link dry run report.txt"
VARIOUS_DC = {194, 355}                 # Discogs "Various", "Unknown Artist"
MEMBER_TYPES = {"member of band", "is person", "collaboration", "subgroup"}


# ---------------------------------------------------------------- fetching
def fetch(site, kind, key, url, params=None):
    """A saved release or artist, or fetched and saved."""
    data = ids.saved_release(kind, key)
    if data is None:
        data = site.get(url, params)
        ids.save_release(kind, key, data)
    return data

def mb_release(mb, rid):
    return fetch(mb, "mbrel", rid, f"{ids.MB}release/{rid}", {"inc": ids.LOOKUP_INC, "fmt": "json"})

def mb_artist(mb, aid):
    return fetch(mb, "mbart", aid, f"{ids.MB}artist/{aid}", {"inc": "url-rels+artist-rels", "fmt": "json"})

def dc_release(dc, rid):
    return fetch(dc, "dcrel", rid, f"{ids.DISCOGS}releases/{rid}")


# ---------------------------------------------------------------- credits
def fold(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).casefold()
    s = re.sub(r"\s*\(\d+\)$", "", s)                  # Discogs "Tom Smith (2)"
    s = s.replace("&", "and")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()

def mb_people(rel):
    """[(pid, name, shown_as, note, role, group, track or None)], songwriters
    included: MusicBrainz credits them on the song (the work), not the recording."""
    out = []
    def add(rels, track):
        for r in rels or []:
            if r.get("target-type") == "work":
                add((r.get("work") or {}).get("relations"), track)
                continue
            if r.get("target-type") != "artist":
                continue
            a = r.get("artist") or {}
            if not a.get("id"):
                continue
            attrs = ", ".join(sorted(r.get("attributes") or []))
            role = r.get("type", "") + (f" ({attrs})" if attrs else "")
            out.append((("mb", a["id"]), a.get("name", ""), r.get("target-credit") or a.get("name", ""),
                        a.get("disambiguation", ""), role, ids.mb_group(r.get("type")), track))
    add(rel.get("relations"), None)
    for medium in rel.get("media") or []:
        for t in medium.get("tracks") or []:
            rec = t.get("recording") or {}
            add(rec.get("relations"), t.get("title") or rec.get("title"))
    return out

def dc_people(rel):
    out = []
    def add(people, track):
        for a in people or []:
            if not a.get("id") or a["id"] in VARIOUS_DC:
                continue
            for role in re.split(r",\s*(?![^\[]*\])", a.get("role") or ""):
                role = role.strip()
                if role:
                    out.append((("dc", a["id"]), a.get("name", ""), a.get("anv") or a.get("name", ""),
                                "", role, ids.dc_group(role),
                                track or (f"tracks {a['tracks']}" if a.get("tracks") else None)))
    add(rel.get("extraartists"), None)
    for t in rel.get("tracklist") or []:
        add(t.get("extraartists"), t.get("title"))
    return out

def discogs_artist_ids(mb_artist_json):
    out = set()
    for r in (mb_artist_json or {}).get("relations") or []:
        m = re.search(r"discogs\.com/artist/(\d+)", ((r.get("url") or {}).get("resource") or ""))
        if m:
            out.add(("dc", int(m.group(1))))
    return out


# ---------------------------------------------------------------- union-find
class Same:
    def __init__(self):
        self.up = {}
    def find(self, x):
        self.up.setdefault(x, x)
        while self.up[x] != x:
            self.up[x] = self.up[self.up[x]]
            x = self.up[x]
        return x
    def join(self, a, b):
        a, b = self.find(a), self.find(b)
        if a != b:
            self.up[max(a, b)] = min(a, b)
            return True
        return False


# ---------------------------------------------------------------- the run
def album_artist(key):
    """The album artist as your tags give it: the key is "<album artist> - <album>"."""
    return key.split(" - ", 1)[0]

def load_records():
    recs = {}
    for path in sorted(ids.CACHE.glob("*.json")):
        rec = ab.load_json(path)
        if rec and rec.get("key"):
            recs[rec["key"]] = rec
    return recs

def main():
    records = load_records()
    if not records:
        print(f"Nothing identified yet in {ids.CACHE}. Run ids.py first.")
        return 1
    token = ab.settings().get("discogs token")
    mb = ids.Site(1.1)
    dc = ids.Site(1.1, {"Authorization": f"Discogs token={token}"}) if token else None
    albums = sorted(records)
    mb_ids = {k: (records[k].get("mb") or {}).get("id") for k in albums}
    dc_ids = {k: (records[k].get("discogs") or {}).get("id") for k in albums}
    lib_artists = sorted({a["id"] for k in albums for a in (records[k].get("mb") or {}).get("artists") or []
                          if a.get("id") and a["id"] != ids.VARIOUS})
    print(f"{len(albums)} albums: {sum(1 for v in mb_ids.values() if v)} on MusicBrainz, "
          f"{sum(1 for v in dc_ids.values() if v)} on Discogs, {len(lib_artists)} library artists on MusicBrainz.")
    print("Releases saved by ids.py are reused; only artists are looked up (kept for next time).")

    mbrel, dcrel, mbart = {}, {}, {}
    progress = {"mb": 0, "dc": 0, "art": 0}
    def run_mb():
        for k in albums:
            if mb_ids[k]:
                mbrel[k] = mb_release(mb, mb_ids[k])
            progress["mb"] += 1
        for a in lib_artists:
            mbart[a] = mb_artist(mb, a)
            progress["art"] += 1
    def run_dc():
        for k in albums:
            if dc and dc_ids[k]:
                dcrel[k] = dc_release(dc, dc_ids[k])
            progress["dc"] += 1
    threads = [threading.Thread(target=run_mb, daemon=True), threading.Thread(target=run_dc, daemon=True)]
    for t in threads:
        t.start()
    try:
        while any(t.is_alive() for t in threads):
            time.sleep(2)
            print(f"\r  releases {progress['mb']}/{len(albums)}  library artists {progress['art']}/{len(lib_artists)}"
                  f"   ({mb.count + (dc.count if dc else 0)} requests)  ", end="", flush=True)
    except KeyboardInterrupt:
        print("\nStopped. What was fetched is kept; run again to carry on.")
        return 1
    print()

    # -- each album's credits, each group from the source that credits more people in it
    credits, chosen = {}, defaultdict(int)
    for k in albums:
        m = mb_people(mbrel[k]) if mbrel.get(k) else []
        d = dc_people(dcrel[k]) if dcrel.get(k) else []
        rows = []
        for group in ids.GROUPS:
            ms = [r for r in m if r[5] == group]
            ds = [r for r in d if r[5] == group]
            n_m, n_d = len({(r[0], r[4]) for r in ms}), len({(r[0], r[4]) for r in ds})
            if not n_m and not n_d:
                continue
            src, pick = ("MusicBrainz", ms) if n_m >= n_d else ("Discogs", ds)
            chosen[(group, src)] += 1
            rows += [r + (src,) for r in pick]
        credits[k] = rows

    # -- who is the release artist of what (MusicBrainz and Discogs IDs, from ids.py)
    release_artist_of = defaultdict(set)
    for k in albums:
        for a in (records[k].get("mb") or {}).get("artists") or []:
            if a.get("id") and a["id"] != ids.VARIOUS:
                release_artist_of[("mb", a["id"])].add(k)
        for a in (records[k].get("discogs") or {}).get("artists") or []:
            if a.get("id") and a["id"] not in VARIOUS_DC:
                release_artist_of[("dc", a["id"])].add(k)

    # -- library bands' members, and library artists' Discogs IDs
    same = Same()
    member_of = defaultdict(set)
    for a, data in mbart.items():
        for d in discogs_artist_ids(data):
            same.join(("mb", a), d)
        for r in (data or {}).get("relations") or []:
            if r.get("target-type") == "artist" and r.get("type") in MEMBER_TYPES and (r.get("artist") or {}).get("id"):
                member_of[("mb", r["artist"]["id"])].add(("mb", a))

    # -- same name on both sites: confirmed only through MusicBrainz's Discogs link
    names, shown, notes = defaultdict(set), defaultdict(set), {}
    for k, rows in credits.items():
        for pid, name, sh, note, *_ in rows:
            names[fold(name)].add(pid)
            shown[pid].update({name, sh})
            if note:
                notes[pid] = note
    candidates = {n: ps for n, ps in names.items()
                  if any(p[0] == "mb" for p in ps) and any(p[0] == "dc" for p in ps)}
    to_check = sorted({p[1] for ps in candidates.values() for p in ps if p[0] == "mb"} - set(mbart))
    print(f"Checking {len(to_check)} people credited under the same name on both sites...")
    for i, aid in enumerate(to_check, 1):
        mbart[aid] = mb_artist(mb, aid)
        print(f"\r  {i}/{len(to_check)}", end="", flush=True)
    print()
    confirmed, unconfirmed = [], []
    for n, ps in sorted(candidates.items()):
        mbs = [p for p in ps if p[0] == "mb"]
        dcs = [p for p in ps if p[0] == "dc"]
        linked = set()
        for p in mbs:
            for d in discogs_artist_ids(mbart.get(p[1])) & set(dcs):
                same.join(p, d)
                linked.add(d)
                confirmed.append((n, p, d))
        unconfirmed += [(n, d, mbs) for d in dcs if d not in linked]

    # -- appearances per person, after joining
    appear = defaultdict(lambda: defaultdict(set))     # root -> album -> {(group, role text)}
    for k, rows in credits.items():
        for pid, name, sh, note, role, group, track, src in rows:
            appear[same.find(pid)][k].add((group, role + (f" on \"{track}\"" if track else "")))
    for pid, ks in release_artist_of.items():
        r = same.find(pid)
        if r in appear:
            for k in ks:
                appear[r][k].add(("Artist", "the album's artist"))
    for person, bands in member_of.items():
        r = same.find(person)
        if r in appear:
            for b in bands:
                for k in release_artist_of.get(b, ()):
                    appear[r][k].add(("Member", "member of " + album_artist(k)))
    members_of_root = defaultdict(set)
    for p in list(same.up):
        members_of_root[same.find(p)].add(p)

    def label(root):
        ns = set()
        for p in members_of_root.get(root, {root}):
            ns |= shown.get(p, set())
        ns.discard("")
        return sorted(ns, key=len)[0] if ns else str(root)

    def select_list(k, cross_only, skip_credited):
        out, seen = [], set()
        for pid, name, sh, note, role, group, *_r in credits[k]:
            root = same.find(pid)
            if root in seen or (skip_credited and group == "Credited"):
                continue
            seen.add(root)
            here = album_artist(k).casefold()
            others = [o for o in appear[root] if o != k and (not cross_only or album_artist(o).casefold() != here)]
            if others:
                out.append((root, group, others))
        return out

    variants = {"everyone, any other album": (False, False),
                "everyone, other artists only": (True, False),
                "without Credited, other artists only": (True, True)}
    lines = []
    add = lines.append
    add(f"Link dry run, {time.strftime('%d %b %Y %H:%M')}")
    add("")
    add(f"Albums with credits: {sum(1 for r in credits.values() if r)} of {len(albums)}")
    add(f"Different people credited: {len({same.find(r[0]) for rows in credits.values() for r in rows})}")
    add("")
    add("Albums with each group, and the site it came from")
    for g in ids.GROUPS:
        add(f"  {g:12} MusicBrainz {chosen[(g, 'MusicBrainz')]:3}   Discogs {chosen[(g, 'Discogs')]:3}")
    add("")
    add("How many albums would have a Select list, and how long it would be")
    for name, (cross, skip) in variants.items():
        nz = [len(x) for x in (select_list(k, cross, skip) for k in albums if credits[k]) if x]
        add(f"  {name:38} {len(nz):3} albums" + (f", median {statistics.median(nz):.0f} names, most {max(nz)}" if nz else ""))
    by_group = defaultdict(set)
    for k in albums:
        for root, group, _ in select_list(k, True, False):
            by_group[group].add(root)
    add("People who link to another artist's album, by group: "
        + ", ".join(f"{g} {len(by_group[g])}" for g in ids.GROUPS))
    linked_people = set().union(*by_group.values()) if by_group else set()
    add("")
    add(f"Same name on both sites: {len(candidates)} names")
    add(f"  confirmed the same person (MusicBrainz links to that Discogs artist): {len(confirmed)}")
    add(f"  not confirmed, kept apart: {len(unconfirmed)}")
    add("")

    clashes = []
    for n, ps in names.items():
        roots = {same.find(p) for p in ps}
        if len(roots) > 1:
            by = {r: sorted(appear[r]) for r in roots}
            if sum(1 for v in by.values() if v) > 1:
                clashes.append((n, by))
    add(f"Names shared by different people in your library (name matching would join these): {len(clashes)}")
    for n, by in sorted(clashes):
        add(f"  {n}")
        for r, ks in by.items():
            idl = ", ".join(f"{p[0]}:{p[1]}" for p in sorted(members_of_root.get(r, {r}), key=str))
            note = next((notes[p] for p in members_of_root.get(r, {r}) if p in notes), "")
            add(f"    [{idl}]{' (' + note + ')' if note else ''}: " + "; ".join(ks[:4]) + (" ..." if len(ks) > 4 else ""))
    add("")
    add("Everyone who links to another artist's album")
    for root in sorted(linked_people, key=lambda r: (-len(appear[r]), label(r).casefold())):
        idl = ", ".join(f"{p[0]}:{p[1]}" for p in sorted(members_of_root.get(root, {root}), key=str))
        add(f"  {label(root)}   [{idl}]")
        for k in sorted(appear[root]):
            hows = sorted({f"{g}: {x}" for g, x in appear[root][k]})
            add(f"      {k}: " + "; ".join(hows[:3]) + (f" (+{len(hows) - 3} more)" if len(hows) > 3 else ""))
    add("")
    add("Same name on both sites, not confirmed (kept apart)")
    for n, d, mbs in unconfirmed:
        add(f"  {n}: discogs:{d[1]} vs " + ", ".join(f"mb:{p[1]}" for p in mbs))
    size = sum(40 + 60 * len(o) for k in albums for _, _, o in select_list(k, True, False))
    add("")
    add(f"Rough size of the #links sections across all credits files: {size / 1024:.0f} KB")
    add(f"Requests made this run: MusicBrainz {mb.count}, Discogs {dc.count if dc else 0}")

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:24]))
    print(f"\nFull report: {REPORT}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
