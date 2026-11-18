import React, { useState } from 'react';
import { Box, Link, Tooltip } from '@mui/material';
import { segmentText } from './reviewModel';

interface PlainTextProps {
  value: string;
  /** Characters shown before "Show all" appears. */
  clampAt?: number;
  /** Keep line breaks (notes, quotes, descriptions). */
  multiline?: boolean;
  sx?: object;
  component?: React.ElementType;
}

/**
 * Text from a proposal, shown exactly as stored and only as text: never HTML, markdown or an
 * automatic link. Invisible and direction-changing characters are shown as small "U+202E" markers
 * so a value cannot display differently from what would be saved. Long values wrap and can be expanded.
 */
const PlainText: React.FC<PlainTextProps> = ({ value, clampAt = 400, multiline = false, sx, component = 'span' }) => {
  const [expanded, setExpanded] = useState(false);
  const long = value.length > clampAt;
  const shown = long && !expanded ? value.slice(0, clampAt) : value;
  const segments = segmentText(shown);

  return (
    <Box
      component={component}
      sx={{
        whiteSpace: multiline ? 'pre-wrap' : 'normal',
        overflowWrap: 'anywhere',
        wordBreak: 'break-word',
        unicodeBidi: 'isolate',
        ...sx,
      }}
    >
      {segments.map((seg, i) =>
        seg.hidden ? (
          <Tooltip key={i} title="Invisible or direction-changing character. It would be saved as part of the value.">
            <Box
              component="span"
              data-hidden-char={seg.hidden}
              sx={{
                mx: '1px',
                px: '3px',
                borderRadius: '3px',
                fontSize: '0.7em',
                fontFamily: 'monospace',
                verticalAlign: 'middle',
                bgcolor: 'warning.main',
                color: 'warning.contrastText',
                whiteSpace: 'nowrap',
              }}
            >
              {seg.hidden}
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

export default PlainText;
