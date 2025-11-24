import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Box, CircularProgress, Alert } from '@mui/material';
import { Zone } from '../types';
import ApiService from '../services/api';
import ZoneForm from '../components/ZoneForm';

const ZoneEdit: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [zone, setZone] = useState<Zone | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (id) {
      loadZone();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const loadZone = async () => {
    if (!id) return;
    try {
      setLoading(true);
      const data = await ApiService.getZone(id);
      setZone(data);
    } catch (err: any) {
      console.error('Zone load error:', err);
      setError('Failed to load zone');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
        <CircularProgress size={40} />
      </Box>
    );
  }

  if (error || !zone) {
    return (
      <Alert severity="error" sx={{ mb: 2 }}>
        {error || 'Zone not found'}
      </Alert>
    );
  }

  return <ZoneForm zone={zone} mode="edit" />;
};

export default ZoneEdit;
