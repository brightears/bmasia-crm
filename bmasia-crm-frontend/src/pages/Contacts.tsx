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
  CircularProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Tooltip,
  Avatar,
  Menu,
  ListItemIcon,
  ListItemText,
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
  Business,
  LinkedIn,
  Sort,
} from '@mui/icons-material';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Contact, Company, ApiResponse } from '../types';
import ApiService from '../services/api';
import ContactForm from '../components/ContactForm';
import ContactDetail from '../components/ContactDetail';

const sortOptions = [
  { value: 'name', label: 'Name A-Z' },
  { value: '-name', label: 'Name Z-A' },
  { value: '-created_at', label: 'Newest First' },
  { value: 'created_at', label: 'Oldest First' },
  { value: '-updated_at', label: 'Recently Updated' },
  { value: 'company__name', label: 'Company' },
];

const Contacts: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [totalCount, setTotalCount] = useState(0);

  // Filters
  const [selectedCompany, setSelectedCompany] = useState('');
  const [selectedStatus, setSelectedStatus] = useState('');
  const [sortBy, setSortBy] = useState('name');

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
      const response: ApiResponse<Company> = await ApiService.getCompanies({
        page_size: 1000,
        ordering: 'name',
      });
      setCompanies(response.results);
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
    setSearch(event.target.value);
    setPage(0);
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

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1">
          Contacts
        </Typography>
        <Button
          variant="contained"
          startIcon={<Add />}
          onClick={handleNewContact}
        >
          New Contact
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* Search and Filters */}
      <Paper sx={{ mb: 2 }}>
        <Box sx={{ p: 2, display: 'flex', gap: 2, alignItems: 'center' }}>
          <TextField
            fullWidth
            placeholder="Search contacts..."
            value={search}
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
            <InputLabel>Company</InputLabel>
            <Select
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
            <InputLabel>Status</InputLabel>
            <Select
              value={selectedStatus}
              onChange={(e) => { setSelectedStatus(e.target.value); setPage(0); }}
              label="Status"
            >
              <MenuItem value="">All</MenuItem>
              <MenuItem value="Active">Active</MenuItem>
              <MenuItem value="Inactive">Inactive</MenuItem>
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 200 }}>
            <Select
              value={sortBy}
              onChange={handleSortChange}
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
      </Paper>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Contact</TableCell>
              <TableCell>Title</TableCell>
              <TableCell>Company</TableCell>
              <TableCell>Email</TableCell>
              <TableCell>Phone</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={7} align="center">
                  <CircularProgress />
                </TableCell>
              </TableRow>
            ) : contacts.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} align="center">
                  <Box sx={{ py: 4 }}>
                    <People sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
                    <Typography variant="h6" color="text.secondary">
                      No contacts found
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {search || selectedCompany || selectedStatus ?
                        'Try adjusting your search criteria' :
                        'Start by adding your first contact'
                      }
                    </Typography>
                  </Box>
                </TableCell>
              </TableRow>
            ) : (
              contacts.map((contact) => {
                // Get initials from name
                const nameParts = contact.name.split(' ');
                const initials = nameParts.length >= 2
                  ? `${nameParts[0][0]}${nameParts[nameParts.length - 1][0]}`
                  : contact.name.substring(0, 2);
                const isDecisionMaker = contact.contact_type === 'Decision Maker';

                return (
                  <TableRow key={contact.id} hover sx={{ cursor: 'pointer' }} onClick={() => handleViewContact(contact)}>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        <Avatar sx={{ mr: 2, bgcolor: 'primary.main', width: 40, height: 40 }}>
                          {initials.toUpperCase()}
                        </Avatar>
                        <Box>
                          <Typography variant="body2" fontWeight="medium">
                            {contact.name}
                            {isDecisionMaker && (
                              <Chip
                                label="Decision Maker"
                                size="small"
                                color="primary"
                                sx={{ ml: 1, fontSize: '0.7rem' }}
                              />
                            )}
                          </Typography>
                          {contact.department && (
                            <Typography variant="caption" color="text.secondary">
                              {contact.department}
                            </Typography>
                          )}
                        </Box>
                      </Box>
                    </TableCell>
                    <TableCell>{contact.title || '-'}</TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        <Business sx={{ mr: 1, fontSize: 16, color: 'text.secondary' }} />
                        {contact.company_name}
                      </Box>
                    </TableCell>
                    <TableCell>{contact.email}</TableCell>
                    <TableCell>
                      {contact.phone ? (
                        <Typography variant="body2">{contact.phone}</Typography>
                      ) : '-'}
                    </TableCell>
                    <TableCell>
                      {!contact.is_active && (
                        <Chip
                          label="Inactive"
                          size="small"
                          color="default"
                        />
                      )}
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        {contact.email && (
                          <Tooltip title="Send Email">
                            <IconButton
                              size="small"
                              onClick={() => handleSendEmail(contact)}
                            >
                              <Email />
                            </IconButton>
                          </Tooltip>
                        )}
                        {contact.linkedin_url && (
                          <Tooltip title="LinkedIn Profile">
                            <IconButton
                              size="small"
                              onClick={() => window.open(contact.linkedin_url, '_blank')}
                            >
                              <LinkedIn />
                            </IconButton>
                          </Tooltip>
                        )}
                        <Tooltip title="More Actions">
                          <IconButton
                            size="small"
                            onClick={(e) => { e.stopPropagation(); handleMenuOpen(e, contact); }}
                          >
                            <MoreVert />
                          </IconButton>
                        </Tooltip>
                      </Box>
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
        <TablePagination
          rowsPerPageOptions={[10, 25, 50, 100]}
          component="div"
          count={totalCount}
          rowsPerPage={rowsPerPage}
          page={page}
          onPageChange={handleChangePage}
          onRowsPerPageChange={handleChangeRowsPerPage}
        />
      </TableContainer>

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
