import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link as RouterLink } from 'react-router-dom';
import {
  Box,
  Typography,
  Button,
  Paper,
  Alert,
  CircularProgress,
  Chip,
  Link,
} from '@mui/material';
import {
  ArrowBack,
  Edit,
  GetApp,
  Send,
  CheckCircle,
  Cancel,
  Assignment,
  Print,
} from '@mui/icons-material';
import { Quote } from '../types';
import ApiService from '../services/api';
import { QuoteDetail as QuoteDetailComponent } from '../components';
import { PageHeader } from '../components/ui';
import { statusTone } from '../theme';

const QuoteDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [quote, setQuote] = useState<Quote | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    if (id) {
      loadQuote();
    }
  }, [id]);

  const loadQuote = async () => {
    if (!id) return;

    try {
      setLoading(true);
      const quoteData = await ApiService.getQuote(id);
      setQuote(quoteData);
    } catch (err: any) {
      setError('Failed to load quote details');
    } finally {
      setLoading(false);
    }
  };

  const handleSendQuote = async () => {
    if (!quote) return;

    try {
      setLoading(true);
      await ApiService.sendQuote(quote.id);
      setSuccess('Quote sent successfully');
      loadQuote();
    } catch (err) {
      setError('Failed to send quote');
    } finally {
      setLoading(false);
    }
  };

  const handleAcceptQuote = async () => {
    if (!quote) return;

    try {
      setLoading(true);
      await ApiService.acceptQuote(quote.id);
      setSuccess('Quote accepted successfully');
      loadQuote();
    } catch (err) {
      setError('Failed to accept quote');
    } finally {
      setLoading(false);
    }
  };

  const handleRejectQuote = async () => {
    if (!quote) return;

    const reason = window.prompt('Please provide a reason for rejecting this quote:');
    if (reason === null) return; // User cancelled

    try {
      setLoading(true);
      await ApiService.rejectQuote(quote.id, reason);
      setSuccess('Quote rejected successfully');
      loadQuote();
    } catch (err) {
      setError('Failed to reject quote');
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadPDF = async () => {
    if (!quote) return;

    try {
      const blob = await ApiService.downloadQuotePDF(quote.id);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `Quote_${quote.quote_number}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError('Failed to download PDF');
    }
  };

  const handleConvertToContract = async () => {
    if (!quote) return;

    if (!window.confirm('Are you sure you want to convert this quote to a contract?')) {
      return;
    }

    try {
      setLoading(true);
      await ApiService.convertQuoteToContract(quote.id);
      setSuccess('Quote converted to contract successfully');
      loadQuote();
    } catch (err) {
      setError('Failed to convert quote to contract');
    } finally {
      setLoading(false);
    }
  };

  if (loading && !quote) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error && !quote) {
    return (
      <Alert severity="error" sx={{ mb: 2 }}>
        {error}
      </Alert>
    );
  }

  if (!quote) {
    return (
      <Alert severity="error" sx={{ mb: 2 }}>
        Quote not found
      </Alert>
    );
  }

  return (
    <Box>
      <PageHeader
        breadcrumbs={[{ label: 'Quotes', to: '/quotes' }, { label: quote.quote_number }]}
        title={quote.quote_number}
        subtitle={
          quote.company ? (
            <Link component={RouterLink} to={`/companies/${quote.company}`} underline="hover" sx={{ fontWeight: 600 }}>
              {quote.company_name}
            </Link>
          ) : (
            quote.company_name
          )
        }
        meta={<Chip label={quote.status} size="small" color={statusTone(quote.status)} />}
        actions={
          <>
          {quote.status === 'Draft' && (
            <Button
              variant="outlined"
              startIcon={<Send />}
              onClick={handleSendQuote}
              disabled={loading}
            >
              Send Quote
            </Button>
          )}
          {quote.status === 'Sent' && (
            <>
              <Button
                variant="outlined"
                color="success"
                startIcon={<CheckCircle />}
                onClick={handleAcceptQuote}
                disabled={loading}
              >
                Accept
              </Button>
              <Button
                variant="outlined"
                color="error"
                startIcon={<Cancel />}
                onClick={handleRejectQuote}
                disabled={loading}
              >
                Reject
              </Button>
            </>
          )}
          {quote.status === 'Accepted' && (
            <Button
              variant="contained"
              startIcon={<Assignment />}
              onClick={handleConvertToContract}
              disabled={loading}
            >
              Convert to Contract
            </Button>
          )}
          <Button
            variant="outlined"
            startIcon={<Edit />}
            onClick={() => navigate(`/quotes?edit=${quote.id}`)}
          >
            Edit
          </Button>
          <Button
            variant="outlined"
            startIcon={<GetApp />}
            onClick={handleDownloadPDF}
          >
            PDF
          </Button>
          <Button
            variant="outlined"
            startIcon={<Print />}
            onClick={() => window.print()}
          >
            Print
          </Button>
          </>
        }
      />

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

      {/* The quote's content, as a page (it used to open as a pop-up over this page) */}
      <QuoteDetailComponent
        variant="page"
        open={true}
        onClose={() => navigate('/quotes')}
        quote={quote}
        onQuoteUpdate={loadQuote}
      />
    </Box>
  );
};

export default QuoteDetailPage;