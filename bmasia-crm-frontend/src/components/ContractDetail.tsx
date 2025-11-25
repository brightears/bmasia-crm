import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Paper,
  Chip,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  IconButton,
  GridLegacy as Grid,
  Alert,
  CircularProgress,
  Card,
  CardContent,
  LinearProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material';
import {
  Timeline,
  TimelineItem,
  TimelineSeparator,
  TimelineConnector,
  TimelineContent,
  TimelineDot,
} from '@mui/lab';
import {
  Close,
  Business,
  CalendarToday,
  AttachMoney,
  Description,
  Edit,
  Refresh,
  Receipt,
  CheckCircle,
  Warning,
  Info,
  Assignment,
  Email,
  GetApp,
  Print,
  LocationOn as LocationOnIcon,
} from '@mui/icons-material';
import { Contract, Invoice, ContractZone } from '../types';
import ApiService from '../services/api';

interface ContractDetailProps {
  open: boolean;
  onClose: () => void;
  onEdit: (contract: Contract) => void;
  contractId: string | null;
}

interface PaymentHistory {
  id: string;
  date: string;
  amount: number;
  status: string;
  method: string;
  reference: string;
}

interface ContractEvent {
  id: string;
  date: string;
  type: string;
  description: string;
  user: string;
}

const ContractDetail: React.FC<ContractDetailProps> = ({
  open,
  onClose,
  onEdit,
  contractId,
}) => {
  const [contract, setContract] = useState<Contract | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [paymentHistory] = useState<PaymentHistory[]>([]);
  const [contractEvents] = useState<ContractEvent[]>([]);
  const [sendingRenewal, setSendingRenewal] = useState(false);
  const [contractZones, setContractZones] = useState<ContractZone[]>([]);
  const [loadingZones, setLoadingZones] = useState(false);

  useEffect(() => {
    if (open && contractId) {
      loadContractDetails();
    }
  }, [open, contractId]);

  const loadContractDetails = async () => {
    if (!contractId) return;

    try {
      setLoading(true);
      setError('');

      const [contractData, invoicesData] = await Promise.all([
        ApiService.getContract(contractId),
        ApiService.getInvoices({ contract: contractId }),
      ]);

      setContract(contractData);
      setInvoices(invoicesData.results);
    } catch (err: any) {
      setError('Failed to load contract details');
      console.error('Contract detail error:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadContractZones = async () => {
    if (!contract?.id) return;

    try {
      setLoadingZones(true);
      const zones = await ApiService.getContractZones(contract.id);
      setContractZones(zones);
    } catch (err) {
      console.error('Failed to load contract zones:', err);
    } finally {
      setLoadingZones(false);
    }
  };

  useEffect(() => {
    if (contract) {
      loadContractZones();
    }
  }, [contract]);

  const handleSendRenewalNotice = async () => {
    if (!contract) return;

    try {
      setSendingRenewal(true);
      await ApiService.sendRenewalNotice(contract.id);
      // Reload contract to get updated renewal notice status
      const updatedContract = await ApiService.getContract(contract.id);
      setContract(updatedContract);
    } catch (err) {
      console.error('Failed to send renewal notice:', err);
    } finally {
      setSendingRenewal(false);
    }
  };

  const formatCurrency = (value: number, currency = 'USD'): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  const formatDate = (dateString: string | null | undefined): string => {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleDateString();
  };

  const getStatusColor = (status: string): 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning' => {
    switch (status?.toLowerCase()) {
      case 'active': return 'success';
      case 'signed': return 'success';
      case 'expired': return 'error';
      case 'terminated': return 'error';
      case 'draft': return 'default';
      case 'sent': return 'info';
      case 'renewed': return 'success';
      default: return 'default';
    }
  };

  const getInvoiceStatusColor = (status: string): 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning' => {
    switch (status?.toLowerCase()) {
      case 'paid': return 'success';
      case 'overdue': return 'error';
      case 'sent': return 'info';
      case 'draft': return 'default';
      case 'cancelled': return 'error';
      case 'refunded': return 'warning';
      default: return 'default';
    }
  };

  const getTimelineIcon = (type: string) => {
    switch (type) {
      case 'created': return <Assignment />;
      case 'signed': return <CheckCircle />;
      case 'renewed': return <Refresh />;
      case 'terminated': return <Warning />;
      case 'invoice': return <Receipt />;
      default: return <Info />;
    }
  };

  const calculateContractProgress = () => {
    if (!contract || !contract.start_date || !contract.end_date) return 0;

    const now = new Date();
    const start = new Date(contract.start_date);
    const end = new Date(contract.end_date);

    if (now < start) return 0;
    if (now > end) return 100;

    const total = end.getTime() - start.getTime();
    const elapsed = now.getTime() - start.getTime();
    return Math.round((elapsed / total) * 100);
  };

  if (!open || !contractId) return null;

  if (loading) {
    return (
      <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
        <DialogContent sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </DialogContent>
      </Dialog>
    );
  }

  if (error || !contract) {
    return (
      <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
        <DialogContent>
          <Alert severity="error">{error || 'Contract not found'}</Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>Close</Button>
        </DialogActions>
      </Dialog>
    );
  }

  const progress = calculateContractProgress();

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="lg"
      fullWidth
      scroll="paper"
    >
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Box>
            <Typography variant="h6">
              Contract Details
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {contract.contract_number}
            </Typography>
          </Box>
          <IconButton onClick={onClose}>
            <Close />
          </IconButton>
        </Box>
      </DialogTitle>

      <DialogContent dividers>
        <Grid container spacing={3}>
          {/* Contract Overview */}
          <Grid item xs={12}>
            <Paper sx={{ p: 3, mb: 3 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                <Box>
                  <Typography variant="h5" gutterBottom>
                    {contract.company_name}
                  </Typography>
                  <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
                    <Chip
                      label={contract.status}
                      color={getStatusColor(contract.status)}
                      size="medium"
                    />
                    <Chip
                      label={contract.contract_type}
                      variant="outlined"
                      size="medium"
                    />
                    {contract.auto_renew && (
                      <Chip
                        label="Auto-Renew"
                        color="info"
                        variant="outlined"
                        size="medium"
                      />
                    )}
                  </Box>
                </Box>
                <Box sx={{ textAlign: 'right' }}>
                  <Typography variant="h4" color="primary">
                    {formatCurrency(contract.value, contract.currency)}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Total Contract Value
                  </Typography>
                </Box>
              </Box>

              {/* Contract Progress */}
              {contract.status === 'Active' && (
                <Box sx={{ mb: 2 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography variant="body2" color="text.secondary">
                      Contract Progress
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {progress}% Complete
                    </Typography>
                  </Box>
                  <LinearProgress
                    variant="determinate"
                    value={progress}
                    sx={{
                      height: 8,
                      borderRadius: 4,
                      backgroundColor: 'grey.200',
                    }}
                  />
                </Box>
              )}

              {/* Key Information */}
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6} md={3}>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                    <CalendarToday sx={{ mr: 1, color: 'text.secondary', fontSize: 20 }} />
                    <Typography variant="body2" color="text.secondary">
                      Start Date
                    </Typography>
                  </Box>
                  <Typography variant="body1" fontWeight="medium">
                    {formatDate(contract.start_date)}
                  </Typography>
                </Grid>

                <Grid item xs={12} sm={6} md={3}>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                    <CalendarToday sx={{ mr: 1, color: 'text.secondary', fontSize: 20 }} />
                    <Typography variant="body2" color="text.secondary">
                      End Date
                    </Typography>
                  </Box>
                  <Typography variant="body1" fontWeight="medium">
                    {formatDate(contract.end_date)}
                  </Typography>
                </Grid>

                <Grid item xs={12} sm={6} md={3}>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                    <AttachMoney sx={{ mr: 1, color: 'text.secondary', fontSize: 20 }} />
                    <Typography variant="body2" color="text.secondary">
                      Monthly Value
                    </Typography>
                  </Box>
                  <Typography variant="body1" fontWeight="medium">
                    {formatCurrency(contract.monthly_value, contract.currency)}
                  </Typography>
                </Grid>

                <Grid item xs={12} sm={6} md={3}>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                    <Warning sx={{
                      mr: 1,
                      fontSize: 20,
                      color: contract.is_expiring_soon ? 'warning.main' : 'text.secondary'
                    }} />
                    <Typography variant="body2" color="text.secondary">
                      Days Until Expiry
                    </Typography>
                  </Box>
                  <Typography
                    variant="body1"
                    fontWeight="medium"
                    color={contract.is_expiring_soon ? 'warning.main' : 'inherit'}
                  >
                    {contract.days_until_expiry} days
                  </Typography>
                </Grid>
              </Grid>

              {contract.is_expiring_soon && (
                <Alert severity="warning" sx={{ mt: 2 }}>
                  This contract expires in {contract.days_until_expiry} days.
                  {!contract.renewal_notice_sent && (
                    <Box sx={{ mt: 1 }}>
                      <Button
                        size="small"
                        variant="contained"
                        color="warning"
                        onClick={handleSendRenewalNotice}
                        disabled={sendingRenewal}
                        startIcon={sendingRenewal ? <CircularProgress size={16} /> : <Email />}
                      >
                        {sendingRenewal ? 'Sending...' : 'Send Renewal Notice'}
                      </Button>
                    </Box>
                  )}
                </Alert>
              )}
            </Paper>
          </Grid>

          {/* Financial Details */}
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Financial Details
              </Typography>

              <List dense>
                <ListItem>
                  <ListItemText
                    primary="Payment Terms"
                    secondary={contract.payment_terms || 'Net 30'}
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary="Billing Frequency"
                    secondary={contract.billing_frequency}
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary="Discount Applied"
                    secondary={`${contract.discount_percentage}%`}
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary="Outstanding Amount"
                    secondary={formatCurrency(contract.outstanding_amount, contract.currency)}
                  />
                </ListItem>
                {contract.auto_renew && (
                  <ListItem>
                    <ListItemText
                      primary="Renewal Period"
                      secondary={`${contract.renewal_period_months} months`}
                    />
                  </ListItem>
                )}
              </List>
            </Paper>
          </Grid>

          {/* Contract Timeline */}
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Contract Timeline
              </Typography>

              <Timeline sx={{ p: 0 }}>
                <TimelineItem>
                  <TimelineSeparator>
                    <TimelineDot color="primary">
                      <Assignment />
                    </TimelineDot>
                    <TimelineConnector />
                  </TimelineSeparator>
                  <TimelineContent>
                    <Typography variant="body2" fontWeight="medium">
                      Contract Created
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {formatDate(contract.created_at)}
                    </Typography>
                  </TimelineContent>
                </TimelineItem>

                {contract.status === 'Signed' && (
                  <TimelineItem>
                    <TimelineSeparator>
                      <TimelineDot color="success">
                        <CheckCircle />
                      </TimelineDot>
                      <TimelineConnector />
                    </TimelineSeparator>
                    <TimelineContent>
                      <Typography variant="body2" fontWeight="medium">
                        Contract Signed
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {formatDate(contract.start_date)}
                      </Typography>
                    </TimelineContent>
                  </TimelineItem>
                )}

                {contract.renewal_notice_sent && (
                  <TimelineItem>
                    <TimelineSeparator>
                      <TimelineDot color="warning">
                        <Email />
                      </TimelineDot>
                      <TimelineConnector />
                    </TimelineSeparator>
                    <TimelineContent>
                      <Typography variant="body2" fontWeight="medium">
                        Renewal Notice Sent
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {formatDate(contract.renewal_notice_date)}
                      </Typography>
                    </TimelineContent>
                  </TimelineItem>
                )}

                <TimelineItem>
                  <TimelineSeparator>
                    <TimelineDot color={contract.status === 'Expired' ? 'error' : 'grey'}>
                      <Warning />
                    </TimelineDot>
                  </TimelineSeparator>
                  <TimelineContent>
                    <Typography variant="body2" fontWeight="medium">
                      Contract {contract.status === 'Expired' ? 'Expired' : 'Expires'}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {formatDate(contract.end_date)}
                    </Typography>
                  </TimelineContent>
                </TimelineItem>
              </Timeline>
            </Paper>
          </Grid>

          {/* Invoices */}
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Related Invoices ({invoices.length})
              </Typography>

              {invoices.length > 0 ? (
                <TableContainer>
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableCell>Invoice Number</TableCell>
                        <TableCell>Issue Date</TableCell>
                        <TableCell>Due Date</TableCell>
                        <TableCell>Amount</TableCell>
                        <TableCell>Status</TableCell>
                        <TableCell>Actions</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {invoices.map((invoice) => (
                        <TableRow key={invoice.id} hover>
                          <TableCell>
                            <Typography variant="body2" fontWeight="medium">
                              {invoice.invoice_number}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            {formatDate(invoice.issue_date)}
                          </TableCell>
                          <TableCell>
                            <Typography
                              variant="body2"
                              color={invoice.is_overdue ? 'error.main' : 'inherit'}
                            >
                              {formatDate(invoice.due_date)}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            {formatCurrency(invoice.total_amount, invoice.currency)}
                          </TableCell>
                          <TableCell>
                            <Chip
                              label={invoice.status}
                              color={getInvoiceStatusColor(invoice.status)}
                              size="small"
                            />
                          </TableCell>
                          <TableCell>
                            <IconButton size="small" title="Download">
                              <GetApp />
                            </IconButton>
                            <IconButton size="small" title="Print">
                              <Print />
                            </IconButton>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  No invoices generated for this contract yet.
                </Typography>
              )}
            </Paper>
          </Grid>

          {/* Notes */}
          {contract.notes && (
            <Grid item xs={12}>
              <Paper sx={{ p: 3 }}>
                <Typography variant="h6" gutterBottom>
                  Contract Notes
                </Typography>
                <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                  {contract.notes}
                </Typography>
              </Paper>
            </Grid>
          )}

          {/* Music Zones */}
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
                <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <LocationOnIcon sx={{ color: '#FFA500' }} />
                  Music Zones
                </Typography>
                <Chip
                  label={`${contract.active_zone_count || 0} active`}
                  color="success"
                  size="small"
                />
              </Box>

              {loadingZones ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
                  <CircularProgress />
                </Box>
              ) : contractZones.length === 0 ? (
                <Paper sx={{ p: 3, textAlign: 'center', bgcolor: 'grey.50' }}>
                  <LocationOnIcon sx={{ fontSize: 60, color: 'text.secondary', mb: 2 }} />
                  <Typography variant="body1" color="text.secondary">
                    No zones configured for this contract
                  </Typography>
                </Paper>
              ) : (
                <Grid container spacing={2}>
                  {contractZones.map((cz) => (
                    <Grid item xs={12} sm={6} md={4} key={cz.id}>
                      <Card variant="outlined">
                        <CardContent>
                          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', mb: 2 }}>
                            <Typography variant="h6" sx={{ fontSize: '1rem' }}>
                              {cz.zone_name}
                            </Typography>
                            <Chip
                              label={cz.is_active ? 'Active' : 'Ended'}
                              size="small"
                              color={cz.is_active ? 'success' : 'default'}
                            />
                          </Box>
                          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                            Platform: {cz.zone_platform === 'soundtrack' ? 'Soundtrack Your Brand' : 'Beat Breeze'}
                          </Typography>
                          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                            Status: {cz.zone_status}
                          </Typography>
                          <Typography variant="caption" color="text.secondary" display="block">
                            Active: {formatDate(cz.start_date)}
                            {cz.end_date && ` - ${formatDate(cz.end_date)}`}
                          </Typography>
                        </CardContent>
                      </Card>
                    </Grid>
                  ))}
                </Grid>
              )}
            </Paper>
          </Grid>
        </Grid>
      </DialogContent>

      <DialogActions>
        <Button
          variant="outlined"
          startIcon={<Receipt />}
          onClick={() => {
            // Generate invoice functionality
            console.log('Generate invoice for contract:', contract.id);
          }}
        >
          Generate Invoice
        </Button>
        <Button
          variant="contained"
          startIcon={<Edit />}
          onClick={() => onEdit(contract)}
        >
          Edit Contract
        </Button>
        <Button onClick={onClose}>
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default ContractDetail;