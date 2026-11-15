import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import { Contract } from '../types';
import ContractDetail from '../components/ContractDetail';
import ContractForm from '../components/ContractForm';

/** The contract record page: /contracts/:id. The component below loads the contract (once). */
const ContractDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();

  // The contract as the component loaded it, handed over when Edit is clicked.
  const [contract, setContract] = useState<Contract | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  // Bumped after an edit so the page reloads the saved contract.
  const [version, setVersion] = useState(0);

  const handleEdit = (loaded: Contract) => {
    setContract(loaded);
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
