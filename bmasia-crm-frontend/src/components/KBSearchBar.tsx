import React from 'react';
import {
  Box,
  TextField,
  InputAdornment,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  Button,
  SelectChangeEvent,
} from '@mui/material';
import { Search, Clear, FilterList } from '@mui/icons-material';
import { KBCategory, KBTag } from '../types';

interface KBSearchBarProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  selectedCategory: string;
  onCategoryChange: (category: string) => void;
  selectedTags: string[];
  onTagsChange: (tags: string[]) => void;
  selectedStatus: string;
  onStatusChange: (status: string) => void;
  sortBy: string;
  onSortChange: (sort: string) => void;
  categories: KBCategory[];
  tags: KBTag[];
  onClearFilters: () => void;
}

const KBSearchBar: React.FC<KBSearchBarProps> = ({
  searchQuery,
  onSearchChange,
  selectedCategory,
  onCategoryChange,
  selectedTags,
  onTagsChange,
  selectedStatus,
  onStatusChange,
  sortBy,
  onSortChange,
  categories,
  tags,
  onClearFilters,
}) => {
  const handleTagChange = (event: SelectChangeEvent<string[]>) => {
    const value = event.target.value;
    onTagsChange(typeof value === 'string' ? value.split(',') : value);
  };

  const handleTagDelete = (tagId: string) => {
    onTagsChange(selectedTags.filter(id => id !== tagId));
  };

  const hasActiveFilters = searchQuery || selectedCategory || selectedTags.length > 0 || selectedStatus;

  return (
    <Box sx={{ mb: 3 }}>
      {/* Search Bar */}
      <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
        <TextField
          fullWidth
          placeholder="Search articles by title, content, or tags..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <Search />
              </InputAdornment>
            ),
          }}
        />
      </Box>

      {/* Filter Row */}
      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
        <FilterList sx={{ color: 'text.secondary' }} />

        {/* Category Filter */}
        <FormControl sx={{ minWidth: 200 }} size="small">
          <InputLabel>Category</InputLabel>
          <Select
            value={selectedCategory}
            onChange={(e) => onCategoryChange(e.target.value)}
            label="Category"
          >
            <MenuItem value="">All Categories</MenuItem>
            {categories.map((category) => (
              <MenuItem key={category.id} value={category.id}>
                {category.icon && `${category.icon} `}
                {category.name} ({category.article_count})
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {/* Status Filter */}
        <FormControl sx={{ minWidth: 150 }} size="small">
          <InputLabel>Status</InputLabel>
          <Select
            value={selectedStatus}
            onChange={(e) => onStatusChange(e.target.value)}
            label="Status"
          >
            <MenuItem value="">All Statuses</MenuItem>
            <MenuItem value="draft">Draft</MenuItem>
            <MenuItem value="published">Published</MenuItem>
            <MenuItem value="archived">Archived</MenuItem>
          </Select>
        </FormControl>

        {/* Tag Filter */}
        <FormControl sx={{ minWidth: 250 }} size="small">
          <InputLabel>Tags</InputLabel>
          <Select
            multiple
            value={selectedTags}
            onChange={handleTagChange}
            label="Tags"
            renderValue={(selected) => (
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                {selected.map((tagId) => {
                  const tag = tags.find(t => t.id === tagId);
                  return tag ? (
                    <Chip
                      key={tagId}
                      label={tag.name}
                      size="small"
                      onMouseDown={(e) => e.stopPropagation()}
                      onDelete={() => handleTagDelete(tagId)}
                      sx={{
                        bgcolor: tag.color || '#FFA500',
                        color: 'white',
                      }}
                    />
                  ) : null;
                })}
              </Box>
            )}
          >
            {tags.map((tag) => (
              <MenuItem key={tag.id} value={tag.id}>
                <Chip
                  label={`${tag.name} (${tag.article_count})`}
                  size="small"
                  sx={{
                    bgcolor: tag.color || '#FFA500',
                    color: 'white',
                  }}
                />
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {/* Sort Filter */}
        <FormControl sx={{ minWidth: 180 }} size="small">
          <InputLabel>Sort By</InputLabel>
          <Select
            value={sortBy}
            onChange={(e) => onSortChange(e.target.value)}
            label="Sort By"
          >
            <MenuItem value="-created_at">Newest First</MenuItem>
            <MenuItem value="created_at">Oldest First</MenuItem>
            <MenuItem value="-updated_at">Recently Updated</MenuItem>
            <MenuItem value="-view_count">Most Viewed</MenuItem>
            <MenuItem value="-helpfulness_ratio">Most Helpful</MenuItem>
            <MenuItem value="title">Title (A-Z)</MenuItem>
            <MenuItem value="-title">Title (Z-A)</MenuItem>
          </Select>
        </FormControl>

        {/* Clear Filters Button */}
        {hasActiveFilters && (
          <Button
            variant="outlined"
            size="small"
            startIcon={<Clear />}
            onClick={onClearFilters}
            sx={{ ml: 'auto' }}
          >
            Clear Filters
          </Button>
        )}
      </Box>
    </Box>
  );
};

export default KBSearchBar;
