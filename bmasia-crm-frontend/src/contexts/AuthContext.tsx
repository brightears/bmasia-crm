import React, { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';
import { AuthContextType, AuthState, LoginCredentials } from '../types';
import AuthService from '../services/authService';
import { hasPermission, hasRole } from '../utils/permissions';


const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [authState, setAuthState] = useState<AuthState>({
    user: null,
    accessToken: null,
    refreshToken: null,
    isAuthenticated: false,
    loading: true,
    tokenExpiry: null,
  });

  // Initialize auth state from stored data
  useEffect(() => {
    const initializeAuth = async () => {
      try {
        const accessToken = AuthService.getAccessToken();
        const refreshToken = AuthService.getRefreshToken();
        const storedUser = AuthService.getStoredUser();

        if (accessToken && refreshToken && storedUser) {
          // Check if token is expired
          if (AuthService.isTokenExpired(accessToken)) {
            try {
              // Try to refresh the token
              await AuthService.refreshToken();
              const newAccessToken = AuthService.getAccessToken();

              setAuthState({
                user: storedUser,
                accessToken: newAccessToken,
                refreshToken,
                isAuthenticated: true,
                loading: false,
                tokenExpiry: AuthService.getTokenExpiry(),
              });

              // Schedule next refresh
              AuthService.scheduleTokenRefresh();
            } catch (error) {
              console.error('Token refresh failed during initialization:', error);
              AuthService.clearAuthData();
              setAuthState(prev => ({ ...prev, loading: false }));
            }
          } else {
            // Token is still valid
            setAuthState({
              user: storedUser,
              accessToken,
              refreshToken,
              isAuthenticated: true,
              loading: false,
              tokenExpiry: AuthService.getTokenExpiry(),
            });

            // Schedule token refresh
            AuthService.scheduleTokenRefresh();
          }
        } else {
          // No valid auth data found
          setAuthState(prev => ({ ...prev, loading: false }));
        }
      } catch (error) {
        console.error('Auth initialization error:', error);
        AuthService.clearAuthData();
        setAuthState(prev => ({ ...prev, loading: false }));
      }
    };

    initializeAuth();
  }, []);

  const login = useCallback(async (credentials: LoginCredentials) => {
    try {
      console.log('AuthContext: Starting login process...');
      setAuthState(prev => ({ ...prev, loading: true }));

      const response = await AuthService.login(credentials);
      console.log('AuthContext: Login successful, setting auth state...');

      setAuthState({
        user: response.user,
        accessToken: response.access,
        refreshToken: response.refresh,
        isAuthenticated: true,
        loading: false,
        tokenExpiry: AuthService.getTokenExpiry(),
      });

      // Schedule automatic token refresh
      AuthService.scheduleTokenRefresh();
      console.log('AuthContext: Auth state updated successfully');
    } catch (error) {
      console.error('AuthContext: Login error:', error);
      setAuthState(prev => ({ ...prev, loading: false }));
      throw error;
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await AuthService.logout();
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      setAuthState({
        user: null,
        accessToken: null,
        refreshToken: null,
        isAuthenticated: false,
        loading: false,
        tokenExpiry: null,
      });
    }
  }, []);

  const refreshAccessToken = useCallback(async () => {
    try {
      const newAccessToken = await AuthService.refreshToken();
      setAuthState(prev => ({
        ...prev,
        accessToken: newAccessToken,
        tokenExpiry: AuthService.getTokenExpiry(),
      }));
    } catch (error) {
      console.error('Token refresh failed:', error);
      await logout();
      throw error;
    }
  }, [logout]);

  const hasPermissionCheck = useCallback((permission: string): boolean => {
    return hasPermission(authState.user, permission);
  }, [authState.user]);

  const hasRoleCheck = useCallback((role: string | string[]): boolean => {
    return hasRole(authState.user, role);
  }, [authState.user]);

  const isTokenExpired = useCallback((): boolean => {
    return AuthService.isTokenExpired(authState.accessToken || undefined);
  }, [authState.accessToken]);

  const value: AuthContextType = {
    ...authState,
    login,
    logout,
    refreshAccessToken,
    hasPermission: hasPermissionCheck,
    hasRole: hasRoleCheck,
    isTokenExpired,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};