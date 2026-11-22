# CLAUDE.md

Read `DEVELOPING.md` before changing anything: it describes every script, the
order they run in, where the text comes from, and the file formats the iPod
reads. `README.md` is for people using the scripts.

Rules for this repository:

- **The files written onto the iPod are the firmware's input.** A change to
  what a file says needs the matching change to PodBox's Liner Notes viewer
  (Polytracker/podbox, `apps-ipod/viewers/artist_bio/`) and its
  `docs/podbox/artwork-guide.md`. Say so before making it.
- **Never commit a key.** `iPod Liner Notes settings.txt` is committed with
  `discogs token` and `deepl key` empty; the owner's copy on their PC holds
  the real ones. Never print them either.
- **Never delete anything on the iPod.** The scripts write and replace
  files; they don't remove them.
- **Be a polite client:** keep the request spacing and retries described in
  `DEVELOPING.md`, and the `User-Agent` naming this project.
- **Run `python -m pytest -q`** before committing; add a test for any change
  to what's written onto the iPod.
- **Commits** are authored as `Polytracker <Polytracker@users.noreply.github.com>`.
- **The owner is a product owner, not a programmer.** Explain changes by
  what they do on the iPod and what they cost, ask before changing behaviour,
  and give commands to run as one PowerShell block.
