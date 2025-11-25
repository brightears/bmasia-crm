import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  Chip,
  Alert,
  CircularProgress,
  Card,
  CardContent,
  GridLegacy as Grid,
  Tabs,
  Tab,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
} from '@mui/material';
import {
  LocationOn,
  Edit,
  Delete,
  ArrowBack,
  CloudQueue,
  Devices,
  Notes as NotesIcon,
  CalendarMonth,
  Assignment,
} from '@mui/icons-material';
import { useParams, useNavigate } from 'react-router-dom';
import { Zone, ContractZone } from '../types';
import ApiService from '../services/api';
import { format } from 'date-fns';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`zone-tabpanel-${index}`}
      aria-labelledby={`zone-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
}

const ZoneDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [zone, setZone] = useState<Zone | null>(null);
  const [contracts, setContracts] = useState<ContractZone[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tabValue, setTabValue] = useState(0);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (id) {
      loadZoneData();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const loadZoneData = async () => {
    if (!id) return;
    try {
      setLoading(true);
      setError('');

      // Load zone and contracts in parallel
      const [zoneData, contractsData] = await Promise.all([
        ApiService.getZone(id),
        ApiService.getZoneContracts(id),
      ]);

      setZone(zoneData);
      setContracts(contractsData);
    } catch (err: any) {
      console.error('Zone load error:', err);
      setError('Failed to load zone details');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!id) return;

    try {
      setDeleting(true);
      await ApiService.deleteZone(id);
      navigate('/zones');
    } catch (err: any) {
      console.error('Delete error:', err);
      setError('Failed to delete zone. Please try again.');
      setDeleteDialogOpen(false);
    } finally {
      setDeleting(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'online':
        return 'success';
      case 'offline':
        return 'error';
      case 'no_device':
        return 'warning';
      case 'expired':
        return 'error';
      case 'pending':
        return 'default';
      default:
        return 'default';
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
        <CircularProgress size={40} />
      </Box>
    );
  }

  if (error && !zone) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error" sx={{ mb: 2 }}>
          {error || 'Zone not found'}
        </Alert>
        <Button variant="contained" onClick={() => navigate('/zones')} startIcon={<ArrowBack />}>
          Back to Zones
        </Button>
      </Box>
    );
  }

  if (!zone) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error" sx={{ mb: 2 }}>
          Zone not found
        </Alert>
        <Button variant="contained" onClick={() => navigate('/zones')} startIcon={<ArrowBack />}>
          Back to Zones
        </Button>
      </Box>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 3 }}>
        <Box>
          <Button
            startIcon={<ArrowBack />}
            onClick={() => navigate('/zones')}
            sx={{ mb: 1 }}
          >
            Back to Zones
          </Button>
          <Typography variant="h4" component="h1" gutterBottom>
            <LocationOn sx={{ mr: 1, verticalAlign: 'bottom' }} />
            {zone.name}
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <Chip
              label={zone.status?.replace('_', ' ')}
              size="small"
              color={getStatusColor(zone.status) as any}
              sx={{ textTransform: 'capitalize' }}
            />
            <Chip
              label={zone.platform}
              size="small"
              variant="outlined"
              sx={{ textTransform: 'capitalize' }}
            />
          </Box>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            startIcon={<Delete />}
            onClick={() => setDeleteDialogOpen(true)}
            color="error"
          >
            Delete
          </Button>
          <Button
            variant="contained"
            startIcon={<Edit />}
            onClick={() => navigate(`/zones/${id}/edit`)}
            sx={{ bgcolor: '#FFA500', '&:hover': { bgcolor: '#FF8C00' } }}
          >
            Edit Zone
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* Tabs */}
      <Paper sx={{ mb: 3 }}>
        <Tabs value={tabValue} onChange={(e, v) => setTabValue(v)}>
          <Tab label="Overview" />
          <Tab label={`Contract History (${contracts.length})`} />
        </Tabs>

        {/* Overview Tab */}
        <TabPanel value={tabValue} index={0}>
          <Grid container spacing={3}>
            {/* Zone Info */}
            <Grid item xs={12} md={6}>
              <Card variant="outlined">
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    <LocationOn sx={{ mr: 1, verticalAlign: 'bottom', fontSize: 20 }} />
                    Zone Information
                  </Typography>
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Zone Name
                      </Typography>
                      <Typography variant="body1">{zone.name}</Typography>
                    </Box>
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Company
                      </Typography>
                      <Typography
                        variant="body1"
                        sx={{
                          color: 'primary.main',
                          cursor: 'pointer',
                          '&:hover': { textDecoration: 'underline' },
                        }}
                        onClick={() => navigate(`/companies/${zone.company}`)}
                      >
                        {zone.company_name}
                      </Typography>
                    </Box>
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Platform
                      </Typography>
                      <Typography variant="body1" sx={{ textTransform: 'capitalize' }}>
                        {zone.platform}
                      </Typography>
                    </Box>
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Status
                      </Typography>
                      <Box sx={{ mt: 0.5 }}>
                        <Chip
                          label={zone.status?.replace('_', ' ')}
                          size="small"
                          color={getStatusColor(zone.status) as any}
                          sx={{ textTransform: 'capitalize' }}
                        />
                      </Box>
                    </Box>
                  </Box>
                </CardContent>
              </Card>
            </Grid>

            {/* Platform Details */}
            <Grid item xs={12} md={6}>
              <Card variant="outlined">
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    <CloudQueue sx={{ mr: 1, verticalAlign: 'bottom', fontSize: 20 }} />
                    Platform Details
                  </Typography>
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
                    {zone.soundtrack_zone_id && (
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Soundtrack Zone ID
                        </Typography>
                        <Typography variant="body1" fontFamily="monospace">
                          {zone.soundtrack_zone_id}
                        </Typography>
                      </Box>
                    )}
                    {zone.device && zone.device_name ? (
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          <Devices sx={{ fontSize: 14, mr: 0.5, verticalAlign: 'middle' }} />
                          Running on Device
                        </Typography>
                        <Typography variant="body1" fontWeight="medium">
                          {zone.device_name}
                        </Typography>
                      </Box>
                    ) : (
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          <Devices sx={{ fontSize: 14, mr: 0.5, verticalAlign: 'middle' }} />
                          Device
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {zone.device_name || 'No device assigned'}
                        </Typography>
                      </Box>
                    )}
                  </Box>
                </CardContent>
              </Card>
            </Grid>

            {/* Dates */}
            <Grid item xs={12} md={6}>
              <Card variant="outlined">
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    <CalendarMonth sx={{ mr: 1, verticalAlign: 'bottom', fontSize: 20 }} />
                    Important Dates
                  </Typography>
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Created
                      </Typography>
                      <Typography variant="body1">
                        {zone.created_at
                          ? format(new Date(zone.created_at), 'MMM dd, yyyy')
                          : '-'}
                      </Typography>
                    </Box>
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Last Updated
                      </Typography>
                      <Typography variant="body1">
                        {zone.updated_at
                          ? format(new Date(zone.updated_at), 'MMM dd, yyyy')
                          : '-'}
                      </Typography>
                    </Box>
                  </Box>
                </CardContent>
              </Card>
            </Grid>

            {/* Notes */}
            {zone.notes && (
              <Grid item xs={12}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      <NotesIcon sx={{ mr: 1, verticalAlign: 'bottom', fontSize: 20 }} />
                      Notes
                    </Typography>
                    <Typography variant="body2" sx={{ mt: 1, whiteSpace: 'pre-wrap' }}>
                      {zone.notes}
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            )}
          </Grid>
        </TabPanel>

        {/* Contract History Tab */}
        <TabPanel value={tabValue} index={1}>
          <Box sx={{ mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              <Assignment sx={{ mr: 1, verticalAlign: 'bottom' }} />
              Contract History
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              All contracts associated with this zone, past and present
            </Typography>

            {contracts.length > 0 ? (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {/* Active Contracts */}
                {contracts.filter(c => c.is_active).length > 0 && (
                  <Box>
                    <Typography variant="subtitle1" fontWeight={600} color="success.main" sx={{ mb: 2 }}>
                      Active Contracts
                    </Typography>
                    {contracts
                      .filter(c => c.is_active)
                      .map((contractZone) => (
                        <Card key={contractZone.id} variant="outlined" sx={{ mb: 2 }}>
                          <CardContent>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                              <Box sx={{ flexGrow: 1 }}>
                                <Box
                                  sx={{
                                    cursor: 'pointer',
                                    color: 'primary.main',
                                    fontWeight: 600,
                                    fontSize: '1.1rem',
                                    mb: 1,
                                    '&:hover': { textDecoration: 'underline' },
                                  }}
                                  onClick={() => navigate(`/contracts/${contractZone.contract}`)}
                                >
                                  {contractZone.contract_number}
                                </Box>
                                <Box sx={{ display: 'flex', gap: 2, mb: 1 }}>
                                  <Box>
                                    <Typography variant="caption" color="text.secondary">
                                      Start Date
                                    </Typography>
                                    <Typography variant="body2">
                                      {format(new Date(contractZone.start_date), 'MMM dd, yyyy')}
                                    </Typography>
                                  </Box>
                                  {contractZone.end_date && (
                                    <Box>
                                      <Typography variant="caption" color="text.secondary">
                                        End Date
                                      </Typography>
                                      <Typography variant="body2">
                                        {format(new Date(contractZone.end_date), 'MMM dd, yyyy')}
                                      </Typography>
                                    </Box>
                                  )}
                                </Box>
                                {contractZone.notes && (
                                  <Box sx={{ mt: 1 }}>
                                    <Typography variant="caption" color="text.secondary">
                                      Notes
                                    </Typography>
                                    <Typography variant="body2">{contractZone.notes}</Typography>
                                  </Box>
                                )}
                              </Box>
                              <Chip label="Active" color="success" size="small" />
                            </Box>
                          </CardContent>
                        </Card>
                      ))}
                  </Box>
                )}

                {/* Historical Contracts */}
                {contracts.filter(c => !c.is_active).length > 0 && (
                  <Box>
                    <Typography variant="subtitle1" fontWeight={600} color="text.secondary" sx={{ mb: 2 }}>
                      Historical Contracts
                    </Typography>
                    {contracts
                      .filter(c => !c.is_active)
                      .sort((a, b) => {
                        // Sort by end_date descending (most recent first)
                        const dateA = a.end_date ? new Date(a.end_date).getTime() : 0;
                        const dateB = b.end_date ? new Date(b.end_date).getTime() : 0;
                        return dateB - dateA;
                      })
                      .map((contractZone) => (
                        <Card key={contractZone.id} variant="outlined" sx={{ mb: 2, bgcolor: 'grey.50' }}>
                          <CardContent>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                              <Box sx={{ flexGrow: 1 }}>
                                <Box
                                  sx={{
                                    cursor: 'pointer',
                                    color: 'primary.main',
                                    fontWeight: 500,
                                    fontSize: '1rem',
                                    mb: 1,
                                    '&:hover': { textDecoration: 'underline' },
                                  }}
                                  onClick={() => navigate(`/contracts/${contractZone.contract}`)}
                                >
                                  {contractZone.contract_number}
                                </Box>
                                <Box sx={{ display: 'flex', gap: 2, mb: 1 }}>
                                  <Box>
                                    <Typography variant="caption" color="text.secondary">
                                      Start Date
                                    </Typography>
                                    <Typography variant="body2">
                                      {format(new Date(contractZone.start_date), 'MMM dd, yyyy')}
                                    </Typography>
                                  </Box>
                                  {contractZone.end_date && (
                                    <Box>
                                      <Typography variant="caption" color="text.secondary">
                                        End Date
                                      </Typography>
                                      <Typography variant="body2">
                                        {format(new Date(contractZone.end_date), 'MMM dd, yyyy')}
                                      </Typography>
                                    </Box>
                                  )}
                                </Box>
                                {contractZone.notes && (
                                  <Box sx={{ mt: 1 }}>
                                    <Typography variant="caption" color="text.secondary">
                                      Notes
                                    </Typography>
                                    <Typography variant="body2">{contractZone.notes}</Typography>
                                  </Box>
                                )}
                              </Box>
                              <Chip label="Ended" color="default" size="small" />
                            </Box>
                          </CardContent>
                        </Card>
                      ))}
                  </Box>
                )}
              </Box>
            ) : (
              <Box sx={{ textAlign: 'center', py: 4 }}>
                <Assignment sx={{ fontSize: 60, color: 'text.disabled', mb: 2 }} />
                <Typography variant="body1" color="text.secondary">
                  No contracts associated with this zone
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  Contracts can be linked to zones from the contract management page
                </Typography>
              </Box>
            )}
          </Box>
        </TabPanel>
      </Paper>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)}>
        <DialogTitle>Delete Zone?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete the zone "{zone.name}"? This action cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={handleDelete}
            color="error"
            variant="contained"
            disabled={deleting}
          >
            {deleting ? 'Deleting...' : 'Delete'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default ZoneDetail;
