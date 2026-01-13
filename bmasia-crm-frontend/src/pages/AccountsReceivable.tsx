import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Card,
  CardContent,
  FormControl,
  Select,
  MenuItem,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  GridLegacy as Grid,
  Alert,
  CircularProgress,
  SelectChangeEvent,
  Tooltip,
  IconButton,
  Collapse,
  Chip,
} from '@mui/material';
import {
  AccountBalance,
  Warning,
  CheckCircle,
  Refresh,
  ExpandMore,
  ExpandLess,
  Receipt,
} from '@mui/icons-material';
import ApiService, { ARAgingReport, ARCompanyDetail } from '../services/api';

interface KPICardProps {
  title: string;
  value: string;
  subtitle?: string;
  icon: React.ReactNode;
  color: string;
  alert?: boolean;
}

const KPICard: React.FC<KPICardProps> = ({ title, value, subtitle, icon, color, alert }) => {
  return (
    <Card sx={{ height: '100%', borderLeft: alert ? '4px solid #F44336' : 'none' }}>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
          <Box
            sx={{
              backgroundColor: color,
              borderRadius: '50%',
              width: 48,
              height: 48,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'white',
            }}
          >
            {icon}
          </Box>
          {alert && (
            <Tooltip title="Requires attention">
              <Warning color="error" />
            </Tooltip>
          )}
        </Box>
        <Typography variant="h4" component="div" sx={{ mb: 0.5, fontWeight: 600 }}>
          {value}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {title}
        </Typography>
        {subtitle && (
          <Typography variant="caption" color="text.secondary">
            {subtitle}
          </Typography>
        )}
      </CardContent>
    </Card>
  );
};

const AccountsReceivable: React.FC = () => {
  const [currency, setCurrency] = useState<string>('USD');
  const [billingEntity, setBillingEntity] = useState<string>('bmasia_th');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string>('');
  const [report, setReport] = useState<ARAgingReport | null>(null);
  const [expandedCompanies, setExpandedCompanies] = useState<Set<string>>(new Set());

  useEffect(() => {
    loadARData();
  }, [currency, billingEntity]);

  const loadARData = async () => {
    try {
      setLoading(true);
      setError('');
      const response = await ApiService.getARAgingReport(currency, billingEntity);
      setReport(response);
    } catch (err: any) {
      console.error('AR Aging error:', err);
      setError('Failed to load AR aging data.');
    } finally {
      setLoading(false);
    }
  };

  const handleCurrencyChange = (event: SelectChangeEvent<string>) => {
    setCurrency(event.target.value);
  };

  const handleEntityChange = (event: SelectChangeEvent<string>) => {
    setBillingEntity(event.target.value);
  };

  const toggleCompanyExpand = (companyId: string) => {
    setExpandedCompanies(prev => {
      const newSet = new Set(prev);
      if (newSet.has(companyId)) {
        newSet.delete(companyId);
      } else {
        newSet.add(companyId);
      }
      return newSet;
    });
  };

  const formatCurrency = (value: number): string => {
    const locale = currency === 'THB' ? 'th-TH' : 'en-US';
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: currency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  const getAgingBucketColor = (bucket: string): string => {
    switch (bucket) {
      case 'current':
        return '#4CAF50';
      case '1_30':
        return '#FFC107';
      case '31_60':
        return '#FF9800';
      case '61_90':
        return '#F44336';
      case '90_plus':
        return '#B71C1C';
      default:
        return '#9E9E9E';
    }
  };

  const getAgingBucketLabel = (bucket: string): string => {
    switch (bucket) {
      case 'current':
        return 'Current';
      case '1_30':
        return '1-30 Days';
      case '31_60':
        return '31-60 Days';
      case '61_90':
        return '61-90 Days';
      case '90_plus':
        return '90+ Days';
      default:
        return bucket;
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  const summary = report?.summary || {
    total_ar: 0,
    current: 0,
    '1_30': 0,
    '31_60': 0,
    '61_90': 0,
    '90_plus': 0,
    invoice_count: 0,
  };

  const overdueTotal = summary['1_30'] + summary['31_60'] + summary['61_90'] + summary['90_plus'];
  const criticalTotal = summary['61_90'] + summary['90_plus'];

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" component="h1" gutterBottom>
            Accounts Receivable Aging
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Outstanding invoices by aging bucket (as of {report?.as_of_date || 'today'})
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <FormControl size="small" sx={{ minWidth: 100 }}>
            <Select value={currency} onChange={handleCurrencyChange}>
              <MenuItem value="USD">USD</MenuItem>
              <MenuItem value="THB">THB</MenuItem>
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 150 }}>
            <Select value={billingEntity} onChange={handleEntityChange}>
              <MenuItem value="bmasia_th">Thailand</MenuItem>
              <MenuItem value="bmasia_hk">Hong Kong</MenuItem>
            </Select>
          </FormControl>
          <Tooltip title="Refresh data">
            <IconButton onClick={loadARData} disabled={loading}>
              <Refresh />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* KPI Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <KPICard
            title="Total AR"
            value={formatCurrency(summary.total_ar)}
            subtitle={`${summary.invoice_count} invoices`}
            icon={<AccountBalance />}
            color="#FFA500"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KPICard
            title="Current"
            value={formatCurrency(summary.current)}
            subtitle="Not yet due"
            icon={<CheckCircle />}
            color="#4CAF50"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KPICard
            title="Overdue"
            value={formatCurrency(overdueTotal)}
            subtitle="Past due date"
            icon={<Warning />}
            color="#FF9800"
            alert={overdueTotal > 0}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KPICard
            title="Critical (60+ Days)"
            value={formatCurrency(criticalTotal)}
            subtitle="Requires immediate action"
            icon={<Warning />}
            color="#F44336"
            alert={criticalTotal > 0}
          />
        </Grid>
      </Grid>

      {/* Aging Buckets Summary */}
      <Paper sx={{ mb: 4, p: 2 }}>
        <Typography variant="h6" gutterBottom>
          Aging Distribution
        </Typography>
        <Grid container spacing={2}>
          {[
            { key: 'current', label: 'Current' },
            { key: '1_30', label: '1-30 Days' },
            { key: '31_60', label: '31-60 Days' },
            { key: '61_90', label: '61-90 Days' },
            { key: '90_plus', label: '90+ Days' },
          ].map(bucket => {
            const value = summary[bucket.key as keyof typeof summary] as number;
            const percentage = summary.total_ar > 0 ? (value / summary.total_ar) * 100 : 0;
            return (
              <Grid item xs={12} sm={6} md={2.4} key={bucket.key}>
                <Box sx={{ textAlign: 'center' }}>
                  <Typography variant="h6" sx={{ color: getAgingBucketColor(bucket.key) }}>
                    {formatCurrency(value)}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {bucket.label}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {percentage.toFixed(1)}%
                  </Typography>
                </Box>
              </Grid>
            );
          })}
        </Grid>
      </Paper>

      {/* Company Breakdown Table */}
      <Paper sx={{ width: '100%', overflow: 'hidden' }}>
        <Box sx={{ p: 2, borderBottom: '1px solid #e0e0e0' }}>
          <Typography variant="h6">
            AR by Company
          </Typography>
        </Box>
        <TableContainer sx={{ maxHeight: 600 }}>
          <Table stickyHeader size="small">
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 600, backgroundColor: '#f5f5f5', width: 40 }} />
                <TableCell sx={{ fontWeight: 600, backgroundColor: '#f5f5f5' }}>
                  Company
                </TableCell>
                <TableCell align="right" sx={{ fontWeight: 600, backgroundColor: '#f5f5f5' }}>
                  Total
                </TableCell>
                <TableCell align="right" sx={{ fontWeight: 600, backgroundColor: '#f5f5f5' }}>
                  Current
                </TableCell>
                <TableCell align="right" sx={{ fontWeight: 600, backgroundColor: '#f5f5f5' }}>
                  1-30 Days
                </TableCell>
                <TableCell align="right" sx={{ fontWeight: 600, backgroundColor: '#f5f5f5' }}>
                  31-60 Days
                </TableCell>
                <TableCell align="right" sx={{ fontWeight: 600, backgroundColor: '#f5f5f5' }}>
                  61-90 Days
                </TableCell>
                <TableCell align="right" sx={{ fontWeight: 600, backgroundColor: '#f5f5f5' }}>
                  90+ Days
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {report?.by_company.map((company: ARCompanyDetail) => (
                <React.Fragment key={company.company_id}>
                  <TableRow
                    hover
                    onClick={() => toggleCompanyExpand(company.company_id)}
                    sx={{ cursor: 'pointer', '&:hover': { backgroundColor: '#f5f5f5' } }}
                  >
                    <TableCell>
                      <IconButton size="small">
                        {expandedCompanies.has(company.company_id) ? <ExpandLess /> : <ExpandMore />}
                      </IconButton>
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Typography variant="body2" sx={{ fontWeight: 500 }}>
                          {company.company_name}
                        </Typography>
                        <Chip
                          size="small"
                          label={`${company.invoices.length} invoices`}
                          sx={{ fontSize: '0.7rem' }}
                        />
                      </Box>
                    </TableCell>
                    <TableCell align="right">
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        {formatCurrency(company.total)}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      {company.current > 0 && (
                        <Typography variant="body2" sx={{ color: getAgingBucketColor('current') }}>
                          {formatCurrency(company.current)}
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell align="right">
                      {company['1_30'] > 0 && (
                        <Typography variant="body2" sx={{ color: getAgingBucketColor('1_30') }}>
                          {formatCurrency(company['1_30'])}
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell align="right">
                      {company['31_60'] > 0 && (
                        <Typography variant="body2" sx={{ color: getAgingBucketColor('31_60') }}>
                          {formatCurrency(company['31_60'])}
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell align="right">
                      {company['61_90'] > 0 && (
                        <Typography variant="body2" sx={{ color: getAgingBucketColor('61_90') }}>
                          {formatCurrency(company['61_90'])}
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell align="right">
                      {company['90_plus'] > 0 && (
                        <Typography variant="body2" sx={{ color: getAgingBucketColor('90_plus'), fontWeight: 600 }}>
                          {formatCurrency(company['90_plus'])}
                        </Typography>
                      )}
                    </TableCell>
                  </TableRow>

                  {/* Expanded Invoice Details */}
                  <TableRow>
                    <TableCell colSpan={8} sx={{ p: 0, border: 0 }}>
                      <Collapse in={expandedCompanies.has(company.company_id)} timeout="auto" unmountOnExit>
                        <Box sx={{ p: 2, backgroundColor: '#fafafa' }}>
                          <Table size="small">
                            <TableHead>
                              <TableRow>
                                <TableCell sx={{ fontWeight: 600 }}>Invoice #</TableCell>
                                <TableCell sx={{ fontWeight: 600 }}>Issue Date</TableCell>
                                <TableCell sx={{ fontWeight: 600 }}>Due Date</TableCell>
                                <TableCell align="right" sx={{ fontWeight: 600 }}>Amount</TableCell>
                                <TableCell align="right" sx={{ fontWeight: 600 }}>Days Overdue</TableCell>
                                <TableCell sx={{ fontWeight: 600 }}>Status</TableCell>
                              </TableRow>
                            </TableHead>
                            <TableBody>
                              {company.invoices.map(invoice => (
                                <TableRow key={invoice.invoice_id}>
                                  <TableCell>
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                      <Receipt fontSize="small" color="action" />
                                      {invoice.invoice_number}
                                    </Box>
                                  </TableCell>
                                  <TableCell>{invoice.issue_date}</TableCell>
                                  <TableCell>{invoice.due_date}</TableCell>
                                  <TableCell align="right">{formatCurrency(invoice.amount)}</TableCell>
                                  <TableCell align="right">
                                    {invoice.days_overdue > 0 ? (
                                      <Chip
                                        size="small"
                                        label={`${invoice.days_overdue} days`}
                                        sx={{
                                          backgroundColor: getAgingBucketColor(invoice.aging_bucket),
                                          color: 'white',
                                          fontWeight: 500,
                                        }}
                                      />
                                    ) : (
                                      <Chip size="small" label="Current" color="success" />
                                    )}
                                  </TableCell>
                                  <TableCell>
                                    <Chip
                                      size="small"
                                      label={invoice.status}
                                      variant="outlined"
                                    />
                                  </TableCell>
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
                        </Box>
                      </Collapse>
                    </TableCell>
                  </TableRow>
                </React.Fragment>
              ))}

              {(!report?.by_company || report.by_company.length === 0) && (
                <TableRow>
                  <TableCell colSpan={8} align="center" sx={{ py: 4 }}>
                    <Typography color="text.secondary">
                      No outstanding invoices found
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>
    </Box>
  );
};

export default AccountsReceivable;
