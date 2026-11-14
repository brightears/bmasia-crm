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
  Divider,
  GridLegacy as Grid,
  Tabs,
  Tab,
  Avatar,
  Tooltip,
  Fab,
} from '@mui/material';
import {
  Edit,
  LocationOn,
  Person,
  TrendingUp,
  Assignment,
  AccountBalance,
  Add,
  ContactPhone,
  Handshake,
  PlaylistAdd,
  Public,
  Category,
  SupportAgent,
  ChevronRight,
} from '@mui/icons-material';
import { useParams, useNavigate } from 'react-router-dom';
import { Company, Contact, Opportunity, Contract, Zone, Ticket } from '../types';
import ApiService from '../services/api';
import CompanyForm from '../components/CompanyForm';
import ContactForm from '../components/ContactForm';
import OpportunityForm from '../components/OpportunityForm';
import { PageHeader, SectionCard, EmptyState, DetailField, ProductChip } from '../components/ui';
import { statusTone, humanize, formatDate, formatMoney, initialsOf, totalsByCurrency, visuallyHidden } from '../theme';
import { currencyForEntity } from '../constants/entities';

const tabLabel = (label: string, count: number) => (
  <Box component="span" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.75 }}>
    {label}
    <Box
      component="span"
      sx={{
        minWidth: 20,
        height: 20,
        px: 0.75,
        borderRadius: '10px',
        fontSize: '0.75rem',
        fontWeight: 600,
        lineHeight: '20px',
        textAlign: 'center',
        bgcolor: 'action.hover',
        color: 'text.secondary',
      }}
    >
      {count}
    </Box>
  </Box>
);

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
      {value === index && <Box>{children}</Box>}
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
  const [zones, setZones] = useState<Zone[]>([]);
  const [tickets, setTickets] = useState<Ticket[]>([]);
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
      const [contactsResponse, opportunitiesResponse, contractsResponse, zonesResponse, ticketsResponse] = await Promise.all([
        ApiService.getContacts({ company: id }),
        ApiService.getOpportunities({ company: id }),
        // All of this company's contracts (not just the first page), so the per-currency totals are complete.
        ApiService.getContracts({ company: id, page_size: 1000 }),
        ApiService.getZonesByCompany(id),
        ApiService.getTickets({ company: id, page_size: 100 }),
      ]);

      setContacts(contactsResponse.results);
      setOpportunities(opportunitiesResponse.results);
      setContracts(contractsResponse.results);
      setZones(zonesResponse);
      setTickets(ticketsResponse.results || []);
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

  const activeZones = zones.filter(z => z.status !== 'expired' && z.status !== 'offline');
  const inactiveZones = zones.filter(z => z.status === 'expired' || z.status === 'offline');
  const openTickets = tickets.filter(t => !['resolved', 'closed'].includes(t.status));
  const location = [company.city, company.country].filter(Boolean).join(', ');

  // Never add different currencies together: one total per currency, over active contracts
  // (the same contracts the server's total_contract_value counts).
  const activeTotals = totalsByCurrency(
    contracts.filter((c) => c.is_active).map((c) => ({ amount: c.value, currency: c.currency }))
  );
  const opportunityCurrency = currencyForEntity(company.billing_entity);

  const facts = [
    { label: 'Contacts', value: contacts.length, tab: 0 },
    { label: 'Opportunities', value: opportunities.length, tab: 1 },
    { label: 'Contracts', value: contracts.length, tab: 2 },
    { label: 'Music zones', value: zones.length, tab: 3 },
    { label: 'Open tickets', value: openTickets.length, tab: 4 },
    {
      label: 'Active contract value',
      value:
        activeTotals.length === 0 ? (
          '—'
        ) : (
          <>
            {activeTotals.map(([cur, total]) => (
              <Box component="span" key={cur} sx={{ display: 'block' }}>
                {formatMoney(total, cur)}
              </Box>
            ))}
          </>
        ),
    },
  ];

  const zoneCard = (zone: Zone, inactive: boolean) => (
    <Grid item xs={12} sm={6} lg={4} key={zone.id}>
      <Card
        variant="outlined"
        sx={{
          cursor: 'pointer',
          height: '100%',
          bgcolor: inactive ? 'background.default' : 'background.paper',
          transition: 'border-color 120ms',
          '&:hover': { borderColor: 'text.secondary' },
        }}
        onClick={() => navigate(`/zones/${zone.id}`)}
      >
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 1, mb: 1 }}>
            <Typography sx={{ fontWeight: 600, color: inactive ? 'text.secondary' : 'text.primary' }}>
              {zone.name}
            </Typography>
            <Chip label={humanize(zone.status)} size="small" color={statusTone(zone.status)} />
          </Box>
          <ProductChip value={zone.platform} />
          {zone.device_name && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              Device: {zone.device_name}
            </Typography>
          )}
          {!inactive && zone.current_contract && (
            <Box sx={{ mt: 1.5, pt: 1.5, borderTop: 1, borderColor: 'divider' }}>
              <Typography variant="caption" color="text.secondary" display="block">
                Contract
              </Typography>
              <Typography
                variant="body2"
                sx={{ color: 'primary.main', fontWeight: 600, '&:hover': { textDecoration: 'underline' } }}
                onClick={(e) => {
                  e.stopPropagation();
                  navigate(`/contracts/${zone.current_contract?.id}`);
                }}
              >
                {zone.current_contract?.contract_number}
              </Typography>
            </Box>
          )}
          {inactive && zone.contract_count !== undefined && zone.contract_count > 0 && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              {zone.contract_count} contract{zone.contract_count > 1 ? 's' : ''} (historical)
            </Typography>
          )}
        </CardContent>
      </Card>
    </Grid>
  );

  return (
    <Box sx={{ flexGrow: 1 }}>
      {/* Record header */}
      <PageHeader
        breadcrumbs={[{ label: 'Companies', to: '/companies' }, { label: company.name }]}
        avatar={
          <Avatar variant="rounded" sx={{ width: 52, height: 52, fontSize: '1.125rem', borderRadius: 2 }}>
            {initialsOf(company.name)}
          </Avatar>
        }
        title={company.name}
        meta={
          <>
            <Chip
              label={company.is_active ? 'Active' : 'Inactive'}
              color={company.is_active ? 'success' : 'default'}
              size="small"
            />
            <ProductChip value={company.contracted_product} />
            {company.industry && (
              <Chip label={company.industry} variant="outlined" size="small" icon={<Category />} />
            )}
            {location && (
              <Chip label={location} variant="outlined" size="small" icon={<Public />} />
            )}
          </>
        }
        actions={
          <>
            <Button variant="outlined" startIcon={<ContactPhone />} onClick={() => setContactFormOpen(true)}>
              Add Contact
            </Button>
            <Button variant="outlined" startIcon={<Handshake />} onClick={() => setOpportunityFormOpen(true)}>
              Create Opportunity
            </Button>
            <Tooltip title="Create Ticket">
              <IconButton
                aria-label="Create Ticket"
                onClick={() => navigate(`/tickets/new?company=${company.id}`)}
                sx={{ border: 1, borderColor: 'divider' }}
              >
                <SupportAgent fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title="Create Task">
              <IconButton
                aria-label="Create Task"
                onClick={() => navigate(`/tasks/new?company=${company.id}`)}
                sx={{ border: 1, borderColor: 'divider' }}
              >
                <PlaylistAdd fontSize="small" />
              </IconButton>
            </Tooltip>
            <Button variant="contained" startIcon={<Edit />} onClick={() => setEditFormOpen(true)}>
              Edit Company
            </Button>
          </>
        }
      />

      {/* Key facts: one strip instead of four separate cards */}
      <Paper sx={{ mb: 3, display: 'grid', gridTemplateColumns: { xs: 'repeat(2, 1fr)', sm: 'repeat(3, 1fr)', lg: 'repeat(6, 1fr)' } }}>
        {facts.map((fact, i) => (
          <Box
            key={fact.label}
            component={fact.tab !== undefined ? 'button' : 'div'}
            onClick={fact.tab !== undefined ? () => setTabValue(fact.tab as number) : undefined}
            sx={{
              all: 'unset',
              boxSizing: 'border-box',
              px: 2.5,
              py: 2,
              cursor: fact.tab !== undefined ? 'pointer' : 'default',
              borderLeft: { lg: i === 0 ? 0 : 1 },
              borderTop: { xs: i < 2 ? 0 : 1, sm: i < 3 ? 0 : 1, lg: 0 },
              borderColor: { xs: 'divider', lg: 'divider' },
              '&:hover': fact.tab !== undefined ? { bgcolor: 'action.hover' } : undefined,
              '&:focus-visible': { outline: '2px solid', outlineColor: 'primary.main', outlineOffset: -2 },
            }}
          >
            <Typography variant="caption" color="text.secondary" component="div">
              {fact.label}
            </Typography>
            <Typography sx={{ fontSize: '1.25rem', fontWeight: 600, fontVariantNumeric: 'tabular-nums', mt: 0.25 }}>
              {fact.value}
            </Typography>
          </Box>
        ))}
      </Paper>

      <Grid container spacing={3}>
        {/* Left: about this company */}
        <Grid item xs={12} md={4}>
          <SectionCard title="About">
            <Box sx={{ display: 'grid', gap: 2 }}>
              <DetailField label="Website">
                {company.website && (
                  <a href={company.website} target="_blank" rel="noopener noreferrer">
                    {company.website.replace(/^https?:\/\//, '')}
                  </a>
                )}
              </DetailField>
              <DetailField label="Phone">{company.phone}</DetailField>
              <DetailField label="Email">
                {company.email && <a href={`mailto:${company.email}`}>{company.email}</a>}
              </DetailField>
              <DetailField label="Location">{location}</DetailField>
              {company.full_address && company.full_address !== location && (
                <DetailField label="Full address">{company.full_address}</DetailField>
              )}
              <DetailField label="Billing entity">{company.billing_entity}</DetailField>
              {company.contracted_zone_count != null ? (
                <DetailField label="Music zones (contracted, from the renewal funnel)">
                  {company.contracted_zone_count}
                </DetailField>
              ) : (
                <DetailField label="Music zones (counted in the CRM, no contracted number yet)">
                  {company.music_zone_count}
                </DetailField>
              )}
              {company.notes && (
                <>
                  <Divider />
                  <DetailField label="Notes">
                    <Box component="span" sx={{ whiteSpace: 'pre-line' }}>{company.notes}</Box>
                  </DetailField>
                </>
              )}
            </Box>
          </SectionCard>
        </Grid>

        {/* Right: related records */}
        <Grid item xs={12} md={8}>
          <Paper sx={{ overflow: 'hidden' }}>
            <Tabs
              value={tabValue}
              onChange={handleTabChange}
              aria-label="company tabs"
              variant="scrollable"
              scrollButtons="auto"
              sx={{ px: 1 }}
            >
              <Tab label={tabLabel('Contacts', contacts.length)} {...a11yProps(0)} />
              <Tab label={tabLabel('Opportunities', opportunities.length)} {...a11yProps(1)} />
              <Tab label={tabLabel('Contracts', contracts.length)} {...a11yProps(2)} />
              <Tab label={tabLabel('Zones', zones.length)} {...a11yProps(3)} />
              <Tab label={tabLabel('Support', openTickets.length)} {...a11yProps(4)} />
              <Tab label="Plans" {...a11yProps(5)} />
            </Tabs>

            <TabPanel value={tabValue} index={0}>
              {contacts.length > 0 ? (
                <TableContainer>
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableCell>Name</TableCell>
                        <TableCell sx={{ display: { xs: 'none', sm: 'table-cell' } }}>Email</TableCell>
                        <TableCell sx={{ display: { xs: 'none', xl: 'table-cell' } }}>Phone</TableCell>
                        <TableCell>Role</TableCell>
                        <TableCell align="right"><Box component="span" sx={visuallyHidden}>Actions</Box></TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {contacts.map((contact) => {
                        // Get initials from name
                        const nameParts = contact.name.split(' ');
                        const initials = nameParts.length >= 2
                          ? `${nameParts[0][0]}${nameParts[nameParts.length - 1][0]}`
                          : contact.name.substring(0, 2);
                        const isDecisionMaker = contact.contact_type === 'Decision Maker';

                        return (
                          <TableRow key={contact.id} hover>
                            <TableCell>
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                                <Avatar sx={{ width: 32, height: 32 }}>
                                  {initials.toUpperCase()}
                                </Avatar>
                                <Box sx={{ minWidth: 0 }}>
                                  <Typography sx={{ fontWeight: 600, fontSize: '0.875rem', whiteSpace: 'nowrap' }}>
                                    {contact.name}
                                    {!contact.is_active && (
                                      <Chip label="Inactive" size="small" sx={{ ml: 1 }} />
                                    )}
                                  </Typography>
                                  <Typography variant="body2" color="text.secondary">
                                    {contact.title || '—'}
                                  </Typography>
                                </Box>
                              </Box>
                            </TableCell>
                            <TableCell sx={{ display: { xs: 'none', sm: 'table-cell' } }}>
                              {contact.email && (
                                <a href={`mailto:${contact.email}`}>{contact.email}</a>
                              )}
                            </TableCell>
                            <TableCell sx={{ display: { xs: 'none', xl: 'table-cell' }, whiteSpace: 'nowrap' }}>
                              {contact.phone || '—'}
                            </TableCell>
                            <TableCell>
                              {isDecisionMaker ? (
                                <Chip label="Decision Maker" size="small" color="primary" />
                              ) : (
                                <Typography variant="body2" color="text.secondary">{contact.contact_type || '—'}</Typography>
                              )}
                            </TableCell>
                            <TableCell align="right">
                              <Tooltip title="View Contact">
                                <IconButton
                                  size="small"
                                  aria-label={`View ${contact.name}`}
                                  onClick={() => navigate(`/contacts/${contact.id}`)}
                                >
                                  <ChevronRight fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </TableContainer>
              ) : (
                <EmptyState
                  icon={<Person />}
                  title="No contacts yet"
                  description="Add contacts to start managing relationships with this company."
                  action={
                    <Button variant="contained" startIcon={<Add />} onClick={() => setContactFormOpen(true)}>
                      Add First Contact
                    </Button>
                  }
                />
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
                        <TableCell align="right">Value</TableCell>
                        <TableCell sx={{ display: { xs: 'none', sm: 'table-cell' } }} align="right">Probability</TableCell>
                        <TableCell sx={{ display: { xs: 'none', lg: 'table-cell' } }}>Owner</TableCell>
                        <TableCell sx={{ display: { xs: 'none', sm: 'table-cell' } }}>Expected close</TableCell>
                        <TableCell align="right"><Box component="span" sx={visuallyHidden}>Actions</Box></TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {opportunities.map((opportunity) => (
                        <TableRow
                          key={opportunity.id}
                          hover
                          sx={{ cursor: 'pointer' }}
                          onClick={() => navigate(`/opportunities/${opportunity.id}`)}
                        >
                          <TableCell sx={{ fontWeight: 600 }}>{opportunity.name}</TableCell>
                          <TableCell>
                            <Chip label={opportunity.stage} size="small" color={statusTone(opportunity.stage)} />
                          </TableCell>
                          <TableCell align="right" sx={{ fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>
                            {opportunity.expected_value ? formatMoney(opportunity.expected_value, opportunityCurrency) : '—'}
                          </TableCell>
                          <TableCell sx={{ display: { xs: 'none', sm: 'table-cell' } }} align="right">{opportunity.probability}%</TableCell>
                          <TableCell sx={{ display: { xs: 'none', lg: 'table-cell' } }}>{opportunity.owner_name}</TableCell>
                          <TableCell sx={{ display: { xs: 'none', sm: 'table-cell' }, whiteSpace: 'nowrap' }}>
                            {formatDate(opportunity.expected_close_date)}
                          </TableCell>
                          <TableCell align="right" sx={{ width: 48 }}>
                            <Tooltip title="View Opportunity">
                              <IconButton
                                size="small"
                                aria-label={`View ${opportunity.name}`}
                                onClick={(e) => { e.stopPropagation(); navigate(`/opportunities/${opportunity.id}`); }}
                              >
                                <ChevronRight fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              ) : (
                <EmptyState
                  icon={<TrendingUp />}
                  title="No opportunities yet"
                  description="Create an opportunity to track a potential deal with this company."
                  action={
                    <Button variant="contained" startIcon={<Add />} onClick={() => setOpportunityFormOpen(true)}>
                      Create First Opportunity
                    </Button>
                  }
                />
              )}
            </TabPanel>

            <TabPanel value={tabValue} index={2}>
              {contracts.length > 0 ? (
                <TableContainer>
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableCell>Contract</TableCell>
                        <TableCell>Status</TableCell>
                        <TableCell align="right">Value</TableCell>
                        <TableCell sx={{ display: { xs: 'none', sm: 'table-cell' } }}>Term</TableCell>
                        <TableCell align="right"><Box component="span" sx={visuallyHidden}>Actions</Box></TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {contracts.map((contract) => (
                        <TableRow
                          key={contract.id}
                          hover
                          sx={{ cursor: 'pointer' }}
                          onClick={() => navigate(`/contracts/${contract.id}`)}
                        >
                          <TableCell>
                            <Typography sx={{ fontWeight: 600, fontSize: '0.875rem', whiteSpace: 'nowrap' }}>
                              {contract.contract_number}
                            </Typography>
                            <Typography variant="body2" color="text.secondary">{contract.contract_type}</Typography>
                          </TableCell>
                          <TableCell>
                            <Chip label={contract.status} size="small" color={statusTone(contract.status)} />
                          </TableCell>
                          <TableCell align="right" sx={{ fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>
                            {formatMoney(contract.value, contract.currency || 'USD')}
                          </TableCell>
                          <TableCell sx={{ display: { xs: 'none', sm: 'table-cell' }, whiteSpace: 'nowrap' }}>
                            {formatDate(contract.start_date)} – {formatDate(contract.end_date)}
                          </TableCell>
                          <TableCell align="right" sx={{ width: 48 }}>
                            <Tooltip title="View Contract">
                              <IconButton
                                size="small"
                                aria-label={`View ${contract.contract_number}`}
                                onClick={(e) => { e.stopPropagation(); navigate(`/contracts/${contract.id}`); }}
                              >
                                <ChevronRight fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              ) : (
                <EmptyState
                  icon={<Assignment />}
                  title="No contracts yet"
                  description="Contracts appear here when an opportunity is converted into a deal."
                />
              )}
            </TabPanel>

            <TabPanel value={tabValue} index={3}>
              {zones.length > 0 ? (
                <Box sx={{ p: 2.5 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                    <Typography variant="subtitle2" color="text.secondary">
                      {activeZones.length} active · {inactiveZones.length} inactive
                    </Typography>
                    <Button
                      variant="outlined"
                      size="small"
                      startIcon={<Add />}
                      onClick={() => navigate(`/zones/new?company=${id}&return_to=${encodeURIComponent(`/companies/${id}`)}`)}
                    >
                      Add Zone
                    </Button>
                  </Box>

                  {activeZones.length > 0 && (
                    <Box sx={{ mb: 3 }}>
                      <Typography variant="overline" color="text.secondary" component="h3" sx={{ mb: 1 }}>
                        Active zones ({activeZones.length})
                      </Typography>
                      <Grid container spacing={2}>
                        {activeZones.map((zone) => zoneCard(zone, false))}
                      </Grid>
                    </Box>
                  )}

                  {inactiveZones.length > 0 && (
                    <Box>
                      <Typography variant="overline" color="text.secondary" component="h3" sx={{ mb: 1 }}>
                        Inactive zones ({inactiveZones.length})
                      </Typography>
                      <Grid container spacing={2}>
                        {inactiveZones.map((zone) => zoneCard(zone, true))}
                      </Grid>
                    </Box>
                  )}
                </Box>
              ) : (
                <EmptyState
                  icon={<LocationOn />}
                  title="No zones yet"
                  description="Add music zones to track locations and their contracts."
                  action={
                    <Button
                      variant="contained"
                      startIcon={<Add />}
                      onClick={() => navigate(`/zones/new?company=${id}&return_to=${encodeURIComponent(`/companies/${id}`)}`)}
                    >
                      Add First Zone
                    </Button>
                  }
                />
              )}
            </TabPanel>

            <TabPanel value={tabValue} index={4}>
              {tickets.length > 0 ? (
                <>
                  <Box sx={{ display: 'flex', justifyContent: 'flex-end', px: 2.5, pt: 2 }}>
                    <Button
                      variant="outlined"
                      size="small"
                      startIcon={<Add />}
                      onClick={() => navigate(`/tickets/new?company=${company.id}`)}
                    >
                      New Ticket
                    </Button>
                  </Box>
                  <TableContainer>
                    <Table>
                      <TableHead>
                        <TableRow>
                          <TableCell>Ticket</TableCell>
                          <TableCell>Status</TableCell>
                          <TableCell sx={{ display: { xs: 'none', sm: 'table-cell' } }}>Priority</TableCell>
                          <TableCell sx={{ display: { xs: 'none', lg: 'table-cell' } }}>Assigned to</TableCell>
                          <TableCell sx={{ display: { xs: 'none', sm: 'table-cell' } }}>Created</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {tickets.map((ticket) => (
                          <TableRow
                            key={ticket.id}
                            hover
                            sx={{ cursor: 'pointer' }}
                            onClick={() => navigate(`/tickets/${ticket.id}`)}
                          >
                            <TableCell>
                              <Typography sx={{ fontWeight: 600, fontSize: '0.875rem' }}>{ticket.subject}</Typography>
                              <Typography variant="body2" color="text.secondary">{ticket.ticket_number}</Typography>
                            </TableCell>
                            <TableCell>
                              <Chip label={humanize(ticket.status)} size="small" color={statusTone(ticket.status)} />
                            </TableCell>
                            <TableCell sx={{ display: { xs: 'none', sm: 'table-cell' } }}>
                              <Chip label={humanize(ticket.priority)} size="small" color={statusTone(ticket.priority)} variant="outlined" />
                            </TableCell>
                            <TableCell sx={{ display: { xs: 'none', lg: 'table-cell' } }}>{ticket.assigned_to_name || 'Unassigned'}</TableCell>
                            <TableCell sx={{ display: { xs: 'none', sm: 'table-cell' }, whiteSpace: 'nowrap' }}>
                              {formatDate(ticket.created_at)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </>
              ) : (
                <EmptyState
                  icon={<SupportAgent />}
                  title="No support tickets"
                  description="Create a ticket when this company needs help."
                  action={
                    <Button
                      variant="contained"
                      startIcon={<Add />}
                      onClick={() => navigate(`/tickets/new?company=${company.id}`)}
                    >
                      Create First Ticket
                    </Button>
                  }
                />
              )}
            </TabPanel>

            <TabPanel value={tabValue} index={5}>
              {company.subscription_plans && company.subscription_plans.length > 0 ? (
                <Grid container spacing={2} sx={{ p: 2.5 }}>
                  {company.subscription_plans.map((plan) => (
                    <Grid item xs={12} md={6} key={plan.id}>
                      <Card variant="outlined">
                        <CardContent>
                          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                            <Typography sx={{ fontWeight: 600 }}>{plan.tier}</Typography>
                            <Chip
                              label={plan.is_active ? 'Active' : 'Inactive'}
                              size="small"
                              color={plan.is_active ? 'success' : 'default'}
                            />
                          </Box>
                          <Typography variant="body2" color="text.secondary">
                            {plan.zone_count} zones · billed {plan.billing_period}
                          </Typography>
                          <Typography sx={{ fontWeight: 600, fontSize: '1.125rem', mt: 1 }}>
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
                <EmptyState
                  icon={<AccountBalance />}
                  title="No subscription plans"
                  description="Subscription plans are shown here once they are set up."
                />
              )}
            </TabPanel>
          </Paper>
        </Grid>
      </Grid>

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
          sx={{ position: 'fixed', bottom: 80, right: 16 }}
          onClick={() => setContactFormOpen(true)}
        >
          <Add />
        </Fab>
      </Box>
    </Box>
  );
};

export default CompanyDetail;