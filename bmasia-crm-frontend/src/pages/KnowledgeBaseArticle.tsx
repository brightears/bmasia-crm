import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Button,
  Chip,
  IconButton,
  Alert,
  CircularProgress,
  Paper,
  Divider,
  Card,
  CardContent,
  CardActionArea,
  Link as MuiLink,
} from '@mui/material';
import { GridLegacy as Grid } from '@mui/material';
import {
  ArrowBack,
  Visibility,
  Person,
  CalendarToday,
  Update,
  GetApp,
  Article as ArticleIcon,
} from '@mui/icons-material';
import { useNavigate, useParams } from 'react-router-dom';
import { formatDistanceToNow, format } from 'date-fns';
import DOMPurify from 'dompurify';
import { KBArticle } from '../types';
import ApiService from '../services/api';
import KBVotingButtons from '../components/KBVotingButtons';

const KnowledgeBaseArticle: React.FC = () => {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [article, setArticle] = useState<KBArticle | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadArticle = useCallback(async () => {
    if (!id) return;

    try {
      setLoading(true);
      setError('');
      const data = await ApiService.getKBArticle(id);
      setArticle(data);

      // Record view
      try {
        await ApiService.recordArticleView(id);
      } catch (err) {
        // Silent fail - view tracking is not critical
        console.error('Failed to record view:', err);
      }
    } catch (err: any) {
      console.error('Failed to load article:', err);
      setError(`Failed to load article: ${err.response?.data?.detail || err.message || 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadArticle();
  }, [loadArticle]);

  const handleVote = async (articleId: string, isHelpful: boolean) => {
    await ApiService.rateArticle(articleId, isHelpful);
    // Reload article to get updated counts
    await loadArticle();
  };

  const handleRelatedArticleClick = (relatedArticle: KBArticle) => {
    navigate(`/knowledge-base/${relatedArticle.id}`);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const formatDate = (dateString: string): string => {
    try {
      return format(new Date(dateString), 'MMMM dd, yyyy');
    } catch {
      return dateString;
    }
  };

  const formatRelativeTime = (dateString: string): string => {
    try {
      return formatDistanceToNow(new Date(dateString), { addSuffix: true });
    } catch {
      return dateString;
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress sx={{ color: '#FFA500' }} />
      </Box>
    );
  }

  if (error || !article) {
    return (
      <Box>
        <Alert severity="error" sx={{ mb: 2 }}>
          {error || 'Article not found'}
        </Alert>
        <Button startIcon={<ArrowBack />} onClick={() => navigate('/knowledge-base')}>
          Back to Knowledge Base
        </Button>
      </Box>
    );
  }

  // Sanitize HTML content
  const sanitizedContent = DOMPurify.sanitize(article.content, {
    ALLOWED_TAGS: [
      'p',
      'br',
      'strong',
      'em',
      'u',
      'h1',
      'h2',
      'h3',
      'h4',
      'h5',
      'h6',
      'ul',
      'ol',
      'li',
      'a',
      'img',
      'table',
      'thead',
      'tbody',
      'tr',
      'th',
      'td',
      'code',
      'pre',
      'blockquote',
      'hr',
    ],
    ALLOWED_ATTR: ['href', 'src', 'alt', 'title', 'class', 'id'],
  });

  return (
    <Box>
      {/* Back Button */}
      <Button
        startIcon={<ArrowBack />}
        onClick={() => navigate('/knowledge-base')}
        sx={{ mb: 3 }}
      >
        Back to Knowledge Base
      </Button>

      <Grid container spacing={3}>
        {/* Main Content */}
        <Grid item xs={12} md={9}>
          <Paper sx={{ p: 4 }}>
            {/* Header */}
            <Box sx={{ mb: 4 }}>
              {/* Category Badge */}
              <Chip
                label={article.category.name}
                sx={{
                  mb: 2,
                  bgcolor: 'rgba(255, 165, 0, 0.1)',
                  color: '#FFA500',
                  fontWeight: 500,
                }}
              />

              {/* Title */}
              <Typography variant="h3" component="h1" gutterBottom sx={{ fontWeight: 600 }}>
                {article.title}
              </Typography>

              {/* Metadata */}
              <Box
                sx={{
                  display: 'flex',
                  gap: 3,
                  flexWrap: 'wrap',
                  alignItems: 'center',
                  color: 'text.secondary',
                  mb: 2,
                }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <Person sx={{ fontSize: 18 }} />
                  <Typography variant="body2">{article.author.full_name || article.author.username}</Typography>
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <CalendarToday sx={{ fontSize: 18 }} />
                  <Typography variant="body2">{formatDate(article.published_at || article.created_at)}</Typography>
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <Update sx={{ fontSize: 18 }} />
                  <Typography variant="body2">Updated {formatRelativeTime(article.updated_at)}</Typography>
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <Visibility sx={{ fontSize: 18 }} />
                  <Typography variant="body2">{article.view_count} views</Typography>
                </Box>
              </Box>

              {/* Tags */}
              {article.tags.length > 0 && (
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                  {article.tags.map((tag) => (
                    <Chip
                      key={tag.id}
                      label={tag.name}
                      size="small"
                      sx={{
                        bgcolor: tag.color || '#FFA500',
                        color: 'white',
                      }}
                    />
                  ))}
                </Box>
              )}
            </Box>

            <Divider sx={{ mb: 4 }} />

            {/* Article Content */}
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

            {/* Attachments */}
            {article.attachments && article.attachments.length > 0 && (
              <Box sx={{ mt: 4 }}>
                <Divider sx={{ mb: 3 }} />
                <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
                  Attachments
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  {article.attachments.map((attachment: any) => (
                    <Button
                      key={attachment.id}
                      variant="outlined"
                      startIcon={<GetApp />}
                      href={attachment.file}
                      target="_blank"
                      rel="noopener noreferrer"
                      sx={{
                        justifyContent: 'flex-start',
                        borderColor: '#FFA500',
                        color: '#FFA500',
                        '&:hover': { borderColor: '#FF8C00', bgcolor: 'rgba(255, 165, 0, 0.08)' },
                      }}
                    >
                      {attachment.name} ({formatFileSize(attachment.size)})
                    </Button>
                  ))}
                </Box>
              </Box>
            )}

            <Divider sx={{ my: 4 }} />

            {/* Voting Buttons */}
            <KBVotingButtons
              articleId={article.id}
              helpfulCount={article.helpful_count}
              notHelpfulCount={article.not_helpful_count}
              onVote={handleVote}
            />
          </Paper>
        </Grid>

        {/* Sidebar */}
        <Grid item xs={12} md={3}>
          {/* Related Articles */}
          {article.related_articles && article.related_articles.length > 0 && (
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
                Related Articles
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {article.related_articles.map((relatedArticle) => (
                  <Card key={relatedArticle.id} variant="outlined">
                    <CardActionArea onClick={() => handleRelatedArticleClick(relatedArticle)}>
                      <CardContent sx={{ p: 2 }}>
                        <Typography variant="body2" fontWeight={500} gutterBottom>
                          {relatedArticle.title}
                        </Typography>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Chip
                            label={relatedArticle.category.name}
                            size="small"
                            sx={{ fontSize: '0.7rem', height: 20 }}
                          />
                          <Typography variant="caption" color="text.secondary">
                            {relatedArticle.view_count} views
                          </Typography>
                        </Box>
                      </CardContent>
                    </CardActionArea>
                  </Card>
                ))}
              </Box>
            </Paper>
          )}

          {/* Article Info */}
          <Paper sx={{ p: 2, mt: 2 }}>
            <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
              Article Info
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
              <Box>
                <Typography variant="caption" color="text.secondary" display="block">
                  Article Number
                </Typography>
                <Typography variant="body2" fontWeight={500}>
                  {article.article_number}
                </Typography>
              </Box>
              <Divider />
              <Box>
                <Typography variant="caption" color="text.secondary" display="block">
                  Published
                </Typography>
                <Typography variant="body2" fontWeight={500}>
                  {formatDate(article.published_at || article.created_at)}
                </Typography>
              </Box>
              <Divider />
              <Box>
                <Typography variant="caption" color="text.secondary" display="block">
                  Last Updated
                </Typography>
                <Typography variant="body2" fontWeight={500}>
                  {formatDate(article.updated_at)}
                </Typography>
              </Box>
              <Divider />
              <Box>
                <Typography variant="caption" color="text.secondary" display="block">
                  Views
                </Typography>
                <Typography variant="body2" fontWeight={500}>
                  {article.view_count}
                </Typography>
              </Box>
              <Divider />
              <Box>
                <Typography variant="caption" color="text.secondary" display="block">
                  Helpfulness
                </Typography>
                <Typography variant="body2" fontWeight={500}>
                  {Math.round(article.helpfulness_ratio * 100)}%
                </Typography>
              </Box>
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default KnowledgeBaseArticle;
