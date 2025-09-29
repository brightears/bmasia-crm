import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
  Button,
  Chip,
  IconButton,
  Alert,
  CircularProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Card,
  CardContent,
  CardActions,
  Divider,
  GridLegacy as Grid,
  Tabs,
  Tab,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Avatar,
  Tooltip,
  Fab,
} from '@mui/material';
import {
  Business,
  Edit,
  Email,
  Phone,
  Language,
  LocationOn,
  Person,
  TrendingUp,
  Assignment,
  AccountBalance,
  History,
  Add,
  ContactPhone,
  Handshake,
  PlaylistAdd,
  Public,
  Category,
} from '@mui/icons-material';
import { useParams, useNavigate } from 'react-router-dom';
import { Company, Contact, Opportunity, Contract } from '../types';
import ApiService from '../services/api';
import CompanyForm from '../components/CompanyForm';
import ContactForm from '../components/ContactForm';
import OpportunityForm from '../components/OpportunityForm';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`company-tabpanel-${index}`}
      aria-labelledby={`company-tab-${index}`}
      {...other}
    >
      {value === index && (
        <Box sx={{ p: 3 }}>
          {children}
        </Box>
      )}
    </div>
  );
}

function a11yProps(index: number) {
  return {
    id: `company-tab-${index}`,
    'aria-controls': `company-tabpanel-${index}`,
  };
}

const CompanyDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [company, setCompany] = useState<Company | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tabValue, setTabValue] = useState(0);
  const [editFormOpen, setEditFormOpen] = useState(false);
  const [contactFormOpen, setContactFormOpen] = useState(false);
  const [opportunityFormOpen, setOpportunityFormOpen] = useState(false);

  useEffect(() => {
    if (id) {
      loadCompanyData();
    }
  }, [id]);

  const loadCompanyData = async () => {
    if (!id) return;

    try {
      setLoading(true);
      setError('');

      // Load company details
      const companyData = await ApiService.getCompany(id);
      setCompany(companyData);

      // Load related data
      const [contactsResponse, opportunitiesResponse, contractsResponse] = await Promise.all([
        ApiService.getContacts({ company: id }),
        ApiService.getOpportunities({ company: id }),
        ApiService.getContracts({ company: id }),
      ]);

      setContacts(contactsResponse.results);
      setOpportunities(opportunitiesResponse.results);
      setContracts(contractsResponse.results);
    } catch (err: any) {
      console.error('Company detail error:', err);
      setError('Failed to load company details');
    } finally {
      setLoading(false);
    }
  };

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  const handleEditSave = () => {
    setEditFormOpen(false);
    loadCompanyData();
  };

  const handleContactSave = () => {
    setContactFormOpen(false);
    loadCompanyData();
  };

  const handleOpportunitySave = () => {
    setOpportunityFormOpen(false);
    loadCompanyData();
  };

  const formatCurrency = (amount: number, currency: string = 'USD') => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency,
    }).format(amount);
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'active':
      case 'signed':
      case 'won':
        return 'success';
      case 'inactive':
      case 'expired':
      case 'lost':
        return 'error';
      case 'contacted':
      case 'quotation sent':
      case 'contract sent':
        return 'warning';
      default:
        return 'default';
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
        <CircularProgress size={40} />
      </Box>
    );
  }

  if (error || !company) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error" sx={{ mb: 2 }}>
          {error || 'Company not found'}
        </Alert>
        <Button variant="contained" onClick={() => navigate('/companies')}>
          Back to Companies
        </Button>
      </Box>
    );
  }

  return (
    <Box sx={{ flexGrow: 1 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 3 }}>
        <Box>
          <Typography variant="h4" component="h1" gutterBottom>
            <Business sx={{ mr: 1, verticalAlign: 'bottom' }} />
            {company.name}
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
            <Chip
              label={company.is_active ? 'Active' : 'Inactive'}
              color={company.is_active ? 'success' : 'default'}
              size="small"
            />
            {company.industry && (
              <Chip
                label={company.industry}
                variant="outlined"
                size="small"
                icon={<Category />}
              />
            )}
            {company.country && (
              <Chip
                label={company.country}
                variant="outlined"
                size="small"
                icon={<Public />}
              />
            )}
          </Box>
        </Box>
        <Button
          variant="contained"
          startIcon={<Edit />}
          onClick={() => setEditFormOpen(true)}
        >
          Edit Company
        </Button>
      </Box>

      {/* Quick Stats Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <Person sx={{ mr: 1, color: 'primary.main' }} />
                <Typography variant="h6">{contacts.length}</Typography>
              </Box>
              <Typography variant="body2" color="text.secondary">
                Contacts
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <TrendingUp sx={{ mr: 1, color: 'warning.main' }} />
                <Typography variant="h6">{opportunities.length}</Typography>
              </Box>
              <Typography variant="body2" color="text.secondary">
                Opportunities
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <Assignment sx={{ mr: 1, color: 'success.main' }} />
                <Typography variant="h6">{contracts.length}</Typography>
              </Box>
              <Typography variant="body2" color="text.secondary">
                Contracts
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <AccountBalance sx={{ mr: 1, color: 'info.main' }} />
                <Typography variant="h6">
                  {formatCurrency(company.total_contract_value || 0)}
                </Typography>
              </Box>
              <Typography variant="body2" color="text.secondary">
                Total Value
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Company Information */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} md={8}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Company Information
              </Typography>
              <Grid container spacing={2}>
                {company.website && (
                  <Grid item xs={12} sm={6}>
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                      <Language sx={{ mr: 1, color: 'text.secondary' }} />
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Website
                        </Typography>
                        <Typography variant="body2">
                          <a href={company.website} target="_blank" rel="noopener noreferrer">
                            {company.website}
                          </a>
                        </Typography>
                      </Box>
                    </Box>
                  </Grid>
                )}
                <Grid item xs={12} sm={6}>
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <LocationOn sx={{ mr: 1, color: 'text.secondary' }} />
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Location
                      </Typography>
                      <Typography variant="body2">
                        {[company.city, company.country].filter(Boolean).join(', ') || 'Not specified'}
                      </Typography>
                    </Box>
                  </Box>
                </Grid>
                {company.full_address && (
                  <Grid item xs={12}>
                    <Box sx={{ display: 'flex', alignItems: 'flex-start' }}>
                      <LocationOn sx={{ mr: 1, color: 'text.secondary', mt: 0.5 }} />
                      <Box>
                        <Typography variant="caption" color="text.secondary">
                          Full Address
                        </Typography>
                        <Typography variant="body2">
                          {company.full_address}
                        </Typography>
                      </Box>
                    </Box>
                  </Grid>
                )}
                {company.notes && (
                  <Grid item xs={12}>
                    <Typography variant="caption" color="text.secondary">
                      Notes
                    </Typography>
                    <Typography variant="body2" sx={{ mt: 0.5 }}>
                      {company.notes}
                    </Typography>
                  </Grid>
                )}
              </Grid>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Quick Actions
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                <Button
                  variant="outlined"
                  startIcon={<ContactPhone />}
                  onClick={() => setContactFormOpen(true)}
                  fullWidth
                >
                  Add Contact
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<Handshake />}
                  onClick={() => setOpportunityFormOpen(true)}
                  fullWidth
                >
                  Create Opportunity
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<PlaylistAdd />}
                  onClick={() => navigate(`/tasks/new?company=${company.id}`)}
                  fullWidth
                >
                  Create Task
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Tabs */}
      <Paper sx={{ mb: 3 }}>
        <Tabs value={tabValue} onChange={handleTabChange} aria-label="company tabs">
          <Tab label={`Contacts (${contacts.length})`} {...a11yProps(0)} />
          <Tab label={`Opportunities (${opportunities.length})`} {...a11yProps(1)} />
          <Tab label={`Contracts (${contracts.length})`} {...a11yProps(2)} />
          <Tab label="Subscription Plans" {...a11yProps(3)} />
        </Tabs>

        <TabPanel value={tabValue} index={0}>
          {contacts.length > 0 ? (
            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Name</TableCell>
                    <TableCell>Title</TableCell>
                    <TableCell>Email</TableCell>
                    <TableCell>Phone</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Decision Maker</TableCell>
                    <TableCell>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {contacts.map((contact) => (
                    <TableRow key={contact.id} hover>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center' }}>
                          <Avatar sx={{ mr: 1, width: 32, height: 32 }}>
                            {contact.first_name?.charAt(0)}{contact.last_name?.charAt(0)}
                          </Avatar>
                          {contact.name}
                        </Box>
                      </TableCell>
                      <TableCell>{contact.title || '-'}</TableCell>
                      <TableCell>
                        {contact.email && (
                          <a href={`mailto:${contact.email}`}>{contact.email}</a>
                        )}
                      </TableCell>
                      <TableCell>{contact.phone || contact.mobile || '-'}</TableCell>
                      <TableCell>
                        <Chip
                          label={contact.status}
                          size="small"
                          color={getStatusColor(contact.status) as any}
                        />
                      </TableCell>
                      <TableCell>
                        {contact.is_decision_maker && (
                          <Chip label="Decision Maker" size="small" color="primary" />
                        )}
                      </TableCell>
                      <TableCell>
                        <Tooltip title="View Contact">
                          <IconButton
                            size="small"
                            onClick={() => navigate(`/contacts/${contact.id}`)}
                          >
                            <Person />
                          </IconButton>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          ) : (
            <Box sx={{ textAlign: 'center', py: 4 }}>
              <Person sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
              <Typography variant="h6" color="text.secondary" gutterBottom>
                No contacts yet
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Add contacts to start managing relationships with this company
              </Typography>
              <Button
                variant="contained"
                startIcon={<Add />}
                onClick={() => setContactFormOpen(true)}
              >
                Add First Contact
              </Button>
            </Box>
          )}
        </TabPanel>

        <TabPanel value={tabValue} index={1}>
          {opportunities.length > 0 ? (
            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Name</TableCell>
                    <TableCell>Stage</TableCell>
                    <TableCell>Value</TableCell>
                    <TableCell>Probability</TableCell>
                    <TableCell>Owner</TableCell>
                    <TableCell>Expected Close</TableCell>
                    <TableCell>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {opportunities.map((opportunity) => (
                    <TableRow key={opportunity.id} hover>
                      <TableCell>{opportunity.name}</TableCell>
                      <TableCell>
                        <Chip
                          label={opportunity.stage}
                          size="small"
                          color={getStatusColor(opportunity.stage) as any}
                        />
                      </TableCell>
                      <TableCell>
                        {opportunity.expected_value ? formatCurrency(opportunity.expected_value) : '-'}
                      </TableCell>
                      <TableCell>{opportunity.probability}%</TableCell>
                      <TableCell>{opportunity.owner_name}</TableCell>
                      <TableCell>
                        {opportunity.expected_close_date
                          ? new Date(opportunity.expected_close_date).toLocaleDateString()
                          : '-'}
                      </TableCell>
                      <TableCell>
                        <Tooltip title="View Opportunity">
                          <IconButton
                            size="small"
                            onClick={() => navigate(`/opportunities/${opportunity.id}`)}
                          >
                            <TrendingUp />
                          </IconButton>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          ) : (
            <Box sx={{ textAlign: 'center', py: 4 }}>
              <TrendingUp sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
              <Typography variant="h6" color="text.secondary" gutterBottom>
                No opportunities yet
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Create opportunities to track potential deals with this company
              </Typography>
              <Button
                variant="contained"
                startIcon={<Add />}
                onClick={() => setOpportunityFormOpen(true)}
              >
                Create First Opportunity
              </Button>
            </Box>
          )}
        </TabPanel>

        <TabPanel value={tabValue} index={2}>
          {contracts.length > 0 ? (
            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Contract Number</TableCell>
                    <TableCell>Type</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>Value</TableCell>
                    <TableCell>Start Date</TableCell>
                    <TableCell>End Date</TableCell>
                    <TableCell>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {contracts.map((contract) => (
                    <TableRow key={contract.id} hover>
                      <TableCell>{contract.contract_number}</TableCell>
                      <TableCell>{contract.contract_type}</TableCell>
                      <TableCell>
                        <Chip
                          label={contract.status}
                          size="small"
                          color={getStatusColor(contract.status) as any}
                        />
                      </TableCell>
                      <TableCell>{formatCurrency(contract.value)}</TableCell>
                      <TableCell>
                        {new Date(contract.start_date).toLocaleDateString()}
                      </TableCell>
                      <TableCell>
                        {new Date(contract.end_date).toLocaleDateString()}
                      </TableCell>
                      <TableCell>
                        <Tooltip title="View Contract">
                          <IconButton
                            size="small"
                            onClick={() => navigate(`/contracts/${contract.id}`)}
                          >
                            <Assignment />
                          </IconButton>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          ) : (
            <Box sx={{ textAlign: 'center', py: 4 }}>
              <Assignment sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
              <Typography variant="h6" color="text.secondary" gutterBottom>
                No contracts yet
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Contracts will appear here when opportunities are converted to deals
              </Typography>
            </Box>
          )}
        </TabPanel>

        <TabPanel value={tabValue} index={3}>
          {company.subscription_plans && company.subscription_plans.length > 0 ? (
            <Grid container spacing={2}>
              {company.subscription_plans.map((plan) => (
                <Grid item xs={12} md={6} key={plan.id}>
                  <Card variant="outlined">
                    <CardContent>
                      <Typography variant="h6" gutterBottom>
                        {plan.tier}
                      </Typography>
                      <Box sx={{ mb: 2 }}>
                        <Chip
                          label={plan.is_active ? 'Active' : 'Inactive'}
                          size="small"
                          color={plan.is_active ? 'success' : 'default'}
                        />
                      </Box>
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Zone Count: {plan.zone_count}
                      </Typography>
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Billing: {plan.billing_period}
                      </Typography>
                      <Typography variant="h6" color="primary">
                        {plan.display_price}
                      </Typography>
                      {plan.notes && (
                        <Typography variant="body2" sx={{ mt: 1 }}>
                          {plan.notes}
                        </Typography>
                      )}
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>
          ) : (
            <Box sx={{ textAlign: 'center', py: 4 }}>
              <AccountBalance sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
              <Typography variant="h6" color="text.secondary" gutterBottom>
                No subscription plans
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Subscription plans will be displayed here once configured
              </Typography>
            </Box>
          )}
        </TabPanel>
      </Paper>

      {/* Forms */}
      <CompanyForm
        open={editFormOpen}
        onClose={() => setEditFormOpen(false)}
        onSave={handleEditSave}
        company={company}
      />

      <ContactForm
        open={contactFormOpen}
        onClose={() => setContactFormOpen(false)}
        onSave={handleContactSave}
        contact={null}
        companies={[company]}
      />

      <OpportunityForm
        open={opportunityFormOpen}
        onClose={() => setOpportunityFormOpen(false)}
        onSave={handleOpportunitySave}
        opportunity={null}
        mode="create"
      />

      {/* Floating Action Button for Mobile */}
      <Box sx={{ display: { xs: 'block', sm: 'none' } }}>
        <Fab
          color="primary"
          aria-label="add"
          sx={{ position: 'fixed', bottom: 16, right: 16 }}
          onClick={() => setContactFormOpen(true)}
        >
          <Add />
        </Fab>
      </Box>
    </Box>
  );
};

export default CompanyDetail;