import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  FormGroup,
  FormControlLabel,
  Checkbox,
  Box,
  Typography,
  Alert,
  CircularProgress,
  Divider,
  Chip,
} from '@mui/material';
import {
  Email as EmailIcon,
  Send as SendIcon,
  Close as CloseIcon,
} from '@mui/icons-material';
import { Contact } from '../types';

export interface EmailSendData {
  recipients: string[];
  cc: string[];
  subject: string;
  body: string;
}

interface EmailSendDialogProps {
  open: boolean;
  onClose: () => void;
  documentType: 'quote' | 'contract' | 'invoice';
  documentId: string;
  documentNumber: string;
  companyName: string;
  contacts: Contact[];
  onSendSuccess: () => void;
  onSendEmail: (data: EmailSendData) => Promise<void>;
  documentDetails?: {
    currency?: string;
    totalValue?: number;
    validUntil?: string;
    startDate?: string;
    endDate?: string;
  };
}

const EmailSendDialog: React.FC<EmailSendDialogProps> = ({
  open,
  onClose,
  documentType,
  documentId,
  documentNumber,
  companyName,
  contacts,
  onSendSuccess,
  onSendEmail,
  documentDetails = {},
}) => {
  const [selectedContacts, setSelectedContacts] = useState<string[]>([]);
  const [ccContacts, setCcContacts] = useState<string[]>([]);
  const [ccExternal, setCcExternal] = useState('');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Initialize default values when dialog opens or document changes
  useEffect(() => {
    if (open && contacts.length > 0) {
      // Pre-select contacts based on document-type preference
      const prefKey = documentType === 'quote' ? 'receives_quote_emails'
        : documentType === 'contract' ? 'receives_contract_emails'
        : 'receives_invoice_emails';

      const defaultContacts = contacts
        .filter(c => c[prefKey] === true)
        .map(c => c.email);

      // Fallback to Primary + Billing if no preferences set, then first contact
      if (defaultContacts.length > 0) {
        setSelectedContacts(defaultContacts);
      } else {
        const fallback = contacts
          .filter(c => c.contact_type === 'Primary' || c.contact_type === 'Billing')
          .map(c => c.email);
        setSelectedContacts(fallback.length > 0 ? fallback : [contacts[0].email]);
      }

      // Reset CC
      setCcContacts([]);
      setCcExternal('');

      // Set default subject
      const subjectPrefix = documentType.charAt(0).toUpperCase() + documentType.slice(1);
      setSubject(`${subjectPrefix} ${documentNumber} from BMAsia Music`);

      // Set default body based on document type
      setBody(getDefaultEmailBody());

      // Reset error
      setError('');
    }
  }, [open, documentType, documentNumber, companyName, contacts]);

  const getDefaultEmailBody = (): string => {
    const { currency, totalValue, validUntil, startDate, endDate } = documentDetails;

    switch (documentType) {
      case 'quote':
        return `Dear Valued Customer,

Please find attached quote ${documentNumber} for ${companyName}.

${totalValue ? `Total Amount: ${currency || 'USD'} ${formatCurrency(totalValue)}` : ''}
${validUntil ? `Valid Until: ${formatDate(validUntil)}` : ''}

If you have any questions, please don't hesitate to contact us.

Best regards,
BMAsia Music Team`;

      case 'contract':
        return `Dear Valued Customer,

Please find attached contract ${documentNumber} for ${companyName}.

${totalValue ? `Contract Value: ${currency || 'USD'} ${formatCurrency(totalValue)}` : ''}
${startDate && endDate ? `Contract Period: ${formatDate(startDate)} - ${formatDate(endDate)}` : ''}

Please review and sign at your earliest convenience.

Best regards,
BMAsia Music Team`;

      case 'invoice':
        return `Dear Valued Customer,

Please find attached invoice ${documentNumber} for ${companyName}.

${totalValue ? `Total Amount: ${currency || 'USD'} ${formatCurrency(totalValue)}` : ''}

Payment is requested at your earliest convenience.

Best regards,
BMAsia Music Team`;

      default:
        return '';
    }
  };

  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  };

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  const handleContactToggle = (email: string) => {
    setSelectedContacts(prev => {
      const newSelected = prev.includes(email)
        ? prev.filter(e => e !== email)
        : [...prev, email];
      // Remove from CC if being added to To
      if (newSelected.includes(email)) {
        setCcContacts(ccPrev => ccPrev.filter(e => e !== email));
      }
      return newSelected;
    });
  };

  const handleCcContactToggle = (email: string) => {
    setCcContacts(prev =>
      prev.includes(email)
        ? prev.filter(e => e !== email)
        : [...prev, email]
    );
  };

  // Contacts not selected as To recipients — available for CC
  const availableCcContacts = contacts.filter(
    c => !selectedContacts.includes(c.email)
  );

  const handleSend = async () => {
    // Validation
    if (selectedContacts.length === 0) {
      setError('Please select at least one recipient');
      return;
    }

    if (!subject.trim()) {
      setError('Please enter a subject');
      return;
    }

    if (!body.trim()) {
      setError('Please enter a message body');
      return;
    }

    // Parse and validate external CC emails
    const externalCcList = ccExternal
      .split(',')
      .map(e => e.trim())
      .filter(e => e && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e));

    const allCc = [...ccContacts, ...externalCcList];

    try {
      setLoading(true);
      setError('');

      await onSendEmail({
        recipients: selectedContacts,
        cc: allCc,
        subject: subject.trim(),
        body: body.trim(),
      });

      onSendSuccess();
      handleClose();
    } catch (err: any) {
      setError(err.response?.data?.error || err.message || 'Failed to send email');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      onClose();
    }
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: {
          minHeight: '600px',
        },
      }}
    >
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <EmailIcon sx={{ mr: 1, color: '#FFA500' }} />
            <Typography variant="h6">
              Send {documentType.charAt(0).toUpperCase() + documentType.slice(1)}
            </Typography>
          </Box>
          <Box>
            <Chip
              label={documentNumber}
              size="small"
              sx={{ mr: 1, bgcolor: '#FFA500', color: 'white', fontWeight: 600 }}
            />
          </Box>
        </Box>
      </DialogTitle>

      <Divider />

      <DialogContent>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
            {error}
          </Alert>
        )}

        {/* Company Info */}
        <Box sx={{ mb: 3, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
          <Typography variant="body2" color="text.secondary">
            <strong>Company:</strong> {companyName}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            <strong>Document:</strong> {documentNumber}
          </Typography>
        </Box>

        {/* To Recipients */}
        <Box sx={{ mb: 2 }}>
          <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
            To *
          </Typography>
          {contacts.length === 0 ? (
            <Alert severity="warning">
              No contacts found for this company. Please add contacts before sending emails.
            </Alert>
          ) : (
            <FormGroup>
              {contacts.map((contact) => (
                <FormControlLabel
                  key={contact.id}
                  control={
                    <Checkbox
                      checked={selectedContacts.includes(contact.email)}
                      onChange={() => handleContactToggle(contact.email)}
                      disabled={loading}
                      sx={{
                        color: '#FFA500',
                        '&.Mui-checked': {
                          color: '#FFA500',
                        },
                      }}
                    />
                  }
                  label={
                    <Box>
                      <Typography variant="body2">
                        {contact.name} ({contact.email})
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {contact.contact_type}
                        {contact.title ? ` - ${contact.title}` : ''}
                      </Typography>
                    </Box>
                  }
                />
              ))}
            </FormGroup>
          )}
        </Box>

        {/* CC Recipients */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
            CC
          </Typography>

          {/* Company contacts available for CC */}
          {availableCcContacts.length > 0 && (
            <FormGroup>
              {availableCcContacts.map((contact) => (
                <FormControlLabel
                  key={contact.id}
                  control={
                    <Checkbox
                      checked={ccContacts.includes(contact.email)}
                      onChange={() => handleCcContactToggle(contact.email)}
                      disabled={loading}
                      size="small"
                      sx={{
                        color: '#90CAF9',
                        '&.Mui-checked': {
                          color: '#2196F3',
                        },
                      }}
                    />
                  }
                  label={
                    <Box>
                      <Typography variant="body2" sx={{ fontSize: '0.85rem' }}>
                        {contact.name} ({contact.email})
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {contact.contact_type}
                        {contact.title ? ` - ${contact.title}` : ''}
                      </Typography>
                    </Box>
                  }
                />
              ))}
            </FormGroup>
          )}

          {/* External CC addresses */}
          <TextField
            fullWidth
            size="small"
            label="Additional CC emails"
            value={ccExternal}
            onChange={(e) => setCcExternal(e.target.value)}
            disabled={loading}
            placeholder="external@example.com, another@example.com"
            sx={{ mt: 1 }}
            helperText="Separate multiple emails with commas"
          />
        </Box>

        {/* Subject */}
        <Box sx={{ mb: 3 }}>
          <TextField
            fullWidth
            label="Subject *"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            disabled={loading}
            variant="outlined"
            error={!subject.trim() && !!error}
          />
        </Box>

        {/* Body */}
        <Box sx={{ mb: 2 }}>
          <TextField
            fullWidth
            label="Message *"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            disabled={loading}
            variant="outlined"
            multiline
            rows={12}
            error={!body.trim() && !!error}
            helperText="The document will be automatically attached as a PDF"
          />
        </Box>

        {/* Info note */}
        <Alert severity="info" sx={{ mt: 2 }}>
          This email will be sent from your configured email account with the PDF automatically attached.
        </Alert>
      </DialogContent>

      <Divider />

      <DialogActions sx={{ p: 2 }}>
        <Button
          onClick={handleClose}
          disabled={loading}
          startIcon={<CloseIcon />}
        >
          Cancel
        </Button>
        <Button
          onClick={handleSend}
          variant="contained"
          disabled={loading || selectedContacts.length === 0}
          startIcon={loading ? <CircularProgress size={20} /> : <SendIcon />}
          sx={{
            bgcolor: '#FFA500',
            '&:hover': {
              bgcolor: '#FF8C00',
            },
          }}
        >
          {loading ? 'Sending...' : 'Send Email'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default EmailSendDialog;
