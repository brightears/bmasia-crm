import React, { useState } from 'react';
import {
  Box,
  List,
  ListItemButton,
  ListItemText,
  ListItemIcon,
  Collapse,
  Chip,
  Typography,
} from '@mui/material';
import {
  ExpandLess,
  ExpandMore,
  Folder,
  FolderOpen,
  Article,
} from '@mui/icons-material';
import { KBCategory } from '../types';

interface KBCategoryTreeProps {
  categories: KBCategory[];
  selectedCategoryId: string;
  onCategorySelect: (categoryId: string) => void;
}

const KBCategoryTree: React.FC<KBCategoryTreeProps> = ({
  categories,
  selectedCategoryId,
  onCategorySelect,
}) => {
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());

  // Build category hierarchy
  const rootCategories = categories.filter(cat => !cat.parent);
  const getCategoryChildren = (parentId: string) =>
    categories.filter(cat => cat.parent === parentId);

  const toggleExpanded = (categoryId: string) => {
    const newExpanded = new Set(expandedCategories);
    if (newExpanded.has(categoryId)) {
      newExpanded.delete(categoryId);
    } else {
      newExpanded.add(categoryId);
    }
    setExpandedCategories(newExpanded);
  };

  const renderCategory = (category: KBCategory, level: number = 0) => {
    const children = getCategoryChildren(category.id);
    const hasChildren = children.length > 0;
    const isExpanded = expandedCategories.has(category.id);
    const isSelected = selectedCategoryId === category.id;

    return (
      <React.Fragment key={category.id}>
        <ListItemButton
          selected={isSelected}
          onClick={() => onCategorySelect(category.id)}
          sx={{
            pl: 2 + level * 2,
            bgcolor: isSelected ? 'rgba(255, 165, 0, 0.1)' : undefined,
            '&:hover': {
              bgcolor: isSelected ? 'rgba(255, 165, 0, 0.15)' : undefined,
            },
            '&.Mui-selected': {
              bgcolor: 'rgba(255, 165, 0, 0.1)',
              '&:hover': {
                bgcolor: 'rgba(255, 165, 0, 0.15)',
              },
            },
          }}
        >
          {hasChildren && (
            <ListItemIcon
              sx={{ minWidth: 32, cursor: 'pointer' }}
              onClick={(e) => {
                e.stopPropagation();
                toggleExpanded(category.id);
              }}
            >
              {isExpanded ? <ExpandLess /> : <ExpandMore />}
            </ListItemIcon>
          )}
          {!hasChildren && <Box sx={{ width: 32 }} />}

          <ListItemIcon sx={{ minWidth: 36 }}>
            {category.icon ? (
              <Typography component="span" sx={{ fontSize: '1.2rem' }}>
                {category.icon}
              </Typography>
            ) : hasChildren ? (
              isExpanded ? <FolderOpen /> : <Folder />
            ) : (
              <Article />
            )}
          </ListItemIcon>

          <ListItemText
            primary={category.name}
            primaryTypographyProps={{
              variant: 'body2',
              fontWeight: isSelected ? 600 : 400,
            }}
          />

          <Chip
            label={category.article_count}
            size="small"
            sx={{
              height: 20,
              fontSize: '0.7rem',
              bgcolor: isSelected ? '#FFA500' : 'rgba(0, 0, 0, 0.08)',
              color: isSelected ? 'white' : 'text.secondary',
            }}
          />
        </ListItemButton>

        {hasChildren && (
          <Collapse in={isExpanded} timeout="auto" unmountOnExit>
            <List component="div" disablePadding>
              {children
                .sort((a, b) => a.display_order - b.display_order)
                .map(child => renderCategory(child, level + 1))}
            </List>
          </Collapse>
        )}
      </React.Fragment>
    );
  };

  return (
    <Box sx={{ width: '100%' }}>
      <Typography variant="h6" sx={{ px: 2, py: 1.5, fontWeight: 600 }}>
        Categories
      </Typography>

      {/* All Categories Option */}
      <ListItemButton
        selected={!selectedCategoryId}
        onClick={() => onCategorySelect('')}
        sx={{
          pl: 2,
          bgcolor: !selectedCategoryId ? 'rgba(255, 165, 0, 0.1)' : undefined,
          '&:hover': {
            bgcolor: !selectedCategoryId ? 'rgba(255, 165, 0, 0.15)' : undefined,
          },
          '&.Mui-selected': {
            bgcolor: 'rgba(255, 165, 0, 0.1)',
            '&:hover': {
              bgcolor: 'rgba(255, 165, 0, 0.15)',
            },
          },
        }}
      >
        <ListItemIcon sx={{ minWidth: 36 }}>
          <Article />
        </ListItemIcon>
        <ListItemText
          primary="All Articles"
          primaryTypographyProps={{
            variant: 'body2',
            fontWeight: !selectedCategoryId ? 600 : 400,
          }}
        />
        <Chip
          label={categories.reduce((sum, cat) => sum + cat.article_count, 0)}
          size="small"
          sx={{
            height: 20,
            fontSize: '0.7rem',
            bgcolor: !selectedCategoryId ? '#FFA500' : 'rgba(0, 0, 0, 0.08)',
            color: !selectedCategoryId ? 'white' : 'text.secondary',
          }}
        />
      </ListItemButton>

      {/* Category Tree */}
      <List component="nav" disablePadding>
        {rootCategories
          .sort((a, b) => a.display_order - b.display_order)
          .map(category => renderCategory(category))}
      </List>
    </Box>
  );
};

export default KBCategoryTree;
