# OCR Setup (one time, Windows)

The OCR step uses `ocrmypdf`, which needs two system tools installed first:
Tesseract (the OCR engine) and Ghostscript (used internally by ocrmypdf).

## 1. Install Tesseract OCR
Download the 64-bit Windows installer from:
https://github.com/UB-Mannheim/tesseract/wiki
Run it and accept defaults (or install to a custom folder and note the path).

## 2. Install Ghostscript
Download the 64-bit "Ghostscript AGPL Release" for Windows from:
https://www.ghostscript.com/releases/gsdnld.html
Run it. ocrmypdf uses it internally.

## 3. Make both findable (PATH)
If you installed to a custom folder, add each program's folder to your user PATH
so Windows can find them. Example (PowerShell):

    [Environment]::SetEnvironmentVariable("Path", $env:Path + ";PATH_TO_TESSERACT_FOLDER", "User")
    [Environment]::SetEnvironmentVariable("Path", $env:Path + ";PATH_TO_GHOSTSCRIPT_BIN_FOLDER", "User")

The Ghostscript executable (gswin64c.exe) lives in a `bin` subfolder, e.g.
`...\gs10.07.1\bin`. After changing PATH, close and reopen VS Code.

## 4. Install the Python package
With the virtual environment active:

    pip install ocrmypdf

(A warning about a pdfminer.six version conflict is harmless — ignore it.)

## 5. Confirm everything works
    tesseract --version
    gswin64c --version
    ocrmypdf --version

If all three print version numbers, OCR is ready. If any says "not recognized,"
close and reopen VS Code so it picks up the new PATH, then try again.

## Note on requirements.txt
Only `ocrmypdf` is a pip package (add it to requirements.txt). Tesseract and
Ghostscript are system tools installed separately, which is why this setup note
exists rather than them being in requirements.txt.