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
} from '@mui/material';
import {
  Campaign,
  TrendingUp,
  Visibility,
  TouchApp,
  Email,
  Share,
  AttachMoney,
  Assessment,
  Timeline,
  CalendarToday,
  Refresh,
  PictureAsPdf,
  TableChart,
  Add,
  Edit,
  Analytics,
  Science,
  MonetizationOn,
  Group,
  Web,
  Computer,
  PhoneAndroid,
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
  FunnelChart,
  Funnel,
  LabelList,
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
import CampaignPerformanceChart from './charts/CampaignPerformanceChart';
import ChannelDistributionChart from './charts/ChannelDistributionChart';
import ConversionFunnelChart from './charts/ConversionFunnelChart';
import CampaignCalendarView from './charts/CampaignCalendarView';

interface MarketingKPIs {
  activeCampaigns: number;
  totalReach: {
    current: number;
    previous: number;
    change: number;
  };
  conversionRate: {
    current: number;
    previous: number;
    change: number;
  };
  roi: {
    current: number;
    previous: number;
    change: number;
  };
  emailOpenRate: {
    current: number;
    previous: number;
    change: number;
  };
  clickThroughRate: {
    current: number;
    previous: number;
    change: number;
  };
}

interface Campaign {
  id: string;
  name: string;
  status: 'active' | 'scheduled' | 'completed' | 'paused';
  channel: 'email' | 'social' | 'web' | 'mobile' | 'display';
  budget: number;
  spent: number;
  impressions: number;
  clicks: number;
  conversions: number;
  revenue: number;
  startDate: string;
  endDate: string;
  ctr: number;
  cpc: number;
  roas: number;
}

interface ChannelData {
  channel: string;
  impressions: number;
  clicks: number;
  conversions: number;
  spend: number;
  fill: string;
}

interface ConversionFunnelData {
  stage: string;
  visitors: number;
  percentage: number;
  fill: string;
}

interface ABTestResult {
  id: string;
  campaignName: string;
  variant: 'A' | 'B';
  conversions: number;
  conversionRate: number;
  confidence: number;
  winner: boolean;
}

interface ContentPerformance {
  id: string;
  title: string;
  type: 'blog' | 'video' | 'infographic' | 'ebook' | 'webinar';
  views: number;
  shares: number;
  leads: number;
  engagementRate: number;
  publishDate: string;
}

interface SocialEngagement {
  platform: string;
  followers: number;
  engagement: number;
  posts: number;
  reach: number;
  icon: React.ReactNode;
}

// Marketing-specific color scheme (orange/deep orange)
const MARKETING_COLORS = {
  primary: '#ff6f00', // Deep Orange
  secondary: '#ff8f00', // Orange
  accent: '#ffb74d', // Light Orange
  success: '#4caf50',
  warning: '#ff9800',
  error: '#f44336',
  info: '#2196f3',
  channels: ['#ff6f00', '#ff8f00', '#ffb74d', '#ffcc80', '#ffe0b2'],
  funnel: ['#ff6f00', '#ff8f00', '#ffb74d', '#ffcc80', '#ffe0b2'],
  social: {
    facebook: '#1877f2',
    instagram: '#e4405f',
    twitter: '#1da1f2',
    linkedin: '#0077b5',
    youtube: '#ff0000',
  },
};

const MarketingDashboard: React.FC = () => {
  const dashboardRef = useRef<HTMLDivElement>(null);
  const [timeFilter, setTimeFilter] = useState<'today' | 'week' | 'month' | 'quarter' | 'year'>('month');
  const [loading, setLoading] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false,
    message: '',
    severity: 'success',
  });

  const [kpis, setKpis] = useState<MarketingKPIs>({
    activeCampaigns: 0,
    totalReach: { current: 0, previous: 0, change: 0 },
    conversionRate: { current: 0, previous: 0, change: 0 },
    roi: { current: 0, previous: 0, change: 0 },
    emailOpenRate: { current: 0, previous: 0, change: 0 },
    clickThroughRate: { current: 0, previous: 0, change: 0 },
  });

  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [channelData, setChannelData] = useState<ChannelData[]>([]);
  const [funnelData, setFunnelData] = useState<ConversionFunnelData[]>([]);
  const [abTestResults, setAbTestResults] = useState<ABTestResult[]>([]);
  const [topContent, setTopContent] = useState<ContentPerformance[]>([]);
  const [socialEngagement, setSocialEngagement] = useState<SocialEngagement[]>([]);
  const [campaignPerformanceData, setCampaignPerformanceData] = useState<any[]>([]);
  const [budgetData, setBudgetData] = useState<any[]>([]);
  const [leadGenData, setLeadGenData] = useState<any[]>([]);

  // Auto-refresh every 5 minutes
  useEffect(() => {
    const interval = setInterval(() => {
      refreshData();
    }, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  // Initial data load
  useEffect(() => {
    loadMarketingData();
  }, [timeFilter]);

  const loadMarketingData = async () => {
    setLoading(true);
    try {
      // Simulate API calls with mock data
      await new Promise(resolve => setTimeout(resolve, 800));

      setKpis(generateMockKPIs());
      setCampaigns(generateMockCampaigns());
      setChannelData(generateMockChannelData());
      setFunnelData(generateMockFunnelData());
      setAbTestResults(generateMockABTestResults());
      setTopContent(generateMockContentPerformance());
      setSocialEngagement(generateMockSocialEngagement());
      setCampaignPerformanceData(generateMockCampaignPerformanceData());
      setBudgetData(generateMockBudgetData());
      setLeadGenData(generateMockLeadGenData());

      setLastRefresh(new Date());
    } catch (error) {
      console.error('Error loading marketing data:', error);
    } finally {
      setLoading(false);
    }
  };

  const refreshData = useCallback(() => {
    loadMarketingData();
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

      pdf.save(`marketing-dashboard-${format(new Date(), 'yyyy-MM-dd')}.pdf`);
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
        ['Active Campaigns', kpis.activeCampaigns, '', ''],
        ['Total Reach', kpis.totalReach.current, kpis.totalReach.previous, `${kpis.totalReach.change}%`],
        ['Conversion Rate', `${kpis.conversionRate.current}%`, `${kpis.conversionRate.previous}%`, `${kpis.conversionRate.change}%`],
        ['ROI', `${kpis.roi.current}%`, `${kpis.roi.previous}%`, `${kpis.roi.change}%`],
        ['Email Open Rate', `${kpis.emailOpenRate.current}%`, `${kpis.emailOpenRate.previous}%`, `${kpis.emailOpenRate.change}%`],
        ['Click-Through Rate', `${kpis.clickThroughRate.current}%`, `${kpis.clickThroughRate.previous}%`, `${kpis.clickThroughRate.change}%`],
      ];
      const kpiSheet = XLSX.utils.aoa_to_sheet(kpiData);
      XLSX.utils.book_append_sheet(workbook, kpiSheet, 'KPIs');

      // Campaigns sheet
      const campaignsSheet = XLSX.utils.json_to_sheet(campaigns);
      XLSX.utils.book_append_sheet(workbook, campaignsSheet, 'Campaigns');

      // Channel Performance sheet
      const channelSheet = XLSX.utils.json_to_sheet(channelData);
      XLSX.utils.book_append_sheet(workbook, channelSheet, 'Channel Performance');

      // A/B Test Results sheet
      const abTestSheet = XLSX.utils.json_to_sheet(abTestResults);
      XLSX.utils.book_append_sheet(workbook, abTestSheet, 'A/B Test Results');

      // Content Performance sheet
      const contentSheet = XLSX.utils.json_to_sheet(topContent);
      XLSX.utils.book_append_sheet(workbook, contentSheet, 'Content Performance');

      XLSX.writeFile(workbook, `marketing-data-${format(new Date(), 'yyyy-MM-dd')}.xlsx`);
      setSnackbar({ open: true, message: 'Excel file exported successfully!', severity: 'success' });
    } catch (error) {
      console.error('Error exporting Excel:', error);
      setSnackbar({ open: true, message: 'Failed to export Excel file', severity: 'error' });
    }
  };

  const getStatusColor = (status: Campaign['status']) => {
    switch (status) {
      case 'active':
        return 'success';
      case 'scheduled':
        return 'info';
      case 'completed':
        return 'default';
      case 'paused':
        return 'warning';
      default:
        return 'default';
    }
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
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
          <Typography variant="h4" component="h1" gutterBottom sx={{ color: MARKETING_COLORS.primary }}>
            Marketing Dashboard
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
          <CircularProgress sx={{ color: MARKETING_COLORS.primary }} />
        </Box>
      )}

      {/* KPI Cards */}
      <Box sx={{ display: 'flex', gap: 3, mb: 3, flexWrap: 'wrap' }}>
        <Box sx={{ flex: '1 1 250px', minWidth: 200 }}>
          <SalesKPICard
            title="Active Campaigns"
            value={kpis.activeCampaigns}
            icon={<Campaign />}
            color={MARKETING_COLORS.primary}
            loading={loading}
            tooltip="Number of currently active marketing campaigns"
          />
        </Box>

        <Box sx={{ flex: '1 1 250px', minWidth: 200 }}>
          <SalesKPICard
            title="Total Reach"
            value={kpis.totalReach.current}
            previousValue={kpis.totalReach.previous}
            icon={<Visibility />}
            color={MARKETING_COLORS.secondary}
            loading={loading}
            tooltip="Total number of people reached across all campaigns"
            trendValue={kpis.totalReach.change}
          />
        </Box>

        <Box sx={{ flex: '1 1 250px', minWidth: 200 }}>
          <SalesKPICard
            title="Conversion Rate"
            value={kpis.conversionRate.current}
            previousValue={kpis.conversionRate.previous}
            icon={<Assessment />}
            color={MARKETING_COLORS.accent}
            format="percentage"
            loading={loading}
            tooltip="Percentage of visitors who convert to customers"
            trendValue={kpis.conversionRate.change}
          />
        </Box>

        <Box sx={{ flex: '1 1 250px', minWidth: 200 }}>
          <SalesKPICard
            title="ROI"
            value={kpis.roi.current}
            previousValue={kpis.roi.previous}
            icon={<MonetizationOn />}
            color={MARKETING_COLORS.success}
            format="percentage"
            loading={loading}
            tooltip="Return on Investment for marketing spend"
            trendValue={kpis.roi.change}
          />
        </Box>

        <Box sx={{ flex: '1 1 250px', minWidth: 200 }}>
          <SalesKPICard
            title="Email Open Rate"
            value={kpis.emailOpenRate.current}
            previousValue={kpis.emailOpenRate.previous}
            icon={<Email />}
            color={MARKETING_COLORS.info}
            format="percentage"
            loading={loading}
            tooltip="Percentage of email recipients who open emails"
            trendValue={kpis.emailOpenRate.change}
          />
        </Box>

        <Box sx={{ flex: '1 1 250px', minWidth: 200 }}>
          <SalesKPICard
            title="Click-Through Rate"
            value={kpis.clickThroughRate.current}
            previousValue={kpis.clickThroughRate.previous}
            icon={<TouchApp />}
            color={MARKETING_COLORS.warning}
            format="percentage"
            loading={loading}
            tooltip="Percentage of people who click on campaign links"
            trendValue={kpis.clickThroughRate.change}
          />
        </Box>
      </Box>

      {/* Charts Row 1 - Campaign Performance & Channel Distribution */}
      <Box sx={{ display: 'flex', gap: 3, mb: 3, flexWrap: 'wrap' }}>
        <Box sx={{ flex: '1 1 500px', minWidth: 450 }}>
          <CampaignPerformanceChart data={campaignPerformanceData} loading={loading} />
        </Box>

        <Box sx={{ flex: '1 1 400px', minWidth: 350 }}>
          <ChannelDistributionChart data={channelData} loading={loading} />
        </Box>
      </Box>

      {/* Charts Row 2 - Conversion Funnel & Budget vs Spend */}
      <Box sx={{ display: 'flex', gap: 3, mb: 3, flexWrap: 'wrap' }}>
        <Box sx={{ flex: '1 1 400px', minWidth: 350 }}>
          <ConversionFunnelChart data={funnelData} loading={loading} />
        </Box>

        <Box sx={{ flex: '1 1 400px', minWidth: 350 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ color: MARKETING_COLORS.primary }}>
                Budget vs Spend Tracking
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <ComposedChart data={budgetData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="campaign" tick={{ fontSize: 11 }} angle={-45} textAnchor="end" height={80} />
                  <YAxis tickFormatter={(value) => `$${(value / 1000)}K`} />
                  <RechartsTooltip formatter={(value) => `$${(value as number).toLocaleString()}`} />
                  <Bar dataKey="budget" fill={MARKETING_COLORS.accent} name="Budget" />
                  <Bar dataKey="spent" fill={MARKETING_COLORS.primary} name="Spent" />
                  <Line type="monotone" dataKey="efficiency" stroke={MARKETING_COLORS.success} name="Efficiency %" />
                </ComposedChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Box>
      </Box>

      {/* Campaign Status Cards */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h6" gutterBottom sx={{ color: MARKETING_COLORS.primary }}>
          Campaign Status Overview
        </Typography>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', md: 'repeat(3, 1fr)' }, gap: 2 }}>
          {campaigns.slice(0, 6).map((campaign) => (
            <Card key={campaign.id} sx={{ height: '100%' }}>
              <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                  <Typography variant="h6" sx={{ fontSize: '1rem', fontWeight: 'bold' }}>
                    {campaign.name}
                  </Typography>
                  <Chip
                    label={campaign.status.toUpperCase()}
                    color={getStatusColor(campaign.status) as any}
                    size="small"
                  />
                </Box>

                <Box sx={{ mb: 2 }}>
                  <Typography variant="body2" color="text.secondary">
                    Channel: {campaign.channel.toUpperCase()}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {format(new Date(campaign.startDate), 'MMM dd')} - {format(new Date(campaign.endDate), 'MMM dd')}
                  </Typography>
                </Box>

                <Divider sx={{ my: 1 }} />

                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                  <Typography variant="body2">Budget:</Typography>
                  <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                    {formatCurrency(campaign.budget)}
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                  <Typography variant="body2">Spent:</Typography>
                  <Typography variant="body2" sx={{ fontWeight: 'bold', color: MARKETING_COLORS.primary }}>
                    {formatCurrency(campaign.spent)}
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                  <Typography variant="body2">CTR:</Typography>
                  <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                    {campaign.ctr.toFixed(2)}%
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body2">ROAS:</Typography>
                  <Typography variant="body2" sx={{ fontWeight: 'bold', color: MARKETING_COLORS.success }}>
                    {campaign.roas.toFixed(1)}x
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          ))}
        </Box>
      </Box>

      {/* Bottom Row - A/B Testing Results, Top Content, Social Engagement */}
      <Box sx={{ display: 'flex', gap: 3, mb: 3, flexWrap: 'wrap' }}>
        {/* A/B Testing Results */}
        <Box sx={{ flex: '1 1 400px', minWidth: 350 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ color: MARKETING_COLORS.primary }}>
                A/B Testing Results
              </Typography>
              <TableContainer component={Paper} elevation={0}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Campaign</TableCell>
                      <TableCell>Variant</TableCell>
                      <TableCell align="right">Conv. Rate</TableCell>
                      <TableCell align="right">Confidence</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {abTestResults.map((result) => (
                      <TableRow key={result.id}>
                        <TableCell>{result.campaignName}</TableCell>
                        <TableCell>
                          <Box sx={{ display: 'flex', alignItems: 'center' }}>
                            {result.variant}
                            {result.winner && (
                              <Chip label="Winner" color="success" size="small" sx={{ ml: 1 }} />
                            )}
                          </Box>
                        </TableCell>
                        <TableCell align="right">{result.conversionRate.toFixed(2)}%</TableCell>
                        <TableCell align="right">{result.confidence.toFixed(0)}%</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </Card>
        </Box>

        {/* Top Performing Content */}
        <Box sx={{ flex: '1 1 400px', minWidth: 350 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ color: MARKETING_COLORS.primary }}>
                Top Performing Content
              </Typography>
              <TableContainer component={Paper} elevation={0}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Content</TableCell>
                      <TableCell align="right">Views</TableCell>
                      <TableCell align="right">Leads</TableCell>
                      <TableCell align="right">Engagement</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {topContent.slice(0, 5).map((content) => (
                      <TableRow key={content.id}>
                        <TableCell>
                          <Box>
                            <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                              {content.title}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {content.type.toUpperCase()}
                            </Typography>
                          </Box>
                        </TableCell>
                        <TableCell align="right">{formatNumber(content.views)}</TableCell>
                        <TableCell align="right">{content.leads}</TableCell>
                        <TableCell align="right">{content.engagementRate.toFixed(1)}%</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </Card>
        </Box>
      </Box>

      {/* Social Media Engagement & Campaign Calendar */}
      <Box sx={{ display: 'flex', gap: 3, mb: 3, flexWrap: 'wrap' }}>
        {/* Social Media Engagement */}
        <Box sx={{ flex: '1 1 400px', minWidth: 350 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ color: MARKETING_COLORS.primary }}>
                Social Media Engagement
              </Typography>
              {socialEngagement.map((social) => (
                <Box key={social.platform} sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                  <ListItemAvatar>
                    <Avatar sx={{ bgcolor: (MARKETING_COLORS.social as any)[social.platform.toLowerCase()] }}>
                      {social.icon}
                    </Avatar>
                  </ListItemAvatar>
                  <ListItemText
                    primary={social.platform}
                    secondary={`${formatNumber(social.followers)} followers • ${social.engagement.toFixed(1)}% engagement`}
                  />
                  <Box sx={{ textAlign: 'right' }}>
                    <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                      {formatNumber(social.reach)}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      reach
                    </Typography>
                  </Box>
                </Box>
              ))}
            </CardContent>
          </Card>
        </Box>

        {/* Campaign Calendar */}
        <Box sx={{ flex: '1 1 500px', minWidth: 450 }}>
          <CampaignCalendarView campaigns={campaigns} loading={loading} />
        </Box>
      </Box>

      {/* Lead Generation Metrics */}
      <Box sx={{ mb: 3 }}>
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom sx={{ color: MARKETING_COLORS.primary }}>
              Lead Generation Metrics
            </Typography>
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={leadGenData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" />
                <YAxis />
                <RechartsTooltip />
                <Area
                  type="monotone"
                  dataKey="leads"
                  stackId="1"
                  stroke={MARKETING_COLORS.primary}
                  fill={MARKETING_COLORS.primary}
                  fillOpacity={0.6}
                  name="Total Leads"
                />
                <Area
                  type="monotone"
                  dataKey="qualifiedLeads"
                  stackId="2"
                  stroke={MARKETING_COLORS.success}
                  fill={MARKETING_COLORS.success}
                  fillOpacity={0.6}
                  name="Qualified Leads"
                />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </Box>

      {/* Quick Actions */}
      <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
        <Box sx={{ flex: '1 1 300px', minWidth: 250 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ color: MARKETING_COLORS.primary }}>
                Quick Actions
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <Button
                  variant="contained"
                  startIcon={<Add />}
                  fullWidth
                  sx={{
                    bgcolor: MARKETING_COLORS.primary,
                    '&:hover': { bgcolor: MARKETING_COLORS.secondary }
                  }}
                >
                  Create New Campaign
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<Science />}
                  fullWidth
                  sx={{
                    borderColor: MARKETING_COLORS.primary,
                    color: MARKETING_COLORS.primary,
                    '&:hover': { borderColor: MARKETING_COLORS.secondary, color: MARKETING_COLORS.secondary }
                  }}
                >
                  Start A/B Test
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<Analytics />}
                  fullWidth
                  sx={{
                    borderColor: MARKETING_COLORS.primary,
                    color: MARKETING_COLORS.primary,
                    '&:hover': { borderColor: MARKETING_COLORS.secondary, color: MARKETING_COLORS.secondary }
                  }}
                >
                  View Analytics
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<CalendarToday />}
                  fullWidth
                  sx={{
                    borderColor: MARKETING_COLORS.primary,
                    color: MARKETING_COLORS.primary,
                    '&:hover': { borderColor: MARKETING_COLORS.secondary, color: MARKETING_COLORS.secondary }
                  }}
                >
                  Schedule Content
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
const generateMockKPIs = (): MarketingKPIs => ({
  activeCampaigns: 12,
  totalReach: {
    current: 2450000,
    previous: 2100000,
    change: 16.7,
  },
  conversionRate: {
    current: 3.2,
    previous: 2.8,
    change: 14.3,
  },
  roi: {
    current: 285,
    previous: 245,
    change: 16.3,
  },
  emailOpenRate: {
    current: 24.5,
    previous: 22.1,
    change: 10.9,
  },
  clickThroughRate: {
    current: 3.8,
    previous: 3.2,
    change: 18.8,
  },
});

const generateMockCampaigns = (): Campaign[] => [
  {
    id: '1',
    name: 'Summer Music Festival Promo',
    status: 'active',
    channel: 'social',
    budget: 25000,
    spent: 18500,
    impressions: 450000,
    clicks: 13500,
    conversions: 425,
    revenue: 127500,
    startDate: new Date(Date.now() - 15 * 24 * 60 * 60 * 1000).toISOString(),
    endDate: new Date(Date.now() + 10 * 24 * 60 * 60 * 1000).toISOString(),
    ctr: 3.0,
    cpc: 1.37,
    roas: 6.9,
  },
  {
    id: '2',
    name: 'Soundtrack Essential Q3 Push',
    status: 'active',
    channel: 'email',
    budget: 15000,
    spent: 12300,
    impressions: 185000,
    clicks: 7400,
    conversions: 296,
    revenue: 88800,
    startDate: new Date(Date.now() - 20 * 24 * 60 * 60 * 1000).toISOString(),
    endDate: new Date(Date.now() + 5 * 24 * 60 * 60 * 1000).toISOString(),
    ctr: 4.0,
    cpc: 1.66,
    roas: 7.2,
  },
  {
    id: '3',
    name: 'Beat Breeze Mobile Launch',
    status: 'scheduled',
    channel: 'mobile',
    budget: 30000,
    spent: 0,
    impressions: 0,
    clicks: 0,
    conversions: 0,
    revenue: 0,
    startDate: new Date(Date.now() + 5 * 24 * 60 * 60 * 1000).toISOString(),
    endDate: new Date(Date.now() + 35 * 24 * 60 * 60 * 1000).toISOString(),
    ctr: 0,
    cpc: 0,
    roas: 0,
  },
  {
    id: '4',
    name: 'Restaurant Chain Retargeting',
    status: 'active',
    channel: 'web',
    budget: 20000,
    spent: 16800,
    impressions: 320000,
    clicks: 9600,
    conversions: 192,
    revenue: 57600,
    startDate: new Date(Date.now() - 25 * 24 * 60 * 60 * 1000).toISOString(),
    endDate: new Date(Date.now() + 5 * 24 * 60 * 60 * 1000).toISOString(),
    ctr: 3.0,
    cpc: 1.75,
    roas: 3.4,
  },
  {
    id: '5',
    name: 'Holiday Season Prep',
    status: 'completed',
    channel: 'email',
    budget: 18000,
    spent: 18000,
    impressions: 240000,
    clicks: 12000,
    conversions: 360,
    revenue: 108000,
    startDate: new Date(Date.now() - 60 * 24 * 60 * 60 * 1000).toISOString(),
    endDate: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
    ctr: 5.0,
    cpc: 1.50,
    roas: 6.0,
  },
  {
    id: '6',
    name: 'Gym Network Partnership',
    status: 'paused',
    channel: 'display',
    budget: 12000,
    spent: 8500,
    impressions: 180000,
    clicks: 3600,
    conversions: 72,
    revenue: 21600,
    startDate: new Date(Date.now() - 40 * 24 * 60 * 60 * 1000).toISOString(),
    endDate: new Date(Date.now() - 10 * 24 * 60 * 60 * 1000).toISOString(),
    ctr: 2.0,
    cpc: 2.36,
    roas: 2.5,
  },
];

const generateMockChannelData = (): ChannelData[] => [
  { channel: 'Email', impressions: 625000, clicks: 31250, conversions: 1250, spend: 28800, fill: MARKETING_COLORS.channels[0] },
  { channel: 'Social Media', impressions: 450000, clicks: 13500, conversions: 425, spend: 18500, fill: MARKETING_COLORS.channels[1] },
  { channel: 'Web/Display', impressions: 500000, clicks: 15000, conversions: 300, spend: 25300, fill: MARKETING_COLORS.channels[2] },
  { channel: 'Mobile', impressions: 380000, clicks: 11400, conversions: 285, spend: 19200, fill: MARKETING_COLORS.channels[3] },
  { channel: 'Search', impressions: 295000, clicks: 14750, conversions: 442, spend: 22100, fill: MARKETING_COLORS.channels[4] },
];

const generateMockFunnelData = (): ConversionFunnelData[] => [
  { stage: 'Visitors', visitors: 150000, percentage: 100, fill: MARKETING_COLORS.funnel[0] },
  { stage: 'Interested', visitors: 45000, percentage: 30, fill: MARKETING_COLORS.funnel[1] },
  { stage: 'Consideration', visitors: 15000, percentage: 10, fill: MARKETING_COLORS.funnel[2] },
  { stage: 'Intent', visitors: 7500, percentage: 5, fill: MARKETING_COLORS.funnel[3] },
  { stage: 'Purchase', visitors: 4500, percentage: 3, fill: MARKETING_COLORS.funnel[4] },
];

const generateMockABTestResults = (): ABTestResult[] => [
  { id: '1', campaignName: 'Summer Festival', variant: 'A', conversions: 245, conversionRate: 3.2, confidence: 95, winner: true },
  { id: '2', campaignName: 'Summer Festival', variant: 'B', conversions: 198, conversionRate: 2.6, confidence: 95, winner: false },
  { id: '3', campaignName: 'Email Campaign', variant: 'A', conversions: 156, conversionRate: 4.1, confidence: 92, winner: false },
  { id: '4', campaignName: 'Email Campaign', variant: 'B', conversions: 189, conversionRate: 4.8, confidence: 92, winner: true },
  { id: '5', campaignName: 'Mobile Ad', variant: 'A', conversions: 89, conversionRate: 2.8, confidence: 88, winner: false },
  { id: '6', campaignName: 'Mobile Ad', variant: 'B', conversions: 112, conversionRate: 3.5, confidence: 88, winner: true },
];

const generateMockContentPerformance = (): ContentPerformance[] => [
  { id: '1', title: 'Ultimate Guide to Restaurant Music', type: 'blog', views: 25400, shares: 1240, leads: 184, engagementRate: 8.2, publishDate: '2024-08-15' },
  { id: '2', title: 'Music Psychology in Retail', type: 'video', views: 18600, shares: 950, leads: 156, engagementRate: 12.4, publishDate: '2024-08-20' },
  { id: '3', title: 'Soundtrack Success Stories', type: 'ebook', views: 12800, shares: 640, leads: 220, engagementRate: 15.8, publishDate: '2024-08-10' },
  { id: '4', title: 'Creating Brand Atmosphere', type: 'webinar', views: 8500, shares: 425, leads: 148, engagementRate: 22.1, publishDate: '2024-08-25' },
  { id: '5', title: 'Music Licensing Basics', type: 'infographic', views: 15200, shares: 760, leads: 95, engagementRate: 9.8, publishDate: '2024-08-12' },
];

const generateMockSocialEngagement = (): SocialEngagement[] => [
  { platform: 'Facebook', followers: 24500, engagement: 4.2, posts: 28, reach: 125000, icon: <Share /> },
  { platform: 'Instagram', followers: 18200, engagement: 6.8, posts: 35, reach: 89000, icon: <Share /> },
  { platform: 'LinkedIn', followers: 12800, engagement: 3.1, posts: 18, reach: 45000, icon: <Share /> },
  { platform: 'Twitter', followers: 15600, engagement: 2.9, posts: 42, reach: 68000, icon: <Share /> },
  { platform: 'YouTube', followers: 8900, engagement: 8.4, posts: 12, reach: 156000, icon: <Share /> },
];

const generateMockCampaignPerformanceData = () => {
  const months = [];
  for (let i = 11; i >= 0; i--) {
    const date = subMonths(new Date(), i);
    months.push({
      month: format(date, 'MMM'),
      impressions: 400000 + Math.random() * 200000,
      clicks: 12000 + Math.random() * 8000,
      conversions: 300 + Math.random() * 200,
      spend: 15000 + Math.random() * 10000,
    });
  }
  return months;
};

const generateMockBudgetData = () => [
  { campaign: 'Summer Festival', budget: 25000, spent: 18500, efficiency: 74 },
  { campaign: 'Email Campaign', budget: 15000, spent: 12300, efficiency: 82 },
  { campaign: 'Mobile Launch', budget: 30000, spent: 0, efficiency: 0 },
  { campaign: 'Web Retargeting', budget: 20000, spent: 16800, efficiency: 84 },
  { campaign: 'Holiday Prep', budget: 18000, spent: 18000, efficiency: 100 },
];

const generateMockLeadGenData = () => {
  const months = [];
  for (let i = 11; i >= 0; i--) {
    const date = subMonths(new Date(), i);
    const totalLeads = 400 + Math.random() * 300;
    months.push({
      month: format(date, 'MMM'),
      leads: Math.round(totalLeads),
      qualifiedLeads: Math.round(totalLeads * 0.65),
    });
  }
  return months;
};

export default MarketingDashboard;