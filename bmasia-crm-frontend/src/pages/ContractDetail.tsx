import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Contract } from '../types';
import ApiService from '../services/api';
import ContractDetail from '../components/ContractDetail';
import ContractForm from '../components/ContractForm';

/** The contract record page: /contracts/:id */
const ContractDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();

  const [contract, setContract] = useState<Contract | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  // Bumped after an edit so the page reloads the saved contract.
  const [version, setVersion] = useState(0);

  useEffect(() => {
    if (!id) return;
    ApiService.getContract(id)
      .then(setContract)
      .catch((err) => console.error('Contract detail error:', err));
  }, [id, version]);

  const handleEdit = () => {
    setFormOpen(true);
  };

  const handleContractSave = (updatedContract: Contract) => {
    setContract(updatedContract);
    setVersion((v) => v + 1);
  };

  return (
    <>
      <ContractDetail
        key={`${id}-${version}`}
        variant="page"
        open={true}
        onClose={() => {}}
        onEdit={handleEdit}
        onContractUpdated={setContract}
        contractId={id || null}
      />

      {/* Contract Form */}
      {contract && (
        <ContractForm
          open={formOpen}
          onClose={() => setFormOpen(false)}
          onSave={handleContractSave}
          contract={contract}
          mode="edit"
        />
      )}
    </>
  );
};

export default ContractDetailPage;
