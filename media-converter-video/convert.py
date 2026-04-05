from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

OUTPUT_ALIASES = {
    ".mp4": "mp4",
    ".webm": "webm",
    ".mov": "mov",
    ".mkv": "mkv",
    ".avi": "avi",
    ".gif": "gif",
    ".apng": "apng",
}
FORMATS_WITHOUT_AUDIO = {"gif", "apng"}


def detect_output_format(path: Path) -> str:
    output_format = OUTPUT_ALIASES.get(path.suffix.lower())
    if output_format is None:
        supported = ", ".join(sorted(alias.lstrip(".") for alias in OUTPUT_ALIASES))
        raise ValueError(f"Unsupported output format '{path.suffix}'. Supported extensions: {supported}.")
    return output_format


def format_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:g}"


def load_imageio_ffmpeg_module():
    try:
        import imageio_ffmpeg
    except ImportError:
        return None
    return imageio_ffmpeg


def resolve_ffmpeg_executable() -> str:
    imageio_ffmpeg = load_imageio_ffmpeg_module()
    if imageio_ffmpeg is not None:
        try:
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass

    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    raise RuntimeError(
        "Could not find FFmpeg. Install imageio-ffmpeg or make sure a system ffmpeg executable is on PATH."
    )


def build_scale_filter(width: int | None, height: int | None) -> str | None:
    if width and height:
        return f"scale=w={width}:h={height}:force_original_aspect_ratio=decrease"
    if width:
        return f"scale=w={width}:h=-2"
    if height:
        return f"scale=w=-2:h={height}"
    return None


def build_base_filters(args: argparse.Namespace) -> list[str]:
    filters: list[str] = []
    if args.fps is not None:
        filters.append(f"fps={format_number(args.fps)}")

    scale_filter = build_scale_filter(args.width, args.height)
    if scale_filter:
        filters.append(scale_filter)

    return filters


def build_gif_filter(args: argparse.Namespace) -> str:
    filters = build_base_filters(args)
    if not any(filter_part.startswith("fps=") for filter_part in filters):
        filters.insert(0, "fps=15")
    if not any(filter_part.startswith("scale=") for filter_part in filters):
        filters.append("scale=w=iw:h=ih:flags=lanczos")

    base_chain = ",".join(filters)
    return (
        f"{base_chain},split[s0][s1];"
        "[s0]palettegen=stats_mode=single[p];"
        "[s1][p]paletteuse=dither=sierra2_4a"
    )


def build_standard_output_args(target_format: str, args: argparse.Namespace) -> list[str]:
    output_args: list[str] = []
    base_filters = build_base_filters(args)
    if base_filters:
        output_args.extend(["-vf", ",".join(base_filters)])

    if target_format == "mp4":
        output_args.extend(["-c:v", args.video_codec or "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart"])
        if not args.video_codec:
            output_args.extend(["-preset", args.preset, "-crf", str(args.crf or 23)])
    elif target_format == "webm":
        output_args.extend(["-c:v", args.video_codec or "libvpx-vp9", "-pix_fmt", "yuv420p"])
        if not args.video_codec:
            output_args.extend(["-row-mt", "1", "-crf", str(args.crf or 32), "-b:v", args.video_bitrate or "0"])
    elif target_format == "mov":
        output_args.extend(["-c:v", args.video_codec or "libx264", "-pix_fmt", "yuv420p"])
        if not args.video_codec:
            output_args.extend(["-preset", args.preset, "-crf", str(args.crf or 23)])
    elif target_format == "mkv":
        output_args.extend(["-c:v", args.video_codec or "libx264", "-pix_fmt", "yuv420p"])
        if not args.video_codec:
            output_args.extend(["-preset", args.preset, "-crf", str(args.crf or 23)])
    elif target_format == "avi":
        output_args.extend(["-c:v", args.video_codec or "mpeg4"])
        if not args.video_codec and args.video_bitrate:
            output_args.extend(["-b:v", args.video_bitrate])
    else:
        raise ValueError(f"Unsupported standard video output format: {target_format}")

    if target_format != "avi" and args.video_bitrate and not (target_format == "webm" and not args.video_codec):
        output_args.extend(["-b:v", args.video_bitrate])

    if args.no_audio or target_format in FORMATS_WITHOUT_AUDIO:
        output_args.append("-an")
        return output_args

    if target_format in {"mp4", "mov", "mkv"}:
        output_args.extend(["-c:a", args.audio_codec or "aac", "-b:a", args.audio_bitrate])
    elif target_format == "webm":
        output_args.extend(["-c:a", args.audio_codec or "libopus", "-b:a", args.audio_bitrate])
    elif target_format == "avi":
        output_args.extend(["-c:a", args.audio_codec or "mp3", "-b:a", args.audio_bitrate])

    return output_args


def build_output_args(target_format: str, args: argparse.Namespace) -> list[str]:
    if target_format == "gif":
        return ["-filter_complex", build_gif_filter(args), "-an", "-loop", str(args.loop)]

    if target_format == "apng":
        output_args: list[str] = []
        base_filters = build_base_filters(args)
        if base_filters:
            output_args.extend(["-vf", ",".join(base_filters)])
        output_args.extend(["-an", "-plays", str(args.loop), "-f", "apng"])
        return output_args

    return build_standard_output_args(target_format, args)


def build_ffmpeg_command(
    ffmpeg_executable: str,
    input_path: Path,
    output_path: Path,
    args: argparse.Namespace,
) -> list[str]:
    target_format = detect_output_format(output_path)
    command = [ffmpeg_executable, "-hide_banner", "-loglevel", args.ffmpeg_log_level]
    command.append("-y" if args.overwrite else "-n")

    if args.start:
        command.extend(["-ss", args.start])

    command.extend(["-i", str(input_path)])

    if args.duration:
        command.extend(["-t", args.duration])

    command.extend(build_output_args(target_format, args))
    command.append(str(output_path))
    return command


def convert_video(input_path: Path, output_path: Path, args: argparse.Namespace) -> list[str]:
    ffmpeg_executable = resolve_ffmpeg_executable()
    command = build_ffmpeg_command(ffmpeg_executable, input_path, output_path, args)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        stderr = (completed.stderr or completed.stdout or "FFmpeg exited with a non-zero status.").strip()
        raise RuntimeError(stderr)

    return command


def validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        parser.error(f"Input file does not exist: {input_path}")
    if input_path.resolve() == output_path.resolve():
        parser.error("Input and output paths must be different.")
    if args.fps is not None and args.fps <= 0:
        parser.error("--fps must be greater than 0.")
    if args.width is not None and args.width < 1:
        parser.error("--width must be greater than 0.")
    if args.height is not None and args.height < 1:
        parser.error("--height must be greater than 0.")
    if args.loop < -1:
        parser.error("--loop must be -1 or greater.")
    detect_output_format(output_path)
    if output_path.exists() and not args.overwrite:
        parser.error(f"Output file already exists: {output_path}. Use --overwrite to replace it.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert common video formats locally with FFmpeg.")
    parser.add_argument("input", help="Input video path")
    parser.add_argument("output", help="Output video path")
    parser.add_argument("--fps", type=float, help="Override output frame rate")
    parser.add_argument("--width", type=int, help="Resize output width")
    parser.add_argument("--height", type=int, help="Resize output height")
    parser.add_argument("--start", help="Trim start position, for example 00:00:03")
    parser.add_argument("--duration", help="Trim duration, for example 4 or 00:00:04")
    parser.add_argument("--video-codec", dest="video_codec", help="Explicit FFmpeg video codec")
    parser.add_argument("--audio-codec", dest="audio_codec", help="Explicit FFmpeg audio codec")
    parser.add_argument("--video-bitrate", dest="video_bitrate", help="Explicit video bitrate, for example 4M")
    parser.add_argument("--audio-bitrate", dest="audio_bitrate", default="192k", help="Audio bitrate (default: 192k)")
    parser.add_argument("--crf", type=int, help="Quality factor for codec presets that support CRF")
    parser.add_argument("--preset", default="medium", help="Encoder preset for x264-like codecs")
    parser.add_argument("--no-audio", action="store_true", dest="no_audio", help="Drop audio from the output")
    parser.add_argument("--loop", type=int, default=0, help="Loop count for GIF/APNG; 0 means infinite where supported")
    parser.add_argument("--ffmpeg-log-level", default="warning", dest="ffmpeg_log_level", help="FFmpeg log level")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite the output file if it already exists")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        validate_args(parser, args)
        command = convert_video(Path(args.input), Path(args.output), args)
    except SystemExit:
        raise
    except Exception as exc:
        print(f"Conversion failed: {exc}", file=sys.stderr)
        return 1

    print("Success! FFmpeg command completed:")
    print(" ".join(command))
    return 0


if __name__ == "__main__":
    sys.exit(main())
