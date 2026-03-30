from __future__ import annotations

import json
import builtins
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import load_module

MODULE = load_module("pdf-text-extractor/extract.py", "pdf_text_extractor")
SCRIPT_PATH = Path(__file__).with_name("extract.py")


def test_extract_pdf_text_concatenates_all_pages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    fake_reader = SimpleNamespace(
        pages=[
            SimpleNamespace(extract_text=lambda: "First page"),
            SimpleNamespace(extract_text=lambda: "Second page"),
        ]
    )
    monkeypatch.setitem(sys.modules, "PyPDF2", SimpleNamespace(PdfReader=lambda _file: fake_reader))

    assert MODULE.extract_pdf_text(str(pdf_path)) == "First page\nSecond page\n"


def test_extract_pdf_text_exits_when_pypdf2_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "PyPDF2":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.delitem(sys.modules, "PyPDF2", raising=False)
    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(SystemExit) as exc_info:
        MODULE.extract_pdf_text("missing.pdf")

    assert exc_info.value.code == 1
    assert "PyPDF2 module is not installed" in capsys.readouterr().out


def test_extract_pdf_text_exits_on_reader_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pdf_path = tmp_path / "broken.pdf"
    pdf_path.write_bytes(b"not-really-a-pdf")

    def raise_reader_error(_file: object) -> object:
        raise ValueError("bad pdf")

    monkeypatch.setitem(sys.modules, "PyPDF2", SimpleNamespace(PdfReader=raise_reader_error))

    with pytest.raises(SystemExit) as exc_info:
        MODULE.extract_pdf_text(str(pdf_path))

    assert exc_info.value.code == 1
    assert "Error reading PDF: bad pdf" in capsys.readouterr().out


def test_extract_pdf_text_supports_page_ranges_and_blank_pages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    fake_reader = SimpleNamespace(
        pages=[
            SimpleNamespace(extract_text=lambda: "First page"),
            SimpleNamespace(extract_text=lambda: None),
            SimpleNamespace(extract_text=lambda: "Third page"),
        ]
    )
    monkeypatch.setitem(sys.modules, "PyPDF2", SimpleNamespace(PdfReader=lambda _file: fake_reader))

    assert MODULE.extract_pdf_text(str(pdf_path), start_page=2, end_page=3) == "\nThird page\n"


def test_cli_prints_usage_when_path_is_missing(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "argv", [str(SCRIPT_PATH)])

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(str(SCRIPT_PATH), run_name="__main__")

    assert exc_info.value.code == 1
    assert "Usage: python extract.py <path_to_pdf>" in capsys.readouterr().out


def test_cli_prints_extracted_text_when_path_is_provided(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    fake_reader = SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda: "CLI page")])
    monkeypatch.setitem(sys.modules, "PyPDF2", SimpleNamespace(PdfReader=lambda _file: fake_reader))
    monkeypatch.setattr(sys, "argv", [str(SCRIPT_PATH), str(pdf_path)])

    runpy.run_path(str(SCRIPT_PATH), run_name="__main__")

    assert "CLI page" in capsys.readouterr().out


def test_cli_supports_json_output_and_page_arguments(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    fake_reader = SimpleNamespace(
        pages=[
            SimpleNamespace(extract_text=lambda: "Page one"),
            SimpleNamespace(extract_text=lambda: "Page two"),
        ]
    )
    monkeypatch.setitem(sys.modules, "PyPDF2", SimpleNamespace(PdfReader=lambda _file: fake_reader))
    monkeypatch.setattr(
        sys,
        "argv",
        [str(SCRIPT_PATH), str(pdf_path), "--start-page", "2", "--end-page", "2", "--output", "json"],
    )

    runpy.run_path(str(SCRIPT_PATH), run_name="__main__")

    payload = json.loads(capsys.readouterr().out)
    assert payload["path"] == str(pdf_path)
    assert payload["start_page"] == 2
    assert payload["end_page"] == 2
    assert payload["text"] == "Page two\n"
