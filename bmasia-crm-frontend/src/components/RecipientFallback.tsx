import React, { useState } from 'react';
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Link,
  Typography,
} from '@mui/material';
import ApiService from '../services/api';
import { Contact } from '../types';
import EmailSendDialog, { EmailSendData } from './EmailSendDialog';

/**
 * The server's message when a send found no contact set to receive this kind of
 * email ("No contact of X is set to receive invoice emails. …"), or null.
 */
export function noRecipientMessage(error: any): string | null {
  const message = error?.response?.data?.error;
  return typeof message === 'string' && message.startsWith('No contact of') ? message : null;
}

/** The server's own message for a failed send, or the fallback text. */
export function sendErrorMessage(error: any, fallback: string): string {
  const message = error?.response?.data?.error;
  return typeof message === 'string' && message ? message : fallback;
}

interface RecipientFallbackProps {
  open: boolean;
  message: string;
  documentType: 'invoice' | 'quote';
  documentId: string;
  documentNumber: string;
  companyId: string;
  companyName: string;
  onClose: () => void;
  onSendEmail: (data: EmailSendData) => Promise<void>;
  onSent: () => void;
}

/**
 * Shown when a send went nowhere because no contact is set to receive this kind
 * of email: says so, links to the company's contacts, and lets the user choose
 * the recipients by hand (hand-picked recipients are always sent to).
 */
const RecipientFallback: React.FC<RecipientFallbackProps> = ({
  open,
  message,
  documentType,
  documentId,
  documentNumber,
  companyId,
  companyName,
  onClose,
  onSendEmail,
  onSent,
}) => {
  const [contacts, setContacts] = useState<Contact[] | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [loadError, setLoadError] = useState('');

  const choose = async () => {
    setLoadError('');
    try {
      const company: any = await ApiService.getCompany(companyId);
      const withEmail = ((company?.contacts || []) as Contact[]).filter(c => c.email);
      setContacts(withEmail);
      setPickerOpen(true);
    } catch {
      setLoadError('The contacts could not be loaded.');
    }
  };

  return (
    <>
      <Dialog open={open && !pickerOpen} onClose={onClose} aria-labelledby="recipient-fallback-title">
        <DialogTitle id="recipient-fallback-title">Not sent</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>{message}</Alert>
          <Typography variant="body2">
            <Link href={`/companies/${companyId}`}>Open {companyName}'s contacts</Link>
            {' '}to switch the email setting on for a contact, or choose the recipients for this
            {documentType === 'invoice' ? ' invoice' : ' quote'} now.
          </Typography>
          {loadError && <Alert severity="error" sx={{ mt: 2 }}>{loadError}</Alert>}
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>Close</Button>
          <Button variant="contained" onClick={choose}>Choose recipients</Button>
        </DialogActions>
      </Dialog>
      {pickerOpen && contacts && (
        <EmailSendDialog
          open={pickerOpen}
          onClose={() => { setPickerOpen(false); onClose(); }}
          documentType={documentType}
          documentId={documentId}
          documentNumber={documentNumber}
          companyName={companyName}
          contacts={contacts}
          onSendEmail={onSendEmail}
          onSendSuccess={() => { setPickerOpen(false); onSent(); }}
        />
      )}
    </>
  );
};

export default RecipientFallback;
