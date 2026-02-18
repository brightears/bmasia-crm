import React from 'react';
import {
  Card,
  CardContent,
  CardActionArea,
  Typography,
  Chip,
  Box,
} from '@mui/material';
import {
  Visibility,
  ThumbUp,
  Star,
} from '@mui/icons-material';
import { KBArticle } from '../types';

interface KBArticleCardProps {
  article: KBArticle;
  onClick: (article: KBArticle) => void;
}

const KBArticleCard: React.FC<KBArticleCardProps> = ({ article, onClick }) => {
  const truncateText = (text: string, maxLength: number): string => {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength).trim() + '...';
  };

  const tags = article.tags || [];
  const visibleTags = tags.slice(0, 3);
  const remainingTagsCount = tags.length - 3;

  return (
    <Card
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        transition: 'all 0.2s',
        '&:hover': {
          transform: 'translateY(-4px)',
          boxShadow: 4,
        },
        position: 'relative',
      }}
    >
      <CardActionArea
        onClick={() => onClick(article)}
        sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', alignItems: 'stretch' }}
      >
        <CardContent sx={{ flexGrow: 1, width: '100%' }}>
          {/* Featured Badge */}
          {article.featured && (
            <Box
              sx={{
                position: 'absolute',
                top: 8,
                right: 8,
                bgcolor: '#FFA500',
                color: 'white',
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
          )}

          {/* Category Badge */}
          <Chip
            label={article.category?.name || 'Uncategorized'}
            size="small"
            sx={{
              mb: 1.5,
              bgcolor: 'rgba(255, 165, 0, 0.1)',
              color: '#FFA500',
              fontWeight: 500,
            }}
          />

          {/* Title */}
          <Typography
            variant="h6"
            component="h3"
            gutterBottom
            sx={{
              fontWeight: 600,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              minHeight: '3.5em',
            }}
          >
            {article.title}
          </Typography>

          {/* Excerpt */}
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{
              mb: 2,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              display: '-webkit-box',
              WebkitLineClamp: 3,
              WebkitBoxOrient: 'vertical',
              minHeight: '4.5em',
            }}
          >
            {article.excerpt || truncateText((article.content || '').replace(/<[^>]*>/g, ''), 150)}
          </Typography>

          {/* Tags */}
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 2 }}>
            {visibleTags.map((tag) => (
              <Chip
                key={tag.id}
                label={tag.name}
                size="small"
                variant="outlined"
                sx={{
                  borderColor: tag.color || '#FFA500',
                  color: tag.color || '#FFA500',
                  fontSize: '0.7rem',
                }}
              />
            ))}
            {remainingTagsCount > 0 && (
              <Chip
                label={`+${remainingTagsCount}`}
                size="small"
                variant="outlined"
                sx={{
                  borderColor: 'text.secondary',
                  color: 'text.secondary',
                  fontSize: '0.7rem',
                }}
              />
            )}
          </Box>

          {/* Stats */}
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <Visibility sx={{ fontSize: 16, color: 'text.secondary' }} />
              <Typography variant="caption" color="text.secondary">
                {article.view_count}
              </Typography>
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
              <ThumbUp sx={{ fontSize: 16, color: 'text.secondary' }} />
              <Typography variant="caption" color="text.secondary">
                {Math.round(article.helpfulness_ratio * 100)}%
              </Typography>
            </Box>
          </Box>
        </CardContent>
      </CardActionArea>
    </Card>
  );
};

export default KBArticleCard;
