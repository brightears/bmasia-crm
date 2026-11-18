import React, { useState } from 'react';
import { Box, Link, Tooltip } from '@mui/material';
import { segmentText } from './textSafety';

interface PlainTextProps {
  value: string;
  /** Characters shown before "Show all" appears. */
  clampAt?: number;
  /** Kept for callers; line breaks and runs of spaces are always shown as stored. */
  multiline?: boolean;
  /** A stored value: spaces at its start and end show as "\u2423". */
  edges?: boolean;
  sx?: object;
}

const MARKER_HELP: Record<string, string> = {
  invisible: 'Invisible or direction-changing character. It would be saved as part of the value.',
  space: 'Not an ordinary space (for example a non-breaking space). It would be saved as part of the value.',
  edge: 'A space at the start or end of the value. It would be saved as part of the value.',
};

/**
 * Text from a proposal, shown exactly as stored and only as text: never HTML, markdown or an
 * automatic link. It sits in its own direction-isolated element, so it cannot reorder what is
 * around it. Line breaks and runs of spaces are kept; invisible characters and unusual spaces
 * show as small markers. Long values wrap and can be expanded.
 */
const PlainText: React.FC<PlainTextProps> = ({ value, clampAt = 400, edges = false, sx }) => {
  const [expanded, setExpanded] = useState(false);
  const long = value.length > clampAt;
  const shown = long && !expanded ? value.slice(0, clampAt) : value;
  const segments = segmentText(shown, edges);

  return (
    <Box
      component="bdi"
      sx={{
        whiteSpace: 'pre-wrap',
        overflowWrap: 'anywhere',
        wordBreak: 'break-word',
        unicodeBidi: 'isolate',
        ...sx,
      }}
    >
      {segments.map((seg, i) =>
        seg.marker ? (
          <Tooltip key={i} title={MARKER_HELP[seg.kind || 'invisible']}>
            <Box
              component="span"
              data-hidden-char={seg.marker}
              sx={{
                mx: '1px',
                px: '3px',
                borderRadius: '3px',
                fontSize: '0.7em',
                fontFamily: 'monospace',
                verticalAlign: 'middle',
                bgcolor: seg.kind === 'invisible' ? 'warning.main' : 'action.selected',
                color: seg.kind === 'invisible' ? 'warning.contrastText' : 'text.primary',
                whiteSpace: 'nowrap',
              }}
            >
              {seg.marker}
            </Box>
          </Tooltip>
        ) : (
          <React.Fragment key={i}>{seg.text}</React.Fragment>
        ),
      )}
      {long && (
        <>
          {!expanded && '… '}
          <Link
            component="button"
            type="button"
            variant="body2"
            onClick={() => setExpanded((v) => !v)}
            sx={{ ml: 0.5, verticalAlign: 'baseline' }}
          >
            {expanded ? 'Show less' : `Show all (${value.length.toLocaleString('en-US')} characters)`}
          </Link>
        </>
      )}
    </Box>
  );
};

export default React.memo(PlainText);
