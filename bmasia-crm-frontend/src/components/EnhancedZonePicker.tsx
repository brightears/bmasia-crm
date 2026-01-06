import React, { useState, useEffect, useCallback } from 'react';
import {
  Autocomplete,
  TextField,
  Chip,
  Box,
  Typography,
  CircularProgress,
  Alert,
  Button,
  Divider,
  Paper,
  IconButton,
  InputAdornment,
} from '@mui/material';
import {
  LocationOn,
  CheckCircle,
  Warning,
  WifiOff,
  HelpOutline,
  MusicNote,
  LibraryMusic,
  SelectAll,
  Deselect,
  Add,
} from '@mui/icons-material';
import { Zone, PreviewZone } from '../types';
import ApiService from '../services/api';

interface EnhancedZonePickerProps {
  companyId: string | null;
  soundtrackAccountId?: string;
  previewZones?: PreviewZone[];
  selectedZones: Zone[];
  onChange: (zones: Zone[]) => void;
  disabled?: boolean;
  mode: 'create' | 'edit';
}

const EnhancedZonePicker: React.FC<EnhancedZonePickerProps> = ({
  companyId,
  soundtrackAccountId,
  previewZones = [],
  selectedZones,
  onChange,
  disabled = false,
  mode,
}) => {
  const [soundtrackZones, setSoundtrackZones] = useState<Zone[]>([]);
  const [beatbreezeZones, setBeatbreezeZones] = useState<Zone[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [newBeatbreezeName, setNewBeatbreezeName] = useState('');
  const [addingZone, setAddingZone] = useState(false);

  // Split selected zones by platform
  const selectedSoundtrack = selectedZones.filter(z => z.platform === 'soundtrack');
  const selectedBeatbreeze = selectedZones.filter(z => z.platform === 'beatbreeze');

  const loadZones = useCallback(async (compId: string) => {
    setLoading(true);
    setLoadError(null);
    try {
      // If we have preview zones, convert them to Zone format for Soundtrack section
      if (previewZones.length > 0) {
        // Convert PreviewZone to Zone format (temporary zones, not yet in database)
        const convertedPreviewZones: Zone[] = previewZones.map(pz => ({
          id: pz.id, // Use preview zone ID temporarily
          company: compId,
          name: pz.name,
          platform: 'soundtrack' as const,
          status: pz.status,
          device_name: pz.device_name,
          soundtrack_zone_id: pz.id,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }));

        // Still load Beat Breeze zones from database
        const zones = await ApiService.getZonesByCompany(compId);
        const bbZones = zones.filter(z => z.platform === 'beatbreeze');

        setSoundtrackZones(convertedPreviewZones);
        setBeatbreezeZones(bbZones);

        // Auto-select all preview Soundtrack zones for NEW contracts only
        if (mode === 'create' && convertedPreviewZones.length > 0 && selectedZones.length === 0) {
          onChange(convertedPreviewZones);
        }
      } else {
        // Fallback to loading zones from database (original behavior)
        const zones = await ApiService.getZonesByCompany(compId);
        const stZones = zones.filter(z => z.platform === 'soundtrack');
        const bbZones = zones.filter(z => z.platform === 'beatbreeze');

        setSoundtrackZones(stZones);
        setBeatbreezeZones(bbZones);

        // Auto-select all Soundtrack zones for NEW contracts only
        if (mode === 'create' && stZones.length > 0 && selectedZones.length === 0) {
          onChange(stZones);
        }
      }
    } catch (err) {
      setLoadError('Failed to load zones. Please sync with Soundtrack first.');
      setSoundtrackZones([]);
      setBeatbreezeZones([]);
    } finally {
      setLoading(false);
    }
  }, [mode, onChange, selectedZones.length, previewZones]);

  useEffect(() => {
    if (companyId) {
      loadZones(companyId);
    } else {
      setSoundtrackZones([]);
      setBeatbreezeZones([]);
    }
  }, [companyId, loadZones]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'online':
        return '#4CAF50';
      case 'offline':
        return '#F44336';
      case 'pending':
        return '#FF9800';
      case 'no_device':
        return '#9E9E9E';
      default:
        return '#9E9E9E';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'online':
        return <CheckCircle sx={{ color: '#4CAF50', fontSize: 18 }} />;
      case 'offline':
        return <WifiOff sx={{ color: '#F44336', fontSize: 18 }} />;
      case 'pending':
        return <HelpOutline sx={{ color: '#FF9800', fontSize: 18 }} />;
      case 'no_device':
        return <Warning sx={{ color: '#9E9E9E', fontSize: 18 }} />;
      default:
        return <LocationOn sx={{ color: '#9E9E9E', fontSize: 18 }} />;
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'online':
        return 'Online';
      case 'offline':
        return 'Offline';
      case 'pending':
        return 'Pending';
      case 'no_device':
        return 'No Device';
      default:
        return status;
    }
  };

  // Soundtrack: Select All
  const handleSelectAllSoundtrack = () => {
    const currentBB = selectedZones.filter(z => z.platform === 'beatbreeze');
    onChange([...soundtrackZones, ...currentBB]);
  };

  // Soundtrack: Deselect All
  const handleDeselectAllSoundtrack = () => {
    const currentBB = selectedZones.filter(z => z.platform === 'beatbreeze');
    onChange(currentBB);
  };

  // Handle Soundtrack zone selection change
  const handleSoundtrackChange = (_: React.SyntheticEvent, newValue: Zone[]) => {
    const currentBB = selectedZones.filter(z => z.platform === 'beatbreeze');
    onChange([...newValue, ...currentBB]);
  };

  // Handle Beat Breeze zone selection change
  const handleBeatbreezeChange = (_: React.SyntheticEvent, newValue: Zone[]) => {
    const currentST = selectedZones.filter(z => z.platform === 'soundtrack');
    onChange([...currentST, ...newValue]);
  };

  // Add new Beat Breeze zone
  const handleAddNewBeatbreeze = async () => {
    if (!newBeatbreezeName.trim() || !companyId) return;

    setAddingZone(true);
    try {
      const newZone = await ApiService.createZone({
        company: companyId,
        name: newBeatbreezeName.trim(),
        platform: 'beatbreeze',
        status: 'pending',
      });

      // Add to available and selected lists
      setBeatbreezeZones(prev => [...prev, newZone]);
      const currentST = selectedZones.filter(z => z.platform === 'soundtrack');
      const currentBB = selectedZones.filter(z => z.platform === 'beatbreeze');
      onChange([...currentST, ...currentBB, newZone]);

      setNewBeatbreezeName('');
    } catch (err) {
      console.error('Failed to create Beat Breeze zone:', err);
    } finally {
      setAddingZone(false);
    }
  };

  if (!companyId) {
    return (
      <Alert severity="info" sx={{ mt: 2 }}>
        Please select a company first to choose zones.
      </Alert>
    );
  }

  if (loadError) {
    return (
      <Alert severity="warning" sx={{ mt: 2 }}>
        {loadError}
      </Alert>
    );
  }

  if (loading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 2 }}>
        <CircularProgress size={20} />
        <Typography variant="body2">Loading zones...</Typography>
      </Box>
    );
  }

  const totalZones = selectedZones.length;
  const hasSoundtrackZones = soundtrackZones.length > 0;
  const hasBeatbreezeZones = beatbreezeZones.length > 0;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      {/* Soundtrack Zones Section */}
      <Paper variant="outlined" sx={{ p: 2, borderColor: '#1976d2' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <MusicNote sx={{ color: '#1976d2' }} />
            <Typography variant="subtitle1" fontWeight={600} color="primary">
              Soundtrack Zones
            </Typography>
            {previewZones.length > 0 && (
              <Chip
                size="small"
                label="Live Preview"
                color="success"
                variant="outlined"
              />
            )}
            {hasSoundtrackZones && (
              <Chip
                size="small"
                label={`${selectedSoundtrack.length}/${soundtrackZones.length}`}
                color="primary"
                variant="outlined"
              />
            )}
          </Box>
          {hasSoundtrackZones && (
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button
                size="small"
                startIcon={<SelectAll />}
                onClick={handleSelectAllSoundtrack}
                disabled={disabled || selectedSoundtrack.length === soundtrackZones.length}
              >
                Select All
              </Button>
              <Button
                size="small"
                startIcon={<Deselect />}
                onClick={handleDeselectAllSoundtrack}
                disabled={disabled || selectedSoundtrack.length === 0}
                color="inherit"
              >
                Clear All
              </Button>
            </Box>
          )}
        </Box>

        {hasSoundtrackZones ? (
          <Autocomplete
            multiple
            options={soundtrackZones}
            value={selectedSoundtrack}
            onChange={handleSoundtrackChange}
            disabled={disabled}
            getOptionLabel={(option) => option.name}
            isOptionEqualToValue={(option, value) => option.id === value.id}
            renderInput={(params) => (
              <TextField
                {...params}
                placeholder={selectedSoundtrack.length === 0 ? 'Select Soundtrack zones...' : ''}
                size="small"
              />
            )}
            renderOption={(props, option) => (
              <Box
                component="li"
                {...props}
                sx={{ display: 'flex', alignItems: 'center', gap: 1.5, py: 1 }}
              >
                {getStatusIcon(option.status)}
                <Box sx={{ flexGrow: 1 }}>
                  <Typography variant="body2" fontWeight={500}>
                    {option.name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {getStatusLabel(option.status)}
                    {option.device_name && ` | ${option.device_name}`}
                  </Typography>
                </Box>
              </Box>
            )}
            renderTags={(value, getTagProps) =>
              value.map((option, index) => (
                <Chip
                  {...getTagProps({ index })}
                  key={option.id}
                  label={option.name}
                  size="small"
                  icon={getStatusIcon(option.status)}
                  sx={{
                    borderLeft: `3px solid ${getStatusColor(option.status)}`,
                    '& .MuiChip-icon': {
                      marginLeft: '8px',
                    },
                  }}
                />
              ))
            }
            ListboxProps={{
              sx: { maxHeight: 250 },
            }}
          />
        ) : (
          <Alert severity="info" variant="outlined">
            {previewZones.length > 0
              ? 'Enter a Soundtrack Account ID above to preview available zones.'
              : 'No Soundtrack zones found. Sync zones from the Zone Status page or the company\'s Soundtrack Account ID is not set.'
            }
          </Alert>
        )}
      </Paper>

      {/* Beat Breeze Zones Section */}
      <Paper variant="outlined" sx={{ p: 2, borderColor: '#9c27b0' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
          <LibraryMusic sx={{ color: '#9c27b0' }} />
          <Typography variant="subtitle1" fontWeight={600} sx={{ color: '#9c27b0' }}>
            Beat Breeze Zones
          </Typography>
          {selectedBeatbreeze.length > 0 && (
            <Chip
              size="small"
              label={`${selectedBeatbreeze.length} selected`}
              sx={{ backgroundColor: '#9c27b0', color: 'white' }}
            />
          )}
        </Box>

        {hasBeatbreezeZones && (
          <Autocomplete
            multiple
            options={beatbreezeZones}
            value={selectedBeatbreeze}
            onChange={handleBeatbreezeChange}
            disabled={disabled}
            getOptionLabel={(option) => option.name}
            isOptionEqualToValue={(option, value) => option.id === value.id}
            renderInput={(params) => (
              <TextField
                {...params}
                placeholder={selectedBeatbreeze.length === 0 ? 'Select existing Beat Breeze zones...' : ''}
                size="small"
              />
            )}
            renderOption={(props, option) => (
              <Box
                component="li"
                {...props}
                sx={{ display: 'flex', alignItems: 'center', gap: 1.5, py: 1 }}
              >
                <LibraryMusic sx={{ color: '#9c27b0', fontSize: 18 }} />
                <Typography variant="body2" fontWeight={500}>
                  {option.name}
                </Typography>
              </Box>
            )}
            renderTags={(value, getTagProps) =>
              value.map((option, index) => (
                <Chip
                  {...getTagProps({ index })}
                  key={option.id}
                  label={option.name}
                  size="small"
                  icon={<LibraryMusic sx={{ fontSize: 16 }} />}
                  sx={{
                    borderLeft: '3px solid #9c27b0',
                    '& .MuiChip-icon': {
                      marginLeft: '8px',
                      color: '#9c27b0',
                    },
                  }}
                />
              ))
            }
            ListboxProps={{
              sx: { maxHeight: 200 },
            }}
            sx={{ mb: 2 }}
          />
        )}

        <Divider sx={{ my: 2 }}>
          <Typography variant="caption" color="text.secondary">
            Add New Zone
          </Typography>
        </Divider>

        <Box sx={{ display: 'flex', gap: 1 }}>
          <TextField
            size="small"
            fullWidth
            placeholder="Enter new Beat Breeze zone name..."
            value={newBeatbreezeName}
            onChange={(e) => setNewBeatbreezeName(e.target.value)}
            disabled={disabled || addingZone}
            onKeyPress={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                handleAddNewBeatbreeze();
              }
            }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <LibraryMusic sx={{ color: '#9c27b0', fontSize: 20 }} />
                </InputAdornment>
              ),
            }}
          />
          <Button
            variant="contained"
            onClick={handleAddNewBeatbreeze}
            disabled={disabled || addingZone || !newBeatbreezeName.trim()}
            sx={{
              minWidth: 'auto',
              px: 2,
              backgroundColor: '#9c27b0',
              '&:hover': { backgroundColor: '#7b1fa2' },
            }}
          >
            {addingZone ? <CircularProgress size={20} color="inherit" /> : <Add />}
          </Button>
        </Box>

        <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
          Beat Breeze zones are managed manually (no API sync)
        </Typography>
      </Paper>

      {/* Summary */}
      {totalZones > 0 && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 1 }}>
          <LocationOn sx={{ color: '#FFA500', fontSize: 20 }} />
          <Typography variant="body2" color="text.secondary">
            <strong>{totalZones}</strong> zone{totalZones !== 1 ? 's' : ''} total: {' '}
            {selectedSoundtrack.length > 0 && (
              <span style={{ color: '#1976d2' }}>
                {selectedSoundtrack.length} Soundtrack
              </span>
            )}
            {selectedSoundtrack.length > 0 && selectedBeatbreeze.length > 0 && ', '}
            {selectedBeatbreeze.length > 0 && (
              <span style={{ color: '#9c27b0' }}>
                {selectedBeatbreeze.length} Beat Breeze
              </span>
            )}
          </Typography>
        </Box>
      )}
    </Box>
  );
};

export default EnhancedZonePicker;
