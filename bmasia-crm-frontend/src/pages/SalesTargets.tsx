import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Paper,
  Typography,
  GridLegacy as Grid,
  Card,
  CardContent,
  Alert,
  CircularProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  SelectChangeEvent,
  ToggleButtonGroup,
  ToggleButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Button,
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  CheckCircle as CheckCircleIcon,
  AttachMoney as AttachMoneyIcon,
  ShowChart as ShowChartIcon,
  PictureAsPdf as PdfIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { Opportunity, ApiResponse } from '../types';
import ApiService from '../services/api';

interface PeriodData {
  period: string;
  dealsWon: number;
  totalValue: number;
  avgValue: number;
}

type EntityFilter = 'all' | 'BMAsia Limited' | 'BMAsia (Thailand) Co., Ltd.';

const ENTITY_CURRENCY: Record<string, { currency: string; locale: string }> = {
  'BMAsia Limited': { currency: 'USD', locale: 'en-US' },
  'BMAsia (Thailand) Co., Ltd.': { currency: 'THB', locale: 'th-TH' },
};

const SalesPerformance: React.FC = () => {
  const navigate = useNavigate();
  const [wonOpportunities, setWonOpportunities] = useState<Opportunity[]>([]);
  const [lostOpportunities, setLostOpportunities] = useState<Opportunity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedYear, setSelectedYear] = useState<number>(new Date().getFullYear());
  const [periodType, setPeriodType] = useState<'monthly' | 'quarterly'>('monthly');
  const [entityFilter, setEntityFilter] = useState<EntityFilter>('all');
  const [exporting, setExporting] = useState(false);

  // Generate year options (current year and previous 2 years)
  const currentYear = new Date().getFullYear();
  const yearOptions = [currentYear, currentYear - 1, currentYear - 2];

  useEffect(() => {
    loadData();
  }, [selectedYear, entityFilter]);

  const loadData = async () => {
    try {
      setLoading(true);
      setError('');

      const yearStart = `${selectedYear}-01-01`;

      const baseParams: any = {
        page_size: 500,
        created_after: yearStart,
      };

      if (entityFilter !== 'all') {
        baseParams.company__billing_entity = entityFilter;
      }

      // Load Won opportunities
      const wonResponse: ApiResponse<Opportunity> = await ApiService.getOpportunities({
        ...baseParams,
        stage: 'Won',
      });

      // Load Lost opportunities for win rate calculation
      const lostResponse: ApiResponse<Opportunity> = await ApiService.getOpportunities({
        ...baseParams,
        stage: 'Lost',
      });

      setWonOpportunities(wonResponse.results);
      setLostOpportunities(lostResponse.results);
    } catch (err: any) {
      setError('Failed to load sales performance data');
      console.error('Sales performance error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleYearChange = useCallback((event: SelectChangeEvent<number>) => {
    setSelectedYear(event.target.value as number);
  }, []);

  const handlePeriodTypeChange = useCallback((_: React.MouseEvent<HTMLElement>, newValue: 'monthly' | 'quarterly' | null) => {
    if (newValue !== null) {
      setPeriodType(newValue);
    }
  }, []);

  const handleEntityChange = useCallback((event: SelectChangeEvent<EntityFilter>) => {
    setEntityFilter(event.target.value as EntityFilter);
  }, []);

  const handleExportPDF = async () => {
    setExporting(true);
    try {
      const token = localStorage.getItem('bmasia_access_token') || sessionStorage.getItem('bmasia_access_token');
      const baseUrl = process.env.REACT_APP_API_URL || '';
      const params = new URLSearchParams();

      params.append('year', selectedYear.toString());
      params.append('period_type', periodType);
      if (entityFilter !== 'all') params.append('entity', entityFilter);

      const response = await fetch(
        `${baseUrl}/api/v1/opportunities/export/sales-performance-pdf/?${params.toString()}`,
        { headers: { 'Authorization': `Bearer ${token}` } }
      );

      if (!response.ok) throw new Error('Export failed');

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Sales_Performance_${selectedYear}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      console.error('Export error:', err);
      setError('Failed to export PDF');
    } finally {
      setExporting(false);
    }
  };

  // Calculate KPIs
  const totalWonValue = wonOpportunities.reduce((sum, opp) => sum + (opp.expected_value || 0), 0);
  const dealsWon = wonOpportunities.length;
  const avgDealSize = dealsWon > 0 ? totalWonValue / dealsWon : 0;
  const totalDeals = wonOpportunities.length + lostOpportunities.length;
  const winRate = totalDeals > 0 ? (wonOpportunities.length / totalDeals) * 100 : 0;

  // Format currency based on entity filter
  const formatCurrency = (value: number, entity?: string): string => {
    const resolvedEntity = entity || (entityFilter !== 'all' ? entityFilter : undefined);
    const config = resolvedEntity ? ENTITY_CURRENCY[resolvedEntity] : undefined;
    const currency = config?.currency || 'USD';
    const locale = config?.locale || 'en-US';

    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  // Get currency label for "All" mode
  const getCurrencyLabel = (): string => {
    if (entityFilter !== 'all') {
      return ENTITY_CURRENCY[entityFilter]?.currency || 'USD';
    }
    return 'USD'; // Default for mixed view
  };

  // Get month/quarter from opportunity date
  const getOpportunityPeriod = (opp: Opportunity): string => {
    const date = new Date(opp.actual_close_date || opp.updated_at);
    const month = date.getMonth(); // 0-11

    if (periodType === 'monthly') {
      return new Date(date.getFullYear(), month, 1).toLocaleDateString('en-US', { month: 'short' });
    } else {
      const quarter = Math.floor(month / 3) + 1;
      return `Q${quarter}`;
    }
  };

  // Group opportunities by period
  const getPeriodBreakdown = (): PeriodData[] => {
    const periodMap = new Map<string, Opportunity[]>();

    // Initialize all periods
    if (periodType === 'monthly') {
      const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
      months.forEach(month => periodMap.set(month, []));
    } else {
      ['Q1', 'Q2', 'Q3', 'Q4'].forEach(quarter => periodMap.set(quarter, []));
    }

    // Group opportunities
    wonOpportunities.forEach(opp => {
      const period = getOpportunityPeriod(opp);
      const existing = periodMap.get(period) || [];
      periodMap.set(period, [...existing, opp]);
    });

    // Calculate totals for each period
    const periodData: PeriodData[] = [];
    periodMap.forEach((opps, period) => {
      const totalValue = opps.reduce((sum, opp) => sum + (opp.expected_value || 0), 0);
      const dealsWon = opps.length;
      const avgValue = dealsWon > 0 ? totalValue / dealsWon : 0;

      periodData.push({
        period,
        dealsWon,
        totalValue,
        avgValue,
      });
    });

    return periodData;
  };

  // Get top 5 won deals
  const getTopDeals = (): Opportunity[] => {
    return [...wonOpportunities]
      .sort((a, b) => (b.expected_value || 0) - (a.expected_value || 0))
      .slice(0, 5);
  };

  const periodBreakdown = getPeriodBreakdown();
  const topDeals = getTopDeals();

  // Calculate totals
  const totals = periodBreakdown.reduce(
    (acc, period) => ({
      dealsWon: acc.dealsWon + period.dealsWon,
      totalValue: acc.totalValue + period.totalValue,
      avgValue: 0, // Will be calculated after
    }),
    { dealsWon: 0, totalValue: 0, avgValue: 0 }
  );
  totals.avgValue = totals.dealsWon > 0 ? totals.totalValue / totals.dealsWon : 0;

  // Shared filter controls
  const renderFilters = () => (
    <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
      <Button
        variant="outlined"
        size="small"
        startIcon={exporting ? <CircularProgress size={16} /> : <PdfIcon />}
        onClick={handleExportPDF}
        disabled={exporting || loading || wonOpportunities.length === 0}
        sx={{ whiteSpace: 'nowrap' }}
      >
        PDF
      </Button>
      <ToggleButtonGroup
        value={periodType}
        exclusive
        onChange={handlePeriodTypeChange}
        size="small"
      >
        <ToggleButton value="monthly" sx={{ whiteSpace: 'nowrap' }}>
          Monthly
        </ToggleButton>
        <ToggleButton value="quarterly" sx={{ whiteSpace: 'nowrap' }}>
          Quarterly
        </ToggleButton>
      </ToggleButtonGroup>
      <FormControl size="small" sx={{ minWidth: 180 }}>
        <InputLabel>Entity</InputLabel>
        <Select value={entityFilter} onChange={handleEntityChange} label="Entity">
          <MenuItem value="all">All Entities (USD)</MenuItem>
          <MenuItem value="BMAsia Limited">BMAsia Limited (USD)</MenuItem>
          <MenuItem value="BMAsia (Thailand) Co., Ltd.">BMAsia Thailand (THB)</MenuItem>
        </Select>
      </FormControl>
      <FormControl size="small" sx={{ minWidth: 100 }}>
        <InputLabel>Year</InputLabel>
        <Select value={selectedYear} onChange={handleYearChange} label="Year">
          {yearOptions.map(year => (
            <MenuItem key={year} value={year}>
              {year}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
    </Box>
  );

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '400px' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box>
        <Typography variant="h4" component="h1" sx={{ mb: 3 }}>
          Sales Performance
        </Typography>
        <Alert severity="error">{error}</Alert>
      </Box>
    );
  }

  if (wonOpportunities.length === 0) {
    return (
      <Box>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h4" component="h1">
            Sales Performance
          </Typography>
          {renderFilters()}
        </Box>
        {entityFilter === 'all' && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            Values shown in USD. Select a specific entity for accurate currency display.
          </Alert>
        )}
        <Alert severity="info">No won deals found for {selectedYear}{entityFilter !== 'all' ? ` (${entityFilter})` : ''}</Alert>
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1">
          Sales Performance
        </Typography>
        {renderFilters()}
      </Box>

      {/* Mixed currency warning */}
      {entityFilter === 'all' && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          Showing all entities — values displayed in USD. THB deals are shown at face value (not converted). Select a specific entity for accurate totals.
        </Alert>
      )}

      {/* KPI Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ bgcolor: 'success.light', color: 'success.contrastText' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <TrendingUpIcon sx={{ mr: 1, fontSize: 32 }} />
                <Typography variant="h5" component="div">
                  {formatCurrency(totalWonValue)}
                </Typography>
              </Box>
              <Typography variant="body2">Total Won Value</Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ bgcolor: 'info.light', color: 'info.contrastText' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <CheckCircleIcon sx={{ mr: 1, fontSize: 32 }} />
                <Typography variant="h5" component="div">
                  {dealsWon}
                </Typography>
              </Box>
              <Typography variant="body2">Deals Won</Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ bgcolor: 'warning.light', color: 'warning.contrastText' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <AttachMoneyIcon sx={{ mr: 1, fontSize: 32 }} />
                <Typography variant="h5" component="div">
                  {formatCurrency(avgDealSize)}
                </Typography>
              </Box>
              <Typography variant="body2">Average Deal Size</Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ bgcolor: 'secondary.light', color: 'secondary.contrastText' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <ShowChartIcon sx={{ mr: 1, fontSize: 32 }} />
                <Typography variant="h5" component="div">
                  {winRate.toFixed(1)}%
                </Typography>
              </Box>
              <Typography variant="body2">Win Rate</Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Main Content */}
      <Grid container spacing={3}>
        {/* Period Breakdown Table */}
        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" sx={{ mb: 2 }}>
              {periodType === 'monthly' ? 'Monthly' : 'Quarterly'} Breakdown ({getCurrencyLabel()})
            </Typography>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>
                      <strong>Period</strong>
                    </TableCell>
                    <TableCell align="right">
                      <strong>Deals Won</strong>
                    </TableCell>
                    <TableCell align="right">
                      <strong>Total Value</strong>
                    </TableCell>
                    <TableCell align="right">
                      <strong>Avg Value</strong>
                    </TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {periodBreakdown.map((period) => (
                    <TableRow key={period.period} hover>
                      <TableCell>{period.period}</TableCell>
                      <TableCell align="right">{period.dealsWon}</TableCell>
                      <TableCell align="right">{formatCurrency(period.totalValue)}</TableCell>
                      <TableCell align="right">{formatCurrency(period.avgValue)}</TableCell>
                    </TableRow>
                  ))}
                  <TableRow sx={{ bgcolor: 'grey.100' }}>
                    <TableCell>
                      <strong>Total</strong>
                    </TableCell>
                    <TableCell align="right">
                      <strong>{totals.dealsWon}</strong>
                    </TableCell>
                    <TableCell align="right">
                      <strong>{formatCurrency(totals.totalValue)}</strong>
                    </TableCell>
                    <TableCell align="right">
                      <strong>{formatCurrency(totals.avgValue)}</strong>
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        </Grid>

        {/* Top Won Deals */}
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" sx={{ mb: 2 }}>
              Top Won Deals
            </Typography>
            {topDeals.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                No deals to display
              </Typography>
            ) : (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {topDeals.map((deal) => (
                  <Card
                    key={deal.id}
                    sx={{
                      cursor: 'pointer',
                      transition: 'all 0.2s',
                      '&:hover': {
                        boxShadow: 3,
                        transform: 'translateY(-2px)',
                      },
                    }}
                    onClick={() => navigate(`/opportunities/${deal.id}`)}
                  >
                    <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                      <Typography variant="subtitle2" noWrap sx={{ mb: 0.5 }}>
                        {deal.company_name}
                      </Typography>
                      <Typography variant="body2" color="text.secondary" noWrap sx={{ mb: 1 }}>
                        {deal.name}
                      </Typography>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Chip
                          label={formatCurrency(deal.expected_value || 0, deal.company_billing_entity)}
                          size="small"
                          color="success"
                        />
                        <Typography variant="caption" color="text.secondary">
                          {deal.owner_name}
                        </Typography>
                      </Box>
                    </CardContent>
                  </Card>
                ))}
              </Box>
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default SalesPerformance;
