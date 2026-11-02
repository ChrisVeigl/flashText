#!/bin/bash
# Usage: ./ticker.sh FG_COLOR BG_COLOR SPEED_PX_PER_SEC TEXTFILE [OUTPUT.mp4]
# Example: ./ticker.sh red black 1200 headlines.txt ticker.mp4
#
# Optional environment variables:
#   FONT, SIZE, WIDTH, HEIGHT, FPS, SEP
#   e.g. SIZE=120 FPS=60 ./ticker.sh "#FFD54F" "#1a237e" 900 news.txt out.mp4

set -euo pipefail

if [ $# -lt 4 ]; then
  echo "Usage: $0 FG_COLOR BG_COLOR SPEED_PX_PER_SEC TEXTFILE [OUTPUT.mp4]" >&2
  exit 1
fi

FG="$1"; BG="$2"; SPEED="$3"; TEXTFILE="$4"; OUT="${5:-ticker.mp4}"

FONT="${FONT:-/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf}"
SIZE="${SIZE:-500}"
WIDTH="${WIDTH:-800}"
HEIGHT="${HEIGHT:-600}"
FPS="${FPS:-33}"
SEP="${SEP:-     }"      # separator inserted between lines of the text file

[ -f "$TEXTFILE" ] || { echo "Text file not found: $TEXTFILE" >&2; exit 1; }
[ -f "$FONT" ]     || { echo "Font not found: $FONT" >&2; exit 1; }

# Whole pixels per frame = no sub-pixel jitter
STEP=$(( SPEED / FPS ))
[ "$STEP" -lt 1 ] && STEP=1
echo "Scroll: $STEP px/frame x $FPS fps = $(( STEP * FPS )) px/s"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
PNG="$TMP/text.png"

# 1) Render the whole text once into one long image
python3 - "$TEXTFILE" "$FONT" "$SIZE" "$FG" "$BG" "$SEP" "$PNG" <<'PY'
import sys
from PIL import Image, ImageDraw, ImageFont
textfile, fontfile, size, fg, bg, sep, out = sys.argv[1:8]
with open(textfile, encoding="utf-8") as f:
    lines = [l.strip() for l in f if l.strip()]
text = sep.join(lines) + sep            # trailing separator for a clean gap
font = ImageFont.truetype(fontfile, int(size))
asc, desc = font.getmetrics()
w = int(font.getlength(text)) + 4
img = Image.new("RGB", (w, asc + desc), bg)
ImageDraw.Draw(img).text((0, 0), text, font=font, fill=fg)
img.save(out)
PY

IMGW=$(python3 -c "from PIL import Image; print(Image.open('$PNG').size[0])")
IMGH=$(python3 -c "from PIL import Image; print(Image.open('$PNG').size[1])")
[ "$IMGH" -le "$HEIGHT" ] || { echo "Text height ($IMGH) exceeds video height ($HEIGHT); reduce SIZE" >&2; exit 1; }

# Frames needed for the text to enter from the right and fully exit left
FRAMES=$(( (IMGW + WIDTH) / STEP + 1 ))
echo "Duration: $(( FRAMES / FPS )) s ($FRAMES frames)"

# 2) Pad the image with one screen of background on each side and
#    crop a moving window, shifted by exactly STEP pixels per frame
ffmpeg -y -loglevel error -stats \
  -loop 1 -framerate "$FPS" -i "$PNG" \
  -vf "pad=iw+2*$WIDTH:$HEIGHT:$WIDTH:($HEIGHT-ih)/2:color=$BG,crop=$WIDTH:$HEIGHT:n*$STEP:0,format=yuv420p" \
  -frames:v "$FRAMES" -r "$FPS" \
  -c:v libx264 -preset medium -crf 18 \
  "$OUT"

echo "Done: $OUT"
