import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Paper,
  Alert,
  Drawer,
  IconButton,
  useMediaQuery,
  useTheme,
  Button,
} from '@mui/material';
import { GridLegacy as Grid } from '@mui/material';
import { Menu as MenuIcon, AddCircle, Settings as SettingsIcon } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { KBArticle, KBCategory, KBTag, ApiResponse } from '../types';
import ApiService from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import KBSearchBar from '../components/KBSearchBar';
import KBCategoryTree from '../components/KBCategoryTree';
import KBFeaturedArticles from '../components/KBFeaturedArticles';
import KBArticleList from '../components/KBArticleList';

const KnowledgeBase: React.FC = () => {
  const navigate = useNavigate();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const { user } = useAuth();

  const [articles, setArticles] = useState<KBArticle[]>([]);
  const [featuredArticles, setFeaturedArticles] = useState<KBArticle[]>([]);
  const [categories, setCategories] = useState<KBCategory[]>([]);
  const [tags, setTags] = useState<KBTag[]>([]);
  const [loading, setLoading] = useState(true);
  const [featuredLoading, setFeaturedLoading] = useState(true);
  const [error, setError] = useState('');

  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [sortBy, setSortBy] = useState('-created_at');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(12);
  const [totalCount, setTotalCount] = useState(0);

  const [sidebarOpen, setSidebarOpen] = useState(!isMobile);

  const loadCategories = useCallback(async () => {
    try {
      const response = await ApiService.getKBCategories();
      setCategories(response.data?.results || response.data || []);
    } catch (err: any) {
      console.error('Failed to load categories:', err);
    }
  }, []);

  const loadTags = useCallback(async () => {
    try {
      const response = await ApiService.getKBTags();
      setTags(response.data?.results || response.data || []);
    } catch (err: any) {
      console.error('Failed to load tags:', err);
    }
  }, []);

  const loadFeaturedArticles = useCallback(async () => {
    try {
      setFeaturedLoading(true);
      const response = await ApiService.getFeaturedArticles();
      setFeaturedArticles(response.data?.results || response.data || []);
    } catch (err: any) {
      console.error('Failed to load featured articles:', err);
    } finally {
      setFeaturedLoading(false);
    }
  }, []);

  const loadArticles = useCallback(async () => {
    try {
      setLoading(true);
      setError('');

      const params: any = {
        page: page + 1,
        page_size: rowsPerPage,
        ordering: sortBy,
        status: 'published',
      };

      if (searchQuery) {
        params.search = searchQuery;
      }

      if (selectedCategory) {
        params.category = selectedCategory;
      }

      if (selectedTags.length > 0) {
        params.tags = selectedTags.join(',');
      }

      const response: ApiResponse<KBArticle> = await ApiService.getKBArticles(params);
      setArticles(response.results || []);
      setTotalCount(response.count || 0);
    } catch (err: any) {
      console.error('Failed to load articles:', err);
      setError(`Failed to load articles: ${err.response?.data?.detail || err.message || 'Unknown error'}`);
      setArticles([]);
      setTotalCount(0);
    } finally {
      setLoading(false);
    }
  }, [page, rowsPerPage, searchQuery, selectedCategory, selectedTags, sortBy]);

  useEffect(() => {
    loadCategories();
    loadTags();
    loadFeaturedArticles();
  }, [loadCategories, loadTags, loadFeaturedArticles]);

  useEffect(() => {
    loadArticles();
  }, [loadArticles]);

  const handleSearchChange = (query: string) => {
    setSearchQuery(query);
    setPage(0);
  };

  const handleCategoryChange = (categoryId: string) => {
    setSelectedCategory(categoryId);
    setPage(0);
  };

  const handleTagsChange = (tagIds: string[]) => {
    setSelectedTags(tagIds);
    setPage(0);
  };

  const handleSortChange = (sort: string) => {
    setSortBy(sort);
    setPage(0);
  };

  const handleClearFilters = () => {
    setSearchQuery('');
    setSelectedCategory('');
    setSelectedTags([]);
    setSortBy('-created_at');
    setPage(0);
  };

  const handlePageChange = (event: unknown, newPage: number) => {
    setPage(newPage);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleRowsPerPageChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const handleArticleClick = (article: KBArticle) => {
    navigate(`/knowledge-base/${article.id}`);
  };

  const sidebarContent = (
    <Box sx={{ width: isMobile ? 280 : '100%', pt: isMobile ? 2 : 0 }}>
      <KBCategoryTree
        categories={categories}
        selectedCategoryId={selectedCategory}
        onCategorySelect={handleCategoryChange}
      />
    </Box>
  );

  // Check if user can create articles (All authenticated users)
  const canCreateArticles = !!user; // All authenticated users can create articles

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3, gap: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          {isMobile && (
            <IconButton onClick={() => setSidebarOpen(!sidebarOpen)}>
              <MenuIcon />
            </IconButton>
          )}
          <Box>
            <Typography variant="h4" component="h1" gutterBottom>
              Knowledge Base
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Find answers, tutorials, and helpful guides
            </Typography>
          </Box>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          {canCreateArticles && (
            <Button
              variant="outlined"
              startIcon={<SettingsIcon />}
              onClick={() => navigate('/knowledge-base/settings')}
            >
              Settings
            </Button>
          )}
          {canCreateArticles && (
            <Button
              variant="contained"
              startIcon={<AddCircle />}
              onClick={() => navigate('/knowledge-base/new')}
              sx={{
                bgcolor: '#FFA500',
                '&:hover': { bgcolor: '#FF8C00' },
              }}
            >
              New Article
            </Button>
          )}
        </Box>
      </Box>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* Search Bar */}
      <KBSearchBar
        searchQuery={searchQuery}
        onSearchChange={handleSearchChange}
        selectedCategory={selectedCategory}
        onCategoryChange={handleCategoryChange}
        selectedTags={selectedTags}
        onTagsChange={handleTagsChange}
        sortBy={sortBy}
        onSortChange={handleSortChange}
        categories={categories}
        tags={tags}
        onClearFilters={handleClearFilters}
      />

      <Grid container spacing={3}>
        {/* Sidebar - Desktop */}
        {!isMobile && (
          <Grid item xs={12} md={3}>
            <Paper sx={{ position: 'sticky', top: 16 }}>{sidebarContent}</Paper>
          </Grid>
        )}

        {/* Main Content */}
        <Grid item xs={12} md={isMobile ? 12 : 9}>
          {/* Featured Articles */}
          <KBFeaturedArticles
            articles={featuredArticles}
            loading={featuredLoading}
            onArticleClick={handleArticleClick}
          />

          {/* All Articles Section */}
          <Box sx={{ mb: 3 }}>
            <Typography variant="h5" gutterBottom sx={{ fontWeight: 600 }}>
              {selectedCategory
                ? categories.find(c => c.id === selectedCategory)?.name || 'Articles'
                : 'All Articles'}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {totalCount} {totalCount === 1 ? 'article' : 'articles'} found
            </Typography>
          </Box>

          {/* Article List */}
          <KBArticleList
            articles={articles}
            loading={loading}
            page={page}
            rowsPerPage={rowsPerPage}
            totalCount={totalCount}
            onPageChange={handlePageChange}
            onRowsPerPageChange={handleRowsPerPageChange}
            onArticleClick={handleArticleClick}
            emptyMessage={
              searchQuery || selectedCategory || selectedTags.length > 0
                ? 'No articles match your search criteria'
                : 'No articles available'
            }
          />
        </Grid>
      </Grid>

      {/* Mobile Sidebar Drawer */}
      {isMobile && (
        <Drawer
          anchor="left"
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          sx={{
            '& .MuiDrawer-paper': {
              width: 280,
            },
          }}
        >
          {sidebarContent}
        </Drawer>
      )}
    </Box>
  );
};

export default KnowledgeBase;
