import React, { useState, useEffect } from 'react';
import { Box, Typography, Breadcrumbs, Link as MuiLink, CircularProgress } from '@mui/material';
import { useNavigate, useParams } from 'react-router-dom';
import { NavigateNext } from '@mui/icons-material';
import KBArticleForm from '../components/KBArticleForm';
import { KBArticle } from '../types';
import ApiService from '../services/api';

const KBArticleEdit: React.FC = () => {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [article, setArticle] = useState<KBArticle | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (id) {
      loadArticle();
    }
  }, [id]);

  const loadArticle = async () => {
    try {
      setLoading(true);
      const data = await ApiService.getKBArticle(id!);
      setArticle(data);
    } catch (err: any) {
      console.error('Failed to load article:', err);
      navigate('/knowledge-base');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = (updatedArticle: KBArticle) => {
    navigate(`/knowledge-base/${updatedArticle.id}`);
  };

  const handleCancel = () => {
    navigate(`/knowledge-base/${id}`);
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress sx={{ color: '#FFA500' }} />
      </Box>
    );
  }

  return (
    <Box>
      {/* Breadcrumbs */}
      <Breadcrumbs
        separator={<NavigateNext fontSize="small" />}
        aria-label="breadcrumb"
        sx={{ mb: 3 }}
      >
        <MuiLink
          underline="hover"
          color="inherit"
          onClick={() => navigate('/knowledge-base')}
          sx={{ cursor: 'pointer' }}
        >
          Knowledge Base
        </MuiLink>
        <MuiLink
          underline="hover"
          color="inherit"
          onClick={() => navigate(`/knowledge-base/${id}`)}
          sx={{ cursor: 'pointer' }}
        >
          {article?.title || 'Article'}
        </MuiLink>
        <Typography color="text.primary">Edit</Typography>
      </Breadcrumbs>

      {/* Form */}
      <KBArticleForm articleId={id} onSave={handleSave} onCancel={handleCancel} />
    </Box>
  );
};

export default KBArticleEdit;
