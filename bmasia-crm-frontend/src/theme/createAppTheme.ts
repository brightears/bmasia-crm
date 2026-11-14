import { alpha, createTheme, Theme, ThemeOptions } from '@mui/material/styles';
import { brand, dark, fontFamily, ink, layout, status } from './tokens';

type SoftTone = { text: string; bg: string };

const softTone = (color: string | undefined, isDark: boolean): SoftTone | null => {
  const map: Record<string, SoftTone> = {
    success: status.success,
    warning: status.warning,
    error: status.error,
    info: status.info,
    primary: { text: brand.amberText, bg: brand.amberTint },
    secondary: status.neutral,
    default: status.neutral,
  };
  const tone = map[color || 'default'];
  if (!tone) return null;
  if (!isDark) return tone;
  // Dark mode: tinted background with a light text colour.
  const darkText: Record<string, string> = {
    success: '#7FD3A8',
    warning: '#F5C46E',
    error: '#F59A8F',
    info: '#8DB9F0',
    primary: brand.amber,
    secondary: dark.textSecondary,
    default: dark.textSecondary,
  };
  const solid: Record<string, string> = {
    success: status.success.main,
    warning: status.warning.main,
    error: status.error.main,
    info: status.info.main,
    primary: brand.amber,
    secondary: ink[400],
    default: ink[400],
  };
  return { text: darkText[color || 'default'], bg: alpha(solid[color || 'default'], 0.18) };
};

/**
 * The one theme for the whole app. Pages get the BMAsia look through MUI component
 * defaults, so most screens improve without being edited.
 */
export const createAppTheme = (mode: 'light' | 'dark'): Theme => {
  const isDark = mode === 'dark';
  const textPrimary = isDark ? dark.text : ink[900];
  const textSecondary = isDark ? dark.textSecondary : ink[500];
  const divider = isDark ? dark.border : ink[200];
  const paper = isDark ? dark.paper : '#FFFFFF';
  const subtle = isDark ? dark.raised : ink[25];
  const focusRing = isDark ? brand.amber : brand.amberStrong;
  const primaryMain = isDark ? brand.amber : brand.amberStrong;
  const pageBackground = isDark ? dark.background : ink[50];
  const hoverBg = isDark ? 'rgba(255,255,255,0.05)' : alpha(ink[900], 0.04);
  const selectedBg = isDark ? alpha(brand.amber, 0.14) : brand.amberTint;

  const options: ThemeOptions = {
    palette: {
      mode,
      primary: {
        // `main` is the accessible amber used for text, icons, outlines and focus.
        // Filled primary buttons use the bright brand amber (see MuiButton below).
        main: primaryMain,
        light: '#F5B84D',
        dark: isDark ? brand.amberHover : '#8F560A',
        contrastText: isDark ? brand.onAmber : '#FFFFFF',
      },
      secondary: {
        main: isDark ? '#C9D3DC' : ink[700],
        contrastText: isDark ? brand.navy : '#FFFFFF',
      },
      success: { main: status.success.main, dark: status.success.text, contrastText: '#FFFFFF' },
      warning: { main: status.warning.main, dark: status.warning.text, contrastText: '#FFFFFF' },
      error: { main: status.error.main, dark: status.error.text, contrastText: '#FFFFFF' },
      info: { main: status.info.main, dark: status.info.text, contrastText: '#FFFFFF' },
      background: {
        default: pageBackground,
        paper,
      },
      text: {
        primary: textPrimary,
        secondary: textSecondary,
        disabled: isDark ? 'rgba(232,237,242,0.38)' : ink[400],
      },
      divider,
      action: {
        hover: hoverBg,
        selected: selectedBg,
      },
      grey: {
        50: ink[25],
        100: ink[100],
        200: ink[200],
        300: ink[300],
        400: ink[400],
        500: ink[500],
        700: ink[700],
        900: ink[900],
      },
    },
    shape: { borderRadius: layout.radius },
    typography: {
      fontFamily,
      htmlFontSize: 16,
      fontSize: 14,
      h1: { fontSize: '1.875rem', fontWeight: 650, lineHeight: 1.25, letterSpacing: '-0.015em' },
      h2: { fontSize: '1.625rem', fontWeight: 650, lineHeight: 1.25, letterSpacing: '-0.015em' },
      h3: { fontSize: '1.5rem', fontWeight: 600, lineHeight: 1.3, letterSpacing: '-0.01em' },
      // Page titles across the app use h4.
      h4: { fontSize: '1.5rem', fontWeight: 600, lineHeight: 1.3, letterSpacing: '-0.01em' },
      h5: { fontSize: '1.25rem', fontWeight: 600, lineHeight: 1.35, letterSpacing: '-0.005em' },
      // Card and section titles.
      h6: { fontSize: '1rem', fontWeight: 600, lineHeight: 1.4 },
      subtitle1: { fontSize: '0.9375rem', fontWeight: 500, lineHeight: 1.5 },
      subtitle2: { fontSize: '0.8125rem', fontWeight: 600, lineHeight: 1.5 },
      body1: { fontSize: '0.875rem', lineHeight: 1.55 },
      body2: { fontSize: '0.8125rem', lineHeight: 1.5 },
      caption: { fontSize: '0.75rem', lineHeight: 1.45 },
      overline: { fontSize: '0.6875rem', fontWeight: 600, letterSpacing: '0.07em', lineHeight: 1.6 },
      button: { textTransform: 'none', fontWeight: 600, fontSize: '0.875rem', letterSpacing: 0 },
    },
  };

  const cardShadow = isDark ? 'none' : '0 1px 2px rgba(14, 27, 38, 0.04)';
  const menuShadow = isDark
    ? '0 8px 24px rgba(0,0,0,0.45)'
    : '0 8px 24px rgba(14, 27, 38, 0.10), 0 2px 6px rgba(14, 27, 38, 0.06)';

  // Component defaults. Kept as a plain object so the type checker does not have to compare it
  // against MUI's full component typings (that comparison is very slow with TypeScript 4.9).
  const overrides: Record<string, unknown> = {
    components: {
      MuiCssBaseline: {
        styleOverrides: {
          body: {
            backgroundColor: pageBackground,
            WebkitFontSmoothing: 'antialiased',
            MozOsxFontSmoothing: 'grayscale',
            fontFeatureSettings: '"tnum" 0',
          },
          '::selection': { backgroundColor: alpha(brand.amber, 0.35) },
          // One visible keyboard focus style for anything focusable.
          ':focus-visible': { outline: `2px solid ${focusRing}`, outlineOffset: 2 },
          a: { color: primaryMain, textUnderlineOffset: '2px' },
        },
      },
      MuiButtonBase: {
        defaultProps: { disableRipple: false },
        styleOverrides: {
          root: {
            '&.Mui-focusVisible': { outline: `2px solid ${focusRing}`, outlineOffset: 2 },
          },
        },
      },
      MuiButton: {
        defaultProps: { disableElevation: true },
        styleOverrides: {
          root: {
            borderRadius: layout.radius,
            padding: '7px 16px',
            minHeight: 36,
            fontWeight: 600,
            whiteSpace: 'nowrap',
          },
          sizeSmall: { padding: '4px 12px', minHeight: 30, fontSize: '0.8125rem' },
          sizeLarge: { padding: '10px 22px', minHeight: 44, fontSize: '0.9375rem' },
          containedPrimary: {
            backgroundColor: brand.amber,
            color: brand.onAmber,
            '&:hover': { backgroundColor: brand.amberHover },
            '&.Mui-disabled': { backgroundColor: alpha(brand.amber, 0.4), color: alpha(brand.onAmber, 0.5) },
          },
          outlined: {
            borderColor: isDark ? dark.border : ink[300],
            color: textPrimary,
            backgroundColor: paper,
            '&:hover': { borderColor: isDark ? 'rgba(255,255,255,0.24)' : ink[400], backgroundColor: subtle },
          },
          outlinedError: { color: status.error.text, borderColor: alpha(status.error.main, 0.5) },
          text: { color: textPrimary, '&:hover': { backgroundColor: hoverBg } },
          textError: { color: status.error.text },
          textPrimary: { color: textPrimary },
        },
      },
      MuiIconButton: {
        styleOverrides: {
          root: { borderRadius: layout.radius, color: textSecondary },
          colorPrimary: { color: primaryMain },
          colorError: { color: status.error.main },
        },
      },
      MuiFab: {
        styleOverrides: {
          primary: {
            backgroundColor: brand.amber,
            color: brand.onAmber,
            '&:hover': { backgroundColor: brand.amberHover },
          },
        },
      },
      MuiPaper: {
        defaultProps: { elevation: 0 },
        styleOverrides: {
          root: { backgroundImage: 'none' },
          outlined: { borderColor: divider },
          elevation0: { border: `1px solid ${divider}`, boxShadow: cardShadow },
          elevation1: { border: `1px solid ${divider}`, boxShadow: cardShadow },
          elevation2: { border: `1px solid ${divider}`, boxShadow: cardShadow },
          elevation3: { border: `1px solid ${divider}`, boxShadow: cardShadow },
          rounded: { borderRadius: layout.radiusCard },
        },
      },
      MuiCard: {
        defaultProps: { elevation: 0 },
        styleOverrides: {
          root: {
            borderRadius: layout.radiusCard,
            border: `1px solid ${divider}`,
            boxShadow: cardShadow,
          },
        },
      },
      MuiCardContent: {
        styleOverrides: { root: { padding: 20, '&:last-child': { paddingBottom: 20 } } },
      },
      MuiCardHeader: {
        styleOverrides: {
          root: { padding: '16px 20px' },
          title: { fontSize: '1rem', fontWeight: 600 },
          subheader: { fontSize: '0.8125rem' },
        },
      },
      MuiAppBar: {
        defaultProps: { elevation: 0, color: 'inherit' },
        styleOverrides: {
          root: {
            backgroundImage: 'none',
            backgroundColor: paper,
            color: textPrimary,
            borderBottom: `1px solid ${divider}`,
            boxShadow: 'none',
          },
        },
      },
      MuiDrawer: {
        styleOverrides: { paper: { backgroundImage: 'none', borderColor: divider } },
      },
      MuiDialog: {
        styleOverrides: {
          paper: { borderRadius: layout.radiusCard, border: 'none', boxShadow: menuShadow },
        },
      },
      MuiDialogTitle: {
        styleOverrides: { root: { fontSize: '1.125rem', fontWeight: 600, padding: '20px 24px 12px' } },
      },
      MuiDialogContent: { styleOverrides: { root: { padding: '12px 24px' } } },
      MuiDialogActions: {
        styleOverrides: { root: { padding: '12px 24px 20px', gap: 8, '& > :not(style) ~ :not(style)': { marginLeft: 0 } } },
      },
      MuiMenu: {
        styleOverrides: {
          paper: { borderRadius: layout.radius, border: `1px solid ${divider}`, boxShadow: menuShadow },
        },
      },
      MuiPopover: {
        styleOverrides: { paper: { boxShadow: menuShadow } },
      },
      MuiMenuItem: {
        styleOverrides: { root: { fontSize: '0.875rem', minHeight: 36, borderRadius: 6, margin: '0 4px' } },
      },
      MuiTooltip: {
        styleOverrides: {
          tooltip: {
            backgroundColor: isDark ? '#E8EDF2' : ink[900],
            color: isDark ? ink[900] : '#FFFFFF',
            fontSize: '0.75rem',
            fontWeight: 500,
            padding: '6px 10px',
            borderRadius: 6,
          },
          arrow: { color: isDark ? '#E8EDF2' : ink[900] },
        },
      },
      MuiTextField: { defaultProps: { size: 'small' } },
      // Date pickers render their own text field; keep them the same height as other inputs.
      MuiDatePicker: { defaultProps: { slotProps: { textField: { size: 'small' } } } },
      MuiDateTimePicker: { defaultProps: { slotProps: { textField: { size: 'small' } } } },
      MuiPickersTextField: { defaultProps: { size: 'small' } },
      MuiFormControl: { defaultProps: { size: 'small' } },
      MuiAutocomplete: { defaultProps: { size: 'small' } },
      MuiOutlinedInput: {
        styleOverrides: {
          root: {
            borderRadius: layout.radius,
            backgroundColor: isDark ? dark.raised : '#FFFFFF',
            '& .MuiOutlinedInput-notchedOutline': { borderColor: isDark ? 'rgba(255,255,255,0.18)' : ink[400] },
            '&:hover:not(.Mui-disabled) .MuiOutlinedInput-notchedOutline': { borderColor: textPrimary },
            '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
              borderColor: focusRing,
              borderWidth: 2,
            },
            '&.Mui-disabled': { backgroundColor: subtle },
          },
          input: { '&::placeholder': { color: textSecondary, opacity: 1 } },
        },
      },
      MuiInputLabel: {
        styleOverrides: {
          root: { color: textSecondary, '&.Mui-focused': { color: isDark ? brand.amber : brand.amberText } },
        },
      },
      MuiFormHelperText: { styleOverrides: { root: { marginLeft: 2, fontSize: '0.75rem' } } },
      MuiCheckbox: {
        styleOverrides: { root: { color: isDark ? dark.textSecondary : ink[400] } },
      },
      MuiRadio: {
        styleOverrides: { root: { color: isDark ? dark.textSecondary : ink[400] } },
      },
      MuiChip: {
        styleOverrides: {
          root: ({ ownerState }: { ownerState: { color?: string; variant?: string } }) => {
            const tone = softTone(ownerState.color, isDark);
            const common = {
              borderRadius: 6,
              fontWeight: 600,
              fontSize: '0.75rem',
              height: 24,
            };
            if (ownerState.variant === 'outlined') {
              return {
                ...common,
                borderColor: isDark ? dark.border : ink[200],
                color: tone && ownerState.color && ownerState.color !== 'default' ? tone.text : textPrimary,
                backgroundColor: paper,
                fontWeight: 500,
              };
            }
            return tone
              ? {
                  ...common,
                  backgroundColor: tone.bg,
                  color: tone.text,
                  '&.MuiChip-clickable:hover': { backgroundColor: alpha(tone.text, 0.14) },
                  '& .MuiChip-icon': { color: 'inherit' },
                  '& .MuiChip-deleteIcon': { color: alpha(tone.text, 0.6) },
                }
              : common;
          },
          sizeMedium: { height: 28, fontSize: '0.8125rem' },
          label: { paddingLeft: 8, paddingRight: 8 },
          icon: { fontSize: 16, marginLeft: 6 },
        },
      },
      MuiBadge: { styleOverrides: { badge: { fontWeight: 700, fontSize: '0.6875rem' } } },
      MuiAvatar: {
        styleOverrides: {
          root: { fontWeight: 600, fontSize: '0.8125rem' },
          colorDefault: {
            backgroundColor: isDark ? dark.raised : brand.amberTint2,
            color: isDark ? brand.amber : brand.amberText,
          },
        },
      },
      MuiTabs: {
        styleOverrides: {
          root: { minHeight: 44, borderBottom: `1px solid ${divider}` },
          indicator: { height: 2, borderRadius: 2, backgroundColor: isDark ? brand.amber : brand.amberStrong },
        },
      },
      MuiTab: {
        styleOverrides: {
          root: {
            minHeight: 44,
            padding: '10px 14px',
            minWidth: 0,
            fontWeight: 500,
            fontSize: '0.875rem',
            color: textSecondary,
            '&.Mui-selected': { color: textPrimary, fontWeight: 600 },
          },
        },
      },
      MuiTableContainer: {
        styleOverrides: { root: { borderRadius: layout.radiusCard, position: 'relative' } },
      },
      MuiTableHead: {
        styleOverrides: {
          root: {
            '& .MuiTableCell-head': {
              backgroundColor: subtle,
              color: textSecondary,
              fontSize: '0.75rem',
              fontWeight: 600,
              letterSpacing: '0.02em',
              lineHeight: 1.3,
              paddingTop: 10,
              paddingBottom: 10,
              whiteSpace: 'nowrap',
            },
          },
        },
      },
      MuiTableCell: {
        styleOverrides: {
          root: { borderBottom: `1px solid ${divider}`, fontSize: '0.8125rem', padding: '11px 14px' },
          sizeSmall: { padding: '8px 12px' },
        },
      },
      MuiTableRow: {
        styleOverrides: {
          root: {
            '&.MuiTableRow-hover:hover': { backgroundColor: isDark ? 'rgba(255,255,255,0.03)' : ink[25] },
            '&:last-child td, &:last-child th': { borderBottom: 0 },
          },
        },
      },
      MuiTablePagination: {
        styleOverrides: {
          root: { borderTop: `1px solid ${divider}` },
          toolbar: { minHeight: 48 },
          selectLabel: { fontSize: '0.8125rem', color: textSecondary },
          displayedRows: { fontSize: '0.8125rem', color: textSecondary },
        },
      },
      MuiListItemButton: {
        styleOverrides: {
          root: {
            borderRadius: layout.radius,
            '&.Mui-selected': {
              backgroundColor: selectedBg,
              '&:hover': { backgroundColor: isDark ? alpha(brand.amber, 0.2) : brand.amberTint2 },
            },
          },
        },
      },
      MuiAlert: {
        styleOverrides: {
          root: { borderRadius: layout.radius, fontSize: '0.875rem', alignItems: 'center' },
          standardSuccess: { backgroundColor: isDark ? undefined : status.success.bg, color: isDark ? undefined : status.success.text },
          standardWarning: { backgroundColor: isDark ? undefined : status.warning.bg, color: isDark ? undefined : status.warning.text },
          standardError: { backgroundColor: isDark ? undefined : status.error.bg, color: isDark ? undefined : status.error.text },
          standardInfo: { backgroundColor: isDark ? undefined : status.info.bg, color: isDark ? undefined : status.info.text },
        },
      },
      MuiLinearProgress: {
        styleOverrides: {
          root: { borderRadius: 4, backgroundColor: isDark ? dark.raised : ink[100] },
          barColorPrimary: { backgroundColor: brand.amber },
        },
      },
      MuiCircularProgress: { defaultProps: { thickness: 4 } },
      MuiDivider: { styleOverrides: { root: { borderColor: divider } } },
      MuiSwitch: {
        styleOverrides: {
          switchBase: { '&.Mui-checked + .MuiSwitch-track': { opacity: 1 } },
          track: { backgroundColor: isDark ? '#3A4752' : ink[300], opacity: 1 },
        },
      },
      MuiSkeleton: {
        styleOverrides: { root: { backgroundColor: isDark ? dark.raised : ink[100] } },
      },
      MuiAccordion: {
        defaultProps: { elevation: 0, disableGutters: true },
        styleOverrides: { root: { border: `1px solid ${divider}`, '&:before': { display: 'none' } } },
      },
    },
  };

  // Passing plain option objects (not a built Theme) keeps type checking cheap.
  return createTheme(options, overrides);
};

export default createAppTheme;
