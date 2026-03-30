from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def parse_positive_page(value: str) -> int:
    try:
        page_number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Page numbers must be integers.") from exc
    if page_number < 1:
        raise argparse.ArgumentTypeError("Page numbers must be at least 1.")
    return page_number


def load_pdf_reader() -> Any:
    try:
        import PyPDF2
    except ImportError:
        print("Error: PyPDF2 module is not installed. Please run `pip install PyPDF2`.")
        sys.exit(1)
    return PyPDF2.PdfReader


def validate_page_range(start_page: int | None, end_page: int | None, total_pages: int) -> tuple[int, int]:
    start_index = 0 if start_page is None else start_page - 1
    end_index = total_pages if end_page is None else end_page

    if start_index < 0:
        raise ValueError("Start page must be at least 1.")
    if end_index < start_index + 1:
        raise ValueError("End page must be greater than or equal to the start page.")
    if start_index >= total_pages:
        raise ValueError(f"Start page {start_page} is outside the document page range 1-{total_pages}.")
    if end_index > total_pages:
        raise ValueError(f"End page {end_page} is outside the document page range 1-{total_pages}.")

    return start_index, end_index


def extract_pdf_text(filepath: str, start_page: int | None = None, end_page: int | None = None) -> str:
    try:
        reader_class = load_pdf_reader()
        pdf_path = Path(filepath)
        if not pdf_path.exists():
            raise FileNotFoundError(f"File not found: {pdf_path}")

        with pdf_path.open("rb") as file_handle:
            reader = reader_class(file_handle)
            start_index, end_index = validate_page_range(start_page, end_page, len(reader.pages))
            chunks: list[str] = []
            for page in reader.pages[start_index:end_index]:
                extracted_text = page.extract_text() or ""
                if extracted_text.endswith("\n"):
                    chunks.append(extracted_text)
                else:
                    chunks.append(f"{extracted_text}\n")
            return "".join(chunks)
    except SystemExit:
        raise
    except Exception as exc:
        print(f"Error reading PDF: {exc}")
        sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract text from a standard PDF document using PyPDF2.")
    parser.add_argument("path", help="Path to the PDF file.")
    parser.add_argument("--start-page", type=parse_positive_page, help="1-based inclusive start page.")
    parser.add_argument("--end-page", type=parse_positive_page, help="1-based inclusive end page.")
    parser.add_argument(
        "--output",
        choices=("text", "json"),
        default="text",
        help="Output format. Default: text.",
    )
    return parser


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python extract.py <path_to_pdf>")
        return 1

    parser = build_parser()
    args = parser.parse_args()

    if args.start_page and args.end_page and args.end_page < args.start_page:
        parser.error("--end-page must be greater than or equal to --start-page.")

    text = extract_pdf_text(args.path, start_page=args.start_page, end_page=args.end_page)

    if args.output == "json":
        payload = {
            "path": str(Path(args.path)),
            "start_page": args.start_page,
            "end_page": args.end_page,
            "text": text,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
