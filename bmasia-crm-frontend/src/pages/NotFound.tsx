import React from 'react';
import { Button, Paper } from '@mui/material';
import { SearchOff } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { EmptyState } from '../components/ui';

/** Shown for any address the app does not know, instead of an empty page. */
const NotFoundPage: React.FC = () => {
  const navigate = useNavigate();
  return (
    <Paper>
      <EmptyState
        icon={<SearchOff />}
        title="This page does not exist"
        description="The link may be old or mistyped. Use the menu, or go back to Today."
        action={
          <Button variant="contained" onClick={() => navigate('/today')}>
            Go to Today
          </Button>
        }
      />
    </Paper>
  );
};

export default NotFoundPage;
