import React, { useState, useEffect } from 'react';
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
  IconButton,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  CircularProgress,
  Chip,
  Tooltip
} from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  CalendarMonth as CalendarIcon,
  Email as EmailIcon
} from '@mui/icons-material';
import { SeasonalTriggerDate } from '../types';
import api from '../services/api';

const HOLIDAY_TYPES = [
  { value: 'auto_seasonal_cny', label: 'Chinese New Year', countries: 'Asia' },
  { value: 'auto_seasonal_ramadan', label: 'Ramadan', countries: 'Middle East' },
  { value: 'auto_seasonal_loy_krathong', label: 'Loy Krathong', countries: 'Thailand' }
];

const Settings: React.FC = () => {
  const [triggerDates, setTriggerDates] = useState<SeasonalTriggerDate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingDate, setEditingDate] = useState<SeasonalTriggerDate | null>(null);
  const [saving, setSaving] = useState(false);

  // Form state
  const [formData, setFormData] = useState({
    holiday_type: 'auto_seasonal_cny' as SeasonalTriggerDate['holiday_type'],
    year: new Date().getFullYear(),
    trigger_date: '',
    holiday_date: '',
    notes: ''
  });

  const loadTriggerDates = async () => {
    try {
      setLoading(true);
      const data = await api.getSeasonalTriggerDates();
      setTriggerDates(data);
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load holiday dates');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTriggerDates();
  }, []);

  const handleOpenDialog = (date?: SeasonalTriggerDate) => {
    if (date) {
      setEditingDate(date);
      setFormData({
        holiday_type: date.holiday_type,
        year: date.year,
        trigger_date: date.trigger_date,
        holiday_date: date.holiday_date,
        notes: date.notes || ''
      });
    } else {
      setEditingDate(null);
      setFormData({
        holiday_type: 'auto_seasonal_cny',
        year: new Date().getFullYear(),
        trigger_date: '',
        holiday_date: '',
        notes: ''
      });
    }
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setEditingDate(null);
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      if (editingDate) {
        await api.updateSeasonalTriggerDate(editingDate.id, formData);
      } else {
        await api.createSeasonalTriggerDate(formData);
      }
      handleCloseDialog();
      loadTriggerDates();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save holiday date');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm('Are you sure you want to delete this holiday date?')) return;
    try {
      await api.deleteSeasonalTriggerDate(id);
      loadTriggerDates();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete holiday date');
    }
  };

  const getHolidayLabel = (type: string) => {
    return HOLIDAY_TYPES.find(h => h.value === type)?.label || type;
  };

  const getCountries = (type: string) => {
    return HOLIDAY_TYPES.find(h => h.value === type)?.countries || '';
  };

  const formatDate = (dateStr: string) => {
    if (!dateStr) return '';
    return new Date(dateStr).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric'
    });
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <CalendarIcon /> Settings
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Seasonal Email Trigger Dates */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Box>
            <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <EmailIcon color="primary" /> Variable Holiday Dates
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Set trigger dates for seasonal email campaigns with variable dates (CNY, Ramadan, Loy Krathong).
              Emails are sent on the trigger date, typically 2 weeks before the actual holiday.
            </Typography>
          </Box>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => handleOpenDialog()}
          >
            Add Holiday Date
          </Button>
        </Box>

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        ) : triggerDates.length === 0 ? (
          <Alert severity="info">
            No holiday dates configured yet. Add dates for CNY, Ramadan, and Loy Krathong to enable automatic seasonal email campaigns.
          </Alert>
        ) : (
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Holiday</TableCell>
                  <TableCell>Year</TableCell>
                  <TableCell>Trigger Date</TableCell>
                  <TableCell>Holiday Date</TableCell>
                  <TableCell>Target Countries</TableCell>
                  <TableCell>Notes</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {triggerDates.map((date) => (
                  <TableRow key={date.id}>
                    <TableCell>
                      <Typography fontWeight="medium">
                        {getHolidayLabel(date.holiday_type)}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip label={date.year} size="small" />
                    </TableCell>
                    <TableCell>
                      <Tooltip title="Emails sent on this date">
                        <span>{formatDate(date.trigger_date)}</span>
                      </Tooltip>
                    </TableCell>
                    <TableCell>{formatDate(date.holiday_date)}</TableCell>
                    <TableCell>
                      <Chip
                        label={getCountries(date.holiday_type)}
                        size="small"
                        variant="outlined"
                        color="primary"
                      />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 200 }} noWrap>
                        {date.notes || '-'}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      <IconButton size="small" onClick={() => handleOpenDialog(date)}>
                        <EditIcon />
                      </IconButton>
                      <IconButton size="small" color="error" onClick={() => handleDelete(date.id)}>
                        <DeleteIcon />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>

      {/* Add/Edit Dialog */}
      <Dialog open={dialogOpen} onClose={handleCloseDialog} maxWidth="sm" fullWidth>
        <DialogTitle>
          {editingDate ? 'Edit Holiday Date' : 'Add Holiday Date'}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
            <FormControl fullWidth>
              <InputLabel>Holiday</InputLabel>
              <Select
                value={formData.holiday_type}
                label="Holiday"
                onChange={(e) => setFormData({ ...formData, holiday_type: e.target.value as SeasonalTriggerDate['holiday_type'] })}
              >
                {HOLIDAY_TYPES.map((h) => (
                  <MenuItem key={h.value} value={h.value}>
                    {h.label} ({h.countries})
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <TextField
              label="Year"
              type="number"
              value={formData.year}
              onChange={(e) => setFormData({ ...formData, year: parseInt(e.target.value) })}
              fullWidth
            />

            <TextField
              label="Holiday Date"
              type="date"
              value={formData.holiday_date}
              onChange={(e) => setFormData({ ...formData, holiday_date: e.target.value })}
              fullWidth
              InputLabelProps={{ shrink: true }}
              helperText="The actual date of the holiday"
            />

            <TextField
              label="Trigger Date"
              type="date"
              value={formData.trigger_date}
              onChange={(e) => setFormData({ ...formData, trigger_date: e.target.value })}
              fullWidth
              InputLabelProps={{ shrink: true }}
              helperText="When to send the email campaign (typically 2 weeks before holiday)"
            />

            <TextField
              label="Notes"
              multiline
              rows={2}
              value={formData.notes}
              onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              fullWidth
              placeholder="e.g., CNY 2026 falls on a Sunday"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Cancel</Button>
          <Button
            onClick={handleSave}
            variant="contained"
            disabled={saving || !formData.trigger_date || !formData.holiday_date}
          >
            {saving ? <CircularProgress size={20} /> : (editingDate ? 'Save Changes' : 'Add')}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Settings;
