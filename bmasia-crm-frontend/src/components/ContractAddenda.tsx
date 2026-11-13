import React, { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import { Add, Cancel, Download, Edit, Email, TaskAlt } from '@mui/icons-material';
import { AddendumChange, Contract, ContractAddendum } from '../types';
import ApiService from '../services/api';
import ContractAddendumForm from './ContractAddendumForm';

interface ContractAddendaProps {
  contract: Contract;
  onContractChanged?: () => void;
}

const STATUS_COLORS: Record<string, 'default' | 'info' | 'success' | 'error'> = {
  Draft: 'default', Sent: 'info', Signed: 'success', Cancelled: 'error',
};

const PARENT_STATUSES = ['Sent', 'Active', 'Renewed'];

export const describeChange = (change: AddendumChange): string => {
  switch (change.type) {
    case 'zone_add': return `Add zone ${change.name}`;
    case 'zone_remove': return `Remove zone ${change.name || ''}`.trim();
    case 'dates': {
      const parts = [change.start_date && `start ${change.start_date}`, change.end_date && `end ${change.end_date}`];
      return `New dates: ${parts.filter(Boolean).join(', ')}`;
    }
    case 'party': return change.legal_name ? `Client name: ${change.legal_name}` : 'New client address';
    case 'clause': return change.action === 'replace' ? `Replace ${change.clause_ref}` : 'Additional clause';
    default: return 'Bank details';
  }
};

const today = () => new Date().toISOString().slice(0, 10);

const ContractAddenda: React.FC<ContractAddendaProps> = ({ contract, onContractChanged }) => {
  const [addenda, setAddenda] = useState<ContractAddendum[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<ContractAddendum | null>(null);
  const [signing, setSigning] = useState<ContractAddendum | null>(null);
  const [signedDate, setSignedDate] = useState(today());
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      setLoading(true);
      setAddenda(await ApiService.getContractAddenda({ contract: contract.id }));
    } catch (err) {
      setError('Failed to load addenda');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [contract.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const eligible = PARENT_STATUSES.includes(contract.status) && !contract.contract_number.startsWith('DRAFT-');

  const changeStatus = async (addendum: ContractAddendum, status: 'Sent' | 'Signed' | 'Cancelled', date?: string) => {
    setBusy(true);
    setError('');
    try {
      await ApiService.setContractAddendumStatus(addendum.id, status, addendum.version, date);
      await load();
      if (status === 'Signed') onContractChanged?.();
      setSigning(null);
    } catch (err: any) {
      setError(err?.response?.data?.error || `Could not mark ${addendum.addendum_number} ${status}`);
    } finally {
      setBusy(false);
    }
  };

  const download = async (addendum: ContractAddendum) => {
    try {
      const blob = await ApiService.downloadContractAddendumPDF(addendum.id);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `Addendum_${addendum.addendum_number}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError('Failed to download the addendum PDF');
    }
  };

  return (
    <Paper sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">Addenda</Typography>
        <Tooltip title={eligible ? '' : 'Only a numbered Sent, Active or Renewed contract takes an addendum. Edit a Draft directly.'}>
          <span>
            <Button variant="outlined" startIcon={<Add />} disabled={!eligible}
              onClick={() => { setEditing(null); setFormOpen(true); }}>
              Create addendum
            </Button>
          </span>
        </Tooltip>
      </Box>
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}
      {loading ? (
        <CircularProgress size={24} />
      ) : addenda.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          No addenda. Use an addendum for any change after the contract was sent: zones, dates, client details, a clause, or bank details.
        </Typography>
      ) : (
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Number</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Effective</TableCell>
                <TableCell>Changes</TableCell>
                <TableCell>Value change</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {addenda.map((addendum) => (
                <TableRow key={addendum.id}>
                  <TableCell>{addendum.addendum_number}</TableCell>
                  <TableCell>
                    <Chip size="small" label={addendum.status} color={STATUS_COLORS[addendum.status]} />
                    {addendum.signed_date && (
                      <Typography variant="caption" display="block" color="text.secondary">
                        signed {addendum.signed_date}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>{addendum.effective_date}</TableCell>
                  <TableCell>{addendum.changes.map(describeChange).join('; ')}</TableCell>
                  <TableCell>
                    {addendum.value_summary
                      ? `${Number(addendum.value_summary.change) >= 0 ? '+' : ''}${addendum.value_summary.currency} ${addendum.value_summary.change}`
                      : '—'}
                  </TableCell>
                  <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
                    <Tooltip title="Download PDF">
                      <IconButton size="small" onClick={() => download(addendum)}><Download fontSize="small" /></IconButton>
                    </Tooltip>
                    {addendum.status === 'Draft' && (
                      <>
                        <Tooltip title="Edit">
                          <IconButton size="small" onClick={() => { setEditing(addendum); setFormOpen(true); }}>
                            <Edit fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Mark as Sent">
                          <IconButton size="small" disabled={busy} onClick={() => changeStatus(addendum, 'Sent')}>
                            <Email fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </>
                    )}
                    {addendum.status === 'Sent' && (
                      <Tooltip title="Mark as Signed">
                        <IconButton size="small" disabled={busy}
                          onClick={() => { setSignedDate(today()); setSigning(addendum); }}>
                          <TaskAlt fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    )}
                    {(addendum.status === 'Draft' || addendum.status === 'Sent') && (
                      <Tooltip title="Cancel addendum">
                        <IconButton size="small" disabled={busy} onClick={() => {
                          if (window.confirm(`Cancel ${addendum.addendum_number}? This cannot be undone.`)) {
                            changeStatus(addendum, 'Cancelled');
                          }
                        }}>
                          <Cancel fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <ContractAddendumForm
        open={formOpen}
        contract={contract}
        addendum={editing}
        onClose={() => setFormOpen(false)}
        onSaved={() => { setFormOpen(false); load(); }}
      />

      <Dialog open={Boolean(signing)} onClose={() => setSigning(null)} maxWidth="sm" fullWidth>
        <DialogTitle>Mark {signing?.addendum_number} as Signed</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ mb: 2 }}>
            Do this only once the client's signed copy is in hand. Signing applies the changes to
            contract {contract.contract_number} now
            {signing?.value_summary
              ? ` (value ${signing.value_summary.currency} ${signing.value_summary.before} → ${signing.value_summary.after})`
              : ''}
            . It cannot be undone; a later change needs a new addendum.
          </Typography>
          <TextField size="small" type="date" label="Signed on" InputLabelProps={{ shrink: true }}
            value={signedDate} onChange={(e) => setSignedDate(e.target.value)} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSigning(null)} disabled={busy}>Back</Button>
          <Button variant="contained" disabled={busy}
            onClick={() => signing && changeStatus(signing, 'Signed', signedDate)}>
            Mark Signed and apply
          </Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
};

export default ContractAddenda;
