"""Convert WRITEUP.md to PDF: markdown -> styled HTML -> headless Chrome print.

Chrome is used rather than a LaTeX toolchain because the document is mostly
tables, and Chrome's print engine handles them without fighting a float model.
"""
import subprocess
import sys
from pathlib import Path

import markdown

SRC = Path("WRITEUP.md")
HTML = Path("/tmp/writeup.html")
PDF = Path("WRITEUP.pdf")

CSS = """
@page { size: A4; margin: 11mm 12mm; }
* { box-sizing: border-box; }
body {
  font-family: "Latin Modern Roman", "LM Roman 10", "Computer Modern", serif;
  font-size: 10.6pt; line-height: 1.34; color: #16181d; margin: 0;
  -webkit-font-smoothing: antialiased;
}
h1 { font-size: 18pt; margin: 0 0 1mm; letter-spacing: -0.2pt; }
h2 { font-size: 12.4pt; margin: 3.4mm 0 1.6mm; padding-bottom: 0.8mm;
     border-bottom: 1px solid #dcdfe4; }
h3 { font-size: 11pt; margin: 4mm 0 1.5mm; }
p { margin: 0 0 2mm; }
hr { border: none; border-top: 1px solid #e4e7ec; margin: 3mm 0; }
table { border-collapse: collapse; width: 100%; margin: 2mm 0 3mm;
        font-size: 9.0pt; page-break-inside: avoid; }
th, td { border: 1px solid #d9dde3; padding: 1.3mm 2mm; text-align: left;
         vertical-align: top; }
th { background: #f2f4f7; font-weight: 600; }
td:first-child { white-space: nowrap; }
code { font-family: "Latin Modern Mono Light", "LM Mono 10", monospace;
       font-size: 9.0pt; background: #f4f5f7; padding: 0 0.7mm;
       border-radius: 2px; }
ul { margin: 0.8mm 0 2.4mm; padding-left: 4.5mm; }
li { margin-bottom: 0.9mm; }
strong { font-weight: 600; }
a { color: inherit; text-decoration: none; }
"""

html = markdown.markdown(
    SRC.read_text(),
    extensions=["tables", "fenced_code", "sane_lists", "attr_list"],
)
HTML.write_text(
    f"<!doctype html><html><head><meta charset='utf-8'>"
    f"<title>FYTA — submission notes</title><style>{CSS}</style>"
    f"</head><body>{html}</body></html>"
)
print(f"  html  {HTML}  ({HTML.stat().st_size / 1024:.1f} KB)")

cmd = [
    "google-chrome", "--headless", "--disable-gpu", "--no-sandbox",
    "--no-pdf-header-footer", "--print-to-pdf-no-header",
    f"--print-to-pdf={PDF.resolve()}", HTML.resolve().as_uri(),
]
r = subprocess.run(cmd, capture_output=True, text=True)
if not PDF.exists():
    print("  chrome failed:", r.stderr[-1500:])
    sys.exit(1)
print(f"  pdf   {PDF}  ({PDF.stat().st_size / 1024:.1f} KB)")
