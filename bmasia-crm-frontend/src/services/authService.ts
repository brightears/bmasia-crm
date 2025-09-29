import axios, { AxiosResponse } from 'axios';
import { LoginCredentials, AuthResponse, RefreshTokenResponse, User, JWTPayload } from '../types';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'https://bmasia-crm.onrender.com';

/**
 * JWT Token Management Service
 * Handles secure storage and management of JWT tokens
 */
class AuthService {
  private readonly ACCESS_TOKEN_KEY = 'bmasia_access_token';
  private readonly REFRESH_TOKEN_KEY = 'bmasia_refresh_token';
  private readonly USER_KEY = 'bmasia_user';
  private readonly REMEMBER_ME_KEY = 'bmasia_remember_me';

  private api = axios.create({
    baseURL: `${API_BASE_URL}/api/v1`,
    headers: {
      'Content-Type': 'application/json',
    },
  });

  constructor() {
    this.setupInterceptors();
  }

  /**
   * Setup axios interceptors for automatic token handling
   */
  private setupInterceptors(): void {
    // Request interceptor to add access token
    this.api.interceptors.request.use(
      (config) => {
        const token = this.getAccessToken();
        if (token && !this.isTokenExpired(token)) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor for token refresh
    this.api.interceptors.response.use(
      (response) => response,
      async (error) => {
        const originalRequest = error.config;

        if (error.response?.status === 401 && !originalRequest._retry) {
          originalRequest._retry = true;

          try {
            await this.refreshToken();
            const newToken = this.getAccessToken();
            if (newToken) {
              originalRequest.headers.Authorization = `Bearer ${newToken}`;
              return this.api(originalRequest);
            }
          } catch (refreshError) {
            this.clearAuthData();
            window.location.href = '/login';
            return Promise.reject(refreshError);
          }
        }

        return Promise.reject(error);
      }
    );
  }

  /**
   * Authenticate user with credentials
   */
  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    try {
      const response: AxiosResponse<AuthResponse> = await this.api.post('/auth/login/', credentials);
      const { access, refresh, user } = response.data;

      // Store tokens based on remember me preference
      const storage = credentials.remember_me ? localStorage : sessionStorage;

      storage.setItem(this.ACCESS_TOKEN_KEY, access);
      storage.setItem(this.REFRESH_TOKEN_KEY, refresh);
      storage.setItem(this.USER_KEY, JSON.stringify(user));

      if (credentials.remember_me) {
        localStorage.setItem(this.REMEMBER_ME_KEY, 'true');
      }

      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Login failed');
    }
  }

  /**
   * Logout user and clear all auth data
   */
  async logout(): Promise<void> {
    try {
      const refreshToken = this.getRefreshToken();
      if (refreshToken) {
        await this.api.post('/auth/logout/', { refresh: refreshToken });
      }
    } catch (error) {
      // Continue with logout even if API call fails
      console.error('Logout API error:', error);
    } finally {
      this.clearAuthData();
    }
  }

  /**
   * Refresh access token using refresh token
   */
  async refreshToken(): Promise<string> {
    const refreshToken = this.getRefreshToken();
    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    try {
      const response: AxiosResponse<RefreshTokenResponse> = await this.api.post('/auth/refresh/', {
        refresh: refreshToken
      });

      const { access } = response.data;
      const storage = this.isRememberMeEnabled() ? localStorage : sessionStorage;
      storage.setItem(this.ACCESS_TOKEN_KEY, access);

      return access;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Token refresh failed');
    }
  }

  /**
   * Get current user info from API
   */
  async getCurrentUser(): Promise<User> {
    try {
      const response: AxiosResponse<User> = await this.api.get('/auth/me/');
      const storage = this.isRememberMeEnabled() ? localStorage : sessionStorage;
      storage.setItem(this.USER_KEY, JSON.stringify(response.data));
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Failed to fetch user info');
    }
  }

  /**
   * Get stored access token
   */
  getAccessToken(): string | null {
    return localStorage.getItem(this.ACCESS_TOKEN_KEY) ||
           sessionStorage.getItem(this.ACCESS_TOKEN_KEY);
  }

  /**
   * Get stored refresh token
   */
  getRefreshToken(): string | null {
    return localStorage.getItem(this.REFRESH_TOKEN_KEY) ||
           sessionStorage.getItem(this.REFRESH_TOKEN_KEY);
  }

  /**
   * Get stored user data
   */
  getStoredUser(): User | null {
    try {
      const userStr = localStorage.getItem(this.USER_KEY) ||
                      sessionStorage.getItem(this.USER_KEY);
      return userStr ? JSON.parse(userStr) : null;
    } catch (error) {
      console.error('Error parsing stored user data:', error);
      return null;
    }
  }

  /**
   * Check if remember me is enabled
   */
  isRememberMeEnabled(): boolean {
    return localStorage.getItem(this.REMEMBER_ME_KEY) === 'true';
  }

  /**
   * Decode JWT token payload
   */
  decodeToken(token: string): JWTPayload | null {
    try {
      const base64Url = token.split('.')[1];
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
      const jsonPayload = decodeURIComponent(
        atob(base64)
          .split('')
          .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
          .join('')
      );
      return JSON.parse(jsonPayload);
    } catch (error) {
      console.error('Error decoding token:', error);
      return null;
    }
  }

  /**
   * Check if token is expired
   */
  isTokenExpired(token?: string): boolean {
    const tokenToCheck = token || this.getAccessToken();
    if (!tokenToCheck) return true;

    const payload = this.decodeToken(tokenToCheck);
    if (!payload) return true;

    // Add 5 minute buffer for token refresh
    const now = Date.now() / 1000;
    return payload.exp < (now + 300);
  }

  /**
   * Get token expiry timestamp
   */
  getTokenExpiry(): number | null {
    const token = this.getAccessToken();
    if (!token) return null;

    const payload = this.decodeToken(token);
    return payload?.exp ? payload.exp * 1000 : null;
  }

  /**
   * Check if user is authenticated
   */
  isAuthenticated(): boolean {
    const token = this.getAccessToken();
    const user = this.getStoredUser();
    return !!(token && user && !this.isTokenExpired(token));
  }

  /**
   * Clear all authentication data
   */
  clearAuthData(): void {
    // Clear from both localStorage and sessionStorage
    [localStorage, sessionStorage].forEach(storage => {
      storage.removeItem(this.ACCESS_TOKEN_KEY);
      storage.removeItem(this.REFRESH_TOKEN_KEY);
      storage.removeItem(this.USER_KEY);
    });
    localStorage.removeItem(this.REMEMBER_ME_KEY);
  }

  /**
   * Set up automatic token refresh before expiry
   */
  scheduleTokenRefresh(): void {
    const token = this.getAccessToken();
    if (!token) return;

    const payload = this.decodeToken(token);
    if (!payload) return;

    // Schedule refresh 5 minutes before expiry
    const now = Date.now() / 1000;
    const timeUntilRefresh = (payload.exp - now - 300) * 1000;

    if (timeUntilRefresh > 0) {
      setTimeout(async () => {
        try {
          await this.refreshToken();
          this.scheduleTokenRefresh(); // Schedule next refresh
        } catch (error) {
          console.error('Scheduled token refresh failed:', error);
          this.clearAuthData();
          window.location.href = '/login';
        }
      }, timeUntilRefresh);
    }
  }
}

export default new AuthService();