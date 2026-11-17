"""
Offline checks for track_notes.py: finding an album's songs on Wikidata,
matching them to your tracks, and which introductions are used.

  python -m unittest discover tests
"""
import os, sys, tempfile, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
os.environ.setdefault("XDG_CONFIG_HOME", tempfile.mkdtemp())

import artist_bios as ab  # noqa: E402
import track_notes as tn  # noqa: E402


class Reply:
    def __init__(self, data):
        self.data, self.ok, self.status_code, self.headers = data, True, 200, {}
    def json(self):
        return self.data


class FakeSession:
    def __init__(self, answer):
        self.answer, self.asked = answer, []
    def get(self, url, params=None, headers=None, timeout=None):
        self.asked.append(params)
        return Reply(self.answer(url, params or {}))


INTRO = ("Karma Police is a song by the English rock band Radiohead, released as the second single from "
         "their third album, OK Computer (1997). It was written by the band members and produced by Nigel "
         "Godrich. The song features a piano and guitar arrangement and was accompanied by a music video "
         "directed by Jonathan Glazer, in which a man is pursued by a car. It reached number eight.")


class Songs(unittest.TestCase):
    def setUp(self):
        ab.time.sleep = lambda s: None

    def test_tracklist_and_part_of(self):
        def answer(url, p):
            if p.get("action") == "wbgetentities" and p.get("props") == "claims":
                return {"entities": {"Q1": {"claims": {"P658": [
                    {"mainsnak": {"datavalue": {"value": {"id": "Q10"}}}}]}}}}
            if p.get("list") == "search":
                return {"query": {"search": [{"title": "Q11"}, {"title": "Q10"}]}}
            return {"entities": {"Q10": {"sitelinks": {"enwiki": {"title": "Karma Police"}},
                                         "labels": {"en": {"value": "Karma Police"}}},
                                 "Q11": {"sitelinks": {}, "labels": {"en": {"value": "Airbag"}}},
                                 "Q12": {"sitelinks": {}}}}
        s = FakeSession(answer)
        items = tn.album_songs("Q1", s)
        self.assertEqual(items, ["Q10", "Q11"])
        self.assertEqual(tn.english_titles(items, s), {"Q10": ("Karma Police", "Karma Police"),
                                                      "Q11": ("", "Airbag")})

    def test_match_by_title_and_disambiguation(self):
        tracks = [[1, 1, "Airbag"], [1, 6, "Karma Police"], [1, 11, "Lucky"]]
        songs = {"Q10": ("Karma Police", "Karma Police"), "Q12": ("Lucky (Radiohead song)", "Lucky"),
                 "Q13": ("Creep (Radiohead song)", "Creep")}
        songs["Q14"] = ("", "Airbag")
        self.assertEqual(tn.match_tracks(tracks, songs), {0: "", 1: "Karma Police", 2: "Lucky (Radiohead song)"})


class Checks(unittest.TestCase):
    def test_usable(self):
        self.assertEqual(tn.usable(INTRO, "Radiohead"), "")
        self.assertIn("too short", tn.usable("Short.", "Radiohead"))
        dre = ('"Still D.R.E." is a song by American rapper and record producer Dr. Dre, featuring Snoop Dogg. '
               + "x" * 300)
        self.assertEqual(tn.usable(dre, "Dr. Dre"), "")
        linus = '"Linus and Lucy" is a jazz piece composed by Vince Guaraldi. ' + "x" * 300
        self.assertEqual(tn.usable(linus, "Vince Guaraldi Trio"), "")
        money = '"Money Folder" is a song by American hip hop duo Madvillain, from their album Madvillainy. ' + "x" * 300
        self.assertEqual(tn.usable(money, "MF DOOM", album="Madvillainy"), "")
        self.assertIn("cover", tn.usable(money, "MF DOOM", album="Operation: Doomsday"))
        self.assertIn("other meanings", tn.usable("Lucky may refer to: " + "x" * 400, "Radiohead"))
        cover = INTRO.replace("the English rock band Radiohead", "the American singer Someone Else")
        self.assertIn("cover", tn.usable(cover + " Radiohead covered it.", "Radiohead"))

    def test_page_text(self):
        t = tn.page_text("Karma Police", "6", "OK Computer", INTRO, "Karma Police", "2026-11-17")
        lines = t.splitlines()
        self.assertEqual(lines[:2], ["#title\tKarma Police", "#facts\tTrack 6, OK Computer"])
        self.assertTrue(lines[3].startswith("Karma Police is a song"))
        self.assertEqual(lines[-1], "#sources\tFrom the introduction to the Wikipedia article "
                                    "\"Karma Police\", CC BY-SA 4.0, retrieved 17 Nov 2026")


class FillOut(unittest.TestCase):
    def test_short_lead_gets_background_paragraph(self):
        lead = '"War Pigs" is an anti-war song by the English heavy metal band Black Sabbath.'
        article = (lead + "\n\n== Track listing ==\nSide one, a very long list of tracks that should never be used here.\n"
                   "== Background ==\nThe song was first called Walpurgis, after the witches' sabbath, and its lyrics "
                   "were written by Geezer Butler about the Vietnam War and the politicians who sent others to fight.\n")
        tn.wiki_article = lambda title, session: (article, "")
        text, part = tn.fill_out(lead, "War Pigs", None)
        self.assertEqual(part, "excerpts")
        self.assertIn("Walpurgis", text)
        self.assertNotIn("Side one", text)
        self.assertEqual(tn.fill_out("x" * 400, "A", None), ("x" * 400, "introduction"))


class Continue(unittest.TestCase):
    def test_summaries_follow_continue(self):
        import liner_notes as ln
        ab.time.sleep = lambda s: None
        def answer(url, p):
            if "excontinue" not in p:
                return {"query": {"pages": [{"title": "A", "extract": "a" * 50}, {"title": "B"}]},
                        "continue": {"excontinue": 1, "continue": "||"}}
            return {"query": {"pages": [{"title": "A"}, {"title": "B", "extract": "b" * 50}]}}
        got = ln.wiki_summaries(["A", "B"], FakeSession(answer))
        self.assertEqual(sorted(got), ["A", "B"])


class LastFm(unittest.TestCase):
    def setUp(self):
        tn.time.sleep = lambda s: None

    def answer(self, artist, album, text):
        return lambda url, p: {"track": {"artist": {"name": artist}, "album": {"title": album},
                                         "wiki": {"content": text + ' <a href="https://www.last.fm/music/x">Read more on Last.fm</a>. '
                                                  "User-contributed text is available under the Creative Commons"}}}

    def test_used_when_on_your_album_or_by_your_artist(self):
        s = FakeSession(self.answer("Radiohead", "OK Computer", "Airbag is the opening track."))
        text, why = tn.lastfm_track("Radiohead", "Airbag", "OK Computer", s, "key", mbid="rec1")
        self.assertEqual((text, why), ("Airbag is the opening track.", ""))
        self.assertEqual(s.asked[0]["mbid"], "rec1")

    def test_same_title_by_someone_else_is_not_used(self):
        s = FakeSession(self.answer("Someone Else", "Another Album", "A different Airbag."))
        self.assertEqual(tn.lastfm_track("Radiohead", "Airbag", "OK Computer", s, "key")[0], "")

    def test_credit(self):
        t = tn.page_text("Airbag", "1", "OK Computer", "x" * 10, None, "2026-11-17", source="lastfm")
        self.assertEqual(t.splitlines()[-1], "#sources\tFrom Last.fm, CC BY-SA, retrieved 17 Nov 2026")
