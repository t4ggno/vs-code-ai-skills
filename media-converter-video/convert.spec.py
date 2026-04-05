from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import load_module

MODULE = load_module("media-converter-video/convert.py", "media_converter_video")


class FakeCompletedProcess:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def make_args(**overrides: object) -> SimpleNamespace:
    defaults: dict[str, object] = {
        "fps": None,
        "width": None,
        "height": None,
        "start": None,
        "duration": None,
        "video_codec": None,
        "audio_codec": None,
        "video_bitrate": None,
        "audio_bitrate": "192k",
        "crf": None,
        "preset": "medium",
        "no_audio": False,
        "loop": 0,
        "ffmpeg_log_level": "warning",
        "overwrite": True,
        "input": "",
        "output": "",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_detect_output_format_and_scale_filter() -> None:
    assert MODULE.detect_output_format(Path("video.mp4")) == "mp4"
    assert MODULE.detect_output_format(Path("preview.apng")) == "apng"
    assert MODULE.build_scale_filter(640, None) == "scale=w=640:h=-2"
    assert MODULE.build_scale_filter(None, 360) == "scale=w=-2:h=360"
    assert MODULE.build_scale_filter(640, 360) == "scale=w=640:h=360:force_original_aspect_ratio=decrease"


def test_build_ffmpeg_command_for_mp4() -> None:
    command = MODULE.build_ffmpeg_command(
        "ffmpeg",
        Path("input.webm"),
        Path("output.mp4"),
        make_args(),
    )

    joined = " ".join(command)
    assert "-c:v libx264" in joined
    assert "+faststart" in joined
    assert "-c:a aac" in joined


def test_build_ffmpeg_command_for_gif_uses_palette_filter() -> None:
    command = MODULE.build_ffmpeg_command(
        "ffmpeg",
        Path("input.mp4"),
        Path("output.gif"),
        make_args(fps=12.0, width=320),
    )

    joined = " ".join(command)
    assert "palettegen" in joined
    assert "paletteuse" in joined
    assert "-loop 0" in joined
    assert "-an" in joined


def test_convert_video_invokes_subprocess(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    input_path = tmp_path / "input.mp4"
    output_path = tmp_path / "output.webm"
    input_path.write_bytes(b"fake-video")

    calls: list[list[str]] = []

    monkeypatch.setattr(MODULE, "resolve_ffmpeg_executable", lambda: "ffmpeg")
    monkeypatch.setattr(
        MODULE.subprocess,
        "run",
        lambda command, capture_output, text, check: calls.append(command) or FakeCompletedProcess(),
    )

    command = MODULE.convert_video(input_path, output_path, make_args())

    assert calls
    assert command == calls[0]
    assert calls[0][0] == "ffmpeg"
    assert calls[0][-1] == str(output_path)


def test_convert_video_raises_on_ffmpeg_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    input_path = tmp_path / "input.mp4"
    output_path = tmp_path / "output.webm"
    input_path.write_bytes(b"fake-video")

    monkeypatch.setattr(MODULE, "resolve_ffmpeg_executable", lambda: "ffmpeg")
    monkeypatch.setattr(
        MODULE.subprocess,
        "run",
        lambda command, capture_output, text, check: FakeCompletedProcess(returncode=1, stderr="boom"),
    )

    with pytest.raises(RuntimeError, match="boom"):
        MODULE.convert_video(input_path, output_path, make_args())


def test_validate_args_rejects_bad_fps(tmp_path: Path) -> None:
    parser = MODULE.build_parser()
    input_path = tmp_path / "input.mp4"
    output_path = tmp_path / "output.webm"
    input_path.write_bytes(b"fake-video")
    args = parser.parse_args([str(input_path), str(output_path), "--fps", "0", "--overwrite"])

    with pytest.raises(SystemExit):
        MODULE.validate_args(parser, args)
