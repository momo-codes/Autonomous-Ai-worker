"""Generates a sample PDF invoice for Globex Logistics"""
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

out = Path("sandbox/workspace/inbox/2026-09-11_globex_GLX-88121.pdf")

c = canvas.Canvas(str(out), pagesize=A4)
y = 800

lines = [
    "GLOBEX LOGISTICS LIMITED - TAX INVOICE",
    "",
    "Invoice Number: GLX-88121",
    "Invoice Date:   10 Sep 2026",
    "Due Date:       10 Oct 2026",
    "Bill To:        Acme Corp",
    "Currency:       INR",
    "",
    "Description                        Amount",
    "Freight services - September     15,466.10",
    "Subtotal                         15,466.10",
    "GST 18%                           2,783.90",
    "GRAND TOTAL                      18,250.00",
]

for line in lines:
    c.drawString(60, y, line)
    y -= 25

c.save()
print(f"PDF created at: {out}")