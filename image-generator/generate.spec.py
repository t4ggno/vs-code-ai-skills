from __future__ import annotations

import argparse
import base64
from io import BytesIO
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace

import pytest
from PIL import Image

from conftest import load_module

MODULE = load_module("image-generator/generate.py", "image_generator")
SCRIPT_PATH = Path(__file__).with_name("generate.py")


def build_png_bytes(size: tuple[int, int] = (4, 4), color: tuple[int, int, int, int] = (255, 0, 0, 255)) -> bytes:
    image = Image.new("RGBA", size, color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def make_openai_stub(
    image_response: SimpleNamespace | None,
    *,
    vision_text: str = "YES",
    generate_error: Exception | None = None,
    evaluation_error: Exception | None = None,
) -> type:
    class FakeChatCompletions:
        def create(self, **kwargs: object) -> SimpleNamespace:
            if evaluation_error is not None:
                raise evaluation_error
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=vision_text))])

    class FakeChat:
        def __init__(self) -> None:
            self.completions = FakeChatCompletions()

    class FakeImages:
        def generate(self, **kwargs: object) -> SimpleNamespace:
            if generate_error is not None:
                raise generate_error
            assert image_response is not None
            return image_response

    class FakeOpenAI:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key
            self.images = FakeImages()
            self.chat = FakeChat()

    return FakeOpenAI


def test_format_helpers_and_mime_types() -> None:
    assert MODULE.clamp(10, 0, 5) == 5
    assert MODULE.normalize_output_format("jpg") == "JPEG"
    assert MODULE.normalize_output_format("png") == "PNG"
    assert MODULE.get_mime_subtype("jpg") == "jpeg"
    assert MODULE.get_mime_subtype("webp") == "webp"


def test_extract_generated_image_supports_base64_and_download(monkeypatch: pytest.MonkeyPatch) -> None:
    image_bytes = build_png_bytes()
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    assert MODULE.extract_generated_image(SimpleNamespace(b64_json=encoded, url=None), 5) == image_bytes

    class FakeDownloadResponse:
        def __init__(self) -> None:
            self.content = image_bytes

        def raise_for_status(self) -> None:
            return None

    monkeypatch.setattr(MODULE.requests, "get", lambda url, timeout: FakeDownloadResponse())
    assert MODULE.extract_generated_image(SimpleNamespace(b64_json=None, url="https://example.com/image.png"), 5) == image_bytes

    with pytest.raises(RuntimeError):
        MODULE.extract_generated_image(SimpleNamespace(b64_json=None, url=None), 5)


def test_tile_helpers_preserve_size_and_create_preview() -> None:
    image = Image.new("RGBA", (4, 4), (10, 20, 30, 255))
    processed = MODULE.apply_tileable_postprocess(image, 0.25)
    preview = MODULE.create_tile_preview(image, 1)

    assert processed.size == image.size
    assert preview.size == (8, 8)


def test_create_tile_preview_resizes_large_images() -> None:
    image = Image.new("RGBA", (400, 200), (10, 20, 30, 255))

    preview = MODULE.create_tile_preview(image, 2)

    assert preview.size == (512, 256)


def test_save_image_and_encode_image_support_jpeg_output() -> None:
    image = Image.new("RGBA", (3, 3), (100, 120, 140, 255))
    buffer = BytesIO()

    MODULE.save_image(image, buffer, "jpg")
    encoded = MODULE.encode_image(image, "png")

    assert buffer.getvalue().startswith(b"\xff\xd8")
    assert encoded.startswith(b"\x89PNG")


def test_build_prompt_helpers_include_tileable_suffixes() -> None:
    prompt = MODULE.build_generation_prompt(" mossy stone ", " realistic texture ", True)
    criteria = MODULE.build_effective_criteria(" realistic texture ", True)
    evaluation_prompt = MODULE.build_evaluation_prompt(criteria, True, 3)

    assert "seamless, tileable texture" in prompt
    assert "repeating material sample" in criteria
    assert "3x3 tiled preview" in evaluation_prompt


def test_build_image_generation_kwargs_applies_model_specific_options() -> None:
    gpt_image_args = SimpleNamespace(
        model="gpt-image-1.5",
        size="1024x1024",
        quality="standard",
        moderation="low",
        background="transparent",
        output_format="jpg",
    )
    dalle_args = SimpleNamespace(
        model="dall-e-3",
        size="1024x1024",
        quality="hd",
        moderation="low",
        background="transparent",
        output_format="png",
    )

    gpt_kwargs = MODULE.build_image_generation_kwargs(gpt_image_args, "prompt")
    dalle_kwargs = MODULE.build_image_generation_kwargs(dalle_args, "prompt")

    assert gpt_kwargs["moderation"] == "low"
    assert gpt_kwargs["background"] == "transparent"
    assert gpt_kwargs["output_format"] == "jpeg"
    assert gpt_kwargs["quality"] == "standard"
    assert "moderation" not in dalle_kwargs
    assert "background" not in dalle_kwargs
    assert "output_format" not in dalle_kwargs
    assert dalle_kwargs["quality"] == "hd"


def test_validate_args_rejects_invalid_values() -> None:
    parser = argparse.ArgumentParser()
    valid_args = SimpleNamespace(
        prompt="prompt",
        criteria="criteria",
        timeout=180,
        poll_interval=2,
        tile_preview_grid=3,
        tile_blend_ratio=0.125,
        output_format="png",
    )

    MODULE.validate_args(parser, valid_args)

    with pytest.raises(SystemExit):
        MODULE.validate_args(parser, SimpleNamespace(**{**valid_args.__dict__, "prompt": "   "}))

    with pytest.raises(SystemExit):
        MODULE.validate_args(parser, SimpleNamespace(**{**valid_args.__dict__, "tile_blend_ratio": 0.0}))

    with pytest.raises(SystemExit):
        MODULE.validate_args(parser, SimpleNamespace(**{**valid_args.__dict__, "output_format": "bmp"}))


def test_load_openai_api_key_prefers_environment_and_dotenv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    assert MODULE.load_openai_api_key() == "env-key"

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    image_dir = tmp_path / "image-generator"
    image_dir.mkdir()
    (tmp_path / ".env").write_text("OPENAI_API_KEY=from-dotenv", encoding="utf-8")
    monkeypatch.setattr(MODULE, "__file__", str(image_dir / "generate.py"))
    monkeypatch.setattr(MODULE, "load_dotenv", lambda path, override=False: monkeypatch.setenv("OPENAI_API_KEY", "dotenv-key"))

    assert MODULE.load_openai_api_key() == "dotenv-key"


def test_main_exits_when_api_key_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(MODULE, "load_openai_api_key", lambda: None)
    monkeypatch.setattr(sys, "argv", ["generate.py", "prompt", "folder", "criteria"])

    with pytest.raises(SystemExit) as exc_info:
        MODULE.main()

    assert exc_info.value.code == 1
    assert "OPENAI_API_KEY environment variable is missing" in capsys.readouterr().err


def test_main_exits_for_generation_download_processing_and_encoding_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    image_bytes = build_png_bytes()
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    image_response = SimpleNamespace(data=[SimpleNamespace(b64_json=encoded, revised_prompt=None)])
    original_image_open = MODULE.Image.open

    monkeypatch.setattr(MODULE, "load_openai_api_key", lambda: "test-key")
    monkeypatch.setattr(MODULE, "OpenAI", make_openai_stub(None, generate_error=RuntimeError("generation boom")))
    monkeypatch.setattr(sys, "argv", ["generate.py", "prompt", str(tmp_path), "criteria"])
    with pytest.raises(SystemExit) as exc_info:
        MODULE.main()
    assert exc_info.value.code == 1
    assert "Generation failed: generation boom" in capsys.readouterr().err

    monkeypatch.setattr(MODULE, "OpenAI", make_openai_stub(image_response))
    monkeypatch.setattr(MODULE, "extract_generated_image", lambda *_args: (_ for _ in ()).throw(RuntimeError("download boom")))
    with pytest.raises(SystemExit) as exc_info:
        MODULE.main()
    assert exc_info.value.code == 1
    assert "Downloading image failed: download boom" in capsys.readouterr().err

    monkeypatch.setattr(MODULE, "extract_generated_image", lambda *_args: b"broken-image")
    monkeypatch.setattr(MODULE.Image, "open", lambda _source: (_ for _ in ()).throw(ValueError("decode boom")))
    with pytest.raises(SystemExit) as exc_info:
        MODULE.main()
    assert exc_info.value.code == 1
    assert "Processing image failed: decode boom" in capsys.readouterr().err

    monkeypatch.setattr(MODULE, "extract_generated_image", lambda *_args: image_bytes)
    monkeypatch.setattr(MODULE.Image, "open", original_image_open)
    monkeypatch.setattr(MODULE, "encode_image", lambda *_args: (_ for _ in ()).throw(RuntimeError("encode boom")))
    with pytest.raises(SystemExit) as exc_info:
        MODULE.main()
    assert exc_info.value.code == 1
    assert "Encoding output image failed: encode boom" in capsys.readouterr().err


def test_main_exits_for_tile_preview_and_evaluation_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    image_bytes = build_png_bytes()
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    image_response = SimpleNamespace(data=[SimpleNamespace(b64_json=encoded, revised_prompt=None)])
    original_create_tile_preview = MODULE.create_tile_preview

    monkeypatch.setattr(MODULE, "load_openai_api_key", lambda: "test-key")
    monkeypatch.setattr(MODULE, "OpenAI", make_openai_stub(image_response))
    monkeypatch.setattr(
        sys,
        "argv",
        ["generate.py", "mossy stone", str(tmp_path), "realistic texture", "--tileable"],
    )
    monkeypatch.setattr(MODULE, "create_tile_preview", lambda *_args: (_ for _ in ()).throw(RuntimeError("preview boom")))

    with pytest.raises(SystemExit) as exc_info:
        MODULE.main()

    assert exc_info.value.code == 1
    assert "Building tile preview failed: preview boom" in capsys.readouterr().err

    monkeypatch.setattr(MODULE, "create_tile_preview", original_create_tile_preview)
    monkeypatch.setattr(MODULE, "OpenAI", make_openai_stub(image_response, evaluation_error=RuntimeError("vision boom")))
    monkeypatch.setattr(sys, "argv", ["generate.py", "mossy stone", str(tmp_path), "realistic texture"])

    with pytest.raises(SystemExit) as exc_info:
        MODULE.main()

    assert exc_info.value.code == 1
    assert "Evaluation request failed: vision boom" in capsys.readouterr().err


def test_main_generates_and_evaluates_tileable_image(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    image_bytes = build_png_bytes()
    vision_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="YES"))]
    )
    image_response = SimpleNamespace(
        data=[SimpleNamespace(b64_json=base64.b64encode(image_bytes).decode("utf-8"), revised_prompt="refined")]
    )

    class FakeChatCompletions:
        def create(self, **kwargs: object) -> SimpleNamespace:
            return vision_response

    class FakeChat:
        def __init__(self) -> None:
            self.completions = FakeChatCompletions()

    class FakeImages:
        def generate(self, **kwargs: object) -> SimpleNamespace:
            return image_response

    class FakeOpenAI:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key
            self.images = FakeImages()
            self.chat = FakeChat()

    monkeypatch.setattr(MODULE, "load_openai_api_key", lambda: "test-key")
    monkeypatch.setattr(MODULE, "OpenAI", FakeOpenAI)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate.py",
            "mossy stone",
            str(tmp_path),
            "realistic texture",
            "--tileable",
            "--output-format",
            "png",
        ],
    )

    MODULE.main()

    image_path = tmp_path / "generated_image.png"
    preview_path = tmp_path / "generated_image_tiled_preview.png"
    assert image_path.exists()
    assert preview_path.exists()


def test_main_exits_when_vision_evaluation_rejects_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    image_bytes = build_png_bytes()
    vision_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="NO: seam detected"))]
    )
    image_response = SimpleNamespace(
        data=[SimpleNamespace(b64_json=base64.b64encode(image_bytes).decode("utf-8"), revised_prompt=None)]
    )

    class FakeChatCompletions:
        def create(self, **kwargs: object) -> SimpleNamespace:
            return vision_response

    class FakeChat:
        def __init__(self) -> None:
            self.completions = FakeChatCompletions()

    class FakeImages:
        def generate(self, **kwargs: object) -> SimpleNamespace:
            return image_response

    class FakeOpenAI:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key
            self.images = FakeImages()
            self.chat = FakeChat()

    monkeypatch.setattr(MODULE, "load_openai_api_key", lambda: "test-key")
    monkeypatch.setattr(MODULE, "OpenAI", FakeOpenAI)
    monkeypatch.setattr(sys, "argv", ["generate.py", "mossy stone", str(tmp_path), "realistic texture"])

    with pytest.raises(SystemExit) as exc_info:
        MODULE.main()

    assert exc_info.value.code == 1


def test_script_entrypoint_saves_non_tileable_images(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    image_bytes = build_png_bytes()
    image_response = SimpleNamespace(
        data=[SimpleNamespace(b64_json=base64.b64encode(image_bytes).decode("utf-8"), revised_prompt=None)]
    )
    fake_openai = make_openai_stub(image_response)

    monkeypatch.setenv("OPENAI_API_KEY", "entrypoint-key")
    monkeypatch.setattr(sys.modules["openai"], "OpenAI", fake_openai)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT_PATH), "mossy stone", str(tmp_path), "realistic texture"])

    runpy.run_path(str(SCRIPT_PATH), run_name="__main__")

    image_path = tmp_path / "generated_image.png"
    assert image_path.exists()
    assert f"Success! Image saved to {image_path}" in capsys.readouterr().out
