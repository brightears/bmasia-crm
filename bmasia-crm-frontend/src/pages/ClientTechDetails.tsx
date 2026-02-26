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
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Divider,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Snackbar,
  Autocomplete,
  Link,
} from '@mui/material';
import {
  Add,
  Search,
  Edit,
  Visibility,
  Delete,
  MoreVert,
  Computer,
  Business,
  LocationOn,
  OpenInNew,
  PictureAsPdf,
} from '@mui/icons-material';
import { Company, ClientTechDetail, ApiResponse } from '../types';
import ApiService from '../services/api';
import ClientTechDetailForm from '../components/ClientTechDetailForm';

const ClientTechDetails: React.FC = () => {
  // Data state
  const [details, setDetails] = useState<ClientTechDetail[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Pagination
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [totalCount, setTotalCount] = useState(0);

  // Filters
  const [search, setSearch] = useState('');
  const [selectedCompanyId, setSelectedCompanyId] = useState('');
  const [selectedCompanyObj, setSelectedCompanyObj] = useState<Company | null>(null);

  // Dialog state
  const [formOpen, setFormOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedDetail, setSelectedDetail] = useState<ClientTechDetail | null>(null);
  const [deletingId, setDeletingId] = useState('');
  const [deletingLabel, setDeletingLabel] = useState('');
  const [deleteLoading, setDeleteLoading] = useState(false);

  // Stats
  const [stats, setStats] = useState({ total_zones: 0, total_clients: 0 });

  // Action menu
  const [actionMenuAnchor, setActionMenuAnchor] = useState<null | HTMLElement>(null);
  const [actionMenuDetail, setActionMenuDetail] = useState<ClientTechDetail | null>(null);

  // ---- Data loading ----

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const params: any = {
        page: page + 1,
        page_size: rowsPerPage,
        ordering: '-created_at',
      };
      if (search) params.search = search;
      if (selectedCompanyId) params.company = selectedCompanyId;
      const [response, statsData] = await Promise.all([
        ApiService.getClientTechDetails(params),
        ApiService.getClientTechDetailStats(
          search || selectedCompanyId
            ? { ...(search && { search }), ...(selectedCompanyId && { company: selectedCompanyId }) }
            : undefined
        ),
      ]);
      setDetails(response.results || []);
      setTotalCount(response.count || 0);
      setStats(statsData);
    } catch (err: any) {
      setError('Failed to load tech details');
      console.error('ClientTechDetails error:', err);
    } finally {
      setLoading(false);
    }
  }, [page, rowsPerPage, search, selectedCompanyId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    const loadCompanies = async () => {
      try {
        const response = await ApiService.getCompanies({ page_size: 1000, ordering: 'name' });
        setCompanies(response.results || []);
      } catch (err) {
        console.error('Failed to load companies:', err);
      }
    };
    loadCompanies();
  }, []);

  // ---- Handlers ----

  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearch(event.target.value);
    setPage(0);
  };

  const handleCompanyChange = (_event: React.SyntheticEvent, value: Company | null) => {
    setSelectedCompanyObj(value);
    setSelectedCompanyId(value ? value.id : '');
    setPage(0);
  };

  const handleChangePage = (_event: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const handleCreate = () => {
    setSelectedDetail(null);
    setFormOpen(true);
  };

  const handleEdit = (detail: ClientTechDetail) => {
    setSelectedDetail(detail);
    setFormOpen(true);
    setActionMenuAnchor(null);
  };

  const handleView = (detail: ClientTechDetail) => {
    setSelectedDetail(detail);
    setDetailOpen(true);
    setActionMenuAnchor(null);
  };

  const handleDeletePrompt = (detail: ClientTechDetail) => {
    setDeletingId(detail.id);
    setDeletingLabel(detail.outlet_name || detail.company_name || 'this record');
    setDeleteDialogOpen(true);
    setActionMenuAnchor(null);
  };

  const handleDelete = async () => {
    if (!deletingId) return;
    try {
      setDeleteLoading(true);
      await ApiService.deleteClientTechDetail(deletingId);
      setSuccess('Tech detail deleted');
      setDeleteDialogOpen(false);
      setDeletingId('');
      loadData();
    } catch (err) {
      setError('Failed to delete tech detail');
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleDownloadPDF = async (detail: ClientTechDetail) => {
    try {
      const blob = await ApiService.downloadClientTechDetailPDF(detail.id);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      const safeCompany = (detail.company_name || 'Unknown').replace(/[^a-zA-Z0-9_\-]/g, '_').slice(0, 50);
      const safeOutlet = (detail.outlet_name || 'Unknown').replace(/[^a-zA-Z0-9_\-]/g, '_').slice(0, 50);
      link.download = `TechDetail_${safeCompany}_${safeOutlet}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      setActionMenuAnchor(null);
    } catch (err) {
      setError('Failed to download PDF');
    }
  };

  const handleFormSave = () => {
    setFormOpen(false);
    loadData();
  };

  const handleActionMenuOpen = (event: React.MouseEvent<HTMLElement>, detail: ClientTechDetail) => {
    event.stopPropagation();
    setActionMenuAnchor(event.currentTarget);
    setActionMenuDetail(detail);
  };

  const handleActionMenuClose = () => {
    setActionMenuAnchor(null);
    setActionMenuDetail(null);
  };

  // ---- Helpers ----

  const getSystemTypeChip = (systemType: string) => {
    if (systemType === 'single') {
      return (
        <Chip
          label="Single"
          size="small"
          sx={{ backgroundColor: '#2196f3', color: 'white', fontWeight: 600 }}
        />
      );
    }
    if (systemType === 'multi') {
      return (
        <Chip
          label="Multi"
          size="small"
          sx={{ backgroundColor: '#4caf50', color: 'white', fontWeight: 600 }}
        />
      );
    }
    return <Typography variant="body2" color="text.secondary">-</Typography>;
  };

  const getPlatformTypeChip = (platformType: string) => {
    if (platformType === 'soundtrack') {
      return (
        <Chip
          label="SYB"
          size="small"
          sx={{ backgroundColor: '#FF8C00', color: 'white', fontWeight: 600 }}
        />
      );
    }
    if (platformType === 'beatbreeze') {
      return (
        <Chip
          label="Beat Breeze"
          size="small"
          sx={{ backgroundColor: '#9c27b0', color: 'white', fontWeight: 600 }}
        />
      );
    }
    if (platformType === 'bms') {
      return (
        <Chip
          label="BMS"
          size="small"
          sx={{ backgroundColor: '#1565C0', color: 'white', fontWeight: 600 }}
        />
      );
    }
    if (platformType === 'dm') {
      return (
        <Chip
          label="DM"
          size="small"
          sx={{ backgroundColor: '#2e7d32', color: 'white', fontWeight: 600 }}
        />
      );
    }
    return <Typography variant="body2" color="text.secondary">-</Typography>;
  };

  const formatField = (value: string | null | undefined): string => {
    if (!value || value.trim() === '') return '-';
    return value;
  };

  // ---- Detail dialog sections ----

  const DetailSection: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
    <Box sx={{ mb: 3 }}>
      <Typography
        variant="subtitle1"
        fontWeight={600}
        sx={{
          mb: 1,
          pb: 0.5,
          borderBottom: '1px solid',
          borderColor: 'divider',
          color: 'primary.main',
        }}
      >
        {title}
      </Typography>
      {children}
    </Box>
  );

  const DetailRow: React.FC<{ label: string; value: React.ReactNode }> = ({ label, value }) => (
    <Box sx={{ display: 'flex', py: 0.5, gap: 1 }}>
      <Typography variant="body2" color="text.secondary" sx={{ minWidth: 180, flexShrink: 0 }}>
        {label}
      </Typography>
      <Typography variant="body2" sx={{ flex: 1, wordBreak: 'break-word' }}>
        {value}
      </Typography>
    </Box>
  );

  // ---- Render ----

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1">
          Client Tech Details
        </Typography>
        <Button
          variant="contained"
          startIcon={<Add />}
          onClick={handleCreate}
          sx={{ backgroundColor: '#FF8C00', '&:hover': { backgroundColor: '#e67e00' } }}
        >
          New
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* Filter bar */}
      <Paper sx={{ mb: 2 }}>
        <Box sx={{ p: 2, display: 'flex', gap: 2, alignItems: 'center' }}>
          <TextField
            fullWidth
            size="small"
            placeholder="Search by outlet, AnyDesk ID, company..."
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
          <Autocomplete
            size="small"
            sx={{ minWidth: 240 }}
            options={companies}
            getOptionLabel={(option) => option.name}
            value={selectedCompanyObj}
            onChange={handleCompanyChange}
            renderInput={(params) => (
              <TextField {...params} label="Company" placeholder="All companies" />
            )}
            isOptionEqualToValue={(option, value) => option.id === value.id}
          />
        </Box>
      </Paper>

      {/* Summary counts */}
      <Box sx={{ display: 'flex', gap: 1.5, mb: 2 }}>
        <Chip
          icon={<Business />}
          label={`${stats.total_clients} Clients`}
          variant="outlined"
          color="primary"
        />
        <Chip
          icon={<LocationOn />}
          label={`${stats.total_zones} Zones`}
          variant="outlined"
          color="primary"
        />
      </Box>

      {/* Table */}
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Client</TableCell>
              <TableCell>Outlet / Zone</TableCell>
              <TableCell>AnyDesk</TableCell>
              <TableCell>UltraViewer</TableCell>
              <TableCell>Platform</TableCell>
              <TableCell>System Type</TableCell>
              <TableCell sx={{ width: 80 }}>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={7} align="center">
                  <CircularProgress />
                </TableCell>
              </TableRow>
            ) : details.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} align="center">
                  <Box sx={{ py: 4 }}>
                    <Computer sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
                    <Typography variant="h6" color="text.secondary">
                      No tech details found
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {search || selectedCompanyId
                        ? 'Try adjusting your filters'
                        : 'Start by adding your first client tech detail'}
                    </Typography>
                  </Box>
                </TableCell>
              </TableRow>
            ) : (
              details.map((detail) => (
                <TableRow
                  key={detail.id}
                  hover
                  sx={{ cursor: 'pointer' }}
                  onClick={() => handleView(detail)}
                >
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                      <Business sx={{ mr: 1, color: 'text.secondary', fontSize: 16 }} />
                      <Typography variant="body2" fontWeight="medium">
                        {detail.company_name || '-'}
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                      <LocationOn sx={{ mr: 0.5, color: 'text.secondary', fontSize: 16 }} />
                      <Typography variant="body2">
                        {formatField(detail.outlet_name)}
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" fontFamily="monospace">
                      {formatField(detail.anydesk_id)}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" fontFamily="monospace">
                      {formatField(detail.ultraviewer_id)}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    {getPlatformTypeChip(detail.platform_type)}
                  </TableCell>
                  <TableCell>
                    {getSystemTypeChip(detail.system_type)}
                  </TableCell>
                  <TableCell>
                    <IconButton
                      size="small"
                      onClick={(e) => handleActionMenuOpen(e, detail)}
                    >
                      <MoreVert />
                    </IconButton>
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

      {/* Action menu */}
      <Menu
        anchorEl={actionMenuAnchor}
        open={Boolean(actionMenuAnchor)}
        onClose={handleActionMenuClose}
      >
        <MenuItem onClick={() => handleView(actionMenuDetail!)}>
          <ListItemIcon>
            <Visibility fontSize="small" />
          </ListItemIcon>
          <ListItemText>View Details</ListItemText>
        </MenuItem>
        <MenuItem onClick={() => handleDownloadPDF(actionMenuDetail!)}>
          <ListItemIcon>
            <PictureAsPdf fontSize="small" />
          </ListItemIcon>
          <ListItemText>Download PDF</ListItemText>
        </MenuItem>
        <MenuItem onClick={() => handleEdit(actionMenuDetail!)}>
          <ListItemIcon>
            <Edit fontSize="small" />
          </ListItemIcon>
          <ListItemText>Edit</ListItemText>
        </MenuItem>
        <Divider />
        <MenuItem
          onClick={() => handleDeletePrompt(actionMenuDetail!)}
          sx={{ color: 'error.main' }}
        >
          <ListItemIcon>
            <Delete fontSize="small" sx={{ color: 'error.main' }} />
          </ListItemIcon>
          <ListItemText>Delete</ListItemText>
        </MenuItem>
      </Menu>

      {/* Detail dialog */}
      {selectedDetail && (
        <Dialog
          open={detailOpen}
          onClose={() => setDetailOpen(false)}
          maxWidth="md"
          fullWidth
        >
          <DialogTitle>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Computer />
              <Box>
                <Typography variant="h6">
                  {selectedDetail.outlet_name || 'Tech Detail'}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {selectedDetail.company_name}
                </Typography>
              </Box>
            </Box>
          </DialogTitle>
          <DialogContent dividers>
            {/* Section 1: Client & Location */}
            <DetailSection title="Client & Location">
              <DetailRow label="Company" value={formatField(selectedDetail.company_name)} />
              <DetailRow label="Outlet / Zone Name" value={formatField(selectedDetail.outlet_name)} />
              {selectedDetail.zone_name && (
                <DetailRow label="Zone" value={selectedDetail.zone_name} />
              )}
              <DetailRow label="Platform Type" value={getPlatformTypeChip(selectedDetail.platform_type)} />
            </DetailSection>

            {/* Section 2: Remote Access */}
            <DetailSection title="Remote Access">
              <DetailRow label="AnyDesk ID" value={
                <Typography variant="body2" fontFamily="monospace">
                  {formatField(selectedDetail.anydesk_id)}
                </Typography>
              } />
              <DetailRow label="TeamViewer ID" value={
                <Typography variant="body2" fontFamily="monospace">
                  {formatField(selectedDetail.teamviewer_id)}
                </Typography>
              } />
              <DetailRow label="UltraViewer ID" value={
                <Typography variant="body2" fontFamily="monospace">
                  {formatField(selectedDetail.ultraviewer_id)}
                </Typography>
              } />
              <DetailRow label="Other Remote ID" value={
                <Typography variant="body2" fontFamily="monospace">
                  {formatField(selectedDetail.other_remote_id)}
                </Typography>
              } />
            </DetailSection>

            {/* Section 3: System Config */}
            <DetailSection title="System Configuration">
              <DetailRow label="System Type" value={getSystemTypeChip(selectedDetail.system_type)} />
              <DetailRow label="Soundcard Channel" value={formatField(selectedDetail.soundcard_channel)} />
              <DetailRow label="BMS License" value={formatField(selectedDetail.bms_license)} />
              <DetailRow label="Additional Hardware" value={formatField(selectedDetail.additional_hardware)} />
            </DetailSection>

            {/* Section 3b: Dates & Licensing */}
            <DetailSection title="Dates and Licensing">
              <DetailRow label="Install Date" value={selectedDetail.install_date
                ? new Date(selectedDetail.install_date + 'T00:00:00').toLocaleDateString('en-GB')
                : '-'} />
              <DetailRow label="Commencement Date" value={selectedDetail.commencement_date
                ? new Date(selectedDetail.commencement_date + 'T00:00:00').toLocaleDateString('en-GB')
                : '-'} />
              <DetailRow label="Activation Date (SYB)" value={selectedDetail.activation_date
                ? new Date(selectedDetail.activation_date + 'T00:00:00').toLocaleDateString('en-GB')
                : '-'} />
              <DetailRow label="LIM Source" value={formatField(selectedDetail.lim_source)} />
              <DetailRow label="Expiry Date" value={selectedDetail.expiry_date
                ? new Date(selectedDetail.expiry_date + 'T00:00:00').toLocaleDateString('en-GB')
                : '-'} />
            </DetailSection>

            {/* Section 4: PC Specs */}
            <DetailSection title="PC Specifications">
              <DetailRow label="PC Name" value={formatField(selectedDetail.pc_name)} />
              <DetailRow label="Operating System" value={formatField(selectedDetail.operating_system)} />
              <DetailRow label="OS Type" value={formatField(selectedDetail.os_type)} />
              <DetailRow label="Make / Brand" value={formatField(selectedDetail.pc_make)} />
              <DetailRow label="Model" value={formatField(selectedDetail.pc_model)} />
              <DetailRow label="PC Type" value={formatField(selectedDetail.pc_type)} />
              <DetailRow label="RAM" value={formatField(selectedDetail.ram)} />
              <DetailRow label="CPU Type" value={formatField(selectedDetail.cpu_type)} />
              <DetailRow label="CPU Speed" value={formatField(selectedDetail.cpu_speed)} />
              <DetailRow label="CPU Cores" value={formatField(selectedDetail.cpu_cores)} />
              <DetailRow label="HDD C:" value={formatField(selectedDetail.hdd_c)} />
              <DetailRow label="HDD D:" value={formatField(selectedDetail.hdd_d)} />
              <DetailRow label="Network Type" value={formatField(selectedDetail.network_type)} />
            </DetailSection>

            {/* Section 5: Audio Equipment */}
            <DetailSection title="Audio Equipment">
              <DetailRow label="Amplifiers" value={formatField(selectedDetail.amplifiers)} />
              <DetailRow label="Distribution" value={formatField(selectedDetail.distribution)} />
              <DetailRow label="Speakers" value={formatField(selectedDetail.speakers)} />
              <DetailRow label="Other Equipment" value={formatField(selectedDetail.other_equipment)} />
            </DetailSection>

            {/* Section 6: Links & Notes */}
            <DetailSection title="Links & Notes">
              <DetailRow
                label="Music Spec Link"
                value={
                  selectedDetail.music_spec_link ? (
                    <Link
                      href={selectedDetail.music_spec_link}
                      target="_blank"
                      rel="noopener noreferrer"
                      sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}
                    >
                      Open link
                      <OpenInNew sx={{ fontSize: 14 }} />
                    </Link>
                  ) : (
                    '-'
                  )
                }
              />
              <DetailRow
                label="SYB Schedules Link"
                value={
                  selectedDetail.syb_schedules_link ? (
                    <Link
                      href={selectedDetail.syb_schedules_link}
                      target="_blank"
                      rel="noopener noreferrer"
                      sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}
                    >
                      Open link
                      <OpenInNew sx={{ fontSize: 14 }} />
                    </Link>
                  ) : (
                    '-'
                  )
                }
              />
              <DetailRow label="Comments" value={formatField(selectedDetail.comments)} />
            </DetailSection>
          </DialogContent>
          <DialogActions>
            <Button
              startIcon={<PictureAsPdf />}
              onClick={() => handleDownloadPDF(selectedDetail)}
              sx={{ color: '#FFA500' }}
            >
              Download PDF
            </Button>
            <Button
              startIcon={<Edit />}
              onClick={() => {
                setDetailOpen(false);
                handleEdit(selectedDetail);
              }}
            >
              Edit
            </Button>
            <Button
              startIcon={<Delete />}
              color="error"
              onClick={() => {
                setDetailOpen(false);
                handleDeletePrompt(selectedDetail);
              }}
            >
              Delete
            </Button>
            <Button variant="contained" onClick={() => setDetailOpen(false)}>
              Close
            </Button>
          </DialogActions>
        </Dialog>
      )}

      {/* Form dialog */}
      <ClientTechDetailForm
        open={formOpen}
        onClose={() => setFormOpen(false)}
        onSave={handleFormSave}
        detail={selectedDetail}
        companies={companies}
      />

      {/* Delete confirmation dialog */}
      <Dialog
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>Delete Tech Detail</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete the tech detail for{' '}
            <strong>{deletingLabel}</strong>? This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)} disabled={deleteLoading}>
            Cancel
          </Button>
          <Button
            onClick={handleDelete}
            color="error"
            variant="contained"
            disabled={deleteLoading}
            startIcon={deleteLoading ? <CircularProgress size={16} /> : <Delete />}
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>

      {/* Success snackbar */}
      <Snackbar
        open={!!success}
        autoHideDuration={6000}
        onClose={() => setSuccess('')}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={() => setSuccess('')} severity="success">
          {success}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default ClientTechDetails;
