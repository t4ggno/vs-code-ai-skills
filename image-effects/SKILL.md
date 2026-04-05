---
name: image-effects
description: Applies local image effects such as background removal, masking, transparency cleanup, grayscale, sepia, blur, sharpen, brightness, contrast, saturation, inversion, resize, rotate, and transparent-edge trimming. Use this when the user asks to remove an image background or apply common local image effects without sending files to external services. Do not use it for video effects, generative image creation, or complex Photoshop-style compositing workflows.
argument-hint: <input> <output> [remove-background, model, blur, contrast, resize]
---

# Image Effects

1. Use this skill for local image cleanup and effect pipelines.
2. Prefer the local script [effects.py](./effects.py) instead of ad-hoc snippets.
3. For background removal, use `--remove-background` and choose a `--bg-model` only when the default is not appropriate.
4. Use `--trim-transparent` after background removal when the user wants a tightly cropped cutout.
5. Stack simple effects deliberately; avoid piling on unrelated filters just because you can.
6. Preserve transparency whenever the output format supports it. If the target format does not support alpha, set `--background-color` intentionally.
7. Keep everything local; do not upload user images to third-party services.

## Common invocations

- Remove a background:
  `python ./effects.py images/product.png images/product-cutout.png --remove-background --bg-model birefnet-general --trim-transparent --overwrite`
- Remove a background and place on white:
  `python ./effects.py images/headshot.jpg images/headshot-clean.jpg --remove-background --background-color "#ffffff" --overwrite`
- Create a mask only:
  `python ./effects.py images/object.png images/object-mask.png --remove-background --only-mask --overwrite`
- Apply a polished effect stack:
  `python ./effects.py images/banner.png images/banner-polished.webp --autocontrast --sharpen 1.2 --contrast 1.1 --saturation 1.05 --overwrite`
- Make a stylized sepia image:
  `python ./effects.py images/photo.jpg images/photo-sepia.png --sepia --brightness 1.05 --contrast 1.1 --overwrite`

## Guardrails

- Prefer PNG or WEBP for transparent cutouts.
- Background removal may download local ONNX models on first use; keep the user informed if that happens.
- For `rembg`, Python 3.12 or 3.11 is the safest choice today.
- Use stronger effects sparingly; subtle adjustments usually look better.
