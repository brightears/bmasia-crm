import React from 'react';
import {
  Box,
  Paper,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Divider,
  Button,
  Stack,
} from '@mui/material';
import {
  GetApp,
  Print,
  Share,
} from '@mui/icons-material';
import { Invoice } from '../types';

interface InvoicePDFGeneratorProps {
  invoice: Invoice;
  onDownload?: () => void;
  onPrint?: () => void;
  onShare?: () => void;
}

const InvoicePDFGenerator: React.FC<InvoicePDFGeneratorProps> = ({
  invoice,
  onDownload,
  onPrint,
  onShare,
}) => {
  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
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

  const handlePrint = () => {
    if (onPrint) {
      onPrint();
    } else {
      window.print();
    }
  };

  return (
    <Box>
      {/* Action Buttons */}
      <Stack direction="row" spacing={2} sx={{ mb: 3, '@media print': { display: 'none' } }}>
        <Button
          variant="contained"
          startIcon={<GetApp />}
          onClick={onDownload}
        >
          Download PDF
        </Button>
        <Button
          variant="outlined"
          startIcon={<Print />}
          onClick={handlePrint}
        >
          Print
        </Button>
        {onShare && (
          <Button
            variant="outlined"
            startIcon={<Share />}
            onClick={onShare}
          >
            Share
          </Button>
        )}
      </Stack>

      {/* Invoice Template */}
      <Paper
        sx={{
          p: 4,
          maxWidth: '8.5in',
          mx: 'auto',
          backgroundColor: 'white',
          color: 'black',
          '@media print': {
            boxShadow: 'none',
            margin: 0,
            maxWidth: 'none',
            padding: '0.5in',
          },
        }}
        id="invoice-content"
      >
        {/* Header */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 4 }}>
          <Box>
            <Typography variant="h3" sx={{ fontWeight: 'bold', color: '#1976d2', mb: 1 }}>
              BMAsia
            </Typography>
            <Typography variant="subtitle1" color="text.secondary">
              Music Technology Solutions
            </Typography>
            <Box sx={{ mt: 2 }}>
              <Typography variant="body2">123 Business Street</Typography>
              <Typography variant="body2">Bangkok, Thailand 10110</Typography>
              <Typography variant="body2">+66 2 xxx xxxx</Typography>
              <Typography variant="body2">info@bmasia.com</Typography>
            </Box>
          </Box>
          <Box sx={{ textAlign: 'right' }}>
            <Typography variant="h4" sx={{ fontWeight: 'bold', mb: 2 }}>
              INVOICE
            </Typography>
            <Typography variant="h5" color="primary" sx={{ fontWeight: 'medium' }}>
              {invoice.invoice_number}
            </Typography>
          </Box>
        </Box>

        {/* Bill To and Invoice Details */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 4 }}>
          <Box sx={{ flex: 1, mr: 4 }}>
            <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold' }}>
              Bill To:
            </Typography>
            <Typography variant="body1" sx={{ fontWeight: 'medium', mb: 1 }}>
              {invoice.company_name}
            </Typography>
            {/* Add company address here if available */}
            <Typography variant="body2" color="text.secondary">
              Contract: {invoice.contract_number}
            </Typography>
          </Box>
          <Box sx={{ flex: 1 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
              <Typography variant="body2" fontWeight="medium">Invoice Date:</Typography>
              <Typography variant="body2">{formatDate(invoice.issue_date)}</Typography>
            </Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
              <Typography variant="body2" fontWeight="medium">Due Date:</Typography>
              <Typography variant="body2">{formatDate(invoice.due_date)}</Typography>
            </Box>
            {invoice.payment_terms && (
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                <Typography variant="body2" fontWeight="medium">Payment Terms:</Typography>
                <Typography variant="body2">{invoice.payment_terms}</Typography>
              </Box>
            )}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
              <Typography variant="body2" fontWeight="medium">Currency:</Typography>
              <Typography variant="body2">{invoice.currency}</Typography>
            </Box>
          </Box>
        </Box>

        {/* Line Items Table */}
        <TableContainer sx={{ mb: 4 }}>
          <Table>
            <TableHead>
              <TableRow sx={{ backgroundColor: '#f5f5f5' }}>
                <TableCell sx={{ fontWeight: 'bold', py: 2 }}>Description</TableCell>
                <TableCell align="center" sx={{ fontWeight: 'bold', py: 2 }}>Qty</TableCell>
                <TableCell align="right" sx={{ fontWeight: 'bold', py: 2 }}>Unit Price</TableCell>
                <TableCell align="center" sx={{ fontWeight: 'bold', py: 2 }}>Tax Rate</TableCell>
                <TableCell align="right" sx={{ fontWeight: 'bold', py: 2 }}>Amount</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {invoice.line_items.map((item, index) => (
                <TableRow key={index}>
                  <TableCell sx={{ py: 2 }}>
                    <Typography variant="body2">{item.description}</Typography>
                  </TableCell>
                  <TableCell align="center" sx={{ py: 2 }}>
                    {item.quantity}
                  </TableCell>
                  <TableCell align="right" sx={{ py: 2 }}>
                    {formatCurrency(item.unit_price)}
                  </TableCell>
                  <TableCell align="center" sx={{ py: 2 }}>
                    {item.tax_rate}%
                  </TableCell>
                  <TableCell align="right" sx={{ py: 2 }}>
                    {formatCurrency(item.total)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>

        {/* Totals Section */}
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 4 }}>
          <Box sx={{ minWidth: 300 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
              <Typography variant="body2">Subtotal:</Typography>
              <Typography variant="body2">{formatCurrency(invoice.amount)}</Typography>
            </Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
              <Typography variant="body2">Tax:</Typography>
              <Typography variant="body2">{formatCurrency(invoice.tax_amount)}</Typography>
            </Box>
            {invoice.discount_amount > 0 && (
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                <Typography variant="body2">Discount:</Typography>
                <Typography variant="body2" color="error">
                  -{formatCurrency(invoice.discount_amount)}
                </Typography>
              </Box>
            )}
            <Divider sx={{ my: 1 }} />
            <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
              <Typography variant="h6" fontWeight="bold">Total:</Typography>
              <Typography variant="h6" fontWeight="bold" color="primary">
                {formatCurrency(invoice.total_amount)}
              </Typography>
            </Box>
          </Box>
        </Box>

        {/* Payment Information */}
        <Box sx={{ mb: 4, p: 3, backgroundColor: '#f8f9fa', borderRadius: 1 }}>
          <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold' }}>
            Payment Information
          </Typography>
          <Typography variant="body2" sx={{ mb: 1 }}>
            <strong>Bank Transfer:</strong> Bangkok Bank
          </Typography>
          <Typography variant="body2" sx={{ mb: 1 }}>
            <strong>Account Name:</strong> BMAsia Co., Ltd.
          </Typography>
          <Typography variant="body2" sx={{ mb: 1 }}>
            <strong>Account Number:</strong> 123-456-7890
          </Typography>
          <Typography variant="body2" sx={{ mb: 1 }}>
            <strong>Swift Code:</strong> BKKBTHBK
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            Please include invoice number {invoice.invoice_number} in your payment reference.
          </Typography>
        </Box>

        {/* Notes */}
        {invoice.notes && (
          <Box sx={{ mb: 4 }}>
            <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold' }}>
              Notes
            </Typography>
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
              {invoice.notes}
            </Typography>
          </Box>
        )}

        {/* Terms and Conditions */}
        <Box sx={{ mb: 4 }}>
          <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold' }}>
            Terms and Conditions
          </Typography>
          <Typography variant="body2" sx={{ mb: 1 }}>
            1. Payment is due within the specified payment terms.
          </Typography>
          <Typography variant="body2" sx={{ mb: 1 }}>
            2. Late payment may incur additional charges.
          </Typography>
          <Typography variant="body2" sx={{ mb: 1 }}>
            3. Please retain this invoice for your records.
          </Typography>
          <Typography variant="body2" sx={{ mb: 1 }}>
            4. For any questions regarding this invoice, please contact our billing department.
          </Typography>
        </Box>

        {/* Footer */}
        <Divider sx={{ mb: 3 }} />
        <Box sx={{ textAlign: 'center' }}>
          <Typography variant="body2" color="text.secondary">
            Thank you for your business!
          </Typography>
          <Typography variant="body2" color="text.secondary">
            BMAsia - Your Music Technology Partner
          </Typography>
        </Box>
      </Paper>
    </Box>
  );
};

export default InvoicePDFGenerator;