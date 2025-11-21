import React from 'react';
import { Box, Typography, Breadcrumbs, Link as MuiLink } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { NavigateNext } from '@mui/icons-material';
import KBArticleForm from '../components/KBArticleForm';
import { KBArticle } from '../types';

const KBArticleNew: React.FC = () => {
  const navigate = useNavigate();

  const handleSave = (article: KBArticle) => {
    navigate(`/knowledge-base/${article.id}`);
  };

  const handleCancel = () => {
    navigate('/knowledge-base');
  };

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
        <Typography color="text.primary">New Article</Typography>
      </Breadcrumbs>

      {/* Form */}
      <KBArticleForm onSave={handleSave} onCancel={handleCancel} />
    </Box>
  );
};

export default KBArticleNew;
