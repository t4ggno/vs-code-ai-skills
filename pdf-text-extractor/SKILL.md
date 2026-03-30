---
name: pdf-text-extractor
description: Extracts text from standard PDF files so the agent can read, summarize, or analyze them. Use for text-based PDFs or selectable text layers. Do not use it as OCR for scanned or image-only PDFs unless another OCR step is added.
argument-hint: <pdf path> [page range, summary goal]
---

# PDF Text Extractor

1. Use this skill when the input is a PDF file and the task requires reading its text content.
2. Execute the local script [extract.py](./extract.py) instead of trying to treat the PDF as plain text.
3. If the document is large, narrow the extraction with `--start-page` and `--end-page`.
4. If the downstream step benefits from structured output, use `--output json`.
5. If extraction returns little or no text, assume the file may be scan-based or image-only and switch to an OCR-capable approach.

## Common invocations

- Extract the full document:
	`python ./extract.py ./document.pdf`
- Extract only a page range:
	`python ./extract.py ./document.pdf --start-page 5 --end-page 12`
- Return structured JSON:
	`python ./extract.py ./document.pdf --output json`

## Guardrails

- This skill extracts text layers; it is not a replacement for OCR.
- Expect imperfect extraction on complex layouts, embedded tables, or heavily styled PDFs.
- Keep binary PDFs out of chat and pass file paths to the script instead.
