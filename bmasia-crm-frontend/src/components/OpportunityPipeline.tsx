import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Card,
  CardContent,
  Avatar,
  Chip,
  IconButton,
  Tooltip,
  Dialog,
  DialogContent,
  DialogTitle,
  useTheme,
  Grid,
  CircularProgress,
  Alert,
} from '@mui/material';
import {
  DragIndicator as DragIcon,
  Visibility as VisibilityIcon,
  Edit as EditIcon,
  Close as CloseIcon,
  AttachMoney as MoneyIcon,
  Person as PersonIcon,
  Business as BusinessIcon,
} from '@mui/icons-material';
import { Opportunity } from '../types';
import ApiService from '../services/api';

interface OpportunityPipelineProps {
  opportunities: Opportunity[];
  onOpportunityUpdate: (opportunity: Opportunity) => void;
  onOpportunityEdit: (opportunity: Opportunity) => void;
  loading?: boolean;
}

interface StageColumn {
  id: string;
  label: string;
  color: string;
  opportunities: Opportunity[];
  totalValue: number;
  weightedValue: number;
}

interface OpportunityDetailDialogProps {
  opportunity: Opportunity | null;
  open: boolean;
  onClose: () => void;
  onEdit: (opportunity: Opportunity) => void;
}

const stageConfig = [
  { id: 'Contacted', label: 'Contacted', color: '#2196f3' },
  { id: 'Quotation Sent', label: 'Quotation Sent', color: '#ff9800' },
  { id: 'Contract Sent', label: 'Contract Sent', color: '#9c27b0' },
  { id: 'Won', label: 'Won', color: '#4caf50' },
  { id: 'Lost', label: 'Lost', color: '#f44336' },
];

const OpportunityDetailDialog: React.FC<OpportunityDetailDialogProps> = ({
  opportunity,
  open,
  onClose,
  onEdit,
}) => {
  if (!opportunity) return null;

  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  const formatDate = (dateString: string | null | undefined): string => {
    if (!dateString) return 'Not set';
    return new Date(dateString).toLocaleDateString();
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6">{opportunity.name}</Typography>
          <Box>
            <IconButton onClick={() => onEdit(opportunity)} size="small" sx={{ mr: 1 }}>
              <EditIcon />
            </IconButton>
            <IconButton onClick={onClose} size="small">
              <CloseIcon />
            </IconButton>
          </Box>
        </Box>
      </DialogTitle>
      <DialogContent>
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Box sx={{ mb: 3 }}>
              <Typography variant="h6" gutterBottom color="primary">
                Basic Information
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <BusinessIcon sx={{ mr: 1, color: 'text.secondary' }} />
                <Typography><strong>Company:</strong> {opportunity.company_name}</Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <PersonIcon sx={{ mr: 1, color: 'text.secondary' }} />
                <Typography><strong>Owner:</strong> {opportunity.owner_name}</Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <Chip 
                  label={opportunity.stage}
                  size="small"
                  sx={{ 
                    backgroundColor: stageConfig.find(s => s.id === opportunity.stage)?.color,
                    color: 'white',
                    fontWeight: 600
                  }}
                />
              </Box>
            </Box>

            <Box sx={{ mb: 3 }}>
              <Typography variant="h6" gutterBottom color="primary">
                Financial Details
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <MoneyIcon sx={{ mr: 1, color: 'text.secondary' }} />
                <Typography><strong>Expected Value:</strong> {formatCurrency(opportunity.expected_value || 0)}</Typography>
              </Box>
              <Typography><strong>Probability:</strong> {opportunity.probability}%</Typography>
              <Typography><strong>Weighted Value:</strong> {formatCurrency(opportunity.weighted_value)}</Typography>
            </Box>
          </Grid>

          <Grid item xs={12} md={6}>
            <Box sx={{ mb: 3 }}>
              <Typography variant="h6" gutterBottom color="primary">
                Timeline
              </Typography>
              <Typography><strong>Created:</strong> {formatDate(opportunity.created_at)}</Typography>
              <Typography><strong>Last Updated:</strong> {formatDate(opportunity.updated_at)}</Typography>
              <Typography><strong>Expected Close:</strong> {formatDate(opportunity.expected_close_date)}</Typography>
              <Typography><strong>Follow-up Date:</strong> {formatDate(opportunity.follow_up_date)}</Typography>
              <Typography><strong>Days in Stage:</strong> {opportunity.days_in_stage} days</Typography>
            </Box>

            <Box sx={{ mb: 3 }}>
              <Typography variant="h6" gutterBottom color="primary">
                Source & Contact
              </Typography>
              <Typography><strong>Lead Source:</strong> {opportunity.lead_source || 'Not specified'}</Typography>
              <Typography><strong>Contact Method:</strong> {opportunity.contact_method || 'Not specified'}</Typography>
              <Typography><strong>Last Contact:</strong> {formatDate(opportunity.last_contact_date)}</Typography>
            </Box>
          </Grid>

          {(opportunity.notes || opportunity.competitors || opportunity.pain_points) && (
            <Grid item xs={12}>
              <Typography variant="h6" gutterBottom color="primary">
                Additional Details
              </Typography>
              {opportunity.notes && (
                <Box sx={{ mb: 2 }}>
                  <Typography variant="subtitle2" gutterBottom>Notes:</Typography>
                  <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                    {opportunity.notes}
                  </Typography>
                </Box>
              )}
              {opportunity.competitors && (
                <Box sx={{ mb: 2 }}>
                  <Typography variant="subtitle2" gutterBottom>Competitors:</Typography>
                  <Typography variant="body2">{opportunity.competitors}</Typography>
                </Box>
              )}
              {opportunity.pain_points && (
                <Box sx={{ mb: 2 }}>
                  <Typography variant="subtitle2" gutterBottom>Pain Points:</Typography>
                  <Typography variant="body2">{opportunity.pain_points}</Typography>
                </Box>
              )}
            </Grid>
          )}
        </Grid>
      </DialogContent>
    </Dialog>
  );
};

const OpportunityCard: React.FC<{
  opportunity: Opportunity;
  onView: (opportunity: Opportunity) => void;
  onEdit: (opportunity: Opportunity) => void;
  onStageChange: (opportunityId: string, newStage: string) => void;
}> = ({ opportunity, onView, onEdit, onStageChange }) => {
  const theme = useTheme();
  const [draggedOver, setDraggedOver] = useState(false);

  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  const handleDragStart = (e: React.DragEvent) => {
    e.dataTransfer.setData('text/plain', JSON.stringify({
      id: opportunity.id,
      stage: opportunity.stage
    }));
  };

  const stageColor = stageConfig.find(s => s.id === opportunity.stage)?.color || '#2196f3';

  return (
    <Card 
      sx={{ 
        mb: 1, 
        cursor: 'grab',
        transition: 'all 0.2s ease-in-out',
        transform: draggedOver ? 'scale(1.02)' : 'scale(1)',
        boxShadow: draggedOver ? theme.shadows[8] : theme.shadows[1],
        borderLeft: `4px solid ${stageColor}`,
        '&:hover': {
          boxShadow: theme.shadows[4],
        },
        '&:active': {
          cursor: 'grabbing',
        }
      }}
      draggable
      onDragStart={handleDragStart}
      onDragEnd={() => setDraggedOver(false)}
    >
      <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 600, flex: 1 }}>
            {opportunity.name}
          </Typography>
          <DragIcon sx={{ color: 'text.disabled', fontSize: 16, ml: 1 }} />
        </Box>
        
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          {opportunity.company_name}
        </Typography>
        
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
          <Typography variant="body2" sx={{ fontWeight: 600, color: stageColor }}>
            {formatCurrency(opportunity.expected_value || 0)}
          </Typography>
          <Chip 
            label={`${opportunity.probability}%`} 
            size="small"
            sx={{ 
              backgroundColor: stageColor,
              color: 'white',
              fontSize: '0.75rem',
              height: 20
            }}
          />
        </Box>
        
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <Avatar 
              sx={{ 
                width: 24, 
                height: 24, 
                fontSize: '0.75rem',
                backgroundColor: stageColor
              }}
            >
              {opportunity.owner_name?.split(' ').map(n => n[0]).join('').substring(0, 2)}
            </Avatar>
            <Typography variant="caption" sx={{ ml: 1, color: 'text.secondary' }}>
              {opportunity.days_in_stage}d
            </Typography>
          </Box>
          
          <Box>
            <Tooltip title="View Details">
              <IconButton 
                size="small" 
                onClick={(e) => {
                  e.stopPropagation();
                  onView(opportunity);
                }}
              >
                <VisibilityIcon sx={{ fontSize: 16 }} />
              </IconButton>
            </Tooltip>
            <Tooltip title="Edit">
              <IconButton 
                size="small" 
                onClick={(e) => {
                  e.stopPropagation();
                  onEdit(opportunity);
                }}
              >
                <EditIcon sx={{ fontSize: 16 }} />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
};

const OpportunityPipeline: React.FC<OpportunityPipelineProps> = ({
  opportunities,
  onOpportunityUpdate,
  onOpportunityEdit,
  loading = false,
}) => {
  const [selectedOpportunity, setSelectedOpportunity] = useState<Opportunity | null>(null);
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);
  const [draggedOver, setDraggedOver] = useState<string | null>(null);
  const [updating, setUpdating] = useState(false);
  const [error, setError] = useState('');

  const formatCurrency = (value: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  const organizeOpportunitiesByStage = (): StageColumn[] => {
    return stageConfig.map(stage => {
      const stageOpportunities = opportunities.filter(opp => opp.stage === stage.id);
      const totalValue = stageOpportunities.reduce((sum, opp) => sum + (opp.expected_value || 0), 0);
      const weightedValue = stageOpportunities.reduce((sum, opp) => sum + opp.weighted_value, 0);
      
      return {
        id: stage.id,
        label: stage.label,
        color: stage.color,
        opportunities: stageOpportunities,
        totalValue,
        weightedValue,
      };
    });
  };

  const handleOpportunityView = (opportunity: Opportunity) => {
    setSelectedOpportunity(opportunity);
    setDetailDialogOpen(true);
  };

  const handleStageChange = async (opportunityId: string, newStage: string) => {
    try {
      setUpdating(true);
      setError('');
      
      const updatedOpportunity = await ApiService.updateOpportunity(opportunityId, { stage: newStage });
      onOpportunityUpdate(updatedOpportunity);
    } catch (err: any) {
      setError('Failed to update opportunity stage');
      console.error('Stage update error:', err);
    } finally {
      setUpdating(false);
    }
  };

  const handleDragOver = (e: React.DragEvent, stageId: string) => {
    e.preventDefault();
    setDraggedOver(stageId);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setDraggedOver(null);
  };

  const handleDrop = (e: React.DragEvent, newStage: string) => {
    e.preventDefault();
    setDraggedOver(null);
    
    try {
      const data = JSON.parse(e.dataTransfer.getData('text/plain'));
      if (data.id && data.stage !== newStage) {
        handleStageChange(data.id, newStage);
      }
    } catch (err) {
      console.error('Drop error:', err);
    }
  };

  const stages = organizeOpportunitiesByStage();
  const totalPipelineValue = stages.reduce((sum, stage) => sum + stage.totalValue, 0);
  const totalWeightedValue = stages.reduce((sum, stage) => sum + stage.weightedValue, 0);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* Pipeline Summary */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          Pipeline Summary
        </Typography>
        <Grid container spacing={3}>
          <Grid item xs={12} sm={4}>
            <Typography variant="h4" color="primary">
              {opportunities.length}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Total Opportunities
            </Typography>
          </Grid>
          <Grid item xs={12} sm={4}>
            <Typography variant="h4" color="primary">
              {formatCurrency(totalPipelineValue)}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Total Pipeline Value
            </Typography>
          </Grid>
          <Grid item xs={12} sm={4}>
            <Typography variant="h4" color="primary">
              {formatCurrency(totalWeightedValue)}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Weighted Pipeline Value
            </Typography>
          </Grid>
        </Grid>
      </Paper>

      {/* Pipeline Stages */}
      <Box sx={{ display: 'flex', gap: 2, overflowX: 'auto', pb: 2 }}>
        {stages.map((stage) => (
          <Paper
            key={stage.id}
            sx={{
              minWidth: 280,
              maxWidth: 320,
              p: 2,
              backgroundColor: draggedOver === stage.id ? 'action.hover' : 'background.paper',
              border: draggedOver === stage.id ? `2px dashed ${stage.color}` : '1px solid',
              borderColor: draggedOver === stage.id ? stage.color : 'divider',
              transition: 'all 0.2s ease-in-out',
            }}
            onDragOver={(e) => handleDragOver(e, stage.id)}
            onDragLeave={handleDragLeave}
            onDrop={(e) => handleDrop(e, stage.id)}
          >
            {/* Stage Header */}
            <Box sx={{ mb: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <Box
                  sx={{
                    width: 12,
                    height: 12,
                    borderRadius: '50%',
                    backgroundColor: stage.color,
                    mr: 1,
                  }}
                />
                <Typography variant="h6" sx={{ fontWeight: 600 }}>
                  {stage.label}
                </Typography>
                <Chip 
                  label={stage.opportunities.length} 
                  size="small" 
                  sx={{ ml: 'auto', backgroundColor: stage.color, color: 'white' }}
                />
              </Box>
              
              <Typography variant="body2" color="text.secondary">
                {formatCurrency(stage.totalValue)} total
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {formatCurrency(stage.weightedValue)} weighted
              </Typography>
            </Box>

            {/* Opportunities */}
            <Box sx={{ maxHeight: 600, overflowY: 'auto' }}>
              {stage.opportunities.length === 0 ? (
                <Typography 
                  variant="body2" 
                  color="text.secondary" 
                  sx={{ 
                    textAlign: 'center', 
                    py: 4,
                    border: '2px dashed',
                    borderColor: 'divider',
                    borderRadius: 1
                  }}
                >
                  Drop opportunities here
                </Typography>
              ) : (
                stage.opportunities.map((opportunity) => (
                  <OpportunityCard
                    key={opportunity.id}
                    opportunity={opportunity}
                    onView={handleOpportunityView}
                    onEdit={onOpportunityEdit}
                    onStageChange={handleStageChange}
                  />
                ))
              )}
            </Box>
          </Paper>
        ))}
      </Box>

      {/* Detail Dialog */}
      <OpportunityDetailDialog
        opportunity={selectedOpportunity}
        open={detailDialogOpen}
        onClose={() => {
          setDetailDialogOpen(false);
          setSelectedOpportunity(null);
        }}
        onEdit={(opportunity) => {
          setDetailDialogOpen(false);
          setSelectedOpportunity(null);
          onOpportunityEdit(opportunity);
        }}
      />

      {/* Loading Overlay */}
      {updating && (
        <Box
          sx={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.3)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
          }}
        >
          <CircularProgress size={60} />
        </Box>
      )}
    </Box>
  );
};

export default OpportunityPipeline;