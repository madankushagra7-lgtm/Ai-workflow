"""
Generates a branded A4 PDF competitor analysis report.
Reads .tmp/analysis.json and branding_config.json.
Saves to reports/competitor_analysis_YYYY-MM-DD.pdf
"""

import json
import os
import sys
from datetime import date

from dotenv import load_dotenv
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))

PAGE_W, PAGE_H = A4
MARGIN = 2.5 * cm


def hex_color(hex_str, fallback="#1A1A2E"):
    try:
        h = hex_str.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return colors.Color(r / 255, g / 255, b / 255)
    except Exception:
        h = fallback.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return colors.Color(r / 255, g / 255, b / 255)


def load_branding():
    path = os.path.join(ROOT, "branding_config.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_analysis():
    path = os.path.join(ROOT, ".tmp", "analysis.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_styles(branding):
    primary = hex_color(branding.get("primary_color", "#1A1A2E"))
    accent = hex_color(branding.get("accent_color", "#0F3460"))
    dark_gray = colors.Color(0.2, 0.2, 0.2)
    mid_gray = colors.Color(0.5, 0.5, 0.5)

    return {
        "ReportTitle": ParagraphStyle(
            "ReportTitle",
            fontName="Helvetica-Bold",
            fontSize=30,
            textColor=primary,
            spaceAfter=10,
            alignment=TA_CENTER,
            leading=36,
        ),
        "Subtitle": ParagraphStyle(
            "Subtitle",
            fontName="Helvetica",
            fontSize=16,
            textColor=accent,
            spaceAfter=6,
            alignment=TA_CENTER,
        ),
        "Caption": ParagraphStyle(
            "Caption",
            fontName="Helvetica-Oblique",
            fontSize=9,
            textColor=mid_gray,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "H1": ParagraphStyle(
            "H1",
            fontName="Helvetica-Bold",
            fontSize=18,
            textColor=primary,
            spaceBefore=18,
            spaceAfter=8,
            leading=22,
        ),
        "H2": ParagraphStyle(
            "H2",
            fontName="Helvetica-Bold",
            fontSize=13,
            textColor=accent,
            spaceBefore=12,
            spaceAfter=6,
            leading=16,
        ),
        "Body": ParagraphStyle(
            "Body",
            fontName="Helvetica",
            fontSize=10,
            textColor=dark_gray,
            spaceAfter=8,
            leading=14,
        ),
        "BulletItem": ParagraphStyle(
            "BulletItem",
            fontName="Helvetica",
            fontSize=10,
            textColor=dark_gray,
            leftIndent=16,
            spaceAfter=4,
            leading=14,
            bulletIndent=4,
        ),
        "NumberedItem": ParagraphStyle(
            "NumberedItem",
            fontName="Helvetica",
            fontSize=10,
            textColor=dark_gray,
            leftIndent=20,
            spaceAfter=6,
            leading=14,
        ),
        "ActionTitle": ParagraphStyle(
            "ActionTitle",
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=dark_gray,
            spaceAfter=2,
            leading=14,
        ),
        "Warning": ParagraphStyle(
            "Warning",
            fontName="Helvetica-Oblique",
            fontSize=9,
            textColor=colors.Color(0.7, 0.4, 0),
            spaceAfter=6,
        ),
        "TOCEntry": ParagraphStyle(
            "TOCEntry",
            fontName="Helvetica",
            fontSize=11,
            textColor=dark_gray,
            spaceAfter=6,
            leading=16,
        ),
        "TableHeader": ParagraphStyle(
            "TableHeader",
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=colors.white,
            alignment=TA_CENTER,
        ),
        "TableCell": ParagraphStyle(
            "TableCell",
            fontName="Helvetica",
            fontSize=9,
            textColor=dark_gray,
            leading=12,
        ),
    }


class ReportBuilder:
    def __init__(self, analysis, branding):
        self.analysis = analysis
        self.branding = branding
        self.styles = build_styles(branding)
        self.primary = hex_color(branding.get("primary_color", "#1A1A2E"))
        self.secondary = hex_color(branding.get("secondary_color", "#16213E"))
        self.accent = hex_color(branding.get("accent_color", "#0F3460"))
        self.company_name = branding.get("company_name", "Your Company")
        self.today = date.today().strftime("%B %d, %Y")
        self.today_file = date.today().strftime("%Y-%m-%d")
        self._page_num = [0]

    def _header_footer(self, canvas, doc):
        canvas.saveState()
        page_num = doc.page

        if page_num > 1:
            canvas.setStrokeColor(self.accent)
            canvas.setLineWidth(0.5)
            footer_y = MARGIN - 0.4 * cm
            canvas.line(MARGIN, footer_y + 0.5 * cm, PAGE_W - MARGIN, footer_y + 0.5 * cm)

            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(colors.Color(0.5, 0.5, 0.5))
            canvas.drawString(MARGIN, footer_y, self.company_name)
            canvas.drawCentredString(PAGE_W / 2, footer_y, "Confidential")
            canvas.drawRightString(PAGE_W - MARGIN, footer_y, f"Page {page_num}")

        canvas.restoreState()

    def _divider(self, story, color=None):
        story.append(Spacer(1, 4))
        story.append(HRFlowable(
            width="100%",
            thickness=1,
            color=color or self.accent,
            spaceAfter=8,
        ))

    def _h1(self, story, text):
        story.append(Paragraph(text, self.styles["H1"]))
        self._divider(story, self.primary)

    def _h2(self, story, text):
        story.append(Paragraph(text, self.styles["H2"]))

    def _body(self, story, text):
        if text:
            story.append(Paragraph(str(text), self.styles["Body"]))

    def _bullet(self, story, items):
        for item in items:
            story.append(Paragraph(f"• {item}", self.styles["BulletItem"]))

    def _cover_page(self, story):
        story.append(Spacer(1, 3 * cm))

        logo_path = self.branding.get("logo_path")
        if logo_path and os.path.isfile(logo_path):
            try:
                img = Image(logo_path, width=6 * cm, height=3 * cm, kind="proportional")
                img.hAlign = "CENTER"
                story.append(img)
                story.append(Spacer(1, 1 * cm))
            except Exception:
                self._logo_text_fallback(story)
        else:
            self._logo_text_fallback(story)

        story.append(Paragraph("Competitor Analysis Report", self.styles["ReportTitle"]))
        story.append(Spacer(1, 0.3 * cm))
        story.append(Paragraph(self.company_name, self.styles["Subtitle"]))
        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph(self.today, self.styles["Caption"]))
        story.append(Spacer(1, 1 * cm))
        self._divider(story, self.accent)
        story.append(Spacer(1, 2 * cm))

        meta = self.analysis.get("analysis_metadata", {})
        n_competitors = meta.get("competitors_analyzed", len(self.analysis.get("competitors", [])))
        story.append(Paragraph(
            f"Analyzing {n_competitors} competitors in your market",
            self.styles["Caption"],
        ))

    def _logo_text_fallback(self, story):
        logo_table = Table(
            [[Paragraph(self.company_name, ParagraphStyle(
                "LogoText",
                fontName="Helvetica-Bold",
                fontSize=20,
                textColor=colors.white,
                alignment=TA_CENTER,
            ))]],
            colWidths=[8 * cm],
            rowHeights=[2.2 * cm],
        )
        logo_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), self.primary),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROUNDEDCORNERS", [6]),
        ]))
        story.append(logo_table)
        story.append(Spacer(1, 1 * cm))

    def _toc(self, story):
        self._h1(story, "Contents")
        competitors = self.analysis.get("competitors", [])
        toc_entries = [
            ("1", "Executive Summary"),
        ]
        for i, c in enumerate(competitors, 1):
            toc_entries.append((f"2.{i}", f"Competitor: {c.get('name', f'Competitor {i}')}"))
        toc_entries += [
            ("3", "SWOT Comparison"),
            ("4", "Market Gaps & Opportunities"),
            ("5", "Recommended Actions"),
        ]
        for num, title in toc_entries:
            story.append(Paragraph(
                f"<b>{num}</b> &nbsp;&nbsp; {title}",
                self.styles["TOCEntry"],
            ))

    def _executive_summary(self, story):
        self._h1(story, "1. Executive Summary")
        summary = self.analysis.get("executive_summary", "No summary available.")
        for para in summary.split("\n\n"):
            if para.strip():
                self._body(story, para.strip())

    def _competitor_profiles(self, story):
        competitors = self.analysis.get("competitors", [])
        for i, comp in enumerate(competitors, 1):
            story.append(PageBreak())
            name = comp.get("name", f"Competitor {i}")
            self._h1(story, f"2.{i}. {name}")

            if comp.get("data_quality") == "limited":
                story.append(Paragraph(
                    "Note: Limited data was available for this competitor. Analysis is based on partial information.",
                    self.styles["Warning"],
                ))

            self._h2(story, "Overview")
            self._body(story, comp.get("overview", "N/A"))

            self._h2(story, "Target Market")
            self._body(story, comp.get("target_market", "N/A"))

            self._h2(story, "Pricing")
            self._body(story, comp.get("pricing_summary", "Not publicly available"))

            key_features = comp.get("key_features", [])
            if key_features:
                self._h2(story, "Key Features / Services")
                self._bullet(story, key_features)

            strengths = comp.get("strengths", [])
            if strengths:
                self._h2(story, "Strengths")
                self._bullet(story, strengths)

            weaknesses = comp.get("weaknesses", [])
            if weaknesses:
                self._h2(story, "Weaknesses")
                self._bullet(story, weaknesses)

            self._h2(story, "Online Presence")
            self._body(story, comp.get("online_presence", "N/A"))

            url = comp.get("url", "")
            if url:
                story.append(Paragraph(
                    f"Website: <link href='{url}' color='#0F3460'>{url}</link>",
                    self.styles["Caption"],
                ))

    def _swot_table(self, story):
        story.append(PageBreak())
        self._h1(story, "3. SWOT Comparison")

        swot = self.analysis.get("swot_comparison", {})

        def fmt_list(items):
            if not items:
                return "—"
            return "\n".join(f"• {x}" for x in items)

        our_strengths = fmt_list(swot.get("strengths", {}).get("our_business", []))
        comp_strengths = fmt_list(swot.get("strengths", {}).get("competitor_aggregate", []))
        our_weaknesses = fmt_list(swot.get("weaknesses", {}).get("our_business", []))
        comp_weaknesses = fmt_list(swot.get("weaknesses", {}).get("competitor_aggregate", []))
        opportunities = fmt_list(swot.get("opportunities", []))
        threats = fmt_list(swot.get("threats", []))

        cell_style = self.styles["TableCell"]
        header_style = self.styles["TableHeader"]

        data = [
            [
                Paragraph("Category", header_style),
                Paragraph("Our Business", header_style),
                Paragraph("Competitors (Aggregate)", header_style),
            ],
            [
                Paragraph("Strengths", cell_style),
                Paragraph(our_strengths, cell_style),
                Paragraph(comp_strengths, cell_style),
            ],
            [
                Paragraph("Weaknesses", cell_style),
                Paragraph(our_weaknesses, cell_style),
                Paragraph(comp_weaknesses, cell_style),
            ],
            [
                Paragraph("Opportunities", header_style),
                Paragraph(opportunities, cell_style),
                Paragraph("", cell_style),
            ],
            [
                Paragraph("Threats", header_style),
                Paragraph(threats, cell_style),
                Paragraph("", cell_style),
            ],
        ]

        col_widths = [3.5 * cm, 7.5 * cm, 7.5 * cm]
        table = Table(data, colWidths=col_widths, repeatRows=1)

        light_bg = colors.Color(0.94, 0.94, 0.97)

        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), self.primary),
            ("BACKGROUND", (0, 3), (0, 3), self.secondary),
            ("BACKGROUND", (0, 4), (0, 4), self.secondary),
            ("BACKGROUND", (0, 1), (-1, 1), light_bg),
            ("BACKGROUND", (0, 2), (-1, 2), colors.white),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("TEXTCOLOR", (0, 3), (0, 3), colors.white),
            ("TEXTCOLOR", (0, 4), (0, 4), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.Color(0.8, 0.8, 0.8)),
            ("ROWBACKGROUNDS", (1, 3), (-1, 4), [light_bg, colors.white]),
            ("SPAN", (1, 3), (2, 3)),
            ("SPAN", (1, 4), (2, 4)),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))

        story.append(table)

    def _market_gaps(self, story):
        story.append(PageBreak())
        self._h1(story, "4. Market Gaps & Opportunities")
        gaps = self.analysis.get("market_gaps", [])
        if gaps:
            self._bullet(story, gaps)
        else:
            self._body(story, "No market gaps identified.")

    def _recommended_actions(self, story):
        story.append(PageBreak())
        self._h1(story, "5. Recommended Actions")

        actions = self.analysis.get("recommended_actions", [])
        if not actions:
            self._body(story, "No recommended actions available.")
            return

        priority_colors = {
            "high": colors.Color(0.7, 0.1, 0.1),
            "medium": colors.Color(0.7, 0.5, 0.0),
            "low": colors.Color(0.2, 0.5, 0.2),
        }

        for i, action in enumerate(actions, 1):
            title = action.get("title", f"Action {i}")
            description = action.get("description", "")
            priority = action.get("priority", "medium").lower()
            timeframe = action.get("timeframe", "").replace("_", " ").title()

            p_color = priority_colors.get(priority, colors.Color(0.3, 0.3, 0.3))
            priority_label = f"[{priority.upper()}]"
            timeframe_label = f" — {timeframe}" if timeframe else ""

            story.append(Paragraph(
                f"<b>{i}. {title}</b> "
                f"<font color='#{int(p_color.red*255):02x}{int(p_color.green*255):02x}{int(p_color.blue*255):02x}'>{priority_label}</font>"
                f"<font color='#888888'>{timeframe_label}</font>",
                self.styles["ActionTitle"],
            ))
            if description:
                self._body(story, description)
            story.append(Spacer(1, 4))

    def build(self):
        reports_dir = os.path.join(ROOT, "reports")
        os.makedirs(reports_dir, exist_ok=True)
        out_path = os.path.join(reports_dir, f"competitor_analysis_{self.today_file}.pdf")

        doc = SimpleDocTemplate(
            out_path,
            pagesize=A4,
            leftMargin=MARGIN,
            rightMargin=MARGIN,
            topMargin=MARGIN,
            bottomMargin=MARGIN + 0.6 * cm,
            title="Competitor Analysis Report",
            author=self.company_name,
        )

        story = []
        self._cover_page(story)
        story.append(PageBreak())
        self._toc(story)
        story.append(PageBreak())
        self._executive_summary(story)
        self._competitor_profiles(story)
        self._swot_table(story)
        self._market_gaps(story)
        self._recommended_actions(story)

        doc.build(story, onFirstPage=self._header_footer, onLaterPages=self._header_footer)
        return out_path


def main():
    branding = load_branding()
    analysis = load_analysis()
    builder = ReportBuilder(analysis, branding)
    out_path = builder.build()
    print(f"[OK] Report saved to {out_path}")


if __name__ == "__main__":
    main()
