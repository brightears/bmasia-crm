import React, { useState, useEffect } from 'react';
import {
  Autocomplete,
  TextField,
  Chip,
  Box,
  Typography,
  CircularProgress,
  Alert,
} from '@mui/material';
import {
  LocationOn,
  CheckCircle,
  Warning,
  WifiOff,
  HelpOutline,
} from '@mui/icons-material';
import { Zone } from '../types';
import ApiService from '../services/api';

interface ZonePickerProps {
  companyId: string | null;
  selectedZones: Zone[];
  onChange: (zones: Zone[]) => void;
  disabled?: boolean;
  error?: boolean;
  helperText?: string;
}

const ZonePicker: React.FC<ZonePickerProps> = ({
  companyId,
  selectedZones,
  onChange,
  disabled = false,
  error = false,
  helperText,
}) => {
  const [availableZones, setAvailableZones] = useState<Zone[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (companyId) {
      loadZones(companyId);
    } else {
      setAvailableZones([]);
    }
  }, [companyId]);

  const loadZones = async (compId: string) => {
    setLoading(true);
    setLoadError(null);
    try {
      const zones = await ApiService.getZonesByCompany(compId);
      setAvailableZones(zones);
    } catch (err) {
      setLoadError('Failed to load zones. Please sync with Soundtrack first.');
      setAvailableZones([]);
    } finally {
      setLoading(false);
    }
  };

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

  if (availableZones.length === 0) {
    return (
      <Alert severity="warning" sx={{ mt: 2 }}>
        No zones found for this company. Please sync with Soundtrack API first from the Zone Status page.
      </Alert>
    );
  }

  return (
    <Autocomplete
      multiple
      options={availableZones}
      value={selectedZones}
      onChange={(_, newValue) => onChange(newValue)}
      disabled={disabled}
      getOptionLabel={(option) => option.name}
      isOptionEqualToValue={(option, value) => option.id === value.id}
      renderInput={(params) => (
        <TextField
          {...params}
          label="Select Zones"
          placeholder={selectedZones.length === 0 ? 'Choose zones for this contract' : ''}
          error={error}
          helperText={helperText}
          InputProps={{
            ...params.InputProps,
            startAdornment: (
              <>
                <LocationOn sx={{ color: '#FFA500', ml: 1, mr: 0.5 }} />
                {params.InputProps.startAdornment}
              </>
            ),
          }}
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
              {option.platform === 'soundtrack' ? 'Soundtrack' : 'Beat Breeze'} | {getStatusLabel(option.status)}
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
        sx: {
          maxHeight: 300,
        },
      }}
    />
  );
};

export default ZonePicker;
