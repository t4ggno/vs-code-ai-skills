from __future__ import annotations

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from conftest import load_module

MODULE = load_module("media-converter-image/convert.py", "media_converter_image")


def build_png_file(path: Path, *, color: tuple[int, int, int, int] = (255, 0, 0, 128)) -> Path:
    image = Image.new("RGBA", (8, 8), color)
    image.save(path, format="PNG")
    return path


def build_png_bytes(size: tuple[int, int] = (8, 8), color: tuple[int, int, int, int] = (0, 255, 0, 255)) -> bytes:
    image = Image.new("RGBA", size, color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def make_args(**overrides: object) -> SimpleNamespace:
    defaults: dict[str, object] = {
        "quality": 90,
        "lossless": False,
        "background": "#ffffff",
        "background_rgba": (255, 255, 255, 255),
        "sizes": [],
        "icon_sizes": [],
        "all_frames": False,
        "duration": None,
        "loop": 0,
        "svg_dpi": 96,
        "svg_scale": 1.0,
        "output_width": None,
        "output_height": None,
        "overwrite": True,
        "input": "",
        "output": "",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_detect_output_format_and_parse_icon_sizes() -> None:
    assert MODULE.detect_output_format(Path("icon.ico")) == "ico"
    assert MODULE.detect_output_format(Path("photo.jpg")) == "jpeg"
    assert MODULE.parse_icon_sizes(["16x16", "32x32"]) == [(16, 16), (32, 32)]

    with pytest.raises(ValueError):
        MODULE.parse_icon_sizes(["32"])


def test_flatten_alpha_and_filter_icon_sizes() -> None:
    image = Image.new("RGBA", (4, 4), (255, 0, 0, 128))

    flattened = MODULE.flatten_alpha(image, (255, 255, 255, 255))
    sizes = MODULE.filter_icon_sizes((48, 48), [(16, 16), (64, 64)])

    assert flattened.mode == "RGB"
    assert sizes == [(16, 16)]


def test_convert_png_to_jpeg(tmp_path: Path) -> None:
    input_path = build_png_file(tmp_path / "input.png")
    output_path = tmp_path / "output.jpg"

    MODULE.convert_image(input_path, output_path, make_args())

    assert output_path.exists()
    with Image.open(output_path) as result:
        assert result.mode == "RGB"
        assert result.size == (8, 8)


def test_svg_input_uses_rasterizer(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    input_path = tmp_path / "vector.svg"
    output_path = tmp_path / "vector.png"
    input_path.write_text("<svg xmlns='http://www.w3.org/2000/svg'></svg>", encoding="utf-8")

    monkeypatch.setattr(MODULE, "rasterize_svg_to_png_bytes", lambda *_args: build_png_bytes())

    MODULE.convert_image(input_path, output_path, make_args())

    assert output_path.exists()
    with Image.open(output_path) as result:
        assert result.size == (8, 8)


def test_raster_to_svg_is_rejected(tmp_path: Path) -> None:
    input_path = build_png_file(tmp_path / "input.png")
    output_path = tmp_path / "output.svg"

    with pytest.raises(ValueError):
        MODULE.convert_image(input_path, output_path, make_args())


def test_validate_args_rejects_invalid_jpeg_background(tmp_path: Path) -> None:
    parser = MODULE.build_parser()
    input_path = build_png_file(tmp_path / "input.png")
    output_path = tmp_path / "output.jpg"
    args = parser.parse_args([str(input_path), str(output_path), "--background", "transparent", "--overwrite"])

    with pytest.raises(SystemExit):
        MODULE.validate_args(parser, args)
