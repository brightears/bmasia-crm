/**
 * BMAsia CRM design tokens.
 *
 * Brand colours come from the public BMAsia website (amber #EFA634, deep navy surfaces,
 * Beat Breeze teal, Soundtrack lavender). Text and status colours are chosen so that
 * text on its background reaches WCAG AA (4.5:1) and UI outlines reach 3:1.
 */

export const brand = {
  amber: '#EFA634', // logo / primary button fill (use dark text on it: 9:1)
  amberHover: '#E2972A',
  amberStrong: '#A86A12', // amber for text, icons and outlines on white (4.4:1)
  amberText: '#8F560A', // amber text on tinted amber backgrounds (5.9:1)
  amberTint: '#FEF6E7', // selected / highlighted backgrounds
  amberTint2: '#FCEBCB',
  onAmber: '#101417',
  navy: '#0B1722', // deep navy from the website, used for dark mode and accents
} as const;

export const ink = {
  900: '#0E1B26', // headings, primary text (16:1)
  700: '#2F3D4A', // body text
  500: '#5B6874', // secondary text (5.7:1)
  400: '#8B97A3', // input borders, placeholder icons (3:1)
  300: '#C3CBD3',
  200: '#E3E7EB', // dividers, card borders
  100: '#EEF0F3',
  50: '#F5F6F8', // page background
  25: '#F9FAFB', // table header, subtle panels
} as const;

/** Product accents (from the website's product pages). Dark text is used on both. */
export const product = {
  beatbreeze: { bg: '#DDF6F3', fg: '#0E5E57', solid: '#49D5C5' },
  soundtrack: { bg: '#EFE7FF', fg: '#5B3A99', solid: '#D6C2FF' },
} as const;

/** Soft status colours: tinted background + dark text, all at least 4.8:1. */
export const status = {
  success: { main: '#1E8A57', text: '#1B6B44', bg: '#E6F4EC' },
  warning: { main: '#B86E00', text: '#9A5B00', bg: '#FDF1DE' },
  error: { main: '#C4321F', text: '#B42318', bg: '#FDECEA' },
  info: { main: '#1F65B8', text: '#1F5FAF', bg: '#E8F0FB' },
  neutral: { main: '#5B6874', text: '#4A5561', bg: '#EEF0F3' },
} as const;

export const dark = {
  background: '#0B141C',
  paper: '#111D27',
  raised: '#16242F',
  border: 'rgba(255,255,255,0.09)',
  text: '#E8EDF2',
  textSecondary: '#9AA6B2',
} as const;

export const fontFamily =
  '"Geist", "Inter", system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';

/** Layout constants shared by the shell and page patterns (px). */
export const layout = {
  sidebarWidth: 248,
  sidebarCollapsedWidth: 68,
  topBarHeight: 60,
  pagePaddingX: { xs: 16, md: 32 },
  pageMaxWidth: 1440,
  radius: 8,
  radiusCard: 12,
} as const;
