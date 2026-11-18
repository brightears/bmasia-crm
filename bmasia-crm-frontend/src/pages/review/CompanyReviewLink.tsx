import React, { useEffect, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { Chip } from '@mui/material';
import { FactCheckOutlined } from '@mui/icons-material';
import reviewApi from '../../services/reviewApi';
import { loadReviewSettings, proposalsOn, REVIEW_CHANGED_EVENT } from './useReviewStatus';

/**
 * "3 suggestions to review" on a company header. Shows nothing while suggestions are switched off,
 * when there are none, or when the count cannot be read.
 */
const CompanyReviewLink: React.FC<{ companyId: string }> = ({ companyId }) => {
  const [count, setCount] = useState(0);

  useEffect(() => {
    let alive = true;
    const refresh = async () => {
      const settings = await loadReviewSettings();
      if (!proposalsOn(settings)) {
        if (alive) setCount(0);
        return;
      }
      try {
        const n = await reviewApi.openCount(companyId);
        if (alive) setCount(n);
      } catch {
        if (alive) setCount(0);
      }
    };
    refresh();
    window.addEventListener(REVIEW_CHANGED_EVENT, refresh);
    return () => {
      alive = false;
      window.removeEventListener(REVIEW_CHANGED_EVENT, refresh);
    };
  }, [companyId]);

  if (count <= 0) return null;
  return (
    <Chip
      component={RouterLink}
      to={`/review?company=${encodeURIComponent(companyId)}`}
      clickable
      size="small"
      color="warning"
      icon={<FactCheckOutlined />}
      label={`${count} ${count === 1 ? 'suggestion' : 'suggestions'} to review`}
      data-testid="company-review-link"
    />
  );
};

export default CompanyReviewLink;
