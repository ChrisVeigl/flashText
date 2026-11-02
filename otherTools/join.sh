for f in *.mp4; do echo "file '$PWD/$f'"; done > list.txt
ffmpeg -f concat -safe 0 -i list.txt -c copy joined.mp4
