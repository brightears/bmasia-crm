import React from 'react';
import {
  Box,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Divider,
  Paper,
  GridLegacy as Grid,
} from '@mui/material';
import { Quote } from '../types';

interface QuotePDFGeneratorProps {
  quote: Quote;
}

const QuotePDFGenerator: React.FC<QuotePDFGeneratorProps> = ({ quote }) => {
  const formatCurrency = (value: number, currency: string = 'USD'): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency,
      minimumFractionDigits: 2,
    }).format(value);
  };

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  return (
    <Paper
      sx={{
        p: 4,
        maxWidth: '8.5in',
        minHeight: '11in',
        bgcolor: 'white',
        color: 'black',
        fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
        '@media print': {
          boxShadow: 'none',
          m: 0,
          p: '0.5in',
          maxWidth: 'none',
          width: '100%',
        }
      }}
    >
      {/* Header */}
      <Box sx={{ mb: 4, borderBottom: '3px solid #1976d2', pb: 2 }}>
        <Grid container justifyContent="space-between" alignItems="center">
          <Grid item>
            <Typography variant="h3" sx={{ color: '#1976d2', fontWeight: 'bold', mb: 1 }}>
              BMAsia
            </Typography>
            <Typography variant="h6" sx={{ color: '#666' }}>
              Music Technology Solutions
            </Typography>
          </Grid>
          <Grid item>
            <Typography variant="h4" sx={{ color: '#1976d2', fontWeight: 'bold' }}>
              QUOTE
            </Typography>
            <Typography variant="h6" sx={{ color: '#666' }}>
              {quote.quote_number}
            </Typography>
          </Grid>
        </Grid>
      </Box>

      {/* Company Information */}
      <Box sx={{ mb: 4 }}>
        <Grid container spacing={4}>
          <Grid item xs={6}>
            <Typography variant="h6" sx={{ fontWeight: 'bold', mb: 1, color: '#333' }}>
              From:
            </Typography>
            <Typography variant="body1" sx={{ mb: 0.5, fontWeight: 'bold' }}>
              BMAsia Co., Ltd.
            </Typography>
            <Typography variant="body2" sx={{ color: '#666' }}>
              123 Business Street<br />
              Bangkok, Thailand 10110<br />
              Phone: +66 2 123 4567<br />
              Email: quotes@bmasia.com<br />
              Website: www.bmasia.com
            </Typography>
          </Grid>
          <Grid item xs={6}>
            <Typography variant="h6" sx={{ fontWeight: 'bold', mb: 1, color: '#333' }}>
              To:
            </Typography>
            <Typography variant="body1" sx={{ mb: 0.5, fontWeight: 'bold' }}>
              {quote.company_name}
            </Typography>
            {quote.contact_name && (
              <Typography variant="body2" sx={{ color: '#666', mb: 0.5 }}>
                Attention: {quote.contact_name}
              </Typography>
            )}
            <Typography variant="body2" sx={{ color: '#666' }}>
              {/* Add company address when available */}
            </Typography>
          </Grid>
        </Grid>
      </Box>

      {/* Quote Details */}
      <Box sx={{ mb: 4 }}>
        <Grid container spacing={2}>
          <Grid item xs={6}>
            <Box sx={{ p: 2, bgcolor: '#f5f5f5', borderRadius: 1 }}>
              <Typography variant="body2" sx={{ color: '#666', fontWeight: 'bold' }}>
                Quote Date:
              </Typography>
              <Typography variant="body1">
                {formatDate(quote.created_at)}
              </Typography>
            </Box>
          </Grid>
          <Grid item xs={6}>
            <Box sx={{ p: 2, bgcolor: '#f5f5f5', borderRadius: 1 }}>
              <Typography variant="body2" sx={{ color: '#666', fontWeight: 'bold' }}>
                Valid Until:
              </Typography>
              <Typography variant="body1" sx={{
                color: quote.is_expired ? '#d32f2f' : 'inherit'
              }}>
                {formatDate(quote.valid_until)}
                {quote.is_expired && ' (Expired)'}
              </Typography>
            </Box>
          </Grid>
        </Grid>
      </Box>

      {/* Line Items */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h6" sx={{ fontWeight: 'bold', mb: 2, color: '#333' }}>
          Items & Services
        </Typography>

        <TableContainer component={Paper} variant="outlined">
          <Table>
            <TableHead sx={{ bgcolor: '#1976d2' }}>
              <TableRow>
                <TableCell sx={{ color: 'white', fontWeight: 'bold' }}>
                  Product/Service
                </TableCell>
                <TableCell sx={{ color: 'white', fontWeight: 'bold' }} align="center">
                  Qty
                </TableCell>
                <TableCell sx={{ color: 'white', fontWeight: 'bold' }} align="right">
                  Unit Price
                </TableCell>
                <TableCell sx={{ color: 'white', fontWeight: 'bold' }} align="center">
                  Discount
                </TableCell>
                <TableCell sx={{ color: 'white', fontWeight: 'bold' }} align="center">
                  Tax
                </TableCell>
                <TableCell sx={{ color: 'white', fontWeight: 'bold' }} align="right">
                  Total
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {quote.line_items?.map((item, index) => (
                <TableRow key={index} sx={{ '&:nth-of-type(even)': { bgcolor: '#f9f9f9' } }}>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                      {item.product_service}
                    </Typography>
                    {item.description && (
                      <Typography variant="caption" sx={{ color: '#666', display: 'block', mt: 0.5 }}>
                        {item.description}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell align="center">
                    <Typography variant="body2">
                      {item.quantity}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2">
                      {formatCurrency(item.unit_price, quote.currency)}
                    </Typography>
                  </TableCell>
                  <TableCell align="center">
                    <Typography variant="body2">
                      {item.discount_percentage > 0 ? `${item.discount_percentage}%` : '-'}
                    </Typography>
                  </TableCell>
                  <TableCell align="center">
                    <Typography variant="body2">
                      {item.tax_rate}%
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                      {formatCurrency(item.line_total, quote.currency)}
                    </Typography>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Box>

      {/* Totals */}
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 4 }}>
        <Box sx={{ minWidth: 300 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 1 }}>
            <Typography variant="body1">Subtotal:</Typography>
            <Typography variant="body1">
              {formatCurrency(quote.subtotal, quote.currency)}
            </Typography>
          </Box>

          {quote.discount_amount > 0 && (
            <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 1 }}>
              <Typography variant="body1">Discount:</Typography>
              <Typography variant="body1" sx={{ color: '#d32f2f' }}>
                -{formatCurrency(quote.discount_amount, quote.currency)}
              </Typography>
            </Box>
          )}

          <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 1 }}>
            <Typography variant="body1">Tax:</Typography>
            <Typography variant="body1">
              {formatCurrency(quote.tax_amount, quote.currency)}
            </Typography>
          </Box>

          <Divider sx={{ my: 1 }} />

          <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 1, bgcolor: '#1976d2', color: 'white', px: 2, borderRadius: 1 }}>
            <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
              Total:
            </Typography>
            <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
              {formatCurrency(quote.total_value, quote.currency)}
            </Typography>
          </Box>
        </Box>
      </Box>

      {/* Terms and Conditions */}
      {quote.terms_conditions && (
        <Box sx={{ mb: 4 }}>
          <Typography variant="h6" sx={{ fontWeight: 'bold', mb: 2, color: '#333' }}>
            Terms & Conditions
          </Typography>
          <Paper sx={{ p: 2, bgcolor: '#f9f9f9' }}>
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
              {quote.terms_conditions}
            </Typography>
          </Paper>
        </Box>
      )}

      {/* Notes */}
      {quote.notes && (
        <Box sx={{ mb: 4 }}>
          <Typography variant="h6" sx={{ fontWeight: 'bold', mb: 2, color: '#333' }}>
            Additional Notes
          </Typography>
          <Paper sx={{ p: 2, bgcolor: '#f9f9f9' }}>
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
              {quote.notes}
            </Typography>
          </Paper>
        </Box>
      )}

      {/* Quote Acceptance Section */}
      <Box sx={{ mt: 6, pt: 4, borderTop: '1px solid #ddd' }}>
        <Typography variant="h6" sx={{ fontWeight: 'bold', mb: 3, color: '#333' }}>
          Quote Acceptance
        </Typography>

        <Grid container spacing={4}>
          <Grid item xs={6}>
            <Box>
              <Typography variant="body2" sx={{ mb: 1 }}>
                I/We accept the above quote and authorize the work to proceed as specified.
              </Typography>
              <Box sx={{ mt: 4 }}>
                <Typography variant="body2" sx={{ borderBottom: '1px solid #333', display: 'inline-block', minWidth: '200px', pb: 0.5 }}>
                  &nbsp;
                </Typography>
                <Typography variant="caption" sx={{ display: 'block', mt: 0.5, color: '#666' }}>
                  Authorized Signature
                </Typography>
              </Box>
            </Box>
          </Grid>
          <Grid item xs={6}>
            <Box>
              <Typography variant="body2" sx={{ mb: 1 }}>
                &nbsp;
              </Typography>
              <Box sx={{ mt: 4 }}>
                <Typography variant="body2" sx={{ borderBottom: '1px solid #333', display: 'inline-block', minWidth: '150px', pb: 0.5 }}>
                  &nbsp;
                </Typography>
                <Typography variant="caption" sx={{ display: 'block', mt: 0.5, color: '#666' }}>
                  Date
                </Typography>
              </Box>
            </Box>
          </Grid>
        </Grid>
      </Box>

      {/* Footer */}
      <Box sx={{ mt: 6, pt: 3, borderTop: '1px solid #ddd', textAlign: 'center' }}>
        <Typography variant="caption" sx={{ color: '#666' }}>
          Thank you for considering BMAsia for your music technology needs.<br />
          This quote is valid until {formatDate(quote.valid_until)}.
        </Typography>
      </Box>
    </Paper>
  );
};

export default QuotePDFGenerator;