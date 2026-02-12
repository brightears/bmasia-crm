"""
Sales Export Service for BMAsia CRM

Generates PDF exports for Sales reports:
- Opportunities List (filtered)
- Sales Performance Summary

Uses ReportLab for PDF generation.
"""

import logging
from io import BytesIO
from datetime import datetime
from typing import Dict, List, Optional

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image,
    HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Register Unicode-capable fonts (DejaVu ships with ReportLab)
try:
    pdfmetrics.getFont('DejaVuSans')
except KeyError:
    pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))
    pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', 'DejaVuSans-Bold.ttf'))

import os
from django.conf import settings

logger = logging.getLogger(__name__)

# Entity info using full Company model names
ENTITY_INFO = {
    'BMAsia Limited': {'currency': 'USD', 'symbol': '$', 'name': 'BMAsia Limited'},
    'BMAsia (Thailand) Co., Ltd.': {'currency': 'THB', 'symbol': 'THB ', 'name': 'BMAsia (Thailand) Co., Ltd.'},
}

# Stage colors matching frontend
STAGE_COLORS = {
    'Contacted': colors.HexColor('#2196f3'),
    'Quotation Sent': colors.HexColor('#ff9800'),
    'Contract Sent': colors.HexColor('#9c27b0'),
    'Won': colors.HexColor('#4caf50'),
    'Lost': colors.HexColor('#f44336'),
}


class SalesExportService:
    """Service for generating PDF exports of sales reports."""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Set up custom PDF styles for BMAsia branding."""
        self.title_style = ParagraphStyle(
            'SalesTitle',
            parent=self.styles['Heading1'],
            fontSize=22,
            textColor=colors.HexColor('#FFA500'),
            spaceAfter=12,
            alignment=TA_CENTER,
            fontName='DejaVuSans-Bold'
        )

        self.heading_style = ParagraphStyle(
            'SalesHeading',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#424242'),
            spaceAfter=8,
            spaceBefore=12,
            fontName='DejaVuSans-Bold'
        )

        self.body_style = ParagraphStyle(
            'SalesBody',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#424242'),
            leading=14
        )

        self.small_style = ParagraphStyle(
            'SalesSmall',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#757575'),
            leading=10
        )

        self.cell_style = ParagraphStyle(
            'SalesCell',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#424242'),
            leading=11
        )

    def _format_currency(self, value, billing_entity=None):
        """Format currency based on billing entity."""
        if billing_entity and billing_entity in ENTITY_INFO:
            symbol = ENTITY_INFO[billing_entity]['symbol']
        else:
            symbol = '$'
        if value is None:
            value = 0
        if value < 0:
            return f"({symbol}{abs(value):,.0f})"
        return f"{symbol}{value:,.0f}"

    def _add_pdf_header(self, elements, title, subtitle_lines):
        """Add standard header with logo and title."""
        logo_path = os.path.join(
            settings.BASE_DIR, 'crm_app', 'static', 'crm_app', 'images', 'bmasia_logo.png'
        )
        try:
            if os.path.exists(logo_path):
                logo = Image(logo_path, width=140, height=56, kind='proportional')
                logo.hAlign = 'LEFT'
                elements.append(logo)
            else:
                elements.append(Paragraph("BM ASIA", self.title_style))
        except Exception:
            elements.append(Paragraph("BM ASIA", self.title_style))

        # Orange accent line
        elements.append(Spacer(1, 0.05 * inch))
        elements.append(HRFlowable(
            width="100%", thickness=2,
            color=colors.HexColor('#FFA500'),
            spaceBefore=0, spaceAfter=0
        ))
        elements.append(Spacer(1, 0.15 * inch))

        # Title
        elements.append(Paragraph(title, self.title_style))

        # Subtitle lines
        if subtitle_lines:
            info_text = '<br/>'.join(f"<b>{k}:</b> {v}" for k, v in subtitle_lines.items() if v and not k.startswith('_'))
            elements.append(Paragraph(info_text, self.body_style))
        elements.append(Spacer(1, 0.2 * inch))

    def _add_pdf_footer(self, elements):
        """Add footer with generation timestamp."""
        elements.append(Spacer(1, 0.3 * inch))
        elements.append(HRFlowable(
            width="100%", thickness=0.5,
            color=colors.HexColor('#e0e0e0'),
            spaceBefore=0, spaceAfter=0
        ))
        elements.append(Spacer(1, 0.1 * inch))
        footer_text = f"Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}"
        elements.append(Paragraph(footer_text, self.small_style))

    def _create_table_style(self):
        """Create standard table style with BMAsia branding."""
        return TableStyle([
            # Header row - orange background
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FFA500')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONT', (0, 0), (-1, 0), 'DejaVuSans-Bold', 9),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            # Data rows
            ('FONT', (0, 1), (-1, -1), 'DejaVuSans', 8),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#424242')),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
            # Alternating row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fafafa')]),
        ])

    # =========================================================================
    # OPPORTUNITIES LIST PDF
    # =========================================================================

    def generate_opportunities_pdf(self, opportunities, filters_applied, summary):
        """
        Generate PDF for Opportunities list.

        Args:
            opportunities: list of dicts (opportunity data)
            filters_applied: dict describing active filters
            summary: dict with total_count, total_value, avg_value
        Returns:
            BytesIO PDF buffer
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=landscape(letter),
            topMargin=0.5 * inch, bottomMargin=0.5 * inch,
            leftMargin=0.5 * inch, rightMargin=0.5 * inch
        )

        elements = []

        # Header
        subtitle = {'Date': datetime.now().strftime('%B %d, %Y')}
        if filters_applied:
            subtitle.update(filters_applied)

        self._add_pdf_header(elements, "OPPORTUNITIES REPORT", subtitle)

        # Summary section
        entity_for_summary = filters_applied.get('_entity_raw', None)
        summary_data = [
            ['Total Opportunities', 'Total Expected Value', 'Average Deal Size'],
            [
                str(summary.get('total_count', 0)),
                self._format_currency(summary.get('total_value', 0), entity_for_summary),
                self._format_currency(summary.get('avg_value', 0), entity_for_summary),
            ],
        ]
        summary_table = Table(summary_data, colWidths=[2.5 * inch, 2.5 * inch, 2.5 * inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#424242')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONT', (0, 0), (-1, 0), 'DejaVuSans-Bold', 10),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONT', (0, 1), (-1, 1), 'DejaVuSans-Bold', 14),
            ('TEXTCOLOR', (0, 1), (-1, 1), colors.HexColor('#FFA500')),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
        ]))
        elements.append(summary_table)

        if entity_for_summary is None and summary.get('total_count', 0) > 0:
            elements.append(Spacer(1, 0.05 * inch))
            elements.append(Paragraph(
                "<i>Note: Values shown in original currencies (not converted)</i>",
                self.small_style
            ))

        elements.append(Spacer(1, 0.3 * inch))

        # Opportunities table
        if opportunities:
            elements.append(Paragraph("Opportunities", self.heading_style))

            header = ['Company', 'Opportunity', 'Stage', 'Expected Value', 'Probability', 'Owner', 'Expected Close']
            table_data = [header]

            for opp in opportunities:
                entity = opp.get('company_billing_entity', '')
                close_date = opp.get('expected_close_date', '')
                if close_date:
                    try:
                        close_date = datetime.strptime(close_date, '%Y-%m-%d').strftime('%b %d, %Y')
                    except (ValueError, TypeError):
                        pass

                table_data.append([
                    Paragraph(str(opp.get('company_name', '')), self.cell_style),
                    Paragraph(str(opp.get('name', '')), self.cell_style),
                    str(opp.get('stage', '')),
                    self._format_currency(opp.get('expected_value', 0), entity),
                    f"{opp.get('probability', 0)}%",
                    str(opp.get('owner_name', '')),
                    close_date or '-',
                ])

            col_widths = [1.8 * inch, 2.0 * inch, 1.0 * inch, 1.2 * inch, 0.8 * inch, 1.2 * inch, 1.0 * inch]
            table = Table(table_data, colWidths=col_widths, repeatRows=1)

            style = self._create_table_style()
            # Left-align text columns
            style.add('ALIGN', (0, 1), (1, -1), 'LEFT')
            style.add('ALIGN', (5, 1), (5, -1), 'LEFT')
            # Right-align value column
            style.add('ALIGN', (3, 1), (3, -1), 'RIGHT')
            # Center stage, probability, date
            style.add('ALIGN', (2, 1), (2, -1), 'CENTER')
            style.add('ALIGN', (4, 1), (4, -1), 'CENTER')
            style.add('ALIGN', (6, 1), (6, -1), 'CENTER')

            table.setStyle(style)
            elements.append(table)

        # Footer
        self._add_pdf_footer(elements)

        doc.build(elements)
        buffer.seek(0)
        return buffer

    # =========================================================================
    # SALES PERFORMANCE SUMMARY PDF
    # =========================================================================

    def generate_sales_performance_pdf(self, kpis, period_breakdown, top_deals,
                                        year, entity_filter, period_type, service_type=None):
        """
        Generate PDF for Sales Performance summary.

        Args:
            kpis: dict with total_won_value, deals_won, avg_deal_size, win_rate
            period_breakdown: list of dicts with period, deals_won, total_value, avg_value
            top_deals: list of dicts (top won deals)
            year: int
            entity_filter: str (full entity name or 'all')
            period_type: 'monthly' or 'quarterly'
            service_type: str or None ('soundtrack', 'beatbreeze')
        Returns:
            BytesIO PDF buffer
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=letter,
            topMargin=0.5 * inch, bottomMargin=0.5 * inch,
            leftMargin=0.5 * inch, rightMargin=0.5 * inch
        )

        elements = []

        # Determine currency
        entity_info = ENTITY_INFO.get(entity_filter) if entity_filter and entity_filter != 'all' else None
        currency_label = entity_info['currency'] if entity_info else 'USD'
        entity_name = entity_info['name'] if entity_info else 'All Entities'

        # Header
        subtitle = {
            'Year': str(year),
            'Entity': entity_name,
            'Currency': currency_label,
            'View': 'Monthly' if period_type == 'monthly' else 'Quarterly',
        }
        if service_type:
            subtitle['Service'] = 'Soundtrack' if service_type == 'soundtrack' else 'Beat Breeze'
        self._add_pdf_header(elements, "SALES PERFORMANCE REPORT", subtitle)

        # KPI Section
        elements.append(Paragraph("Key Performance Indicators", self.heading_style))

        billing_entity_for_fmt = entity_filter if entity_filter and entity_filter != 'all' else None

        kpi_data = [
            ['Total Won Value', 'Deals Won', 'Avg Deal Size', 'Win Rate'],
            [
                self._format_currency(kpis.get('total_won_value', 0), billing_entity_for_fmt),
                str(kpis.get('deals_won', 0)),
                self._format_currency(kpis.get('avg_deal_size', 0), billing_entity_for_fmt),
                f"{kpis.get('win_rate', 0):.1f}%",
            ],
        ]
        kpi_table = Table(kpi_data, colWidths=[1.75 * inch, 1.75 * inch, 1.75 * inch, 1.75 * inch])
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#424242')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONT', (0, 0), (-1, 0), 'DejaVuSans-Bold', 10),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONT', (0, 1), (-1, 1), 'DejaVuSans-Bold', 16),
            ('TEXTCOLOR', (0, 1), (-1, 1), colors.HexColor('#FFA500')),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
        ]))
        elements.append(kpi_table)
        elements.append(Spacer(1, 0.3 * inch))

        # Period Breakdown Table
        view_label = 'Monthly' if period_type == 'monthly' else 'Quarterly'
        elements.append(Paragraph(f"{view_label} Breakdown", self.heading_style))

        header = ['Period', 'Deals Won', 'Total Value', 'Avg Value']
        table_data = [header]

        total_deals = 0
        total_value = 0

        for period in period_breakdown:
            deals = period.get('deals_won', 0)
            value = period.get('total_value', 0)
            avg = period.get('avg_value', 0)
            total_deals += deals
            total_value += value

            table_data.append([
                period.get('period', ''),
                str(deals),
                self._format_currency(value, billing_entity_for_fmt),
                self._format_currency(avg, billing_entity_for_fmt),
            ])

        # Totals row
        total_avg = total_value / total_deals if total_deals > 0 else 0
        table_data.append([
            'TOTAL',
            str(total_deals),
            self._format_currency(total_value, billing_entity_for_fmt),
            self._format_currency(total_avg, billing_entity_for_fmt),
        ])

        col_widths = [1.5 * inch, 1.5 * inch, 2 * inch, 2 * inch]
        period_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        style = self._create_table_style()
        style.add('ALIGN', (1, 1), (-1, -1), 'RIGHT')
        style.add('ALIGN', (0, 1), (0, -1), 'LEFT')
        # Bold totals row
        style.add('FONT', (0, -1), (-1, -1), 'DejaVuSans-Bold', 9)
        style.add('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#fff3e0'))
        period_table.setStyle(style)
        elements.append(period_table)
        elements.append(Spacer(1, 0.3 * inch))

        # Top Won Deals
        if top_deals:
            elements.append(Paragraph("Top Won Deals", self.heading_style))

            deals_header = ['#', 'Company', 'Deal Name', 'Value', 'Owner']
            deals_data = [deals_header]

            for i, deal in enumerate(top_deals, 1):
                entity = deal.get('company_billing_entity', '')
                deals_data.append([
                    str(i),
                    Paragraph(str(deal.get('company_name', '')), self.cell_style),
                    Paragraph(str(deal.get('name', '')), self.cell_style),
                    self._format_currency(deal.get('expected_value', 0), entity),
                    str(deal.get('owner_name', '')),
                ])

            deals_widths = [0.4 * inch, 2.0 * inch, 2.5 * inch, 1.2 * inch, 1.4 * inch]
            deals_table = Table(deals_data, colWidths=deals_widths, repeatRows=1)
            deals_style = self._create_table_style()
            deals_style.add('ALIGN', (0, 1), (0, -1), 'CENTER')
            deals_style.add('ALIGN', (1, 1), (2, -1), 'LEFT')
            deals_style.add('ALIGN', (3, 1), (3, -1), 'RIGHT')
            deals_style.add('ALIGN', (4, 1), (4, -1), 'LEFT')
            deals_table.setStyle(deals_style)
            elements.append(deals_table)

        # Footer
        self._add_pdf_footer(elements)

        doc.build(elements)
        buffer.seek(0)
        return buffer
