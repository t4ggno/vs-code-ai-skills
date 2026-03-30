---
name: image-generator
description: Generates project images and seamless tileable textures with OpenAI image models, then evaluates them with vision. Use when the user needs a new asset, texture, or concept image saved to disk. Do not use it for editing existing images or for charts or diagrams that code should generate.
argument-hint: <subject> [style, asset type, size, folder, tileable?]
---

# Image Generator

1. Use this skill when the task is to create a new image asset, not to edit an existing bitmap.
2. Extract the key requirements before generating anything:
   - subject or material
   - style and quality bar
   - output size and folder
   - transparent vs opaque background
   - whether the result must be a seamless tile
3. Verify that `OPENAI_API_KEY` is available in the environment or workspace `.env` before running the script.
4. Execute the local script [generate.py](./generate.py) with the minimum flags needed for the requested asset.
5. For seamless textures, always add `--tileable` and describe the asset as a material sample with even lighting, no perspective, no text, no borders, and no hero object.
6. Let the script save the generated asset, build a tiled preview when relevant, and run the built-in vision evaluation.
7. If the evaluation returns a design mismatch, refine the prompt or criteria and retry deliberately instead of looping blindly.
8. Stop after a small number of high-quality retries; do not burn tokens aimlessly.

## Standard invocation

`python ./generate.py "PROMPT" "FOLDER_PATH" "CRITERIA" --model gpt-image-1.5 --size 1024x1024 --quality standard --moderation low --background opaque --output-format png --timeout 180 --vision-model gpt-5.4`

## Seamless tile example

`python ./generate.py "Worn basalt dungeon floor with subtle cracks and dusty grout" "assets/textures/floors" "Game-ready seamless floor material, readable at a distance, medium detail, no text, no perspective" --model gpt-image-1.5 --size 1024x1024 --tileable --tile-blend-ratio 0.125 --tile-preview-grid 3 --output-format png --vision-model gpt-5.4`

## Texture prompt guardrails

- Ask for a material sample, not a scene illustration.
- Prefer flat or evenly distributed lighting.
- Avoid perspective distortion, borders, logos, text, and singular focal objects.
- Prefer top-down or front-on material views.

## Defaults worth keeping unless the task says otherwise

- `--model gpt-image-1.5`
- `--size 1024x1024`
- `--quality standard`
- `--moderation low`
- `--background opaque`
- `--output-format png`
- `--vision-model gpt-5.4`
- `--tile-blend-ratio 0.125`
- `--tile-preview-grid 3`
