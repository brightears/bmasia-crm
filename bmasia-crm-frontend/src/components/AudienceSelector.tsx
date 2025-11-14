import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  TextField,
  Checkbox,
  FormControlLabel,
  Button,
  CircularProgress,
  Alert,
  Paper,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Chip,
  InputAdornment,
} from '@mui/material';
import {
  ExpandMore,
  Search,
  CheckBox,
  CheckBoxOutlineBlank,
} from '@mui/icons-material';
import { Contact } from '../types';
import ApiService from '../services/api';

interface AudienceSelectorProps {
  selectedContactIds: string[];
  onSelectionChange: (contactIds: string[]) => void;
}

interface ContactsByCompany {
  [companyName: string]: Contact[];
}

const AudienceSelector: React.FC<AudienceSelectorProps> = ({
  selectedContactIds,
  onSelectionChange,
}) => {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    loadContacts();
  }, []);

  const loadContacts = async () => {
    try {
      setLoading(true);
      setError('');
      const response = await ApiService.getContacts({ is_active: true, page_size: 1000 });
      setContacts(response.results);
    } catch (err: any) {
      console.error('Failed to load contacts:', err);
      setError('Failed to load contacts');
    } finally {
      setLoading(false);
    }
  };

  const groupContactsByCompany = (): ContactsByCompany => {
    const grouped: ContactsByCompany = {};

    contacts.forEach((contact) => {
      const companyName = contact.company_name || 'Unknown Company';
      if (!grouped[companyName]) {
        grouped[companyName] = [];
      }
      grouped[companyName].push(contact);
    });

    return grouped;
  };

  const filterContacts = (contactsList: Contact[]): Contact[] => {
    if (!searchTerm) return contactsList;

    const search = searchTerm.toLowerCase();
    return contactsList.filter(
      (contact) =>
        contact.name.toLowerCase().includes(search) ||
        contact.email.toLowerCase().includes(search) ||
        contact.company_name.toLowerCase().includes(search)
    );
  };

  const handleSelectAll = () => {
    const filteredContacts = filterContacts(contacts);
    const allIds = filteredContacts.map((c) => c.id);
    onSelectionChange(allIds);
  };

  const handleDeselectAll = () => {
    onSelectionChange([]);
  };

  const handleToggleContact = (contactId: string) => {
    if (selectedContactIds.includes(contactId)) {
      onSelectionChange(selectedContactIds.filter((id) => id !== contactId));
    } else {
      onSelectionChange([...selectedContactIds, contactId]);
    }
  };

  const handleToggleCompany = (companyContacts: Contact[]) => {
    const companyContactIds = companyContacts.map((c) => c.id);
    const allSelected = companyContactIds.every((id) =>
      selectedContactIds.includes(id)
    );

    if (allSelected) {
      // Deselect all from this company
      onSelectionChange(
        selectedContactIds.filter((id) => !companyContactIds.includes(id))
      );
    } else {
      // Select all from this company
      const newSelected = [...selectedContactIds];
      companyContactIds.forEach((id) => {
        if (!newSelected.includes(id)) {
          newSelected.push(id);
        }
      });
      onSelectionChange(newSelected);
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }

  const contactsByCompany = groupContactsByCompany();
  const companyNames = Object.keys(contactsByCompany).sort();
  const filteredContacts = filterContacts(contacts);
  const filteredCompanyNames = companyNames.filter((companyName) =>
    contactsByCompany[companyName].some((contact) =>
      filteredContacts.includes(contact)
    )
  );

  return (
    <Box>
      <Box sx={{ mb: 2, display: 'flex', gap: 2, alignItems: 'center' }}>
        <TextField
          fullWidth
          size="small"
          placeholder="Search contacts by name, email, or company..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <Search />
              </InputAdornment>
            ),
          }}
        />
        <Button
          variant="outlined"
          size="small"
          startIcon={<CheckBox />}
          onClick={handleSelectAll}
          sx={{ whiteSpace: 'nowrap' }}
        >
          Select All
        </Button>
        <Button
          variant="outlined"
          size="small"
          startIcon={<CheckBoxOutlineBlank />}
          onClick={handleDeselectAll}
          sx={{ whiteSpace: 'nowrap' }}
        >
          Deselect All
        </Button>
      </Box>

      <Paper variant="outlined" sx={{ mb: 2, p: 1 }}>
        <Typography variant="body2" color="text.secondary">
          Selected: <Chip label={selectedContactIds.length} size="small" color="primary" /> of {contacts.length} contacts
        </Typography>
      </Paper>

      {filteredCompanyNames.length === 0 ? (
        <Alert severity="info">No contacts found matching your search.</Alert>
      ) : (
        <Box sx={{ maxHeight: 400, overflowY: 'auto' }}>
          {filteredCompanyNames.map((companyName) => {
            const companyContacts = contactsByCompany[companyName].filter((c) =>
              filteredContacts.includes(c)
            );
            const companyContactIds = companyContacts.map((c) => c.id);
            const allSelected = companyContactIds.every((id) =>
              selectedContactIds.includes(id)
            );
            const someSelected =
              companyContactIds.some((id) => selectedContactIds.includes(id)) &&
              !allSelected;

            return (
              <Accordion key={companyName} defaultExpanded={filteredCompanyNames.length <= 5}>
                <AccordionSummary expandIcon={<ExpandMore />}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Checkbox
                      checked={allSelected}
                      indeterminate={someSelected}
                      onChange={() => handleToggleCompany(companyContacts)}
                      onClick={(e) => e.stopPropagation()}
                    />
                    <Typography fontWeight="medium">{companyName}</Typography>
                    <Chip
                      label={companyContacts.length}
                      size="small"
                      color={allSelected ? 'primary' : 'default'}
                    />
                  </Box>
                </AccordionSummary>
                <AccordionDetails>
                  <Box sx={{ pl: 2 }}>
                    {companyContacts.map((contact) => (
                      <FormControlLabel
                        key={contact.id}
                        control={
                          <Checkbox
                            checked={selectedContactIds.includes(contact.id)}
                            onChange={() => handleToggleContact(contact.id)}
                          />
                        }
                        label={
                          <Box>
                            <Typography variant="body2">{contact.name}</Typography>
                            <Typography variant="caption" color="text.secondary">
                              {contact.email}
                              {contact.contact_type && ` • ${contact.contact_type}`}
                            </Typography>
                          </Box>
                        }
                        sx={{ display: 'flex', width: '100%' }}
                      />
                    ))}
                  </Box>
                </AccordionDetails>
              </Accordion>
            );
          })}
        </Box>
      )}
    </Box>
  );
};

export default AudienceSelector;
