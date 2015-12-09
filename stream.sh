#!/bin/bash

# from http://stackoverflow.com/questions/5825173/pipe-raw-opencv-images-to-ffmpeg

python target_identification.py | cvlc --demux=rawvideo --rawvid-fps=10 --rawvid-width=640 --rawvid-height=480  --rawvid-chroma=RV24 - --sout "#transcode{vcodec=h264,vb=200,fps=10,width=320,height=240}:std{access=http{mime=video/x-flv},mux=ffmpeg{mux=flv},dst=:8081/stream.flv}"
