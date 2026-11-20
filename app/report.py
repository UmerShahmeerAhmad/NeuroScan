"""Builds the one-page PDF report for a saved scan."""
import io
import json
from datetime import timezone
from typing import Optional
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

DISCLAIMER = (
    "This result is decision support produced by a research prototype. It does not replace "
    "a radiologist's diagnosis and must be confirmed by a qualified clinician."
)
NAMES = {"notumor": "No tumor", "glioma": "Glioma", "meningioma": "Meningioma",
         "pituitary": "Pituitary tumor", "other": "Other"}
TEAL = colors.HexColor("#0f766e")
INK = colors.HexColor("#14213d")
GREY = colors.HexColor("#64748b")


def _nice(name: str) -> str:
    return NAMES.get(name, name.replace("_", " ").title())


def _fit_image(data: bytes, max_w: float, max_h: float) -> RLImage:
    from PIL import Image

    width, height = Image.open(io.BytesIO(data)).size
    scale = min(max_w / width, max_h / height)
    return RLImage(io.BytesIO(data), width=width * scale, height=height * scale)


def build_report(row, doctor, image_png: Optional[bytes], heatmap_png: Optional[bytes],
                 low_confidence: bool) -> bytes:
    base = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=base["Title"], textColor=INK, fontSize=20, alignment=0, spaceAfter=2)
    sub = ParagraphStyle("sub", parent=base["Normal"], textColor=GREY, fontSize=9)
    h2 = ParagraphStyle("h2", parent=base["Heading3"], textColor=TEAL, fontSize=11, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("body", parent=base["Normal"], fontSize=9.5, leading=13, textColor=INK)
    small = ParagraphStyle("small", parent=body, fontSize=8, textColor=GREY, leading=11)
    big = ParagraphStyle("big", parent=body, fontSize=18, leading=22, textColor=INK, fontName="Helvetica-Bold")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title="NeuroScan AI scan report", author="NeuroScan AI")
    story = [Paragraph("NeuroScan AI", h1), Paragraph("Brain MRI classification report", sub), Spacer(1, 8)]

    created = row.created_at
    if created is not None:
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        stamp = created.astimezone(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    else:
        stamp = "-"
    info = [
        ["Scan ID", str(row.id), "Date", stamp],
        ["Case reference", row.patient_ref or "-", "File", row.original_filename or "-"],
        ["Requested by", doctor.full_name, "Institution", doctor.institution or "-"],
        ["Model", row.model_name or "-", "", ""],
    ]
    t = Table(info, colWidths=[28 * mm, 55 * mm, 24 * mm, 63 * mm])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8.5), ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("TEXTCOLOR", (0, 0), (0, -1), GREY), ("TEXTCOLOR", (2, 0), (2, -1), GREY),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story += [t, Spacer(1, 10)]

    story.append(Paragraph("Result", h2))
    story.append(Paragraph(f"{_nice(row.predicted_class)} &nbsp;<font size=12 color='#0f766e'>"
                           f"{row.confidence * 100:.1f}% confidence</font>", big))
    if low_confidence:
        story.append(Spacer(1, 4))
        story.append(Paragraph("<b>Review manually.</b> The model's confidence is below its own limit for this scan.", body))

    if getattr(row, "feedback", None):
        story.append(Spacer(1, 4))
        verdict = "agrees" if row.feedback == "agree" else "disagrees"
        note = f" Note: {escape(row.feedback_note)}" if row.feedback_note else ""
        story.append(Paragraph(f"<b>Doctor feedback:</b> the doctor {verdict} with this result.{note}", body))

    # images side by side
    cells, captions = [], []
    if image_png:
        cells.append(_fit_image(image_png, 80 * mm, 80 * mm)); captions.append("Uploaded image")
    if heatmap_png:
        cells.append(_fit_image(heatmap_png, 80 * mm, 80 * mm)); captions.append("Grad-CAM heatmap")
    if cells:
        story.append(Spacer(1, 8))
        grid = Table([cells, [Paragraph(c, small) for c in captions]], colWidths=[87 * mm] * len(cells))
        grid.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, 0), "MIDDLE")]))
        story.append(grid)
        if heatmap_png:
            story.append(Paragraph("The heatmap marks the areas that influenced the model's answer most "
                                   "(red is strongest). It is a visual aid, not a tumor outline.", small))

    story.append(Paragraph("Probability of each class", h2))
    probs = sorted(json.loads(row.probabilities).items(), key=lambda kv: kv[1], reverse=True)
    rows = [["Class", "Probability"]] + [[_nice(k), f"{v * 100:.2f}%"] for k, v in probs]
    pt = Table(rows, colWidths=[60 * mm, 30 * mm], hAlign="LEFT")
    pt.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9), ("TEXTCOLOR", (0, 0), (-1, 0), GREY),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"), ("ALIGN", (1, 0), (1, -1), "RIGHT"),
    ]))
    story += [pt, Spacer(1, 12), Paragraph(DISCLAIMER, small)]

    doc.build(story)
    return buffer.getvalue()
