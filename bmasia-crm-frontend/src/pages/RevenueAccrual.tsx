import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  CircularProgress,
  LinearProgress,
  Stack,
  GridLegacy as Grid,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Chip,
  Tooltip,
  IconButton,
  Checkbox,
  FormControlLabel,
} from '@mui/material';
import {
  AccountBalance as AccountBalanceIcon,
  TrendingUp as TrendingUpIcon,
  Savings as SavingsIcon,
  Speed as SpeedIcon,
  TableChart as ExcelIcon,
  Upload as UploadIcon,
  Refresh as RefreshIcon,
  Cancel as CancelIcon,
  CheckCircle as CheckCircleIcon,
  Info as InfoIcon,
} from '@mui/icons-material';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  ResponsiveContainer,
  Line,
  ComposedChart,
} from 'recharts';
import apiService from '../services/api';

// ──────────────────────────────────────────────────────────────────────────────
// Constants
// ──────────────────────────────────────────────────────────────────────────────

const PRODUCT_COLORS: Record<string, string> = {
  SYB: '#FF6B35',
  LIM: '#4A90D9',
  SONOS: '#7B68EE',
  OTHER: '#9E9E9E',
};

const ENTITY_CURRENCY: Record<string, string> = {
  bmasia_th: 'THB',
  bmasia_hk: 'USD',
  '': 'THB',
};

const QUARTERS = ['Q1', 'Q2', 'Q3', 'Q4'] as const;

// ──────────────────────────────────────────────────────────────────────────────
// Formatting helpers
// ──────────────────────────────────────────────────────────────────────────────

const formatCurrency = (amount: number, currency: string = 'THB') => {
  const locale = currency === 'THB' ? 'th-TH' : 'en-US';
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
};

const formatPercent = (value: number) => `${value.toFixed(1)}%`;

const formatDate = (dateStr: string) => {
  if (!dateStr) return '-';
  try {
    return new Date(dateStr).toLocaleDateString('en-GB', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });
  } catch {
    return dateStr;
  }
};

// ──────────────────────────────────────────────────────────────────────────────
// KPI Card
// ──────────────────────────────────────────────────────────────────────────────

interface KPICardProps {
  title: string;
  value: string;
  subtitle?: string;
  icon: React.ReactNode;
  color: string;
}

const KPICard: React.FC<KPICardProps> = ({ title, value, subtitle, icon, color }) => (
  <Card sx={{ height: '100%' }}>
    <CardContent>
      <Box display="flex" alignItems="flex-start" justifyContent="space-between">
        <Box flex={1} minWidth={0}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            {title}
          </Typography>
          <Typography
            variant="h5"
            component="div"
            fontWeight="bold"
            color={color}
            sx={{ wordBreak: 'break-word' }}
          >
            {value}
          </Typography>
          {subtitle && (
            <Typography variant="body2" color="text.secondary" mt={0.5}>
              {subtitle}
            </Typography>
          )}
        </Box>
        <Box
          sx={{
            backgroundColor: `${color}15`,
            borderRadius: 2,
            p: 1,
            ml: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          {React.cloneElement(icon as React.ReactElement, { sx: { color, fontSize: 32 } })}
        </Box>
      </Box>
    </CardContent>
  </Card>
);

// ──────────────────────────────────────────────────────────────────────────────
// Recognition Chart (stacked bars by product + deferred balance line)
// ──────────────────────────────────────────────────────────────────────────────

interface ChartDataPoint {
  quarter: string;
  SYB: number;
  LIM: number;
  SONOS: number;
  OTHER: number;
  deferred: number;
}

interface RecognitionChartProps {
  data: ChartDataPoint[];
  currency: string;
  product: string;
}

const RecognitionChart: React.FC<RecognitionChartProps> = ({ data, currency, product }) => {
  const currencySymbol = currency === 'THB' ? '฿' : '$';
  const products = product && product !== '' ? [product] : ['SYB', 'LIM', 'SONOS', 'OTHER'];

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" fontWeight="bold" gutterBottom>
          Quarterly Revenue Recognition by Product
        </Typography>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          Stacked bars = recognized income | Line = deferred balance (Advance Received)
        </Typography>
        <ResponsiveContainer width="100%" height={380}>
          <ComposedChart data={data} margin={{ top: 8, right: 24, left: 8, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="quarter" />
            <YAxis
              yAxisId="left"
              tickFormatter={(v) => `${currencySymbol}${(v / 1000).toFixed(0)}k`}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              tickFormatter={(v) => `${currencySymbol}${(v / 1000).toFixed(0)}k`}
            />
            <RechartsTooltip
              formatter={(value: number, name: string) => {
                const label =
                  name === 'deferred'
                    ? 'Deferred Balance'
                    : `${name} Income`;
                return [formatCurrency(value, currency), label];
              }}
            />
            <Legend
              formatter={(value: string) =>
                value === 'deferred' ? 'Deferred Balance' : `${value} Income`
              }
            />
            {products.map((p) => (
              <Bar
                key={p}
                yAxisId="left"
                dataKey={p}
                stackId="income"
                fill={PRODUCT_COLORS[p] || '#9E9E9E'}
                name={p}
              />
            ))}
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="deferred"
              stroke="#d32f2f"
              strokeWidth={2}
              dot={{ r: 4 }}
              name="deferred"
            />
          </ComposedChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
};

// ──────────────────────────────────────────────────────────────────────────────
// Data table
// ──────────────────────────────────────────────────────────────────────────────

interface Schedule {
  id: number;
  invoice_number: string;
  invoice_date: string;
  client_name: string;
  memo: string;
  product: string;
  revenue_class: string;
  currency: string;
  quantity: number;
  sales_price: number | null;
  amount: number;
  service_period_start: string;
  service_period_end: string;
  duration_months: number;
  status: string;
  is_imported: boolean;
  q1_income: number;
  q1_balance: number;
  q2_income: number;
  q2_balance: number;
  q3_income: number;
  q3_balance: number;
  q4_income: number;
  q4_balance: number;
}

interface SchedulesTableProps {
  schedules: Schedule[];
  currency: string;
  onCancel: (id: number) => void;
  cancelling: number | null;
}

const cellSx = { fontSize: '0.75rem', py: 0.5, px: 1, whiteSpace: 'nowrap' as const };
const numCellSx = { ...cellSx, textAlign: 'right' as const };
const headerCellSx = { ...cellSx, fontWeight: 'bold', backgroundColor: '#263238', color: '#fff' };
const numHeaderCellSx = { ...headerCellSx, textAlign: 'right' as const };

const SchedulesTable: React.FC<SchedulesTableProps> = ({
  schedules,
  currency,
  onCancel,
  cancelling,
}) => {
  // Group by product
  const productGroups: Record<string, Schedule[]> = {};
  schedules.forEach((s) => {
    const key = s.product || 'OTHER';
    if (!productGroups[key]) productGroups[key] = [];
    productGroups[key].push(s);
  });

  const productOrder = ['SYB', 'LIM', 'SONOS', 'OTHER'];
  const sortedProducts = [
    ...productOrder.filter((p) => productGroups[p]),
    ...Object.keys(productGroups).filter((p) => !productOrder.includes(p)),
  ];

  // Grand totals
  const grandTotal = {
    amount: schedules.reduce((s, r) => s + r.amount, 0),
    q1_income: schedules.reduce((s, r) => s + r.q1_income, 0),
    q1_balance: schedules.reduce((s, r) => s + r.q1_balance, 0),
    q2_income: schedules.reduce((s, r) => s + r.q2_income, 0),
    q2_balance: schedules.reduce((s, r) => s + r.q2_balance, 0),
    q3_income: schedules.reduce((s, r) => s + r.q3_income, 0),
    q3_balance: schedules.reduce((s, r) => s + r.q3_balance, 0),
    q4_income: schedules.reduce((s, r) => s + r.q4_income, 0),
    q4_balance: schedules.reduce((s, r) => s + r.q4_balance, 0),
  };

  const fmt = (v: number) => formatCurrency(v, currency);

  const statusChip = (status: string) => {
    const color =
      status === 'active'
        ? 'success'
        : status === 'cancelled'
        ? 'error'
        : status === 'completed'
        ? 'default'
        : 'warning';
    return (
      <Chip
        label={status}
        color={color as any}
        size="small"
        sx={{ fontSize: '0.65rem', height: 18 }}
      />
    );
  };

  return (
    <TableContainer component={Paper} variant="outlined" sx={{ overflowX: 'auto' }}>
      <Table size="small" sx={{ minWidth: 1400 }}>
        <TableHead>
          <TableRow>
            <TableCell sx={headerCellSx}>Invoice #</TableCell>
            <TableCell sx={headerCellSx}>Date</TableCell>
            <TableCell sx={headerCellSx}>Client</TableCell>
            <TableCell sx={headerCellSx}>Product</TableCell>
            <TableCell sx={headerCellSx}>Class</TableCell>
            <TableCell sx={numHeaderCellSx}>Amount</TableCell>
            <TableCell sx={headerCellSx}>Start</TableCell>
            <TableCell sx={headerCellSx}>End</TableCell>
            <TableCell sx={numHeaderCellSx}>Q1 Inc</TableCell>
            <TableCell sx={numHeaderCellSx}>Q1 Bal</TableCell>
            <TableCell sx={numHeaderCellSx}>Q2 Inc</TableCell>
            <TableCell sx={numHeaderCellSx}>Q2 Bal</TableCell>
            <TableCell sx={numHeaderCellSx}>Q3 Inc</TableCell>
            <TableCell sx={numHeaderCellSx}>Q3 Bal</TableCell>
            <TableCell sx={numHeaderCellSx}>Q4 Inc</TableCell>
            <TableCell sx={numHeaderCellSx}>Q4 Bal</TableCell>
            <TableCell sx={headerCellSx}>Status</TableCell>
            <TableCell sx={headerCellSx} />
          </TableRow>
        </TableHead>
        <TableBody>
          {sortedProducts.map((product) => {
            const rows = productGroups[product];
            const productColor = PRODUCT_COLORS[product] || '#9E9E9E';

            // Product subtotals
            const subtotal = {
              amount: rows.reduce((s, r) => s + r.amount, 0),
              q1_income: rows.reduce((s, r) => s + r.q1_income, 0),
              q1_balance: rows.reduce((s, r) => s + r.q1_balance, 0),
              q2_income: rows.reduce((s, r) => s + r.q2_income, 0),
              q2_balance: rows.reduce((s, r) => s + r.q2_balance, 0),
              q3_income: rows.reduce((s, r) => s + r.q3_income, 0),
              q3_balance: rows.reduce((s, r) => s + r.q3_balance, 0),
              q4_income: rows.reduce((s, r) => s + r.q4_income, 0),
              q4_balance: rows.reduce((s, r) => s + r.q4_balance, 0),
            };

            return (
              <React.Fragment key={product}>
                {/* Product group header */}
                <TableRow sx={{ backgroundColor: `${productColor}18` }}>
                  <TableCell
                    colSpan={18}
                    sx={{
                      ...cellSx,
                      fontWeight: 'bold',
                      color: productColor,
                      borderLeft: `4px solid ${productColor}`,
                    }}
                  >
                    {product}
                  </TableCell>
                </TableRow>

                {/* Data rows */}
                {rows.map((row) => (
                  <TableRow
                    key={row.id}
                    sx={{
                      '&:hover': { backgroundColor: 'action.hover' },
                      opacity: row.status === 'cancelled' ? 0.5 : 1,
                    }}
                  >
                    <TableCell sx={cellSx}>
                      <Box display="flex" alignItems="center" gap={0.5}>
                        {row.invoice_number}
                        {row.is_imported && (
                          <Tooltip title="Imported from Excel">
                            <InfoIcon sx={{ fontSize: 12, color: 'text.secondary' }} />
                          </Tooltip>
                        )}
                      </Box>
                    </TableCell>
                    <TableCell sx={cellSx}>{formatDate(row.invoice_date)}</TableCell>
                    <TableCell sx={{ ...cellSx, maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      <Tooltip title={row.client_name}>
                        <span>{row.client_name}</span>
                      </Tooltip>
                    </TableCell>
                    <TableCell sx={cellSx}>
                      <Chip
                        label={row.product}
                        size="small"
                        sx={{
                          fontSize: '0.65rem',
                          height: 18,
                          backgroundColor: `${productColor}20`,
                          color: productColor,
                          fontWeight: 'bold',
                        }}
                      />
                    </TableCell>
                    <TableCell sx={cellSx}>{row.revenue_class}</TableCell>
                    <TableCell sx={numCellSx}>{fmt(row.amount)}</TableCell>
                    <TableCell sx={cellSx}>{formatDate(row.service_period_start)}</TableCell>
                    <TableCell sx={cellSx}>{formatDate(row.service_period_end)}</TableCell>
                    <TableCell sx={numCellSx}>{row.q1_income ? fmt(row.q1_income) : '-'}</TableCell>
                    <TableCell sx={numCellSx}>{row.q1_balance ? fmt(row.q1_balance) : '-'}</TableCell>
                    <TableCell sx={numCellSx}>{row.q2_income ? fmt(row.q2_income) : '-'}</TableCell>
                    <TableCell sx={numCellSx}>{row.q2_balance ? fmt(row.q2_balance) : '-'}</TableCell>
                    <TableCell sx={numCellSx}>{row.q3_income ? fmt(row.q3_income) : '-'}</TableCell>
                    <TableCell sx={numCellSx}>{row.q3_balance ? fmt(row.q3_balance) : '-'}</TableCell>
                    <TableCell sx={numCellSx}>{row.q4_income ? fmt(row.q4_income) : '-'}</TableCell>
                    <TableCell sx={numCellSx}>{row.q4_balance ? fmt(row.q4_balance) : '-'}</TableCell>
                    <TableCell sx={cellSx}>{statusChip(row.status)}</TableCell>
                    <TableCell sx={cellSx}>
                      {row.status === 'active' && (
                        <Tooltip title="Cancel schedule">
                          <span>
                            <IconButton
                              size="small"
                              color="error"
                              disabled={cancelling === row.id}
                              onClick={() => onCancel(row.id)}
                            >
                              {cancelling === row.id ? (
                                <CircularProgress size={14} />
                              ) : (
                                <CancelIcon sx={{ fontSize: 16 }} />
                              )}
                            </IconButton>
                          </span>
                        </Tooltip>
                      )}
                    </TableCell>
                  </TableRow>
                ))}

                {/* Product subtotal row */}
                <TableRow sx={{ backgroundColor: `${productColor}10` }}>
                  <TableCell
                    colSpan={5}
                    sx={{
                      ...cellSx,
                      fontWeight: 'bold',
                      color: productColor,
                      pl: 2,
                    }}
                  >
                    {product} Total ({rows.length} schedules)
                  </TableCell>
                  <TableCell sx={{ ...numCellSx, fontWeight: 'bold', color: productColor }}>
                    {fmt(subtotal.amount)}
                  </TableCell>
                  <TableCell colSpan={2} />
                  <TableCell sx={{ ...numCellSx, fontWeight: 'bold' }}>{fmt(subtotal.q1_income)}</TableCell>
                  <TableCell sx={{ ...numCellSx, fontWeight: 'bold' }}>{fmt(subtotal.q1_balance)}</TableCell>
                  <TableCell sx={{ ...numCellSx, fontWeight: 'bold' }}>{fmt(subtotal.q2_income)}</TableCell>
                  <TableCell sx={{ ...numCellSx, fontWeight: 'bold' }}>{fmt(subtotal.q2_balance)}</TableCell>
                  <TableCell sx={{ ...numCellSx, fontWeight: 'bold' }}>{fmt(subtotal.q3_income)}</TableCell>
                  <TableCell sx={{ ...numCellSx, fontWeight: 'bold' }}>{fmt(subtotal.q3_balance)}</TableCell>
                  <TableCell sx={{ ...numCellSx, fontWeight: 'bold' }}>{fmt(subtotal.q4_income)}</TableCell>
                  <TableCell sx={{ ...numCellSx, fontWeight: 'bold' }}>{fmt(subtotal.q4_balance)}</TableCell>
                  <TableCell colSpan={2} />
                </TableRow>
              </React.Fragment>
            );
          })}

          {/* Grand total row */}
          {schedules.length > 0 && (
            <TableRow sx={{ backgroundColor: '#263238' }}>
              <TableCell
                colSpan={5}
                sx={{ ...cellSx, fontWeight: 'bold', color: '#fff', fontSize: '0.8rem' }}
              >
                GRAND TOTAL ({schedules.length} schedules)
              </TableCell>
              <TableCell
                sx={{ ...numCellSx, fontWeight: 'bold', color: '#FFD54F', fontSize: '0.8rem' }}
              >
                {fmt(grandTotal.amount)}
              </TableCell>
              <TableCell colSpan={2} sx={{ backgroundColor: '#263238' }} />
              {QUARTERS.map((q) => (
                <React.Fragment key={q}>
                  <TableCell
                    sx={{ ...numCellSx, fontWeight: 'bold', color: '#81C784', fontSize: '0.8rem' }}
                  >
                    {fmt(grandTotal[`${q.toLowerCase()}_income` as keyof typeof grandTotal] as number)}
                  </TableCell>
                  <TableCell
                    sx={{ ...numCellSx, fontWeight: 'bold', color: '#EF9A9A', fontSize: '0.8rem' }}
                  >
                    {fmt(grandTotal[`${q.toLowerCase()}_balance` as keyof typeof grandTotal] as number)}
                  </TableCell>
                </React.Fragment>
              ))}
              <TableCell colSpan={2} sx={{ backgroundColor: '#263238' }} />
            </TableRow>
          )}

          {schedules.length === 0 && (
            <TableRow>
              <TableCell colSpan={18} align="center" sx={{ py: 4, fontStyle: 'italic', color: 'text.secondary' }}>
                No schedules found for the selected filters.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </TableContainer>
  );
};

// ──────────────────────────────────────────────────────────────────────────────
// Import Dialog
// ──────────────────────────────────────────────────────────────────────────────

interface ImportDialogProps {
  open: boolean;
  onClose: () => void;
  onImported: () => void;
}

const ImportDialog: React.FC<ImportDialogProps> = ({ open, onClose, onImported }) => {
  const [file, setFile] = useState<File | null>(null);
  const [importEntity, setImportEntity] = useState<string>('bmasia_th');
  const [importCurrency, setImportCurrency] = useState<string>('THB');
  const [clearExisting, setClearExisting] = useState<boolean>(true);
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleEntityChange = (entity: string) => {
    setImportEntity(entity);
    setImportCurrency(ENTITY_CURRENCY[entity] || 'THB');
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] || null;
    setFile(f);
    setResult(null);
    setImportError(null);
  };

  const handleImport = async () => {
    if (!file) return;
    setImporting(true);
    setImportError(null);
    setResult(null);
    try {
      const data = await apiService.importRevenueRecognition(file, importEntity, importCurrency, clearExisting);
      setResult(data);
    } catch (err: any) {
      const msg =
        err?.response?.data?.error ||
        err?.response?.data?.detail ||
        err?.message ||
        'Import failed';
      setImportError(msg);
    } finally {
      setImporting(false);
    }
  };

  const handleClose = () => {
    if (result) onImported();
    setFile(null);
    setResult(null);
    setImportError(null);
    onClose();
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>Import Revenue Recognition from Excel</DialogTitle>
      <DialogContent>
        <Stack spacing={2} mt={1}>
          <FormControl size="small" fullWidth>
            <InputLabel>Billing Entity</InputLabel>
            <Select
              value={importEntity}
              label="Billing Entity"
              onChange={(e) => handleEntityChange(e.target.value)}
            >
              <MenuItem value="bmasia_th">BMAsia Thailand (THB)</MenuItem>
              <MenuItem value="bmasia_hk">BMAsia HK (USD)</MenuItem>
            </Select>
          </FormControl>

          <FormControl size="small" fullWidth>
            <InputLabel>Currency</InputLabel>
            <Select
              value={importCurrency}
              label="Currency"
              onChange={(e) => setImportCurrency(e.target.value)}
            >
              <MenuItem value="THB">THB</MenuItem>
              <MenuItem value="USD">USD</MenuItem>
            </Select>
          </FormControl>

          <FormControlLabel
            control={
              <Checkbox
                checked={clearExisting}
                onChange={(e) => setClearExisting(e.target.checked)}
                size="small"
              />
            }
            label={
              <Typography variant="body2">
                Clear existing schedules for this entity before importing
              </Typography>
            }
          />

          <Box>
            <input
              ref={fileInputRef}
              type="file"
              accept=".xlsx,.xls,.csv"
              onChange={handleFileChange}
              style={{ display: 'none' }}
            />
            <Button
              variant="outlined"
              startIcon={<UploadIcon />}
              onClick={() => fileInputRef.current?.click()}
              size="small"
              fullWidth
            >
              {file ? file.name : 'Choose Excel / CSV File'}
            </Button>
            {file && (
              <Typography variant="caption" color="text.secondary" display="block" mt={0.5}>
                Selected: {file.name} ({(file.size / 1024).toFixed(1)} KB)
              </Typography>
            )}
          </Box>

          {importError && (
            <Alert severity="error" onClose={() => setImportError(null)}>
              {importError}
            </Alert>
          )}

          {result && (
            <Alert severity="success" icon={<CheckCircleIcon />}>
              <Typography variant="body2" fontWeight="bold">
                Import complete
              </Typography>
              {result.cleared !== undefined && result.cleared > 0 && (
                <Typography variant="body2">
                  Cleared: {result.cleared} existing schedules
                </Typography>
              )}
              <Typography variant="body2">
                Created: {result.created} | Skipped: {result.skipped} | Errors: {result.errors}
              </Typography>
              {result.entries_created !== undefined && (
                <Typography variant="body2">
                  Recognition entries: {result.entries_created}
                </Typography>
              )}
              {result.total_amount !== undefined && (
                <Typography variant="body2">
                  Total amount: {formatCurrency(result.total_amount, importCurrency)}
                </Typography>
              )}
              {result.error_details && result.error_details.length > 0 && (
                <Box mt={1}>
                  <Typography variant="caption" color="error">
                    Errors:
                  </Typography>
                  {result.error_details.slice(0, 5).map((e: string, i: number) => (
                    <Typography key={i} variant="caption" display="block" color="error">
                      {e}
                    </Typography>
                  ))}
                </Box>
              )}
            </Alert>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} disabled={importing}>
          {result ? 'Close & Refresh' : 'Cancel'}
        </Button>
        <Button
          variant="contained"
          onClick={handleImport}
          disabled={!file || importing || !!result}
          startIcon={importing ? <CircularProgress size={16} /> : <UploadIcon />}
        >
          {importing ? 'Importing...' : 'Import'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

// ──────────────────────────────────────────────────────────────────────────────
// Main Component
// ──────────────────────────────────────────────────────────────────────────────

const RevenueAccrual: React.FC = () => {
  const [summary, setSummary] = useState<any>(null);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  // Filters
  const [year, setYear] = useState<number>(new Date().getFullYear());
  const [billingEntity, setBillingEntity] = useState<string>('bmasia_th');
  const [product, setProduct] = useState<string>('');

  // Actions
  const [exporting, setExporting] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [cancelling, setCancelling] = useState<number | null>(null);
  const [importOpen, setImportOpen] = useState(false);

  const years = Array.from({ length: 5 }, (_, i) => new Date().getFullYear() - i);
  const displayCurrency = ENTITY_CURRENCY[billingEntity] || 'THB';

  // ── Load data ──────────────────────────────────────────────────────────────

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [year, billingEntity, product]);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: any = { year, billing_entity: billingEntity };
      if (product) params.product = product;

      // Fetch summary first (fast, always works)
      const summaryData = await apiService.getRevenueRecognitionSummary(params);
      setSummary(summaryData);

      // Fetch schedules independently — don't block summary on failure
      try {
        const schedulesData = await apiService.getRevenueRecognitionSchedules(params);
        setSchedules(Array.isArray(schedulesData) ? schedulesData : schedulesData.results || []);
      } catch (schedErr: any) {
        console.warn('Schedules load failed (summary still available):', schedErr?.message);
        setSchedules([]);
      }
    } catch (err: any) {
      const msg =
        err?.response?.data?.error ||
        err?.response?.data?.detail ||
        err?.message ||
        'Failed to load revenue accrual data';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  // ── Build chart data from summary ─────────────────────────────────────────

  const chartData: ChartDataPoint[] = QUARTERS.map((q) => {
    const qKey = q as 'Q1' | 'Q2' | 'Q3' | 'Q4';
    const byProduct = summary?.by_product || {};

    const point: ChartDataPoint = {
      quarter: q,
      SYB: byProduct.SYB?.[qKey]?.income ?? 0,
      LIM: byProduct.LIM?.[qKey]?.income ?? 0,
      SONOS: byProduct.SONOS?.[qKey]?.income ?? 0,
      OTHER: byProduct.OTHER?.[qKey]?.income ?? 0,
      deferred: summary?.quarterly?.[qKey]?.balance ?? 0,
    };
    return point;
  });

  // ── Action handlers ────────────────────────────────────────────────────────

  const handleExportExcel = async () => {
    setExporting(true);
    setError(null);
    try {
      const blob = await apiService.exportRevenueAccrualExcel(year, billingEntity);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `RevenueAccrual_${billingEntity}_${year}.xlsx`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      setError('Failed to export Excel. Please try again.');
    } finally {
      setExporting(false);
    }
  };

  const handleRegenerate = async () => {
    if (
      !window.confirm(
        `Regenerate all revenue recognition schedules for ${billingEntity} — ${year}?\n\nThis will delete and rebuild all existing schedules for this entity and year.`
      )
    )
      return;

    setRegenerating(true);
    setError(null);
    setActionMessage(null);
    try {
      const result = await apiService.regenerateRevenueRecognition(year, billingEntity);
      setActionMessage(
        result?.message ||
          `Regenerated successfully. ${result?.created ?? ''} schedules created.`
      );
      await loadData();
    } catch (err: any) {
      const msg =
        err?.response?.data?.error ||
        err?.response?.data?.detail ||
        err?.message ||
        'Regeneration failed';
      setError(msg);
    } finally {
      setRegenerating(false);
    }
  };

  const handleCancel = async (id: number) => {
    if (!window.confirm('Cancel this revenue recognition schedule? This cannot be undone.')) return;
    setCancelling(id);
    setError(null);
    try {
      await apiService.cancelRevenueSchedule(id);
      setSchedules((prev) =>
        prev.map((s) => (s.id === id ? { ...s, status: 'cancelled' } : s))
      );
      setActionMessage('Schedule cancelled successfully.');
    } catch (err: any) {
      setError('Failed to cancel schedule.');
    } finally {
      setCancelling(null);
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────

  if (loading && !summary) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={3} flexWrap="wrap" gap={2}>
        <Box>
          <Typography variant="h4" fontWeight="bold">
            Revenue Accrual / Recognition
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Deferred revenue schedules and quarterly income recognition by product
          </Typography>
        </Box>

        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
          {/* Action buttons */}
          <Button
            variant="outlined"
            size="small"
            startIcon={<UploadIcon />}
            onClick={() => setImportOpen(true)}
            disabled={loading}
          >
            Import Excel
          </Button>
          <Button
            variant="outlined"
            size="small"
            startIcon={exporting ? <CircularProgress size={16} /> : <ExcelIcon />}
            onClick={handleExportExcel}
            disabled={exporting || loading}
          >
            Export Excel
          </Button>
          <Button
            variant="outlined"
            size="small"
            color="warning"
            startIcon={regenerating ? <CircularProgress size={16} /> : <RefreshIcon />}
            onClick={handleRegenerate}
            disabled={regenerating || loading}
          >
            Regenerate
          </Button>

          {/* Filters */}
          <FormControl size="small" sx={{ minWidth: 100 }}>
            <InputLabel>Year</InputLabel>
            <Select
              value={year}
              label="Year"
              onChange={(e) => setYear(e.target.value as number)}
            >
              {years.map((y) => (
                <MenuItem key={y} value={y}>
                  {y}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel>Entity</InputLabel>
            <Select
              value={billingEntity}
              label="Entity"
              onChange={(e) => setBillingEntity(e.target.value)}
            >
              <MenuItem value="bmasia_th">BMAsia Thailand</MenuItem>
              <MenuItem value="bmasia_hk">BMAsia HK</MenuItem>
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 110 }}>
            <InputLabel>Product</InputLabel>
            <Select
              value={product}
              label="Product"
              onChange={(e) => setProduct(e.target.value)}
            >
              <MenuItem value="">All</MenuItem>
              <MenuItem value="SYB">SYB</MenuItem>
              <MenuItem value="LIM">LIM</MenuItem>
              <MenuItem value="SONOS">SONOS</MenuItem>
            </Select>
          </FormControl>
        </Stack>
      </Box>

      {/* Progress / messages */}
      {loading && <LinearProgress sx={{ mb: 2 }} />}

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {actionMessage && (
        <Alert severity="success" sx={{ mb: 2 }} onClose={() => setActionMessage(null)}>
          {actionMessage}
        </Alert>
      )}

      {/* Regeneration hint when data exists but no recognition */}
      {summary && summary.schedule_count > 0 && summary.recognition_pct === 0 && (
        <Alert
          severity="info"
          sx={{ mb: 2 }}
          action={
            <Button
              color="inherit"
              size="small"
              onClick={handleRegenerate}
              disabled={regenerating}
              startIcon={regenerating ? <CircularProgress size={14} /> : <RefreshIcon />}
            >
              Regenerate Now
            </Button>
          }
        >
          {summary.schedule_count} schedules imported but no recognition entries calculated yet.
          Click <strong>Regenerate</strong> to compute quarterly income from schedule dates.
        </Alert>
      )}

      {/* KPI Cards */}
      {summary && (
        <Grid container spacing={3} sx={{ mb: 3 }}>
          <Grid item xs={12} sm={6} md={3}>
            <KPICard
              title="Total Invoice Amount"
              value={formatCurrency(summary.total_invoice_amount ?? 0, displayCurrency)}
              subtitle={`${summary.schedule_count ?? 0} schedules — ${year}`}
              icon={<AccountBalanceIcon />}
              color="#1976d2"
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <KPICard
              title="Total Recognized YTD"
              value={formatCurrency(summary.total_recognized_ytd ?? 0, displayCurrency)}
              subtitle={`${formatPercent(summary.recognition_pct ?? 0)} recognized`}
              icon={<TrendingUpIcon />}
              color="#4caf50"
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <KPICard
              title="Total Deferred (Advance Received)"
              value={formatCurrency(summary.total_deferred ?? 0, displayCurrency)}
              subtitle="Remaining balance to recognize"
              icon={<SavingsIcon />}
              color="#e65100"
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <KPICard
              title="Recognition %"
              value={formatPercent(summary.recognition_pct ?? 0)}
              subtitle={`${displayCurrency} — ${billingEntity === 'bmasia_th' ? 'Thailand' : 'Hong Kong'}`}
              icon={<SpeedIcon />}
              color="#7b1fa2"
            />
          </Grid>
        </Grid>
      )}

      {/* Chart */}
      {summary && (
        <Box mb={3}>
          <RecognitionChart data={chartData} currency={displayCurrency} product={product} />
        </Box>
      )}

      {/* Quarterly Summary by Product (compact) */}
      {summary?.by_product && Object.keys(summary.by_product).length > 0 && (
        <Box mb={3}>
          <Card variant="outlined">
            <CardContent sx={{ pb: '12px !important' }}>
              <Typography variant="h6" fontWeight="bold" gutterBottom>
                Quarterly Summary by Product — {year}
              </Typography>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow sx={{ backgroundColor: 'grey.100' }}>
                      <TableCell sx={headerCellSx}>Product</TableCell>
                      {QUARTERS.map((q) => (
                        <React.Fragment key={q}>
                          <TableCell sx={numHeaderCellSx}>{q} Income</TableCell>
                          <TableCell sx={numHeaderCellSx}>{q} Balance</TableCell>
                        </React.Fragment>
                      ))}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {Object.entries(summary.by_product).map(([prod, qData]: [string, any]) => {
                      const color = PRODUCT_COLORS[prod] || '#9E9E9E';
                      return (
                        <TableRow key={prod}>
                          <TableCell sx={cellSx}>
                            <Chip
                              label={prod}
                              size="small"
                              sx={{
                                fontSize: '0.7rem',
                                height: 20,
                                backgroundColor: `${color}20`,
                                color,
                                fontWeight: 'bold',
                              }}
                            />
                          </TableCell>
                          {QUARTERS.map((q) => (
                            <React.Fragment key={q}>
                              <TableCell sx={numCellSx}>
                                {formatCurrency(qData[q]?.income ?? 0, displayCurrency)}
                              </TableCell>
                              <TableCell sx={{ ...numCellSx, color: '#c62828' }}>
                                {formatCurrency(qData[q]?.balance ?? 0, displayCurrency)}
                              </TableCell>
                            </React.Fragment>
                          ))}
                        </TableRow>
                      );
                    })}

                    {/* Summary totals row */}
                    <TableRow sx={{ backgroundColor: '#f5f5f5', borderTop: '2px solid #bdbdbd' }}>
                      <TableCell sx={{ ...cellSx, fontWeight: 'bold' }}>TOTAL</TableCell>
                      {QUARTERS.map((q) => {
                        const qKey = q as 'Q1' | 'Q2' | 'Q3' | 'Q4';
                        return (
                          <React.Fragment key={q}>
                            <TableCell sx={{ ...numCellSx, fontWeight: 'bold', color: '#2e7d32' }}>
                              {formatCurrency(summary.quarterly?.[qKey]?.income ?? 0, displayCurrency)}
                            </TableCell>
                            <TableCell sx={{ ...numCellSx, fontWeight: 'bold', color: '#c62828' }}>
                              {formatCurrency(summary.quarterly?.[qKey]?.balance ?? 0, displayCurrency)}
                            </TableCell>
                          </React.Fragment>
                        );
                      })}
                    </TableRow>
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </Card>
        </Box>
      )}

      {/* Detailed Schedules Table */}
      <Box mb={3}>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
          <Typography variant="h6" fontWeight="bold">
            Recognition Schedules
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {schedules.length} schedules
          </Typography>
        </Box>
        <SchedulesTable
          schedules={schedules}
          currency={displayCurrency}
          onCancel={handleCancel}
          cancelling={cancelling}
        />
      </Box>

      {/* Footer info */}
      <Box mt={2}>
        <Typography variant="caption" color="text.secondary">
          Entity: {billingEntity === 'bmasia_th' ? 'BMAsia (Thailand) Co., Ltd.' : 'BMAsia Limited'} |
          Currency: {displayCurrency} |
          Year: {year} |
          {product ? ` Product: ${product} |` : ''}
          {' '}Schedules: {schedules.length}
          {summary ? ` | Recognition: ${formatPercent(summary.recognition_pct ?? 0)}` : ''}
        </Typography>
      </Box>

      {/* Import Dialog */}
      <ImportDialog
        open={importOpen}
        onClose={() => setImportOpen(false)}
        onImported={() => {
          setImportOpen(false);
          loadData();
        }}
      />
    </Box>
  );
};

export default RevenueAccrual;
