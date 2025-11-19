import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Button,
  Paper,
  TextField,
  FormControl,
  FormLabel,
  RadioGroup,
  FormControlLabel,
  Radio,
  GridLegacy as Grid,
  Select,
  MenuItem,
  IconButton,
  Alert,
  CircularProgress,
  Card,
  CardContent,
  Divider,
  List,
  ListItem,
  ListItemText,
  InputLabel,
} from '@mui/material';
import {
  Add,
  Delete,
  Save,
  Cancel,
  Group,
  Refresh,
} from '@mui/icons-material';
import { useNavigate, useParams } from 'react-router-dom';
import { CustomerSegment, SegmentFilterRule, Contact } from '../types';
import ApiService from '../services/api';

// Field definitions for filter builder
const COMPANY_FIELDS = [
  { value: 'name', label: 'Company Name', type: 'string' },
  { value: 'industry', label: 'Industry', type: 'string' },
  { value: 'country', label: 'Country', type: 'string' },
  { value: 'city', label: 'City', type: 'string' },
  { value: 'is_active', label: 'Is Active', type: 'boolean' },
];

const CONTACT_FIELDS = [
  { value: 'name', label: 'Contact Name', type: 'string' },
  { value: 'email', label: 'Email', type: 'string' },
  { value: 'title', label: 'Job Title', type: 'string' },
  { value: 'contact_type', label: 'Contact Type', type: 'string' },
  { value: 'is_primary', label: 'Is Primary Contact', type: 'boolean' },
  { value: 'company.name', label: 'Company Name', type: 'string' },
  { value: 'company.industry', label: 'Company Industry', type: 'string' },
  { value: 'company.country', label: 'Company Country', type: 'string' },
];

const OPERATORS = {
  string: [
    { value: 'equals', label: 'Equals' },
    { value: 'not_equals', label: 'Not Equals' },
    { value: 'contains', label: 'Contains' },
    { value: 'not_contains', label: 'Does Not Contain' },
    { value: 'starts_with', label: 'Starts With' },
    { value: 'ends_with', label: 'Ends With' },
    { value: 'is_empty', label: 'Is Empty' },
    { value: 'is_not_empty', label: 'Is Not Empty' },
  ],
  boolean: [
    { value: 'equals', label: 'Is' },
  ],
};

const SegmentForm: React.FC = () => {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const isEditMode = Boolean(id);

  // Form state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [segmentType, setSegmentType] = useState<'dynamic' | 'static'>('dynamic');
  const [status, setStatus] = useState<'active' | 'paused' | 'archived'>('active');
  const [tags, setTags] = useState('');
  const [entity, setEntity] = useState<'company' | 'contact'>('contact');
  const [matchType, setMatchType] = useState<'all' | 'any'>('all');
  const [rules, setRules] = useState<SegmentFilterRule[]>([
    { field: '', operator: 'equals', value: '' }
  ]);

  // Preview state
  const [previewCount, setPreviewCount] = useState<number | null>(null);
  const [previewContacts, setPreviewContacts] = useState<Contact[]>([]);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState('');

  // UI state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});

  // Load existing segment
  useEffect(() => {
    if (isEditMode && id) {
      loadSegment();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, isEditMode]);

  const loadSegment = async () => {
    try {
      setLoading(true);
      const segment = await ApiService.getSegment(id!);
      setName(segment.name);
      setDescription(segment.description);
      setSegmentType(segment.segment_type);
      setStatus(segment.status);
      setTags(segment.tags || '');

      if (segment.filter_criteria) {
        setEntity(segment.filter_criteria.entity);
        setMatchType(segment.filter_criteria.match_type);
        setRules(segment.filter_criteria.rules || [{ field: '', operator: 'equals', value: '' }]);
      }
    } catch (err: any) {
      console.error('Failed to load segment:', err);
      setError(`Failed to load segment: ${err.response?.data?.detail || err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Update preview when filters change
  useEffect(() => {
    if (segmentType === 'dynamic') {
      const debounceTimer = setTimeout(() => {
        updatePreview();
      }, 500);
      return () => clearTimeout(debounceTimer);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entity, matchType, rules, segmentType]);

  const updatePreview = async () => {
    // Only preview if we have at least one valid rule
    const hasValidRule = rules.some(rule => rule.field && rule.operator);
    if (!hasValidRule) {
      setPreviewCount(null);
      setPreviewContacts([]);
      return;
    }

    try {
      setPreviewLoading(true);
      setPreviewError('');
      const response = await ApiService.validateSegmentFilters({
        entity,
        match_type: matchType,
        rules: rules.filter(rule => rule.field && rule.operator),
      });

      if (response.valid) {
        setPreviewCount(response.estimated_count || 0);
        setPreviewContacts(response.preview || []);
      } else {
        setPreviewError(response.error || 'Invalid filters');
        setPreviewCount(null);
        setPreviewContacts([]);
      }
    } catch (err: any) {
      console.error('Failed to validate filters:', err);
      setPreviewError('Failed to validate filters');
      setPreviewCount(null);
      setPreviewContacts([]);
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleAddRule = () => {
    setRules([...rules, { field: '', operator: 'equals', value: '' }]);
  };

  const handleRemoveRule = (index: number) => {
    const newRules = rules.filter((_, i) => i !== index);
    setRules(newRules.length > 0 ? newRules : [{ field: '', operator: 'equals', value: '' }]);
  };

  const handleRuleChange = (index: number, field: keyof SegmentFilterRule, value: any) => {
    const newRules = [...rules];
    newRules[index] = { ...newRules[index], [field]: value };

    // Reset operator if field type changes
    if (field === 'field') {
      const fieldDef = getFieldDefinition(value);
      if (fieldDef?.type === 'boolean') {
        newRules[index].operator = 'equals';
        newRules[index].value = 'true';
      }
    }

    setRules(newRules);
  };

  const getFieldDefinition = (fieldValue: string) => {
    const fields = entity === 'company' ? COMPANY_FIELDS : CONTACT_FIELDS;
    return fields.find(f => f.value === fieldValue);
  };

  const getOperatorsForField = (fieldValue: string) => {
    const fieldDef = getFieldDefinition(fieldValue);
    return OPERATORS[fieldDef?.type as keyof typeof OPERATORS] || OPERATORS.string;
  };

  const validate = (): boolean => {
    const errors: Record<string, string> = {};

    if (!name.trim()) {
      errors.name = 'Segment name is required';
    }

    if (segmentType === 'dynamic') {
      const hasValidRule = rules.some(rule => rule.field && rule.operator);
      if (!hasValidRule) {
        errors.rules = 'At least one filter rule is required for dynamic segments';
      }
    }

    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate()) {
      return;
    }

    try {
      setLoading(true);
      setError('');

      const data: Partial<CustomerSegment> = {
        name,
        description,
        segment_type: segmentType,
        status,
        tags,
        filter_criteria: segmentType === 'dynamic' ? {
          entity,
          match_type: matchType,
          rules: rules.filter(rule => rule.field && rule.operator),
        } : { entity: 'contact', match_type: 'all', rules: [] },
      };

      if (isEditMode && id) {
        await ApiService.updateSegment(id, data);
      } else {
        await ApiService.createSegment(data);
      }

      navigate('/segments');
    } catch (err: any) {
      console.error('Failed to save segment:', err);
      setError(`Failed to save segment: ${err.response?.data?.detail || err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    navigate('/segments');
  };

  const availableFields = entity === 'company' ? COMPANY_FIELDS : CONTACT_FIELDS;

  if (loading && isEditMode) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress sx={{ color: '#FFA500' }} />
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" component="h1" gutterBottom>
            {isEditMode ? 'Edit Segment' : 'Create New Segment'}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {isEditMode ? 'Update segment configuration' : 'Define filters to create a targeted customer segment'}
          </Typography>
        </Box>
        <Box display="flex" gap={1}>
          <Button
            variant="outlined"
            startIcon={<Cancel />}
            onClick={handleCancel}
            disabled={loading}
          >
            Cancel
          </Button>
          <Button
            variant="contained"
            startIcon={loading ? <CircularProgress size={16} /> : <Save />}
            onClick={handleSubmit}
            disabled={loading}
            sx={{
              bgcolor: '#FFA500',
              '&:hover': { bgcolor: '#FF8C00' },
            }}
          >
            {isEditMode ? 'Update Segment' : 'Create Segment'}
          </Button>
        </Box>
      </Box>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" onClose={() => setError('')} sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* Left Column - Form */}
        <Grid item xs={12} md={7}>
          <Paper sx={{ p: 3 }}>
            {/* Basic Info Section */}
            <Typography variant="h6" gutterBottom>
              Basic Information
            </Typography>
            <Box sx={{ mb: 3 }}>
              <TextField
                fullWidth
                label="Segment Name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                error={Boolean(validationErrors.name)}
                helperText={validationErrors.name}
                required
                sx={{ mb: 2 }}
              />
              <TextField
                fullWidth
                label="Description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                multiline
                rows={2}
                sx={{ mb: 2 }}
              />
              <Grid container spacing={2}>
                <Grid item xs={12} sm={4}>
                  <FormControl fullWidth>
                    <InputLabel>Type</InputLabel>
                    <Select
                      value={segmentType}
                      onChange={(e) => setSegmentType(e.target.value as 'dynamic' | 'static')}
                      label="Type"
                      disabled={isEditMode}
                    >
                      <MenuItem value="dynamic">Dynamic</MenuItem>
                      <MenuItem value="static">Static</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>
                <Grid item xs={12} sm={4}>
                  <FormControl fullWidth>
                    <InputLabel>Status</InputLabel>
                    <Select
                      value={status}
                      onChange={(e) => setStatus(e.target.value as 'active' | 'paused' | 'archived')}
                      label="Status"
                    >
                      <MenuItem value="active">Active</MenuItem>
                      <MenuItem value="paused">Paused</MenuItem>
                      <MenuItem value="archived">Archived</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>
                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    label="Tags (comma-separated)"
                    value={tags}
                    onChange={(e) => setTags(e.target.value)}
                    placeholder="tag1, tag2"
                  />
                </Grid>
              </Grid>
            </Box>

            {/* Filter Builder Section - Only for Dynamic */}
            {segmentType === 'dynamic' && (
              <>
                <Divider sx={{ my: 3 }} />
                <Typography variant="h6" gutterBottom>
                  Filter Criteria
                </Typography>

                {validationErrors.rules && (
                  <Alert severity="error" sx={{ mb: 2 }}>
                    {validationErrors.rules}
                  </Alert>
                )}

                {/* Entity Selector */}
                <FormControl component="fieldset" sx={{ mb: 2 }}>
                  <FormLabel component="legend">Target Entity</FormLabel>
                  <RadioGroup
                    row
                    value={entity}
                    onChange={(e) => {
                      setEntity(e.target.value as 'company' | 'contact');
                      setRules([{ field: '', operator: 'equals', value: '' }]);
                    }}
                  >
                    <FormControlLabel value="contact" control={<Radio />} label="Contacts" />
                    <FormControlLabel value="company" control={<Radio />} label="Companies" />
                  </RadioGroup>
                </FormControl>

                {/* Match Type Selector */}
                <FormControl component="fieldset" sx={{ mb: 3 }}>
                  <FormLabel component="legend">Match Conditions</FormLabel>
                  <RadioGroup
                    row
                    value={matchType}
                    onChange={(e) => setMatchType(e.target.value as 'all' | 'any')}
                  >
                    <FormControlLabel value="all" control={<Radio />} label="All (AND)" />
                    <FormControlLabel value="any" control={<Radio />} label="Any (OR)" />
                  </RadioGroup>
                </FormControl>

                {/* Rules */}
                <Box>
                  {rules.map((rule, index) => (
                    <Card key={index} variant="outlined" sx={{ mb: 2 }}>
                      <CardContent>
                        <Grid container spacing={2} alignItems="center">
                          <Grid item xs={12} sm={4}>
                            <FormControl fullWidth size="small">
                              <InputLabel>Field</InputLabel>
                              <Select
                                value={rule.field}
                                onChange={(e) => handleRuleChange(index, 'field', e.target.value)}
                                label="Field"
                              >
                                {availableFields.map((field) => (
                                  <MenuItem key={field.value} value={field.value}>
                                    {field.label}
                                  </MenuItem>
                                ))}
                              </Select>
                            </FormControl>
                          </Grid>
                          <Grid item xs={12} sm={3}>
                            <FormControl fullWidth size="small">
                              <InputLabel>Operator</InputLabel>
                              <Select
                                value={rule.operator}
                                onChange={(e) => handleRuleChange(index, 'operator', e.target.value)}
                                label="Operator"
                                disabled={!rule.field}
                              >
                                {getOperatorsForField(rule.field).map((op) => (
                                  <MenuItem key={op.value} value={op.value}>
                                    {op.label}
                                  </MenuItem>
                                ))}
                              </Select>
                            </FormControl>
                          </Grid>
                          <Grid item xs={12} sm={4}>
                            {getFieldDefinition(rule.field)?.type === 'boolean' ? (
                              <FormControl fullWidth size="small">
                                <InputLabel>Value</InputLabel>
                                <Select
                                  value={rule.value}
                                  onChange={(e) => handleRuleChange(index, 'value', e.target.value)}
                                  label="Value"
                                >
                                  <MenuItem value="true">Yes</MenuItem>
                                  <MenuItem value="false">No</MenuItem>
                                </Select>
                              </FormControl>
                            ) : (
                              <TextField
                                fullWidth
                                size="small"
                                label="Value"
                                value={rule.value}
                                onChange={(e) => handleRuleChange(index, 'value', e.target.value)}
                                disabled={!rule.field || rule.operator === 'is_empty' || rule.operator === 'is_not_empty'}
                              />
                            )}
                          </Grid>
                          <Grid item xs={12} sm={1}>
                            <IconButton
                              size="small"
                              color="error"
                              onClick={() => handleRemoveRule(index)}
                              disabled={rules.length === 1}
                            >
                              <Delete />
                            </IconButton>
                          </Grid>
                        </Grid>
                      </CardContent>
                    </Card>
                  ))}
                </Box>

                <Button
                  startIcon={<Add />}
                  onClick={handleAddRule}
                  variant="outlined"
                  size="small"
                >
                  Add Rule
                </Button>
              </>
            )}
          </Paper>
        </Grid>

        {/* Right Column - Preview */}
        <Grid item xs={12} md={5}>
          <Paper sx={{ p: 3, position: 'sticky', top: 20 }}>
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
              <Typography variant="h6">
                Live Preview
              </Typography>
              {segmentType === 'dynamic' && (
                <IconButton size="small" onClick={updatePreview}>
                  <Refresh />
                </IconButton>
              )}
            </Box>

            {segmentType === 'static' ? (
              <Alert severity="info">
                Static segments require manual member addition after creation.
              </Alert>
            ) : (
              <>
                {previewLoading ? (
                  <Box display="flex" justifyContent="center" py={4}>
                    <CircularProgress size={32} sx={{ color: '#FFA500' }} />
                  </Box>
                ) : previewError ? (
                  <Alert severity="error">{previewError}</Alert>
                ) : previewCount !== null ? (
                  <>
                    <Box
                      sx={{
                        p: 2,
                        bgcolor: '#FFF8E1',
                        borderRadius: 1,
                        mb: 2,
                        textAlign: 'center',
                      }}
                    >
                      <Typography variant="h3" sx={{ color: '#FFA500', fontWeight: 'bold' }}>
                        {previewCount.toLocaleString()}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Estimated Members
                      </Typography>
                    </Box>

                    {previewContacts.length > 0 && (
                      <>
                        <Typography variant="subtitle2" gutterBottom sx={{ mt: 2 }}>
                          Sample Members (up to 5):
                        </Typography>
                        <List dense>
                          {previewContacts.slice(0, 5).map((contact) => (
                            <ListItem key={contact.id} divider>
                              <ListItemText
                                primary={contact.name}
                                secondary={
                                  <>
                                    {contact.email}
                                    {contact.company_name && (
                                      <Typography
                                        component="span"
                                        variant="body2"
                                        color="text.secondary"
                                        display="block"
                                      >
                                        {contact.company_name}
                                      </Typography>
                                    )}
                                  </>
                                }
                              />
                            </ListItem>
                          ))}
                        </List>
                      </>
                    )}
                  </>
                ) : (
                  <Box display="flex" flexDirection="column" alignItems="center" py={4}>
                    <Group sx={{ fontSize: 60, color: 'text.secondary', mb: 2 }} />
                    <Typography variant="body2" color="text.secondary" textAlign="center">
                      Add filter rules to see estimated member count
                    </Typography>
                  </Box>
                )}
              </>
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default SegmentForm;
