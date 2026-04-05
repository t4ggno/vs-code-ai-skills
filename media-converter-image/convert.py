from __future__ import annotations

import argparse
import shutil
import sys
from io import BytesIO
from pathlib import Path
from typing import Sequence

from PIL import Image, ImageColor, ImageOps, ImageSequence, UnidentifiedImageError, features

RESAMPLING = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS

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
    ".ico": "ico",
    ".icns": "icns",
    ".svg": "svg",
}
PILLOW_FORMATS = {
    "jpeg": "JPEG",
    "png": "PNG",
    "webp": "WEBP",
    "avif": "AVIF",
    "gif": "GIF",
    "bmp": "BMP",
    "tiff": "TIFF",
    "ico": "ICO",
    "icns": "ICNS",
}
SEQUENCE_OUTPUT_FORMATS = {"png", "gif", "webp", "avif", "tiff"}
FORMATS_WITHOUT_ALPHA = {"jpeg"}
FEATURE_FLAGS = {"webp": "webp", "avif": "avif"}
ICON_DEFAULT_SIZES = [
    (16, 16),
    (24, 24),
    (32, 32),
    (48, 48),
    (64, 64),
    (128, 128),
    (256, 256),
]


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def detect_output_format(path: Path) -> str:
    output_format = OUTPUT_ALIASES.get(path.suffix.lower())
    if output_format is None:
        supported = ", ".join(sorted(alias.lstrip(".") for alias in OUTPUT_ALIASES))
        raise ValueError(f"Unsupported output format '{path.suffix}'. Supported extensions: {supported}.")
    return output_format


def parse_size_token(value: str) -> tuple[int, int]:
    parts = value.lower().split("x", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid size '{value}'. Expected WIDTHxHEIGHT.")

    width = int(parts[0])
    height = int(parts[1])
    if width < 1 or height < 1:
        raise ValueError(f"Invalid size '{value}'. Dimensions must be positive.")
    return width, height


def parse_icon_sizes(values: Sequence[str] | None) -> list[tuple[int, int]]:
    if not values:
        return []
    return [parse_size_token(value) for value in values]


def parse_background_color(value: str) -> tuple[int, int, int, int]:
    if value.lower() == "transparent":
        return (0, 0, 0, 0)

    color = ImageColor.getrgb(value)
    if len(color) == 4:
        return color
    return color + (255,)


def pillow_feature_is_available(flag: str) -> bool:
    try:
        return bool(features.check(flag))
    except Exception:
        return False


def ensure_output_support(target_format: str) -> None:
    if target_format == "svg":
        return

    feature_flag = FEATURE_FLAGS.get(target_format)
    if feature_flag and not pillow_feature_is_available(feature_flag):
        raise RuntimeError(
            f"Pillow in this environment cannot write {target_format.upper()} files. "
            f"Install the needed codec support or choose another target format."
        )


def filter_icon_sizes(image_size: tuple[int, int], requested: Sequence[tuple[int, int]]) -> list[tuple[int, int]]:
    sizes = list(requested) if requested else list(ICON_DEFAULT_SIZES)
    filtered = [
        size
        for size in sizes
        if size[0] <= image_size[0] and size[1] <= image_size[1] and max(size) <= 256
    ]

    if filtered:
        return filtered

    fallback_side = min(image_size[0], image_size[1], 256)
    return [(fallback_side, fallback_side)]


def flatten_alpha(image: Image.Image, background: tuple[int, int, int, int]) -> Image.Image:
    rgba_image = image.convert("RGBA")
    base = Image.new("RGBA", rgba_image.size, background)
    composited = Image.alpha_composite(base, rgba_image)
    return composited.convert("RGB")


def prepare_frame(image: Image.Image, target_format: str, background: tuple[int, int, int, int]) -> Image.Image:
    prepared = ImageOps.exif_transpose(image.copy())

    if target_format in FORMATS_WITHOUT_ALPHA:
        return flatten_alpha(prepared, background)

    if target_format in {"ico", "icns", "gif"}:
        return prepared.convert("RGBA")

    if prepared.mode not in {"1", "L", "LA", "P", "RGB", "RGBA", "CMYK"}:
        return prepared.convert("RGBA")

    return prepared


def rasterize_svg_to_png_bytes(input_path: Path, args: argparse.Namespace) -> bytes:
    try:
        import cairosvg
    except ImportError as exc:
        raise RuntimeError(
            "SVG input requires CairoSVG. Install the dependency and, on Windows, make sure the Cairo runtime is available."
        ) from exc

    render_kwargs: dict[str, object] = {"url": str(input_path)}
    if args.svg_dpi is not None:
        render_kwargs["dpi"] = args.svg_dpi
    if args.svg_scale != 1.0:
        render_kwargs["scale"] = args.svg_scale
    if args.output_width is not None:
        render_kwargs["output_width"] = args.output_width
    if args.output_height is not None:
        render_kwargs["output_height"] = args.output_height

    return cairosvg.svg2png(**render_kwargs)


def load_image_source(input_path: Path, args: argparse.Namespace) -> Image.Image:
    if input_path.suffix.lower() == ".svg":
        png_bytes = rasterize_svg_to_png_bytes(input_path, args)
        image = Image.open(BytesIO(png_bytes))
        image.load()
        return image

    try:
        return Image.open(input_path)
    except UnidentifiedImageError as exc:
        raise RuntimeError(f"Could not identify image file: {input_path}") from exc


def collect_frames(
    image: Image.Image,
    target_format: str,
    args: argparse.Namespace,
) -> tuple[list[Image.Image], list[int]]:
    if not getattr(image, "is_animated", False) or not args.all_frames or target_format not in SEQUENCE_OUTPUT_FORMATS:
        frame_duration = args.duration if args.duration is not None else int(getattr(image, "info", {}).get("duration", 100))
        return [prepare_frame(image, target_format, args.background_rgba)], [frame_duration]

    frames: list[Image.Image] = []
    durations: list[int] = []
    for frame in ImageSequence.Iterator(image):
        frames.append(prepare_frame(frame, target_format, args.background_rgba))
        durations.append(args.duration if args.duration is not None else int(frame.info.get("duration", 100)))

    return frames, durations


def build_save_kwargs(
    target_format: str,
    frames: Sequence[Image.Image],
    durations: Sequence[int],
    args: argparse.Namespace,
) -> dict[str, object]:
    kwargs: dict[str, object] = {}

    if target_format == "jpeg":
        kwargs.update({"quality": clamp(args.quality, 0, 95), "optimize": True, "progressive": True})
    elif target_format == "png":
        kwargs.update({"optimize": True, "compress_level": 6})
    elif target_format == "webp":
        kwargs.update({"quality": clamp(args.quality, 0, 100), "lossless": args.lossless})
    elif target_format == "avif":
        kwargs.update({"quality": clamp(args.quality, 0, 100), "speed": 6})
    elif target_format == "ico":
        kwargs["sizes"] = filter_icon_sizes(frames[0].size, args.icon_sizes)
    elif target_format == "icns" and args.icon_sizes:
        resized = [frames[0].resize(size, RESAMPLING) for size in args.icon_sizes if size != frames[0].size]
        if resized:
            kwargs["append_images"] = resized

    if len(frames) > 1 and target_format in SEQUENCE_OUTPUT_FORMATS:
        kwargs.update(
            {
                "save_all": True,
                "append_images": list(frames[1:]),
                "duration": list(durations),
                "loop": args.loop,
            }
        )
        if target_format == "gif":
            kwargs["optimize"] = True

    return kwargs


def convert_image(input_path: Path, output_path: Path, args: argparse.Namespace) -> Path:
    if input_path.resolve() == output_path.resolve():
        raise ValueError("Input and output paths must be different.")

    target_format = detect_output_format(output_path)
    ensure_output_support(target_format)

    if target_format == "svg":
        if input_path.suffix.lower() != ".svg":
            raise ValueError("Raster-to-SVG conversion is not supported. Use a vector tracing workflow instead.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(input_path, output_path)
        return output_path

    image = load_image_source(input_path, args)
    try:
        frames, durations = collect_frames(image, target_format, args)
        save_kwargs = build_save_kwargs(target_format, frames, durations, args)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        frames[0].save(output_path, format=PILLOW_FORMATS[target_format], **save_kwargs)
        return output_path
    finally:
        image.close()


def validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        parser.error(f"Input file does not exist: {input_path}")
    if args.quality < 0 or args.quality > 100:
        parser.error("--quality must be between 0 and 100.")
    if args.loop < -1:
        parser.error("--loop must be -1 or greater.")

    args.icon_sizes = parse_icon_sizes(args.sizes)
    args.background_rgba = parse_background_color(args.background)

    target_format = detect_output_format(output_path)
    if target_format == "jpeg" and args.background_rgba[3] < 255:
        parser.error("JPEG output requires an opaque --background color.")
    if (args.output_width is not None or args.output_height is not None) and input_path.suffix.lower() != ".svg":
        parser.error("--output-width and --output-height are only used for SVG rasterization input.")
    if output_path.exists() and not args.overwrite:
        parser.error(f"Output file already exists: {output_path}. Use --overwrite to replace it.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert common image formats locally.")
    parser.add_argument("input", help="Input image path")
    parser.add_argument("output", help="Output image path")
    parser.add_argument("--quality", type=int, default=90, help="Quality for lossy formats (default: 90)")
    parser.add_argument("--lossless", action="store_true", help="Use lossless mode when supported (for example WEBP)")
    parser.add_argument("--background", default="#ffffff", help="Background color for formats without alpha support")
    parser.add_argument("--sizes", nargs="*", help="Icon sizes for ICO/ICNS output, for example 16x16 32x32 256x256")
    parser.add_argument("--all-frames", action="store_true", help="Preserve animation frames when the target format supports it")
    parser.add_argument("--duration", type=int, help="Frame duration in milliseconds for animated output")
    parser.add_argument("--loop", type=int, default=0, help="Animation loop count; 0 means infinite where supported")
    parser.add_argument("--svg-dpi", type=int, default=96, dest="svg_dpi", help="DPI to use when rasterizing SVG input")
    parser.add_argument("--svg-scale", type=float, default=1.0, dest="svg_scale", help="Scale factor for SVG rasterization")
    parser.add_argument("--output-width", type=int, dest="output_width", help="Explicit rasterized width for SVG input")
    parser.add_argument("--output-height", type=int, dest="output_height", help="Explicit rasterized height for SVG input")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite the output file if it already exists")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        validate_args(parser, args)
        output_path = convert_image(Path(args.input), Path(args.output), args)
    except SystemExit:
        raise
    except Exception as exc:
        print(f"Conversion failed: {exc}", file=sys.stderr)
        return 1

    print(f"Success! Converted image saved to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
