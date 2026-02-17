import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Divider,
  Alert,
  CircularProgress,
  GridLegacy as Grid,
  IconButton,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Tooltip,
  Card,
  CardContent,
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
  Edit,
  GetApp,
  Send,
  CheckCircle,
  Cancel,
  Assignment,
  Business,
  Person,
  Schedule,
  AttachMoney,
  Percent,
  AttachFile,
  Print,
  Email,
  FileCopy,
  TrendingUp,
  Description,
  Close,
  Receipt,
  Visibility,
} from '@mui/icons-material';
import { Quote, QuoteActivity } from '../types';
import ApiService from '../services/api';

interface QuoteDetailProps {
  open: boolean;
  onClose: () => void;
  quote?: Quote | null;
  onQuoteUpdate: () => void;
}

const QuoteDetail: React.FC<QuoteDetailProps> = ({
  open,
  onClose,
  quote,
  onQuoteUpdate
}) => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [quoteDetail, setQuoteDetail] = useState<Quote | null>(null);
  const [activities, setActivities] = useState<QuoteActivity[]>([]);

  useEffect(() => {
    if (open && quote) {
      loadQuoteDetail();
    }
  }, [open, quote]);

  const loadQuoteDetail = async () => {
    if (!quote) return;

    try {
      setLoading(true);
      const detail = await ApiService.getQuote(quote.id);
      setQuoteDetail(detail);
      setActivities(detail.activities || []);
    } catch (err) {
      setError('Failed to load quote details');
    } finally {
      setLoading(false);
    }
  };

  const handleSendQuote = async () => {
    if (!quoteDetail) return;

    try {
      setLoading(true);
      await ApiService.sendQuote(quoteDetail.id);
      setSuccess('Quote sent successfully');
      onQuoteUpdate();
      loadQuoteDetail();
    } catch (err) {
      setError('Failed to send quote');
    } finally {
      setLoading(false);
    }
  };

  const handleAcceptQuote = async () => {
    if (!quoteDetail) return;

    try {
      setLoading(true);
      await ApiService.acceptQuote(quoteDetail.id);
      setSuccess('Quote accepted successfully');
      onQuoteUpdate();
      loadQuoteDetail();
    } catch (err) {
      setError('Failed to accept quote');
    } finally {
      setLoading(false);
    }
  };

  const handleRejectQuote = async () => {
    if (!quoteDetail) return;

    const reason = window.prompt('Please provide a reason for rejecting this quote:');
    if (reason === null) return; // User cancelled

    try {
      setLoading(true);
      await ApiService.rejectQuote(quoteDetail.id, reason);
      setSuccess('Quote rejected successfully');
      onQuoteUpdate();
      loadQuoteDetail();
    } catch (err) {
      setError('Failed to reject quote');
    } finally {
      setLoading(false);
    }
  };

  const handlePreviewPDF = async () => {
    if (!quoteDetail) return;
    try {
      const blob = await ApiService.downloadQuotePDF(quoteDetail.id);
      const url = window.URL.createObjectURL(blob);
      window.open(url, '_blank');
    } catch (err) {
      setError('Failed to preview PDF');
    }
  };

  const handleDownloadPDF = async () => {
    if (!quoteDetail) return;

    try {
      const blob = await ApiService.downloadQuotePDF(quoteDetail.id);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `Quote_${quoteDetail.quote_number}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError('Failed to download PDF');
    }
  };

  const handlePrintQuote = () => {
    window.print();
  };

  const handleConvertToContract = () => {
    if (!quoteDetail) return;
    onClose();
    navigate(`/contracts?new=true&company=${quoteDetail.company}&quote=${quoteDetail.id}`);
  };

  const formatCurrency = (value: number, currency: string = 'USD'): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency,
      minimumFractionDigits: 2,
    }).format(value);
  };

  const formatDate = (dateString: string | null | undefined): string => {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleDateString();
  };

  const getStatusColor = (status: string): string => {
    switch (status) {
      case 'Draft': return '#9e9e9e';
      case 'Sent': return '#2196f3';
      case 'Accepted': return '#4caf50';
      case 'Rejected': return '#f44336';
      case 'Expired': return '#ff9800';
      default: return '#2196f3';
    }
  };

  const getActivityIcon = (activityType: string) => {
    switch (activityType) {
      case 'Created': return <Description />;
      case 'Sent': return <Send />;
      case 'Viewed': return <TrendingUp />;
      case 'Accepted': return <CheckCircle />;
      case 'Rejected': return <Cancel />;
      case 'Expired': return <Schedule />;
      case 'Updated': return <Edit />;
      case 'Converted': return <Assignment />;
      default: return <Description />;
    }
  };

  const getActivityColor = (activityType: string) => {
    switch (activityType) {
      case 'Created': return 'primary';
      case 'Sent': return 'info';
      case 'Viewed': return 'secondary';
      case 'Accepted': return 'success';
      case 'Rejected': return 'error';
      case 'Expired': return 'warning';
      case 'Updated': return 'primary';
      case 'Converted': return 'success';
      default: return 'primary';
    }
  };

  if (!quoteDetail && !loading) {
    return null;
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xl" fullWidth>
      <DialogTitle sx={{ pb: 1 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box>
            <Typography variant="h5" component="span">
              {quoteDetail?.quote_number || 'Loading...'}
            </Typography>
            {quoteDetail && (
              <Chip
                label={quoteDetail.status}
                size="small"
                sx={{
                  ml: 2,
                  backgroundColor: getStatusColor(quoteDetail.status),
                  color: 'white',
                  fontWeight: 600
                }}
              />
            )}
          </Box>
          <Box>
            {quoteDetail?.status === 'Draft' && (
              <Button
                variant="outlined"
                startIcon={<Send />}
                onClick={handleSendQuote}
                sx={{ mr: 1 }}
                disabled={loading}
              >
                Send Quote
              </Button>
            )}
            {quoteDetail?.status === 'Sent' && (
              <>
                <Button
                  variant="outlined"
                  color="success"
                  startIcon={<CheckCircle />}
                  onClick={handleAcceptQuote}
                  sx={{ mr: 1 }}
                  disabled={loading}
                >
                  Accept
                </Button>
                <Button
                  variant="outlined"
                  color="error"
                  startIcon={<Cancel />}
                  onClick={handleRejectQuote}
                  sx={{ mr: 1 }}
                  disabled={loading}
                >
                  Reject
                </Button>
              </>
            )}
            {quoteDetail?.status === 'Accepted' && (
              <>
                <Button
                  variant="contained"
                  startIcon={<Assignment />}
                  onClick={handleConvertToContract}
                  sx={{ mr: 1 }}
                  disabled={loading}
                >
                  Convert to Contract
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<Receipt />}
                  onClick={() => {
                    onClose();
                    navigate(`/invoices?new=true&company=${quoteDetail.company}&quote=${quoteDetail.id}`);
                  }}
                  sx={{ mr: 1 }}
                  disabled={loading}
                >
                  Create Invoice
                </Button>
              </>
            )}
            <Button
              variant="outlined"
              startIcon={<Visibility />}
              onClick={handlePreviewPDF}
              sx={{ mr: 1 }}
              disabled={loading}
            >
              Preview
            </Button>
            <Button
              variant="outlined"
              startIcon={<GetApp />}
              onClick={handleDownloadPDF}
              sx={{ mr: 1 }}
              disabled={loading}
            >
              PDF
            </Button>
            <Button
              variant="outlined"
              startIcon={<Print />}
              onClick={handlePrintQuote}
              disabled={loading}
            >
              Print
            </Button>
          </Box>
        </Box>
      </DialogTitle>

      <DialogContent sx={{ pb: 1 }}>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
            {error}
          </Alert>
        )}

        {success && (
          <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess('')}>
            {success}
          </Alert>
        )}

        {loading && !quoteDetail ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        ) : quoteDetail && (
          <Grid container spacing={3}>
            {/* Quote Information */}
            <Grid item xs={12} md={8}>
              <Paper sx={{ p: 3, mb: 3 }}>
                <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center' }}>
                  <Business sx={{ mr: 1 }} />
                  Quote Information
                </Typography>

                <Grid container spacing={2}>
                  <Grid item xs={12} sm={6}>
                    <Typography variant="body2" color="text.secondary">Company</Typography>
                    <Typography variant="body1" fontWeight="medium">
                      {quoteDetail.company_name}
                    </Typography>
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <Typography variant="body2" color="text.secondary">Contact</Typography>
                    <Typography variant="body1" fontWeight="medium">
                      {quoteDetail.contact_name || '-'}
                    </Typography>
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <Typography variant="body2" color="text.secondary">Opportunity</Typography>
                    <Typography variant="body1" fontWeight="medium">
                      {quoteDetail.opportunity_name || '-'}
                    </Typography>
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <Typography variant="body2" color="text.secondary">Created By</Typography>
                    <Typography variant="body1" fontWeight="medium">
                      {quoteDetail.created_by_name}
                    </Typography>
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <Typography variant="body2" color="text.secondary">Valid From</Typography>
                    <Typography variant="body1" fontWeight="medium">
                      {formatDate(quoteDetail.valid_from)}
                    </Typography>
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <Typography variant="body2" color="text.secondary">Valid Until</Typography>
                    <Typography variant="body1" fontWeight="medium" sx={{
                      color: quoteDetail.is_expired ? 'error.main' : 'text.primary'
                    }}>
                      {formatDate(quoteDetail.valid_until)}
                      {quoteDetail.is_expired && ' (Expired)'}
                    </Typography>
                  </Grid>
                </Grid>
              </Paper>

              {/* Line Items */}
              <Paper sx={{ p: 3, mb: 3 }}>
                <Typography variant="h6" sx={{ mb: 2 }}>
                  Line Items
                </Typography>

                <TableContainer>
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableCell>Product/Service</TableCell>
                        <TableCell>Description</TableCell>
                        <TableCell align="center">Qty</TableCell>
                        <TableCell align="right">Unit Price</TableCell>
                        <TableCell align="center">Discount</TableCell>
                        <TableCell align="center">Tax</TableCell>
                        <TableCell align="right">Line Total</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {quoteDetail.line_items?.map((item, index) => (
                        <TableRow key={index}>
                          <TableCell>
                            <Typography variant="body2" fontWeight="medium">
                              {item.product_service}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2" color="text.secondary">
                              {item.description}
                            </Typography>
                          </TableCell>
                          <TableCell align="center">
                            <Typography variant="body2">
                              {item.quantity}
                            </Typography>
                          </TableCell>
                          <TableCell align="right">
                            <Typography variant="body2">
                              {formatCurrency(item.unit_price, quoteDetail.currency)}
                            </Typography>
                          </TableCell>
                          <TableCell align="center">
                            <Typography variant="body2">
                              {item.discount_percentage}%
                            </Typography>
                          </TableCell>
                          <TableCell align="center">
                            <Typography variant="body2">
                              {item.tax_rate}%
                            </Typography>
                          </TableCell>
                          <TableCell align="right">
                            <Typography variant="body2" fontWeight="medium">
                              {formatCurrency(item.line_total, quoteDetail.currency)}
                            </Typography>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>

                {/* Totals */}
                <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 3 }}>
                  <Paper variant="outlined" sx={{ p: 2, minWidth: 300 }}>
                    <Grid container spacing={1}>
                      <Grid item xs={6}>
                        <Typography variant="body2">Subtotal:</Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="body2" align="right">
                          {formatCurrency(quoteDetail.subtotal, quoteDetail.currency)}
                        </Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="body2">Discount:</Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="body2" align="right" color="error.main">
                          -{formatCurrency(quoteDetail.discount_amount, quoteDetail.currency)}
                        </Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="body2">Tax:</Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="body2" align="right">
                          {formatCurrency(quoteDetail.tax_amount, quoteDetail.currency)}
                        </Typography>
                      </Grid>
                      <Divider sx={{ width: '100%', my: 1 }} />
                      <Grid item xs={6}>
                        <Typography variant="h6">Total:</Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="h6" align="right">
                          {formatCurrency(quoteDetail.total_value, quoteDetail.currency)}
                        </Typography>
                      </Grid>
                    </Grid>
                  </Paper>
                </Box>
              </Paper>

              {/* Terms and Notes */}
              {(quoteDetail.terms_conditions || quoteDetail.notes) && (
                <Paper sx={{ p: 3, mb: 3 }}>
                  <Grid container spacing={3}>
                    {quoteDetail.terms_conditions && (
                      <Grid item xs={12} md={6}>
                        <Typography variant="h6" sx={{ mb: 1 }}>
                          Terms & Conditions
                        </Typography>
                        <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                          {quoteDetail.terms_conditions}
                        </Typography>
                      </Grid>
                    )}
                    {quoteDetail.notes && (
                      <Grid item xs={12} md={6}>
                        <Typography variant="h6" sx={{ mb: 1 }}>
                          Notes
                        </Typography>
                        <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                          {quoteDetail.notes}
                        </Typography>
                      </Grid>
                    )}
                  </Grid>
                </Paper>
              )}

              {/* Attachments */}
              {quoteDetail.attachments && quoteDetail.attachments.length > 0 && (
                <Paper sx={{ p: 3 }}>
                  <Typography variant="h6" sx={{ mb: 2 }}>
                    Attachments
                  </Typography>
                  <List dense>
                    {quoteDetail.attachments.map((attachment, index) => (
                      <ListItem key={index}>
                        <ListItemIcon>
                          <AttachFile />
                        </ListItemIcon>
                        <ListItemText
                          primary={attachment.name}
                          secondary={`Uploaded by ${attachment.uploaded_by_name} on ${formatDate(attachment.created_at)}`}
                        />
                        <IconButton edge="end" onClick={() => window.open(attachment.file, '_blank')}>
                          <GetApp />
                        </IconButton>
                      </ListItem>
                    ))}
                  </List>
                </Paper>
              )}
            </Grid>

            {/* Right Sidebar */}
            <Grid item xs={12} md={4}>
              {/* Quick Stats */}
              <Paper sx={{ p: 2, mb: 3 }}>
                <Typography variant="h6" sx={{ mb: 2 }}>
                  Quote Summary
                </Typography>
                <Grid container spacing={2}>
                  <Grid item xs={6}>
                    <Typography variant="body2" color="text.secondary">Total Value</Typography>
                    <Typography variant="h6">
                      {formatCurrency(quoteDetail.total_value, quoteDetail.currency)}
                    </Typography>
                  </Grid>
                  <Grid item xs={6}>
                    <Typography variant="body2" color="text.secondary">Days Until Expiry</Typography>
                    <Typography variant="h6" sx={{
                      color: quoteDetail.is_expired ? 'error.main' :
                             quoteDetail.days_until_expiry <= 7 ? 'warning.main' : 'text.primary'
                    }}>
                      {quoteDetail.is_expired ? 'Expired' : `${quoteDetail.days_until_expiry} days`}
                    </Typography>
                  </Grid>
                  <Grid item xs={12}>
                    <Typography variant="body2" color="text.secondary">Created</Typography>
                    <Typography variant="body1">
                      {formatDate(quoteDetail.created_at)}
                    </Typography>
                  </Grid>
                </Grid>
              </Paper>

              {/* Activity Timeline */}
              <Paper sx={{ p: 2 }}>
                <Typography variant="h6" sx={{ mb: 2 }}>
                  Activity Timeline
                </Typography>
                {activities.length === 0 ? (
                  <Typography variant="body2" color="text.secondary">
                    No activities recorded
                  </Typography>
                ) : (
                  <Timeline sx={{ py: 0, px: 0, '& .MuiTimelineItem-root': { minHeight: 60 } }}>
                    {activities.map((activity, index) => (
                      <TimelineItem key={activity.id}>
                        <TimelineSeparator>
                          <TimelineDot color={getActivityColor(activity.activity_type) as any}>
                            {getActivityIcon(activity.activity_type)}
                          </TimelineDot>
                          {index < activities.length - 1 && <TimelineConnector />}
                        </TimelineSeparator>
                        <TimelineContent sx={{ py: 1 }}>
                          <Typography variant="body2" fontWeight="medium">
                            {activity.activity_type}
                          </Typography>
                          <Typography variant="body2" color="text.secondary">
                            {activity.description}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {activity.user_name} • {formatDate(activity.created_at)}
                          </Typography>
                        </TimelineContent>
                      </TimelineItem>
                    ))}
                  </Timeline>
                )}
              </Paper>
            </Grid>
          </Grid>
        )}
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 3 }}>
        <Button onClick={onClose} startIcon={<Close />}>
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default QuoteDetail;