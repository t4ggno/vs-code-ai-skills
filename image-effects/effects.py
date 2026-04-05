from __future__ import annotations

import argparse
import sys
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageColor, ImageEnhance, ImageFilter, ImageOps

RESAMPLING = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
ROTATE_RESAMPLING = Image.Resampling.BICUBIC if hasattr(Image, "Resampling") else Image.BICUBIC
OUTPUT_ALIASES = {
    ".jpg": "jpeg",
    ".jpeg": "jpeg",
    ".png": "png",
    ".webp": "webp",
    ".avif": "avif",
    ".gif": "gif",
    ".bmp": "bmp",
    ".tif": "tiff",
    ".tiff": "tiff",
}
FORMATS_WITHOUT_ALPHA = {"jpeg"}
SESSION_CACHE: dict[str, Any] = {}


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def detect_output_format(path: Path) -> str:
    output_format = OUTPUT_ALIASES.get(path.suffix.lower())
    if output_format is None:
        supported = ", ".join(sorted(alias.lstrip(".") for alias in OUTPUT_ALIASES))
        raise ValueError(f"Unsupported output format '{path.suffix}'. Supported extensions: {supported}.")
    return output_format


def parse_size(value: str) -> tuple[int, int]:
    parts = value.lower().split("x", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid size '{value}'. Expected WIDTHxHEIGHT.")

    width = int(parts[0])
    height = int(parts[1])
    if width < 1 or height < 1:
        raise ValueError(f"Invalid size '{value}'. Dimensions must be positive.")
    return width, height


def parse_background_color(value: str | None) -> tuple[int, int, int, int] | None:
    if value is None:
        return None
    if value.lower() == "transparent":
        return (0, 0, 0, 0)

    color = ImageColor.getrgb(value)
    if len(color) == 4:
        return color
    return color + (255,)


def get_rembg_api():
    try:
        from rembg import new_session, remove
    except ImportError as exc:
        raise RuntimeError(
            "Background removal requires rembg. Use Python 3.12/3.11 and install the workspace requirements first."
        ) from exc
    return remove, new_session


def get_rembg_session(model_name: str):
    session = SESSION_CACHE.get(model_name)
    if session is not None:
        return session

    _remove, new_session = get_rembg_api()
    session = new_session(model_name)
    SESSION_CACHE[model_name] = session
    return session


def coerce_pil_image(value: Any) -> Image.Image:
    if isinstance(value, Image.Image):
        return value
    if isinstance(value, (bytes, bytearray)):
        image = Image.open(BytesIO(value))
        image.load()
        return image
    raise TypeError(f"Unsupported image result type: {type(value)!r}")


def remove_background_with_rembg(image: Image.Image, args: argparse.Namespace) -> Image.Image:
    remove, _new_session = get_rembg_api()
    session = get_rembg_session(args.bg_model)
    result = remove(
        image,
        session=session,
        only_mask=args.only_mask,
        post_process_mask=args.post_process_mask,
    )
    return coerce_pil_image(result)


def apply_sepia(image: Image.Image) -> Image.Image:
    alpha = image.getchannel("A") if "A" in image.getbands() else None
    grayscale = ImageOps.grayscale(image.convert("RGB"))
    sepia = ImageOps.colorize(grayscale, "#704214", "#C0A080")
    if alpha is not None:
        sepia = sepia.convert("RGBA")
        sepia.putalpha(alpha)
    return sepia


def invert_image(image: Image.Image) -> Image.Image:
    if "A" not in image.getbands():
        return ImageOps.invert(image.convert("RGB"))

    alpha = image.getchannel("A")
    inverted = ImageOps.invert(image.convert("RGB")).convert("RGBA")
    inverted.putalpha(alpha)
    return inverted


def grayscale_with_alpha(image: Image.Image) -> Image.Image:
    alpha = image.getchannel("A") if "A" in image.getbands() else None
    grayscale = ImageOps.grayscale(image.convert("RGB"))
    if alpha is not None:
        grayscale = grayscale.convert("RGBA")
        grayscale.putalpha(alpha)
    return grayscale


def trim_transparent_bounds(image: Image.Image) -> Image.Image:
    rgba_image = image.convert("RGBA")
    bounds = rgba_image.getbbox()
    if bounds is None:
        return rgba_image
    return rgba_image.crop(bounds)


def apply_background(image: Image.Image, background: tuple[int, int, int, int]) -> Image.Image:
    rgba_image = image.convert("RGBA")
    base = Image.new("RGBA", rgba_image.size, background)
    return Image.alpha_composite(base, rgba_image)


def enhance_rgb_image(image: Image.Image, enhancer_factory, factor: float) -> Image.Image:
    if "A" not in image.getbands():
        return enhancer_factory(image).enhance(factor)

    alpha = image.getchannel("A")
    enhanced = enhancer_factory(image.convert("RGB")).enhance(factor).convert("RGBA")
    enhanced.putalpha(alpha)
    return enhanced


def apply_rgb_operation(image: Image.Image, operation) -> Image.Image:
    if "A" not in image.getbands():
        base_image = image if image.mode in {"L", "RGB"} else image.convert("RGB")
        return operation(base_image)

    alpha = image.getchannel("A")
    processed = operation(image.convert("RGB")).convert("RGBA")
    processed.putalpha(alpha)
    return processed


def save_image(output_path: Path, image: Image.Image, target_format: str, args: argparse.Namespace) -> None:
    save_kwargs: dict[str, object] = {}
    if target_format == "jpeg":
        save_kwargs.update({"quality": clamp(args.quality, 0, 95), "optimize": True, "progressive": True})
    elif target_format == "png":
        save_kwargs.update({"optimize": True, "compress_level": 6})
    elif target_format == "webp":
        save_kwargs.update({"quality": clamp(args.quality, 0, 100), "lossless": args.lossless})
    elif target_format == "avif":
        save_kwargs.update({"quality": clamp(args.quality, 0, 100), "speed": 6})

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format=target_format.upper() if target_format != "jpeg" else "JPEG", **save_kwargs)


def apply_effects(input_path: Path, output_path: Path, args: argparse.Namespace) -> Path:
    target_format = detect_output_format(output_path)
    image = Image.open(input_path)
    try:
        working = ImageOps.exif_transpose(image)

        if args.remove_background:
            working = remove_background_with_rembg(working, args)

        if args.trim_transparent:
            working = trim_transparent_bounds(working)

        if args.resize is not None:
            working = working.resize(args.resize, RESAMPLING)

        if args.rotate is not None:
            working = working.rotate(args.rotate, expand=True, resample=ROTATE_RESAMPLING)

        if args.grayscale:
            working = grayscale_with_alpha(working)

        if args.sepia:
            working = apply_sepia(working)

        if args.autocontrast:
            working = apply_rgb_operation(working, ImageOps.autocontrast)

        if args.invert:
            working = invert_image(working)

        if args.blur > 0:
            working = working.filter(ImageFilter.GaussianBlur(args.blur))

        if args.sharpen != 1.0:
            working = enhance_rgb_image(working, ImageEnhance.Sharpness, args.sharpen)

        if args.brightness != 1.0:
            working = enhance_rgb_image(working, ImageEnhance.Brightness, args.brightness)

        if args.contrast != 1.0:
            working = enhance_rgb_image(working, ImageEnhance.Contrast, args.contrast)

        if args.saturation != 1.0:
            working = enhance_rgb_image(working, ImageEnhance.Color, args.saturation)

        if args.background_rgba is not None:
            working = apply_background(working, args.background_rgba)

        if target_format in FORMATS_WITHOUT_ALPHA and "A" in working.getbands():
            fallback_background = args.background_rgba or (255, 255, 255, 255)
            working = apply_background(working, fallback_background).convert("RGB")

        save_image(output_path, working, target_format, args)
        return output_path
    finally:
        image.close()


def validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        parser.error(f"Input file does not exist: {input_path}")
    if input_path.resolve() == output_path.resolve():
        parser.error("Input and output paths must be different.")
    if args.blur < 0:
        parser.error("--blur must be 0 or greater.")
    if args.sharpen <= 0:
        parser.error("--sharpen must be greater than 0.")
    if args.brightness <= 0:
        parser.error("--brightness must be greater than 0.")
    if args.contrast <= 0:
        parser.error("--contrast must be greater than 0.")
    if args.saturation <= 0:
        parser.error("--saturation must be greater than 0.")
    if args.only_mask and not args.remove_background:
        parser.error("--only-mask requires --remove-background.")
    if output_path.exists() and not args.overwrite:
        parser.error(f"Output file already exists: {output_path}. Use --overwrite to replace it.")

    detect_output_format(output_path)
    args.resize = parse_size(args.resize) if args.resize else None
    args.background_rgba = parse_background_color(args.background_color)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Apply local image effects and optional background removal.")
    parser.add_argument("input", help="Input image path")
    parser.add_argument("output", help="Output image path")
    parser.add_argument("--remove-background", action="store_true", dest="remove_background", help="Remove the image background locally using rembg")
    parser.add_argument("--bg-model", default="birefnet-general", dest="bg_model", help="rembg model name for background removal")
    parser.add_argument("--only-mask", action="store_true", dest="only_mask", help="Return only the background mask")
    parser.add_argument("--post-process-mask", action="store_true", dest="post_process_mask", help="Post-process the generated mask when supported")
    parser.add_argument("--trim-transparent", action="store_true", dest="trim_transparent", help="Trim transparent borders after effects")
    parser.add_argument("--background-color", dest="background_color", help="Composite the image onto this color after processing")
    parser.add_argument("--resize", help="Resize output to WIDTHxHEIGHT")
    parser.add_argument("--rotate", type=float, help="Rotate the image by this many degrees")
    parser.add_argument("--grayscale", action="store_true", help="Convert the image to grayscale")
    parser.add_argument("--sepia", action="store_true", help="Apply a sepia tone")
    parser.add_argument("--autocontrast", action="store_true", help="Apply automatic contrast correction")
    parser.add_argument("--invert", action="store_true", help="Invert the image colors")
    parser.add_argument("--blur", type=float, default=0.0, help="Gaussian blur radius (default: 0)")
    parser.add_argument("--sharpen", type=float, default=1.0, help="Sharpness factor (default: 1.0)")
    parser.add_argument("--brightness", type=float, default=1.0, help="Brightness factor (default: 1.0)")
    parser.add_argument("--contrast", type=float, default=1.0, help="Contrast factor (default: 1.0)")
    parser.add_argument("--saturation", type=float, default=1.0, help="Color saturation factor (default: 1.0)")
    parser.add_argument("--quality", type=int, default=90, help="Quality for lossy output formats")
    parser.add_argument("--lossless", action="store_true", help="Use lossless mode when supported (for example WEBP)")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite the output file if it already exists")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        validate_args(parser, args)
        output_path = apply_effects(Path(args.input), Path(args.output), args)
    except SystemExit:
        raise
    except Exception as exc:
        print(f"Image effects failed: {exc}", file=sys.stderr)
        return 1

    print(f"Success! Image saved to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
