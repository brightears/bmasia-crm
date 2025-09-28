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
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Avatar,
  ListItemAvatar,
  ListItemText,
  Divider,
  LinearProgress,
} from '@mui/material';
import {
  Support,
  Schedule,
  AccessTime,
  Star,
  TrendingUp,
  Assignment,
  CheckCircle,
  Warning,
  Error,
  HelpOutline,
  ThumbUp,
  Speed,
  Assessment,
  Timeline,
  CalendarToday,
  Refresh,
  PictureAsPdf,
  TableChart,
  Add,
  Edit,
  Analytics,
  Group,
  Computer,
  PhoneAndroid,
  Web,
  Email,
  Chat,
  Phone,
  HealthAndSafety,
  MonitorHeart,
  NetworkCheck,
  Storage,
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
  LineChart,
  Line,
  ComposedChart,
  Area,
  AreaChart,
} from 'recharts';
import { format, subMonths, addDays } from 'date-fns';
import html2canvas from 'html2canvas';
import jsPDF from 'jspdf';
import * as XLSX from 'xlsx';

// Import custom components
import SalesKPICard from './SalesKPICard';
import TicketStatusChart from './charts/TicketStatusChart';
import TicketPriorityChart from './charts/TicketPriorityChart';
import ResolutionTimeChart from './charts/ResolutionTimeChart';
import TicketVolumeChart from './charts/TicketVolumeChart';
import AgentPerformanceTable from './charts/AgentPerformanceTable';

interface TechSupportKPIs {
  openTickets: number;
  resolvedToday: {
    current: number;
    previous: number;
    change: number;
  };
  averageResolutionTime: {
    current: number;
    previous: number;
    change: number;
  };
  firstResponseTime: {
    current: number;
    previous: number;
    change: number;
  };
  customerSatisfaction: {
    current: number;
    previous: number;
    change: number;
  };
  escalationRate: {
    current: number;
    previous: number;
    change: number;
  };
}

interface Ticket {
  id: string;
  title: string;
  status: 'open' | 'in_progress' | 'resolved' | 'closed';
  priority: 'low' | 'medium' | 'high' | 'critical';
  category: 'technical' | 'billing' | 'account' | 'feature_request' | 'bug_report';
  customerName: string;
  assignedAgent: string;
  createdAt: string;
  resolvedAt?: string;
  firstResponseTime?: number;
  resolutionTime?: number;
  satisfaction?: number;
  channel: 'email' | 'chat' | 'phone' | 'web_form';
}

interface TicketStatusData {
  status: string;
  count: number;
  percentage: number;
  fill: string;
}

interface TicketPriorityData {
  priority: string;
  count: number;
  percentage: number;
  fill: string;
}

interface CategoryVolumeData {
  category: string;
  tickets: number;
  resolved: number;
  avgResolutionTime: number;
  fill: string;
}

interface AgentPerformance {
  id: string;
  name: string;
  avatar: string;
  ticketsAssigned: number;
  ticketsResolved: number;
  avgResolutionTime: number;
  firstResponseTime: number;
  customerSatisfaction: number;
  workload: number;
  status: 'available' | 'busy' | 'away';
}

interface SLAMetric {
  metric: string;
  target: number;
  current: number;
  compliance: number;
  status: 'excellent' | 'good' | 'warning' | 'critical';
}

interface KnowledgeBaseArticle {
  id: string;
  title: string;
  category: string;
  views: number;
  helpfulVotes: number;
  totalVotes: number;
  lastUpdated: string;
  effectiveness: number;
}

interface CustomerFeedback {
  id: string;
  ticketId: string;
  rating: number;
  comment: string;
  category: string;
  date: string;
}

interface SystemHealth {
  service: string;
  status: 'healthy' | 'warning' | 'critical';
  uptime: number;
  responseTime: number;
  lastCheck: string;
  icon: React.ReactNode;
}

// Tech Support-specific color scheme (blue/light blue)
const TECH_SUPPORT_COLORS = {
  primary: '#1976d2', // Blue
  secondary: '#42a5f5', // Light Blue
  accent: '#64b5f6', // Lighter Blue
  success: '#4caf50',
  warning: '#ff9800',
  error: '#f44336',
  info: '#2196f3',
  critical: '#d32f2f',
  high: '#ff5722',
  medium: '#ff9800',
  low: '#4caf50',
  status: {
    open: '#2196f3',
    in_progress: '#ff9800',
    resolved: '#4caf50',
    closed: '#9e9e9e',
  },
  priority: {
    critical: '#d32f2f',
    high: '#ff5722',
    medium: '#ff9800',
    low: '#4caf50',
  },
  categories: ['#1976d2', '#42a5f5', '#64b5f6', '#90caf9', '#bbdefb'],
};

const TechSupportDashboard: React.FC = () => {
  const dashboardRef = useRef<HTMLDivElement>(null);
  const [timeFilter, setTimeFilter] = useState<'today' | 'week' | 'month' | 'quarter' | 'year'>('month');
  const [loading, setLoading] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false,
    message: '',
    severity: 'success',
  });

  const [kpis, setKpis] = useState<TechSupportKPIs>({
    openTickets: 0,
    resolvedToday: { current: 0, previous: 0, change: 0 },
    averageResolutionTime: { current: 0, previous: 0, change: 0 },
    firstResponseTime: { current: 0, previous: 0, change: 0 },
    customerSatisfaction: { current: 0, previous: 0, change: 0 },
    escalationRate: { current: 0, previous: 0, change: 0 },
  });

  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [statusData, setStatusData] = useState<TicketStatusData[]>([]);
  const [priorityData, setPriorityData] = useState<TicketPriorityData[]>([]);
  const [categoryVolumeData, setCategoryVolumeData] = useState<CategoryVolumeData[]>([]);
  const [agentPerformance, setAgentPerformance] = useState<AgentPerformance[]>([]);
  const [slaMetrics, setSlaMetrics] = useState<SLAMetric[]>([]);
  const [knowledgeBaseArticles, setKnowledgeBaseArticles] = useState<KnowledgeBaseArticle[]>([]);
  const [customerFeedback, setCustomerFeedback] = useState<CustomerFeedback[]>([]);
  const [systemHealth, setSystemHealth] = useState<SystemHealth[]>([]);
  const [resolutionTrendData, setResolutionTrendData] = useState<any[]>([]);

  // Auto-refresh every 5 minutes
  useEffect(() => {
    const interval = setInterval(() => {
      refreshData();
    }, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  // Initial data load
  useEffect(() => {
    loadTechSupportData();
  }, [timeFilter]);

  const loadTechSupportData = async () => {
    setLoading(true);
    try {
      // Simulate API calls with mock data
      await new Promise(resolve => setTimeout(resolve, 800));

      setKpis(generateMockKPIs());
      setTickets(generateMockTickets());
      setStatusData(generateMockStatusData());
      setPriorityData(generateMockPriorityData());
      setCategoryVolumeData(generateMockCategoryVolumeData());
      setAgentPerformance(generateMockAgentPerformance());
      setSlaMetrics(generateMockSLAMetrics());
      setKnowledgeBaseArticles(generateMockKnowledgeBaseArticles());
      setCustomerFeedback(generateMockCustomerFeedback());
      setSystemHealth(generateMockSystemHealth());
      setResolutionTrendData(generateMockResolutionTrendData());

      setLastRefresh(new Date());
    } catch (error) {
      console.error('Error loading tech support data:', error);
    } finally {
      setLoading(false);
    }
  };

  const refreshData = useCallback(() => {
    loadTechSupportData();
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

      pdf.save(`tech-support-dashboard-${format(new Date(), 'yyyy-MM-dd')}.pdf`);
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
        ['Open Tickets', kpis.openTickets, '', ''],
        ['Resolved Today', kpis.resolvedToday.current, kpis.resolvedToday.previous, `${kpis.resolvedToday.change}%`],
        ['Avg Resolution Time (hrs)', kpis.averageResolutionTime.current, kpis.averageResolutionTime.previous, `${kpis.averageResolutionTime.change}%`],
        ['First Response Time (hrs)', kpis.firstResponseTime.current, kpis.firstResponseTime.previous, `${kpis.firstResponseTime.change}%`],
        ['Customer Satisfaction', `${kpis.customerSatisfaction.current}/5`, `${kpis.customerSatisfaction.previous}/5`, `${kpis.customerSatisfaction.change}%`],
        ['Escalation Rate', `${kpis.escalationRate.current}%`, `${kpis.escalationRate.previous}%`, `${kpis.escalationRate.change}%`],
      ];
      const kpiSheet = XLSX.utils.aoa_to_sheet(kpiData);
      XLSX.utils.book_append_sheet(workbook, kpiSheet, 'KPIs');

      // Tickets sheet
      const ticketsSheet = XLSX.utils.json_to_sheet(tickets);
      XLSX.utils.book_append_sheet(workbook, ticketsSheet, 'Tickets');

      // Agent Performance sheet
      const agentSheet = XLSX.utils.json_to_sheet(agentPerformance);
      XLSX.utils.book_append_sheet(workbook, agentSheet, 'Agent Performance');

      // SLA Metrics sheet
      const slaSheet = XLSX.utils.json_to_sheet(slaMetrics);
      XLSX.utils.book_append_sheet(workbook, slaSheet, 'SLA Metrics');

      // Knowledge Base sheet
      const kbSheet = XLSX.utils.json_to_sheet(knowledgeBaseArticles);
      XLSX.utils.book_append_sheet(workbook, kbSheet, 'Knowledge Base');

      XLSX.writeFile(workbook, `tech-support-data-${format(new Date(), 'yyyy-MM-dd')}.xlsx`);
      setSnackbar({ open: true, message: 'Excel file exported successfully!', severity: 'success' });
    } catch (error) {
      console.error('Error exporting Excel:', error);
      setSnackbar({ open: true, message: 'Failed to export Excel file', severity: 'error' });
    }
  };

  const getStatusColor = (status: Ticket['status']) => {
    switch (status) {
      case 'open':
        return 'info';
      case 'in_progress':
        return 'warning';
      case 'resolved':
        return 'success';
      case 'closed':
        return 'default';
      default:
        return 'default';
    }
  };

  const getPriorityColor = (priority: Ticket['priority']) => {
    switch (priority) {
      case 'critical':
        return 'error';
      case 'high':
        return 'warning';
      case 'medium':
        return 'info';
      case 'low':
        return 'success';
      default:
        return 'default';
    }
  };

  const getSLAStatusColor = (status: SLAMetric['status']) => {
    switch (status) {
      case 'excellent':
        return 'success';
      case 'good':
        return 'info';
      case 'warning':
        return 'warning';
      case 'critical':
        return 'error';
      default:
        return 'default';
    }
  };

  const getSystemHealthColor = (status: SystemHealth['status']) => {
    switch (status) {
      case 'healthy':
        return 'success';
      case 'warning':
        return 'warning';
      case 'critical':
        return 'error';
      default:
        return 'default';
    }
  };

  const formatTime = (hours: number) => {
    if (hours < 1) {
      return `${Math.round(hours * 60)}m`;
    }
    return `${hours.toFixed(1)}h`;
  };

  const formatNumber = (value: number) => {
    if (value >= 1000000) {
      return `${(value / 1000000).toFixed(1)}M`;
    } else if (value >= 1000) {
      return `${(value / 1000).toFixed(1)}K`;
    }
    return value.toLocaleString();
  };

  return (
    <Box ref={dashboardRef} sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" component="h1" gutterBottom sx={{ color: TECH_SUPPORT_COLORS.primary }}>
            Tech Support Dashboard
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
          <CircularProgress sx={{ color: TECH_SUPPORT_COLORS.primary }} />
        </Box>
      )}

      {/* KPI Cards */}
      <Box sx={{ display: 'flex', gap: 3, mb: 3, flexWrap: 'wrap' }}>
        <Box sx={{ flex: '1 1 250px', minWidth: 200 }}>
          <SalesKPICard
            title="Open Tickets"
            value={kpis.openTickets}
            icon={<Assignment />}
            color={TECH_SUPPORT_COLORS.primary}
            loading={loading}
            tooltip="Number of currently open support tickets"
          />
        </Box>

        <Box sx={{ flex: '1 1 250px', minWidth: 200 }}>
          <SalesKPICard
            title="Resolved Today"
            value={kpis.resolvedToday.current}
            previousValue={kpis.resolvedToday.previous}
            icon={<CheckCircle />}
            color={TECH_SUPPORT_COLORS.success}
            loading={loading}
            tooltip="Number of tickets resolved today"
            trendValue={kpis.resolvedToday.change}
          />
        </Box>

        <Box sx={{ flex: '1 1 250px', minWidth: 200 }}>
          <SalesKPICard
            title="Avg Resolution Time"
            value={`${kpis.averageResolutionTime.current}h`}
            previousValue={kpis.averageResolutionTime.previous}
            icon={<AccessTime />}
            color={TECH_SUPPORT_COLORS.secondary}
            loading={loading}
            tooltip="Average time to resolve tickets"
            trendValue={kpis.averageResolutionTime.change}
          />
        </Box>

        <Box sx={{ flex: '1 1 250px', minWidth: 200 }}>
          <SalesKPICard
            title="First Response Time"
            value={`${kpis.firstResponseTime.current}h`}
            previousValue={kpis.firstResponseTime.previous}
            icon={<Schedule />}
            color={TECH_SUPPORT_COLORS.accent}
            loading={loading}
            tooltip="Average time to first response"
            trendValue={kpis.firstResponseTime.change}
          />
        </Box>

        <Box sx={{ flex: '1 1 250px', minWidth: 200 }}>
          <SalesKPICard
            title="Customer Satisfaction"
            value={`${kpis.customerSatisfaction.current}/5`}
            previousValue={kpis.customerSatisfaction.previous}
            icon={<Star />}
            color={TECH_SUPPORT_COLORS.warning}
            loading={loading}
            tooltip="Average customer satisfaction score"
            trendValue={kpis.customerSatisfaction.change}
          />
        </Box>

        <Box sx={{ flex: '1 1 250px', minWidth: 200 }}>
          <SalesKPICard
            title="Escalation Rate"
            value={`${kpis.escalationRate.current}%`}
            previousValue={kpis.escalationRate.previous}
            icon={<TrendingUp />}
            color={TECH_SUPPORT_COLORS.error}
            format="percentage"
            loading={loading}
            tooltip="Percentage of tickets that get escalated"
            trendValue={kpis.escalationRate.change}
          />
        </Box>
      </Box>

      {/* Charts Row 1 - Ticket Status & Priority Distribution */}
      <Box sx={{ display: 'flex', gap: 3, mb: 3, flexWrap: 'wrap' }}>
        <Box sx={{ flex: '1 1 400px', minWidth: 350 }}>
          <TicketStatusChart data={statusData} loading={loading} />
        </Box>

        <Box sx={{ flex: '1 1 400px', minWidth: 350 }}>
          <TicketPriorityChart data={priorityData} loading={loading} />
        </Box>
      </Box>

      {/* Charts Row 2 - Resolution Time Trend & Category Volume */}
      <Box sx={{ display: 'flex', gap: 3, mb: 3, flexWrap: 'wrap' }}>
        <Box sx={{ flex: '1 1 500px', minWidth: 450 }}>
          <ResolutionTimeChart data={resolutionTrendData} loading={loading} />
        </Box>

        <Box sx={{ flex: '1 1 400px', minWidth: 350 }}>
          <TicketVolumeChart data={categoryVolumeData} loading={loading} />
        </Box>
      </Box>

      {/* Recent Tickets List */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h6" gutterBottom sx={{ color: TECH_SUPPORT_COLORS.primary }}>
          Recent Tickets
        </Typography>
        <Card>
          <CardContent>
            <TableContainer component={Paper} elevation={0}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>ID</TableCell>
                    <TableCell>Title</TableCell>
                    <TableCell>Customer</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Priority</TableCell>
                    <TableCell>Agent</TableCell>
                    <TableCell>Created</TableCell>
                    <TableCell>Channel</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {tickets.slice(0, 10).map((ticket) => (
                    <TableRow key={ticket.id}>
                      <TableCell>#{ticket.id.slice(-4)}</TableCell>
                      <TableCell>
                        <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                          {ticket.title}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {ticket.category.replace('_', ' ').toUpperCase()}
                        </Typography>
                      </TableCell>
                      <TableCell>{ticket.customerName}</TableCell>
                      <TableCell>
                        <Chip
                          label={ticket.status.replace('_', ' ').toUpperCase()}
                          color={getStatusColor(ticket.status) as any}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={ticket.priority.toUpperCase()}
                          color={getPriorityColor(ticket.priority) as any}
                          size="small"
                          variant="outlined"
                        />
                      </TableCell>
                      <TableCell>{ticket.assignedAgent}</TableCell>
                      <TableCell>{format(new Date(ticket.createdAt), 'MMM dd, HH:mm')}</TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center' }}>
                          {ticket.channel === 'email' && <Email fontSize="small" />}
                          {ticket.channel === 'chat' && <Chat fontSize="small" />}
                          {ticket.channel === 'phone' && <Phone fontSize="small" />}
                          {ticket.channel === 'web_form' && <Web fontSize="small" />}
                          <Typography variant="caption" sx={{ ml: 0.5 }}>
                            {ticket.channel.replace('_', ' ').toUpperCase()}
                          </Typography>
                        </Box>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </CardContent>
        </Card>
      </Box>

      {/* SLA Compliance & Agent Performance */}
      <Box sx={{ display: 'flex', gap: 3, mb: 3, flexWrap: 'wrap' }}>
        {/* SLA Compliance Tracking */}
        <Box sx={{ flex: '1 1 400px', minWidth: 350 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ color: TECH_SUPPORT_COLORS.primary }}>
                SLA Compliance Tracking
              </Typography>
              {slaMetrics.map((sla, index) => (
                <Box key={index} sx={{ mb: 2 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                    <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                      {sla.metric}
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography variant="body2" color="text.secondary">
                        {sla.current} / {sla.target}
                      </Typography>
                      <Chip
                        label={`${sla.compliance}%`}
                        color={getSLAStatusColor(sla.status) as any}
                        size="small"
                      />
                    </Box>
                  </Box>
                  <LinearProgress
                    variant="determinate"
                    value={sla.compliance}
                    sx={{
                      height: 8,
                      borderRadius: 4,
                      backgroundColor: 'grey.200',
                      '& .MuiLinearProgress-bar': {
                        backgroundColor: sla.status === 'excellent' ? TECH_SUPPORT_COLORS.success :
                          sla.status === 'good' ? TECH_SUPPORT_COLORS.info :
                          sla.status === 'warning' ? TECH_SUPPORT_COLORS.warning :
                          TECH_SUPPORT_COLORS.error,
                      },
                    }}
                  />
                </Box>
              ))}
            </CardContent>
          </Card>
        </Box>

        {/* Agent Performance */}
        <Box sx={{ flex: '1 1 500px', minWidth: 450 }}>
          <AgentPerformanceTable data={agentPerformance} loading={loading} />
        </Box>
      </Box>

      {/* Knowledge Base & Customer Feedback */}
      <Box sx={{ display: 'flex', gap: 3, mb: 3, flexWrap: 'wrap' }}>
        {/* Knowledge Base Effectiveness */}
        <Box sx={{ flex: '1 1 400px', minWidth: 350 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ color: TECH_SUPPORT_COLORS.primary }}>
                Knowledge Base Article Effectiveness
              </Typography>
              <TableContainer component={Paper} elevation={0}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Article</TableCell>
                      <TableCell align="right">Views</TableCell>
                      <TableCell align="right">Helpful %</TableCell>
                      <TableCell align="right">Effectiveness</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {knowledgeBaseArticles.slice(0, 5).map((article) => (
                      <TableRow key={article.id}>
                        <TableCell>
                          <Box>
                            <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                              {article.title}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {article.category}
                            </Typography>
                          </Box>
                        </TableCell>
                        <TableCell align="right">{formatNumber(article.views)}</TableCell>
                        <TableCell align="right">
                          {((article.helpfulVotes / article.totalVotes) * 100).toFixed(1)}%
                        </TableCell>
                        <TableCell align="right">
                          <Chip
                            label={`${article.effectiveness}%`}
                            color={article.effectiveness >= 80 ? 'success' : article.effectiveness >= 60 ? 'warning' : 'error'}
                            size="small"
                          />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </Card>
        </Box>

        {/* Customer Feedback Summary */}
        <Box sx={{ flex: '1 1 400px', minWidth: 350 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ color: TECH_SUPPORT_COLORS.primary }}>
                Customer Feedback Summary
              </Typography>
              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  Average Rating
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Typography variant="h4" sx={{ fontWeight: 'bold', color: TECH_SUPPORT_COLORS.warning }}>
                    {(customerFeedback.reduce((sum, f) => sum + f.rating, 0) / customerFeedback.length).toFixed(1)}
                  </Typography>
                  <Box sx={{ display: 'flex' }}>
                    {Array.from({ length: 5 }, (_, i) => (
                      <Star
                        key={i}
                        sx={{
                          color: i < Math.round(customerFeedback.reduce((sum, f) => sum + f.rating, 0) / customerFeedback.length)
                            ? TECH_SUPPORT_COLORS.warning
                            : 'lightgray',
                          fontSize: 20,
                        }}
                      />
                    ))}
                  </Box>
                </Box>
              </Box>
              <Divider sx={{ my: 2 }} />
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Recent Feedback
              </Typography>
              {customerFeedback.slice(0, 3).map((feedback) => (
                <Box key={feedback.id} sx={{ mb: 2, p: 1, bgcolor: 'grey.50', borderRadius: 1 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                        Ticket #{feedback.ticketId.slice(-4)}
                      </Typography>
                      <Box sx={{ display: 'flex' }}>
                        {Array.from({ length: feedback.rating }, (_, i) => (
                          <Star key={i} sx={{ color: TECH_SUPPORT_COLORS.warning, fontSize: 16 }} />
                        ))}
                      </Box>
                    </Box>
                    <Typography variant="caption" color="text.secondary">
                      {format(new Date(feedback.date), 'MMM dd')}
                    </Typography>
                  </Box>
                  <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.8rem' }}>
                    {feedback.comment}
                  </Typography>
                </Box>
              ))}
            </CardContent>
          </Card>
        </Box>
      </Box>

      {/* System Health Indicators */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h6" gutterBottom sx={{ color: TECH_SUPPORT_COLORS.primary }}>
          System Health Indicators
        </Typography>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(4, 1fr)' }, gap: 2 }}>
          {systemHealth.map((system, index) => (
            <Box key={index}>
              <Card>
                <CardContent sx={{ textAlign: 'center' }}>
                  <Box sx={{ display: 'flex', justifyContent: 'center', mb: 1 }}>
                    <Avatar
                      sx={{
                        bgcolor: getSystemHealthColor(system.status) === 'success' ? TECH_SUPPORT_COLORS.success :
                          getSystemHealthColor(system.status) === 'warning' ? TECH_SUPPORT_COLORS.warning :
                          TECH_SUPPORT_COLORS.error,
                        width: 40,
                        height: 40,
                      }}
                    >
                      {system.icon}
                    </Avatar>
                  </Box>
                  <Typography variant="h6" sx={{ fontWeight: 'bold', mb: 0.5 }}>
                    {system.service}
                  </Typography>
                  <Chip
                    label={system.status.toUpperCase()}
                    color={getSystemHealthColor(system.status) as any}
                    size="small"
                    sx={{ mb: 1 }}
                  />
                  <Typography variant="body2" color="text.secondary">
                    Uptime: {system.uptime.toFixed(2)}%
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Response: {system.responseTime}ms
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Last check: {format(new Date(system.lastCheck), 'HH:mm')}
                  </Typography>
                </CardContent>
              </Card>
            </Box>
          ))}
        </Box>
      </Box>

      {/* Quick Actions */}
      <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
        <Box sx={{ flex: '1 1 300px', minWidth: 250 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ color: TECH_SUPPORT_COLORS.primary }}>
                Quick Actions
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <Button
                  variant="contained"
                  startIcon={<Add />}
                  fullWidth
                  sx={{
                    bgcolor: TECH_SUPPORT_COLORS.primary,
                    '&:hover': { bgcolor: TECH_SUPPORT_COLORS.secondary }
                  }}
                >
                  Create New Ticket
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<Assignment />}
                  fullWidth
                  sx={{
                    borderColor: TECH_SUPPORT_COLORS.primary,
                    color: TECH_SUPPORT_COLORS.primary,
                    '&:hover': { borderColor: TECH_SUPPORT_COLORS.secondary, color: TECH_SUPPORT_COLORS.secondary }
                  }}
                >
                  View All Tickets
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<HelpOutline />}
                  fullWidth
                  sx={{
                    borderColor: TECH_SUPPORT_COLORS.primary,
                    color: TECH_SUPPORT_COLORS.primary,
                    '&:hover': { borderColor: TECH_SUPPORT_COLORS.secondary, color: TECH_SUPPORT_COLORS.secondary }
                  }}
                >
                  Knowledge Base
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<Analytics />}
                  fullWidth
                  sx={{
                    borderColor: TECH_SUPPORT_COLORS.primary,
                    color: TECH_SUPPORT_COLORS.primary,
                    '&:hover': { borderColor: TECH_SUPPORT_COLORS.secondary, color: TECH_SUPPORT_COLORS.secondary }
                  }}
                >
                  Generate Report
                </Button>
              </Box>
            </CardContent>
          </Card>
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
const generateMockKPIs = (): TechSupportKPIs => ({
  openTickets: 42,
  resolvedToday: {
    current: 28,
    previous: 24,
    change: 16.7,
  },
  averageResolutionTime: {
    current: 4.2,
    previous: 5.1,
    change: -17.6,
  },
  firstResponseTime: {
    current: 0.8,
    previous: 1.2,
    change: -33.3,
  },
  customerSatisfaction: {
    current: 4.3,
    previous: 4.1,
    change: 4.9,
  },
  escalationRate: {
    current: 8.5,
    previous: 12.3,
    change: -30.9,
  },
});

const generateMockTickets = (): Ticket[] => [
  {
    id: 'TSK-001',
    title: 'Login issues with mobile app',
    status: 'open',
    priority: 'high',
    category: 'technical',
    customerName: 'John Smith',
    assignedAgent: 'Sarah Chen',
    createdAt: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    channel: 'chat',
  },
  {
    id: 'TSK-002',
    title: 'Payment processing error',
    status: 'in_progress',
    priority: 'critical',
    category: 'billing',
    customerName: 'Emily Johnson',
    assignedAgent: 'Mike Rodriguez',
    createdAt: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
    channel: 'phone',
    firstResponseTime: 0.5,
  },
  {
    id: 'TSK-003',
    title: 'Account verification needed',
    status: 'resolved',
    priority: 'medium',
    category: 'account',
    customerName: 'David Brown',
    assignedAgent: 'Lisa Wang',
    createdAt: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
    resolvedAt: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString(),
    channel: 'email',
    firstResponseTime: 1.2,
    resolutionTime: 5.0,
    satisfaction: 5,
  },
  {
    id: 'TSK-004',
    title: 'Feature request: Dark mode',
    status: 'open',
    priority: 'low',
    category: 'feature_request',
    customerName: 'Jennifer Lee',
    assignedAgent: 'Alex Thompson',
    createdAt: new Date(Date.now() - 8 * 60 * 60 * 1000).toISOString(),
    channel: 'web_form',
  },
  {
    id: 'TSK-005',
    title: 'Bug: Dashboard not loading',
    status: 'in_progress',
    priority: 'high',
    category: 'bug_report',
    customerName: 'Robert Wilson',
    assignedAgent: 'Sarah Chen',
    createdAt: new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString(),
    channel: 'email',
    firstResponseTime: 0.3,
  },
  {
    id: 'TSK-006',
    title: 'Invoice download issue',
    status: 'closed',
    priority: 'medium',
    category: 'billing',
    customerName: 'Maria Garcia',
    assignedAgent: 'Mike Rodriguez',
    createdAt: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
    resolvedAt: new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString(),
    channel: 'chat',
    firstResponseTime: 0.7,
    resolutionTime: 12.0,
    satisfaction: 4,
  },
  {
    id: 'TSK-007',
    title: 'Password reset not working',
    status: 'open',
    priority: 'medium',
    category: 'technical',
    customerName: 'James Miller',
    assignedAgent: 'Lisa Wang',
    createdAt: new Date(Date.now() - 16 * 60 * 60 * 1000).toISOString(),
    channel: 'web_form',
  },
  {
    id: 'TSK-008',
    title: 'API rate limit exceeded',
    status: 'resolved',
    priority: 'high',
    category: 'technical',
    customerName: 'TechCorp Inc.',
    assignedAgent: 'Alex Thompson',
    createdAt: new Date(Date.now() - 20 * 60 * 60 * 1000).toISOString(),
    resolvedAt: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
    channel: 'email',
    firstResponseTime: 0.2,
    resolutionTime: 16.0,
    satisfaction: 4,
  },
  {
    id: 'TSK-009',
    title: 'Data export malformed',
    status: 'in_progress',
    priority: 'medium',
    category: 'bug_report',
    customerName: 'Analytics Ltd.',
    assignedAgent: 'Sarah Chen',
    createdAt: new Date(Date.now() - 28 * 60 * 60 * 1000).toISOString(),
    channel: 'phone',
    firstResponseTime: 1.5,
  },
  {
    id: 'TSK-010',
    title: 'Account upgrade assistance',
    status: 'open',
    priority: 'low',
    category: 'account',
    customerName: 'Small Business Co.',
    assignedAgent: 'Mike Rodriguez',
    createdAt: new Date(Date.now() - 32 * 60 * 60 * 1000).toISOString(),
    channel: 'chat',
  },
];

const generateMockStatusData = (): TicketStatusData[] => [
  { status: 'Open', count: 42, percentage: 35, fill: TECH_SUPPORT_COLORS.status.open },
  { status: 'In Progress', count: 28, percentage: 23, fill: TECH_SUPPORT_COLORS.status.in_progress },
  { status: 'Resolved', count: 38, percentage: 32, fill: TECH_SUPPORT_COLORS.status.resolved },
  { status: 'Closed', count: 12, percentage: 10, fill: TECH_SUPPORT_COLORS.status.closed },
];

const generateMockPriorityData = (): TicketPriorityData[] => [
  { priority: 'Critical', count: 8, percentage: 7, fill: TECH_SUPPORT_COLORS.priority.critical },
  { priority: 'High', count: 24, percentage: 20, fill: TECH_SUPPORT_COLORS.priority.high },
  { priority: 'Medium', count: 58, percentage: 48, fill: TECH_SUPPORT_COLORS.priority.medium },
  { priority: 'Low', count: 30, percentage: 25, fill: TECH_SUPPORT_COLORS.priority.low },
];

const generateMockCategoryVolumeData = (): CategoryVolumeData[] => [
  { category: 'Technical', tickets: 45, resolved: 32, avgResolutionTime: 4.2, fill: TECH_SUPPORT_COLORS.categories[0] },
  { category: 'Billing', tickets: 28, resolved: 24, avgResolutionTime: 2.8, fill: TECH_SUPPORT_COLORS.categories[1] },
  { category: 'Account', tickets: 22, resolved: 18, avgResolutionTime: 3.1, fill: TECH_SUPPORT_COLORS.categories[2] },
  { category: 'Feature Request', tickets: 15, resolved: 8, avgResolutionTime: 12.5, fill: TECH_SUPPORT_COLORS.categories[3] },
  { category: 'Bug Report', tickets: 10, resolved: 7, avgResolutionTime: 6.8, fill: TECH_SUPPORT_COLORS.categories[4] },
];

const generateMockAgentPerformance = (): AgentPerformance[] => [
  {
    id: '1',
    name: 'Sarah Chen',
    avatar: 'SC',
    ticketsAssigned: 25,
    ticketsResolved: 22,
    avgResolutionTime: 3.8,
    firstResponseTime: 0.5,
    customerSatisfaction: 4.6,
    workload: 85,
    status: 'available',
  },
  {
    id: '2',
    name: 'Mike Rodriguez',
    avatar: 'MR',
    ticketsAssigned: 18,
    ticketsResolved: 16,
    avgResolutionTime: 4.2,
    firstResponseTime: 0.8,
    customerSatisfaction: 4.3,
    workload: 70,
    status: 'busy',
  },
  {
    id: '3',
    name: 'Lisa Wang',
    avatar: 'LW',
    ticketsAssigned: 22,
    ticketsResolved: 20,
    avgResolutionTime: 3.5,
    firstResponseTime: 0.3,
    customerSatisfaction: 4.8,
    workload: 90,
    status: 'available',
  },
  {
    id: '4',
    name: 'Alex Thompson',
    avatar: 'AT',
    ticketsAssigned: 15,
    ticketsResolved: 12,
    avgResolutionTime: 5.1,
    firstResponseTime: 1.2,
    customerSatisfaction: 4.1,
    workload: 60,
    status: 'away',
  },
];

const generateMockSLAMetrics = (): SLAMetric[] => [
  { metric: 'First Response Time', target: 1, current: 0.8, compliance: 96, status: 'excellent' },
  { metric: 'Resolution Time', target: 24, current: 4.2, compliance: 92, status: 'excellent' },
  { metric: 'Customer Satisfaction', target: 4, current: 4.3, compliance: 88, status: 'good' },
  { metric: 'Escalation Rate', target: 10, current: 8.5, compliance: 85, status: 'good' },
];

const generateMockKnowledgeBaseArticles = (): KnowledgeBaseArticle[] => [
  {
    id: '1',
    title: 'How to Reset Your Password',
    category: 'Account Management',
    views: 1240,
    helpfulVotes: 156,
    totalVotes: 180,
    lastUpdated: '2024-08-15',
    effectiveness: 87,
  },
  {
    id: '2',
    title: 'Payment Methods Setup',
    category: 'Billing',
    views: 980,
    helpfulVotes: 142,
    totalVotes: 165,
    lastUpdated: '2024-08-10',
    effectiveness: 86,
  },
  {
    id: '3',
    title: 'Mobile App Troubleshooting',
    category: 'Technical Support',
    views: 756,
    helpfulVotes: 89,
    totalVotes: 112,
    lastUpdated: '2024-08-20',
    effectiveness: 79,
  },
  {
    id: '4',
    title: 'API Integration Guide',
    category: 'Technical Support',
    views: 432,
    helpfulVotes: 67,
    totalVotes: 78,
    lastUpdated: '2024-08-05',
    effectiveness: 86,
  },
  {
    id: '5',
    title: 'Data Export Instructions',
    category: 'Features',
    views: 324,
    helpfulVotes: 45,
    totalVotes: 62,
    lastUpdated: '2024-08-12',
    effectiveness: 73,
  },
];

const generateMockCustomerFeedback = (): CustomerFeedback[] => [
  {
    id: '1',
    ticketId: 'TSK-003',
    rating: 5,
    comment: 'Sarah was incredibly helpful and resolved my issue quickly. Excellent service!',
    category: 'Account',
    date: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: '2',
    ticketId: 'TSK-006',
    rating: 4,
    comment: 'Good support, though it took a bit longer than expected to get the invoice fixed.',
    category: 'Billing',
    date: new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: '3',
    ticketId: 'TSK-008',
    rating: 4,
    comment: 'Alex understood the technical issue immediately and provided a clear solution.',
    category: 'Technical',
    date: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
  },
];

const generateMockSystemHealth = (): SystemHealth[] => [
  {
    service: 'API Gateway',
    status: 'healthy',
    uptime: 99.98,
    responseTime: 45,
    lastCheck: new Date().toISOString(),
    icon: <NetworkCheck />,
  },
  {
    service: 'Database',
    status: 'healthy',
    uptime: 99.95,
    responseTime: 23,
    lastCheck: new Date().toISOString(),
    icon: <Storage />,
  },
  {
    service: 'Web Application',
    status: 'warning',
    uptime: 98.87,
    responseTime: 156,
    lastCheck: new Date().toISOString(),
    icon: <Web />,
  },
  {
    service: 'Email Service',
    status: 'healthy',
    uptime: 99.99,
    responseTime: 78,
    lastCheck: new Date().toISOString(),
    icon: <Email />,
  },
];

const generateMockResolutionTrendData = () => {
  const months = [];
  for (let i = 11; i >= 0; i--) {
    const date = subMonths(new Date(), i);
    months.push({
      month: format(date, 'MMM'),
      avgResolutionTime: 3 + Math.random() * 3,
      firstResponseTime: 0.5 + Math.random() * 1.5,
      ticketsResolved: 80 + Math.random() * 40,
      customerSatisfaction: 4 + Math.random() * 1,
    });
  }
  return months;
};

export default TechSupportDashboard;