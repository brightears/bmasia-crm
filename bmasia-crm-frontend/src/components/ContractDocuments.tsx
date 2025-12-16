import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
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
  Checkbox,
  FormControlLabel,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Chip,
  CircularProgress,
  Alert,
  Tooltip,
  Stack,
} from '@mui/material';
import {
  Upload,
  Download,
  Delete,
  Description,
  CheckCircle,
  Verified,
  Close,
} from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { ContractDocument } from '../types';
import ApiService from '../services/api';

interface ContractDocumentsProps {
  contractId: string;
}

const DOCUMENT_TYPES = [
  { value: 'generated', label: 'Generated Contract' },
  { value: 'principal_terms', label: 'Principal Terms' },
  { value: 'attachment_a', label: 'Attachment A' },
  { value: 'exhibit_d', label: 'Exhibit D' },
  { value: 'master_agreement', label: 'Master Agreement' },
  { value: 'participation_agreement', label: 'Participation Agreement' },
  { value: 'standard_terms', label: 'Standard Terms' },
  { value: 'insurance', label: 'Insurance Documents' },
  { value: 'other', label: 'Other' },
];

const ContractDocuments: React.FC<ContractDocumentsProps> = ({ contractId }) => {
  const [documents, setDocuments] = useState<ContractDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [documentToDelete, setDocumentToDelete] = useState<string | null>(null);

  // Upload form state
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadData, setUploadData] = useState({
    title: '',
    document_type: 'other' as ContractDocument['document_type'],
    is_official: false,
    is_signed: false,
    signed_date: null as Date | null,
    notes: '',
  });
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');

  useEffect(() => {
    loadDocuments();
  }, [contractId]);

  const loadDocuments = async () => {
    try {
      setLoading(true);
      setError('');
      const docs = await ApiService.getContractDocuments(contractId);
      setDocuments(docs);
    } catch (err: any) {
      setError('Failed to load documents');
      console.error('Failed to load contract documents:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files.length > 0) {
      const file = event.target.files[0];
      setUploadFile(file);

      // Auto-populate title from filename if empty
      if (!uploadData.title) {
        const nameWithoutExtension = file.name.replace(/\.[^/.]+$/, '');
        setUploadData(prev => ({ ...prev, title: nameWithoutExtension }));
      }
    }
  };

  const handleUploadSubmit = async () => {
    if (!uploadFile) {
      setUploadError('Please select a file to upload');
      return;
    }

    if (!uploadData.title.trim()) {
      setUploadError('Please enter a document title');
      return;
    }

    try {
      setUploading(true);
      setUploadError('');

      const formData = new FormData();
      formData.append('file', uploadFile);
      formData.append('contract', contractId);
      formData.append('title', uploadData.title);
      formData.append('document_type', uploadData.document_type);
      formData.append('is_official', uploadData.is_official.toString());
      formData.append('is_signed', uploadData.is_signed.toString());

      if (uploadData.is_signed && uploadData.signed_date) {
        formData.append('signed_date', uploadData.signed_date.toISOString().split('T')[0]);
      }

      if (uploadData.notes) {
        formData.append('notes', uploadData.notes);
      }

      await ApiService.uploadContractDocument(contractId, formData);

      // Reset form and reload documents
      resetUploadForm();
      setUploadDialogOpen(false);
      await loadDocuments();
    } catch (err: any) {
      setUploadError(err.response?.data?.detail || 'Failed to upload document');
      console.error('Upload error:', err);
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteClick = (documentId: string) => {
    setDocumentToDelete(documentId);
    setDeleteConfirmOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!documentToDelete) return;

    try {
      await ApiService.deleteContractDocument(documentToDelete);
      setDeleteConfirmOpen(false);
      setDocumentToDelete(null);
      await loadDocuments();
    } catch (err: any) {
      console.error('Delete error:', err);
      setError('Failed to delete document');
    }
  };

  const resetUploadForm = () => {
    setUploadFile(null);
    setUploadData({
      title: '',
      document_type: 'other',
      is_official: false,
      is_signed: false,
      signed_date: null,
      notes: '',
    });
    setUploadError('');
  };

  const handleUploadDialogClose = () => {
    setUploadDialogOpen(false);
    resetUploadForm();
  };

  const getDocumentTypeLabel = (type: string): string => {
    const docType = DOCUMENT_TYPES.find(dt => dt.value === type);
    return docType ? docType.label : type;
  };

  const getDocumentTypeColor = (type: string): 'default' | 'primary' | 'secondary' | 'success' | 'warning' | 'info' => {
    switch (type) {
      case 'generated':
      case 'master_agreement':
      case 'participation_agreement':
        return 'primary';
      case 'principal_terms':
      case 'standard_terms':
        return 'info';
      case 'insurance':
        return 'warning';
      default:
        return 'default';
    }
  };

  const formatDate = (dateString: string | undefined): string => {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleDateString();
  };

  if (loading) {
    return (
      <Paper sx={{ p: 3, textAlign: 'center' }}>
        <CircularProgress />
        <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
          Loading documents...
        </Typography>
      </Paper>
    );
  }

  return (
    <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Paper sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Description sx={{ color: '#FFA500', fontSize: 28 }} />
            <Box>
              <Typography variant="h6">Contract Documents</Typography>
              <Typography variant="body2" color="text.secondary">
                {documents.length} {documents.length === 1 ? 'document' : 'documents'} attached
              </Typography>
            </Box>
          </Box>
          <Button
            variant="contained"
            startIcon={<Upload />}
            onClick={() => setUploadDialogOpen(true)}
            sx={{ bgcolor: '#FFA500', '&:hover': { bgcolor: '#FF8C00' } }}
          >
            Upload Document
          </Button>
        </Box>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
            {error}
          </Alert>
        )}

        {documents.length === 0 ? (
          <Box sx={{ textAlign: 'center', py: 6, bgcolor: 'grey.50', borderRadius: 1 }}>
            <Description sx={{ fontSize: 80, color: 'text.secondary', mb: 2 }} />
            <Typography variant="h6" color="text.secondary" gutterBottom>
              No documents attached yet
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Upload your first contract document to get started
            </Typography>
            <Button
              variant="outlined"
              startIcon={<Upload />}
              onClick={() => setUploadDialogOpen(true)}
              sx={{ borderColor: '#FFA500', color: '#FFA500' }}
            >
              Upload Document
            </Button>
          </Box>
        ) : (
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Document Title</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Uploaded Date</TableCell>
                  <TableCell>Uploaded By</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {documents.map((doc) => (
                  <TableRow key={doc.id} hover>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Description color="action" />
                        <Box>
                          <Typography variant="body2" fontWeight="medium">
                            {doc.title}
                          </Typography>
                          {doc.notes && (
                            <Typography variant="caption" color="text.secondary">
                              {doc.notes}
                            </Typography>
                          )}
                        </Box>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={getDocumentTypeLabel(doc.document_type)}
                        size="small"
                        color={getDocumentTypeColor(doc.document_type)}
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell>
                      <Stack direction="row" spacing={1}>
                        {doc.is_official && (
                          <Tooltip title="Official Document">
                            <Chip
                              icon={<Verified />}
                              label="Official"
                              size="small"
                              color="primary"
                            />
                          </Tooltip>
                        )}
                        {doc.is_signed && (
                          <Tooltip title={`Signed on ${formatDate(doc.signed_date)}`}>
                            <Chip
                              icon={<CheckCircle />}
                              label="Signed"
                              size="small"
                              color="success"
                            />
                          </Tooltip>
                        )}
                      </Stack>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">
                        {formatDate(doc.uploaded_at)}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary">
                        {doc.uploaded_by_name || '-'}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      <Tooltip title="Download">
                        <IconButton
                          size="small"
                          onClick={() => window.open(doc.file, '_blank')}
                          sx={{ color: '#FFA500' }}
                        >
                          <Download />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Delete">
                        <IconButton
                          size="small"
                          onClick={() => handleDeleteClick(doc.id)}
                          color="error"
                        >
                          <Delete />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}

        {/* Upload Dialog */}
        <Dialog
          open={uploadDialogOpen}
          onClose={handleUploadDialogClose}
          maxWidth="sm"
          fullWidth
        >
          <DialogTitle>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Typography variant="h6">Upload Document</Typography>
              <IconButton onClick={handleUploadDialogClose}>
                <Close />
              </IconButton>
            </Box>
          </DialogTitle>
          <DialogContent dividers>
            {uploadError && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {uploadError}
              </Alert>
            )}

            <Stack spacing={3}>
              {/* File Input */}
              <Box>
                <input
                  accept=".pdf,.doc,.docx"
                  style={{ display: 'none' }}
                  id="document-file-upload"
                  type="file"
                  onChange={handleFileSelect}
                />
                <label htmlFor="document-file-upload">
                  <Button
                    variant="outlined"
                    component="span"
                    fullWidth
                    startIcon={<Upload />}
                    sx={{ py: 2 }}
                  >
                    {uploadFile ? uploadFile.name : 'Select File (PDF, DOC, DOCX)'}
                  </Button>
                </label>
              </Box>

              {/* Title */}
              <TextField
                label="Document Title *"
                fullWidth
                value={uploadData.title}
                onChange={(e) => setUploadData(prev => ({ ...prev, title: e.target.value }))}
                placeholder="Enter a descriptive title"
              />

              {/* Document Type */}
              <FormControl fullWidth>
                <InputLabel>Document Type *</InputLabel>
                <Select
                  value={uploadData.document_type}
                  onChange={(e) => setUploadData(prev => ({ ...prev, document_type: e.target.value as any }))}
                  label="Document Type *"
                >
                  {DOCUMENT_TYPES.map(type => (
                    <MenuItem key={type.value} value={type.value}>
                      {type.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              {/* Official Checkbox */}
              <FormControlLabel
                control={
                  <Checkbox
                    checked={uploadData.is_official}
                    onChange={(e) => setUploadData(prev => ({ ...prev, is_official: e.target.checked }))}
                  />
                }
                label="Mark as Official Document"
              />

              {/* Signed Checkbox and Date */}
              <Box>
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={uploadData.is_signed}
                      onChange={(e) => setUploadData(prev => ({
                        ...prev,
                        is_signed: e.target.checked,
                        signed_date: e.target.checked ? new Date() : null
                      }))}
                    />
                  }
                  label="Document is Signed"
                />
                {uploadData.is_signed && (
                  <Box sx={{ mt: 2 }}>
                    <DatePicker
                      label="Signed Date"
                      value={uploadData.signed_date}
                      onChange={(date) => setUploadData(prev => ({ ...prev, signed_date: date }))}
                      slotProps={{
                        textField: {
                          fullWidth: true,
                        },
                      }}
                    />
                  </Box>
                )}
              </Box>

              {/* Notes */}
              <TextField
                label="Notes"
                fullWidth
                multiline
                rows={3}
                value={uploadData.notes}
                onChange={(e) => setUploadData(prev => ({ ...prev, notes: e.target.value }))}
                placeholder="Add any additional notes about this document"
              />
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleUploadDialogClose}>
              Cancel
            </Button>
            <Button
              variant="contained"
              onClick={handleUploadSubmit}
              disabled={uploading || !uploadFile}
              startIcon={uploading ? <CircularProgress size={20} /> : <Upload />}
              sx={{ bgcolor: '#FFA500', '&:hover': { bgcolor: '#FF8C00' } }}
            >
              {uploading ? 'Uploading...' : 'Upload'}
            </Button>
          </DialogActions>
        </Dialog>

        {/* Delete Confirmation Dialog */}
        <Dialog
          open={deleteConfirmOpen}
          onClose={() => setDeleteConfirmOpen(false)}
          maxWidth="xs"
        >
          <DialogTitle>Confirm Delete</DialogTitle>
          <DialogContent>
            <Typography>
              Are you sure you want to delete this document? This action cannot be undone.
            </Typography>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setDeleteConfirmOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="contained"
              color="error"
              onClick={handleDeleteConfirm}
              startIcon={<Delete />}
            >
              Delete
            </Button>
          </DialogActions>
        </Dialog>
      </Paper>
    </LocalizationProvider>
  );
};

export default ContractDocuments;
