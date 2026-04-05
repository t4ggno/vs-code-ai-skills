---
name: media-converter-image
description: Converts common 2026 image formats such as PNG, JPG/JPEG, WEBP, AVIF, GIF, BMP, TIFF, ICO, ICNS, and SVG-to-raster outputs. Use this when the user asks to convert image files or icons between formats, such as PNG to JPG, JPG to ICO, WEBP to PNG, AVIF to JPEG, or SVG to PNG. Do not use it for true vectorization, advanced photo editing, or video/audio conversion.
argument-hint: <input> <output> [quality, background, sizes, animation]
---

# Media Converter - Image

1. Use this skill for image-format conversion and icon generation.
2. Prefer the local script [convert.py](./convert.py) instead of ad-hoc snippets.
3. Let the output file extension define the target format.
4. For formats without transparency support, pass `--background` explicitly when needed.
5. For ICO output, provide multiple icon sizes with `--sizes` for better Windows results.
6. For SVG input, let the script rasterize through CairoSVG before converting onward.
7. Do not promise raster-to-true-SVG conversion. That requires vector tracing, not ordinary format conversion.
8. If the source is animated and the target also supports animation, add `--all-frames`.

## Common invocations

- PNG to JPG:
  `python ./convert.py assets/logo.png assets/logo.jpg --quality 92 --background "#ffffff" --overwrite`
- JPG to ICO:
  `python ./convert.py assets/app-icon.jpg assets/app-icon.ico --sizes 16x16 32x32 48x48 64x64 128x128 256x256 --overwrite`
- WEBP to PNG:
  `python ./convert.py assets/banner.webp assets/banner.png --overwrite`
- SVG to WEBP:
  `python ./convert.py assets/illustration.svg assets/illustration.webp --output-width 1600 --quality 90 --overwrite`
- Animated GIF to animated WEBP:
  `python ./convert.py assets/spinner.gif assets/spinner.webp --all-frames --quality 85 --overwrite`

## Guardrails

- Keep conversions local; do not upload user files to external services.
- Explain clearly when a conversion is not meaningful, such as raster-to-vector SVG.
- Prefer PNG or WEBP when transparency must survive.
- Prefer ICO for Windows app icons and ICNS for macOS app icons.
