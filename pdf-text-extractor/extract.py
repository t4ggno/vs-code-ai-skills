import sys

def extract_pdf_text(filepath):
    try:
        import PyPDF2
        text = ""
        with open(filepath, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        return text
    except ImportError:
        print("Error: PyPDF2 module is not installed. Please run `pip install PyPDF2`.")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading PDF: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract.py <path_to_pdf>")
        sys.exit(1)

    file_path = sys.argv[1]
    result = extract_pdf_text(file_path)
    print(result)
