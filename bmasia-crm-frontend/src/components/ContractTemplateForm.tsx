import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  GridLegacy as Grid,
  FormControlLabel,
  Switch,
  Box,
  Typography,
  Alert,
  CircularProgress,
  Paper,
  Chip,
  Tooltip,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
  SelectChangeEvent,
} from '@mui/material';
import {
  Save,
  Cancel,
  ContentCopy,
} from '@mui/icons-material';
import { ContractTemplate } from '../types';
import ApiService from '../services/api';

interface ContractTemplateFormProps {
  open: boolean;
  onClose: () => void;
  onSave: () => void;
  template: ContractTemplate | null;
}

interface FormData {
  name: string;
  template_type: string;
  pdf_format: string;
  version: string;
  content: string;
  is_active: boolean;
}

// PDF format options - determines which PDF structure is used when generating contracts
const PDF_FORMAT_OPTIONS = [
  { value: 'standard', label: 'Standard Contract' },
  { value: 'corporate_master', label: 'Corporate Master Agreement' },
  { value: 'participation', label: 'Participation Agreement' },
];

// Available variables for contract templates
const TEMPLATE_VARIABLES = [
  // Company & Client Info
  { name: 'company_name', description: 'Company name' },
  { name: 'legal_entity_name', description: 'Legal entity name (if set)' },
  { name: 'client_address', description: 'Client full address' },
  { name: 'contact_name', description: 'Primary contact name' },
  { name: 'contact_email', description: 'Primary contact email' },
  // Contract Details
  { name: 'contract_number', description: 'Contract number' },
  { name: 'start_date', description: 'Contract start date' },
  { name: 'end_date', description: 'Contract end date' },
  { name: 'agreement_date', description: 'Agreement/signature date' },
  { name: 'value', description: 'Contract value' },
  { name: 'currency', description: 'Currency (THB, USD, etc.)' },
  { name: 'billing_frequency', description: 'Billing frequency' },
  { name: 'payment_terms', description: 'Payment terms' },
  // Venue & Zones
  { name: 'venue_names', description: 'Venue/property names (comma-separated)' },
  { name: 'number_of_zones', description: 'Total number of zones' },
  // Signatories
  { name: 'client_signatory_name', description: 'Client signatory name' },
  { name: 'client_signatory_title', description: 'Client signatory title' },
];

const initialFormData: FormData = {
  name: '',
  template_type: 'preamble', // Default type, not shown in UI
  pdf_format: 'standard',
  version: '1.0',
  content: '',
  is_active: true,
};

const ContractTemplateForm: React.FC<ContractTemplateFormProps> = ({
  open,
  onClose,
  onSave,
  template,
}) => {
  const [formData, setFormData] = useState<FormData>(initialFormData);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedVar, setCopiedVar] = useState<string | null>(null);

  useEffect(() => {
    if (template) {
      setFormData({
        name: template.name || '',
        template_type: template.template_type || 'preamble',
        pdf_format: template.pdf_format || 'standard',
        version: template.version || '1.0',
        content: template.content || '',
        is_active: template.is_active ?? true,
      });
    } else {
      setFormData(initialFormData);
    }
    setError(null);
  }, [template, open]);

  const handleChange = (field: keyof FormData, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleCopyVariable = (varName: string) => {
    navigator.clipboard.writeText(`{{${varName}}}`);
    setCopiedVar(varName);
    setTimeout(() => setCopiedVar(null), 2000);
  };

  const handleInsertVariable = (varName: string) => {
    const textarea = document.getElementById('contract-template-content') as HTMLTextAreaElement;
    if (textarea) {
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      const text = formData.content;
      const variable = `{{${varName}}}`;
      const newContent = text.substring(0, start) + variable + text.substring(end);
      handleChange('content', newContent);
      // Restore focus and cursor position
      setTimeout(() => {
        textarea.focus();
        textarea.setSelectionRange(start + variable.length, start + variable.length);
      }, 0);
    }
  };

  const handleSubmit = async () => {
    if (!formData.name.trim()) {
      setError('Template name is required');
      return;
    }
    if (!formData.content.trim()) {
      setError('Template content is required');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      if (template) {
        await ApiService.updateContractTemplate(template.id, formData);
      } else {
        await ApiService.createContractTemplate(formData);
      }
      onSave();
      onClose();
    } catch (err: any) {
      console.error('Failed to save template:', err);
      setError(err.response?.data?.detail || 'Failed to save template');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        {template ? 'Edit Contract Template' : 'Create Contract Template'}
      </DialogTitle>
      <DialogContent>
        <Box sx={{ pt: 2 }}>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          <Grid container spacing={2}>
            {/* Name */}
            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Template Name"
                value={formData.name}
                onChange={(e) => handleChange('name', e.target.value)}
                required
                placeholder="e.g., SYB Thailand - Standard Contract"
              />
            </Grid>

            {/* PDF Format */}
            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <InputLabel>PDF Format</InputLabel>
                <Select
                  value={formData.pdf_format}
                  label="PDF Format"
                  onChange={(e: SelectChangeEvent) => handleChange('pdf_format', e.target.value)}
                >
                  {PDF_FORMAT_OPTIONS.map((option) => (
                    <MenuItem key={option.value} value={option.value}>
                      {option.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            {/* Version */}
            <Grid item xs={12} sm={4}>
              <TextField
                fullWidth
                label="Version"
                value={formData.version}
                onChange={(e) => handleChange('version', e.target.value)}
                placeholder="1.0"
              />
            </Grid>

            {/* Active Switch */}
            <Grid item xs={12} sm={8}>
              <Box sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={formData.is_active}
                      onChange={(e) => handleChange('is_active', e.target.checked)}
                      color="primary"
                    />
                  }
                  label="Active"
                />
              </Box>
            </Grid>

            {/* Variable Guide */}
            <Grid item xs={12}>
              <Paper variant="outlined" sx={{ p: 2, bgcolor: 'grey.50' }}>
                <Typography variant="subtitle2" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  Available Variables
                  <Typography variant="caption" color="text.secondary">
                    (click to copy, double-click to insert)
                  </Typography>
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  {TEMPLATE_VARIABLES.map((variable) => (
                    <Tooltip key={variable.name} title={variable.description} arrow>
                      <Chip
                        label={`{{${variable.name}}}`}
                        size="small"
                        variant="outlined"
                        onClick={() => handleCopyVariable(variable.name)}
                        onDoubleClick={() => handleInsertVariable(variable.name)}
                        icon={copiedVar === variable.name ? <ContentCopy fontSize="small" /> : undefined}
                        sx={{
                          cursor: 'pointer',
                          '&:hover': { bgcolor: 'primary.light', color: 'white' },
                        }}
                      />
                    </Tooltip>
                  ))}
                </Box>
              </Paper>
            </Grid>

            {/* Content */}
            <Grid item xs={12}>
              <TextField
                id="contract-template-content"
                fullWidth
                label="Template Content"
                value={formData.content}
                onChange={(e) => handleChange('content', e.target.value)}
                multiline
                rows={12}
                required
                placeholder="Enter the contract template text here. Use {{variable_name}} for dynamic content.

Formatting: Use <b>bold</b>, <i>italic</i>, <br/> for line breaks."
                sx={{
                  '& .MuiInputBase-input': {
                    fontFamily: 'monospace',
                    fontSize: '0.875rem',
                  },
                }}
              />
            </Grid>
          </Grid>
        </Box>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} startIcon={<Cancel />} disabled={loading}>
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          startIcon={loading ? <CircularProgress size={20} /> : <Save />}
          disabled={loading}
        >
          {template ? 'Update' : 'Create'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default ContractTemplateForm;
