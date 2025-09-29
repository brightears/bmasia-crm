import axios from 'axios';
import {
  User, Company, Contact, Note, Task, Opportunity, OpportunityActivity,
  Contract, Invoice, DashboardStats, AuditLog, ApiResponse
} from '../types';
import AuthService from './authService';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'https://bmasia-crm.onrender.com';

class ApiService {
  private api = axios.create({
    baseURL: `${API_BASE_URL}/api/v1`,
    headers: {
      'Content-Type': 'application/json',
    },
  });

  constructor() {
    // Add token to requests
    this.api.interceptors.request.use((config) => {
      const token = AuthService.getAccessToken();
      if (token && !AuthService.isTokenExpired(token)) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });

    // Handle unauthorized responses with token refresh
    this.api.interceptors.response.use(
      (response) => response,
      async (error) => {
        const originalRequest = error.config;

        if (error.response?.status === 401 && !originalRequest._retry) {
          originalRequest._retry = true;

          try {
            await AuthService.refreshToken();
            const newToken = AuthService.getAccessToken();
            if (newToken) {
              originalRequest.headers.Authorization = `Bearer ${newToken}`;
              return this.api(originalRequest);
            }
          } catch (refreshError) {
            AuthService.clearAuthData();
            window.location.href = '/login';
            return Promise.reject(refreshError);
          }
        }

        if (error.response?.status === 403) {
          // Handle forbidden responses (insufficient permissions)
          console.error('Access forbidden:', error.response.data);
        }

        return Promise.reject(error);
      }
    );
  }

  // Note: Authentication methods moved to AuthService
  // This service now focuses on business data operations

  // Dashboard
  async getDashboardStats(): Promise<DashboardStats> {
    const response = await this.api.get<DashboardStats>('/dashboard/stats/');
    return response.data;
  }

  // Companies
  async getCompanies(params?: any): Promise<ApiResponse<Company>> {
    const response = await this.api.get<ApiResponse<Company>>('/companies/', { params });
    return response.data;
  }

  async getCompany(id: string): Promise<Company> {
    const response = await this.api.get<Company>(`/companies/${id}/`);
    return response.data;
  }

  async createCompany(data: Partial<Company>): Promise<Company> {
    const response = await this.api.post<Company>('/companies/', data);
    return response.data;
  }

  async updateCompany(id: string, data: Partial<Company>): Promise<Company> {
    const response = await this.api.put<Company>(`/companies/${id}/`, data);
    return response.data;
  }

  async deleteCompany(id: string): Promise<void> {
    await this.api.delete(`/companies/${id}/`);
  }

  async getCompanyDashboard(id: string): Promise<any> {
    const response = await this.api.get(`/companies/${id}/dashboard/`);
    return response.data;
  }

  // Contacts
  async getContacts(params?: any): Promise<ApiResponse<Contact>> {
    const response = await this.api.get<ApiResponse<Contact>>('/contacts/', { params });
    return response.data;
  }

  async getContact(id: string): Promise<Contact> {
    const response = await this.api.get<Contact>(`/contacts/${id}/`);
    return response.data;
  }

  async createContact(data: Partial<Contact>): Promise<Contact> {
    const response = await this.api.post<Contact>('/contacts/', data);
    return response.data;
  }

  async updateContact(id: string, data: Partial<Contact>): Promise<Contact> {
    const response = await this.api.put<Contact>(`/contacts/${id}/`, data);
    return response.data;
  }

  async deleteContact(id: string): Promise<void> {
    await this.api.delete(`/contacts/${id}/`);
  }

  // Notes
  async getNotes(params?: any): Promise<ApiResponse<Note>> {
    const response = await this.api.get<ApiResponse<Note>>('/notes/', { params });
    return response.data;
  }

  async createNote(data: Partial<Note>): Promise<Note> {
    const response = await this.api.post<Note>('/notes/', data);
    return response.data;
  }

  async updateNote(id: string, data: Partial<Note>): Promise<Note> {
    const response = await this.api.put<Note>(`/notes/${id}/`, data);
    return response.data;
  }

  async deleteNote(id: string): Promise<void> {
    await this.api.delete(`/notes/${id}/`);
  }

  // Tasks
  async getTasks(params?: any): Promise<ApiResponse<Task>> {
    const response = await this.api.get<ApiResponse<Task>>('/tasks/', { params });
    return response.data;
  }

  async getMyTasks(): Promise<Task[]> {
    const response = await this.api.get<Task[]>('/tasks/my_tasks/');
    return response.data;
  }

  async getOverdueTasks(): Promise<Task[]> {
    const response = await this.api.get<Task[]>('/tasks/overdue/');
    return response.data;
  }

  async getTask(id: string): Promise<Task> {
    const response = await this.api.get<Task>(`/tasks/${id}/`);
    return response.data;
  }

  async createTask(data: Partial<Task>): Promise<Task> {
    const response = await this.api.post<Task>('/tasks/', data);
    return response.data;
  }

  async updateTask(id: string, data: Partial<Task>): Promise<Task> {
    const response = await this.api.put<Task>(`/tasks/${id}/`, data);
    return response.data;
  }

  async deleteTask(id: string): Promise<void> {
    await this.api.delete(`/tasks/${id}/`);
  }

  // Task Comments
  async addTaskComment(taskId: string, comment: string): Promise<any> {
    const response = await this.api.post(`/tasks/${taskId}/comments/`, { comment });
    return response.data;
  }

  async getTaskComments(taskId: string): Promise<any[]> {
    const response = await this.api.get(`/tasks/${taskId}/comments/`);
    return response.data;
  }

  // Task Subtasks
  async addTaskSubtask(taskId: string, title: string): Promise<any> {
    const response = await this.api.post(`/tasks/${taskId}/subtasks/`, { title });
    return response.data;
  }

  async updateTaskSubtask(taskId: string, subtaskId: string, data: any): Promise<any> {
    const response = await this.api.put(`/tasks/${taskId}/subtasks/${subtaskId}/`, data);
    return response.data;
  }

  async deleteTaskSubtask(taskId: string, subtaskId: string): Promise<void> {
    await this.api.delete(`/tasks/${taskId}/subtasks/${subtaskId}/`);
  }

  // Opportunities
  async getOpportunities(params?: any): Promise<ApiResponse<Opportunity>> {
    const response = await this.api.get<ApiResponse<Opportunity>>('/opportunities/', { params });
    return response.data;
  }

  async getOpportunity(id: string): Promise<Opportunity> {
    const response = await this.api.get<Opportunity>(`/opportunities/${id}/`);
    return response.data;
  }

  async createOpportunity(data: Partial<Opportunity>): Promise<Opportunity> {
    const response = await this.api.post<Opportunity>('/opportunities/', data);
    return response.data;
  }

  async updateOpportunity(id: string, data: Partial<Opportunity>): Promise<Opportunity> {
    const response = await this.api.put<Opportunity>(`/opportunities/${id}/`, data);
    return response.data;
  }

  async deleteOpportunity(id: string): Promise<void> {
    await this.api.delete(`/opportunities/${id}/`);
  }

  async getSalesPipeline(): Promise<any> {
    const response = await this.api.get('/opportunities/pipeline/');
    return response.data;
  }

  async advanceOpportunityStage(id: string): Promise<any> {
    const response = await this.api.post(`/opportunities/${id}/advance_stage/`);
    return response.data;
  }

  // Opportunity Activities
  async getOpportunityActivities(params?: any): Promise<ApiResponse<OpportunityActivity>> {
    const response = await this.api.get<ApiResponse<OpportunityActivity>>('/opportunity-activities/', { params });
    return response.data;
  }

  async getOpportunityActivity(id: string): Promise<OpportunityActivity> {
    const response = await this.api.get<OpportunityActivity>(`/opportunity-activities/${id}/`);
    return response.data;
  }

  async createOpportunityActivity(data: Partial<OpportunityActivity>): Promise<OpportunityActivity> {
    const response = await this.api.post<OpportunityActivity>('/opportunity-activities/', data);
    return response.data;
  }

  async updateOpportunityActivity(id: string, data: Partial<OpportunityActivity>): Promise<OpportunityActivity> {
    const response = await this.api.put<OpportunityActivity>(`/opportunity-activities/${id}/`, data);
    return response.data;
  }

  async deleteOpportunityActivity(id: string): Promise<void> {
    await this.api.delete(`/opportunity-activities/${id}/`);
  }

  async getActivitiesByOpportunity(opportunityId: string): Promise<OpportunityActivity[]> {
    const response = await this.api.get<OpportunityActivity[]>(`/opportunities/${opportunityId}/activities/`);
    return response.data;
  }

  async getActivitiesByContact(contactId: string): Promise<OpportunityActivity[]> {
    const response = await this.api.get<OpportunityActivity[]>(`/contacts/${contactId}/activities/`);
    return response.data;
  }

  // Contracts
  async getContracts(params?: any): Promise<ApiResponse<Contract>> {
    const response = await this.api.get<ApiResponse<Contract>>('/contracts/', { params });
    return response.data;
  }

  async getContract(id: string): Promise<Contract> {
    const response = await this.api.get<Contract>(`/contracts/${id}/`);
    return response.data;
  }

  async getExpiringContracts(): Promise<Contract[]> {
    const response = await this.api.get<Contract[]>('/contracts/expiring_soon/');
    return response.data;
  }

  async createContract(data: Partial<Contract>): Promise<Contract> {
    const response = await this.api.post<Contract>('/contracts/', data);
    return response.data;
  }

  async updateContract(id: string, data: Partial<Contract>): Promise<Contract> {
    const response = await this.api.put<Contract>(`/contracts/${id}/`, data);
    return response.data;
  }

  async sendRenewalNotice(id: string): Promise<any> {
    const response = await this.api.post(`/contracts/${id}/send_renewal_notice/`);
    return response.data;
  }

  // Invoices
  async getInvoices(params?: any): Promise<ApiResponse<Invoice>> {
    const response = await this.api.get<ApiResponse<Invoice>>('/invoices/', { params });
    return response.data;
  }

  async getInvoice(id: string): Promise<Invoice> {
    const response = await this.api.get<Invoice>(`/invoices/${id}/`);
    return response.data;
  }

  async createInvoice(data: Partial<Invoice>): Promise<Invoice> {
    const response = await this.api.post<Invoice>('/invoices/', data);
    return response.data;
  }

  async updateInvoice(id: string, data: Partial<Invoice>): Promise<Invoice> {
    const response = await this.api.put<Invoice>(`/invoices/${id}/`, data);
    return response.data;
  }

  async deleteInvoice(id: string): Promise<void> {
    await this.api.delete(`/invoices/${id}/`);
  }

  async getOverdueInvoices(): Promise<Invoice[]> {
    const response = await this.api.get<Invoice[]>('/invoices/overdue/');
    return response.data;
  }

  async markInvoicePaid(id: string, data?: { payment_method?: string; transaction_id?: string; notes?: string }): Promise<any> {
    const response = await this.api.post(`/invoices/${id}/mark_paid/`, data);
    return response.data;
  }

  async sendInvoice(id: string, email?: string): Promise<any> {
    const response = await this.api.post(`/invoices/${id}/send/`, { email });
    return response.data;
  }

  async downloadInvoicePDF(id: string): Promise<Blob> {
    const response = await this.api.get(`/invoices/${id}/pdf/`, {
      responseType: 'blob'
    });
    return response.data;
  }

  async addInvoicePayment(invoiceId: string, data: Partial<any>): Promise<any> {
    const response = await this.api.post(`/invoices/${invoiceId}/payments/`, data);
    return response.data;
  }

  async getInvoiceStats(): Promise<any> {
    const response = await this.api.get('/invoices/stats/');
    return response.data;
  }

  // Users
  async getUsers(params?: any): Promise<ApiResponse<User>> {
    const response = await this.api.get<ApiResponse<User>>('/users/', { params });
    return response.data;
  }

  // Audit Logs
  async getAuditLogs(params?: any): Promise<ApiResponse<AuditLog>> {
    const response = await this.api.get<ApiResponse<AuditLog>>('/audit-logs/', { params });
    return response.data;
  }

  // Bulk Operations
  async bulkOperation(endpoint: string, action: string, ids: string[], data?: any): Promise<any> {
    const response = await this.api.post(`/${endpoint}/bulk_operations/`, {
      action,
      ids,
      data
    });
    return response.data;
  }

  // Export
  async exportData(endpoint: string, ids?: string[]): Promise<any> {
    const params: any = { action: 'export' };
    if (ids) {
      params.ids = ids;
    }
    const response = await this.api.post(`/${endpoint}/bulk_operations/`, params, {
      responseType: 'blob'
    });
    return response.data;
  }
}

const apiService = new ApiService();
export default apiService;