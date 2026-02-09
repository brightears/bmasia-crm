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
  CloudDownload,
} from '@mui/icons-material';
import { Zone, PreviewZone } from '../types';
import ApiService from '../services/api';

interface ZoneOverlap {
  zone_id: string;
  zone_name: string;
  conflicting_contract_id: string;
  conflicting_contract_number: string;
}

interface EnhancedZonePickerProps {
  companyId: string | null;
  soundtrackAccountId?: string;
  previewZones?: PreviewZone[];
  selectedZones: Zone[];
  onChange: (zones: Zone[]) => void;
  disabled?: boolean;
  mode: 'create' | 'edit';
  contractId?: string;
}

const EnhancedZonePicker: React.FC<EnhancedZonePickerProps> = ({
  companyId,
  soundtrackAccountId,
  previewZones = [],
  selectedZones,
  onChange,
  disabled = false,
  mode,
  contractId,
}) => {
  const [soundtrackZones, setSoundtrackZones] = useState<Zone[]>([]);
  const [beatbreezeZones, setBeatbreezeZones] = useState<Zone[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [newBeatbreezeName, setNewBeatbreezeName] = useState('');
  const [addingZone, setAddingZone] = useState(false);
  const [newSoundtrackName, setNewSoundtrackName] = useState('');
  const [addingSoundtrackZone, setAddingSoundtrackZone] = useState(false);
  const [importingFromApi, setImportingFromApi] = useState(false);
  const [importComplete, setImportComplete] = useState(false);
  const [overlaps, setOverlaps] = useState<ZoneOverlap[]>([]);

  // Check for zone overlaps when selection changes (debounced)
  useEffect(() => {
    const zoneIds = selectedZones.map(z => z.id);
    if (zoneIds.length === 0) {
      setOverlaps([]);
      return;
    }

    const timer = setTimeout(async () => {
      try {
        const conflicts = await ApiService.checkZoneOverlaps(zoneIds, contractId);
        setOverlaps(conflicts || []);
      } catch {
        // Silently fail — overlap check is non-critical
        setOverlaps([]);
      }
    }, 500); // 500ms debounce

    return () => clearTimeout(timer);
  }, [selectedZones, contractId]);

  // Split selected zones by platform
  const selectedSoundtrack = selectedZones.filter(z => z.platform === 'soundtrack');
  const selectedBeatbreeze = selectedZones.filter(z => z.platform === 'beatbreeze');

  // Calculate how many preview zones are not yet in DB
  const unimportedPreviewZones = previewZones.filter(pz => {
    return !soundtrackZones.some(
      sz => sz.soundtrack_zone_id === pz.id || sz.name === pz.name
    );
  });

  const loadZones = useCallback(async (compId: string) => {
    setLoading(true);
    setLoadError(null);
    try {
      // Always load zones from database (real DB zones with proper UUIDs)
      const zones = await ApiService.getZonesByCompany(compId);
      const stZones = zones.filter(z => z.platform === 'soundtrack');
      const bbZones = zones.filter(z => z.platform === 'beatbreeze');

      setSoundtrackZones(stZones);
      setBeatbreezeZones(bbZones);

      // Auto-select all Soundtrack zones for NEW contracts only
      if (mode === 'create' && stZones.length > 0 && selectedZones.length === 0) {
        onChange(stZones);
      }
    } catch (err) {
      setLoadError('Failed to load zones.');
      setSoundtrackZones([]);
      setBeatbreezeZones([]);
    } finally {
      setLoading(false);
    }
  }, [mode, onChange, selectedZones.length]);

  useEffect(() => {
    if (companyId) {
      loadZones(companyId);
    } else {
      setSoundtrackZones([]);
      setBeatbreezeZones([]);
    }
  }, [companyId, loadZones]);

  // Reset import state when preview zones change
  useEffect(() => {
    setImportComplete(false);
  }, [previewZones.length]);

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

  // Add new Soundtrack zone (manual)
  const handleAddNewSoundtrack = async () => {
    if (!newSoundtrackName.trim() || !companyId) return;

    setAddingSoundtrackZone(true);
    try {
      const newZone = await ApiService.createZone({
        company: companyId,
        name: newSoundtrackName.trim(),
        platform: 'soundtrack',
        status: 'pending',
      });

      // Add to available and selected lists
      setSoundtrackZones(prev => [...prev, newZone]);
      const currentST = selectedZones.filter(z => z.platform === 'soundtrack');
      const currentBB = selectedZones.filter(z => z.platform === 'beatbreeze');
      onChange([...currentST, newZone, ...currentBB]);

      setNewSoundtrackName('');
    } catch (err) {
      console.error('Failed to create Soundtrack zone:', err);
    } finally {
      setAddingSoundtrackZone(false);
    }
  };

  // Import all zones from Soundtrack API
  const handleImportFromApi = async () => {
    if (!companyId || unimportedPreviewZones.length === 0) return;

    setImportingFromApi(true);
    try {
      const importedZones: Zone[] = [];

      for (const pz of unimportedPreviewZones) {
        const newZone = await ApiService.createZone({
          company: companyId,
          name: pz.name,
          platform: 'soundtrack',
          status: pz.status || 'pending',
          soundtrack_zone_id: pz.id,
          device_name: pz.device_name || '',
        });
        importedZones.push(newZone);
      }

      // Update available zones (add newly imported, keep existing)
      setSoundtrackZones(prev => {
        const existingIds = new Set(prev.map(z => z.id));
        const newOnes = importedZones.filter(z => !existingIds.has(z.id));
        return [...prev, ...newOnes];
      });

      // Auto-select all imported zones + keep existing Beat Breeze selection
      const allSoundtrack = [...selectedSoundtrack, ...importedZones];
      const currentBB = selectedZones.filter(z => z.platform === 'beatbreeze');
      onChange([...allSoundtrack, ...currentBB]);

      setImportComplete(true);
    } catch (err) {
      console.error('Failed to import zones from API:', err);
    } finally {
      setImportingFromApi(false);
    }
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

        {hasSoundtrackZones && (
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
        )}

        {/* Import from Soundtrack API */}
        {previewZones.length > 0 && (
          <Box sx={{ mt: hasSoundtrackZones ? 2 : 0 }}>
            {importComplete && unimportedPreviewZones.length === 0 ? (
              <Alert severity="success" variant="outlined" sx={{ py: 0.5 }}>
                All {previewZones.length} zones imported from Soundtrack API
              </Alert>
            ) : (
              <Alert
                severity="info"
                variant="outlined"
                sx={{ py: 0.5 }}
                action={
                  <Button
                    size="small"
                    startIcon={importingFromApi ? <CircularProgress size={16} color="inherit" /> : <CloudDownload />}
                    onClick={handleImportFromApi}
                    disabled={disabled || importingFromApi || unimportedPreviewZones.length === 0}
                    variant="contained"
                    sx={{ whiteSpace: 'nowrap' }}
                  >
                    {importingFromApi ? 'Importing...' : `Import ${unimportedPreviewZones.length} Zone${unimportedPreviewZones.length !== 1 ? 's' : ''}`}
                  </Button>
                }
              >
                {unimportedPreviewZones.length} zone{unimportedPreviewZones.length !== 1 ? 's' : ''} found via Soundtrack API
              </Alert>
            )}
          </Box>
        )}

        {/* Add New Soundtrack Zone (manual) */}
        <Divider sx={{ my: 2 }}>
          <Typography variant="caption" color="text.secondary">
            Add New Zone
          </Typography>
        </Divider>

        <Box sx={{ display: 'flex', gap: 1 }}>
          <TextField
            size="small"
            fullWidth
            placeholder="Enter new Soundtrack zone name..."
            value={newSoundtrackName}
            onChange={(e) => setNewSoundtrackName(e.target.value)}
            disabled={disabled || addingSoundtrackZone}
            onKeyPress={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                handleAddNewSoundtrack();
              }
            }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <MusicNote sx={{ color: '#1976d2', fontSize: 20 }} />
                </InputAdornment>
              ),
            }}
          />
          <Button
            variant="contained"
            onClick={handleAddNewSoundtrack}
            disabled={disabled || addingSoundtrackZone || !newSoundtrackName.trim()}
            sx={{
              minWidth: 'auto',
              px: 2,
              backgroundColor: '#1976d2',
              '&:hover': { backgroundColor: '#1565c0' },
            }}
          >
            {addingSoundtrackZone ? <CircularProgress size={20} color="inherit" /> : <Add />}
          </Button>
        </Box>

        <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
          Add zones manually when Soundtrack account is not yet set up
        </Typography>
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

      {/* Overlap Warning */}
      {overlaps.length > 0 && (
        <Alert severity="warning" variant="outlined">
          <Typography variant="body2" fontWeight={500} sx={{ mb: 0.5 }}>
            Zone overlap detected
          </Typography>
          {overlaps.map((o, i) => (
            <Typography key={i} variant="body2">
              "{o.zone_name}" is already on active contract <strong>{o.conflicting_contract_number}</strong>
            </Typography>
          ))}
          <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
            This may be expected for renewals. Proceed if intentional.
          </Typography>
        </Alert>
      )}

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
