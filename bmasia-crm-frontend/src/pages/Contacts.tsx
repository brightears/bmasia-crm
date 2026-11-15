import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Button,
  TextField,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  Chip,
  IconButton,
  InputAdornment,
  Alert,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Tooltip,
  Avatar,
  Menu,
  ListItemIcon,
  ListItemText,
  Link,
  Skeleton,
} from '@mui/material';
import {
  Add,
  Search,
  Edit,
  Delete,
  Visibility,
  Email,
  MoreVert,
  People,
  LinkedIn,
  Sort,
} from '@mui/icons-material';
import { useSearchParams, Link as RouterLink } from 'react-router-dom';
import { Contact, Company, ApiResponse } from '../types';
import ApiService from '../services/api';
import ContactForm from '../components/ContactForm';
import ContactDetail from '../components/ContactDetail';
import { PageHeader, EmptyState } from '../components/ui';
import { initialsOf, visuallyHidden } from '../theme';
import { useListState, optionValues, idFromList } from '../hooks/useListState';
import { useListSearchBox } from '../hooks/useListSearchBox';

const sortOptions = [
  { value: 'name', label: 'Name A-Z' },
  { value: '-name', label: 'Name Z-A' },
  { value: '-created_at', label: 'Newest First' },
  { value: 'created_at', label: 'Oldest First' },
  { value: '-updated_at', label: 'Recently Updated' },
  { value: 'company__name', label: 'Company' },
];

const statusOptions = [
  { value: '', label: 'All' },
  { value: 'Active', label: 'Active' },
  { value: 'Inactive', label: 'Inactive' },
];

const Contacts: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [totalCount, setTotalCount] = useState(0);

  // Search, filters, sort and page live in the address, so a filtered list can be shared as a
  // link and a reload keeps the view. Unknown values in the address fall back to the defaults.
  const list = useListState(
    { q: '', company: '', status: '', sort: 'name', page: 0, size: 25 },
    { company: idFromList(companies), status: optionValues(statusOptions), sort: optionValues(sortOptions) },
    companies.length
  );
  const [search, setSearch] = list.bind('q');
  const [selectedCompany, setSelectedCompany] = list.bind('company');
  const [selectedStatus, setSelectedStatus] = list.bind('status');
  const [sortBy, setSortBy] = list.bind('sort');
  const [page, setPage] = list.bind('page');
  const [rowsPerPage, setRowsPerPage] = list.bind('size');
  // The box's own text, written to the address shortly after typing stops.
  const searchBox = useListSearchBox(search, (text) => {
    setSearch(text);
    setPage(0);
  });

  // Modals
  const [formOpen, setFormOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [editMode, setEditMode] = useState(false);

  // Menu
  const [menuAnchor, setMenuAnchor] = useState<null | HTMLElement>(null);
  const [menuContact, setMenuContact] = useState<Contact | null>(null);

  // Handle query param for opening create dialog from dashboard
  useEffect(() => {
    if (searchParams.get('new') === 'true') {
      setSelectedContact(null);
      setEditMode(false);
      setFormOpen(true);
      // Clear the query param to avoid re-opening on refresh
      searchParams.delete('new');
      setSearchParams(searchParams, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const loadContacts = useCallback(async () => {
    try {
      setLoading(true);
      const params: any = {
        page: page + 1,
        page_size: rowsPerPage,
        search: search || undefined,
        company: selectedCompany || undefined,
        is_active: selectedStatus === 'Active' ? true : selectedStatus === 'Inactive' ? false : undefined,
        ordering: sortBy,
      };

      const response: ApiResponse<Contact> = await ApiService.getContacts(params);
      setContacts(response.results);
      setTotalCount(response.count);
    } catch (err: any) {
      setError('Failed to load contacts');
      console.error('Contacts error:', err);
    } finally {
      setLoading(false);
    }
  }, [page, rowsPerPage, search, selectedCompany, selectedStatus, sortBy]);

  const loadCompanies = async () => {
    try {
      const companiesData = await ApiService.getCompaniesSimple({ ordering: 'name' });
      setCompanies(companiesData as any[]);
    } catch (err: any) {
      console.error('Failed to load companies:', err);
    }
  };

  useEffect(() => {
    loadContacts();
  }, [loadContacts]);

  useEffect(() => {
    loadCompanies();
  }, []);

  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    searchBox.onChange(event.target.value);
  };

  const handleSortChange = (event: any) => {
    setSortBy(event.target.value);
    setPage(0);
  };

  const handleChangePage = (event: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const handleNewContact = () => {
    setSelectedContact(null);
    setEditMode(false);
    setFormOpen(true);
  };

  const handleEditContact = (contact: Contact) => {
    setSelectedContact(contact);
    setEditMode(true);
    setFormOpen(true);
    setMenuAnchor(null);
  };

  const handleViewContact = (contact: Contact) => {
    setSelectedContact(contact);
    setDetailOpen(true);
    setMenuAnchor(null);
  };

  const handleDeleteContact = async (contact: Contact) => {
    if (window.confirm(`Are you sure you want to delete ${contact.name}?`)) {
      try {
        await ApiService.deleteContact(contact.id);
        loadContacts();
        setMenuAnchor(null);
      } catch (err: any) {
        setError('Failed to delete contact');
      }
    }
  };

  const handleSendEmail = (contact: Contact) => {
    window.open(`mailto:${contact.email}`, '_blank');
    setMenuAnchor(null);
  };

  const handleContactSaved = () => {
    setFormOpen(false);
    loadContacts();
  };

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, contact: Contact) => {
    setMenuAnchor(event.currentTarget);
    setMenuContact(contact);
  };

  const handleMenuClose = () => {
    setMenuAnchor(null);
    setMenuContact(null);
  };

  const filtersActive = Boolean(search || selectedCompany || selectedStatus);
  const hideBelowMd = { display: { xs: 'none', md: 'table-cell' } };
  const hideBelowLg = { display: { xs: 'none', lg: 'table-cell' } };

  return (
    <Box>
      <PageHeader
        title="Contacts"
        subtitle="People at customer companies: who decides, who signs, who gets the invoices."
        actions={
          <Button variant="contained" startIcon={<Add />} onClick={handleNewContact}>
            New Contact
          </Button>
        }
      />

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* Filters and table in one card */}
      <Paper sx={{ overflow: 'hidden' }}>
        <Box sx={{ p: 2, display: 'flex', gap: 1.5, alignItems: 'center', flexWrap: 'wrap', borderBottom: 1, borderColor: 'divider' }}>
          <TextField
            sx={{ flex: '1 1 240px', maxWidth: { md: 380 } }}
            inputProps={{ 'aria-label': 'Search contacts' }}
            placeholder="Search by name, email, phone or company"
            value={searchBox.value}
            onChange={handleSearchChange}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <Search />
                </InputAdornment>
              ),
            }}
          />
          <FormControl size="small" sx={{ minWidth: 180 }}>
            <InputLabel id="contacts-company-label">Company</InputLabel>
            <Select
              labelId="contacts-company-label"
              value={selectedCompany}
              onChange={(e) => { setSelectedCompany(e.target.value); setPage(0); }}
              label="Company"
            >
              <MenuItem value="">All Companies</MenuItem>
              {companies.map((company) => (
                <MenuItem key={company.id} value={company.id}>
                  {company.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel id="contacts-status-label">Status</InputLabel>
            <Select
              labelId="contacts-status-label"
              value={selectedStatus}
              onChange={(e) => { setSelectedStatus(e.target.value); setPage(0); }}
              label="Status"
            >
              {statusOptions.map((option) => (
                <MenuItem key={option.value} value={option.value}>
                  {option.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 200 }}>
            <Select
              value={sortBy}
              onChange={handleSortChange}
              inputProps={{ 'aria-label': 'Sort contacts' }}
              startAdornment={<Sort sx={{ mr: 0.5, ml: -0.5, color: 'text.secondary', fontSize: 20 }} />}
              sx={{ '& .MuiSelect-select': { display: 'flex', alignItems: 'center' } }}
            >
              {sortOptions.map((option) => (
                <MenuItem key={option.value} value={option.value}>
                  {option.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>

        <TableContainer sx={{ borderRadius: 0, position: 'relative' }}>
          <Table aria-label="Contacts">
            <TableHead>
              <TableRow>
                <TableCell>Contact</TableCell>
                <TableCell>Company</TableCell>
                <TableCell sx={hideBelowMd}>Email</TableCell>
                <TableCell sx={hideBelowLg}>Phone</TableCell>
                <TableCell sx={hideBelowMd}>Status</TableCell>
                <TableCell align="right"><Box component="span" sx={visuallyHidden}>Actions</Box></TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                Array.from({ length: 6 }).map((_, i) => (
                  <TableRow key={`skeleton-${i}`}>
                    {Array.from({ length: 6 }).map((__, j) => (
                      <TableCell key={j} sx={j === 2 || j === 4 ? hideBelowMd : j === 3 ? hideBelowLg : undefined}>
                        <Skeleton width={j === 5 ? 24 : '70%'} />
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              ) : contacts.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6}>
                    <EmptyState
                      icon={<People />}
                      title={filtersActive ? 'No contacts match these filters' : 'No contacts yet'}
                      description={filtersActive ? 'Try a different search or clear the filters.' : 'Add the first contact for a customer.'}
                    />
                  </TableCell>
                </TableRow>
              ) : (
                contacts.map((contact) => {
                  const isDecisionMaker = contact.contact_type === 'Decision Maker';
                  const role = [contact.title, contact.department].filter(Boolean).join(' · ');
                  return (
                    <TableRow key={contact.id} hover sx={{ cursor: 'pointer' }} onClick={() => handleViewContact(contact)}>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, minWidth: 0 }}>
                          <Avatar sx={{ width: 32, height: 32, fontSize: '0.75rem' }}>
                            {initialsOf(contact.name)}
                          </Avatar>
                          <Box sx={{ minWidth: 0 }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                              <Typography sx={{ fontWeight: 600, fontSize: '0.875rem' }}>{contact.name}</Typography>
                              {isDecisionMaker && <Chip label="Decision maker" size="small" color="primary" />}
                            </Box>
                            {role && (
                              <Typography variant="body2" color="text.secondary" noWrap>
                                {role}
                              </Typography>
                            )}
                          </Box>
                        </Box>
                      </TableCell>
                      <TableCell sx={{ maxWidth: 240 }}>
                        {contact.company ? (
                          <Link
                            component={RouterLink}
                            to={`/companies/${contact.company}`}
                            underline="hover"
                            color="inherit"
                            onClick={(e: React.MouseEvent) => e.stopPropagation()}
                            sx={{ fontWeight: 500, fontSize: '0.875rem', display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                          >
                            {contact.company_name}
                          </Link>
                        ) : (
                          <Typography variant="body2" noWrap>{contact.company_name || '—'}</Typography>
                        )}
                      </TableCell>
                      <TableCell sx={{ ...hideBelowMd, maxWidth: 260 }}>
                        <Typography variant="body2" noWrap>{contact.email || '—'}</Typography>
                      </TableCell>
                      <TableCell sx={{ ...hideBelowLg, whiteSpace: 'nowrap' }}>{contact.phone || '—'}</TableCell>
                      <TableCell sx={hideBelowMd}>
                        <Chip
                          label={contact.is_active ? 'Active' : 'Inactive'}
                          size="small"
                          color={contact.is_active ? 'success' : 'default'}
                        />
                      </TableCell>
                      <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
                        {contact.email && (
                          <Tooltip title="Send email">
                            <IconButton
                              size="small"
                              aria-label={`Send email to ${contact.name}`}
                              onClick={(e) => { e.stopPropagation(); handleSendEmail(contact); }}
                            >
                              <Email fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        )}
                        {contact.linkedin_url && (
                          <Tooltip title="LinkedIn profile">
                            <IconButton
                              size="small"
                              aria-label={`LinkedIn profile of ${contact.name}`}
                              onClick={(e) => { e.stopPropagation(); window.open(contact.linkedin_url, '_blank'); }}
                            >
                              <LinkedIn fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        )}
                        <Tooltip title="More actions">
                          <IconButton
                            size="small"
                            aria-label={`More actions for ${contact.name}`}
                            onClick={(e) => { e.stopPropagation(); handleMenuOpen(e, contact); }}
                          >
                            <MoreVert fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </TableContainer>
        <TablePagination
          rowsPerPageOptions={[10, 25, 50, 100]}
          component="div"
          count={totalCount}
          rowsPerPage={rowsPerPage}
          page={page}
          onPageChange={handleChangePage}
          onRowsPerPageChange={handleChangeRowsPerPage}
        />
      </Paper>

      {/* Action Menu */}
      <Menu
        anchorEl={menuAnchor}
        open={Boolean(menuAnchor)}
        onClose={handleMenuClose}
      >
        <MenuItem onClick={() => menuContact && handleViewContact(menuContact)}>
          <ListItemIcon>
            <Visibility fontSize="small" />
          </ListItemIcon>
          <ListItemText>View Details</ListItemText>
        </MenuItem>
        <MenuItem onClick={() => menuContact && handleEditContact(menuContact)}>
          <ListItemIcon>
            <Edit fontSize="small" />
          </ListItemIcon>
          <ListItemText>Edit Contact</ListItemText>
        </MenuItem>
        {menuContact?.email && (
          <MenuItem onClick={() => menuContact && handleSendEmail(menuContact)}>
            <ListItemIcon>
              <Email fontSize="small" />
            </ListItemIcon>
            <ListItemText>Send Email</ListItemText>
          </MenuItem>
        )}
        <MenuItem
          onClick={() => menuContact && handleDeleteContact(menuContact)}
          sx={{ color: 'error.main' }}
        >
          <ListItemIcon>
            <Delete fontSize="small" sx={{ color: 'error.main' }} />
          </ListItemIcon>
          <ListItemText>Delete Contact</ListItemText>
        </MenuItem>
      </Menu>

      {/* Contact Form Modal */}
      <ContactForm
        open={formOpen}
        onClose={() => setFormOpen(false)}
        onSave={handleContactSaved}
        contact={editMode ? selectedContact : null}
        companies={companies}
      />

      {/* Contact Detail Modal */}
      <ContactDetail
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        contact={selectedContact}
        onEdit={() => {
          setDetailOpen(false);
          setEditMode(true);
          setFormOpen(true);
        }}
      />
    </Box>
  );
};

export default Contacts;
