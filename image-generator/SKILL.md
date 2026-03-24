---
name: image-generator
description: Generates images and seamless tileable textures with OpenAI image models, evaluates them with GPT-5.4 vision, and supports output tuning such as size, quality, moderation, background, and format options.
---

# Image Generation Skill

When the user asks to generate an image for the project, follow these steps:

1. Identify the requested image subject, style, size requirements, background needs, destination folder, and whether the user needs a normal image or a seamless repeating texture tile.
2. Define design criteria based on the request. For seamless tiles, explicitly require a material-like texture that repeats cleanly on all four edges with no seams when tiled.
3. Verify that the user has an `OPENAI_API_KEY` set in their environment variables. Note: If the user explicitly mentions restarting to fix the token, you can proceed without strictly checking from outside, but be ready to show the execution output. Also, check if the `openai`, `requests`, and `pillow` Python packages are installed in the current environment. If not, install them first.
4. Run the generator script in the terminal. The script uses an argparse interface and defaults to `dall-e-3` or `gpt-image-1.5` based on your provided arguments.
5. Use the script arguments to match the requested output:

   ```bash
   python ~/.copilot/skills/image-generator/generate.py "PROMPT" "FOLDER_PATH" "CRITERIA" --model gpt-image-1.5 --size 1024x1024 --quality standard --moderation low --background opaque --output-format png --poll-interval 2 --timeout 180 --vision-model gpt-5.4
   ```

6. For seamless tiles, add `--tileable`. The script will post-process opposite edges to improve wrap continuity, save the base tile, build a tiled preview grid, and evaluate both the tile and the preview.

   Example:

   ```bash
   python ~/.copilot/skills/image-generator/generate.py "Worn basalt dungeon floor with subtle cracks and dusty grout" "assets/textures/floors" "Game-ready seamless floor material, readable at a distance, medium detail, no text, no perspective" --model gpt-image-1.5 --size 1024x1024 --tileable --tile-blend-ratio 0.125 --tile-preview-grid 3 --output-format png --vision-model gpt-5.4
   ```

7. Use these best practices for seamless tile prompts:
   - Ask for a **material sample**, not a scene illustration.
   - Prefer **flat or evenly distributed lighting** and avoid dramatic shadows.
   - Avoid **borders, frames, logos, text, and singular focal objects** near the center or edges.
   - Prefer **top-down or front-on material views** without perspective distortion.
   - For larger surfaces with less obvious repetition, consider generating multiple companion tiles or using a nonperiodic set such as Wang tiles outside this skill.

8. Watch the terminal output for revised prompts, tile post-processing, preview creation, evaluation start, and final success or mismatch results.
9. If the script returns a design mismatch, use the reason to refine the prompt or criteria and retry up to 3 times.
10. Prefer these defaults unless the task needs something else:
   - `--model gpt-image-1.5`
   - `--moderation low`
   - `--size 1024x1024`
   - `--quality standard`
   - `--background opaque`
   - `--output-format png`
   - `--vision-model gpt-5.4`
   - `--tile-blend-ratio 0.125` for seamless texture work
   - `--tile-preview-grid 3` for seam inspection
