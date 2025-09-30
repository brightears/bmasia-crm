import axios, { AxiosResponse } from 'axios';
import { LoginCredentials, AuthResponse, RefreshTokenResponse, User, JWTPayload } from '../types';

// Log environment variables for debugging
console.log('=== Environment Variables ===');
console.log('process.env.REACT_APP_API_URL:', process.env.REACT_APP_API_URL);
console.log('process.env.REACT_APP_BYPASS_AUTH:', process.env.REACT_APP_BYPASS_AUTH);
console.log('process.env.NODE_ENV:', process.env.NODE_ENV);
console.log('============================\n');

const API_BASE_URL = process.env.REACT_APP_API_URL || 'https://bmasia-crm.onrender.com';
console.log('Using API_BASE_URL:', API_BASE_URL);

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
    withCredentials: false, // Ensure we don't send credentials by default
    timeout: 10000, // 10 second timeout
  });

  constructor() {
    console.log('=== AuthService Constructor ===');
    console.log('API_BASE_URL:', API_BASE_URL);
    console.log('Configured baseURL:', `${API_BASE_URL}/api/v1`);
    console.log('Axios defaults transformResponse:', this.api.defaults.transformResponse);
    console.log('Number of request interceptors:', this.api.interceptors.request['handlers']?.length || 0);
    console.log('Number of response interceptors:', this.api.interceptors.response['handlers']?.length || 0);
    console.log('===============================\n');
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

        // Construct full URL for logging
        const fullUrl = `${config.baseURL}${config.url}`;

        console.log('=== REQUEST INTERCEPTOR ===');
        console.log('Full URL:', fullUrl);
        console.log('Method:', config.method?.toUpperCase());
        console.log('Base URL:', config.baseURL);
        console.log('Endpoint:', config.url);
        console.log('Params:', config.params);
        console.log('Has Token:', !!token);

        if (token && !this.isTokenExpired(token)) {
          config.headers.Authorization = `Bearer ${token}`;
          console.log('Authorization Header (first 30 chars):', `${token.substring(0, 30)}...`);
        } else if (token) {
          console.log('Token exists but is EXPIRED');
        } else {
          console.log('No token available');
        }

        console.log('Request Headers:', JSON.stringify(config.headers, null, 2));
        console.log('========================\n');

        return config;
      },
      (error) => {
        console.error('=== REQUEST INTERCEPTOR ERROR ===');
        console.error('Error:', error);
        console.error('==================================\n');
        return Promise.reject(error);
      }
    );

    // Response interceptor for token refresh
    this.api.interceptors.response.use(
      (response) => {
        console.log('=== RESPONSE INTERCEPTOR (SUCCESS) ===');
        console.log('Status:', response.status);
        console.log('Status Text:', response.statusText);
        console.log('URL:', response.config.url);
        console.log('Response Headers:', JSON.stringify(response.headers, null, 2));
        console.log('Response Data Type:', typeof response.data);
        console.log('Response Data:', JSON.stringify(response.data, null, 2));

        // Check if data was transformed
        if (response.data && typeof response.data === 'object') {
          console.log('Response Data Keys:', Object.keys(response.data));
          if ('count' in response.data) {
            console.log('Has count property:', response.data.count);
          }
          if ('results' in response.data) {
            console.log('Has results property, length:', response.data.results?.length);
          }
        }
        console.log('======================================\n');

        return response;
      },
      async (error) => {
        console.error('=== RESPONSE INTERCEPTOR (ERROR) ===');

        if (error.response) {
          // Server responded with error status
          console.error('Error Status:', error.response.status);
          console.error('Error Status Text:', error.response.statusText);
          console.error('Error URL:', error.config?.url);
          console.error('Error Data:', JSON.stringify(error.response.data, null, 2));
          console.error('Error Headers:', JSON.stringify(error.response.headers, null, 2));
        } else if (error.request) {
          // Request was made but no response received
          console.error('No response received');
          console.error('Request:', error.request);
        } else {
          // Something else happened
          console.error('Error Message:', error.message);
        }
        console.error('Error Config:', JSON.stringify(error.config, null, 2));
        console.error('=====================================\n');

        const originalRequest = error.config;

        if (error.response?.status === 401 && !originalRequest._retry) {
          console.log('Attempting token refresh due to 401 error');
          originalRequest._retry = true;

          try {
            await this.refreshToken();
            const newToken = this.getAccessToken();
            if (newToken) {
              console.log('Token refreshed successfully, retrying request');
              originalRequest.headers.Authorization = `Bearer ${newToken}`;
              return this.api(originalRequest);
            }
          } catch (refreshError) {
            console.error('Token refresh failed, redirecting to login');
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
      console.error('Login request failed:', error);

      // Handle different error response formats
      let errorMessage = 'Login failed';
      if (error.response?.data) {
        const data = error.response.data;
        if (data.detail) {
          errorMessage = data.detail;
        } else if (data.non_field_errors && Array.isArray(data.non_field_errors)) {
          errorMessage = data.non_field_errors[0];
        } else if (data.message) {
          errorMessage = data.message;
        } else if (typeof data === 'string') {
          errorMessage = data;
        }
      } else if (error.message) {
        errorMessage = error.message;
      }

      throw new Error(errorMessage);
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

  /**
   * Get the shared axios instance with configured interceptors
   * This allows other services to use the same instance and benefit from automatic token handling
   */
  public getAxiosInstance() {
    console.log('AuthService: Providing shared axios instance');
    return this.api;
  }
}

const authService = new AuthService();
export default authService;

// Export the shared axios instance for use by other services
// This ensures all API calls use the same instance with token management
export const authApi = authService.getAxiosInstance();