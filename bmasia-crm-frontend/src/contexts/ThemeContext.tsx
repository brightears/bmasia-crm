import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { createTheme, ThemeProvider as MuiThemeProvider, Theme } from '@mui/material/styles';
import { CssBaseline } from '@mui/material';

interface ThemeContextType {
  darkMode: boolean;
  toggleDarkMode: () => void;
  departmentTheme: (role: string) => Theme;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

interface ThemeProviderProps {
  children: ReactNode;
}

// Department colors - Supports both new and legacy roles
const departmentColors: Record<string, { primary: string; light: string; dark: string }> = {
  Sales: {
    primary: '#1976d2',
    light: '#42a5f5',
    dark: '#1565c0',
  },
  Finance: {
    primary: '#0288d1',
    light: '#03a9f4',
    dark: '#01579b',
  },
  Tech: {
    primary: '#388e3c',
    light: '#66bb6a',
    dark: '#2e7d32',
  },
  Music: {
    primary: '#7b1fa2',
    light: '#ba68c8',
    dark: '#6a1b9a',
  },
  Admin: {
    primary: '#616161',
    light: '#9e9e9e',
    dark: '#424242',
  },
  // Legacy role support
  Marketing: {
    primary: '#7b1fa2',
    light: '#ba68c8',
    dark: '#6a1b9a',
  },
  'Tech Support': {
    primary: '#388e3c',
    light: '#66bb6a',
    dark: '#2e7d32',
  },
};

export const ThemeProvider: React.FC<ThemeProviderProps> = ({ children }) => {
  const [darkMode, setDarkMode] = useState(() => {
    const savedMode = localStorage.getItem('darkMode');
    return savedMode ? JSON.parse(savedMode) : false;
  });

  useEffect(() => {
    localStorage.setItem('darkMode', JSON.stringify(darkMode));
  }, [darkMode]);

  const toggleDarkMode = () => {
    setDarkMode(!darkMode);
  };

  const createDepartmentTheme = (role: string) => {
    const colors = departmentColors[role as keyof typeof departmentColors] || departmentColors.Admin;

    return createTheme({
      palette: {
        mode: darkMode ? 'dark' : 'light',
        primary: {
          main: colors.primary,
          light: colors.light,
          dark: colors.dark,
        },
        secondary: {
          main: '#ff6b6b',
        },
        background: {
          default: darkMode ? '#121212' : '#f8fafc',
          paper: darkMode ? '#1e1e1e' : '#ffffff',
        },
        text: {
          primary: darkMode ? '#ffffff' : '#333333',
          secondary: darkMode ? '#b3b3b3' : '#666666',
        },
      },
      typography: {
        fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
        h1: {
          fontWeight: 700,
          fontSize: '2.5rem',
        },
        h2: {
          fontWeight: 700,
          fontSize: '2rem',
        },
        h3: {
          fontWeight: 600,
          fontSize: '1.75rem',
        },
        h4: {
          fontWeight: 600,
          fontSize: '1.5rem',
        },
        h5: {
          fontWeight: 600,
          fontSize: '1.25rem',
        },
        h6: {
          fontWeight: 600,
          fontSize: '1rem',
        },
        body1: {
          fontSize: '0.875rem',
          lineHeight: 1.5,
        },
        body2: {
          fontSize: '0.75rem',
          lineHeight: 1.4,
        },
        button: {
          textTransform: 'none',
          fontWeight: 500,
        },
      },
      shape: {
        borderRadius: 8,
      },
      components: {
        MuiButton: {
          styleOverrides: {
            root: {
              borderRadius: 8,
              padding: '8px 16px',
              fontWeight: 500,
            },
            contained: {
              boxShadow: 'none',
              '&:hover': {
                boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
              },
            },
          },
        },
        MuiCard: {
          styleOverrides: {
            root: {
              borderRadius: 12,
              boxShadow: darkMode
                ? '0 2px 8px rgba(0,0,0,0.3)'
                : '0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.06)',
              border: `1px solid ${darkMode ? '#333' : 'rgba(0,0,0,0.06)'}`,
              transition: 'box-shadow 0.2s ease, transform 0.2s ease',
              '&:hover': {
                boxShadow: darkMode
                  ? '0 4px 12px rgba(0,0,0,0.4)'
                  : '0 2px 6px rgba(0,0,0,0.06), 0 8px 24px rgba(0,0,0,0.08)',
                transform: 'translateY(-1px)',
              },
            },
          },
        },
        MuiPaper: {
          styleOverrides: {
            root: {
              backgroundImage: 'none',
            },
          },
        },
        MuiDrawer: {
          styleOverrides: {
            paper: {
              backgroundImage: 'none',
            },
          },
        },
        MuiAppBar: {
          styleOverrides: {
            root: {
              backgroundImage: 'none',
            },
          },
        },
        MuiListItemButton: {
          styleOverrides: {
            root: {
              borderRadius: 8,
              margin: '2px 8px',
              '&.Mui-selected': {
                backgroundColor: `${colors.primary}20`,
                '&:hover': {
                  backgroundColor: `${colors.primary}30`,
                },
              },
            },
          },
        },
        MuiChip: {
          styleOverrides: {
            root: {
              borderRadius: 16,
            },
          },
        },
        MuiTextField: {
          styleOverrides: {
            root: {
              '& .MuiOutlinedInput-root': {
                borderRadius: 8,
              },
            },
          },
        },
        MuiDialog: {
          styleOverrides: {
            paper: {
              borderRadius: 12,
            },
          },
        },
        MuiMenu: {
          styleOverrides: {
            paper: {
              borderRadius: 8,
              border: `1px solid ${darkMode ? '#333' : '#e0e0e0'}`,
            },
          },
        },
      },
    });
  };

  const departmentTheme = (role: string) => createDepartmentTheme(role);

  const defaultTheme = createDepartmentTheme('Admin');

  const value: ThemeContextType = {
    darkMode,
    toggleDarkMode,
    departmentTheme,
  };

  return (
    <ThemeContext.Provider value={value}>
      <MuiThemeProvider theme={defaultTheme}>
        <CssBaseline />
        {children}
      </MuiThemeProvider>
    </ThemeContext.Provider>
  );
};

export const useThemeContext = (): ThemeContextType => {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error('useThemeContext must be used within a ThemeProvider');
  }
  return context;
};