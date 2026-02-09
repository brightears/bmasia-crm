import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Paper,
  Typography,
  GridLegacy as Grid,
  Button,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Switch,
  FormControlLabel,
  Alert,
  CircularProgress,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Divider,
  Tooltip,
  Card,
  CardContent,
  Stack,
  Breadcrumbs,
  Link as MuiLink
} from '@mui/material';
import {
  Settings as SettingsIcon,
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Label as LabelIcon,
  Folder as FolderIcon,
  ArrowBack as ArrowBackIcon
} from '@mui/icons-material';
import { KBCategory, KBTag } from '../types';
import api from '../services/api';

// Preset tag colors
const TAG_COLORS = [
  { value: '#2196F3', label: 'Blue' },
  { value: '#4CAF50', label: 'Green' },
  { value: '#FF9800', label: 'Orange' },
  { value: '#F44336', label: 'Red' },
  { value: '#9C27B0', label: 'Purple' },
  { value: '#00BCD4', label: 'Cyan' },
  { value: '#FFC107', label: 'Amber' },
  { value: '#607D8B', label: 'Gray' }
];

const KBSettings: React.FC = () => {
  const navigate = useNavigate();

  // Categories state
  const [categories, setCategories] = useState<KBCategory[]>([]);
  const [categoriesLoading, setCategoriesLoading] = useState(true);
  const [categoryDialogOpen, setCategoryDialogOpen] = useState(false);
  const [editingCategory, setEditingCategory] = useState<KBCategory | null>(null);
  const [deletingCategory, setDeletingCategory] = useState<KBCategory | null>(null);
  const [categoryFormData, setCategoryFormData] = useState({
    name: '',
    description: '',
    parent: '',
    is_active: true
  });

  // Tags state
  const [tags, setTags] = useState<KBTag[]>([]);
  const [tagsLoading, setTagsLoading] = useState(true);
  const [tagDialogOpen, setTagDialogOpen] = useState(false);
  const [editingTag, setEditingTag] = useState<KBTag | null>(null);
  const [deletingTag, setDeletingTag] = useState<KBTag | null>(null);
  const [tagFormData, setTagFormData] = useState({
    name: '',
    color: '#2196F3'
  });

  // General state
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Load categories
  const loadCategories = async () => {
    try {
      setCategoriesLoading(true);
      const response = await api.getKBCategories();
      const data = response.data?.results || response.data || [];
      setCategories(data);
      setError(null);
    } catch (err: any) {
      console.error('Failed to load categories:', err);
      setError('Failed to load categories');
    } finally {
      setCategoriesLoading(false);
    }
  };

  // Load tags
  const loadTags = async () => {
    try {
      setTagsLoading(true);
      const response = await api.getKBTags();
      const data = response.data?.results || response.data || [];
      setTags(data);
      setError(null);
    } catch (err: any) {
      console.error('Failed to load tags:', err);
      setError('Failed to load tags');
    } finally {
      setTagsLoading(false);
    }
  };

  useEffect(() => {
    loadCategories();
    loadTags();
  }, []);

  // Category handlers
  const handleOpenCategoryDialog = (category?: KBCategory) => {
    if (category) {
      setEditingCategory(category);
      setCategoryFormData({
        name: category.name,
        description: category.description || '',
        parent: category.parent || '',
        is_active: category.is_active
      });
    } else {
      setEditingCategory(null);
      setCategoryFormData({
        name: '',
        description: '',
        parent: '',
        is_active: true
      });
    }
    setCategoryDialogOpen(true);
  };

  const handleCloseCategoryDialog = () => {
    setCategoryDialogOpen(false);
    setEditingCategory(null);
  };

  const handleSaveCategory = async () => {
    if (!categoryFormData.name.trim()) {
      setError('Category name is required');
      return;
    }

    try {
      setSaving(true);
      setError(null);

      const payload: any = {
        name: categoryFormData.name.trim(),
        description: categoryFormData.description.trim(),
        is_active: categoryFormData.is_active
      };

      // Only include parent if it's not empty
      if (categoryFormData.parent) {
        payload.parent = categoryFormData.parent;
      }

      if (editingCategory) {
        await api.updateKBCategory(editingCategory.id, payload);
      } else {
        await api.createKBCategory(payload);
      }

      await loadCategories();
      handleCloseCategoryDialog();
    } catch (err: any) {
      console.error('Failed to save category:', err);
      setError(err.response?.data?.detail || 'Failed to save category');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteCategory = async () => {
    if (!deletingCategory) return;

    try {
      setSaving(true);
      setError(null);
      await api.deleteKBCategory(deletingCategory.id);
      await loadCategories();
      setDeletingCategory(null);
    } catch (err: any) {
      console.error('Failed to delete category:', err);
      setError(err.response?.data?.detail || 'Failed to delete category');
    } finally {
      setSaving(false);
    }
  };

  const handleToggleCategoryActive = async (category: KBCategory) => {
    try {
      await api.updateKBCategory(category.id, { is_active: !category.is_active });
      await loadCategories();
    } catch (err: any) {
      console.error('Failed to toggle category status:', err);
      setError('Failed to update category status');
    }
  };

  // Tag handlers
  const handleOpenTagDialog = (tag?: KBTag) => {
    if (tag) {
      setEditingTag(tag);
      setTagFormData({
        name: tag.name,
        color: tag.color
      });
    } else {
      setEditingTag(null);
      setTagFormData({
        name: '',
        color: '#2196F3'
      });
    }
    setTagDialogOpen(true);
  };

  const handleCloseTagDialog = () => {
    setTagDialogOpen(false);
    setEditingTag(null);
  };

  const handleSaveTag = async () => {
    if (!tagFormData.name.trim()) {
      setError('Tag name is required');
      return;
    }

    try {
      setSaving(true);
      setError(null);

      const payload = {
        name: tagFormData.name.trim(),
        color: tagFormData.color
      };

      if (editingTag) {
        await api.updateKBTag(editingTag.id, payload);
      } else {
        await api.createKBTag(payload);
      }

      await loadTags();
      handleCloseTagDialog();
    } catch (err: any) {
      console.error('Failed to save tag:', err);
      setError(err.response?.data?.detail || 'Failed to save tag');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteTag = async () => {
    if (!deletingTag) return;

    try {
      setSaving(true);
      setError(null);
      await api.deleteKBTag(deletingTag.id);
      await loadTags();
      setDeletingTag(null);
    } catch (err: any) {
      console.error('Failed to delete tag:', err);
      setError(err.response?.data?.detail || 'Failed to delete tag');
    } finally {
      setSaving(false);
    }
  };

  // Helper function to get parent category name
  const getParentCategoryName = (parentId: string | null): string => {
    if (!parentId) return '';
    const parent = categories.find(c => c.id === parentId);
    return parent ? parent.name : '';
  };

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ mb: 3, display: 'flex', alignItems: 'center', gap: 2 }}>
        <IconButton onClick={() => navigate('/knowledge-base')} sx={{ color: '#FFA500' }}>
          <ArrowBackIcon />
        </IconButton>
        <SettingsIcon sx={{ fontSize: 32, color: '#FFA500' }} />
        <Typography variant="h4" sx={{ fontWeight: 600 }}>
          Knowledge Base Settings
        </Typography>
      </Box>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Two-column layout */}
      <Grid container spacing={3}>
        {/* Left Section: Categories */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <FolderIcon sx={{ color: '#FFA500' }} />
                  <Typography variant="h6" sx={{ fontWeight: 600 }}>
                    Categories
                  </Typography>
                </Box>
                <Button
                  variant="contained"
                  startIcon={<AddIcon />}
                  onClick={() => handleOpenCategoryDialog()}
                  sx={{ bgcolor: '#FFA500', '&:hover': { bgcolor: '#ff8c00' } }}
                >
                  Add Category
                </Button>
              </Box>

              <Divider sx={{ mb: 2 }} />

              {categoriesLoading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                  <CircularProgress sx={{ color: '#FFA500' }} />
                </Box>
              ) : categories.length === 0 ? (
                <Box sx={{ textAlign: 'center', py: 4 }}>
                  <Typography variant="body2" color="text.secondary">
                    No categories yet. Create your first category to organize articles.
                  </Typography>
                </Box>
              ) : (
                <List>
                  {categories.map((category, index) => (
                    <React.Fragment key={category.id}>
                      <ListItem
                        sx={{
                          bgcolor: !category.is_active ? '#f5f5f5' : 'transparent',
                          borderRadius: 1,
                          mb: 1
                        }}
                      >
                        <ListItemText
                          primary={
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                              <Typography variant="body1" sx={{ fontWeight: 500 }}>
                                {category.name}
                              </Typography>
                              {category.parent && (
                                <Breadcrumbs separator="›" sx={{ fontSize: '0.875rem' }}>
                                  <Typography variant="caption" color="text.secondary">
                                    {getParentCategoryName(category.parent)}
                                  </Typography>
                                </Breadcrumbs>
                              )}
                              {!category.is_active && (
                                <Chip label="Inactive" size="small" sx={{ height: 20 }} />
                              )}
                              <Chip
                                label={`${category.article_count} articles`}
                                size="small"
                                sx={{ height: 20, bgcolor: '#FFA500', color: 'white' }}
                              />
                            </Box>
                          }
                          secondary={category.description}
                        />
                        <ListItemSecondaryAction>
                          <Stack direction="row" spacing={1} alignItems="center">
                            <Tooltip title={category.is_active ? 'Deactivate' : 'Activate'}>
                              <Switch
                                checked={category.is_active}
                                onChange={() => handleToggleCategoryActive(category)}
                                size="small"
                                sx={{
                                  '& .MuiSwitch-switchBase.Mui-checked': {
                                    color: '#FFA500',
                                  },
                                  '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                                    backgroundColor: '#FFA500',
                                  },
                                }}
                              />
                            </Tooltip>
                            <Tooltip title="Edit">
                              <IconButton
                                size="small"
                                onClick={() => handleOpenCategoryDialog(category)}
                                sx={{ color: '#FFA500' }}
                              >
                                <EditIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                            <Tooltip title="Delete">
                              <IconButton
                                size="small"
                                onClick={() => setDeletingCategory(category)}
                                disabled={category.article_count > 0}
                              >
                                <DeleteIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          </Stack>
                        </ListItemSecondaryAction>
                      </ListItem>
                      {index < categories.length - 1 && <Divider />}
                    </React.Fragment>
                  ))}
                </List>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Right Section: Tags */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <LabelIcon sx={{ color: '#FFA500' }} />
                  <Typography variant="h6" sx={{ fontWeight: 600 }}>
                    Tags
                  </Typography>
                </Box>
                <Button
                  variant="contained"
                  startIcon={<AddIcon />}
                  onClick={() => handleOpenTagDialog()}
                  sx={{ bgcolor: '#FFA500', '&:hover': { bgcolor: '#ff8c00' } }}
                >
                  Add Tag
                </Button>
              </Box>

              <Divider sx={{ mb: 2 }} />

              {tagsLoading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                  <CircularProgress sx={{ color: '#FFA500' }} />
                </Box>
              ) : tags.length === 0 ? (
                <Box sx={{ textAlign: 'center', py: 4 }}>
                  <Typography variant="body2" color="text.secondary">
                    No tags yet. Create tags to help categorize and filter articles.
                  </Typography>
                </Box>
              ) : (
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
                  {tags.map((tag) => (
                    <Card
                      key={tag.id}
                      sx={{
                        minWidth: 180,
                        borderLeft: `4px solid ${tag.color}`,
                        position: 'relative'
                      }}
                    >
                      <CardContent sx={{ pb: '16px !important' }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', mb: 1 }}>
                          <Chip
                            label={tag.name}
                            size="small"
                            sx={{
                              bgcolor: tag.color,
                              color: 'white',
                              fontWeight: 500
                            }}
                          />
                          <Box>
                            <Tooltip title="Edit">
                              <IconButton
                                size="small"
                                onClick={() => handleOpenTagDialog(tag)}
                                sx={{ color: '#FFA500' }}
                              >
                                <EditIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                            <Tooltip title="Delete">
                              <IconButton
                                size="small"
                                onClick={() => setDeletingTag(tag)}
                                disabled={tag.article_count > 0}
                              >
                                <DeleteIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          </Box>
                        </Box>
                        <Typography variant="caption" color="text.secondary">
                          {tag.article_count} {tag.article_count === 1 ? 'article' : 'articles'}
                        </Typography>
                      </CardContent>
                    </Card>
                  ))}
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Category Dialog */}
      <Dialog
        open={categoryDialogOpen}
        onClose={handleCloseCategoryDialog}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          {editingCategory ? 'Edit Category' : 'Add Category'}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
            <TextField
              label="Category Name"
              value={categoryFormData.name}
              onChange={(e) => setCategoryFormData({ ...categoryFormData, name: e.target.value })}
              fullWidth
              required
            />
            <TextField
              label="Description"
              value={categoryFormData.description}
              onChange={(e) => setCategoryFormData({ ...categoryFormData, description: e.target.value })}
              fullWidth
              multiline
              rows={3}
            />
            <FormControl fullWidth>
              <InputLabel>Parent Category</InputLabel>
              <Select
                value={categoryFormData.parent}
                onChange={(e) => setCategoryFormData({ ...categoryFormData, parent: e.target.value })}
                label="Parent Category"
              >
                <MenuItem value="">
                  <em>None (Top Level)</em>
                </MenuItem>
                {categories
                  .filter(c => !editingCategory || c.id !== editingCategory.id)
                  .map((cat) => (
                    <MenuItem key={cat.id} value={cat.id}>
                      {cat.full_path}
                    </MenuItem>
                  ))}
              </Select>
            </FormControl>
            <FormControlLabel
              control={
                <Switch
                  checked={categoryFormData.is_active}
                  onChange={(e) => setCategoryFormData({ ...categoryFormData, is_active: e.target.checked })}
                  sx={{
                    '& .MuiSwitch-switchBase.Mui-checked': {
                      color: '#FFA500',
                    },
                    '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                      backgroundColor: '#FFA500',
                    },
                  }}
                />
              }
              label="Active"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseCategoryDialog}>Cancel</Button>
          <Button
            onClick={handleSaveCategory}
            variant="contained"
            disabled={saving}
            sx={{ bgcolor: '#FFA500', '&:hover': { bgcolor: '#ff8c00' } }}
          >
            {saving ? <CircularProgress size={24} /> : editingCategory ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Tag Dialog */}
      <Dialog
        open={tagDialogOpen}
        onClose={handleCloseTagDialog}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          {editingTag ? 'Edit Tag' : 'Add Tag'}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
            <TextField
              label="Tag Name"
              value={tagFormData.name}
              onChange={(e) => setTagFormData({ ...tagFormData, name: e.target.value })}
              fullWidth
              required
            />
            <FormControl fullWidth>
              <InputLabel>Color</InputLabel>
              <Select
                value={tagFormData.color}
                onChange={(e) => setTagFormData({ ...tagFormData, color: e.target.value })}
                label="Color"
                renderValue={(value) => (
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Box
                      sx={{
                        width: 20,
                        height: 20,
                        borderRadius: '50%',
                        bgcolor: value,
                        border: '1px solid #ccc'
                      }}
                    />
                    {TAG_COLORS.find(c => c.value === value)?.label || 'Custom'}
                  </Box>
                )}
              >
                {TAG_COLORS.map((color) => (
                  <MenuItem key={color.value} value={color.value}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Box
                        sx={{
                          width: 20,
                          height: 20,
                          borderRadius: '50%',
                          bgcolor: color.value,
                          border: '1px solid #ccc'
                        }}
                      />
                      {color.label}
                    </Box>
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Preview:
              </Typography>
              <Box sx={{ mt: 1 }}>
                <Chip
                  label={tagFormData.name || 'Tag Name'}
                  sx={{
                    bgcolor: tagFormData.color,
                    color: 'white',
                    fontWeight: 500
                  }}
                />
              </Box>
            </Box>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseTagDialog}>Cancel</Button>
          <Button
            onClick={handleSaveTag}
            variant="contained"
            disabled={saving}
            sx={{ bgcolor: '#FFA500', '&:hover': { bgcolor: '#ff8c00' } }}
          >
            {saving ? <CircularProgress size={24} /> : editingTag ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Category Confirmation */}
      <Dialog
        open={!!deletingCategory}
        onClose={() => setDeletingCategory(null)}
        maxWidth="sm"
      >
        <DialogTitle>Delete Category</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete the category "{deletingCategory?.name}"?
          </Typography>
          {deletingCategory && deletingCategory.article_count > 0 && (
            <Alert severity="warning" sx={{ mt: 2 }}>
              This category has {deletingCategory.article_count} article(s). You cannot delete a category with articles.
            </Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeletingCategory(null)}>Cancel</Button>
          <Button
            onClick={handleDeleteCategory}
            variant="contained"
            color="error"
            disabled={saving || (deletingCategory?.article_count || 0) > 0}
          >
            {saving ? <CircularProgress size={24} /> : 'Delete'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Tag Confirmation */}
      <Dialog
        open={!!deletingTag}
        onClose={() => setDeletingTag(null)}
        maxWidth="sm"
      >
        <DialogTitle>Delete Tag</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete the tag "{deletingTag?.name}"?
          </Typography>
          {deletingTag && deletingTag.article_count > 0 && (
            <Alert severity="warning" sx={{ mt: 2 }}>
              This tag is used by {deletingTag.article_count} article(s). You cannot delete a tag that is in use.
            </Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeletingTag(null)}>Cancel</Button>
          <Button
            onClick={handleDeleteTag}
            variant="contained"
            color="error"
            disabled={saving || (deletingTag?.article_count || 0) > 0}
          >
            {saving ? <CircularProgress size={24} /> : 'Delete'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default KBSettings;
