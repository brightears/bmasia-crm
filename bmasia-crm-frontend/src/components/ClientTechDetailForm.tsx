import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Box,
  Typography,
  Paper,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Autocomplete,
  Alert,
  CircularProgress,
  Snackbar,
  GridLegacy as Grid,
} from '@mui/material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { Company, Zone, ClientTechDetail } from '../types';
import ApiService from '../services/api';

interface ClientTechDetailFormProps {
  open: boolean;
  onClose: () => void;
  onSave: () => void;
  detail: ClientTechDetail | null; // null = create, object = edit
  companies: Company[];
  initialCompanyId?: string;
}

interface FormState {
  company: string;
  zone: string;
  outlet_name: string;
  platform_type: 'soundtrack' | 'beatbreeze' | 'bms' | 'dm' | '';
  anydesk_id: string;
  teamviewer_id: string;
  ultraviewer_id: string;
  other_remote_id: string;
  system_type: 'single' | 'multi' | '';
  soundcard_channel: string;
  bms_license: string;
  additional_hardware: string;
  lim_source: string;
  pc_name: string;
  pc_make: string;
  pc_model: string;
  pc_type: string;
  operating_system: string;
  os_type: string;
  ram: string;
  cpu_type: string;
  cpu_speed: string;
  cpu_cores: string;
  hdd_c: string;
  hdd_d: string;
  network_type: string;
  amplifiers: string;
  distribution: string;
  speakers: string;
  other_equipment: string;
  music_spec_link: string;
  syb_schedules_link: string;
  comments: string;
}

const emptyForm: FormState = {
  company: '',
  zone: '',
  outlet_name: '',
  platform_type: '',
  anydesk_id: '',
  teamviewer_id: '',
  ultraviewer_id: '',
  other_remote_id: '',
  system_type: '',
  soundcard_channel: '',
  bms_license: '',
  additional_hardware: '',
  lim_source: '',
  pc_name: '',
  pc_make: '',
  pc_model: '',
  pc_type: '',
  operating_system: '',
  os_type: '',
  ram: '',
  cpu_type: '',
  cpu_speed: '',
  cpu_cores: '',
  hdd_c: '',
  hdd_d: '',
  network_type: '',
  amplifiers: '',
  distribution: '',
  speakers: '',
  other_equipment: '',
  music_spec_link: '',
  syb_schedules_link: '',
  comments: '',
};

const ClientTechDetailForm: React.FC<ClientTechDetailFormProps> = ({
  open,
  onClose,
  onSave,
  detail,
  companies,
  initialCompanyId,
}) => {
  const [form, setForm] = useState<FormState>(emptyForm);
  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null);
  const [zones, setZones] = useState<Zone[]>([]);
  const [zonesLoading, setZonesLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successOpen, setSuccessOpen] = useState(false);
  const [installDate, setInstallDate] = useState<Date | null>(null);
  const [commencementDate, setCommencementDate] = useState<Date | null>(null);
  const [activationDate, setActivationDate] = useState<Date | null>(null);
  const [expiryDate, setExpiryDate] = useState<Date | null>(null);

  // Populate form when dialog opens
  useEffect(() => {
    if (!open) return;

    if (detail) {
      // Edit mode: populate from existing record
      setForm({
        company: detail.company || '',
        zone: detail.zone || '',
        outlet_name: detail.outlet_name || '',
        platform_type: detail.platform_type || '',
        anydesk_id: detail.anydesk_id || '',
        teamviewer_id: detail.teamviewer_id || '',
        ultraviewer_id: detail.ultraviewer_id || '',
        other_remote_id: detail.other_remote_id || '',
        system_type: detail.system_type || '',
        soundcard_channel: detail.soundcard_channel || '',
        bms_license: detail.bms_license || '',
        additional_hardware: detail.additional_hardware || '',
        lim_source: detail.lim_source || '',
        pc_name: detail.pc_name || '',
        pc_make: detail.pc_make || '',
        pc_model: detail.pc_model || '',
        pc_type: detail.pc_type || '',
        operating_system: detail.operating_system || '',
        os_type: detail.os_type || '',
        ram: detail.ram || '',
        cpu_type: detail.cpu_type || '',
        cpu_speed: detail.cpu_speed || '',
        cpu_cores: detail.cpu_cores || '',
        hdd_c: detail.hdd_c || '',
        hdd_d: detail.hdd_d || '',
        network_type: detail.network_type || '',
        amplifiers: detail.amplifiers || '',
        distribution: detail.distribution || '',
        speakers: detail.speakers || '',
        other_equipment: detail.other_equipment || '',
        music_spec_link: detail.music_spec_link || '',
        syb_schedules_link: detail.syb_schedules_link || '',
        comments: detail.comments || '',
      });
      // Set date fields
      setInstallDate(detail.install_date ? new Date(detail.install_date + 'T00:00:00') : null);
      setCommencementDate(detail.commencement_date ? new Date(detail.commencement_date + 'T00:00:00') : null);
      setActivationDate(detail.activation_date ? new Date(detail.activation_date + 'T00:00:00') : null);
      setExpiryDate(detail.expiry_date ? new Date(detail.expiry_date + 'T00:00:00') : null);
      // Set selected company object for Autocomplete
      const company = companies.find(c => c.id === detail.company) || null;
      setSelectedCompany(company);
      // Load zones for this company
      if (detail.company) {
        loadZones(detail.company);
      }
    } else {
      // Create mode: reset everything
      setForm({ ...emptyForm });
      setZones([]);
      setInstallDate(null);
      setCommencementDate(null);
      setActivationDate(null);
      setExpiryDate(null);
      setError(null);

      if (initialCompanyId) {
        const company = companies.find(c => c.id === initialCompanyId) || null;
        setSelectedCompany(company);
        setForm(prev => ({ ...prev, company: initialCompanyId }));
        loadZones(initialCompanyId);
      } else {
        setSelectedCompany(null);
      }
    }

    setError(null);
  }, [open, detail]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadZones = async (companyId: string) => {
    if (!companyId) {
      setZones([]);
      return;
    }
    setZonesLoading(true);
    try {
      const data = await ApiService.getZonesByCompany(companyId);
      setZones(data);
    } catch (err) {
      console.error('Failed to load zones:', err);
      setZones([]);
    } finally {
      setZonesLoading(false);
    }
  };

  const handleCompanyChange = (company: Company | null) => {
    setSelectedCompany(company);
    setForm(prev => ({
      ...prev,
      company: company?.id || '',
      zone: '',
      outlet_name: '',
    }));
    setZones([]);
    if (company?.id) {
      loadZones(company.id);
    }
  };

  const handleZoneChange = (zoneId: string) => {
    const zone = zones.find(z => z.id === zoneId);
    setForm(prev => ({
      ...prev,
      zone: zoneId,
      // Auto-fill outlet_name from zone name, but only if user hasn't typed something
      outlet_name: zone ? zone.name : prev.outlet_name,
    }));
  };

  const handleFieldChange = (field: keyof FormState, value: string) => {
    setForm(prev => ({ ...prev, [field]: value }));
  };

  const handleSave = async () => {
    if (!form.company) {
      setError('Company is required');
      return;
    }
    if (!form.outlet_name.trim()) {
      setError('Outlet Name is required');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const payload: Partial<ClientTechDetail> = {
        company: form.company,
        zone: form.zone || null,
        outlet_name: form.outlet_name,
        platform_type: form.platform_type,
        anydesk_id: form.anydesk_id,
        teamviewer_id: form.teamviewer_id,
        ultraviewer_id: form.ultraviewer_id,
        other_remote_id: form.other_remote_id,
        system_type: form.system_type,
        soundcard_channel: form.soundcard_channel,
        bms_license: form.bms_license,
        additional_hardware: form.additional_hardware,
        install_date: installDate ? installDate.toISOString().split('T')[0] : null,
        commencement_date: commencementDate ? commencementDate.toISOString().split('T')[0] : null,
        activation_date: activationDate ? activationDate.toISOString().split('T')[0] : null,
        lim_source: form.lim_source,
        expiry_date: expiryDate ? expiryDate.toISOString().split('T')[0] : null,
        pc_name: form.pc_name,
        pc_make: form.pc_make,
        pc_model: form.pc_model,
        pc_type: form.pc_type,
        operating_system: form.operating_system,
        os_type: form.os_type,
        ram: form.ram,
        cpu_type: form.cpu_type,
        cpu_speed: form.cpu_speed,
        cpu_cores: form.cpu_cores,
        hdd_c: form.hdd_c,
        hdd_d: form.hdd_d,
        network_type: form.network_type,
        amplifiers: form.amplifiers,
        distribution: form.distribution,
        speakers: form.speakers,
        other_equipment: form.other_equipment,
        music_spec_link: form.music_spec_link,
        syb_schedules_link: form.syb_schedules_link,
        comments: form.comments,
      };

      if (detail) {
        await ApiService.updateClientTechDetail(detail.id, payload);
      } else {
        await ApiService.createClientTechDetail(payload);
      }

      setSuccessOpen(true);
      onSave();
      onClose();
    } catch (err: any) {
      console.error('Failed to save client tech detail:', err);
      setError(
        err.response?.data?.detail ||
        err.response?.data?.outlet_name?.[0] ||
        err.response?.data?.company?.[0] ||
        'Failed to save. Please check the form and try again.'
      );
    } finally {
      setLoading(false);
    }
  };

  const isEditMode = Boolean(detail);

  return (
    <>
      <LocalizationProvider dateAdapter={AdapterDateFns}>
      <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
        <DialogTitle>
          {isEditMode ? 'Edit Client Tech Detail' : 'New Client Tech Detail'}
        </DialogTitle>

        <DialogContent dividers>
          <Box sx={{ pt: 1 }}>
            {error && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {error}
              </Alert>
            )}

            {/* Section 1: Client & Location */}
            <Paper sx={{ p: 2, mb: 2 }}>
              <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 2 }}>
                Client and Location
              </Typography>
              <Grid container spacing={2}>
                {/* Company */}
                <Grid item xs={12} sm={6}>
                  <Autocomplete
                    options={companies}
                    value={selectedCompany}
                    onChange={(_event, newValue) => handleCompanyChange(newValue)}
                    getOptionLabel={(option) => option.name}
                    isOptionEqualToValue={(option, value) => option.id === value.id}
                    renderInput={(params) => (
                      <TextField
                        {...params}
                        label="Company"
                        required
                        placeholder="Search company..."
                      />
                    )}
                  />
                </Grid>

                {/* Zone */}
                <Grid item xs={12} sm={6}>
                  <FormControl fullWidth disabled={!form.company || zonesLoading}>
                    <InputLabel>
                      {zonesLoading ? 'Loading zones...' : 'Zone (optional)'}
                    </InputLabel>
                    <Select
                      value={form.zone}
                      label={zonesLoading ? 'Loading zones...' : 'Zone (optional)'}
                      onChange={(e) => handleZoneChange(e.target.value as string)}
                    >
                      <MenuItem value="">
                        <em>None</em>
                      </MenuItem>
                      {zones.map((zone) => (
                        <MenuItem key={zone.id} value={zone.id}>
                          {zone.name}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                </Grid>

                {/* Outlet Name */}
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Outlet Name"
                    value={form.outlet_name}
                    onChange={(e) => handleFieldChange('outlet_name', e.target.value)}
                    required
                    placeholder="e.g., Restaurant Ground Floor"
                    helperText="Auto-fills from zone selection but can be edited freely"
                  />
                </Grid>

                {/* Platform Type */}
                <Grid item xs={12} sm={6}>
                  <FormControl fullWidth>
                    <InputLabel>Platform Type</InputLabel>
                    <Select
                      value={form.platform_type}
                      label="Platform Type"
                      onChange={(e) => handleFieldChange('platform_type', e.target.value as string)}
                    >
                      <MenuItem value="">
                        <em>Not specified</em>
                      </MenuItem>
                      <MenuItem value="soundtrack">Soundtrack Your Brand</MenuItem>
                      <MenuItem value="beatbreeze">Beat Breeze</MenuItem>
                      <MenuItem value="bms">BMS</MenuItem>
                      <MenuItem value="dm">DM</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>
              </Grid>
            </Paper>

            {/* Section 2: Remote Access */}
            <Paper sx={{ p: 2, mb: 2 }}>
              <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 2 }}>
                Remote Access
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="AnyDesk ID"
                    value={form.anydesk_id}
                    onChange={(e) => handleFieldChange('anydesk_id', e.target.value)}
                    placeholder="e.g., 123 456 789"
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="TeamViewer ID"
                    value={form.teamviewer_id}
                    onChange={(e) => handleFieldChange('teamviewer_id', e.target.value)}
                    placeholder="e.g., 1 234 567 890"
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="UltraViewer ID"
                    value={form.ultraviewer_id}
                    onChange={(e) => handleFieldChange('ultraviewer_id', e.target.value)}
                    placeholder="e.g., 987654321"
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Other Remote Access ID"
                    value={form.other_remote_id}
                    onChange={(e) => handleFieldChange('other_remote_id', e.target.value)}
                    placeholder="e.g., RustDesk: abc123"
                  />
                </Grid>
              </Grid>
            </Paper>

            {/* Section 3: System Configuration */}
            <Paper sx={{ p: 2, mb: 2 }}>
              <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 2 }}>
                System Configuration
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <FormControl fullWidth>
                    <InputLabel>System Type</InputLabel>
                    <Select
                      value={form.system_type}
                      label="System Type"
                      onChange={(e) => handleFieldChange('system_type', e.target.value as string)}
                    >
                      <MenuItem value="">
                        <em>Not specified</em>
                      </MenuItem>
                      <MenuItem value="single">Single</MenuItem>
                      <MenuItem value="multi">Multi</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Soundcard Channel"
                    value={form.soundcard_channel}
                    onChange={(e) => handleFieldChange('soundcard_channel', e.target.value)}
                    placeholder="e.g., Channel 1 / 2"
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="BMS License"
                    value={form.bms_license}
                    onChange={(e) => handleFieldChange('bms_license', e.target.value)}
                    placeholder="e.g., BMS-2024-XXXXX"
                  />
                </Grid>
                <Grid item xs={12}>
                  <TextField
                    fullWidth
                    label="Additional System Hardware"
                    value={form.additional_hardware}
                    onChange={(e) => handleFieldChange('additional_hardware', e.target.value)}
                    multiline
                    rows={3}
                    placeholder="List any additional hardware (e.g., USB soundcard, HDMI splitter)"
                  />
                </Grid>
              </Grid>
            </Paper>

            {/* Section 4: Dates and Licensing */}
            <Paper sx={{ p: 2, mb: 2 }}>
              <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 2 }}>
                Dates and Licensing
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <DatePicker
                    label="Install Date"
                    value={installDate}
                    onChange={(val) => setInstallDate(val)}
                    slotProps={{
                      textField: { fullWidth: true },
                      field: { clearable: true },
                    }}
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <DatePicker
                    label="Commencement Date"
                    value={commencementDate}
                    onChange={(val) => setCommencementDate(val)}
                    slotProps={{
                      textField: { fullWidth: true },
                      field: { clearable: true },
                    }}
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <DatePicker
                    label="Activation Date (SYB)"
                    value={activationDate}
                    onChange={(val) => setActivationDate(val)}
                    slotProps={{
                      textField: { fullWidth: true },
                      field: { clearable: true },
                    }}
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="LIM Source"
                    value={form.lim_source}
                    onChange={(e) => handleFieldChange('lim_source', e.target.value)}
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <DatePicker
                    label="Expiry Date"
                    value={expiryDate}
                    onChange={(val) => setExpiryDate(val)}
                    slotProps={{
                      textField: { fullWidth: true },
                      field: { clearable: true },
                    }}
                  />
                </Grid>
              </Grid>
            </Paper>

            {/* Section 5: PC Specifications */}
            <Paper sx={{ p: 2, mb: 2 }}>
              <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 2 }}>
                PC Specifications
              </Typography>
              <Grid container spacing={2}>
                {/* Row 1: PC Name, Operating System, OS Type */}
                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    label="PC Name"
                    value={form.pc_name}
                    onChange={(e) => handleFieldChange('pc_name', e.target.value)}
                    placeholder="e.g., FRONT-DESK-01"
                  />
                </Grid>
                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    label="Operating System"
                    value={form.operating_system}
                    onChange={(e) => handleFieldChange('operating_system', e.target.value)}
                    placeholder="e.g., Windows 10, Windows 11"
                  />
                </Grid>
                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    select
                    label="OS Type"
                    value={form.os_type}
                    onChange={(e) => handleFieldChange('os_type', e.target.value)}
                  >
                    <MenuItem value="">-</MenuItem>
                    <MenuItem value="32-bit">32-bit</MenuItem>
                    <MenuItem value="64-bit">64-bit</MenuItem>
                  </TextField>
                </Grid>

                {/* Row 2: PC Make, Model, Type */}
                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    label="PC Make"
                    value={form.pc_make}
                    onChange={(e) => handleFieldChange('pc_make', e.target.value)}
                    placeholder="e.g., Dell, Lenovo, HP"
                  />
                </Grid>
                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    label="PC Model"
                    value={form.pc_model}
                    onChange={(e) => handleFieldChange('pc_model', e.target.value)}
                    placeholder="e.g., OptiPlex 7010"
                  />
                </Grid>
                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    label="PC Type"
                    value={form.pc_type}
                    onChange={(e) => handleFieldChange('pc_type', e.target.value)}
                    placeholder="e.g., Desktop, Mini PC, SFF"
                  />
                </Grid>

                {/* Row 3: RAM, CPU Type, CPU Speed */}
                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    label="RAM"
                    value={form.ram}
                    onChange={(e) => handleFieldChange('ram', e.target.value)}
                    placeholder="e.g., 8 GB DDR4"
                  />
                </Grid>
                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    label="CPU Type"
                    value={form.cpu_type}
                    onChange={(e) => handleFieldChange('cpu_type', e.target.value)}
                    placeholder="e.g., Intel Core i5"
                  />
                </Grid>
                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    label="CPU Speed"
                    value={form.cpu_speed}
                    onChange={(e) => handleFieldChange('cpu_speed', e.target.value)}
                    placeholder="e.g., 3.0 GHz"
                  />
                </Grid>

                {/* Full width: CPU Cores */}
                <Grid item xs={12}>
                  <TextField
                    fullWidth
                    label="CPU Cores and Logical Processors"
                    value={form.cpu_cores}
                    onChange={(e) => handleFieldChange('cpu_cores', e.target.value)}
                    placeholder="e.g., 6 cores / 12 logical processors"
                  />
                </Grid>

                {/* Row 3: HDD C, HDD D, Network Type */}
                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    label="HDD C:"
                    value={form.hdd_c}
                    onChange={(e) => handleFieldChange('hdd_c', e.target.value)}
                    placeholder="e.g., 256 GB SSD"
                  />
                </Grid>
                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    label="HDD D:"
                    value={form.hdd_d}
                    onChange={(e) => handleFieldChange('hdd_d', e.target.value)}
                    placeholder="e.g., 1 TB HDD"
                  />
                </Grid>
                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    label="Network Type"
                    value={form.network_type}
                    onChange={(e) => handleFieldChange('network_type', e.target.value)}
                    placeholder="e.g., Ethernet, WiFi 5"
                  />
                </Grid>
              </Grid>
            </Paper>

            {/* Section 5: Audio Equipment */}
            <Paper sx={{ p: 2, mb: 2 }}>
              <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 2 }}>
                Audio Equipment
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Amplifiers"
                    value={form.amplifiers}
                    onChange={(e) => handleFieldChange('amplifiers', e.target.value)}
                    multiline
                    rows={3}
                    placeholder="e.g., Crown XLS 1002, 2-channel, 215W per channel"
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Distribution"
                    value={form.distribution}
                    onChange={(e) => handleFieldChange('distribution', e.target.value)}
                    multiline
                    rows={3}
                    placeholder="e.g., BSS Audio Soundweb London, 4x4 matrix"
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Speakers"
                    value={form.speakers}
                    onChange={(e) => handleFieldChange('speakers', e.target.value)}
                    multiline
                    rows={3}
                    placeholder="e.g., Bose DesignMax DM3C, ceiling mount, x8"
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Other Equipment"
                    value={form.other_equipment}
                    onChange={(e) => handleFieldChange('other_equipment', e.target.value)}
                    multiline
                    rows={3}
                    placeholder="e.g., Denon DN-300Z CD player, volume controller"
                  />
                </Grid>
              </Grid>
            </Paper>

            {/* Section 6: Links & Notes */}
            <Paper sx={{ p: 2, mb: 2 }}>
              <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 2 }}>
                Links and Notes
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="Music Spec Link"
                    value={form.music_spec_link}
                    onChange={(e) => handleFieldChange('music_spec_link', e.target.value)}
                    placeholder="https://..."
                    type="url"
                  />
                </Grid>
                <Grid item xs={12} sm={6}>
                  <TextField
                    fullWidth
                    label="SYB Schedules Link"
                    value={form.syb_schedules_link}
                    onChange={(e) => handleFieldChange('syb_schedules_link', e.target.value)}
                    placeholder="https://..."
                    type="url"
                  />
                </Grid>
                <Grid item xs={12}>
                  <TextField
                    fullWidth
                    label="Comments"
                    value={form.comments}
                    onChange={(e) => handleFieldChange('comments', e.target.value)}
                    multiline
                    rows={4}
                    placeholder="Any additional notes, known issues, or special instructions..."
                  />
                </Grid>
              </Grid>
            </Paper>
          </Box>
        </DialogContent>

        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleSave}
            disabled={loading}
            startIcon={loading ? <CircularProgress size={18} /> : undefined}
          >
            {loading ? 'Saving...' : (isEditMode ? 'Save Changes' : 'Create')}
          </Button>
        </DialogActions>
      </Dialog>
      </LocalizationProvider>

      <Snackbar
        open={successOpen}
        autoHideDuration={3000}
        onClose={() => setSuccessOpen(false)}
        message={isEditMode ? 'Client tech detail updated' : 'Client tech detail created'}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      />
    </>
  );
};

export default ClientTechDetailForm;
