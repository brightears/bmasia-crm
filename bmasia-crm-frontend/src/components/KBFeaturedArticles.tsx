import React from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  CardActionArea,
  Chip,
  Skeleton,
} from '@mui/material';
import { Star, Visibility, ThumbUp } from '@mui/icons-material';
import { KBArticle } from '../types';

interface KBFeaturedArticlesProps {
  articles: KBArticle[];
  loading: boolean;
  onArticleClick: (article: KBArticle) => void;
}

const KBFeaturedArticles: React.FC<KBFeaturedArticlesProps> = ({
  articles,
  loading,
  onArticleClick,
}) => {
  if (loading) {
    return (
      <Box sx={{ mb: 4 }}>
        <Typography variant="h5" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Star sx={{ color: '#FFA500' }} />
          Featured Articles
        </Typography>
        <Box sx={{ display: 'flex', gap: 2, overflowX: 'auto', pb: 2 }}>
          {[1, 2, 3].map((i) => (
            <Skeleton
              key={i}
              variant="rectangular"
              width={350}
              height={200}
              sx={{ borderRadius: 2, flexShrink: 0 }}
            />
          ))}
        </Box>
      </Box>
    );
  }

  if (articles.length === 0) {
    return null;
  }

  return (
    <Box sx={{ mb: 4 }}>
      <Typography
        variant="h5"
        gutterBottom
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          fontWeight: 600,
          mb: 2,
        }}
      >
        <Star sx={{ color: '#FFA500' }} />
        Featured Articles
      </Typography>

      <Box
        sx={{
          display: 'flex',
          gap: 3,
          overflowX: 'auto',
          pb: 2,
          '&::-webkit-scrollbar': {
            height: 8,
          },
          '&::-webkit-scrollbar-track': {
            bgcolor: 'rgba(0, 0, 0, 0.05)',
            borderRadius: 4,
          },
          '&::-webkit-scrollbar-thumb': {
            bgcolor: '#FFA500',
            borderRadius: 4,
            '&:hover': {
              bgcolor: '#FF8C00',
            },
          },
        }}
      >
        {articles.map((article) => (
          <Card
            key={article.id}
            sx={{
              minWidth: 350,
              maxWidth: 350,
              flexShrink: 0,
              position: 'relative',
              transition: 'all 0.2s',
              '&:hover': {
                transform: 'translateY(-4px)',
                boxShadow: 6,
              },
              background: 'linear-gradient(135deg, #FFA500 0%, #FF8C00 100%)',
              color: 'white',
            }}
          >
            <CardActionArea onClick={() => onArticleClick(article)}>
              <CardContent>
                {/* Featured Badge */}
                <Box
                  sx={{
                    position: 'absolute',
                    top: 12,
                    right: 12,
                    bgcolor: 'rgba(255, 255, 255, 0.3)',
                    backdropFilter: 'blur(10px)',
                    borderRadius: 1,
                    px: 1,
                    py: 0.5,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 0.5,
                  }}
                >
                  <Star sx={{ fontSize: 16 }} />
                  <Typography variant="caption" fontWeight={600}>
                    Featured
                  </Typography>
                </Box>

                {/* Category */}
                <Chip
                  label={article.category?.name || 'Uncategorized'}
                  size="small"
                  sx={{
                    mb: 2,
                    bgcolor: 'rgba(255, 255, 255, 0.2)',
                    color: 'white',
                    fontWeight: 500,
                  }}
                />

                {/* Title */}
                <Typography
                  variant="h6"
                  gutterBottom
                  sx={{
                    fontWeight: 600,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    display: '-webkit-box',
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: 'vertical',
                    minHeight: '3.5em',
                    color: 'white',
                  }}
                >
                  {article.title}
                </Typography>

                {/* Excerpt */}
                <Typography
                  variant="body2"
                  sx={{
                    mb: 2,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    display: '-webkit-box',
                    WebkitLineClamp: 3,
                    WebkitBoxOrient: 'vertical',
                    color: 'rgba(255, 255, 255, 0.9)',
                  }}
                >
                  {article.excerpt ||
                    (article.content || '').replace(/<[^>]*>/g, '').substring(0, 120) + '...'}
                </Typography>

                {/* Stats */}
                <Box sx={{ display: 'flex', gap: 3, alignItems: 'center' }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <Visibility sx={{ fontSize: 16, color: 'rgba(255, 255, 255, 0.8)' }} />
                    <Typography variant="caption" sx={{ color: 'rgba(255, 255, 255, 0.8)' }}>
                      {article.view_count} views
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <ThumbUp sx={{ fontSize: 16, color: 'rgba(255, 255, 255, 0.8)' }} />
                    <Typography variant="caption" sx={{ color: 'rgba(255, 255, 255, 0.8)' }}>
                      {Math.round(article.helpfulness_ratio * 100)}% helpful
                    </Typography>
                  </Box>
                </Box>
              </CardContent>
            </CardActionArea>
          </Card>
        ))}
      </Box>
    </Box>
  );
};

export default KBFeaturedArticles;
