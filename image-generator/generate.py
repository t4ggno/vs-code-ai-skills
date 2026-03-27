import argparse
import base64
import os
import sys
from io import BytesIO
from pathlib import Path

import requests
from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image

RESAMPLING = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS

TILEABLE_PROMPT_SUFFIX = (
    "Create a seamless, tileable texture that can repeat infinitely for surfaces like "
    "walls, floors, and terrain. Keep the lighting even and material-focused, avoid "
    "perspective distortion, borders, frames, text, logos, and isolated focal objects, "
    "and make sure the left/right and top/bottom edges remain visually compatible when tiled."
)

TILEABLE_CRITERIA_SUFFIX = (
    "When repeated in a 3x3 grid, there must be no visible seams, broken edge transitions, "
    "or lighting discontinuities. The texture should feel like a repeating material sample, "
    "not a standalone illustration."
)


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def normalize_output_format(output_format):
    normalized = output_format.lower()
    if normalized == "jpg":
        return "JPEG"
    return normalized.upper()


def get_mime_subtype(output_format):
    normalized = output_format.lower()
    if normalized == "jpg":
        return "jpeg"
    return normalized


def extract_generated_image(image_result, timeout):
    if getattr(image_result, "b64_json", None):
        return base64.b64decode(image_result.b64_json)

    image_url = getattr(image_result, "url", None)
    if not image_url:
        raise RuntimeError("Image generation did not return a downloadable image payload.")

    print(f"Image generated! Downloading from {image_url}...")
    response = requests.get(image_url, timeout=timeout)
    response.raise_for_status()
    return response.content


def blend_pixel_pair(left_pixel, right_pixel, weight):
    blended_left = []
    blended_right = []
    for left_channel, right_channel in zip(left_pixel, right_pixel):
        midpoint = (left_channel + right_channel) / 2
        left_value = round((1 - weight) * left_channel + weight * midpoint)
        right_value = round((1 - weight) * right_channel + weight * midpoint)
        blended_left.append(max(0, min(255, left_value)))
        blended_right.append(max(0, min(255, right_value)))
    return tuple(blended_left), tuple(blended_right)


def apply_tileable_postprocess(image, blend_ratio):
    width, height = image.size
    band_x = max(1, min(width // 2, int(width * clamp(blend_ratio, 0.01, 0.5))))
    band_y = max(1, min(height // 2, int(height * clamp(blend_ratio, 0.01, 0.5))))

    horizontal = image.copy()
    source_pixels = image.load()
    horizontal_pixels = horizontal.load()

    for offset in range(band_x):
        weight = 1 - (offset / band_x)
        right_x = width - 1 - offset
        for y in range(height):
            blended_left, blended_right = blend_pixel_pair(source_pixels[offset, y], source_pixels[right_x, y], weight)
            horizontal_pixels[offset, y] = blended_left
            horizontal_pixels[right_x, y] = blended_right

    result = horizontal.copy()
    horizontal_source = horizontal.load()
    result_pixels = result.load()

    for offset in range(band_y):
        weight = 1 - (offset / band_y)
        bottom_y = height - 1 - offset
        for x in range(width):
            blended_top, blended_bottom = blend_pixel_pair(horizontal_source[x, offset], horizontal_source[x, bottom_y], weight)
            result_pixels[x, offset] = blended_top
            result_pixels[x, bottom_y] = blended_bottom

    return result


def create_tile_preview(image, grid_size):
    preview_grid = max(2, grid_size)
    preview_tile = image
    max_preview_side = 256
    largest_side = max(image.size)

    if largest_side > max_preview_side:
        scale = max_preview_side / largest_side
        preview_tile = image.resize(
            (max(1, int(image.width * scale)), max(1, int(image.height * scale))),
            RESAMPLING,
        )

    preview = Image.new(preview_tile.mode, (preview_tile.width * preview_grid, preview_tile.height * preview_grid))
    for row in range(preview_grid):
        for column in range(preview_grid):
            preview.paste(preview_tile, (column * preview_tile.width, row * preview_tile.height))
    return preview


def encode_image(image, output_format):
    buffer = BytesIO()
    save_image(image, buffer, output_format)
    return buffer.getvalue()


def save_image(image, destination, output_format):
    normalized_format = normalize_output_format(output_format)
    image_to_save = image.convert("RGB") if normalized_format == "JPEG" else image
    image_to_save.save(destination, format=normalized_format)


def build_generation_prompt(prompt, criteria, tileable):
    prompt_text = prompt.strip()
    criteria_text = build_effective_criteria(criteria, tileable)
    if tileable:
        prompt_text = f"{prompt_text}. {TILEABLE_PROMPT_SUFFIX}"
    return (
        f"Create an image matching this request: {prompt_text}. "
        f"Ensure it strictly follows these criteria: {criteria_text}"
    )


def build_effective_criteria(criteria, tileable):
    criteria_text = criteria.strip()
    if not tileable:
        return criteria_text
    return f"{criteria_text}. {TILEABLE_CRITERIA_SUFFIX}"


def build_evaluation_prompt(criteria, tileable, preview_grid):
    if not tileable:
        return (
            f"Analyze this image. Does it strictly meet the following design criteria: '{criteria}'? "
            "Reply ONLY with 'YES' or 'NO: [Reason]'."
        )

    return (
        f"Analyze the source tile and the {preview_grid}x{preview_grid} tiled preview. "
        f"Does the texture strictly meet these criteria: '{criteria}'? "
        "Pay special attention to visible seams, edge continuity, repeating highlights, and border artifacts. "
        "Reply ONLY with 'YES' or 'NO: [Reason]'."
    )


def load_openai_api_key():
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        return api_key

    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=False)

    return os.environ.get("OPENAI_API_KEY")


def main():
    parser = argparse.ArgumentParser(description="Generate and evaluate an image using OpenAI.")
    parser.add_argument("prompt", help="The prompt for the image generation")
    parser.add_argument("folder", help="Target destination folder")
    parser.add_argument("criteria", help="Criteria for evaluation")
    parser.add_argument("--model", default="dall-e-3", help="Image generation model to use")
    parser.add_argument("--size", default="1024x1024", help="Size of the image")
    parser.add_argument("--quality", default="standard", help="Quality of the image")
    parser.add_argument("--moderation", default="low", help="Moderation setting")
    parser.add_argument("--background", default="opaque", help="Background setting")
    parser.add_argument("--output-format", default="png", dest="output_format")
    parser.add_argument("--tileable", "--seamless-tile", action="store_true", dest="tileable")
    parser.add_argument("--tile-blend-ratio", type=float, default=0.125, dest="tile_blend_ratio")
    parser.add_argument("--tile-preview-grid", type=int, default=3, dest="tile_preview_grid")
    parser.add_argument("--poll-interval", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--vision-model", default="gpt-5.4", dest="vision_model")

    args = parser.parse_args()

    api_key = load_openai_api_key()
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable is missing.", file=sys.stderr)
        print("Please set it in your environment or add it to the workspace .env file.", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=api_key)
    prompt_text = build_generation_prompt(args.prompt, args.criteria, args.tileable)
    effective_criteria = build_effective_criteria(args.criteria, args.tileable)

    print(f"Generating image with model '{args.model}'...")
    try:
        response = client.images.generate(
            model=args.model,
            prompt=prompt_text,
            n=1,
            size=args.size
        )
    except Exception as e:
        print(f"Generation failed: {e}", file=sys.stderr)
        sys.exit(1)

    image_result = response.data[0]
    revised_prompt = getattr(image_result, "revised_prompt", None)
    if revised_prompt:
        print(f"Model revised prompt: {revised_prompt}")

    try:
        image_data = extract_generated_image(image_result, args.timeout)
    except Exception as e:
        print(f"Downloading image failed: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        generated_image = Image.open(BytesIO(image_data)).convert("RGBA")
    except Exception as e:
        print(f"Processing image failed: {e}", file=sys.stderr)
        sys.exit(1)

    if args.tileable:
        print("Applying seamless tile post-processing...")
        generated_image = apply_tileable_postprocess(generated_image, args.tile_blend_ratio)

    try:
        output_image_data = encode_image(generated_image, args.output_format)
    except Exception as e:
        print(f"Encoding output image failed: {e}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(args.folder, exist_ok=True)
    image_path = os.path.join(args.folder, f"generated_image.{args.output_format}")

    with open(image_path, "wb") as f:
        f.write(output_image_data)

    preview_path = None
    preview_image_data = None
    if args.tileable:
        try:
            preview_image = create_tile_preview(generated_image, args.tile_preview_grid)
            preview_image_data = encode_image(preview_image, args.output_format)
            preview_path = os.path.join(args.folder, f"generated_image_tiled_preview.{args.output_format}")
            with open(preview_path, "wb") as f:
                f.write(preview_image_data)
        except Exception as e:
            print(f"Building tile preview failed: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"Evaluating image using '{args.vision_model}' against criteria: '{effective_criteria}'")
    base64_image = base64.b64encode(output_image_data).decode('utf-8')
    mime_subtype = get_mime_subtype(args.output_format)
    content = [
        {
            "type": "text",
            "text": build_evaluation_prompt(effective_criteria, args.tileable, args.tile_preview_grid),
        },
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/{mime_subtype};base64,{base64_image}"},
        },
    ]

    if preview_image_data:
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/{mime_subtype};base64,{base64.b64encode(preview_image_data).decode('utf-8')}"
                },
            }
        )

    try:
        vision_eval = client.chat.completions.create(
            model=args.vision_model,
            messages=[
                {
                    "role": "user",
                    "content": content
                }
            ]
        )
        evaluation = vision_eval.choices[0].message.content
    except Exception as e:
        print(f"Evaluation request failed: {e}", file=sys.stderr)
        sys.exit(1)

    if evaluation.startswith("NO"):
        print(f"Design mismatch: {evaluation}")
        sys.exit(1)

    if preview_path:
        print(f"Success! Tile saved to {image_path} and tiled preview saved to {preview_path}")
        return

    print(f"Success! Image saved to {image_path}")

if __name__ == "__main__":
    main()
