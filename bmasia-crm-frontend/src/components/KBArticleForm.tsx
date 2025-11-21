import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Button,
  Paper,
  TextField,
  MenuItem,
  CircularProgress,
  Alert,
  Autocomplete,
  Chip,
  GridLegacy as Grid,
  FormControl,
  InputLabel,
  Select,
  FormControlLabel,
  Radio,
  RadioGroup,
  Checkbox,
  FormLabel,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  List,
  ListItem,
  ListItemText,
  IconButton,
  LinearProgress,
} from '@mui/material';
import { Cancel, Save, Preview, AttachFile, Delete, Close } from '@mui/icons-material';
import ReactQuill from 'react-quill-new';
import 'react-quill-new/dist/quill.snow.css';
import DOMPurify from 'dompurify';
import { KBArticle, KBCategory, KBTag } from '../types';
import ApiService from '../services/api';

interface KBArticleFormProps {
  articleId?: string;
  onSave: (article: KBArticle) => void;
  onCancel: () => void;
}

interface FormData {
  title: string;
  excerpt: string;
  category: string;
  tags: string[];
  content: string;
  status: 'draft' | 'published' | 'archived';
  visibility: 'public' | 'internal';
  featured: boolean;
}

// ReactQuill modules configuration
const quillModules = {
  toolbar: [
    [{ 'header': [1, 2, 3, false] }],
    ['bold', 'italic', 'underline', 'strike', 'blockquote', 'code-block'],
    [{ 'list': 'ordered' }, { 'list': 'bullet' }],
    ['link', 'image'],
    ['clean']
  ],
};

const KBArticleForm: React.FC<KBArticleFormProps> = ({ articleId, onSave, onCancel }) => {
  const isEditMode = Boolean(articleId);

  // Form state
  const [formData, setFormData] = useState<FormData>({
    title: '',
    excerpt: '',
    category: '',
    tags: [],
    content: '',
    status: 'draft',
    visibility: 'internal',
    featured: false,
  });

  // Data state
  const [categories, setCategories] = useState<KBCategory[]>([]);
  const [tags, setTags] = useState<KBTag[]>([]);
  const [attachments, setAttachments] = useState<File[]>([]);

  // UI state
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(isEditMode);
  const [error, setError] = useState('');
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});
  const [previewOpen, setPreviewOpen] = useState(false);
  const [autoSaving, setAutoSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  const [uploadProgress, setUploadProgress] = useState<Record<string, number>>({});

  // Auto-save timer
  const [autoSaveTimer, setAutoSaveTimer] = useState<NodeJS.Timeout | null>(null);

  // Load categories and tags
  useEffect(() => {
    loadCategories();
    loadTags();
  }, []);

  // Load existing article if editing
  useEffect(() => {
    if (isEditMode && articleId) {
      loadArticle();
    }
  }, [articleId, isEditMode]);

  // Auto-save effect
  useEffect(() => {
    if (!isEditMode || !articleId) return;

    // Clear existing timer
    if (autoSaveTimer) {
      clearTimeout(autoSaveTimer);
    }

    // Set new timer for 30 seconds
    const timer = setTimeout(() => {
      handleAutoSave();
    }, 30000);

    setAutoSaveTimer(timer);

    return () => {
      if (timer) clearTimeout(timer);
    };
  }, [formData, isEditMode, articleId]);

  const loadCategories = async () => {
    try {
      const response = await ApiService.getKBCategories();
      setCategories(response.data?.results || response.data || []);
    } catch (err: any) {
      console.error('Failed to load categories:', err);
      setError('Failed to load categories');
    }
  };

  const loadTags = async () => {
    try {
      const response = await ApiService.getKBTags();
      setTags(response.data?.results || response.data || []);
    } catch (err: any) {
      console.error('Failed to load tags:', err);
      setError('Failed to load tags');
    }
  };

  const loadArticle = async () => {
    try {
      setInitialLoading(true);
      const article: KBArticle = await ApiService.getKBArticle(articleId!);

      setFormData({
        title: article.title,
        excerpt: article.excerpt || '',
        category: article.category.id,
        tags: article.tags.map(t => t.id),
        content: article.content,
        status: article.status,
        visibility: article.visibility,
        featured: article.featured,
      });
    } catch (err: any) {
      console.error('Failed to load article:', err);
      setError(`Failed to load article: ${err.response?.data?.detail || err.message}`);
    } finally {
      setInitialLoading(false);
    }
  };

  const validate = (): boolean => {
    const errors: Record<string, string> = {};

    if (!formData.title.trim()) {
      errors.title = 'Title is required';
    } else if (formData.title.length > 255) {
      errors.title = 'Title must be 255 characters or less';
    }

    if (!formData.category) {
      errors.category = 'Category is required';
    }

    if (!formData.content.trim() || formData.content === '<p><br></p>') {
      errors.content = 'Content is required';
    }

    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleAutoSave = async () => {
    if (!isEditMode || !articleId || autoSaving) return;

    try {
      setAutoSaving(true);
      const submitData = {
        title: formData.title,
        excerpt: formData.excerpt,
        category: formData.category,
        tags: formData.tags,
        content: formData.content,
        status: formData.status,
        visibility: formData.visibility,
        featured: formData.featured,
      };

      await ApiService.updateKBArticle(articleId, submitData);
      setLastSaved(new Date());
    } catch (err: any) {
      console.error('Auto-save failed:', err);
      // Silent fail for auto-save
    } finally {
      setAutoSaving(false);
    }
  };

  const handleSubmit = async () => {
    if (!validate()) {
      return;
    }

    try {
      setLoading(true);
      setError('');

      const submitData = {
        title: formData.title,
        excerpt: formData.excerpt,
        category: formData.category,
        tags: formData.tags,
        content: formData.content,
        status: formData.status,
        visibility: formData.visibility,
        featured: formData.featured,
      };

      let savedArticle: KBArticle;

      if (isEditMode && articleId) {
        savedArticle = await ApiService.updateKBArticle(articleId, submitData);
      } else {
        savedArticle = await ApiService.createKBArticle(submitData);
      }

      // Upload attachments if any
      if (attachments.length > 0) {
        for (const file of attachments) {
          try {
            setUploadProgress(prev => ({ ...prev, [file.name]: 0 }));
            await ApiService.uploadKBAttachment(savedArticle.id, file);
            setUploadProgress(prev => ({ ...prev, [file.name]: 100 }));
          } catch (err) {
            console.error(`Failed to upload ${file.name}:`, err);
            setError(`Failed to upload ${file.name}`);
          }
        }
      }

      onSave(savedArticle);
    } catch (err: any) {
      console.error('Failed to save article:', err);
      setError(err.response?.data?.detail || 'Failed to save article');
    } finally {
      setLoading(false);
    }
  };

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      const newFiles = Array.from(event.target.files);
      setAttachments(prev => [...prev, ...newFiles]);
    }
  };

  const handleRemoveAttachment = (index: number) => {
    setAttachments(prev => prev.filter((_, i) => i !== index));
  };

  const handlePreviewOpen = () => {
    setPreviewOpen(true);
  };

  const handlePreviewClose = () => {
    setPreviewOpen(false);
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
  };

  // Show loading spinner while loading existing article
  if (initialLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress sx={{ color: '#FFA500' }} />
      </Box>
    );
  }

  // Sanitized content for preview
  const sanitizedContent = DOMPurify.sanitize(formData.content, {
    ALLOWED_TAGS: [
      'p', 'br', 'strong', 'em', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'ul', 'ol', 'li', 'a', 'img', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
      'code', 'pre', 'blockquote', 'hr',
    ],
    ALLOWED_ATTR: ['href', 'src', 'alt', 'title', 'class', 'id'],
  });

  return (
    <Box>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" component="h1" gutterBottom>
            {isEditMode ? 'Edit Article' : 'Create New Article'}
          </Typography>
          <Box display="flex" alignItems="center" gap={2}>
            <Typography variant="body2" color="text.secondary">
              {isEditMode ? 'Update knowledge base article' : 'Create a new knowledge base article'}
            </Typography>
            {autoSaving && (
              <Chip label="Auto-saving..." size="small" color="primary" />
            )}
            {lastSaved && (
              <Typography variant="caption" color="text.secondary">
                Last saved: {lastSaved.toLocaleTimeString()}
              </Typography>
            )}
          </Box>
        </Box>
        <Box display="flex" gap={1}>
          <Button
            variant="outlined"
            startIcon={<Preview />}
            onClick={handlePreviewOpen}
            disabled={loading || !formData.content}
          >
            Preview
          </Button>
          <Button
            variant="outlined"
            startIcon={<Cancel />}
            onClick={onCancel}
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
            {isEditMode ? 'Update Article' : 'Create Article'}
          </Button>
        </Box>
      </Box>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" onClose={() => setError('')} sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Form */}
      <Paper sx={{ p: 3 }}>
        <Grid container spacing={3}>
          {/* Title - Required */}
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Title *"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              error={Boolean(validationErrors.title)}
              helperText={validationErrors.title || `${formData.title.length}/255 characters`}
              required
              disabled={loading}
              inputProps={{ maxLength: 255 }}
            />
          </Grid>

          {/* Excerpt - Optional */}
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Excerpt"
              value={formData.excerpt}
              onChange={(e) => setFormData({ ...formData, excerpt: e.target.value })}
              multiline
              rows={2}
              disabled={loading}
              helperText="A brief summary (2-3 sentences)"
            />
          </Grid>

          {/* Category - Required */}
          <Grid item xs={12} sm={6}>
            <FormControl fullWidth required error={Boolean(validationErrors.category)}>
              <InputLabel>Category *</InputLabel>
              <Select
                value={formData.category}
                onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                label="Category *"
                disabled={loading}
              >
                {categories.map((category) => (
                  <MenuItem key={category.id} value={category.id}>
                    {category.name}
                  </MenuItem>
                ))}
              </Select>
              {validationErrors.category && (
                <Typography variant="caption" color="error" sx={{ mt: 0.5, ml: 1.5 }}>
                  {validationErrors.category}
                </Typography>
              )}
            </FormControl>
          </Grid>

          {/* Tags - Optional */}
          <Grid item xs={12} sm={6}>
            <Autocomplete
              multiple
              options={tags}
              value={tags.filter(t => formData.tags.includes(t.id))}
              onChange={(_, newValue) => setFormData({ ...formData, tags: newValue.map(t => t.id) })}
              getOptionLabel={(option) => option.name}
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="Tags"
                  placeholder="Select tags"
                />
              )}
              renderTags={(value, getTagProps) =>
                value.map((option, index) => (
                  <Chip
                    label={option.name}
                    {...getTagProps({ index })}
                    sx={{
                      bgcolor: option.color || '#FFA500',
                      color: 'white',
                    }}
                  />
                ))
              }
              disabled={loading}
            />
          </Grid>

          {/* Content - Required */}
          <Grid item xs={12}>
            <FormControl fullWidth error={Boolean(validationErrors.content)}>
              <FormLabel>Content *</FormLabel>
              <Box sx={{ mt: 1 }}>
                <ReactQuill
                  theme="snow"
                  value={formData.content}
                  onChange={(content) => setFormData({ ...formData, content })}
                  modules={quillModules}
                  style={{ height: '400px', marginBottom: '50px' }}
                />
              </Box>
              {validationErrors.content && (
                <Typography variant="caption" color="error" sx={{ mt: 0.5 }}>
                  {validationErrors.content}
                </Typography>
              )}
            </FormControl>
          </Grid>

          {/* Status - Required */}
          <Grid item xs={12} sm={6}>
            <FormControl component="fieldset">
              <FormLabel>Status</FormLabel>
              <RadioGroup
                row
                value={formData.status}
                onChange={(e) => setFormData({ ...formData, status: e.target.value as 'draft' | 'published' | 'archived' })}
              >
                <FormControlLabel
                  value="draft"
                  control={<Radio />}
                  label="Draft"
                  disabled={loading}
                />
                <FormControlLabel
                  value="published"
                  control={<Radio />}
                  label="Published"
                  disabled={loading}
                />
                <FormControlLabel
                  value="archived"
                  control={<Radio />}
                  label="Archived"
                  disabled={loading}
                />
              </RadioGroup>
            </FormControl>
          </Grid>

          {/* Visibility - Required */}
          <Grid item xs={12} sm={6}>
            <FormControl component="fieldset">
              <FormLabel>Visibility</FormLabel>
              <RadioGroup
                row
                value={formData.visibility}
                onChange={(e) => setFormData({ ...formData, visibility: e.target.value as 'public' | 'internal' })}
              >
                <FormControlLabel
                  value="internal"
                  control={<Radio />}
                  label="Internal"
                  disabled={loading}
                />
                <FormControlLabel
                  value="public"
                  control={<Radio />}
                  label="Public"
                  disabled={loading}
                />
              </RadioGroup>
            </FormControl>
          </Grid>

          {/* Featured - Optional */}
          <Grid item xs={12}>
            <FormControlLabel
              control={
                <Checkbox
                  checked={formData.featured}
                  onChange={(e) => setFormData({ ...formData, featured: e.target.checked })}
                  disabled={loading}
                  sx={{
                    color: '#FFA500',
                    '&.Mui-checked': { color: '#FFA500' },
                  }}
                />
              }
              label="Feature this article (display prominently on Knowledge Base home)"
            />
          </Grid>

          {/* Attachments - Optional */}
          <Grid item xs={12}>
            <Box>
              <Typography variant="subtitle2" gutterBottom>
                Attachments (Optional)
              </Typography>
              <Button
                variant="outlined"
                component="label"
                startIcon={<AttachFile />}
                disabled={loading}
              >
                Add Files
                <input
                  type="file"
                  hidden
                  multiple
                  onChange={handleFileSelect}
                />
              </Button>
              {attachments.length > 0 && (
                <List sx={{ mt: 2 }}>
                  {attachments.map((file, index) => (
                    <ListItem
                      key={index}
                      secondaryAction={
                        <IconButton edge="end" onClick={() => handleRemoveAttachment(index)} disabled={loading}>
                          <Delete />
                        </IconButton>
                      }
                      sx={{ border: '1px solid #e0e0e0', borderRadius: 1, mb: 1 }}
                    >
                      <ListItemText
                        primary={file.name}
                        secondary={formatFileSize(file.size)}
                      />
                      {uploadProgress[file.name] !== undefined && (
                        <Box sx={{ width: '100%', ml: 2 }}>
                          <LinearProgress
                            variant="determinate"
                            value={uploadProgress[file.name]}
                            sx={{
                              '& .MuiLinearProgress-bar': { bgcolor: '#FFA500' },
                            }}
                          />
                        </Box>
                      )}
                    </ListItem>
                  ))}
                </List>
              )}
            </Box>
          </Grid>

          {/* Form Actions */}
          <Grid item xs={12}>
            <Box display="flex" justifyContent="flex-end" gap={2} mt={2}>
              <Button
                variant="outlined"
                onClick={onCancel}
                disabled={loading}
                size="large"
              >
                Cancel
              </Button>
              <Button
                variant="contained"
                onClick={handleSubmit}
                disabled={loading}
                size="large"
                sx={{
                  bgcolor: '#FFA500',
                  '&:hover': { bgcolor: '#FF8C00' },
                }}
              >
                {loading && <CircularProgress size={20} sx={{ mr: 1 }} />}
                {isEditMode ? 'Update Article' : 'Create Article'}
              </Button>
            </Box>
          </Grid>
        </Grid>
      </Paper>

      {/* Preview Dialog */}
      <Dialog
        open={previewOpen}
        onClose={handlePreviewClose}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          <Box display="flex" justifyContent="space-between" alignItems="center">
            <Typography variant="h6">Article Preview</Typography>
            <IconButton onClick={handlePreviewClose}>
              <Close />
            </IconButton>
          </Box>
        </DialogTitle>
        <DialogContent dividers>
          <Typography variant="h4" gutterBottom>
            {formData.title || 'Untitled Article'}
          </Typography>
          {formData.excerpt && (
            <Typography variant="body1" color="text.secondary" paragraph>
              {formData.excerpt}
            </Typography>
          )}
          <Box
            sx={{
              '& img': { maxWidth: '100%', height: 'auto' },
              '& table': { width: '100%', borderCollapse: 'collapse' },
              '& th, & td': { border: '1px solid #ddd', padding: '8px', textAlign: 'left' },
              '& th': { bgcolor: '#f5f5f5', fontWeight: 600 },
              '& code': {
                bgcolor: '#f5f5f5',
                padding: '2px 6px',
                borderRadius: '4px',
                fontFamily: 'monospace',
              },
              '& pre': {
                bgcolor: '#f5f5f5',
                padding: '16px',
                borderRadius: '8px',
                overflow: 'auto',
              },
              '& blockquote': {
                borderLeft: '4px solid #FFA500',
                pl: 2,
                my: 2,
                color: 'text.secondary',
              },
              '& a': { color: '#FFA500', textDecoration: 'none', '&:hover': { textDecoration: 'underline' } },
            }}
            dangerouslySetInnerHTML={{ __html: sanitizedContent }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handlePreviewClose}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default KBArticleForm;
