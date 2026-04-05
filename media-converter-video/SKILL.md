---
name: media-converter-video
description: Converts common 2026 video and animated output formats such as MP4, WEBM, MOV, MKV, AVI, GIF, and APNG by driving FFmpeg locally. Use this when the user asks to convert video files between formats, such as WEBM to MP4, MP4 to WEBM, MP4 to GIF, MOV to MP4, or MKV to WEBM. Do not use it for image-only conversions, non-local cloud transcoding, or advanced NLE editing workflows.
argument-hint: <input> <output> [fps, resize, trim, overwrite]
---

# Media Converter - Video

1. Use this skill for local video/container conversion and video-to-GIF/APNG export.
2. Prefer the local script [convert.py](./convert.py) instead of hand-writing FFmpeg commands every time.
3. Let the output extension define the target format.
4. Use the resize and fps options deliberately for GIF/APNG output to keep files practical.
5. Preserve audio only when the target format supports it.
6. Prefer MP4 for broad compatibility and WEBM for web-first open distribution.
7. If the user needs exact codec control, pass `--video-codec` and `--audio-codec` explicitly.

## Common invocations

- WEBM to MP4:
  `python ./convert.py media/input.webm media/output.mp4 --overwrite`
- MP4 to WEBM:
  `python ./convert.py media/input.mp4 media/output.webm --overwrite`
- MP4 to GIF preview:
  `python ./convert.py media/input.mp4 media/output.gif --fps 15 --width 480 --start 00:00:03 --duration 4 --overwrite`
- MOV to MKV:
  `python ./convert.py media/input.mov media/output.mkv --overwrite`
- MP4 to APNG:
  `python ./convert.py media/input.mp4 media/output.apng --fps 12 --width 640 --overwrite`

## Guardrails

- Keep conversions local and avoid uploading user media to external services.
- Explain when a target format drops audio, alpha, or timing fidelity.
- Use GIF only for short previews; prefer WEBM or MP4 for longer clips.
- When quality or compatibility matters, keep the default codecs unless the user asks otherwise.
