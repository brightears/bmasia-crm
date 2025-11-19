import React, { useState } from 'react';
import {
  Box,
  Button,
  Typography,
  CircularProgress,
  Alert,
  Snackbar,
} from '@mui/material';
import { ThumbUp, ThumbDown } from '@mui/icons-material';

interface KBVotingButtonsProps {
  articleId: string;
  helpfulCount: number;
  notHelpfulCount: number;
  onVote: (articleId: string, isHelpful: boolean) => Promise<void>;
}

const KBVotingButtons: React.FC<KBVotingButtonsProps> = ({
  articleId,
  helpfulCount,
  notHelpfulCount,
  onVote,
}) => {
  const [userVote, setUserVote] = useState<boolean | null>(null);
  const [voting, setVoting] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);
  const [error, setError] = useState('');

  const handleVote = async (isHelpful: boolean) => {
    if (userVote !== null) {
      // Already voted
      return;
    }

    try {
      setVoting(true);
      setError('');
      await onVote(articleId, isHelpful);
      setUserVote(isHelpful);
      setShowSuccess(true);
    } catch (err: any) {
      console.error('Failed to submit vote:', err);
      setError(`Failed to submit vote: ${err.response?.data?.detail || err.message || 'Unknown error'}`);
    } finally {
      setVoting(false);
    }
  };

  const totalVotes = helpfulCount + notHelpfulCount;
  const helpfulPercentage = totalVotes > 0 ? Math.round((helpfulCount / totalVotes) * 100) : 0;

  return (
    <Box>
      <Box sx={{ textAlign: 'center', py: 3, bgcolor: 'rgba(0, 0, 0, 0.02)', borderRadius: 2 }}>
        <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
          Was this article helpful?
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          {totalVotes > 0
            ? `${helpfulPercentage}% of readers found this helpful (${totalVotes} votes)`
            : 'Be the first to rate this article'}
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 2, maxWidth: 600, mx: 'auto' }}>
            {error}
          </Alert>
        )}

        <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center' }}>
          <Button
            variant={userVote === true ? 'contained' : 'outlined'}
            startIcon={voting && userVote === null ? <CircularProgress size={16} /> : <ThumbUp />}
            onClick={() => handleVote(true)}
            disabled={userVote !== null || voting}
            sx={{
              minWidth: 140,
              bgcolor: userVote === true ? '#4CAF50' : undefined,
              borderColor: userVote === true ? '#4CAF50' : '#FFA500',
              color: userVote === true ? 'white' : '#FFA500',
              '&:hover': {
                bgcolor: userVote === true ? '#45a049' : 'rgba(255, 165, 0, 0.08)',
                borderColor: userVote === true ? '#45a049' : '#FF8C00',
              },
              '&.Mui-disabled': {
                bgcolor: userVote === true ? '#4CAF50' : undefined,
                color: userVote === true ? 'white' : undefined,
                borderColor: userVote === true ? '#4CAF50' : undefined,
              },
            }}
          >
            Yes ({helpfulCount + (userVote === true ? 1 : 0)})
          </Button>

          <Button
            variant={userVote === false ? 'contained' : 'outlined'}
            startIcon={voting && userVote === null ? <CircularProgress size={16} /> : <ThumbDown />}
            onClick={() => handleVote(false)}
            disabled={userVote !== null || voting}
            sx={{
              minWidth: 140,
              bgcolor: userVote === false ? '#f44336' : undefined,
              borderColor: userVote === false ? '#f44336' : '#FFA500',
              color: userVote === false ? 'white' : '#FFA500',
              '&:hover': {
                bgcolor: userVote === false ? '#da190b' : 'rgba(255, 165, 0, 0.08)',
                borderColor: userVote === false ? '#da190b' : '#FF8C00',
              },
              '&.Mui-disabled': {
                bgcolor: userVote === false ? '#f44336' : undefined,
                color: userVote === false ? 'white' : undefined,
                borderColor: userVote === false ? '#f44336' : undefined,
              },
            }}
          >
            No ({notHelpfulCount + (userVote === false ? 1 : 0)})
          </Button>
        </Box>

        {userVote !== null && (
          <Typography
            variant="body2"
            color="success.main"
            sx={{ mt: 2, fontWeight: 500 }}
          >
            Thank you for your feedback!
          </Typography>
        )}
      </Box>

      {/* Success Snackbar */}
      <Snackbar
        open={showSuccess}
        autoHideDuration={3000}
        onClose={() => setShowSuccess(false)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={() => setShowSuccess(false)} severity="success" sx={{ width: '100%' }}>
          Thank you for your feedback!
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default KBVotingButtons;
