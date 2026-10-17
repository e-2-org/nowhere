#!/bin/sh
# Renders the original Flash movies to video/now-here-nowhere.mp4, as they played:
# every frame at the original rate (12 fps, then 10 fps), with the original stepped motion.
#
#  - part one (nowhere.swf, 550 x 280) at twice its size, centred on its blue page
#  - part two (begin.swf, 200 x 40) fitted to the width, as SHOWALL did, centred on black, once
#
# 1920 x 1080 at 60 fps, which holds each Flash frame for exactly 5 (part one) or 6 (part two) video frames.
# Frames are rendered by JPEXS FFDec (https://github.com/jindrapetrik/jpexs-decompiler).
#
# Usage: sh _scripts/video.sh /path/to/ffdec-cli.jar
set -e
ffdec="$1"
root="$(cd "$(dirname "$0")/../docs" && pwd)"
frames="$(mktemp -d)"
trap 'rm -rf "$frames"' EXIT

java -jar "$ffdec" -zoom 2 -format frame:png -export frame "$frames/a" "$root/nowhere.swf" > /dev/null
java -jar "$ffdec" -zoom 9.6 -format frame:png -export frame "$frames/b" "$root/begin.swf" > /dev/null

mkdir -p "$root/video"
ffmpeg -y -loglevel error \
    -framerate 12 -i "$frames/a/%d.png" \
    -framerate 10 -i "$frames/b/%d.png" \
    -filter_complex "[0]pad=1920:1080:410:260:color=0x3399FF,fps=60,format=yuv420p[a];[1]pad=1920:1080:0:348:color=black,fps=60,format=yuv420p[b];[a][b]concat=n=2:v=1[v]" \
    -map "[v]" -c:v libx264 -preset slow -crf 16 -tune animation \
    -colorspace bt709 -color_primaries bt709 -color_trc bt709 -movflags +faststart \
    "$root/video/now-here-nowhere.mp4"
echo "video/now-here-nowhere.mp4"
