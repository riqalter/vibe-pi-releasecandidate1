import pytesseract
print(pytesseract.get_tesseract_version())
print(pytesseract.get_languages(config='/usr/share/tesseract/tessdata'))