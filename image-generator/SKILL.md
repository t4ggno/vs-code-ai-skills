---
name: image-generator
description: Generates an image with gpt-image-1.5, shows progress heartbeats while waiting, evaluates the result with GPT-5.4 vision, and supports size, quality, moderation, background, and output format options.
---

# Image Generation Skill

When the user asks to generate an image for the project, follow these steps:

1. Identify the requested image subject, style, size requirements, background needs, and target destination folder.
2. Define the project's design criteria based on the request.
3. Verify that the user has an `OPENAI_API_KEY` set in their environment variables. Note: If the user explicitly mentions restarting to fix the token, you can proceed without strictly checking from outside, but be ready to show the execution output. Also, check if the `openai` and `requests` Python packages are installed in the current environment. If not, install them first.
4. Run the generator script in the terminal. The script uses an argparse interface and defaults to `dall-e-3` or `gpt-image-1.5` based on your provided arguments.
5. Use the script arguments to match the requested output:

   ```bash
   python ~\.copilot\skills\image-generator\generate.py "PROMPT" "FOLDER_PATH" "CRITERIA" --model gpt-image-1.5 --size 1024x1024 --quality standard --moderation low --background opaque --output-format png --poll-interval 2 --timeout 180 --vision-model gpt-5.4
   ```

6. Watch the terminal output for progress updates such as elapsed-time heartbeats during generation, revised prompts, evaluation start, and final success or mismatch results.
7. If the script returns a design mismatch, use the reason to refine the prompt or criteria and retry up to 3 times.
8. Prefer these defaults unless the task needs something else:
   - `--model gpt-image-1.5`
   - `--moderation low`
   - `--size 1024x1024`
   - `--quality standard`
   - `--background opaque`
   - `--output-format png`
   - `--vision-model gpt-5.4`
