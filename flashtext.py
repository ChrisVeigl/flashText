#!/usr/bin/env python3
"""
Turn a text file into a video of centered text slides, keeping the file's layout.

  - every line of the file stays a line on the slide
  - an empty line starts the next slide
  - a line ending in a single dot (end of a sentence) is shown without the dot,
    followed by a pause of the current default pause length
    (see --no-dot-pause / --keep-dots)
  - /* ... */ comments (also over several lines) are ignored
  - a line containing only <command args> is a command (not displayed):

      <duration=1.5>                    set the default duration (seconds)
      <pause=2>                         background-colored screen for 2 sec;
                                        2 sec also becomes the new default pause
      <pause>                           pause with the current default length
      <image= pic.jpg duration= 5 sec>  show an image, scaled to fit
      <fg red>   <bg #1a237e>           text color / background color
      <align left>                      text alignment: left, center or right
      <fade=1>                          fade in AND fade out (in seconds)
      <fadein=2>   <fadeout=1>          fade in / fade out separately
      <crossfade=1>                     cross-fade between following screens
      <loop=100> ... <end>              repeat the lines in between (no nesting)

    Durations accept units: 5, 5s, 5 sec, 0.5, 500 ms, 1 min.
    Fades and cross-fades: 0 = off.  Colors/alignment: 'default' = value from
    the command line.
    (write \\<pause 5> to show such a line as normal text)

Usage:
  ./flashtext.py input.txt [-o out.mp4] [-d 2] [--fg white] [--bg black]
                 [--font "Arial Black"] [--size 200] [-n 0]
                 [--align center|left|right]
                 [--pause 3] [--no-dot-pause] [--keep-dots]
"""
import argparse
import os
import re
import subprocess
import sys
from collections import OrderedDict

from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageOps

W, H, FPS = 1920, 1080, 25
MARGIN_X = 0.92        # text may use at most 92% of the video width
MARGIN_Y = 0.88        # ... and 88% of the video height
LINE_SPACING = 1.15    # multiple of the font's natural line height

CMD_RE = re.compile(r"^\s*<\s*([A-Za-z_][A-Za-z0-9_]*)\s*(.*?)\s*>\s*$")
DUR_RE = re.compile(
    r"^([0-9]*[.,]?[0-9]+)\s*"
    r"(ms|msec|millisec\w*|s|sec|secs|second|seconds|m|min|mins|minute|minutes)?$",
    re.IGNORECASE)
DURATION_KEY_RE = re.compile(r"(?:^|\s)(?:duration|dur)(?:\s*=\s*|\s+)",
                             re.IGNORECASE)
DOT_END_RE = re.compile(r"(?<!\.)\.$")     # single trailing dot ("..." is ignored)
ALIGNMENTS = ("left", "center", "right")


def warn(lineno, msg):
    print(f"Warning: line {lineno}: {msg}", file=sys.stderr)


def strip_eq(arg):
    """'= 5 sec' -> '5 sec'"""
    arg = arg.strip()
    if arg.startswith("="):
        arg = arg[1:].strip()
    return arg


def parse_duration(arg):
    """'5', '0.5', '0,5', '5 sec', '500 ms', '1 min' -> seconds (None if invalid)."""
    m = DUR_RE.match(arg.strip())
    if not m:
        return None
    value = float(m.group(1).replace(",", "."))
    unit = (m.group(2) or "s").lower()
    if unit.startswith("ms") or unit.startswith("milli"):
        return value * 0.001
    if unit.startswith("m"):
        return value * 60
    return value


def read_seconds(arg, lineno, what, allow_zero=False, required=False):
    """Parse a duration argument. Returns (valid, seconds or None if not given)."""
    arg = strip_eq(arg)
    if not arg:
        if required:
            warn(lineno, f"<{what}> needs a value, ignored")
            return False, None
        return True, None
    sec = parse_duration(arg)
    if sec is None or sec < 0 or (sec == 0 and not allow_zero):
        warn(lineno, f"invalid {what} value '{arg}', ignored")
        return False, None
    return True, sec


def valid_color(spec):
    try:
        ImageColor.getrgb(spec)
        return True
    except ValueError:
        return False


def find_image(name, base_dir):
    """Look for an image: as given, relative to the text file's folder
    (a leading '/' is also treated as relative to that folder), then
    relative to the current directory."""
    candidates = []
    if os.path.isabs(name):
        candidates.append(name)
    candidates.append(os.path.join(base_dir, name.lstrip("/")))
    candidates.append(os.path.join(base_dir, name))
    candidates.append(os.path.abspath(name.lstrip("/")))
    for c in candidates:
        if os.path.isfile(c):
            return os.path.abspath(c)
    return None


# ----------------------------------------------------------------------------
# Commands: each handler gets (argument string, line number, base directory of
# the text file) and returns an event dict, or None if the command is invalid.
# To add a command: write a handler, register it in COMMANDS, and handle its
# event type in resolve() / emit_all().
#
# Settings commands return {"type": "set", "values": {name: value}}; a value of
# None means "back to the start value from the command line".
# ----------------------------------------------------------------------------
def cmd_pause(arg, lineno, base_dir):
    ok, sec = read_seconds(arg, lineno, "pause")
    if not ok:
        return None
    # an explicit length also becomes the new default pause length
    return {"type": "pause", "duration": sec, "sets_default": sec is not None,
            "line": lineno}


def cmd_image(arg, lineno, base_dir):
    arg = strip_eq(arg)
    m = DURATION_KEY_RE.search(arg)
    if m:                                   # image= FILE duration= TIME
        name, dur_text = arg[:m.start()].strip(), arg[m.end():].strip()
    elif arg[:1] in ("\"", "'") and arg.count(arg[0]) >= 2:   # "file name.jpg" TIME
        end = arg.index(arg[0], 1)
        name, dur_text = arg[1:end], arg[end + 1:].strip()
    else:                                   # image= FILE [TIME]
        parts = arg.split(None, 1)
        name = parts[0] if parts else ""
        dur_text = parts[1] if len(parts) > 1 else ""

    name = name.strip().strip("\"'")
    if not name:
        warn(lineno, "image command without filename, ignored")
        return None
    ok, sec = read_seconds(dur_text, lineno, "image duration")
    if not ok:
        return None
    path = find_image(name, base_dir)
    if path is None:
        warn(lineno, f"image '{name}' not found, ignored")
        return None
    try:
        with Image.open(path) as im:
            im.verify()
    except Exception as e:
        warn(lineno, f"cannot read image '{name}' ({e}), ignored")
        return None
    return {"type": "image", "path": path, "duration": sec, "line": lineno}


def make_setter(name, keys, allow_zero):
    """<duration=..>, <fadein=..>, <fadeout=..>, <fade=..>, <crossfade=..>"""
    def handler(arg, lineno, base_dir):
        ok, sec = read_seconds(arg, lineno, name, allow_zero=allow_zero,
                               required=True)
        if not ok:
            return None
        return {"type": "set", "values": {k: sec for k in keys}, "line": lineno}
    return handler


def make_color_setter(key):
    """<fg red>, <bg=#1a237e>, <fg default>"""
    def handler(arg, lineno, base_dir):
        val = strip_eq(arg).strip("\"'").strip()
        if not val:
            warn(lineno, f"<{key}> needs a color, ignored")
            return None
        if val.lower() == "default":
            val = None
        elif not valid_color(val):
            warn(lineno, f"unknown color '{val}' for <{key}>, ignored "
                         f"(use a name like red or #RRGGBB)")
            return None
        return {"type": "set", "values": {key: val}, "line": lineno}
    return handler


def cmd_align(arg, lineno, base_dir):
    val = strip_eq(arg).lower()
    if val == "default":
        val = None
    elif val not in ALIGNMENTS:
        warn(lineno, f"invalid alignment '{val}' (use left, center or right), "
                     f"ignored")
        return None
    return {"type": "set", "values": {"align": val}, "line": lineno}


def cmd_loop(arg, lineno, base_dir):
    arg = strip_eq(arg)
    if re.fullmatch(r"[0-9]+", arg) and int(arg) >= 1:
        count = int(arg)
    else:
        warn(lineno, f"invalid loop count '{arg}' (need a whole number >= 1), "
                     f"block is played once")
        count = 1
    return {"type": "loop", "count": count, "line": lineno}


def cmd_end(arg, lineno, base_dir):
    return {"type": "endloop", "line": lineno}


_crossfade = make_setter("crossfade", ["crossfade"], allow_zero=True)

COMMANDS = {
    "pause": cmd_pause,
    "image": cmd_image,
    "duration": make_setter("duration", ["duration"], allow_zero=False),
    "fadein": make_setter("fadein", ["fadein"], allow_zero=True),
    "fadeout": make_setter("fadeout", ["fadeout"], allow_zero=True),
    "fade": make_setter("fade", ["fadein", "fadeout"], allow_zero=True),
    "crossfade": _crossfade,
    "xfade": _crossfade,
    "fg": make_color_setter("fg"),
    "bg": make_color_setter("bg"),
    "align": cmd_align,
    "loop": cmd_loop,
    "end": cmd_end,
    "endloop": cmd_end,
}


# ----------------------------------------------------------------------------
# Parsing
# ----------------------------------------------------------------------------
def wrap_line(line, max_chars):
    """Wrap one line at word boundaries (words are never split)."""
    if max_chars <= 0 or len(line) <= max_chars:
        return [line]
    out, cur = [], ""
    for word in line.split():
        if len(word) > max_chars:
            print(f"Warning: word longer than {max_chars} chars: '{word}'",
                  file=sys.stderr)
        if not cur:
            cur = word
        elif len(cur) + 1 + len(word) <= max_chars:
            cur += " " + word
        else:
            out.append(cur)
            cur = word
    if cur:
        out.append(cur)
    return out


def strip_comments(raw, state, lineno):
    """Remove /* ... */ comments from one line. 'state' remembers whether a
    comment is still open from a previous line. Returns (text, had_comment)."""
    out, i, had = [], 0, False
    while i < len(raw):
        if state["in"]:
            had = True
            j = raw.find("*/", i)
            if j < 0:
                break
            state["in"] = False
            i = j + 2
        else:
            j = raw.find("/*", i)
            if j < 0:
                out.append(raw[i:])
                break
            out.append(raw[i:j])
            state["in"], state["line"], had = True, lineno, True
            i = j + 2
    return "".join(out), had


def parse_events(text, max_chars, base_dir, dot_pauses, keep_dots):
    """Turn the text into a flat list of events:
         slide   {'lines': [...]}          pause   {'duration': sec | None}
         image   {'path', 'duration'}      set     {'values': {...}}
         loop    {'count'}                 endloop
       (duration None = use the current default duration / default pause)"""
    events, cur, cur_line = [], [], 0
    comment = {"in": False, "line": 0}

    def flush():
        nonlocal cur
        if cur:
            events.append({"type": "slide", "lines": cur, "line": cur_line})
            cur = []

    def add_text(line, lineno):
        """Add a text line; a trailing dot ends the slide and adds a pause."""
        nonlocal cur_line
        ends_sentence = dot_pauses and DOT_END_RE.search(line) is not None
        if ends_sentence and not keep_dots:
            line = DOT_END_RE.sub("", line).rstrip()
        if line.strip():
            if not cur:
                cur_line = lineno
            cur.extend(wrap_line(line, max_chars))
        if ends_sentence:
            flush()
            events.append({"type": "pause", "duration": None, "line": lineno})

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    for lineno, raw in enumerate(text.split("\n"), start=1):
        raw, had_comment = strip_comments(raw, comment, lineno)
        if had_comment and not raw.strip():       # line was only a comment
            continue
        line = raw.rstrip().expandtabs(4)

        if not line.strip():                      # empty line -> next slide
            flush()
            continue

        stripped = line.lstrip()
        if stripped.startswith("\\<"):            # escaped: literal text
            line = line[:len(line) - len(stripped)] + stripped[1:]
            add_text(line, lineno)
            continue

        m = CMD_RE.match(line)
        if m:                                     # command line
            name, arg = m.group(1).lower(), m.group(2)
            flush()
            handler = COMMANDS.get(name)
            if handler is None:
                warn(lineno, f"unknown command '{name}', ignored")
                continue
            ev = handler(arg, lineno, base_dir)
            if ev:
                events.append(ev)
            continue

        add_text(line, lineno)                    # normal text line
    flush()
    if comment["in"]:
        warn(comment["line"], "comment '/*' is never closed, "
                              "the rest of the file is ignored")
    return events


def expand_loops(events):
    """Repeat the events between <loop=N> and <end> N times (no nesting)."""
    out, block, count, start = [], None, 1, 0
    for ev in events:
        t = ev["type"]
        if t == "loop":
            if block is not None:
                sys.exit(f"Error: line {ev['line']}: nested loops are not "
                         f"supported (the loop from line {start} is still open)")
            block, count, start = [], ev["count"], ev["line"]
        elif t == "endloop":
            if block is None:
                warn(ev["line"], "<end> without <loop>, ignored")
            else:
                out.extend(block * count)
                block = None
        else:
            (out if block is None else block).append(ev)
    if block is not None:
        warn(start, "<loop> without <end>, the block runs to the end of the file")
        out.extend(block * count)
    return out


def resolve(events, defaults):
    """Apply the running settings to every event and return the final list of
    timed items. 'defaults' holds the start values: duration, pause, fg, bg,
    align (fades and cross-fade start at 0)."""
    state = dict(defaults, fadein=0.0, fadeout=0.0, crossfade=0.0)
    initial = dict(state)
    items, warned = [], set()
    for ev in events:
        t = ev["type"]
        if t == "set":
            for key, val in ev["values"].items():
                state[key] = initial[key] if val is None else val
            continue

        if t == "pause":
            if ev.get("duration"):
                dur = ev["duration"]
                if ev.get("sets_default"):         # <pause=X> changes the default
                    state["pause"] = dur
            else:
                dur = state["pause"]               # <pause> or end of sentence
        else:
            dur = ev.get("duration") or state["duration"]

        it = {"type": t, "duration": dur, "line": ev.get("line", 0),
              "fg": state["fg"], "bg": state["bg"], "align": state["align"],
              "fadein": 0.0, "fadeout": 0.0, "crossfade": state["crossfade"],
              "head": 0, "tail": 0}
        if t == "slide":
            it["lines"] = ev["lines"]
        elif t == "image":
            it["path"] = ev["path"]
        if t != "pause":                          # fading a blank screen is moot
            it["fadein"], it["fadeout"] = state["fadein"], state["fadeout"]
            if it["fadein"] + it["fadeout"] > dur + 1e-9 \
                    and it["line"] not in warned:
                warned.add(it["line"])
                warn(it["line"], f"fadein + fadeout "
                                 f"({it['fadein'] + it['fadeout']:g} s) is longer "
                                 f"than the duration ({dur:g} s); "
                                 f"the fades are shortened")
        items.append(it)
    return items


def plan_transitions(items):
    """Work out the cross-fades. A cross-fade of c frames at the cut between
    two items uses the last (c+1)//2 frames of the first and the first c//2
    frames of the second, so the total length does not change."""
    warned = set()
    for a, b in zip(items, items[1:]):
        want = int(b["crossfade"] * FPS + 0.5)
        if want <= 0:
            continue
        c = min(want, 2 * min(a["frames"] // 2, b["frames"] // 2))
        if c < want and b["line"] not in warned:
            warned.add(b["line"])
            warn(b["line"], f"crossfade of {want / FPS:g} s shortened to "
                            f"{c / FPS:g} s (the neighboring screens are too short)")
        a["tail"] = (c + 1) // 2
        b["head"] = c // 2


# ----------------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------------
def resolve_font(spec):
    """Accept a font file path or a font family name (looked up via fontconfig)."""
    if os.path.isfile(spec):
        return spec
    try:
        out = subprocess.run(
            ["fc-match", "-f", "%{family}|%{file}", spec],
            capture_output=True, text=True, check=True).stdout
        family, path = out.split("|", 1)
        if spec.lower() not in family.lower():
            print(f"Warning: font '{spec}' not found, using '{family}' instead "
                  f"(see: sudo apt install ttf-mscorefonts-installer)",
                  file=sys.stderr)
        if os.path.isfile(path):
            return path
    except (OSError, subprocess.CalledProcessError, ValueError):
        pass
    sys.exit(f"Could not find font '{spec}'. Give a .ttf file path with --font.")


def line_height(font):
    asc, desc = font.getmetrics()
    return (asc + desc) * LINE_SPACING, asc + desc


def block_height(font, n_lines):
    step, natural = line_height(font)
    return (n_lines - 1) * step + natural


def fits(fontfile, slides, size):
    font = ImageFont.truetype(fontfile, size)
    max_w = max(font.getlength(l) for s in slides for l in s)
    max_lines = max(len(s) for s in slides)
    return max_w <= W * MARGIN_X and block_height(font, max_lines) <= H * MARGIN_Y


def fit_font_size(fontfile, slides, max_size):
    """Largest size <= max_size at which every text slide fits the frame."""
    if not slides:
        return max_size
    lo, hi = 10, max_size
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if fits(fontfile, slides, mid):
            lo = mid
        else:
            hi = mid - 1
    return lo


def render_slide(lines, font, fg, bg, align):
    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)
    step, _ = line_height(font)
    top = (H - block_height(font, len(lines))) / 2
    block_w = max(font.getlength(l) for l in lines)
    left = (W - block_w) / 2                       # left edge of the block
    right = (W + block_w) / 2                      # right edge of the block
    for i, line in enumerate(lines):
        y = top + i * step
        if align == "left":
            draw.text((left, y), line, font=font, fill=fg, anchor="la")
        elif align == "right":
            draw.text((right, y), line, font=font, fill=fg, anchor="ra")
        else:
            draw.text((W / 2, y), line, font=font, fill=fg, anchor="ma")
    return img


def render_image(path, bg):
    """Scale an image to fit into the frame (keeping its aspect ratio) and
    center it on a background-colored canvas."""
    img = ImageOps.exif_transpose(Image.open(path))
    if img.mode in ("RGBA", "LA") or "transparency" in img.info:
        img = img.convert("RGBA")
    else:
        img = img.convert("RGB")
    scale = min(W / img.width, H / img.height)
    size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
    img = img.resize(size, Image.LANCZOS)
    canvas = Image.new("RGB", (W, H), bg)
    pos = ((W - size[0]) // 2, (H - size[1]) // 2)
    if img.mode == "RGBA":
        canvas.paste(img, pos, img)                # keep transparency
    else:
        canvas.paste(img, pos)
    return canvas


class Renderer:
    """Renders screens (slides, images, pauses) on demand; keeps the most
    recent ones in memory so that loops don't render the same content again."""

    def __init__(self, font, max_cache=24):
        self.font = font
        self.cache, self.max_cache = OrderedDict(), max_cache

    def get(self, item):
        t = item["type"]
        if t == "slide":
            key = ("slide", tuple(item["lines"]), item["fg"], item["bg"],
                   item["align"])
        elif t == "image":
            key = ("image", item["path"], item["bg"])
        else:
            key = ("pause", item["bg"])
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        if t == "slide":
            img = render_slide(item["lines"], self.font, item["fg"], item["bg"],
                               item["align"])
        elif t == "image":
            img = render_image(item["path"], item["bg"])
        else:
            img = Image.new("RGB", (W, H), item["bg"])
        self.cache[key] = img
        if len(self.cache) > self.max_cache:
            self.cache.popitem(last=False)
        return img

    def background(self, bg):
        return self.get({"type": "pause", "bg": bg})


def emit_all(out, items, renderer):
    """Write all frames (raw RGB) to ffmpeg."""
    for i, it in enumerate(items):
        n = it["frames"]
        if n <= 0:
            continue
        img = renderer.get(it)
        bg_img = renderer.background(it["bg"])

        head, tail = it["head"], it["tail"]        # frames used by cross-fades
        avail = n - head - tail                    # frames of this item itself
        # a cross-fade replaces the fade-in / fade-out at that cut
        fi = int(it["fadein"] * FPS + 0.5) if head == 0 else 0
        fo = int(it["fadeout"] * FPS + 0.5) if tail == 0 else 0
        if fi + fo > avail:                        # shorten fades proportionally
            fi = round(fi * avail / (fi + fo))
            fo = avail - fi
        hold = avail - fi - fo

        for k in range(fi):                        # fade in from background
            out.write(Image.blend(bg_img, img, (k + 1) / (fi + 1)).tobytes())
        if hold > 0:
            data = img.tobytes()
            for _ in range(hold):
                out.write(data)
        for j in range(fo):                        # fade out to background
            out.write(Image.blend(bg_img, img, (fo - j) / (fo + 1)).tobytes())

        if tail > 0:                               # cross-fade into the next item
            nxt = renderer.get(items[i + 1])
            c = tail + items[i + 1]["head"]
            for k in range(c):
                out.write(Image.blend(img, nxt, (k + 1) / (c + 1)).tobytes())


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("textfile")
    ap.add_argument("-o", "--output", default="output.mp4")
    ap.add_argument("-n", "--max-chars", type=int, default=0,
                    help="wrap lines longer than this many characters at word\n"
                         "boundaries (default 0 = never wrap, keep lines as is)")
    ap.add_argument("-d", "--duration", type=float, default=2.0,
                    help="start value for the default duration in seconds\n"
                         "(default 2; can be changed with <duration=..>)")
    ap.add_argument("--fg", default="white",
                    help="start value for the text color (name or #RRGGBB;\n"
                         "can be changed with <fg ..>)")
    ap.add_argument("--bg", default="black",
                    help="start value for the background color\n"
                         "(can be changed with <bg ..>)")
    ap.add_argument("--font", default="Arial Black",
                    help="font family name or path to .ttf/.otf (default Arial Black)")
    ap.add_argument("--size", type=int, default=200,
                    help="maximum font size in px; reduced automatically so\n"
                         "all slides fit (default 200)")
    ap.add_argument("--align", choices=list(ALIGNMENTS), default="center",
                    help="start value for the line alignment inside the\n"
                         "centered block (default center; <align ..> changes it)")
    ap.add_argument("--pause", type=float, default=3.0, metavar="SEC",
                    help="start value for the default pause length in seconds\n"
                         "(default 3; used by <pause> without a value and after\n"
                         "lines ending in a dot; changed by <pause=..>)")
    ap.add_argument("--no-dot-pause", action="store_true",
                    help="do not treat a dot at the end of a line as a pause")
    ap.add_argument("--keep-dots", action="store_true",
                    help="keep the trailing dot visible (pause is still added)")
    args = ap.parse_args()

    for opt, val in (("--fg", args.fg), ("--bg", args.bg)):
        if not valid_color(val):
            sys.exit(f"Unknown color for {opt}: '{val}' "
                     f"(use a name like red or #RRGGBB)")

    base_dir = os.path.dirname(os.path.abspath(args.textfile))
    with open(args.textfile, encoding="utf-8") as f:
        events = parse_events(f.read(), args.max_chars, base_dir,
                              not args.no_dot_pause, args.keep_dots)
    if not events:
        sys.exit("The text file contains no text or commands.")

    text_slides = [e["lines"] for e in events if e["type"] == "slide"]
    items = resolve(expand_loops(events),
                    {"duration": args.duration, "pause": args.pause,
                     "fg": args.fg, "bg": args.bg, "align": args.align})
    if not items:
        sys.exit("Nothing to show (only settings, no text, images or pauses).")

    # Frame counts: rounded on the running total, so nothing drifts
    t, prev = 0.0, 0
    for it in items:
        t += it["duration"]
        end = int(t * FPS + 0.5 + 1e-9)
        it["frames"] = end - prev
        prev = end
    total_frames = prev
    if total_frames == 0:
        sys.exit("The video would have no frames.")
    plan_transitions(items)

    fontfile = resolve_font(args.font)
    size = fit_font_size(fontfile, text_slides, args.size)
    renderer = Renderer(ImageFont.truetype(fontfile, size))

    n_of = lambda kind: sum(it["type"] == kind for it in items)
    print(f"{n_of('slide')} text slides, {n_of('image')} images, "
          f"{n_of('pause')} pauses (incl. loop repetitions), font size {size}px, "
          f"total length {total_frames / FPS:.1f}s")

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-stats",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-video_size", f"{W}x{H}", "-framerate", str(FPS), "-i", "-",
        "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
        "-c:v", "libx264", "-crf", "16", "-preset", "medium",
        "-colorspace", "bt709", "-color_primaries", "bt709",
        "-color_trc", "bt709",
        "-movflags", "+faststart",
        args.output,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        emit_all(proc.stdin, items, renderer)
        proc.stdin.close()
    except BrokenPipeError:
        pass                                       # ffmpeg quit; see its message
    except BaseException:
        proc.kill()
        raise
    if proc.wait() != 0:
        sys.exit("ffmpeg failed.")

    print(f"Done: {args.output}")


if __name__ == "__main__":
    main()
