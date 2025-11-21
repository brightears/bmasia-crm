import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Box, CircularProgress, Alert } from '@mui/material';
import { Equipment } from '../types';
import ApiService from '../services/api';
import EquipmentForm from '../components/EquipmentForm';

const EquipmentEdit: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [equipment, setEquipment] = useState<Equipment | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (id) {
      loadEquipment();
    }
  }, [id]);

  const loadEquipment = async () => {
    if (!id) return;
    try {
      setLoading(true);
      const data = await ApiService.getEquipmentItem(id);
      setEquipment(data);
    } catch (err: any) {
      console.error('Equipment load error:', err);
      setError('Failed to load equipment');
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

  if (error || !equipment) {
    return (
      <Alert severity="error" sx={{ mb: 2 }}>
        {error || 'Equipment not found'}
      </Alert>
    );
  }

  return <EquipmentForm equipment={equipment} mode="edit" />;
};

export default EquipmentEdit;
