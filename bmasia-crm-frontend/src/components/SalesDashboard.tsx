import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  IconButton,
  Chip,
  FormControl,
  Select,
  MenuItem,
  SelectChangeEvent,
  CircularProgress,
  Alert,
  Tooltip,
  Snackbar,
} from '@mui/material';
import {
  TrendingUp,
  AttachMoney,
  Assessment,
  People,
  Refresh,
  PictureAsPdf,
  TableChart,
  PersonAdd,
  EventNote,
  CalendarToday,
  Business,
  AccountTree,
} from '@mui/icons-material';
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
} from 'recharts';
import { format, subMonths } from 'date-fns';
import html2canvas from 'html2canvas';
import jsPDF from 'jspdf';
import * as XLSX from 'xlsx';

// Import our custom components
import SalesKPICard from './SalesKPICard';
import SalesActivityFeed from './SalesActivityFeed';
import SalesPipelineFunnel from './charts/SalesPipelineFunnel';
import RevenueTrendChart from './charts/RevenueTrendChart';

interface SalesKPIs {
  totalRevenue: {
    current: number;
    previous: number;
    change: number;
  };
  pipelineValue: number;
  conversionRate: number;
  averageDealSize: number;
  activeOpportunities: number;
  newLeadsThisMonth: number;
}

interface SalesActivity {
  id: string;
  type: 'deal_closed' | 'opportunity_created' | 'follow_up' | 'meeting' | 'call' | 'email' | 'demo' | 'proposal';
  title: string;
  description: string;
  value?: number;
  contact?: string;
  company: string;
  timestamp: string;
  status?: 'completed' | 'scheduled' | 'overdue' | 'in_progress';
  priority?: 'low' | 'medium' | 'high' | 'urgent';
}

interface PipelineData {
  stage: string;
  count: number;
  value: number;
  fill: string;
}

interface PerformerData {
  name: string;
  revenue: number;
  deals: number;
  conversionRate: number;
}

interface TrendData {
  month: string;
  revenue: number;
  opportunities: number;
  deals: number;
}

const COLORS = {
  primary: '#1976d2',
  success: '#2e7d32',
  warning: '#ed6c02',
  error: '#d32f2f',
  info: '#0288d1',
  pipeline: ['#4caf50', '#2196f3', '#ff9800', '#f44336', '#9c27b0'],
};

const SalesDashboard: React.FC = () => {
  const dashboardRef = useRef<HTMLDivElement>(null);
  const [timeFilter, setTimeFilter] = useState<'today' | 'week' | 'month' | 'quarter' | 'year'>('month');
  const [loading, setLoading] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false,
    message: '',
    severity: 'success',
  });
  const [kpis, setKpis] = useState<SalesKPIs>({
    totalRevenue: { current: 0, previous: 0, change: 0 },
    pipelineValue: 0,
    conversionRate: 0,
    averageDealSize: 0,
    activeOpportunities: 0,
    newLeadsThisMonth: 0,
  });
  const [activities, setActivities] = useState<SalesActivity[]>([]);
  const [pipelineData, setPipelineData] = useState<PipelineData[]>([]);
  const [trendData, setTrendData] = useState<TrendData[]>([]);
  const [performerData, setPerformerData] = useState<PerformerData[]>([]);
  const [productData, setProductData] = useState<any[]>([]);

  // Auto-refresh every 5 minutes
  useEffect(() => {
    const interval = setInterval(() => {
      refreshData();
    }, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  // Initial data load
  useEffect(() => {
    loadSalesData();
  }, [timeFilter]);

  const loadSalesData = async () => {
    setLoading(true);
    try {
      // Simulate API calls with mock data
      await new Promise(resolve => setTimeout(resolve, 800));

      setKpis(generateMockKPIs());
      setActivities(generateMockActivities());
      setPipelineData(generateMockPipelineData());
      setTrendData(generateMockTrendData());
      setPerformerData(generateMockPerformerData());
      setProductData(generateMockProductData());

      setLastRefresh(new Date());
    } catch (error) {
      console.error('Error loading sales data:', error);
    } finally {
      setLoading(false);
    }
  };

  const refreshData = useCallback(() => {
    loadSalesData();
  }, [timeFilter]);

  const handleTimeFilterChange = (event: SelectChangeEvent) => {
    setTimeFilter(event.target.value as any);
  };

  const exportToPDF = async () => {
    if (!dashboardRef.current) return;

    try {
      setSnackbar({ open: true, message: 'Generating PDF...', severity: 'success' });

      const canvas = await html2canvas(dashboardRef.current, {
        useCORS: true,
        allowTaint: false,
      });

      const imgData = canvas.toDataURL('image/png');
      const pdf = new jsPDF('l', 'mm', 'a4');
      const imgWidth = 297;
      const imgHeight = (canvas.height * imgWidth) / canvas.width;

      if (imgHeight > 210) {
        // Split into multiple pages if content is too tall
        let position = 0;
        const pageHeight = 210;

        while (position < imgHeight) {
          pdf.addImage(imgData, 'PNG', 0, -position, imgWidth, imgHeight);
          position += pageHeight;

          if (position < imgHeight) {
            pdf.addPage();
          }
        }
      } else {
        pdf.addImage(imgData, 'PNG', 0, 0, imgWidth, imgHeight);
      }

      pdf.save(`sales-dashboard-${format(new Date(), 'yyyy-MM-dd')}.pdf`);
      setSnackbar({ open: true, message: 'PDF exported successfully!', severity: 'success' });
    } catch (error) {
      console.error('Error exporting PDF:', error);
      setSnackbar({ open: true, message: 'Failed to export PDF', severity: 'error' });
    }
  };

  const exportToExcel = () => {
    try {
      setSnackbar({ open: true, message: 'Generating Excel file...', severity: 'success' });

      const workbook = XLSX.utils.book_new();

      // KPIs sheet
      const kpiData = [
        ['Metric', 'Current', 'Previous', 'Change'],
        ['Total Revenue', kpis.totalRevenue.current, kpis.totalRevenue.previous, `${kpis.totalRevenue.change}%`],
        ['Pipeline Value', kpis.pipelineValue, '', ''],
        ['Conversion Rate', `${kpis.conversionRate}%`, '', ''],
        ['Average Deal Size', kpis.averageDealSize, '', ''],
        ['Active Opportunities', kpis.activeOpportunities, '', ''],
        ['New Leads This Month', kpis.newLeadsThisMonth, '', ''],
      ];
      const kpiSheet = XLSX.utils.aoa_to_sheet(kpiData);
      XLSX.utils.book_append_sheet(workbook, kpiSheet, 'KPIs');

      // Pipeline sheet
      const pipelineSheet = XLSX.utils.json_to_sheet(pipelineData);
      XLSX.utils.book_append_sheet(workbook, pipelineSheet, 'Pipeline');

      // Performers sheet
      const performerSheet = XLSX.utils.json_to_sheet(performerData);
      XLSX.utils.book_append_sheet(workbook, performerSheet, 'Top Performers');

      // Activities sheet
      const activitiesSheet = XLSX.utils.json_to_sheet(activities);
      XLSX.utils.book_append_sheet(workbook, activitiesSheet, 'Activities');

      // Trend data sheet
      const trendSheet = XLSX.utils.json_to_sheet(trendData);
      XLSX.utils.book_append_sheet(workbook, trendSheet, 'Revenue Trend');

      XLSX.writeFile(workbook, `sales-data-${format(new Date(), 'yyyy-MM-dd')}.xlsx`);
      setSnackbar({ open: true, message: 'Excel file exported successfully!', severity: 'success' });
    } catch (error) {
      console.error('Error exporting Excel:', error);
      setSnackbar({ open: true, message: 'Failed to export Excel file', severity: 'error' });
    }
  };


  return (
    <Box ref={dashboardRef} sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" component="h1" gutterBottom>
            Sales Dashboard
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Last updated: {format(lastRefresh, 'MMM dd, yyyy HH:mm')}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <FormControl size="small">
            <Select value={timeFilter} onChange={handleTimeFilterChange}>
              <MenuItem value="today">Today</MenuItem>
              <MenuItem value="week">This Week</MenuItem>
              <MenuItem value="month">This Month</MenuItem>
              <MenuItem value="quarter">This Quarter</MenuItem>
              <MenuItem value="year">This Year</MenuItem>
            </Select>
          </FormControl>
          <Tooltip title="Refresh Data">
            <IconButton onClick={refreshData} disabled={loading}>
              <Refresh />
            </IconButton>
          </Tooltip>
          <Tooltip title="Export as PDF">
            <IconButton onClick={exportToPDF}>
              <PictureAsPdf />
            </IconButton>
          </Tooltip>
          <Tooltip title="Export to Excel">
            <IconButton onClick={exportToExcel}>
              <TableChart />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', mb: 3 }}>
          <CircularProgress />
        </Box>
      )}

      {/* KPI Cards */}
      <Box sx={{ display: 'flex', gap: 3, mb: 3, flexWrap: 'wrap' }}>
        <Box sx={{ flex: '1 1 250px', minWidth: 200 }}>
          <SalesKPICard
            title="Total Revenue"
            value={kpis.totalRevenue.current}
            previousValue={kpis.totalRevenue.previous}
            icon={<AttachMoney />}
            format="currency"
            loading={loading}
            tooltip="Total revenue for the selected time period"
            trendValue={kpis.totalRevenue.change}
          />
        </Box>

        <Box sx={{ flex: '1 1 250px', minWidth: 200 }}>
          <SalesKPICard
            title="Pipeline Value"
            value={kpis.pipelineValue}
            icon={<AccountTree />}
            format="currency"
            loading={loading}
            tooltip="Total value of opportunities in the sales pipeline"
          />
        </Box>

        <Box sx={{ flex: '1 1 250px', minWidth: 200 }}>
          <SalesKPICard
            title="Conversion Rate"
            value={kpis.conversionRate}
            icon={<Assessment />}
            format="percentage"
            loading={loading}
            tooltip="Percentage of leads that convert to customers"
          />
        </Box>

        <Box sx={{ flex: '1 1 250px', minWidth: 200 }}>
          <SalesKPICard
            title="Avg Deal Size"
            value={kpis.averageDealSize}
            icon={<AttachMoney />}
            format="currency"
            loading={loading}
            tooltip="Average value of closed deals"
          />
        </Box>

        <Box sx={{ flex: '1 1 250px', minWidth: 200 }}>
          <SalesKPICard
            title="Active Opportunities"
            value={kpis.activeOpportunities}
            icon={<Business />}
            loading={loading}
            tooltip="Number of opportunities currently in the pipeline"
          />
        </Box>

        <Box sx={{ flex: '1 1 250px', minWidth: 200 }}>
          <SalesKPICard
            title="New Leads"
            value={kpis.newLeadsThisMonth}
            icon={<People />}
            loading={loading}
            tooltip="New leads generated this month"
          />
        </Box>
      </Box>

      {/* Charts Row 1 */}
      <Box sx={{ display: 'flex', gap: 3, mb: 3, flexWrap: 'wrap' }}>
        {/* Sales Pipeline Funnel */}
        <Box sx={{ flex: '1 1 400px', minWidth: 350 }}>
          <SalesPipelineFunnel data={pipelineData} loading={loading} />
        </Box>

        {/* Revenue Trend */}
        <Box sx={{ flex: '1 1 400px', minWidth: 350 }}>
          <RevenueTrendChart data={trendData} loading={loading} />
        </Box>
      </Box>

      {/* Charts Row 2 */}
      <Box sx={{ display: 'flex', gap: 3, mb: 3, flexWrap: 'wrap' }}>
        {/* Top Performers */}
        <Box sx={{ flex: '1 1 400px', minWidth: 350 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Top Performers
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={performerData} layout="horizontal">
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" />
                  <YAxis type="category" dataKey="name" width={80} />
                  <RechartsTooltip formatter={(value) => `$${(value as number).toLocaleString()}`} />
                  <Bar dataKey="revenue" fill={COLORS.info} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Box>

        {/* Sales by Product */}
        <Box sx={{ flex: '1 1 400px', minWidth: 350 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Sales by Product/Service
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={productData}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {productData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS.pipeline[index % COLORS.pipeline.length]} />
                    ))}
                  </Pie>
                  <RechartsTooltip formatter={(value) => `$${(value as number).toLocaleString()}`} />
                </PieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Box>
      </Box>

      {/* Bottom Row */}
      <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
        {/* Quick Actions */}
        <Box sx={{ flex: '1 1 300px', minWidth: 250 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Quick Actions
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <Button
                  variant="contained"
                  startIcon={<PersonAdd />}
                  fullWidth
                >
                  Add New Lead
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<Business />}
                  fullWidth
                >
                  Create Opportunity
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<EventNote />}
                  fullWidth
                >
                  Log Activity
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<CalendarToday />}
                  fullWidth
                >
                  Schedule Meeting
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Box>

        {/* Activity Feed */}
        <Box sx={{ flex: '1 1 500px', minWidth: 400 }}>
          <SalesActivityFeed
            activities={activities}
            loading={loading}
            maxItems={6}
            showViewAll={true}
            onViewAll={() => console.log('View all activities')}
          />
        </Box>
      </Box>

      {/* Snackbar for notifications */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
        message={snackbar.message}
      />
    </Box>
  );
};

// Mock data generators
const generateMockKPIs = (): SalesKPIs => ({
  totalRevenue: {
    current: 1250000,
    previous: 1100000,
    change: 13.6,
  },
  pipelineValue: 890000,
  conversionRate: 24.5,
  averageDealSize: 45000,
  activeOpportunities: 42,
  newLeadsThisMonth: 28,
});

const generateMockActivities = (): SalesActivity[] => [
  {
    id: '1',
    type: 'deal_closed',
    title: 'Major Deal Closed',
    description: 'Soundtrack Unlimited annual contract signed',
    value: 125000,
    contact: 'Sarah Johnson, Operations Director',
    company: 'RetailMax Corporation',
    timestamp: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString(),
    status: 'completed',
    priority: 'high',
  },
  {
    id: '2',
    type: 'opportunity_created',
    title: 'High-Value Opportunity',
    description: 'Multi-location music solution for restaurant chain',
    value: 180000,
    contact: 'Michael Chen, Franchise Manager',
    company: 'Golden Dragon Restaurants',
    timestamp: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
    status: 'in_progress',
    priority: 'urgent',
  },
  {
    id: '3',
    type: 'demo',
    title: 'Product Demo Completed',
    description: 'Successful demo of Beat Breeze solution',
    contact: 'Lisa Wong, Marketing Manager',
    company: 'Boutique Hotels Group',
    timestamp: new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString(),
    status: 'completed',
    priority: 'medium',
  },
  {
    id: '4',
    type: 'call',
    title: 'Discovery Call',
    description: 'Initial consultation and needs assessment',
    contact: 'David Kim, Store Manager',
    company: 'Fashion Forward Retail',
    timestamp: new Date(Date.now() - 7 * 60 * 60 * 1000).toISOString(),
    status: 'completed',
    priority: 'medium',
  },
  {
    id: '5',
    type: 'proposal',
    title: 'Proposal Sent',
    description: 'Custom Soundtrack Essential package proposal',
    value: 65000,
    contact: 'Amanda Rodriguez, Operations Head',
    company: 'Cafe Network LLC',
    timestamp: new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString(),
    status: 'scheduled',
    priority: 'high',
  },
  {
    id: '6',
    type: 'follow_up',
    title: 'Follow-up Meeting',
    description: 'Contract terms discussion',
    contact: 'Robert Taylor, CEO',
    company: 'Fitness First Gyms',
    timestamp: new Date(Date.now() - 18 * 60 * 60 * 1000).toISOString(),
    status: 'scheduled',
    priority: 'medium',
  },
  {
    id: '7',
    type: 'email',
    title: 'Quote Requested',
    description: 'Customer requesting detailed pricing',
    contact: 'Jennifer Lee, Procurement',
    company: 'Urban Spaces Co-working',
    timestamp: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
    status: 'in_progress',
    priority: 'low',
  },
  {
    id: '8',
    type: 'meeting',
    title: 'Contract Signing',
    description: 'Final contract review and signing',
    value: 95000,
    contact: 'Thomas Wilson, Managing Director',
    company: 'Luxury Spa Resorts',
    timestamp: new Date(Date.now() - 30 * 60 * 60 * 1000).toISOString(),
    status: 'scheduled',
    priority: 'urgent',
  },
];

const generateMockPipelineData = (): PipelineData[] => [
  { stage: 'Contacted', count: 45, value: 450000, fill: COLORS.pipeline[0] },
  { stage: 'Qualified', count: 32, value: 380000, fill: COLORS.pipeline[1] },
  { stage: 'Proposal', count: 18, value: 290000, fill: COLORS.pipeline[2] },
  { stage: 'Negotiation', count: 12, value: 220000, fill: COLORS.pipeline[3] },
  { stage: 'Closed Won', count: 8, value: 180000, fill: COLORS.pipeline[4] },
];

const generateMockTrendData = (): TrendData[] => {
  const months = [];
  for (let i = 11; i >= 0; i--) {
    const date = subMonths(new Date(), i);
    months.push({
      month: format(date, 'MMM'),
      revenue: 800000 + Math.random() * 400000,
      opportunities: 30 + Math.floor(Math.random() * 20),
      deals: 5 + Math.floor(Math.random() * 10),
    });
  }
  return months;
};

const generateMockPerformerData = (): PerformerData[] => [
  { name: 'John Smith', revenue: 350000, deals: 12, conversionRate: 28.5 },
  { name: 'Sarah Johnson', revenue: 290000, deals: 10, conversionRate: 25.2 },
  { name: 'Mike Chen', revenue: 245000, deals: 8, conversionRate: 22.8 },
  { name: 'Lisa Wong', revenue: 210000, deals: 7, conversionRate: 21.1 },
  { name: 'David Brown', revenue: 185000, deals: 6, conversionRate: 19.5 },
];

const generateMockProductData = () => [
  { name: 'Soundtrack Essential', value: 450000 },
  { name: 'Soundtrack Unlimited', value: 320000 },
  { name: 'Beat Breeze', value: 180000 },
  { name: 'Custom Solutions', value: 150000 },
  { name: 'Consulting Services', value: 100000 },
];

export default SalesDashboard;