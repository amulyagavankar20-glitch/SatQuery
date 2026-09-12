"""
SatQuery AI — PDF Report Generation Service.

Generates an authoritative, cleanly styled analysis report for SAC analysts
containing query intent, talking VLM answer, geospatial metadata, evidence,
and execution audit trace.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    Image as RLImage
)

from backend.schemas import JobView
from backend.services.job_view import (
    resolve_composite_path,
    resolve_overlay_path,
    resolve_asset_preview_path,
    safe_job_file
)

# Color Palette matching SatQuery Brand
PRIMARY_TEAL = HexColor("#5E8F8A")
DARK_BG = HexColor("#121417")
SURFACE_BG = HexColor("#1A1E22")
TEXT_MUTED = HexColor("#666666")
BORDER_COLOR = HexColor("#DDDDDD")


def generate_job_pdf(job_view: JobView) -> bytes:
    """Generate a PDF document representing the JobView report."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontSize=18,
        leading=22,
        textColor=PRIMARY_TEAL,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=TEXT_MUTED,
        spaceAfter=15,
    )
    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=12,
        leading=16,
        textColor=DARK_BG,
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=HexColor("#222222"),
        spaceAfter=8,
    )
    code_style = ParagraphStyle(
        "ReportCode",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=8,
        leading=11,
        textColor=HexColor("#333333"),
    )

    elements: list[Any] = []

    # 1. Header Banner
    elements.append(Paragraph("<b>SatQuery AI — Earth Observation Analysis Report</b>", title_style))
    elements.append(
        Paragraph(
            f"ISRO / DoS SIH26167 · Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            subtitle_style,
        )
    )
    elements.append(HRFlowable(width="100%", thickness=1.5, color=PRIMARY_TEAL, spaceAfter=12))

    # 2. Key Metadata Table
    input_class_val = getattr(job_view, "input_class", getattr(job_view, "input_mode", "UNKNOWN")) or "UNKNOWN"
    confidence_val = (
        (job_view.answer.confidence if job_view.answer else None)
        or getattr(job_view, "confidence", None)
        or "N/A"
    )

    meta_data = [
        [
            Paragraph("<b>Job ID:</b>", body_style),
            Paragraph(str(job_view.job_id), code_style),
            Paragraph("<b>Status:</b>", body_style),
            Paragraph(str(job_view.status).upper(), body_style),
        ],
        [
            Paragraph("<b>Input Mode:</b>", body_style),
            Paragraph(str(input_class_val), body_style),
            Paragraph("<b>Task:</b>", body_style),
            Paragraph(str(job_view.task or "UNROUTED"), body_style),
        ],
        [
            Paragraph("<b>Confidence:</b>", body_style),
            Paragraph(str(confidence_val), body_style),
            Paragraph("<b>Created:</b>", body_style),
            Paragraph(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), body_style),
        ],
    ]
    meta_table = Table(meta_data, colWidths=[80, 180, 80, 180])
    meta_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), HexColor("#F7F9FA")),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ])
    )
    elements.append(meta_table)
    elements.append(Spacer(1, 14))

    # 3. Analyst Query
    elements.append(Paragraph("Analyst Query", heading_style))
    query_box = Table([[Paragraph(f"<i>\"{job_view.query or 'No query recorded'}\"</i>", body_style)]], colWidths=[520])
    query_box.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), HexColor("#F0F4F4")),
            ("BOX", (0, 0), (-1, -1), 1, PRIMARY_TEAL),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ])
    )
    elements.append(query_box)
    elements.append(Spacer(1, 14))

    # 3.5. Imagery & Evidence
    elements.append(Paragraph("Imagery & Visual Evidence", heading_style))
    
    # Try to load composite/original image
    try:
        composite_rel = resolve_composite_path(job_view.job_id)
        # fallback to raw asset 0
        if not safe_job_file(job_view.job_id, composite_rel):
            composite_rel = resolve_asset_preview_path(job_view.job_id, 0)
            
        composite_path = safe_job_file(job_view.job_id, composite_rel) if composite_rel else None
        
        # Try to load overlay/updated image
        overlay_rel = resolve_overlay_path(job_view.job_id)
        overlay_path = safe_job_file(job_view.job_id, overlay_rel) if overlay_rel else None
        
        img_table_data = []
        img_headers = []
        img_row = []
        
        if composite_path and composite_path.exists():
            img_headers.append(Paragraph("<b>Original Input</b>", body_style))
            img_row.append(RLImage(str(composite_path), width=240, height=240, kind='proportional'))
            
        if overlay_path and overlay_path.exists():
            img_headers.append(Paragraph("<b>Processed / Detected Overlay</b>", body_style))
            img_row.append(RLImage(str(overlay_path), width=240, height=240, kind='proportional'))
            
        if img_row:
            img_table = Table([img_headers, img_row], colWidths=[260] * len(img_row))
            img_table.setStyle(
                TableStyle([
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
                ])
            )
            elements.append(img_table)
            elements.append(Spacer(1, 14))
        else:
            elements.append(Paragraph("<i>No visual evidence available for this job.</i>", body_style))
            elements.append(Spacer(1, 14))
            
    except Exception as e:
        elements.append(Paragraph(f"<i>Could not load images: {e}</i>", body_style))
        elements.append(Spacer(1, 14))

    # 4. Grounded Analysis Answer
    elements.append(Paragraph("Specialist & VLM Grounded Findings", heading_style))
    answer_text = (job_view.answer.text if job_view.answer and job_view.answer.text else "Analysis complete. No narrative text generated.")
    answer_box = Table([[Paragraph(answer_text, body_style)]], colWidths=[520])
    answer_box.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), HexColor("#FFFFFF")),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ])
    )
    elements.append(answer_box)
    elements.append(Spacer(1, 14))

    # 5. Routing Plan & Tool Selection
    elements.append(Paragraph("Router Orchestration Plan", heading_style))
    route = job_view.route
    if route:
        selected = ", ".join(route.get("selected_tools", [])) if isinstance(route, dict) else "None"
        route_info = (
            f"<b>Orchestrator:</b> {route.get('model', 'Qwen2.5-3B-Instruct')} | "
            f"<b>Target Task:</b> {route.get('task', job_view.task)} | "
            f"<b>Selected Specialists:</b> {selected}<br/>"
            f"<b>Routing Policy:</b> {route.get('routing_policy', 'deterministic_v1')}"
        )
    else:
        route_info = "Direct execution baseline."
    elements.append(Paragraph(route_info, body_style))
    elements.append(Spacer(1, 14))

    # 6. Execution Trace Receipt
    elements.append(Paragraph("Audit Execution Trace", heading_style))
    trace_events = job_view.traces or []
    if trace_events:
        trace_rows = [["Time (UTC)", "Node", "Tool ID", "Message"]]
        for t in trace_events[-12:]:  # Last 12 steps
            t_time = str(t.timestamp or "")
            trace_rows.append([
                Paragraph(t_time, code_style),
                Paragraph(t.node_name or "-", code_style),
                Paragraph(t.tool_id or "-", code_style),
                Paragraph(t.message or "", code_style),
            ])
        trace_table = Table(trace_rows, colWidths=[70, 110, 110, 230])
        trace_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), HexColor("#E2E8F0")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ])
        )
        elements.append(trace_table)
    else:
        elements.append(Paragraph("No audit trace events recorded.", body_style))

    # Build PDF
    doc.build(elements)
    return buffer.getvalue()
