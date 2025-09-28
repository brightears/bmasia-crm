import React, { useState } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Avatar,
  Chip,
  LinearProgress,
  IconButton,
  Tooltip,
  TableSortLabel,
  Menu,
  MenuItem,
} from '@mui/material';
import {
  MoreVert,
  Star,
  TrendingUp,
  TrendingDown,
  Remove,
} from '@mui/icons-material';

interface AgentPerformance {
  id: string;
  name: string;
  avatar: string;
  ticketsAssigned: number;
  ticketsResolved: number;
  avgResolutionTime: number;
  firstResponseTime: number;
  customerSatisfaction: number;
  workload: number;
  status: 'available' | 'busy' | 'away';
}

interface AgentPerformanceTableProps {
  data: AgentPerformance[];
  loading?: boolean;
}

type SortKey = keyof AgentPerformance;
type SortOrder = 'asc' | 'desc';

const TECH_SUPPORT_COLORS = {
  primary: '#1976d2',
  secondary: '#42a5f5',
  accent: '#64b5f6',
  success: '#4caf50',
  warning: '#ff9800',
  error: '#f44336',
  info: '#2196f3',
};

const AgentPerformanceTable: React.FC<AgentPerformanceTableProps> = ({
  data,
  loading = false
}) => {
  const [sortKey, setSortKey] = useState<SortKey>('customerSatisfaction');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortOrder('desc');
    }
  };

  const sortedData = [...data].sort((a, b) => {
    let aValue = a[sortKey];
    let bValue = b[sortKey];

    // Handle string values
    if (typeof aValue === 'string') {
      aValue = aValue.toLowerCase();
      bValue = (bValue as string).toLowerCase();
    }

    if (sortOrder === 'asc') {
      return aValue < bValue ? -1 : aValue > bValue ? 1 : 0;
    } else {
      return aValue > bValue ? -1 : aValue < bValue ? 1 : 0;
    }
  });

  const getStatusColor = (status: AgentPerformance['status']) => {
    switch (status) {
      case 'available':
        return 'success';
      case 'busy':
        return 'warning';
      case 'away':
        return 'error';
      default:
        return 'default';
    }
  };

  const getWorkloadColor = (workload: number) => {
    if (workload >= 90) return TECH_SUPPORT_COLORS.error;
    if (workload >= 75) return TECH_SUPPORT_COLORS.warning;
    if (workload >= 50) return TECH_SUPPORT_COLORS.info;
    return TECH_SUPPORT_COLORS.success;
  };

  const getResolutionRate = (assigned: number, resolved: number) => {
    return assigned > 0 ? (resolved / assigned) * 100 : 0;
  };

  const formatTime = (hours: number) => {
    if (hours < 1) {
      return `${Math.round(hours * 60)}m`;
    }
    return `${hours.toFixed(1)}h`;
  };

  const handleMenuClick = (event: React.MouseEvent<HTMLElement>, agentId: string) => {
    setAnchorEl(event.currentTarget);
    setSelectedAgent(agentId);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setSelectedAgent(null);
  };

  if (loading) {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom sx={{ color: TECH_SUPPORT_COLORS.primary }}>
            Agent Performance Metrics
          </Typography>
          <Box sx={{ height: 300, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Typography color="text.secondary">Loading agent performance data...</Typography>
          </Box>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom sx={{ color: TECH_SUPPORT_COLORS.primary }}>
          Agent Performance Metrics
        </Typography>

        <TableContainer component={Paper} elevation={0} sx={{ maxHeight: 400 }}>
          <Table stickyHeader size="small">
            <TableHead>
              <TableRow>
                <TableCell>Agent</TableCell>
                <TableCell align="center">
                  <TableSortLabel
                    active={sortKey === 'ticketsAssigned'}
                    direction={sortKey === 'ticketsAssigned' ? sortOrder : 'asc'}
                    onClick={() => handleSort('ticketsAssigned')}
                  >
                    Assigned
                  </TableSortLabel>
                </TableCell>
                <TableCell align="center">
                  <TableSortLabel
                    active={sortKey === 'ticketsResolved'}
                    direction={sortKey === 'ticketsResolved' ? sortOrder : 'asc'}
                    onClick={() => handleSort('ticketsResolved')}
                  >
                    Resolved
                  </TableSortLabel>
                </TableCell>
                <TableCell align="center">Resolution Rate</TableCell>
                <TableCell align="center">
                  <TableSortLabel
                    active={sortKey === 'avgResolutionTime'}
                    direction={sortKey === 'avgResolutionTime' ? sortOrder : 'asc'}
                    onClick={() => handleSort('avgResolutionTime')}
                  >
                    Avg Time
                  </TableSortLabel>
                </TableCell>
                <TableCell align="center">
                  <TableSortLabel
                    active={sortKey === 'firstResponseTime'}
                    direction={sortKey === 'firstResponseTime' ? sortOrder : 'asc'}
                    onClick={() => handleSort('firstResponseTime')}
                  >
                    Response
                  </TableSortLabel>
                </TableCell>
                <TableCell align="center">
                  <TableSortLabel
                    active={sortKey === 'customerSatisfaction'}
                    direction={sortKey === 'customerSatisfaction' ? sortOrder : 'asc'}
                    onClick={() => handleSort('customerSatisfaction')}
                  >
                    CSAT
                  </TableSortLabel>
                </TableCell>
                <TableCell align="center">
                  <TableSortLabel
                    active={sortKey === 'workload'}
                    direction={sortKey === 'workload' ? sortOrder : 'asc'}
                    onClick={() => handleSort('workload')}
                  >
                    Workload
                  </TableSortLabel>
                </TableCell>
                <TableCell align="center">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {sortedData.map((agent) => {
                const resolutionRate = getResolutionRate(agent.ticketsAssigned, agent.ticketsResolved);
                return (
                  <TableRow key={agent.id} hover>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                        <Avatar
                          sx={{
                            width: 32,
                            height: 32,
                            bgcolor: TECH_SUPPORT_COLORS.primary,
                            fontSize: '0.8rem'
                          }}
                        >
                          {agent.avatar}
                        </Avatar>
                        <Box>
                          <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                            {agent.name}
                          </Typography>
                          <Chip
                            label={agent.status.replace('_', ' ').toUpperCase()}
                            color={getStatusColor(agent.status) as any}
                            size="small"
                            variant="outlined"
                          />
                        </Box>
                      </Box>
                    </TableCell>
                    <TableCell align="center">
                      <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                        {agent.ticketsAssigned}
                      </Typography>
                    </TableCell>
                    <TableCell align="center">
                      <Typography variant="body2" sx={{ fontWeight: 'bold', color: TECH_SUPPORT_COLORS.success }}>
                        {agent.ticketsResolved}
                      </Typography>
                    </TableCell>
                    <TableCell align="center">
                      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5 }}>
                        <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                          {resolutionRate.toFixed(1)}%
                        </Typography>
                        {resolutionRate >= 80 ? (
                          <TrendingUp sx={{ fontSize: 16, color: TECH_SUPPORT_COLORS.success }} />
                        ) : resolutionRate >= 60 ? (
                          <Remove sx={{ fontSize: 16, color: TECH_SUPPORT_COLORS.warning }} />
                        ) : (
                          <TrendingDown sx={{ fontSize: 16, color: TECH_SUPPORT_COLORS.error }} />
                        )}
                      </Box>
                    </TableCell>
                    <TableCell align="center">
                      <Typography variant="body2">
                        {formatTime(agent.avgResolutionTime)}
                      </Typography>
                    </TableCell>
                    <TableCell align="center">
                      <Typography variant="body2">
                        {formatTime(agent.firstResponseTime)}
                      </Typography>
                    </TableCell>
                    <TableCell align="center">
                      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5 }}>
                        <Star
                          sx={{
                            fontSize: 16,
                            color: agent.customerSatisfaction >= 4.5 ? TECH_SUPPORT_COLORS.warning : 'lightgray'
                          }}
                        />
                        <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                          {agent.customerSatisfaction.toFixed(1)}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell align="center">
                      <Box sx={{ width: '100%', minWidth: 60 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <LinearProgress
                            variant="determinate"
                            value={agent.workload}
                            sx={{
                              flex: 1,
                              height: 8,
                              borderRadius: 4,
                              backgroundColor: 'grey.200',
                              '& .MuiLinearProgress-bar': {
                                backgroundColor: getWorkloadColor(agent.workload),
                              },
                            }}
                          />
                          <Typography variant="caption" sx={{ minWidth: 30 }}>
                            {agent.workload}%
                          </Typography>
                        </Box>
                      </Box>
                    </TableCell>
                    <TableCell align="center">
                      <Tooltip title="More actions">
                        <IconButton
                          size="small"
                          onClick={(e) => handleMenuClick(e, agent.id)}
                        >
                          <MoreVert fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>

        {/* Performance Summary */}
        <Box sx={{ mt: 2, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
          <Typography variant="subtitle2" gutterBottom sx={{ color: TECH_SUPPORT_COLORS.primary }}>
            Team Performance Summary
          </Typography>
          <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Top Performer (CSAT)
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                {data.reduce((max, agent) => agent.customerSatisfaction > max.customerSatisfaction ? agent : max, data[0])?.name}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Fastest Resolver
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                {data.reduce((min, agent) => agent.avgResolutionTime < min.avgResolutionTime ? agent : min, data[0])?.name}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Team Avg CSAT
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                {(data.reduce((sum, agent) => sum + agent.customerSatisfaction, 0) / data.length).toFixed(1)}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Total Resolved
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                {data.reduce((sum, agent) => sum + agent.ticketsResolved, 0)}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">
                Agents Available
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                {data.filter(agent => agent.status === 'available').length}/{data.length}
              </Typography>
            </Box>
          </Box>
        </Box>

        {/* Action Menu */}
        <Menu
          anchorEl={anchorEl}
          open={Boolean(anchorEl)}
          onClose={handleMenuClose}
        >
          <MenuItem onClick={handleMenuClose}>View Details</MenuItem>
          <MenuItem onClick={handleMenuClose}>Assign Tickets</MenuItem>
          <MenuItem onClick={handleMenuClose}>Performance Report</MenuItem>
          <MenuItem onClick={handleMenuClose}>Send Message</MenuItem>
        </Menu>
      </CardContent>
    </Card>
  );
};

export default AgentPerformanceTable;