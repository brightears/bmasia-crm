import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Card,
  CardContent,
  List,
  ListItem,
  ListItemText,
  Chip,
  Button,
  IconButton,
  CircularProgress,
  Alert,
  Divider,
  GridLegacy as Grid,
} from '@mui/material';
import {
  Assignment,
  Warning,
  TrendingUp,
  Visibility,
  Refresh,
  AttachMoney,
  CalendarToday,
} from '@mui/icons-material';
import { Contract } from '../types';
import ApiService from '../services/api';

interface ContractWidgetsProps {
  onContractClick?: (contract: Contract) => void;
}

interface ContractStats {
  total_value: number;
  expiring_count: number;
  renewal_rate: number;
  active_count: number;
}

const ContractWidgets: React.FC<ContractWidgetsProps> = ({
  onContractClick,
}) => {
  const [expiringContracts, setExpiringContracts] = useState<Contract[]>([]);
  const [stats, setStats] = useState<ContractStats>({
    total_value: 0,
    expiring_count: 0,
    renewal_rate: 0,
    active_count: 0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    loadContractData();
  }, []);

  const loadContractData = async () => {
    try {
      setLoading(true);
      setError('');

      const [expiringData, allContractsData] = await Promise.all([
        ApiService.getExpiringContracts(),
        ApiService.getContracts({ page_size: 1000 }),
      ]);

      setExpiringContracts(expiringData);

      // Calculate stats from all contracts
      const contracts = allContractsData.results;
      const activeContracts = contracts.filter(c => c.status === 'Active');
      const totalValue = activeContracts.reduce((sum, contract) => sum + contract.value, 0);

      // Mock renewal rate calculation - in real app, this would come from historical data
      const renewalRate = Math.round((activeContracts.length * 0.85) * 100) / 100;

      setStats({
        total_value: totalValue,
        expiring_count: expiringData.length,
        renewal_rate: renewalRate,
        active_count: activeContracts.length,
      });
    } catch (err: any) {
      setError('Failed to load contract data');
      console.error('Contract widgets error:', err);
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (value: number, currency = 'USD'): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString();
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mb: 2 }}>
        {error}
      </Alert>
    );
  }

  return (
    <Grid container spacing={3}>
      {/* Contract Stats Cards */}
      <Grid item xs={12} sm={6} md={3}>
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
              <Assignment sx={{ mr: 1, color: 'primary.main' }} />
              <Typography variant="h6" component="div">
                {stats.active_count}
              </Typography>
            </Box>
            <Typography variant="body2" color="text.secondary">
              Active Contracts
            </Typography>
          </CardContent>
        </Card>
      </Grid>

      <Grid item xs={12} sm={6} md={3}>
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
              <AttachMoney sx={{ mr: 1, color: 'success.main' }} />
              <Typography variant="h6" component="div">
                {formatCurrency(stats.total_value)}
              </Typography>
            </Box>
            <Typography variant="body2" color="text.secondary">
              Total Contract Value
            </Typography>
          </CardContent>
        </Card>
      </Grid>

      <Grid item xs={12} sm={6} md={3}>
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
              <Warning sx={{ mr: 1, color: 'warning.main' }} />
              <Typography variant="h6" component="div">
                {stats.expiring_count}
              </Typography>
            </Box>
            <Typography variant="body2" color="text.secondary">
              Expiring Soon
            </Typography>
          </CardContent>
        </Card>
      </Grid>

      <Grid item xs={12} sm={6} md={3}>
        <Card>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
              <TrendingUp sx={{ mr: 1, color: 'info.main' }} />
              <Typography variant="h6" component="div">
                {stats.renewal_rate}%
              </Typography>
            </Box>
            <Typography variant="body2" color="text.secondary">
              Renewal Rate
            </Typography>
          </CardContent>
        </Card>
      </Grid>

      {/* Expiring Contracts Widget */}
      <Grid item xs={12} lg={6}>
        <Paper sx={{ p: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6">
              Contracts Expiring Soon
            </Typography>
            <IconButton size="small" onClick={loadContractData}>
              <Refresh />
            </IconButton>
          </Box>

          {expiringContracts.length > 0 ? (
            <List sx={{ maxHeight: 400, overflow: 'auto' }}>
              {expiringContracts.slice(0, 10).map((contract, index) => (
                <React.Fragment key={contract.id}>
                  <ListItem
                    sx={{
                      cursor: onContractClick ? 'pointer' : 'default',
                      '&:hover': onContractClick ? { bgcolor: 'action.hover' } : {},
                      px: 0,
                    }}
                    onClick={() => onContractClick?.(contract)}
                  >
                    <ListItemText
                      primary={
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Typography variant="body1" fontWeight="medium">
                            {contract.company_name}
                          </Typography>
                          <Chip
                            size="small"
                            label={`${contract.days_until_expiry} days`}
                            color={contract.days_until_expiry <= 7 ? 'error' : 'warning'}
                          />
                        </Box>
                      }
                      secondary={
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mt: 1 }}>
                          <Box>
                            <Typography variant="caption" display="block">
                              Contract: {contract.contract_number}
                            </Typography>
                            <Typography variant="caption" display="block" color="text.secondary">
                              Value: {formatCurrency(contract.value, contract.currency)}
                            </Typography>
                          </Box>
                          <Box sx={{ textAlign: 'right' }}>
                            <Typography variant="caption" display="block">
                              Expires: {formatDate(contract.end_date)}
                            </Typography>
                            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 0.5 }}>
                              <CalendarToday sx={{ fontSize: 12 }} />
                              <Typography variant="caption">
                                {contract.auto_renew ? 'Auto-renew' : 'Manual renewal'}
                              </Typography>
                            </Box>
                          </Box>
                        </Box>
                      }
                    />
                    {onContractClick && (
                      <IconButton size="small" sx={{ ml: 1 }}>
                        <Visibility />
                      </IconButton>
                    )}
                  </ListItem>
                  {index < expiringContracts.length - 1 && <Divider />}
                </React.Fragment>
              ))}
            </List>
          ) : (
            <Box sx={{ textAlign: 'center', py: 4 }}>
              <Assignment sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
              <Typography variant="body1" color="text.secondary">
                No contracts expiring in the next 30 days
              </Typography>
            </Box>
          )}

          {expiringContracts.length > 0 && (
            <Box sx={{ mt: 2, textAlign: 'center' }}>
              <Button
                size="small"
                variant="outlined"
                href="/contracts?filter=expiring"
              >
                View All Expiring Contracts
              </Button>
            </Box>
          )}
        </Paper>
      </Grid>

      {/* Contract Performance Widget */}
      <Grid item xs={12} lg={6}>
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Contract Performance
          </Typography>

          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {/* Monthly Revenue */}
            <Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                <Typography variant="body2" color="text.secondary">
                  Monthly Recurring Revenue
                </Typography>
                <Typography variant="h6" color="success.main">
                  {formatCurrency(Math.round(stats.total_value / 12))}
                </Typography>
              </Box>
            </Box>

            <Divider />

            {/* Contract Status Breakdown */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Contract Status Breakdown
              </Typography>
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                <Chip
                  label={`Active: ${stats.active_count}`}
                  color="success"
                  size="small"
                />
                <Chip
                  label={`Expiring: ${stats.expiring_count}`}
                  color="warning"
                  size="small"
                />
              </Box>
            </Box>

            <Divider />

            {/* Key Metrics */}
            <Box>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Key Metrics
              </Typography>
              <List dense>
                <ListItem sx={{ px: 0 }}>
                  <ListItemText
                    primary="Average Contract Value"
                    secondary={
                      stats.active_count > 0 ?
                        formatCurrency(Math.round(stats.total_value / stats.active_count)) :
                        '$0'
                    }
                  />
                </ListItem>
                <ListItem sx={{ px: 0 }}>
                  <ListItemText
                    primary="Renewal Rate"
                    secondary={`${stats.renewal_rate}%`}
                  />
                </ListItem>
                <ListItem sx={{ px: 0 }}>
                  <ListItemText
                    primary="Contracts Requiring Action"
                    secondary={`${stats.expiring_count} expiring soon`}
                  />
                </ListItem>
              </List>
            </Box>

            <Button
              variant="outlined"
              size="small"
              href="/contracts"
              fullWidth
            >
              Manage All Contracts
            </Button>
          </Box>
        </Paper>
      </Grid>
    </Grid>
  );
};

export default ContractWidgets;