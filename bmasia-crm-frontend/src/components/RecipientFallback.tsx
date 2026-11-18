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
 * email, or null. Recognised by the reply's code (422, code "no_recipient"),
 * never by its text. Any other failure keeps the page's own fixed message.
 */
export function noRecipientMessage(error: any): string | null {
  const data = error?.response?.data;
  if (error?.response?.status !== 422 || data?.code !== 'no_recipient') {
    return null;
  }
  return typeof data.message === 'string' && data.message ? data.message : 'No contact is set to receive this email.';
}

/** The contacts the picker offers: active contacts with an email address. Inactive ones are left out. */
export function pickableContacts(contacts: Contact[]): Contact[] {
  return contacts.filter(c => c.email && c.is_active !== false);
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
      const pickable = pickableContacts((company?.contacts || []) as Contact[]);
      setContacts(pickable);
      setPickerOpen(pickable.length > 0);
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
          {contacts && contacts.length === 0 && (
            <Alert severity="info" sx={{ mt: 2 }}>
              This company has no active contact with an email address. Activate or add one on its contacts page.
            </Alert>
          )}
          {loadError && <Alert severity="error" sx={{ mt: 2 }}>{loadError}</Alert>}
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>Close</Button>
          <Button variant="contained" onClick={choose}>Choose recipients</Button>
        </DialogActions>
      </Dialog>
      {pickerOpen && contacts && contacts.length > 0 && (
        <EmailSendDialog
          standardEmail
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
