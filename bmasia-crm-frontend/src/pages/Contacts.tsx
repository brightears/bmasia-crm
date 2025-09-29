import React, { useState, useEffect } from 'react';
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
  Grid,
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
  Phone,
  MoreVert,
  People,
  Business,
  LinkedIn,
  FilterList,
  Clear,
} from '@mui/icons-material';
import { Contact, Company, ApiResponse } from '../types';
import ApiService from '../services/api';
import ContactForm from '../components/ContactForm';
import ContactDetail from '../components/ContactDetail';

const Contacts: React.FC = () => {
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
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  // Modals
  const [formOpen, setFormOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [editMode, setEditMode] = useState(false);

  // Menu
  const [menuAnchor, setMenuAnchor] = useState<null | HTMLElement>(null);
  const [menuContact, setMenuContact] = useState<Contact | null>(null);

  useEffect(() => {
    loadContacts();
    loadCompanies();
  }, [page, rowsPerPage, search, selectedCompany, selectedStatus, dateFrom, dateTo]);

  const loadContacts = async () => {
    try {
      setLoading(true);
      const params: any = {
        page: page + 1,
        page_size: rowsPerPage,
        search: search || undefined,
        company: selectedCompany || undefined,
        status: selectedStatus || undefined,
        created_after: dateFrom || undefined,
        created_before: dateTo || undefined,
        ordering: '-created_at',
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
  };

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

  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearch(event.target.value);
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

  const clearFilters = () => {
    setSelectedCompany('');
    setSelectedStatus('');
    setDateFrom('');
    setDateTo('');
    setSearch('');
    setPage(0);
  };

  const getStatusColor = (status: string) => {
    return status === 'Active' ? 'success' : 'default';
  };

  const formatLastContacted = (date: string | undefined) => {
    if (!date) return 'Never';
    const contactDate = new Date(date);
    const now = new Date();
    const diffTime = Math.abs(now.getTime() - contactDate.getTime());
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

    if (diffDays === 1) return '1 day ago';
    if (diffDays < 7) return `${diffDays} days ago`;
    if (diffDays < 30) return `${Math.ceil(diffDays / 7)} weeks ago`;
    return `${Math.ceil(diffDays / 30)} months ago`;
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
      <Paper sx={{ mb: 2, p: 2 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} md={4}>
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
          </Grid>
          <Grid item xs={12} md={2}>
            <FormControl fullWidth>
              <InputLabel>Company</InputLabel>
              <Select
                value={selectedCompany}
                onChange={(e) => setSelectedCompany(e.target.value)}
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
          </Grid>
          <Grid item xs={12} md={2}>
            <FormControl fullWidth>
              <InputLabel>Status</InputLabel>
              <Select
                value={selectedStatus}
                onChange={(e) => setSelectedStatus(e.target.value)}
                label="Status"
              >
                <MenuItem value="">All Status</MenuItem>
                <MenuItem value="Active">Active</MenuItem>
                <MenuItem value="Inactive">Inactive</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} md={2}>
            <TextField
              fullWidth
              type="date"
              label="From Date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              InputLabelProps={{ shrink: true }}
            />
          </Grid>
          <Grid item xs={12} md={1}>
            <TextField
              fullWidth
              type="date"
              label="To Date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              InputLabelProps={{ shrink: true }}
            />
          </Grid>
          <Grid item xs={12} md={1}>
            <Tooltip title="Clear Filters">
              <IconButton onClick={clearFilters} color="primary">
                <Clear />
              </IconButton>
            </Tooltip>
          </Grid>
        </Grid>
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
              <TableCell>Last Contact</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={8} align="center">
                  <CircularProgress />
                </TableCell>
              </TableRow>
            ) : contacts.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} align="center">
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
              contacts.map((contact) => (
                <TableRow key={contact.id} hover>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                      <Avatar sx={{ mr: 2, bgcolor: 'primary.main', width: 40, height: 40 }}>
                        {contact.first_name[0]}{contact.last_name[0]}
                      </Avatar>
                      <Box>
                        <Typography variant="body2" fontWeight="medium">
                          {contact.name}
                          {contact.is_decision_maker && (
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
                    {contact.phone && (
                      <Typography variant="body2">{contact.phone}</Typography>
                    )}
                    {contact.mobile && (
                      <Typography variant="caption" color="text.secondary" display="block">
                        Mobile: {contact.mobile}
                      </Typography>
                    )}
                    {!contact.phone && !contact.mobile && '-'}
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2">
                      {formatLastContacted(contact.last_contacted)}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={contact.status}
                      size="small"
                      color={getStatusColor(contact.status)}
                    />
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
                          onClick={(e) => handleMenuOpen(e, contact)}
                        >
                          <MoreVert />
                        </IconButton>
                      </Tooltip>
                    </Box>
                  </TableCell>
                </TableRow>
              ))
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