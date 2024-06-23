#!/bin/bash

NAME=${*: -1}
echo "click on a window to start recording ${NAME}.mp4"

WINDOW_INFO=$(xdotool selectwindow getwindowgeometry --shell)
eval "$WINDOW_INFO"

XPOS=$(echo "$WINDOW_INFO" | grep "X=" | cut -d '=' -f 2)
YPOS=$(echo "$WINDOW_INFO" | grep "Y=" | cut -d '=' -f 2)
WIDTH=$(echo "$WINDOW_INFO" | grep "WIDTH=" | cut -d '=' -f 2)
HEIGHT=$(echo "$WINDOW_INFO" | grep "HEIGHT=" | cut -d '=' -f 2)

OUT_PATH="${NAME// /_}_%03d.mp4"  # Replace spaces in NAME with underscores
echo "recording ${OUT_PATH} ${WIDTH}x${HEIGHT} at ${XPOS},${YPOS}"

OUTPUT_DIR="${NAME}_output"
mkdir -p "$OUTPUT_DIR"
OUT_PATH="${OUTPUT_DIR}/${NAME}_%03d.mp4"

index=0
while [[ -e "$OUTPUT_DIR/${NAME}_$(printf '%03d' $index).mp4" ]]; do
    index=$((index + 1))
done

ffmpeg -framerate 5 -f x11grab -s "${WIDTH}x${HEIGHT}" \
    -grab_x "$XPOS" -grab_y "$YPOS" -i :1 \
    -vf settb=\(1/30\),setpts=N/TB/30 -r 30 \
    -vcodec libx264 -crf 0 -preset ultrafast \
    -threads 0 -f segment -segment_time 3 -reset_timestamps 1 \
    -segment_start_number $index "$OUT_PATH"

# Once you press 'q' to stop recording:
echo "merge video segments? (y/n)"
read merge_video
if [ "$merge_video" = "y" ]; then
    # Create a file list for ffmpeg
    for f in "$OUTPUT_DIR"/*.mp4; do
        echo "file '$(realpath "$f")'" >> "$OUTPUT_DIR"/filelist.txt;
    done
    # Merge the video segments
    ffmpeg -f concat -safe 0 -i "$OUTPUT_DIR/filelist.txt" -c copy "${OUTPUT_DIR}/${NAME}_merged.mp4"
    rm "$OUTPUT_DIR/filelist.txt"
fi
