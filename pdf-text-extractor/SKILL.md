---
name: pdf-text-extractor
description: Extracts text from all pages of standard PDF files using PyPDF2, allowing the agent to read, summarize, or analyze binary PDF documents.
---

# PDF Text Extractor Skill

Use this skill when a user needs to extract text from a PDF file. Large Language Models cannot natively read binary PDF files, so this skill provides a specialized Python script to parse and extract the text content from them.

## Capabilities

- Extract text from all pages of a PDF file.
- Handle standard PDF formats to retrieve readable strings for further processing.

## How to use

Run the `extract.py` script with the path to the PDF file as an argument.

```bash
python c:/Users/ehrha/.copilot/skills/pdf-text-extractor/extract.py <path_to_pdf_file>
```

This will output the extracted text to stdout, which you can then read, summarize, or analyze.
