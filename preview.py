"""
preview.py -- pictures of the Credits pages as the iPod will draw them.

It lays out each credits file with the iPod's own fonts (the .fnt files
from its .rockbox\\fonts folder), glyph for glyph, on the album's blurred
cover, and saves:

  credits preview\\<Album Artist> - <Album>.png   the whole page, top to bottom
  credits preview\\Other Appearances\\...png     its Select list, and the first person's
  credits preview\\Credits preview report.txt      characters the fonts can't
                                                 draw, the longest pages, and
                                                 rows too long for the screen

It's a quick check before the firmware exists, and later a second opinion
beside the simulator: if the two disagree, one of them is wrong. The layout
numbers (LAYOUT below) are the ones the viewer uses; change them there and
in the viewer together.

Usage:
  python preview.py                                 every page in "credits test"
  python preview.py --pages "G:\\Artwork\\Credits"   pages on the iPod
  python preview.py --only "Radiohead - OK Computer"
"""
from __future__ import annotations

import argparse, io, re, struct, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

try:
    from PIL import Image, ImageFilter
    import artist_bios as ab
    import ids
except ModuleNotFoundError as e:
    print(f"Missing something: {e}  (pip install pillow)")
    sys.exit(1)

# The viewer's layout, in pixels. Keep in step with the firmware.
LAYOUT = {
    "width": 320, "height": 240,
    "margin": 10,                 # left and right; text is 300 px wide
    "strip": 20,                  # the page names, pinned at the top
    "strip_gap": 16,              # between page names
    "fonts": {"title": "26-noto-sans-medium", "small": "14-noto-sans",
              "body": "18-noto-sans", "head": "18-noto-sans-bold"},
    "hang": 12,                   # a person's row that wraps carries on indented, so it can't pass for the next person
    "dim": 170,                   # grey text: the background blended 170/255 toward the text colour
    "pages": ("Bio", "Album", "Track", "Credits"),
}


# ---------------------------------------------------------------- PodBox fonts
class Font:
    """A PodBox .fnt (RB12): 4-bit anti-aliased glyphs, rows packed two
    pixels to a byte, low nibble first; 0 is solid, 15 is clear."""
    def __init__(self, path):
        d = Path(path).read_bytes()
        if d[:4] != b"RB12":
            raise ValueError(f"{path} isn't a PodBox font")
        self.maxwidth, self.height, self.ascent, self.depth = struct.unpack_from("<4H", d, 4)
        self.first, self.default, self.size, nbits, noff, nwid = struct.unpack_from("<6I", d, 12)
        self.bits = d[36:36 + nbits]
        p = 36 + nbits
        if nbits < 0xFFDB:
            p, fmt, step = (p + 1) & ~1, "<H", 2
        else:
            p, fmt, step = (p + 3) & ~3, "<I", 4
        self.offsets = [struct.unpack_from(fmt, d, p + i * step)[0] for i in range(noff)]
        p += noff * step
        self.widths = d[p:p + nwid]
        self._cache = {}

    def _index(self, ch):
        c = ord(ch)
        return c - self.first if self.first <= c < self.first + self.size else None

    def has(self, ch):
        """Whether the font draws this character itself, not its stand-in."""
        i = self._index(ch)
        if i is None:
            return False
        if not self.offsets:
            return True
        d = self.default - self.first
        return i == d or self.offsets[i] != self.offsets[d] or self.widths[i] != self.widths[d]

    def width(self, ch):
        i = self._index(ch)
        if i is None:
            i = self.default - self.first
        return self.widths[i] if self.widths else self.maxwidth

    def text_width(self, s):
        return sum(self.width(c) for c in s)

    def glyph(self, ch):
        """The glyph as an 8-bit coverage mask (255 = ink)."""
        i = self._index(ch)
        if i is None:
            i = self.default - self.first
        if i in self._cache:
            return self._cache[i]
        w = self.widths[i] if self.widths else self.maxwidth
        start = self.offsets[i] if self.offsets else i * ((self.height * w + 1) // 2)
        px = bytearray(w * self.height)
        for n in range(w * self.height):
            b = self.bits[start + n // 2] if start + n // 2 < len(self.bits) else 0xff
            v = (b >> 4) if n & 1 else (b & 0x0f)
            px[n] = (15 - v) * 17
        mask = Image.frombytes("L", (w, self.height), bytes(px)) if w else None
        self._cache[i] = mask
        return mask

    def draw(self, img, x, y, s, colour):
        for ch in s:
            m = self.glyph(ch)
            if m is not None:
                img.paste(colour, (x, y), m)
            x += self.width(ch)
        return x


def wrap(font, text, width):
    """Lines of text no wider than width, broken at spaces like the viewer;
    a word too long for a line is broken where it has to be."""
    lines, line = [], ""
    for word in text.split(" "):
        trial = f"{line} {word}" if line else word
        if font.text_width(trial) <= width:
            line = trial
            continue
        if line:
            lines.append(line)
        while font.text_width(word) > width:
            cut = len(word)
            while cut > 1 and font.text_width(word[:cut]) > width:
                cut -= 1
            lines.append(word[:cut])
            word = word[cut:]
        line = word
    lines.append(line)
    return lines


# ---------------------------------------------------------------- the page
def read_page(text):
    """(facts lines, status, [(group, [rows])], sources, people in #links)."""
    facts, status, groups, sources, linked = [], "", [], "", 0
    in_links = False
    for line in text.splitlines():
        if in_links:
            linked += line.startswith("P\t")
            continue
        if line.startswith("#facts\t"):
            facts.append(line[7:])
        elif line.startswith("#status\t"):
            status = line[8:]
        elif line.startswith("#sources\t"):
            sources = line[9:]
        elif line == "#links":
            in_links = True
        elif line.startswith("## "):
            groups.append((line[3:], []))
        elif line and groups:
            name, _, roles = line.partition("\t")
            groups[-1][1].append((name, roles))
    return facts, status, groups, sources, linked

def background(cover_bytes, height):
    """The blurred, darkened cover the viewer draws behind the text (an
    approximation of Scrim's blur12 + scrim); plain dark grey without one."""
    W = LAYOUT["width"]
    if not cover_bytes:
        return Image.new("RGB", (W, height), (40, 44, 50))
    with Image.open(io.BytesIO(cover_bytes)) as im:
        art = im.convert("RGB").resize((W, W), Image.LANCZOS)
    art = art.filter(ImageFilter.GaussianBlur(12))
    art = Image.blend(art, Image.new("RGB", art.size, (0, 0, 0)), 0.45)
    art = art.crop((0, 40, W, 40 + LAYOUT["height"]))             # placed at y = -40, as Scrim does
    bg = Image.new("RGB", (W, height))
    for y in range(0, height, LAYOUT["height"]):                 # the background stays put as text scrolls;
        bg.paste(art, (0, y))                                    # tiling stands in for that on a tall picture
    return bg

def mix(a, b, n):
    return tuple(round(x + (y - x) * n / 255) for x, y in zip(a, b))

def layout(fonts, title, page):
    """[(font, text, x, y, dim)] for the page from y = 0 (under the strip), and its height."""
    facts, status, groups, sources, _ = read_page(page)
    W, M = LAYOUT["width"], LAYOUT["margin"]
    width = W - 2 * M
    body_h = fonts["body"].height
    out, y = [], 0
    for line in wrap(fonts["title"], title, width):
        out.append(("title", line, M, y, False))
        y += fonts["title"].height
    for t in facts + ([status] if status else []):
        for line in wrap(fonts["small"], t, width):
            out.append(("small", line, M, y, True))
            y += fonts["small"].height
    y += body_h // 2 + 4
    for group, rows in groups:
        out.append(("head", group, M, y, False))
        y += fonts["head"].height + body_h // 4
        for name, roles in rows:
            y = person_row(fonts, out, name, roles, y)
        y += body_h // 2
    if sources:
        for line in wrap(fonts["small"], sources, width):
            out.append(("small", line, M, y, True))
            y += fonts["small"].height
    return out, y + M

def row_units(name, roles):
    """A person's row as the pieces it may wrap between: words of "Name –
    Role, Role" in the body font, and each set of track numbers ("[3, 9]"
    in the file, small and grey) joined to the word before it, so numbers
    never start a line on their own."""
    units = [[("body", w)] for w in (f"{name} \u2013" if roles else name).split(" ")]
    for part in re.split(r"(\[[^\]]*\])", roles):
        if part.startswith("["):
            units[-1].append(("small", part[1:-1]))
        else:
            units += [[("body", w)] for w in part.split(" ") if w]
    return units

def person_row(fonts, out, name, roles, y):
    """Lays out one person's row from y, wrapping between pieces with the
    carried-on lines indented; returns the y below it."""
    W, M, hang = LAYOUT["width"], LAYOUT["margin"], LAYOUT["hang"]
    body = fonts["body"]

    def width(unit):
        return sum(fonts[f].text_width(t) for f, t in unit) + \
               sum(fonts[f].text_width(" ") for f, _ in unit[1:])

    x = M
    for n, unit in enumerate(row_units(name, roles)):
        gap = 0 if n == 0 else body.text_width(" ")
        if n and x + gap + width(unit) > W - M:
            y += body.height
            x, gap = M + hang, 0
        x += gap
        for k, (f, text) in enumerate(unit):
            font = fonts[f]
            if k:
                x += font.text_width(" ")
            out.append((f, text, x, y + body.ascent - font.ascent, f == "small"))
            x += font.text_width(text)
    return y + body.height

def render(fonts, title, page, cover):
    items, h = layout(fonts, title, page)
    S = LAYOUT["strip"]
    img = background(cover, max(h + S, LAYOUT["height"]))
    base = img.getpixel((LAYOUT["width"] // 2, LAYOUT["height"] // 2))
    fg = (255, 255, 255)
    dim = mix(base, fg, LAYOUT["dim"])
    for font, text, x, y, is_dim in items:
        fonts[font].draw(img, x, y + S, text, dim if is_dim else fg)
    # the page names, centred in the strip; the current one bright
    small = fonts["small"]
    names = LAYOUT["pages"]
    total = sum(small.text_width(n) for n in names) + LAYOUT["strip_gap"] * (len(names) - 1)
    x = (LAYOUT["width"] - total) // 2
    ty = (S - small.height) // 2
    for n in names:
        x = small.draw(img, x, ty, n, fg if n == "Credits" else dim) + LAYOUT["strip_gap"]
    return img, items


# ---------------------------------------------------------------- Other Appearances
def read_links(text):
    """[(name, roles, [(kind, artist, album, track or "", role)])] from #links."""
    people, on = [], False
    for line in text.splitlines():
        if line == "#links":
            on = True
        elif on and line.startswith("P\t"):
            _, name, roles = (line.split("\t") + [""])[:3]
            people.append((name, roles, []))
        elif on and people and line[:2] in ("A\t", "T\t"):
            f = line.split("\t")
            if f[0] == "A":
                people[-1][2].append(("A", f[1], f[2], "", f[3] if len(f) > 3 else ""))
            else:
                people[-1][2].append(("T", f[1], f[2], f[3], f[4] if len(f) > 4 else ""))
    return people

def list_screen(fonts, bg, title, rows, clock="12:17 AM"):
    """A Scrim list: the 35 px title bar, then 30 px rows from y = 46, the
    selected (first) row marked by a thin line at its left. A row is
    (main text, grey text after it)."""
    W = LAYOUT["width"]
    img = bg.copy()
    base = img.getpixel((W // 2, 120))
    bar = tuple(int(c * 0.55) for c in base)
    img.paste(bar, (0, 0, W, 35))
    fg = (255, 255, 255)
    dim = mix(base, fg, LAYOUT["dim"])
    head, body = fonts["head"], fonts["body"]
    head.draw(img, 10, 8, title, fg)
    body.draw(img, W - 10 - body.text_width(clock), 8, clock, fg)
    y = 46
    for n, (main, extra) in enumerate(rows[:6]):
        x = 20
        if n == 0:
            img.paste((230, 230, 230), (10, y + 4, 13, y + 26))
        ty = y + (30 - body.height) // 2
        x = body.draw(img, x, ty, main, fg)
        if extra:
            body.draw(img, x, ty, f" · {extra}", dim)
        y += 30
    return img

def how_many(rows):
    """ "1 album", "2 tracks", "1 album, 2 tracks": what a person's row says."""
    a = sum(1 for r in rows if r[0] == "A")
    t = sum(1 for r in rows if r[0] == "T")
    part = lambda n, w: f"{n} {w}{'' if n == 1 else 's'}"
    return ", ".join(x for x in (part(a, "album") if a else "", part(t, "track") if t else "") if x)

def appearances(fonts, bg, text):
    """The people list and the first person's own list, side by side."""
    people = read_links(text)
    if not people:
        return None
    first = list_screen(fonts, bg, "Other Appearances", [(n, how_many(rows)) for n, _, rows in people])
    name, _, rows = people[0]
    second = list_screen(fonts, bg, name, [(f"\u201c{t}\u201d" if k == "T" else alb, art)
                                         for k, art, alb, t, _ in rows])
    W, H = LAYOUT["width"], LAYOUT["height"]
    both = Image.new("RGB", (W * 2 + 10, H), (255, 255, 255))
    both.paste(first, (0, 0))
    both.paste(second, (W + 10, 0))
    return both


# ---------------------------------------------------------------- the run
def main(argv=None):
    conf = ab.settings()
    drive = (conf.get("ipod drive") or "G:").rstrip("\\/")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pages", default=str(HERE / "credits test" / "Artwork" / "Credits"),
                    help="the folder of credits files (default: the credits test folder)")
    ap.add_argument("--fonts", default=f"{drive}\\.rockbox\\fonts",
                    help="the iPod's fonts folder (default: from the settings file)")
    ap.add_argument("--out", default=str(HERE / "credits preview"))
    ap.add_argument("--only", action="append", default=[], help='"Artist - Album" (can be given more than once)')
    args = ap.parse_args(argv)

    try:
        fonts = {k: Font(Path(args.fonts) / f"{v}.fnt") for k, v in LAYOUT["fonts"].items()}
    except (OSError, ValueError) as e:
        print(f"Can't read the iPod's fonts: {e}\nIs the iPod plugged in? Or give --fonts <folder>.")
        return 1
    pages = sorted(Path(args.pages).glob("*.txt"))
    if not pages:
        print(f"No credits files in {args.pages}. Run credits.py first.")
        return 1
    lib = ids.library().get("albums") or {}
    by_name = {ab.safe_name(k): k for k in lib}
    only = {ab.norm(o) for o in args.only}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    missing, sizes, done = {}, [], 0
    for path in pages:
        key = by_name.get(path.stem, path.stem)
        if only and ab.norm(key) not in only:
            continue
        info = lib.get(key) or {}
        title = info.get("album") or key.split(" - ", 1)[-1]
        text = path.read_text(encoding="utf-8")
        cover = None
        if info.get("folder") and Path(info["folder"]).is_dir():
            try:
                cover = ab.album_cover([Path(info["folder"])])[0]
            except Exception:
                cover = None
        img, items = render(fonts, title, text, cover)
        img.save(out / f"{path.stem}.png")
        apps = appearances(fonts, background(cover, LAYOUT["height"]), text)
        if apps:
            (out / "Other Appearances").mkdir(exist_ok=True)
            apps.save(out / "Other Appearances" / f"{path.stem}.png")
        done += 1
        lost = {c for font, t, *_ in items for c in t if not fonts[font].has(c) and not c.isspace()}
        if lost:
            missing[key] = "".join(sorted(lost))
        screens = (img.height - LAYOUT["strip"]) / (LAYOUT["height"] - LAYOUT["strip"])
        sizes.append((screens, key, read_page(text)[4]))
        print(f"\r  {done} pages drawn", end="", flush=True)
    print()

    sizes.sort(reverse=True)
    report = [f"Credits preview: {done} pages, drawn with the fonts in {args.fonts}.", ""]
    report.append("Characters the fonts can't draw (the iPod shows a stand-in):")
    report += [f"  {k}: {v}" for k, v in sorted(missing.items())] or ["  none"]
    report += ["", "Longest pages, in screens of scrolling (and people in Other Appearances):"]
    report += [f"  {s:4.1f}  {k}  ({n})" for s, k, n in sizes[:15]]
    if sizes:
        report += ["", f"Typical page: {sorted(s for s, _, _ in sizes)[len(sizes) // 2]:.1f} screens."]
    (out / "Credits preview report.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    print(f"\nPictures in {out}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
