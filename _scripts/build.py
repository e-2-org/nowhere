"""
Builds index.html, the HTML port of Now Here / Nowhere, from the original Flash movies

The two movies are Flash 1 (FutureSplash era) with no tweens: every frame places each
text again with a new matrix and colour transform. Each run of a text at a depth
becomes one element, animated by CSS keyframes at the times of the original frames,
so it passes through every original position and colour at the original moment,
moving smoothly in between.

 - nowhere.swf: the title, 550 x 280 at 12 fps on blue, played once; it ended with
   getURL("apbl2.html"), which loaded part two
 - begin.swf: 200 x 40 at 10 fps on black, scaled to the window (SHOWALL), looping

The texts are drawn from the movies' own embedded Times New Roman outlines, exported
as SVG by JPEXS FFDec (https://github.com/jindrapetrik/jpexs-decompiler), which also
dumps the movies' tags as XML.

Usage: python3 _scripts/build.py --ffdec /path/to/ffdec-cli.jar
"""
import argparse
import os
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'docs')
MOVIES = [
    # name, prefix, background, played once?
    ('nowhere', 'a', (51, 153, 255), True),
    ('begin', 'b', (0, 0, 0), False),
]


def ffdec_export(jar, swf, out):
    """the movie's tags as XML, and each text as SVG"""
    subprocess.run(['java', '-jar', jar, '-swf2xml', swf, os.path.join(out, 'movie.xml')], check=True, capture_output=True)
    subprocess.run(['java', '-jar', jar, '-format', 'text:svg', '-export', 'text', os.path.join(out, 'texts'), swf], check=True, capture_output=True)


def read_movie(xml_path):
    """header, and the tracks: each run of one character at one depth, with its matrix and colour transform per frame"""
    root = ET.parse(xml_path).getroot()
    rect = root.find('displayRect')
    header = {
        'width': (int(rect.get('Xmax')) - int(rect.get('Xmin'))) / 20,
        'height': (int(rect.get('Ymax')) - int(rect.get('Ymin'))) / 20,
        'fps': float(root.get('frameRate')),
        'frames': int(root.get('frameCount')),
    }
    colours = {}
    tracks, display, frame = [], {}, 1
    for tag in root.find('tags'):
        kind = tag.get('type')
        if kind == 'DefineTextTag':
            c = tag.find('.//textColor')
            colours[int(tag.get('characterID'))] = tuple(int(c.get(k)) for k in ('red', 'green', 'blue')) if c is not None else None
        elif kind == 'RemoveObjectTag':
            track = display.pop(int(tag.get('depth')), None)
            if track:
                track['removed'] = frame
        elif kind == 'PlaceObjectTag':
            depth, char = int(tag.get('depth')), int(tag.get('characterId'))
            m = tag.find('matrix')
            if m.get('hasRotate') == 'true':
                raise ValueError('rotation is not handled')
            sx, sy = (float(m.get('scaleX')), float(m.get('scaleY'))) if m.get('hasScale') == 'true' else (1.0, 1.0)
            matrix = (int(m.get('translateX')) / 20, int(m.get('translateY')) / 20, sx, sy)
            cx = tag.find('colorTransform')
            cxform = None
            if cx is not None:
                mult = cx.get('hasMultTerms') == 'true'
                add = cx.get('hasAddTerms') == 'true'
                cxform = tuple(int(cx.get(f'{c}MultTerm')) if mult else 256 for c in ('red', 'green', 'blue')) + \
                    tuple(int(cx.get(f'{c}AddTerm')) if add else 0 for c in ('red', 'green', 'blue'))
            # removed and placed again in the same frame: the same text carrying on
            track = next((t for t in tracks if t['depth'] == depth and t['char'] == char and t.get('removed') == frame), None)
            if track:
                del track['removed']
            else:
                track = {'depth': depth, 'char': char, 'keys': []}
                tracks.append(track)
            track['keys'].append((frame, matrix, cxform))
            display[depth] = track
        elif kind == 'ShowFrameTag':
            frame += 1
    for track in tracks:
        track.setdefault('removed', header['frames'] + 1)
    return header, colours, tracks


def read_texts(folder, prefix):
    """the glyph outlines, and each text as uses of them, in the text's own coordinates"""
    glyphs, texts = {}, {}
    for name in os.listdir(folder):
        with open(os.path.join(folder, name), encoding='utf-8') as file:
            svg = file.read()
        char = int(name.split('.')[0])
        # FFDec names glyphs per file, and punctuation only by number (_0, _1), so they are named here by their outline
        local = {}
        for gid, body in re.findall(r'<g id="font_Times_New_Roman_([^"]+)">\s*(.*?)\s*</g>', svg, re.S):
            path = re.search(r'd="([^"]+)"', body)[1]
            local[gid] = glyphs.setdefault(path, f'{prefix}-g{len(glyphs)}')
        # the uses inside FFDec's outer group, which only moves the text's bounds to 0,0
        out = []
        for use in re.findall(r'<use [^>]*/>', svg):
            transform = re.search(r'transform="matrix\(([^)]*)\)"', use)[1]
            a, b, c, d, e, f = (float(v) for v in transform.split(','))
            glyph = re.search(r'xlink:href="#font_Times_New_Roman_([^"]+)"', use)[1]
            out.append(f'<use href="#{local[glyph]}" transform="matrix({a:g} {b:g} {c:g} {d:g} {e:g} {f:g})"/>')
        texts[char] = ''.join(out)
    return {gid: path for path, gid in glyphs.items()}, texts


def colour(base, cxform):
    if base is None:
        return None
    if cxform is None:
        return base
    return tuple(max(0, min(255, round(base[i] * cxform[i] / 256 + cxform[3 + i]))) for i in range(3))


def hex_colour(c):
    return '#%02x%02x%02x' % c


def keyframes(name, track, base, header):
    """the track's keyframes over its movie's whole length"""
    frames = header['frames']
    pct = lambda frame: (frame - 1) / frames * 100
    keys = [(f, m, colour(base, cx)) for f, m, cx in track['keys']]
    # a text held still for some frames, then moved: hold until the frame before the move
    held = []
    for i, key in enumerate(keys):
        held.append(key)
        if i + 1 < len(keys) and keys[i + 1][0] > key[0] + 1 and (keys[i + 1][1][:2], keys[i + 1][2]) != (key[1][:2], key[2]):
            held.append((keys[i + 1][0] - 1, key[1], key[2]))
    # drop keys which lie on the line between their neighbours: the same motion, in fewer lines
    def between(a, b, c):
        t = (b[0] - a[0]) / (c[0] - a[0])
        lerp = lambda x, z: x + (z - x) * t
        if any(abs(lerp(x, z) - y) > .01 for x, y, z in zip(a[1][:2], b[1][:2], c[1][:2])):
            return False
        if a[2] and any(abs(lerp(x, z) - y) > .6 for x, y, z in zip(a[2], b[2], c[2])):
            return False
        return True
    simple = [held[0]]
    for i in range(1, len(held) - 1):
        if not between(simple[-1], held[i], held[i + 1]):
            simple.append(held[i])
    if len(held) > 1:
        simple.append(held[-1])

    def style(m, c):
        # x and y rather than transform: Chrome hands transform animations to the compositor, which
        # draws the text at the stage's own size and enlarges it, blurring it; x and y are drawn at full size.
        # The matrices' scales (all within 0.3% of 1) are applied, fixed, to each run's copy of its text in build()
        s = f'x: {m[0]:g}px; y: {m[1]:g}px;'
        if c:
            s += f' color: {hex_colour(c)};'
        return s

    start, end = track['keys'][0][0], track['removed']
    lines = []
    if start > 1:
        lines.append('0% { visibility: hidden; animation-timing-function: steps(1, end); }')
    for i, (f, m, c) in enumerate(simple):
        last = i == len(simple) - 1
        timing = ' animation-timing-function: steps(1, end);' if last and end <= frames else ''
        lines.append(f'{pct(f):.4f}% {{ visibility: visible; {style(m, c)}{timing} }}')
    if end <= frames:
        lines.append(f'{pct(end):.4f}% {{ visibility: hidden; }}')
        lines.append('100% { visibility: hidden; }')
    else:
        f, m, c = simple[-1]
        lines.append(f'100% {{ visibility: visible; {style(m, c)} }}')
    return f'@keyframes {name} {{\n' + ''.join(f'    {line}\n' for line in lines) + '}'


def build(jar):
    parts = []
    for movie, prefix, background, once in MOVIES:
        with tempfile.TemporaryDirectory() as tmp:
            ffdec_export(jar, os.path.join(ROOT, movie + '.swf'), tmp)
            header, colours, tracks = read_movie(os.path.join(tmp, 'movie.xml'))
            glyphs, texts = read_texts(os.path.join(tmp, 'texts'), prefix)
        duration = header['frames'] / header['fps']
        defs = ''.join(f'<path id="{gid}" d="{d}"/>' for gid, d in sorted(glyphs.items()))
        defs += ''.join(f'<g id="{prefix}{char}">{uses}</g>' for char, uses in sorted(texts.items()))
        elements, css = [], []
        # lower depths are drawn first
        for i, track in enumerate(sorted(tracks, key=lambda t: (t['depth'], t['keys'][0][0]))):
            name = f'{prefix}{i}'
            base = colours.get(track['char'])
            href = f'{prefix}{track["char"]}'
            # the run's scale, which hardly changes (see style()), as a fixed transform of its own copy of the text
            # weighted by how many frames each placement stays on screen
            keys = track['keys']
            held = [(keys[k + 1][0] if k + 1 < len(keys) else track['removed']) - keys[k][0] for k in range(len(keys))]
            sx, sy = (sum(m[i] * n for (_, m, _), n in zip(keys, held)) / sum(held) for i in (2, 3))
            if abs(sx - 1) > .0005 or abs(sy - 1) > .0005:
                defs += f'<g id="{name}-scaled" transform="scale({sx:.5f} {sy:.5f})"><use href="#{href}"/></g>'
                href = f'{name}-scaled'
            elements.append(f'<use class="{name}" href="#{href}"/>')
            css.append(keyframes(name, track, base, header))
            css.append(f'.{name} {{ animation-name: {name}; }}')
        parts.append({
            'prefix': prefix, 'header': header, 'duration': duration, 'once': once,
            'background': hex_colour(background), 'defs': defs, 'elements': elements, 'css': css,
        })
    return parts


def page(parts):
    a, b = parts
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Brighid Lowe - Now Here / Nowhere</title>
<meta name="description" content="Now Here / Nowhere by Brighid Lowe: the disembodied nature of words in the limbo of hyper-space.">
<!--
    Now Here / Nowhere, Brighid Lowe, produced by e-2. Built by _scripts/build.py from nowhere.swf and begin.swf:
    don't edit by hand. Part one ({a['header']['frames']} frames at {a['header']['fps']:g} fps) plays once, then part two
    ({b['header']['frames']} frames at {b['header']['fps']:g} fps) plays and loops, as the Flash movies did.
-->
<style>
html, body {{
    margin: 0;
    height: 100%;
    overflow: hidden;
}}
body {{
    background: {a['background']};
}}
body.part-b {{
    background: {b['background']};
}}
main {{
    display: none;
    align-items: center;
    justify-content: center;
    height: 100dvh;
}}
body:not(.part-b) #part-a,
body.part-b #part-b {{
    display: flex;
}}
svg {{
    display: block;
    overflow: visible;
}}
/* part one: the original's size, centred */
#part-a svg {{
    width: {a['header']['width']:g}px;
    max-width: 100vw;
    height: auto;
}}
/* part two: scaled to fit the window, as the movie was (SHOWALL) */
#part-b svg {{
    width: min(100vw, 100dvh * {b['header']['width']:g} / {b['header']['height']:g});
    height: auto;
}}
use[class] {{
    visibility: hidden;
    fill: currentColor;
    animation-timing-function: linear;
    animation-fill-mode: both;
}}
#part-a use[class] {{
    animation-duration: {a['duration']:.4f}s;
}}
/* part two only starts when it's shown */
body.part-b #part-b use[class] {{
    animation-duration: {b['duration']:.4f}s;
    animation-iteration-count: infinite;
}}
body:not(.part-b) #part-b use[class] {{
    animation-name: none !important;
}}
/* times part one: when it ends, part two starts */
#timer {{
    animation: timer {a['duration']:.4f}s linear;
}}
@keyframes timer {{
    from {{ opacity: 0; }}
    to {{ opacity: 0; }}
}}
{chr(10).join(a['css'])}
{chr(10).join(b['css'])}
</style>
</head>
<body>
<svg width="0" height="0" style="position: absolute" aria-hidden="true">
    <defs>{a['defs']}{b['defs']}</defs>
</svg>
<main id="part-a">
    <svg viewBox="0 0 {a['header']['width']:g} {a['header']['height']:g}" role="img" aria-label="Now Here / Nowhere">
        {''.join(a['elements'])}
        <rect id="timer" width="0" height="0"/>
    </svg>
</main>
<main id="part-b">
    <svg viewBox="0 0 {b['header']['width']:g} {b['header']['height']:g}" role="img" aria-label="Words moving across the screen">
        {''.join(b['elements'])}
    </svg>
</main>
<script>
/* part one ended by loading part two (getURL "apbl2.html") */
document.getElementById('timer').addEventListener('animationend', () => document.body.classList.add('part-b'));
</script>
</body>
</html>
'''


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--ffdec', required=True, help='path to ffdec-cli.jar')
    args = parser.parse_args()
    html = page(build(args.ffdec))
    with open(os.path.join(ROOT, 'index.html'), 'w', encoding='utf-8') as file:
        file.write(html)
    print(f'index.html: {len(html) // 1024} KB')
