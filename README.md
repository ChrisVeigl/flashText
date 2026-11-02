# flashtext

Turn a plain text file into an MP4 video of centered text slides, with optional pauses, images, fades and loops. Everything runs offline, using Python (Pillow) and FFmpeg.

- Output: **1920x1080, 25 fps**, H.264 (`yuv420p`, BT.709), MP4
- Text is centered and keeps the line layout of your text file
- Slides are separated by empty lines
- Commands in angle brackets control timing, colors, alignment, images, fades, cross-fades and loops
- No scrolling or text animation, so there is nothing to flicker

---

## Table of contents

1. [Installation](#1-installation)
2. [Quick start](#2-quick-start)
3. [Command-line options](#3-command-line-options)
4. [The text file format](#4-the-text-file-format)
5. [Commands](#5-commands)
6. [How settings work](#6-how-settings-work)
7. [Complete examples](#7-complete-examples)
8. [Fonts](#8-fonts)
9. [Technical details](#9-technical-details)
10. [Troubleshooting](#10-troubleshooting)
11. [Limitations](#11-limitations)
12. [Extending the script](#12-extending-the-script)

---

## 1. Installation

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install ffmpeg python3 python3-pil fontconfig
```

Optional, for the default font (Arial Black) and Impact, which Ubuntu does not include:

```bash
sudo apt install ttf-mscorefonts-installer
fc-cache -f
```

Without these fonts the script still works. It prints a warning and uses the closest font fontconfig finds (usually DejaVu Sans).

### Install the script

Copy `flashtext.py` into a folder of your choice and make it executable:

```bash
chmod +x flashtext.py
```

> **Tip:** If you copy the code out of a web page or chat, indentation can get damaged, which shows up as `IndentationError`. Download the file instead, or see [Troubleshooting](#10-troubleshooting).

### Check the installation

```bash
ffmpeg -version | head -1
python3 -c "import PIL; print('Pillow', PIL.__version__)"
fc-match "Arial Black"          # shows which font will really be used
```

### Other systems

The script needs Python 3.8 or newer, Pillow 8 or newer and an `ffmpeg` executable in the `PATH`. On macOS, `brew install ffmpeg` and `pip install pillow` work. Font lookup by family name uses `fc-match` (fontconfig). Where it is not available, give a font file with `--font /path/to/font.ttf`.

---

## 2. Quick start

Create `story.txt`:

```
Welcome to
flashtext

Roses are red,
Violets are blue.
Sugar is sweet,
And so are you.
```

Run:

```bash
./flashtext.py story.txt -o story.mp4
```

This produces:

| # | What is shown | Duration |
|---|---|---|
| 1 | `Welcome to` / `flashtext` | 2 s |
| 2 | `Roses are red,` / `Violets are blue` (the trailing dot is removed) | 2 s |
| 3 | blank screen (pause after the sentence) | 3 s |
| 4 | `Sugar is sweet,` / `And so are you` | 2 s |
| 5 | blank screen | 3 s |

Sentence dots are explained in [section 4](#sentence-dots-become-pauses). To turn that off, use `--no-dot-pause`.

Common variations:

```bash
./flashtext.py story.txt -d 4                                 # 4 s per slide
./flashtext.py story.txt --fg "#FFD54F" --bg "#1a237e"        # gold on navy
./flashtext.py story.txt --font Impact --size 160             # other font
./flashtext.py story.txt --align left                         # left-aligned block
./flashtext.py story.txt --no-dot-pause                       # keep dots, no pauses
```

---

## 3. Command-line options

```
./flashtext.py TEXTFILE [options]
```

| Option | Default | Description |
|---|---|---|
| `TEXTFILE` | (required) | The input text file (UTF-8). |
| `-o`, `--output FILE` | `output.mp4` | Output video file. An existing file is overwritten. |
| `-d`, `--duration SEC` | `2` | Start value for the default duration of slides, in seconds. Can be changed in the text with `<duration=..>`. |
| `--pause SEC` | `3` | Start value for the default pause length. Used by `<pause>` without a value and after sentence dots. Can be changed in the text with `<pause=..>`. |
| `--fg COLOR` | `white` | Start value for the text color: a name (`red`) or `#RRGGBB`. Can be changed in the text with `<fg ..>`. |
| `--bg COLOR` | `black` | Start value for the background color, also used for pauses, image borders and fades. Can be changed in the text with `<bg ..>`. |
| `--font FONT` | `Arial Black` | Font family name (looked up with fontconfig) or path to a `.ttf`/`.otf` file. |
| `--size PX` | `200` | Maximum font size in pixels. The script reduces it automatically so that every slide fits. |
| `--align center\|left\|right` | `center` | Start value for the alignment of the lines inside the centered text block. Can be changed in the text with `<align ..>`. |
| `-n`, `--max-chars N` | `0` | Wrap lines longer than N characters at word boundaries. `0` means never wrap. Words are never split. |
| `--no-dot-pause` | off | Do not treat a dot at the end of a line as a pause. |
| `--keep-dots` | off | Keep the trailing dot visible. The pause is still added. |
| `-h`, `--help` | | Show the built-in help. |

Resolution (1920x1080) and frame rate (25 fps) are constants at the top of the script (`W, H, FPS`).

---

## 4. The text file format

### Lines and slides

- Every line of the file is a line on the slide.
- **An empty line starts the next slide.** Several empty lines count as one separator.
- Text is centered horizontally and vertically.
- Leading spaces are kept (tabs become 4 spaces). They matter mainly with `--align left`.
- Trailing spaces are removed.
- All slides use the **same font size**. It is the largest size (up to `--size`) at which the widest line and the tallest slide still fit. If one slide with many lines makes everything small, split it with an empty line.

```
Line one
Line two          <- same slide as line one

Next slide
```

### Wrapping long lines

By default, lines are never wrapped, so your layout stays exactly as written. With `-n 30`, lines longer than 30 characters are wrapped at spaces. A single word longer than the limit stays whole (with a warning).

### Sentence dots become pauses

A line that **ends with a single dot** is treated as the end of a sentence:

1. the dot is removed from the text (unless `--keep-dots`),
2. the slide ends there, and
3. a pause with the **current default pause length** follows (3 s at the start, see `--pause` and `<pause=..>`).

```
Roses are red,
Violets are blue.        <- slide ends here, then a pause
Sugar is sweet,
And so are you.          <- same again
```

Rules:

- Only the end of a **line** counts. A dot in the middle of a line is left alone. Put each sentence on its own line if you want a pause after it.
- A line ending in `...` (an ellipsis) is **not** a sentence end.
- Abbreviations and numbers at the end of a line (`Dr.`, `1.`) count as sentence ends. Turn the feature off with `--no-dot-pause` if that is a problem.
- Command lines and comments are never affected.

### Comments

Everything between `/*` and `*/` is ignored. Comments can span several lines or sit inside a line:

```
/* This is a
   multi-line comment */

First slide /* not shown */

/*
Disabled slide

Another disabled slide
*/

Last slide
```

- A line that contains only a comment is dropped completely. It does **not** count as an empty line, so commenting out a line in the middle of a slide does not split the slide.
- Commands inside a comment are ignored.
- Comments cannot be nested.
- A `/*` without a closing `*/` ignores the rest of the file (with a warning).
- There is no way to escape `/*`. Text that must contain it needs a different spelling.

### Commands

A line containing **only** `<name arguments>` is a command. It is not shown, and it ends the current slide, so no empty line is needed before it. Command names are not case sensitive. An unknown command prints a warning and is skipped.

To show a line that looks like a command as normal text, put a backslash in front:

```
\<pause 5> is how you write a pause
```

---

## 5. Commands

### Overview

| Command | Effect |
|---|---|
| `<duration=1.5>` | Set the default duration of slides, images and `<image>` without a duration. |
| `<pause=2>` | Insert a 2 s pause and make 2 s the new default pause length. |
| `<pause>` | Insert a pause with the current default pause length. |
| `<image= file.jpg duration= 5 sec>` | Show an image. |
| `<fg red>` | Set the text color (name or `#RRGGBB`, `default` = back to `--fg`). |
| `<bg #1a237e>` | Set the background color (`default` = back to `--bg`). |
| `<align left>` | Set the text alignment: `left`, `center` or `right` (`default` = back to `--align`). |
| `<fade=0.5>` | Fade in **and** fade out the following slides and images (`0` = off). |
| `<fadein=0.5>` | Fade in only. |
| `<fadeout=0.5>` | Fade out only. |
| `<crossfade=1>` | Blend smoothly from one screen into the next (`0` = off). Alias: `<xfade=1>`. |
| `<loop=N>` ... `<end>` | Repeat everything in between N times. |

### Durations and units

Wherever a time is expected, you can write:

| Written | Meaning |
|---|---|
| `5` | 5 seconds |
| `0.5` or `0,5` | half a second |
| `5s`, `5 sec`, `5 seconds` | 5 seconds |
| `500 ms` | 0.5 seconds |
| `1 min` | 60 seconds |

The `=` is optional everywhere: `<pause=2>`, `<pause 2>` and `<pause= 2 sec>` are equivalent.

### `<duration>`: default duration

```
<duration=1.5>
```

Sets how long the following text slides and images (without their own duration) are shown. The value must be greater than zero. `-d` only sets the starting value.

```
First slide                     <- 2 s (default from -d)

<duration=0.5>
Quick one                       <- 0.5 s

<duration=5>
Slow one                        <- 5 s
```

### `<pause>`: pause screens

A pause is a screen filled with the background color.

```
<pause=2>       pause of 2 s, and 2 s is the new default pause
<pause 0.5>     pause of half a second (also becomes the new default)
<pause>         pause using the current default pause length
```

**An explicit value also changes the default pause length.** That default is used by `<pause>` without a value and by sentence dots, so you can change the rhythm of the whole text from one place:

```
Intro text.                     <- dot: pause of 3 s (start value)

<pause=1>                       <- 1 s pause, default is now 1 s

Short pauses from here.         <- dot: pause of 1 s
<pause>                         <- another 1 s
```

Every pause with an explicit value changes the default. To get back to the old value afterwards, write another explicit pause (for example `<pause=3>`, which is itself a 3 s pause). A pause must be longer than zero.

### `<image>`: show an image

```
<image= logo.png duration= 5 sec>
<image= img/photo.jpg duration= 3>
<image= "my holiday photo.jpg" duration= 2.5>
<image= photo.jpg>                       uses the current default duration
<image photo.jpg 4 sec>                  the = signs are optional
```

- **Supported formats:** whatever Pillow can read (JPEG, PNG, GIF (first frame), BMP, WebP, TIFF, ...).
- **Paths** are looked up in this order:
  1. as given, if it is an absolute path that exists,
  2. relative to the folder of the **text file** (a leading `/` is ignored, so `/img/file.jpg` finds `<text file folder>/img/file.jpg`),
  3. relative to the text file's folder, unchanged,
  4. relative to the current directory.
- File names with spaces must be put in quotes.
- The image is scaled (up or down) to **fit** inside 1920x1080 while keeping its aspect ratio. The remaining area is filled with the background color.
- Transparent PNGs are drawn over the background color.
- Photos are rotated according to their EXIF orientation.
- Missing or unreadable images print a warning with the line number and are skipped. The rest of the video is still made.

### `<fg>` and `<bg>`: colors

```
<fg red>
<fg=#FFD54F>
<bg #1a237e>
<fg default>
```

- `<fg>` sets the text color of the following text slides. `<bg>` sets the background of **everything** after it: slides, the area around images, pauses and the color that fades go to.
- A color is a name (`red`, `navy`, `gold`, `darkgreen`, ... any CSS color name) or `#RRGGBB` / `#RGB`.
- `default` returns to the value from the command line (`--fg` / `--bg`).
- An unknown color prints a warning and the command is ignored.
- Changing `<bg>` between two screens is a hard cut, unless you use fades or a cross-fade. A cross-fade blends the two background colors smoothly.

```
<fg #FFD54F>
<bg #1a237e>
Gold on navy

<fg default>
<bg default>
Back to the command-line colors
```

### `<align>`: text alignment

```
<align left>
<align=right>
<align default>
```

The lines of a slide always form a block that is centered on the screen. `<align>` decides how the lines are aligned **inside** that block (the block is as wide as the longest line). `default` returns to the value from `--align`. It only affects text slides.

```
<align left>
Short
A much longer line        <- both lines start at the same x position

<align right>
Short
A much longer line        <- both lines end at the same x position
```

### `<fade>`, `<fadein>` and `<fadeout>`: fades

```
<fade=0.5>          fade in and fade out, 0.5 s each
<fadein=2>          fade in only
<fadeout=1>         fade out only
```

`<fade=X>` is a shortcut for `<fadein=X>` plus `<fadeout=X>`.

- Applies to **text slides and images**. Pauses are not faded (but see cross-fades below).
- The fade goes **from and to the background color**. Two slides in a row therefore dip through the background color.
- The setting **stays active** until you change it. Use `<fadein=0>` or `<fadeout=0>` to switch off.
- The fades are **part of the slide's duration**, not added to it. A 4 s slide with `fadein=1` and `fadeout=1` is fully visible for 2 s, and the total is still 4 s.
- If `fadein + fadeout` is longer than the duration, both are shortened proportionally and a warning is printed.
- The accuracy of the fade time is one frame (0.04 s).

```
<duration=4>
<fadein=1>
<fadeout=1>

Slide with fades

<fadein=0>
<fadeout=0>

Slide without fades
```

### `<crossfade>`: blend from one screen into the next

```
<crossfade=1>
```

Instead of a hard cut (or a dip through the background color), the picture changes smoothly from one screen to the next. `<crossfade=0>` switches it off. `<xfade=..>` is an alias.

- It works between any two consecutive screens: text slides, images and pauses, and between different colors and alignments.
- The value in effect at the screen that **comes after** the cut counts. Put `<crossfade=1>` before the second screen to blend into it. The first screen of the video has nothing to blend from.
- The transition is **centered on the cut** and takes its time from both screens (half from each), so the total length of the video does not change. With `<crossfade=1>` the last 0.5 s of the first screen and the first 0.5 s of the second screen are blended.
- At a cut with a cross-fade, the fade-out of the earlier screen and the fade-in of the later screen are replaced by the cross-fade. Other cuts keep their fades, so you can combine them: the first slide still fades in and the last one still fades out.
- A cross-fade cannot be longer than the shorter of the two screens. If it is, it is shortened and a warning is printed.
- Pauses take part: with `<crossfade=1>`, slide, pause, slide fades from the first slide into the background color and then into the next slide. This also applies to the pauses after sentence dots.

```
<duration=4>
<crossfade=1>

First slide

Second slide

<image= photo.jpg>
```

### `<loop>` and `<end>`: repeat a block

```
<loop=3>
...lines to repeat...
<end>
```

- Everything between `<loop=N>` and `<end>` is repeated N times. `<endloop>` works as well as `<end>`.
- The block may contain text, pauses, images and settings (`<duration>`, `<fadein>`, ...).
- **Loops cannot be nested.** An inner `<loop>` stops the script with an error.
- `N` must be a whole number of at least 1. Otherwise a warning is printed and the block is played once.
- A `<loop>` without `<end>` repeats the block up to the end of the file (with a warning). An `<end>` without `<loop>` is ignored (with a warning).
- Repeating means exactly what it says: the lines are processed again as if they were written N times. See [How settings work](#6-how-settings-work) for what that means for settings inside a block.

---

## 6. How settings work

The script keeps these running settings while it reads the file from top to bottom:

| Setting | Start value | Changed by | Used by |
|---|---|---|---|
| default duration | `-d` (2 s) | `<duration=..>` | text slides, `<image>` without duration |
| default pause | `--pause` (3 s) | `<pause=..>` / `<pause ..>` | `<pause>` without value, sentence dots |
| fade in | 0 (off) | `<fadein=..>`, `<fade=..>` | text slides, images |
| fade out | 0 (off) | `<fadeout=..>`, `<fade=..>` | text slides, images |
| cross-fade | 0 (off) | `<crossfade=..>` | the cut before each following screen |
| text color | `--fg` (white) | `<fg ..>` | text slides |
| background color | `--bg` (black) | `<bg ..>` | all screens |
| alignment | `--align` (center) | `<align ..>` | text slides |

Rules:

- A setting changes **everything after** the command, until it is changed again.
- `<fg default>`, `<bg default>` and `<align default>` return to the command-line values.
- A time given directly on a command (for example `<image= a.jpg duration= 5>`) is used for that item only and does not change the setting. The exception is `<pause=..>`, which always sets the default pause.
- **Inside loops**, settings are repeated with the block and are still in effect after it. If a block changes a setting, set it at the start of the block so each iteration begins the same way:

```
<loop=3>
<duration=1>          <- set at the top, so every iteration starts at 1 s
A
<duration=0.5>
B
<end>
                      <- duration is 0.5 s here
```

- Because `<pause=..>` changes the default pause, a pause inside a loop also changes the length of later sentence-dot pauses. Write another explicit pause (for example `<pause=3>`) to go back, or use `--no-dot-pause` for texts that do not need dot pauses.

---

## 7. Complete examples

### Example 1: sentence-by-sentence story

`story.txt`:

```
Once upon a time.
There was a small cat.
The cat liked to sleep.
```

```bash
./flashtext.py story.txt -d 2 --pause 1.5 -o story.mp4
```

Every line ends with a dot, so each line becomes its own slide followed by a 1.5 s pause. The dots are not shown. Total: 3 x (2 + 1.5) = 10.5 s.

### Example 2: presentation with fades and an image

Folder layout:

```
demo.txt
img/logo.png
```

`demo.txt`:

```
/* flashtext demo */
<duration=3>
<fadein=0.5>
<fadeout=0.5>

Welcome to
flashtext

<pause=1>

Roses are red,
Violets are blue.
Sugar is sweet,
And so are you.

<image= img/logo.png duration= 4 sec>
```

```bash
./flashtext.py demo.txt -o demo.mp4 --fg "#FFD54F" --bg "#1a237e"
```

| Part | Duration |
|---|---|
| "Welcome to / flashtext" (0.5 s fade in, 0.5 s fade out) | 3 s |
| pause | 1 s |
| "Roses are red, / Violets are blue" | 3 s |
| pause after the dot (default pause is now 1 s) | 1 s |
| "Sugar is sweet, / And so are you" | 3 s |
| pause after the dot | 1 s |
| image `img/logo.png` | 4 s |
| **Total** | **16 s** |

### Example 3: countdown with a loop

`count.txt`:

```
<duration=1>
<loop=3>
3

2

1

<end>
GO!
```

Three countdowns, each number for 1 s, then `GO!` for 1 s: 10 s in total.

### Example 4: blinking text

`blink.txt`:

```
<duration=0.5>
<loop=5>
ALERT
<pause 0.5>
<end>
```

`ALERT` is shown for 0.5 s, followed by 0.5 s of background color, five times: 5 s in total. Note that `<pause 0.5>` makes 0.5 s the default pause from then on.

### Example 5: different timing per section

```
<duration=1>
Fast section
Line two

Another fast one

<duration=6>
<fadein=1>
<fadeout=1>

Slow section with fades

<fadein=0>
<fadeout=0>
<duration=2>

Back to normal
```

### Example 6: left-aligned block with comments

```
/* Shopping list - the second slide is disabled */
Shopping:
  * apples
  * bread
  * coffee

/*
Draft slide that is not part of the video yet
*/

Done
```

```bash
./flashtext.py list.txt --align left -d 4
```

### Example 7: colors, alignment and cross-fades

`slideshow.txt`:

```
/* a small slideshow with colors, alignment and cross-fades */
<duration=3>
<crossfade=1>

<fg #FFD54F>
<bg #1a237e>
Chapter one

<fg white>
<align left>
First line
A much longer second line

<align right>
First line
A much longer second line

<align default>
<fg default>
<bg default>
<crossfade=0>
<fade=0.5>
The End
```

```bash
./flashtext.py slideshow.txt -o slideshow.mp4
```

| Screen | What happens | Duration |
|---|---|---|
| "Chapter one" | gold on navy, first screen (no cross-fade into it) | 3 s |
| two lines, left-aligned | white on navy, blends in from the first screen | 3 s |
| two lines, right-aligned | blends in from the previous screen | 3 s |
| "The End" | colors back to the defaults (white on black); a cross-fade is off, so it fades in and out over 0.5 s each | 3 s |
| **Total** | | **12 s** |

---

## 8. Fonts

- `--font "Arial Black"` and `--font Impact` look the font up by family name with `fc-match`.
- To use a font file directly: `--font ~/fonts/Roboto-Black.ttf`.
- List installed fonts: `fc-list : family | sort -u`.
- If the requested family is not installed, the script warns and uses the closest match, for example:

```
Warning: font 'Impact' not found, using 'DejaVu Sans' instead
```

Install `ttf-mscorefonts-installer` (see [Installation](#1-installation)) or pass a font file to fix it.

---

## 9. Technical details

- **Rendering:** each slide is rendered with Pillow. Frames are streamed as raw RGB to FFmpeg, so no temporary files are written.
- **Encoding:** `libx264`, CRF 16, preset `medium`, `yuv420p`, BT.709 color tags, `+faststart`. The RGB to YUV conversion also uses the BT.709 matrix, so colors match the tags.
- **Frame accuracy:** durations are converted to frames at 25 fps (0.04 s). Rounding is done on the running total, so there is no drift over many items. A 0.5 s pause is 12 or 13 frames depending on where it falls. Very short items (below about 0.02 s) can end up with 0 frames.
- **Cross-fades and fades:** both are computed frame by frame by blending the two pictures (or a picture and the background color). A cross-fade of c frames uses the last `(c+1)/2` frames of the first screen and the first `c/2` frames of the second, so no time is added or lost.
- **Loops:** the block is repeated before rendering. Recently used slides and images are cached in memory, so loops do not render the same content again and again.
- **Speed:** static slides encode quickly. Fades are computed frame by frame (roughly 5 to 10 ms per frame), so very many faded slides take more time.
- **Console output:** a summary line shows the number of text slides, images and pauses (including loop repetitions), the font size and the total length.

---

## 10. Troubleshooting

| Problem | Cause and fix |
|---|---|
| `IndentationError: expected an indented block` | Indentation was lost while copying the code. Download the file again, or run `python3 -m py_compile flashtext.py` to find the damaged spot. `expand -t4 flashtext.py > fixed.py` converts tabs to spaces. |
| `Warning: font '...' not found` | The font is not installed. Install `ttf-mscorefonts-installer` or pass a font file with `--font`. |
| `ffmpeg: command not found` or `FileNotFoundError` | Install FFmpeg: `sudo apt install ffmpeg`. |
| `ModuleNotFoundError: No module named 'PIL'` | `sudo apt install python3-pil` (or `pip install pillow`). |
| Text is much smaller than expected | One slide has a very long line or many lines, and the font size is shared by all slides. Split the slide, wrap with `-n`, or shorten the line. |
| `Warning: image '...' not found` | Check the path. It is relative to the text file's folder. File names with spaces need quotes. |
| `Warning: unknown command '...'` | Typo in a command name. The line is skipped. To show it as text, put `\` in front. |
| A line like `<b>text</b>` disappears | A line made only of `<...>` is read as a command. Write `\<b>text</b>` (or put other text on the line). |
| `Error: ... nested loops are not supported` | Remove the inner `<loop>` or write out the inner repetitions by hand. |
| `Warning: fadein + fadeout ... longer than the duration` | The fades are longer than the slide. Increase `<duration>` or shorten the fades. |
| A sentence is followed by an unwanted pause | Its line ends with a dot. Use `--no-dot-pause`, end the line differently, or use `...`. |
| `Warning: unknown color '...'` | The color name is not known. Use a CSS color name (`red`, `navy`) or `#RRGGBB`. The command is ignored. |
| `Warning: invalid alignment '...'` | `<align>` accepts only `left`, `center`, `right` or `default`. |
| `Warning: crossfade of ... shortened` | A screen next to the cut is shorter than the cross-fade. Make the screens longer or the cross-fade shorter. |
| Fade or cross-fade looks too short or too long | The accuracy is one frame (0.04 s), and fades are part of the duration of the screen. Check `<duration>`. |
| `Nothing to show` | The file only contains settings or comments. |

---

## 11. Limitations

- Fixed output size (1920x1080) and frame rate (25 fps). Change `W, H, FPS` in the script if you need something else.
- No scrolling, per-word animation or audio.
- One font and one font size per video. Colors, alignment, durations and fades can change inside the text, the font cannot.
- Fades go through the background color. Cross-fades blend two consecutive screens, but there are no other transition effects (wipes, slides, zooms).
- Loops cannot be nested.
- Dots are detected only at the end of a line.
- A comment cannot contain `*/` and `/*` cannot be escaped.

---

## 12. Extending the script

Commands are small handler functions at the top of `flashtext.py`:

1. Write a handler `cmd_xyz(arg, lineno, base_dir)` that returns an event dictionary (or `None` if the arguments are invalid).
2. Register it in the `COMMANDS` dictionary.
3. Handle the new event type in `resolve()` (timing and running settings) and in `emit_all()` (writing the frames).

Commands that only change a setting (like `<fg>`, `<align>` or `<fade>`) return `{"type": "set", "values": {...}}`. For those, add the setting's start value to the `defaults` dictionary in `main()` and store it on each item in `resolve()`. A value of `None` means "back to the command-line value".

Ideas that fit this structure: other transition effects (wipes, slides), `<audio>` for a sound track, or per-slide font size.

