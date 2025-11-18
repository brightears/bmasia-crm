import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Alert,
  CircularProgress,
  ToggleButton,
  ToggleButtonGroup,
  Paper,
} from '@mui/material';
import { Close, TextFields, Code } from '@mui/icons-material';
import ApiService from '../services/api';

interface EmailTemplatePreviewProps {
  open: boolean;
  onClose: () => void;
  templateId: string;
}

const EmailTemplatePreview: React.FC<EmailTemplatePreviewProps> = ({
  open,
  onClose,
  templateId,
}) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [previewData, setPreviewData] = useState<{
    subject: string;
    body_text: string;
    body_html?: string;
  } | null>(null);
  const [viewMode, setViewMode] = useState<'text' | 'html'>('text');

  useEffect(() => {
    if (open && templateId) {
      loadPreview();
    }
  }, [open, templateId]);

  const loadPreview = async () => {
    try {
      setLoading(true);
      setError('');
      const data = await ApiService.previewEmailTemplate(templateId);
      setPreviewData(data);

      // Default to HTML view if available, otherwise text
      if (data.body_html) {
        setViewMode('html');
      } else {
        setViewMode('text');
      }
    } catch (err: any) {
      console.error('Preview error:', err);
      setError(`Failed to load preview: ${err.response?.data?.detail || err.message || 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  };

  const handleViewModeChange = (
    event: React.MouseEvent<HTMLElement>,
    newMode: 'text' | 'html' | null
  ) => {
    if (newMode !== null) {
      setViewMode(newMode);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6">Email Template Preview</Typography>
          {previewData && previewData.body_html && (
            <ToggleButtonGroup
              value={viewMode}
              exclusive
              onChange={handleViewModeChange}
              size="small"
            >
              <ToggleButton value="text">
                <TextFields sx={{ mr: 0.5 }} />
                Text
              </ToggleButton>
              <ToggleButton value="html">
                <Code sx={{ mr: 0.5 }} />
                HTML
              </ToggleButton>
            </ToggleButtonGroup>
          )}
        </Box>
      </DialogTitle>

      <DialogContent dividers>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
            <CircularProgress />
          </Box>
        ) : error ? (
          <Alert severity="error">{error}</Alert>
        ) : previewData ? (
          <Box>
            {/* Subject Preview */}
            <Paper sx={{ p: 2, mb: 2, backgroundColor: '#f5f5f5' }}>
              <Typography variant="caption" color="text.secondary" fontWeight={600}>
                SUBJECT:
              </Typography>
              <Typography variant="body1" sx={{ mt: 0.5 }}>
                {previewData.subject}
              </Typography>
            </Paper>

            {/* Body Preview */}
            <Paper sx={{ p: 2 }}>
              <Typography variant="caption" color="text.secondary" fontWeight={600} sx={{ mb: 1, display: 'block' }}>
                BODY {viewMode === 'html' ? '(HTML)' : '(TEXT)'}:
              </Typography>

              {viewMode === 'text' ? (
                <Box
                  component="pre"
                  sx={{
                    fontFamily: 'monospace',
                    fontSize: '0.875rem',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    backgroundColor: '#ffffff',
                    p: 2,
                    borderRadius: 1,
                    border: '1px solid #e0e0e0',
                  }}
                >
                  {previewData.body_text}
                </Box>
              ) : (
                <Box
                  sx={{
                    border: '1px solid #e0e0e0',
                    borderRadius: 1,
                    overflow: 'hidden',
                  }}
                >
                  <iframe
                    srcDoc={previewData.body_html}
                    title="Email HTML Preview"
                    style={{
                      width: '100%',
                      minHeight: '400px',
                      border: 'none',
                      backgroundColor: '#ffffff',
                    }}
                  />
                </Box>
              )}
            </Paper>

            {/* Info Note */}
            <Alert severity="info" sx={{ mt: 2 }}>
              <Typography variant="caption">
                This preview shows the template with sample variable placeholders. Actual emails will replace these with real data.
              </Typography>
            </Alert>
          </Box>
        ) : (
          <Alert severity="warning">No preview data available</Alert>
        )}
      </DialogContent>

      <DialogActions sx={{ p: 2 }}>
        <Button onClick={onClose} startIcon={<Close />}>
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default EmailTemplatePreview;
