import html2canvas from 'html2canvas';
import jsPDF from 'jspdf';
import * as XLSX from 'xlsx';
import { SalesTarget } from '../types';

export interface ExportOptions {
  filename?: string;
  includeCharts?: boolean;
  format: 'pdf' | 'excel' | 'png';
  title?: string;
  subtitle?: string;
}

export const exportTargetsReport = async (
  targets: SalesTarget[],
  options: ExportOptions
): Promise<void> => {
  const { format, filename = 'sales-targets-report', includeCharts = true, title = 'Sales Targets Report', subtitle } = options;

  try {
    switch (format) {
      case 'pdf':
        await exportToPDF(targets, { filename, includeCharts, title, subtitle });
        break;
      case 'excel':
        await exportToExcel(targets, { filename });
        break;
      case 'png':
        await exportToPNG({ filename });
        break;
      default:
        throw new Error(`Unsupported export format: ${format}`);
    }
  } catch (error) {
    console.error('Export failed:', error);
    throw error;
  }
};

const exportToPDF = async (
  targets: SalesTarget[],
  options: { filename: string; includeCharts: boolean; title: string; subtitle?: string }
): Promise<void> => {
  const pdf = new jsPDF();
  const pageWidth = pdf.internal.pageSize.getWidth();
  const pageHeight = pdf.internal.pageSize.getHeight();
  let yPosition = 20;

  // Add title
  pdf.setFontSize(20);
  pdf.setFont('helvetica', 'bold');
  pdf.text(options.title, pageWidth / 2, yPosition, { align: 'center' });
  yPosition += 15;

  // Add subtitle if provided
  if (options.subtitle) {
    pdf.setFontSize(12);
    pdf.setFont('helvetica', 'normal');
    pdf.text(options.subtitle, pageWidth / 2, yPosition, { align: 'center' });
    yPosition += 15;
  }

  // Add generation date
  pdf.setFontSize(10);
  pdf.text(`Generated on: ${new Date().toLocaleDateString()}`, 20, yPosition);
  yPosition += 20;

  // Summary statistics
  const totalTargets = targets.length;
  const activeTargets = targets.filter(t => t.status === 'Active').length;
  const avgAchievement = targets.reduce((sum, t) => sum + t.achievement_percentage, 0) / Math.max(targets.length, 1);
  const atRiskTargets = targets.filter(t => t.risk_level === 'High').length;

  pdf.setFontSize(14);
  pdf.setFont('helvetica', 'bold');
  pdf.text('Summary', 20, yPosition);
  yPosition += 10;

  pdf.setFontSize(10);
  pdf.setFont('helvetica', 'normal');
  const summaryText = [
    `Total Targets: ${totalTargets}`,
    `Active Targets: ${activeTargets}`,
    `Average Achievement: ${Math.round(avgAchievement)}%`,
    `High Risk Targets: ${atRiskTargets}`,
  ];

  summaryText.forEach(text => {
    pdf.text(text, 25, yPosition);
    yPosition += 8;
  });

  yPosition += 10;

  // Targets table
  if (targets.length > 0) {
    pdf.setFontSize(14);
    pdf.setFont('helvetica', 'bold');
    pdf.text('Target Details', 20, yPosition);
    yPosition += 15;

    // Table headers
    const headers = ['Target Name', 'Type', 'Achievement', 'Status', 'Risk'];
    const colWidths = [60, 25, 25, 25, 20];
    let xPosition = 20;

    pdf.setFontSize(9);
    pdf.setFont('helvetica', 'bold');
    headers.forEach((header, index) => {
      pdf.text(header, xPosition, yPosition);
      xPosition += colWidths[index];
    });
    yPosition += 8;

    // Table rows
    pdf.setFont('helvetica', 'normal');
    targets.forEach(target => {
      if (yPosition > pageHeight - 30) {
        pdf.addPage();
        yPosition = 20;
      }

      xPosition = 20;
      const rowData = [
        target.name.length > 25 ? target.name.substring(0, 25) + '...' : target.name,
        target.target_type,
        `${Math.round(target.achievement_percentage)}%`,
        target.status,
        target.risk_level,
      ];

      rowData.forEach((data, index) => {
        pdf.text(data, xPosition, yPosition);
        xPosition += colWidths[index];
      });
      yPosition += 8;
    });
  }

  // Capture charts if requested
  if (options.includeCharts) {
    try {
      const chartElements = document.querySelectorAll('[data-chart="target"]');
      for (let i = 0; i < Math.min(chartElements.length, 2); i++) {
        const element = chartElements[i] as HTMLElement;
        if (element) {
          const canvas = await html2canvas(element);

          const imgData = canvas.toDataURL('image/png');
          const imgWidth = 150;
          const imgHeight = (canvas.height * imgWidth) / canvas.width;

          if (yPosition + imgHeight > pageHeight - 20) {
            pdf.addPage();
            yPosition = 20;
          }

          pdf.addImage(imgData, 'PNG', 20, yPosition, imgWidth, imgHeight);
          yPosition += imgHeight + 10;
        }
      }
    } catch (error) {
      console.warn('Could not capture charts for PDF export:', error);
    }
  }

  // Save the PDF
  pdf.save(`${options.filename}.pdf`);
};

const exportToExcel = async (
  targets: SalesTarget[],
  options: { filename: string }
): Promise<void> => {
  const workbook = XLSX.utils.book_new();

  // Summary sheet
  const summaryData = [
    ['Sales Targets Report'],
    ['Generated on:', new Date().toLocaleDateString()],
    [''],
    ['Summary Statistics'],
    ['Total Targets:', targets.length],
    ['Active Targets:', targets.filter(t => t.status === 'Active').length],
    ['Average Achievement:', `${Math.round(targets.reduce((sum, t) => sum + t.achievement_percentage, 0) / Math.max(targets.length, 1))}%`],
    ['High Risk Targets:', targets.filter(t => t.risk_level === 'High').length],
    [''],
    ['Target Type Distribution'],
    ['Revenue Targets:', targets.filter(t => t.target_type === 'Revenue').length],
    ['Unit Targets:', targets.filter(t => t.target_type === 'Units').length],
    ['Customer Targets:', targets.filter(t => t.target_type === 'Customers').length],
    ['Contract Targets:', targets.filter(t => t.target_type === 'Contracts').length],
  ];

  const summarySheet = XLSX.utils.aoa_to_sheet(summaryData);
  XLSX.utils.book_append_sheet(workbook, summarySheet, 'Summary');

  // Targets detail sheet
  const targetsData = targets.map(target => ({
    'Target Name': target.name,
    'Type': target.target_type,
    'Period Type': target.period_type,
    'Start Date': new Date(target.period_start).toLocaleDateString(),
    'End Date': new Date(target.period_end).toLocaleDateString(),
    'Target Value': target.target_value,
    'Current Value': target.current_value,
    'Achievement %': Math.round(target.achievement_percentage),
    'Forecasted Achievement %': Math.round(target.forecasted_achievement),
    'Status': target.status,
    'Risk Level': target.risk_level,
    'Assigned To': target.assigned_to_name || (target.team_target ? target.team_name : 'N/A'),
    'Team Target': target.team_target ? 'Yes' : 'No',
    'Days Remaining': target.days_remaining,
    'Created By': target.created_by_name,
    'Created Date': new Date(target.created_at).toLocaleDateString(),
    'Notes': target.notes || '',
  }));

  const targetsSheet = XLSX.utils.json_to_sheet(targetsData);
  XLSX.utils.book_append_sheet(workbook, targetsSheet, 'Targets');

  // Performance analysis sheet
  const performanceData = targets.map(target => ({
    'Target Name': target.name,
    'Achievement %': Math.round(target.achievement_percentage),
    'Expected Daily Progress': target.expected_daily_progress,
    'Actual Daily Progress': target.actual_daily_progress,
    'Variance from Plan': target.variance_from_plan,
    'Forecasted Value': target.forecasted_value,
    'Is On Track': target.is_on_track ? 'Yes' : 'No',
    'Previous Period Achievement': target.previous_period_achievement ? `${target.previous_period_achievement}%` : 'N/A',
    'YoY Growth': target.year_over_year_growth ? `${target.year_over_year_growth}%` : 'N/A',
  }));

  const performanceSheet = XLSX.utils.json_to_sheet(performanceData);
  XLSX.utils.book_append_sheet(workbook, performanceSheet, 'Performance Analysis');

  // Save the workbook
  XLSX.writeFile(workbook, `${options.filename}.xlsx`);
};

const exportToPNG = async (options: { filename: string }): Promise<void> => {
  const targetElement = document.querySelector('[data-export="targets-page"]') as HTMLElement;

  if (!targetElement) {
    throw new Error('Could not find target element for PNG export');
  }

  const canvas = await html2canvas(targetElement);

  // Create download link
  const link = document.createElement('a');
  link.download = `${options.filename}.png`;
  link.href = canvas.toDataURL('image/png');
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};

// Utility function to format target data for sharing
export const formatTargetForSharing = (target: SalesTarget): string => {
  const formatValue = (value: number) => {
    if (target.target_type === 'Revenue') {
      const symbol = target.currency === 'USD' ? '$' : target.currency === 'THB' ? '฿' : '€';
      return `${symbol}${value.toLocaleString()}`;
    }
    return `${value.toLocaleString()} ${target.unit_type || ''}`;
  };

  return `
🎯 ${target.name}

📊 Progress: ${target.achievement_percentage}% (${formatValue(target.current_value)} / ${formatValue(target.target_value)})
📅 Period: ${new Date(target.period_start).toLocaleDateString()} - ${new Date(target.period_end).toLocaleDateString()}
⏱️ Days Remaining: ${target.days_remaining}
🎚️ Status: ${target.status}
⚠️ Risk Level: ${target.risk_level}
📈 Forecast: ${target.forecasted_achievement}% achievement expected

${target.notes ? `📝 Notes: ${target.notes}` : ''}

Generated from BMAsia CRM
  `.trim();
};

// Export individual target as a quick summary
export const exportTargetSummary = async (target: SalesTarget, format: 'text' | 'json' = 'text'): Promise<void> => {
  const content = format === 'text'
    ? formatTargetForSharing(target)
    : JSON.stringify(target, null, 2);

  const blob = new Blob([content], { type: format === 'text' ? 'text/plain' : 'application/json' });
  const url = URL.createObjectURL(blob);

  const link = document.createElement('a');
  link.href = url;
  link.download = `${target.name.replace(/[^a-z0-9]/gi, '_').toLowerCase()}.${format === 'text' ? 'txt' : 'json'}`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  URL.revokeObjectURL(url);
};