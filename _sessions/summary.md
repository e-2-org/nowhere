# Now Here / Nowhere in HTML: session summary

13 October 2026, working with Claude Code on `main`. The same session also worked on Tome, Word Perhect, Adelaide and A House Is Not A Home (see those repositories). The Now Here / Nowhere part of the conversation is in [transcript.md](transcript.md).

## Aim

Port Now Here / Nowhere (Brighid Lowe, technical direction by Peter Moore, produced by e-2) from Flash to HTML:

- CSS animations, so the motion is smooth
- the same font
- as close as possible to the original's timings, speeds and crossfades

During the session Pete also asked for a video of the original as Flash played it, keeping its frame rate and jumpiness.

## What was there

- **`apbl.html`** showed `nowhere.swf` (550×280, 12 fps, 188 frames: 15.67 seconds) centred on a `#3399FF` page. Its last frame runs `getURL("apbl2.html")`.
- **`apbl2.html`** showed `begin.swf` (a 200×40 stage, 10 fps, 2,598 frames: 4 minutes 19.8 seconds) at `WIDTH=101% HEIGHT=100%` with `SCALE=SHOWALL`, on black. With no `stop`, it loops.
- **`apblold.html`** was an older page for `nowhere.swf`.
- **The SWFs** are Flash 1 (FutureSplash era):
  - The text is `DefineText` in an embedded Times New Roman (glyph outlines).
  - There are no tweens: every frame removes each text and places it again with a new matrix and, for fades, a colour transform.
- **Part one:** five texts, fading only. A text fades in from the background colour, crossfades into another, and so on. Text 4 is empty, shown for one frame.
- **Part two:** 41 texts in white on black, in a band at the top of the stage:
  - most scroll across, entering on one side and leaving on the other
  - some hold still
  - a few fade in or out
  - one near the end (char 40) has a negative colour transform

## How it was decoded

- JPEXS FFDec 26.3.0 was downloaded to a scratch folder, not the repo. It's used to:
  - dump each SWF's tags to XML (`-swf2xml`)
  - export each text as SVG (`-format text:svg -export text`)
  - render frames (`-format frame:png -export frame`, with `-zoom` and `-select`)
- From the XML, each run of a text at a depth over consecutive frames becomes a *track*: its matrix and colour transform per frame, and the frame it's removed.
- The scales in the matrices are all within 0.3% of 1, the rounding of Flash's fixed-point numbers. Nothing rotates.

## What was built

**`_scripts/build.py`** writes `index.html` from the two SWFs:

```sh
python3 _scripts/build.py --ffdec /path/to/ffdec-cli.jar
```

- **Glyphs.** Glyphs come from FFDec's text SVGs, one set per movie, because 8 of the shared glyphs differ slightly between the two. Each glyph is named by its outline: FFDec names punctuation per file (`_0`, `_1`), and merging by those names turned semicolons into apostrophes. Each text is a group of `<use>`s of its glyphs, filled with `currentColor`.
- **Tracks.** Each track is a `<use>` of its text, with its own `@keyframes` spanning its movie's whole length:
  - a keyframe at every frame's time, `(frame − 1) / fps`, with `x`, `y` and `color`, interpolated linearly in between
  - where a text was held still and then moved, a hold keyframe at the frame before the move
  - keyframes that lie on the straight line between their neighbours are dropped, which changes nothing
  - `visibility` switches with `steps(1, end)` at the frames a text is placed and removed
- **Colour.** Each frame's colour is the Flash colour transform applied to the text's colour: `c × mult/256 + add`, clamped.
- **Movement.** `x` and `y` are animated rather than `transform`. Chrome hands transform animations to the compositor, which drew the text at the 200×40 stage's own size and enlarged it, blurring it.
- **Scale.** Each track's scale, averaged over the frames it's on screen, is a fixed transform on its own copy of the text.
- **Sequence.**
  - Part one plays once, 550×280 centred on blue.
  - A zero-size element's 15.67-second animation then adds a `part-b` class (the only script).
  - Part two then plays and loops, fitted to the window's width (`SHOWALL`), centred on black.

**`index.html`** is 216 KB, almost all glyph outlines and keyframes.

**`_scripts/video.sh`** makes `video/now-here-nowhere.mp4`:

```sh
sh _scripts/video.sh /path/to/ffdec-cli.jar
```

- **Frames:** FFDec renders every frame. Part one is rendered at 2× (1100×560), padded on `#3399FF`; part two at 9.6× (1920×384), padded on black.
- **Assembly:** ffmpeg converts to 60 fps by holding each frame, 5 video frames for each frame of part one and 6 for each frame of part two. It joins the parts and encodes H.264 (CRF 16, `-tune animation`).
- **Result:** 1920×1080, 16,528 frames, 4 minutes 35.5 seconds, 9.9 MB. Part two plays once.

**README:** the viewing requirement is now "A modern browser", with a section on the port and the video.

**Removed:** `apbl.html`, `apbl2.html` and `apblold.html`, with `git rm`.

## Checks

- **Frames against the original.** Reference frames were rendered by FFDec: 12 from part one at 1×, and 17 from part two at 4× (800×160). They cover fades, the one-frame flash, scrolling, holds and the inverted text. The page was captured at the same moments, with every animation paused at that frame's time.
  - Part one is within 0.5% RMSE throughout.
  - Part two was 2–3% at first, with wrong semicolons and soft text. After the glyph naming, `x`/`y` and fixed scales it is about 0.2–2%, which is anti-aliasing level. Side by side, the pictures look identical.
- **Real time.** In Chrome at 1920×1080, part two started 15.669 seconds in (15.67 expected), and its stage is 1920×384 at y = 348. There were no script errors.
- **Video.** It has 16,528 frames (188 × 5 + 2,598 × 6). Video frames 0, 304, 524, 939, 940, 6000, 9001 and 16527 each match the Flash frame they should show, to within compression noise. Running `video.sh` again gave the same result.

## Status

Uncommitted on `main`:

- new: `index.html`, `_scripts/build.py`, `_scripts/video.sh`, `video/now-here-nowhere.mp4`, these notes
- changed: `README.md`
- deleted: the three old pages (staged)

To note:

- Links to `apbl.html` or `apbl2.html` will now get a 404. They need to point at `index.html`, or small redirect pages could be added.
- `nowhere.gif`, the old no-plugin fallback image, and `ws_ftp.log` were left as they were.
- Rebuilding the page or the video needs FFDec downloaded again; the build script needs Python 3 and Java, and the video also needs ffmpeg.
- In the video, part one is shown at 2× so that it isn't tiny on a 1080p screen; the page shows it at its original 550×280.
