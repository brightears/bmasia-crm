import React, { useCallback, useEffect, useState } from 'react';
import { Alert, Box, Button, ButtonBase, Collapse, Paper, Skeleton, Typography } from '@mui/material';
import { CheckCircleOutline, ChevronRight, ExpandLess, ExpandMore, FactCheckOutlined } from '@mui/icons-material';
import { Link as RouterLink } from 'react-router-dom';
import {
  DataQualityCheckSummary,
  DataQualitySummary,
  getDataQualitySummary,
  SEVERITY_LABEL,
  SEVERITY_TONE,
} from '../services/dataQuality';

interface NeedsFixingCardProps {
  /** Change this to load the counts again (Today's refresh button). */
  refreshKey?: number;
}

const toneColor = (check: DataQualityCheckSummary) => {
  const tone = SEVERITY_TONE[check.severity];
  return tone === 'default' ? 'text.secondary' : `${tone}.main`;
};

/**
 * Today's "Needs fixing" card: one line per data-quality check that has records, most severe
 * first (the server's order), each opening that check's list. Checks with nothing to fix are
 * folded into one "N checks clear" line.
 */
const NeedsFixingCard: React.FC<NeedsFixingCardProps> = ({ refreshKey = 0 }) => {
  const [data, setData] = useState<DataQualitySummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showClear, setShowClear] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setData(await getDataQualitySummary(0));
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Could not load the checks');
    }
  }, []);

  useEffect(() => {
    setData(null);
    load();
  }, [load, refreshKey]);

  const open = data ? data.checks.filter((c) => c.count > 0) : [];
  const clear = data ? data.checks.filter((c) => c.count === 0) : [];

  return (
    <Paper component="section" aria-labelledby="needs-fixing-title" sx={{ overflow: 'hidden' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 2.5, pt: 1.75, pb: 1.25 }}>
        <Box sx={{ color: 'primary.main', display: 'flex', '& svg': { fontSize: 20 } }}>
          <FactCheckOutlined />
        </Box>
        <Box sx={{ minWidth: 0, flex: 1 }}>
          <Typography variant="h6" component="h2" id="needs-fixing-title">
            Needs fixing
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Wrong or about to be missed
          </Typography>
        </Box>
        <Button component={RouterLink} to="/needs-fixing" size="small" sx={{ flexShrink: 0 }}>
          View all
        </Button>
      </Box>

      {error && (
        <Box sx={{ px: 2.5, pb: 2 }}>
          <Alert
            severity="error"
            action={
              <Button color="inherit" size="small" onClick={load}>
                Try again
              </Button>
            }
          >
            {error}
          </Alert>
        </Box>
      )}

      {!data && !error && (
        <Box sx={{ px: 2.5, pb: 2 }} aria-busy="true" aria-label="Loading checks">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} variant="rounded" height={36} sx={{ mb: 1 }} />
          ))}
        </Box>
      )}

      {data && open.length === 0 && (
        <Box sx={{ px: 2.5, py: 3, display: 'flex', alignItems: 'center', gap: 1.5, borderTop: 1, borderColor: 'divider' }}>
          <CheckCircleOutline color="success" />
          <Typography variant="body2">Nothing needs fixing: all {data.checks.length} checks are clear.</Typography>
        </Box>
      )}

      {data &&
        (['high', 'medium', 'low'] as const).map((severity) => {
          const group = open.filter((c) => c.severity === severity);
          if (group.length === 0) return null;
          return (
            <Box key={severity} component="section" aria-label={`${SEVERITY_LABEL[severity]} priority`}>
              <Typography
                variant="overline"
                color="text.secondary"
                sx={{ display: 'block', px: 2.5, pt: 1, pb: 0.25, lineHeight: 2, borderTop: 1, borderColor: 'divider' }}
              >
                {SEVERITY_LABEL[severity]} priority
              </Typography>
              <Box component="ul" sx={{ listStyle: 'none', m: 0, p: 0, pb: 0.5 }}>
                {group.map((check) => (
                  <li key={check.key}>
                    <ButtonBase
                      component={RouterLink}
                      to={`/needs-fixing/${check.key}`}
                      title={check.why}
                      sx={{
                        width: '100%',
                        justifyContent: 'flex-start',
                        textAlign: 'left',
                        gap: 1.5,
                        px: 2.5,
                        py: 0.875,
                        '&:hover': { bgcolor: 'action.hover' },
                        '&:hover .row-chevron': { color: 'text.primary', transform: 'translateX(2px)' },
                      }}
                    >
                      <Box
                        aria-hidden
                        sx={{ width: 8, height: 8, borderRadius: '50%', flexShrink: 0, bgcolor: toneColor(check) }}
                      />
                      <Typography sx={{ flex: 1, minWidth: 0, fontSize: '0.875rem', lineHeight: 1.4 }}>
                        {check.title}
                      </Typography>
                      <Typography
                        component="span"
                        sx={{ fontWeight: 700, fontVariantNumeric: 'tabular-nums', color: toneColor(check), flexShrink: 0 }}
                      >
                        {check.count.toLocaleString('en-US')}
                      </Typography>
                      <ChevronRight
                        className="row-chevron"
                        sx={{ color: 'text.disabled', fontSize: 18, transition: 'transform 120ms, color 120ms', flexShrink: 0 }}
                      />
                    </ButtonBase>
                  </li>
                ))}
              </Box>
            </Box>
          );
        })}

      {data && open.length > 0 && clear.length > 0 && (
        <Box sx={{ borderTop: 1, borderColor: 'divider' }}>
          <ButtonBase
            onClick={() => setShowClear((v) => !v)}
            aria-expanded={showClear}
            sx={{ width: '100%', justifyContent: 'flex-start', gap: 1.5, px: 2.5, py: 1.25, color: 'text.secondary' }}
          >
            <CheckCircleOutline color="success" sx={{ fontSize: 18 }} />
            <Typography variant="body2" sx={{ flex: 1, textAlign: 'left' }}>
              {clear.length === 1 ? '1 check clear' : `${clear.length} checks clear`}
            </Typography>
            {showClear ? <ExpandLess fontSize="small" /> : <ExpandMore fontSize="small" />}
          </ButtonBase>
          <Collapse in={showClear} unmountOnExit>
            <Box component="ul" sx={{ listStyle: 'none', m: 0, px: 2.5, pb: 1.5, pt: 0 }}>
              {clear.map((check) => (
                <Typography component="li" key={check.key} variant="body2" color="text.secondary" sx={{ py: 0.5, pl: 4 }}>
                  {check.title}
                </Typography>
              ))}
            </Box>
          </Collapse>
        </Box>
      )}
    </Paper>
  );
};

export default NeedsFixingCard;
