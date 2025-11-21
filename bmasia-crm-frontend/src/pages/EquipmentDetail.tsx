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
  IconButton,
  InputAdornment,
  TextField,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from '@mui/material';
import {
  Build,
  Edit,
  ArrowBack,
  Visibility,
  VisibilityOff,
  Business,
  Memory,
  Router,
  VpnKey,
  Notes as NotesIcon,
  CalendarMonth,
  Add,
} from '@mui/icons-material';
import { useParams, useNavigate } from 'react-router-dom';
import { Equipment, EquipmentHistory } from '../types';
import ApiService from '../services/api';
import { format } from 'date-fns';
import EquipmentHistoryTimeline from '../components/EquipmentHistoryTimeline';

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
      id={`equipment-tabpanel-${index}`}
      aria-labelledby={`equipment-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
}

const EquipmentDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [equipment, setEquipment] = useState<Equipment | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tabValue, setTabValue] = useState(0);
  const [showPassword, setShowPassword] = useState(false);
  const [historyDialogOpen, setHistoryDialogOpen] = useState(false);
  const [historyFormData, setHistoryFormData] = useState({
    action: 'note' as EquipmentHistory['action'],
    description: '',
  });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (id) {
      loadEquipment();
    }
  }, [id]);

  const loadEquipment = async () => {
    if (!id) return;
    try {
      setLoading(true);
      setError('');
      const data = await ApiService.getEquipmentItem(id);
      setEquipment(data);
    } catch (err: any) {
      console.error('Equipment load error:', err);
      setError('Failed to load equipment details');
    } finally {
      setLoading(false);
    }
  };

  const handleAddHistory = async () => {
    if (!id || !historyFormData.description.trim()) return;

    try {
      setSubmitting(true);
      await ApiService.addEquipmentHistory(id, historyFormData);
      setHistoryDialogOpen(false);
      setHistoryFormData({ action: 'note', description: '' });
      loadEquipment(); // Reload to get updated history
    } catch (err: any) {
      console.error('Add history error:', err);
      setError('Failed to add history entry');
    } finally {
      setSubmitting(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'success';
      case 'inactive':
        return 'default';
      case 'maintenance':
        return 'warning';
      case 'retired':
        return 'error';
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

  if (error || !equipment) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error" sx={{ mb: 2 }}>
          {error || 'Equipment not found'}
        </Alert>
        <Button variant="contained" onClick={() => navigate('/equipment')} startIcon={<ArrowBack />}>
          Back to Equipment
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
            onClick={() => navigate('/equipment')}
            sx={{ mb: 1 }}
          >
            Back to Equipment
          </Button>
          <Typography variant="h4" component="h1" gutterBottom>
            <Build sx={{ mr: 1, verticalAlign: 'bottom' }} />
            {equipment.equipment_number}
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <Chip
              label={equipment.status}
              size="small"
              color={getStatusColor(equipment.status) as any}
              sx={{ textTransform: 'capitalize' }}
            />
            <Typography variant="body2" color="text.secondary">
              {equipment.equipment_type_name}
            </Typography>
          </Box>
        </Box>
        <Button
          variant="contained"
          startIcon={<Edit />}
          onClick={() => navigate(`/equipment/${id}/edit`)}
          sx={{ bgcolor: '#FFA500', '&:hover': { bgcolor: '#FF8C00' } }}
        >
          Edit Equipment
        </Button>
      </Box>

      {/* Tabs */}
      <Paper sx={{ mb: 3 }}>
        <Tabs value={tabValue} onChange={(e, v) => setTabValue(v)}>
          <Tab label="Overview" />
          <Tab label={`History (${equipment.history?.length || 0})`} />
          <Tab label="Tickets" />
        </Tabs>

        {/* Overview Tab */}
        <TabPanel value={tabValue} index={0}>
          <Grid container spacing={3}>
            {/* Equipment Info */}
            <Grid item xs={12} md={6}>
              <Card variant="outlined">
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    <Build sx={{ mr: 1, verticalAlign: 'bottom', fontSize: 20 }} />
                    Equipment Information
                  </Typography>
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Equipment Number
                      </Typography>
                      <Typography variant="body1">{equipment.equipment_number}</Typography>
                    </Box>
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Type
                      </Typography>
                      <Typography variant="body1">{equipment.equipment_type_name}</Typography>
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
                        onClick={() => navigate(`/companies/${equipment.company}`)}
                      >
                        {equipment.company_name}
                      </Typography>
                    </Box>
                  </Box>
                </CardContent>
              </Card>
            </Grid>

            {/* Hardware Details */}
            <Grid item xs={12} md={6}>
              <Card variant="outlined">
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    <Memory sx={{ mr: 1, verticalAlign: 'bottom', fontSize: 20 }} />
                    Hardware Details
                  </Typography>
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Serial Number
                      </Typography>
                      <Typography variant="body1">{equipment.serial_number || '-'}</Typography>
                    </Box>
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Model
                      </Typography>
                      <Typography variant="body1">{equipment.model_name || '-'}</Typography>
                    </Box>
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Manufacturer
                      </Typography>
                      <Typography variant="body1">{equipment.manufacturer || '-'}</Typography>
                    </Box>
                  </Box>
                </CardContent>
              </Card>
            </Grid>

            {/* Network Configuration */}
            {(equipment.ip_address || equipment.mac_address) && (
              <Grid item xs={12} md={6}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      <Router sx={{ mr: 1, verticalAlign: 'bottom', fontSize: 20 }} />
                      Network Configuration
                    </Typography>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
                      {equipment.ip_address && (
                        <Box>
                          <Typography variant="caption" color="text.secondary">
                            IP Address
                          </Typography>
                          <Typography variant="body1" fontFamily="monospace">
                            {equipment.ip_address}
                          </Typography>
                        </Box>
                      )}
                      {equipment.mac_address && (
                        <Box>
                          <Typography variant="caption" color="text.secondary">
                            MAC Address
                          </Typography>
                          <Typography variant="body1" fontFamily="monospace">
                            {equipment.mac_address}
                          </Typography>
                        </Box>
                      )}
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            )}

            {/* Remote Access */}
            {(equipment.remote_username || equipment.remote_password) && (
              <Grid item xs={12} md={6}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      <VpnKey sx={{ mr: 1, verticalAlign: 'bottom', fontSize: 20 }} />
                      Remote Access
                    </Typography>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 2 }}>
                      {equipment.remote_username && (
                        <Box>
                          <Typography variant="caption" color="text.secondary">
                            Username
                          </Typography>
                          <Typography variant="body1" fontFamily="monospace">
                            {equipment.remote_username}
                          </Typography>
                        </Box>
                      )}
                      {equipment.remote_password && (
                        <Box>
                          <Typography variant="caption" color="text.secondary">
                            Password
                          </Typography>
                          <TextField
                            fullWidth
                            size="small"
                            type={showPassword ? 'text' : 'password'}
                            value={equipment.remote_password}
                            InputProps={{
                              readOnly: true,
                              sx: { fontFamily: 'monospace' },
                              endAdornment: (
                                <InputAdornment position="end">
                                  <IconButton
                                    onClick={() => setShowPassword(!showPassword)}
                                    edge="end"
                                    size="small"
                                  >
                                    {showPassword ? <VisibilityOff /> : <Visibility />}
                                  </IconButton>
                                </InputAdornment>
                              ),
                            }}
                          />
                        </Box>
                      )}
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            )}

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
                        Installed Date
                      </Typography>
                      <Typography variant="body1">
                        {equipment.installed_date
                          ? format(new Date(equipment.installed_date), 'MMM dd, yyyy')
                          : '-'}
                      </Typography>
                    </Box>
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Warranty Expiry
                      </Typography>
                      <Typography variant="body1">
                        {equipment.warranty_expiry
                          ? format(new Date(equipment.warranty_expiry), 'MMM dd, yyyy')
                          : '-'}
                      </Typography>
                    </Box>
                  </Box>
                </CardContent>
              </Card>
            </Grid>

            {/* Setup Details */}
            {equipment.setup_details && (
              <Grid item xs={12}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      <NotesIcon sx={{ mr: 1, verticalAlign: 'bottom', fontSize: 20 }} />
                      Setup Details
                    </Typography>
                    <Typography
                      variant="body2"
                      sx={{ mt: 1, whiteSpace: 'pre-wrap', fontFamily: 'monospace', bgcolor: 'grey.100', p: 2, borderRadius: 1 }}
                    >
                      {equipment.setup_details}
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            )}

            {/* Notes */}
            {equipment.notes && (
              <Grid item xs={12}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      <NotesIcon sx={{ mr: 1, verticalAlign: 'bottom', fontSize: 20 }} />
                      Notes
                    </Typography>
                    <Typography variant="body2" sx={{ mt: 1, whiteSpace: 'pre-wrap' }}>
                      {equipment.notes}
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            )}
          </Grid>
        </TabPanel>

        {/* History Tab */}
        <TabPanel value={tabValue} index={1}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
            <Typography variant="h6">Equipment History</Typography>
            <Button
              variant="contained"
              size="small"
              startIcon={<Add />}
              onClick={() => setHistoryDialogOpen(true)}
              sx={{ bgcolor: '#FFA500', '&:hover': { bgcolor: '#FF8C00' } }}
            >
              Add Entry
            </Button>
          </Box>
          {equipment.history && equipment.history.length > 0 ? (
            <EquipmentHistoryTimeline history={equipment.history} />
          ) : (
            <Box sx={{ textAlign: 'center', py: 4 }}>
              <Typography variant="body1" color="text.secondary">
                No history entries yet
              </Typography>
            </Box>
          )}
        </TabPanel>

        {/* Tickets Tab (Placeholder) */}
        <TabPanel value={tabValue} index={2}>
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <Typography variant="h6" color="text.secondary" gutterBottom>
              Related Tickets
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Ticket integration coming soon. This will show all support tickets related to this equipment.
            </Typography>
          </Box>
        </TabPanel>
      </Paper>

      {/* Add History Dialog */}
      <Dialog open={historyDialogOpen} onClose={() => setHistoryDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Add History Entry</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
            <FormControl fullWidth>
              <InputLabel>Action</InputLabel>
              <Select
                value={historyFormData.action}
                onChange={(e) => setHistoryFormData({ ...historyFormData, action: e.target.value as any })}
                label="Action"
              >
                <MenuItem value="note">Note</MenuItem>
                <MenuItem value="installed">Installed</MenuItem>
                <MenuItem value="maintenance">Maintenance</MenuItem>
                <MenuItem value="repair">Repair</MenuItem>
                <MenuItem value="upgrade">Upgrade</MenuItem>
                <MenuItem value="replaced">Replaced</MenuItem>
                <MenuItem value="retired">Retired</MenuItem>
              </Select>
            </FormControl>
            <TextField
              fullWidth
              multiline
              rows={4}
              label="Description"
              value={historyFormData.description}
              onChange={(e) => setHistoryFormData({ ...historyFormData, description: e.target.value })}
              placeholder="Enter details about this action..."
              required
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setHistoryDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleAddHistory}
            disabled={submitting || !historyFormData.description.trim()}
          >
            {submitting ? 'Adding...' : 'Add Entry'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default EquipmentDetail;
