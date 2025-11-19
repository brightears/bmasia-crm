import React from 'react';
import { Box, Typography, Skeleton, TablePagination } from '@mui/material';
import { GridLegacy as Grid } from '@mui/material';
import { Article as ArticleIcon } from '@mui/icons-material';
import { KBArticle } from '../types';
import KBArticleCard from './KBArticleCard';

interface KBArticleListProps {
  articles: KBArticle[];
  loading: boolean;
  page: number;
  rowsPerPage: number;
  totalCount: number;
  onPageChange: (event: unknown, newPage: number) => void;
  onRowsPerPageChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onArticleClick: (article: KBArticle) => void;
  emptyMessage?: string;
}

const KBArticleList: React.FC<KBArticleListProps> = ({
  articles,
  loading,
  page,
  rowsPerPage,
  totalCount,
  onPageChange,
  onRowsPerPageChange,
  onArticleClick,
  emptyMessage = 'No articles found',
}) => {
  if (loading) {
    return (
      <Box>
        <Grid container spacing={3}>
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <Grid item xs={12} sm={6} md={4} key={i}>
              <Skeleton variant="rectangular" height={280} sx={{ borderRadius: 1 }} />
            </Grid>
          ))}
        </Grid>
      </Box>
    );
  }

  if (articles.length === 0) {
    return (
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          py: 8,
          textAlign: 'center',
        }}
      >
        <ArticleIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
        <Typography variant="h6" color="text.secondary" gutterBottom>
          {emptyMessage}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Try adjusting your search criteria or filters
        </Typography>
      </Box>
    );
  }

  return (
    <Box>
      <Grid container spacing={3}>
        {articles.map((article) => (
          <Grid item xs={12} sm={6} md={4} key={article.id}>
            <KBArticleCard article={article} onClick={onArticleClick} />
          </Grid>
        ))}
      </Grid>

      {/* Pagination */}
      {totalCount > rowsPerPage && (
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
          <TablePagination
            component="div"
            count={totalCount}
            page={page}
            onPageChange={onPageChange}
            rowsPerPage={rowsPerPage}
            onRowsPerPageChange={onRowsPerPageChange}
            rowsPerPageOptions={[6, 12, 24, 48]}
            labelRowsPerPage="Articles per page:"
          />
        </Box>
      )}
    </Box>
  );
};

export default KBArticleList;
