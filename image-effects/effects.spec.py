from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from conftest import load_module

MODULE = load_module("image-effects/effects.py", "image_effects")


def build_input_file(path: Path, *, color: tuple[int, int, int, int] = (120, 80, 40, 255)) -> Path:
    image = Image.new("RGBA", (8, 8), color)
    image.save(path, format="PNG")
    return path


def make_args(**overrides: object) -> SimpleNamespace:
    defaults: dict[str, object] = {
        "remove_background": False,
        "bg_model": "birefnet-general",
        "only_mask": False,
        "post_process_mask": False,
        "trim_transparent": False,
        "background_color": None,
        "background_rgba": None,
        "resize": None,
        "rotate": None,
        "grayscale": False,
        "sepia": False,
        "autocontrast": False,
        "invert": False,
        "blur": 0.0,
        "sharpen": 1.0,
        "brightness": 1.0,
        "contrast": 1.0,
        "saturation": 1.0,
        "quality": 90,
        "lossless": False,
        "overwrite": True,
        "input": "",
        "output": "",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_parse_size_and_background_color() -> None:
    assert MODULE.parse_size("320x200") == (320, 200)
    assert MODULE.parse_background_color("#ffffff") == (255, 255, 255, 255)
    assert MODULE.parse_background_color("transparent") == (0, 0, 0, 0)

    with pytest.raises(ValueError):
        MODULE.parse_size("320")


def test_apply_sepia_and_trim_transparent_bounds() -> None:
    image = Image.new("RGBA", (6, 6), (0, 0, 0, 0))
    image.paste((200, 150, 100, 255), (1, 1, 5, 5))

    sepia = MODULE.apply_sepia(Image.new("RGBA", (2, 2), (80, 40, 20, 255)))
    trimmed = MODULE.trim_transparent_bounds(image)

    assert sepia.size == (2, 2)
    assert trimmed.size == (4, 4)


def test_apply_effects_with_basic_pipeline(tmp_path: Path) -> None:
    input_path = build_input_file(tmp_path / "input.png")
    output_path = tmp_path / "output.webp"

    MODULE.apply_effects(
        input_path,
        output_path,
        make_args(grayscale=True, contrast=1.1, sharpen=1.2, lossless=True),
    )

    assert output_path.exists()


def test_remove_background_uses_stubbed_rembg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    input_path = build_input_file(tmp_path / "input.png")
    output_path = tmp_path / "output.png"

    def fake_get_rembg_api():
        def fake_remove(image: Image.Image, session, only_mask: bool, post_process_mask: bool) -> Image.Image:
            result = image.convert("RGBA")
            result.putalpha(128)
            return result

        def fake_new_session(model_name: str) -> str:
            return f"session:{model_name}"

        return fake_remove, fake_new_session

    monkeypatch.setattr(MODULE, "get_rembg_api", fake_get_rembg_api)
    MODULE.SESSION_CACHE.clear()

    MODULE.apply_effects(
        input_path,
        output_path,
        make_args(remove_background=True, trim_transparent=True),
    )

    assert output_path.exists()
    assert MODULE.SESSION_CACHE["birefnet-general"] == "session:birefnet-general"


def test_validate_args_rejects_only_mask_without_background(tmp_path: Path) -> None:
    parser = MODULE.build_parser()
    input_path = build_input_file(tmp_path / "input.png")
    output_path = tmp_path / "output.png"
    args = parser.parse_args([str(input_path), str(output_path), "--only-mask", "--overwrite"])

    with pytest.raises(SystemExit):
        MODULE.validate_args(parser, args)
