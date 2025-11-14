import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Button,
  TextField,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  Chip,
  InputAdornment,
  Alert,
  CircularProgress,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
  GridLegacy as Grid,
} from '@mui/material';
import {
  Add,
  Search,
  Campaign,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { EmailCampaign, ApiResponse } from '../types';
import ApiService from '../services/api';

const getStatusColor = (
  status: string
): 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning' => {
  switch (status) {
    case 'draft':
      return 'default';
    case 'scheduled':
      return 'info';
    case 'sending':
      return 'warning';
    case 'sent':
      return 'success';
    case 'paused':
      return 'warning';
    case 'cancelled':
      return 'error';
    default:
      return 'default';
  }
};

const Campaigns: React.FC = () => {
  const navigate = useNavigate();
  const [campaigns, setCampaigns] = useState<EmailCampaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [totalCount, setTotalCount] = useState(0);

  const loadCampaigns = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const params: any = {
        page: page + 1,
        page_size: rowsPerPage,
      };

      if (search) params.search = search;
      if (statusFilter) params.status = statusFilter;
      if (typeFilter) params.campaign_type = typeFilter;

      console.log('Loading campaigns with params:', params);
      const response: ApiResponse<EmailCampaign> = await ApiService.getCampaigns(params);
      console.log('Campaigns API response:', response);

      setCampaigns(response.results || []);
      setTotalCount(response.count || 0);
    } catch (err: any) {
      console.error('Campaigns error:', err);
      setError(`Failed to load campaigns: ${err.response?.data?.detail || err.message || 'Unknown error'}`);
      setCampaigns([]);
      setTotalCount(0);
    } finally {
      setLoading(false);
    }
  }, [page, rowsPerPage, search, statusFilter, typeFilter]);

  useEffect(() => {
    loadCampaigns();
  }, [loadCampaigns]);

  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearch(event.target.value);
    setPage(0);
  };

  const handleChangePage = (event: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const handleViewCampaign = (id: string) => {
    navigate(`/campaigns/${id}`);
  };

  const handleCreateCampaign = () => {
    navigate('/campaigns/new');
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1">
          Email Campaigns
        </Typography>
        <Button
          variant="contained"
          startIcon={<Add />}
          onClick={handleCreateCampaign}
          sx={{ backgroundColor: '#FFA500', '&:hover': { backgroundColor: '#FF8C00' } }}
        >
          New Campaign
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Paper sx={{ mb: 2, p: 2 }}>
        <Grid container spacing={2}>
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              size="small"
              placeholder="Search campaigns..."
              value={search}
              onChange={handleSearchChange}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <Search />
                  </InputAdornment>
                ),
              }}
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <FormControl fullWidth size="small">
              <InputLabel>Status</InputLabel>
              <Select
                value={statusFilter}
                label="Status"
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setPage(0);
                }}
              >
                <MenuItem value="">All Statuses</MenuItem>
                <MenuItem value="draft">Draft</MenuItem>
                <MenuItem value="scheduled">Scheduled</MenuItem>
                <MenuItem value="sending">Sending</MenuItem>
                <MenuItem value="sent">Sent</MenuItem>
                <MenuItem value="paused">Paused</MenuItem>
                <MenuItem value="cancelled">Cancelled</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <FormControl fullWidth size="small">
              <InputLabel>Type</InputLabel>
              <Select
                value={typeFilter}
                label="Type"
                onChange={(e) => {
                  setTypeFilter(e.target.value);
                  setPage(0);
                }}
              >
                <MenuItem value="">All Types</MenuItem>
                <MenuItem value="renewal">Renewal</MenuItem>
                <MenuItem value="payment">Payment</MenuItem>
                <MenuItem value="quarterly">Quarterly</MenuItem>
                <MenuItem value="newsletter">Newsletter</MenuItem>
                <MenuItem value="promotion">Promotion</MenuItem>
                <MenuItem value="onboarding">Onboarding</MenuItem>
                <MenuItem value="engagement">Engagement</MenuItem>
              </Select>
            </FormControl>
          </Grid>
        </Grid>
      </Paper>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Campaign Name</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="right">Audience</TableCell>
              <TableCell align="right">Sent</TableCell>
              <TableCell align="right">Opened</TableCell>
              <TableCell align="right">Clicked</TableCell>
              <TableCell>Scheduled Date</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={8} align="center">
                  <CircularProgress />
                </TableCell>
              </TableRow>
            ) : campaigns.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} align="center">
                  <Box sx={{ py: 4 }}>
                    <Campaign sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
                    <Typography variant="h6" color="text.secondary">
                      No campaigns found
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {search || statusFilter || typeFilter
                        ? 'Try adjusting your filters'
                        : 'Start by creating your first campaign'}
                    </Typography>
                  </Box>
                </TableCell>
              </TableRow>
            ) : (
              campaigns.map((campaign) => (
                <TableRow
                  key={campaign.id}
                  hover
                  onClick={() => handleViewCampaign(campaign.id)}
                  sx={{ cursor: 'pointer' }}
                >
                  <TableCell>
                    <Typography variant="body2" fontWeight="medium">
                      {campaign.name}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" noWrap>
                      {campaign.subject}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={campaign.campaign_type_display}
                      size="small"
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={campaign.status_display}
                      size="small"
                      color={getStatusColor(campaign.status)}
                    />
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2">{campaign.recipients_count}</Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2">{campaign.total_sent}</Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Box>
                      <Typography variant="body2">{campaign.total_opened}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        {campaign.open_rate.toFixed(1)}%
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell align="right">
                    <Box>
                      <Typography variant="body2">{campaign.total_clicked}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        {campaign.click_rate.toFixed(1)}%
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell>
                    {campaign.scheduled_send_date ? (
                      <Typography variant="caption">
                        {new Date(campaign.scheduled_send_date).toLocaleString()}
                      </Typography>
                    ) : (
                      <Typography variant="caption" color="text.secondary">
                        -
                      </Typography>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
        <TablePagination
          rowsPerPageOptions={[10, 25, 50, 100]}
          component="div"
          count={totalCount}
          rowsPerPage={rowsPerPage}
          page={page}
          onPageChange={handleChangePage}
          onRowsPerPageChange={handleChangeRowsPerPage}
        />
      </TableContainer>
    </Box>
  );
};

export default Campaigns;
