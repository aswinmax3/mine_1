import os
import pytesseract
from PIL import Image
from pdfminer.high_level import extract_text


def extract_text_from_document(file_path):
    extension = os.path.splitext(file_path)[1].lower()

    if extension == ".pdf":
        return extract_text_from_pdf(file_path)

    elif extension in [".png", ".jpg", ".jpeg"]:
        return extract_text_from_image(file_path)

    else:
        return "Unsupported file format."


def extract_text_from_pdf(file_path):
    try:
        text = extract_text(file_path)
        return text.strip()
    except Exception as e:
        return f"PDF extraction error: {str(e)}"


def extract_text_from_image(file_path):
    try:
        image = Image.open(file_path)
        text = pytesseract.image_to_string(image)
        return text.strip()
    except Exception as e:
        return f"OCR extraction error: {str(e)}"