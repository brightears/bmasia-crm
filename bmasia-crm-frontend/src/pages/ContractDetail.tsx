import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Button,
  Paper,
  Alert,
  CircularProgress,
  Breadcrumbs,
  Link,
} from '@mui/material';
import {
  ArrowBack,
  Edit,
} from '@mui/icons-material';
import { Contract } from '../types';
import ApiService from '../services/api';
import ContractDetail from '../components/ContractDetail';
import ContractForm from '../components/ContractForm';

const ContractDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [contract, setContract] = useState<Contract | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [formOpen, setFormOpen] = useState(false);

  useEffect(() => {
    if (id) {
      loadContract();
    }
  }, [id]);

  const loadContract = async () => {
    if (!id) return;

    try {
      setLoading(true);
      setError('');

      const contractData = await ApiService.getContract(id);
      setContract(contractData);
    } catch (err: any) {
      setError('Failed to load contract details');
      console.error('Contract detail error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleBack = () => {
    navigate('/contracts');
  };

  const handleEdit = () => {
    setFormOpen(true);
  };

  const handleContractSave = (updatedContract: Contract) => {
    setContract(updatedContract);
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error || !contract) {
    return (
      <Box>
        <Alert severity="error" sx={{ mb: 2 }}>
          {error || 'Contract not found'}
        </Alert>
        <Button
          variant="outlined"
          startIcon={<ArrowBack />}
          onClick={handleBack}
        >
          Back to Contracts
        </Button>
      </Box>
    );
  }

  return (
    <Box>
      {/* Breadcrumbs */}
      <Breadcrumbs sx={{ mb: 2 }}>
        <Link
          component="button"
          variant="body1"
          onClick={handleBack}
          sx={{ textDecoration: 'none', cursor: 'pointer' }}
        >
          Contracts
        </Link>
        <Typography color="text.primary">
          {contract.contract_number}
        </Typography>
      </Breadcrumbs>

      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h4" component="h1">
            Contract Details
          </Typography>
          <Typography variant="body1" color="text.secondary">
            {contract.company_name} - {contract.contract_number}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="outlined"
            startIcon={<ArrowBack />}
            onClick={handleBack}
          >
            Back
          </Button>
          <Button
            variant="contained"
            startIcon={<Edit />}
            onClick={handleEdit}
          >
            Edit Contract
          </Button>
        </Box>
      </Box>

      {/* Contract Detail Component as Page Content */}
      <Paper sx={{ p: 0 }}>
        <ContractDetail
          open={true}
          onClose={() => {}}
          onEdit={handleEdit}
          contractId={id || null}
        />
      </Paper>

      {/* Contract Form */}
      <ContractForm
        open={formOpen}
        onClose={() => setFormOpen(false)}
        onSave={handleContractSave}
        contract={contract}
        mode="edit"
      />
    </Box>
  );
};

export default ContractDetailPage;