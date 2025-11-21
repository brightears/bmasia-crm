import {
  User, Company, Contact, Note, Task, Opportunity, OpportunityActivity,
  Contract, Invoice, Quote, DashboardStats, AuditLog, ApiResponse
} from '../types';
import { authApi } from './authService';
import { MockApiService } from './mockData';

class ApiService {
  private useMockData = process.env.REACT_APP_BYPASS_AUTH === 'true' && process.env.NODE_ENV === 'development';

  constructor() {
    console.log('ApiService: Initialized using shared authApi axios instance');
    console.log('ApiService: Mock data mode:', this.useMockData);
  }

  // Note: Authentication methods are in AuthService
  // This service focuses on business data operations using the shared axios instance

  // Dashboard
  async getDashboardStats(): Promise<DashboardStats> {
    const response = await authApi.get<DashboardStats>('/dashboard/stats/');
    return response.data;
  }

  // Companies
  async getCompanies(params?: any): Promise<ApiResponse<Company>> {
    if (this.useMockData) {
      console.log('ApiService: Using mock data for companies');
      return MockApiService.getCompanies(params);
    }

    console.log('=== ApiService.getCompanies START ===');
    console.log('Params:', JSON.stringify(params, null, 2));
    console.log('authApi instance baseURL:', (authApi as any).defaults?.baseURL);
    console.log('Making request to endpoint: /companies/');

    try {
      const response = await authApi.get<ApiResponse<Company>>('/companies/', { params });

      console.log('=== ApiService.getCompanies RESPONSE ===');
      console.log('Response Status:', response.status);
      console.log('Response Status Text:', response.statusText);
      console.log('Response Data (raw):', JSON.stringify(response.data, null, 2));
      console.log('Response count:', response.data.count);
      console.log('Response results length:', response.data.results?.length || 0);

      if (response.data.results && response.data.results.length > 0) {
        console.log('First company:', JSON.stringify(response.data.results[0], null, 2));
      } else {
        console.warn('WARNING: Results array is empty!');
      }

      console.log('====================================\n');

      return response.data;
    } catch (error: any) {
      console.error('=== ApiService.getCompanies ERROR ===');
      console.error('Error:', error);
      console.error('Error message:', error.message);
      console.error('Error response:', error.response);
      console.error('=====================================\n');
      throw error;
    }
  }

  async getCompany(id: string): Promise<Company> {
    if (this.useMockData) {
      console.log('ApiService: Using mock data for company detail');
      return MockApiService.getCompany(id);
    }

    const response = await authApi.get<Company>(`/companies/${id}/`);
    return response.data;
  }

  async createCompany(data: Partial<Company>): Promise<Company> {
    if (this.useMockData) {
      console.log('ApiService: Using mock data for company creation');
      return MockApiService.createCompany(data);
    }

    const response = await authApi.post<Company>('/companies/', data);
    return response.data;
  }

  async updateCompany(id: string, data: Partial<Company>): Promise<Company> {
    if (this.useMockData) {
      console.log('ApiService: Using mock data for company update');
      return MockApiService.updateCompany(id, data);
    }

    const response = await authApi.put<Company>(`/companies/${id}/`, data);
    return response.data;
  }

  async deleteCompany(id: string): Promise<void> {
    await authApi.delete(`/companies/${id}/`);
  }

  async getCompanyDashboard(id: string): Promise<any> {
    const response = await authApi.get(`/companies/${id}/dashboard/`);
    return response.data;
  }

  // Contacts
  async getContacts(params?: any): Promise<ApiResponse<Contact>> {
    if (this.useMockData) {
      console.log('ApiService: Using mock data for contacts');
      return MockApiService.getContacts(params);
    }

    const response = await authApi.get<ApiResponse<Contact>>('/contacts/', { params });
    return response.data;
  }

  async getContact(id: string): Promise<Contact> {
    const response = await authApi.get<Contact>(`/contacts/${id}/`);
    return response.data;
  }

  async createContact(data: Partial<Contact>): Promise<Contact> {
    const response = await authApi.post<Contact>('/contacts/', data);
    return response.data;
  }

  async updateContact(id: string, data: Partial<Contact>): Promise<Contact> {
    const response = await authApi.put<Contact>(`/contacts/${id}/`, data);
    return response.data;
  }

  async deleteContact(id: string): Promise<void> {
    await authApi.delete(`/contacts/${id}/`);
  }

  // Notes
  async getNotes(params?: any): Promise<ApiResponse<Note>> {
    const response = await authApi.get<ApiResponse<Note>>('/notes/', { params });
    return response.data;
  }

  async createNote(data: Partial<Note>): Promise<Note> {
    const response = await authApi.post<Note>('/notes/', data);
    return response.data;
  }

  async updateNote(id: string, data: Partial<Note>): Promise<Note> {
    const response = await authApi.put<Note>(`/notes/${id}/`, data);
    return response.data;
  }

  async deleteNote(id: string): Promise<void> {
    await authApi.delete(`/notes/${id}/`);
  }

  // Tasks
  async getTasks(params?: any): Promise<ApiResponse<Task>> {
    const response = await authApi.get<ApiResponse<Task>>('/tasks/', { params });
    return response.data;
  }

  async getMyTasks(): Promise<Task[]> {
    const response = await authApi.get<Task[]>('/tasks/my_tasks/');
    return response.data;
  }

  async getOverdueTasks(): Promise<Task[]> {
    const response = await authApi.get<Task[]>('/tasks/overdue/');
    return response.data;
  }

  async getTask(id: string): Promise<Task> {
    const response = await authApi.get<Task>(`/tasks/${id}/`);
    return response.data;
  }

  async createTask(data: Partial<Task>): Promise<Task> {
    const response = await authApi.post<Task>('/tasks/', data);
    return response.data;
  }

  async updateTask(id: string, data: Partial<Task>): Promise<Task> {
    const response = await authApi.put<Task>(`/tasks/${id}/`, data);
    return response.data;
  }

  async deleteTask(id: string): Promise<void> {
    await authApi.delete(`/tasks/${id}/`);
  }

  // Task Comments
  async addTaskComment(taskId: string, comment: string): Promise<any> {
    const response = await authApi.post(`/tasks/${taskId}/comments/`, { comment });
    return response.data;
  }

  async getTaskComments(taskId: string): Promise<any[]> {
    const response = await authApi.get(`/tasks/${taskId}/comments/`);
    return response.data;
  }

  // Task Subtasks
  async addTaskSubtask(taskId: string, title: string): Promise<any> {
    const response = await authApi.post(`/tasks/${taskId}/subtasks/`, { title });
    return response.data;
  }

  async updateTaskSubtask(taskId: string, subtaskId: string, data: any): Promise<any> {
    const response = await authApi.put(`/tasks/${taskId}/subtasks/${subtaskId}/`, data);
    return response.data;
  }

  async deleteTaskSubtask(taskId: string, subtaskId: string): Promise<void> {
    await authApi.delete(`/tasks/${taskId}/subtasks/${subtaskId}/`);
  }

  // Opportunities
  async getOpportunities(params?: any): Promise<ApiResponse<Opportunity>> {
    if (this.useMockData) {
      console.log('ApiService: Using mock data for opportunities');
      return MockApiService.getOpportunities(params);
    }

    const response = await authApi.get<ApiResponse<Opportunity>>('/opportunities/', { params });
    return response.data;
  }

  async getOpportunity(id: string): Promise<Opportunity> {
    const response = await authApi.get<Opportunity>(`/opportunities/${id}/`);
    return response.data;
  }

  async createOpportunity(data: Partial<Opportunity>): Promise<Opportunity> {
    const response = await authApi.post<Opportunity>('/opportunities/', data);
    return response.data;
  }

  async updateOpportunity(id: string, data: Partial<Opportunity>): Promise<Opportunity> {
    const response = await authApi.put<Opportunity>(`/opportunities/${id}/`, data);
    return response.data;
  }

  async deleteOpportunity(id: string): Promise<void> {
    await authApi.delete(`/opportunities/${id}/`);
  }

  async getSalesPipeline(): Promise<any> {
    const response = await authApi.get('/opportunities/pipeline/');
    return response.data;
  }

  async advanceOpportunityStage(id: string): Promise<any> {
    const response = await authApi.post(`/opportunities/${id}/advance_stage/`);
    return response.data;
  }

  // Opportunity Activities
  async getOpportunityActivities(params?: any): Promise<ApiResponse<OpportunityActivity>> {
    const response = await authApi.get<ApiResponse<OpportunityActivity>>('/opportunity-activities/', { params });
    return response.data;
  }

  async getOpportunityActivity(id: string): Promise<OpportunityActivity> {
    const response = await authApi.get<OpportunityActivity>(`/opportunity-activities/${id}/`);
    return response.data;
  }

  async createOpportunityActivity(data: Partial<OpportunityActivity>): Promise<OpportunityActivity> {
    const response = await authApi.post<OpportunityActivity>('/opportunity-activities/', data);
    return response.data;
  }

  async updateOpportunityActivity(id: string, data: Partial<OpportunityActivity>): Promise<OpportunityActivity> {
    const response = await authApi.put<OpportunityActivity>(`/opportunity-activities/${id}/`, data);
    return response.data;
  }

  async deleteOpportunityActivity(id: string): Promise<void> {
    await authApi.delete(`/opportunity-activities/${id}/`);
  }

  async getActivitiesByOpportunity(opportunityId: string): Promise<OpportunityActivity[]> {
    const response = await authApi.get<OpportunityActivity[]>(`/opportunities/${opportunityId}/activities/`);
    return response.data;
  }

  async getActivitiesByContact(contactId: string): Promise<OpportunityActivity[]> {
    const response = await authApi.get<OpportunityActivity[]>(`/contacts/${contactId}/activities/`);
    return response.data;
  }

  // Contracts
  async getContracts(params?: any): Promise<ApiResponse<Contract>> {
    if (this.useMockData) {
      console.log('ApiService: Using mock data for contracts');
      return MockApiService.getContracts(params);
    }

    const response = await authApi.get<ApiResponse<Contract>>('/contracts/', { params });
    return response.data;
  }

  async getContract(id: string): Promise<Contract> {
    const response = await authApi.get<Contract>(`/contracts/${id}/`);
    return response.data;
  }

  async getExpiringContracts(): Promise<Contract[]> {
    const response = await authApi.get<Contract[]>('/contracts/expiring_soon/');
    return response.data;
  }

  async createContract(data: Partial<Contract>): Promise<Contract> {
    const response = await authApi.post<Contract>('/contracts/', data);
    return response.data;
  }

  async updateContract(id: string, data: Partial<Contract>): Promise<Contract> {
    const response = await authApi.put<Contract>(`/contracts/${id}/`, data);
    return response.data;
  }

  async deleteContract(id: string): Promise<void> {
    await authApi.delete(`/contracts/${id}/`);
  }

  async sendRenewalNotice(id: string): Promise<any> {
    const response = await authApi.post(`/contracts/${id}/send_renewal_notice/`);
    return response.data;
  }

  // Invoices
  async getInvoices(params?: any): Promise<ApiResponse<Invoice>> {
    const response = await authApi.get<ApiResponse<Invoice>>('/invoices/', { params });
    return response.data;
  }

  async getInvoice(id: string): Promise<Invoice> {
    const response = await authApi.get<Invoice>(`/invoices/${id}/`);
    return response.data;
  }

  async createInvoice(data: Partial<Invoice>): Promise<Invoice> {
    const response = await authApi.post<Invoice>('/invoices/', data);
    return response.data;
  }

  async updateInvoice(id: string, data: Partial<Invoice>): Promise<Invoice> {
    const response = await authApi.put<Invoice>(`/invoices/${id}/`, data);
    return response.data;
  }

  async deleteInvoice(id: string): Promise<void> {
    await authApi.delete(`/invoices/${id}/`);
  }

  async getOverdueInvoices(): Promise<Invoice[]> {
    const response = await authApi.get<Invoice[]>('/invoices/overdue/');
    return response.data;
  }

  async markInvoicePaid(id: string, data?: { payment_method?: string; transaction_id?: string; notes?: string }): Promise<any> {
    const response = await authApi.post(`/invoices/${id}/mark_paid/`, data);
    return response.data;
  }

  async sendInvoice(id: string, email?: string): Promise<any> {
    const response = await authApi.post(`/invoices/${id}/send/`, { email });
    return response.data;
  }

  async downloadInvoicePDF(id: string): Promise<Blob> {
    const response = await authApi.get(`/invoices/${id}/pdf/`, {
      responseType: 'blob'
    });
    return response.data;
  }

  async addInvoicePayment(invoiceId: string, data: Partial<any>): Promise<any> {
    const response = await authApi.post(`/invoices/${invoiceId}/payments/`, data);
    return response.data;
  }

  async getInvoiceStats(): Promise<any> {
    const response = await authApi.get('/invoices/stats/');
    return response.data;
  }

  // Quotes
  async getQuotes(params?: any): Promise<ApiResponse<Quote>> {
    const response = await authApi.get<ApiResponse<Quote>>('/quotes/', { params });
    return response.data;
  }

  async getQuote(id: string): Promise<Quote> {
    const response = await authApi.get<Quote>(`/quotes/${id}/`);
    return response.data;
  }

  async createQuote(data: Partial<Quote>): Promise<Quote> {
    const response = await authApi.post<Quote>('/quotes/', data);
    return response.data;
  }

  async updateQuote(id: string, data: Partial<Quote>): Promise<Quote> {
    const response = await authApi.put<Quote>(`/quotes/${id}/`, data);
    return response.data;
  }

  async deleteQuote(id: string): Promise<void> {
    await authApi.delete(`/quotes/${id}/`);
  }

  async duplicateQuote(id: string): Promise<Quote> {
    const response = await authApi.post<Quote>(`/quotes/${id}/duplicate/`);
    return response.data;
  }

  async sendQuote(id: string, email?: string): Promise<any> {
    const response = await authApi.post(`/quotes/${id}/send/`, { email });
    return response.data;
  }

  async acceptQuote(id: string): Promise<any> {
    const response = await authApi.post(`/quotes/${id}/accept/`);
    return response.data;
  }

  async rejectQuote(id: string, reason?: string): Promise<any> {
    const response = await authApi.post(`/quotes/${id}/reject/`, { reason });
    return response.data;
  }

  async convertQuoteToContract(id: string, contractData?: Partial<Contract>): Promise<Contract> {
    const response = await authApi.post<Contract>(`/quotes/${id}/convert_to_contract/`, contractData);
    return response.data;
  }

  async downloadQuotePDF(id: string): Promise<Blob> {
    const response = await authApi.get(`/quotes/${id}/pdf/`, {
      responseType: 'blob'
    });
    return response.data;
  }

  async getExpiringQuotes(): Promise<Quote[]> {
    const response = await authApi.get<Quote[]>('/quotes/expiring_soon/');
    return response.data;
  }

  async getQuoteStats(): Promise<any> {
    const response = await authApi.get('/quotes/stats/');
    return response.data;
  }

  async addQuoteAttachment(quoteId: string, file: File): Promise<any> {
    const formData = new FormData();
    formData.append('file', file);
    const response = await authApi.post(`/quotes/${quoteId}/attachments/`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  }

  async deleteQuoteAttachment(quoteId: string, attachmentId: string): Promise<void> {
    await authApi.delete(`/quotes/${quoteId}/attachments/${attachmentId}/`);
  }

  // Users
  async getUsers(params?: any): Promise<ApiResponse<User>> {
    const response = await authApi.get<ApiResponse<User>>('/users/', { params });
    return response.data;
  }

  // Audit Logs
  async getAuditLogs(params?: any): Promise<ApiResponse<AuditLog>> {
    const response = await authApi.get<ApiResponse<AuditLog>>('/audit-logs/', { params });
    return response.data;
  }

  // Bulk Operations
  async bulkOperation(endpoint: string, action: string, ids: string[], data?: any): Promise<any> {
    const response = await authApi.post(`/${endpoint}/bulk_operations/`, {
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
    const response = await authApi.post(`/${endpoint}/bulk_operations/`, params, {
      responseType: 'blob'
    });
    return response.data;
  }

  // Email Sending
  async sendContractEmail(contractId: string, data: EmailSendData): Promise<void> {
    await authApi.post(`/contracts/${contractId}/send/`, data);
  }

  async sendQuoteEmail(quoteId: string, data: EmailSendData): Promise<void> {
    await authApi.post(`/quotes/${quoteId}/send/`, data);
  }

  async sendInvoiceEmail(invoiceId: string, data: EmailSendData): Promise<void> {
    await authApi.post(`/invoices/${invoiceId}/send/`, data);
  }

  // Download Contract PDF
  async downloadContractPDF(id: string): Promise<Blob> {
    const response = await authApi.get(`/contracts/${id}/pdf/`, {
      responseType: 'blob'
    });
    return response.data;
  }

  // Automation endpoints
  async getAutomationStatus(): Promise<AutomationStatus> {
    const response = await authApi.get<AutomationStatus>('/automation/status/');
    return response.data;
  }

  async testRunAutomation(type: string, dryRun: boolean): Promise<TestRunResult> {
    const response = await authApi.post<TestRunResult>('/automation/test-run/', {
      type,
      dry_run: dryRun
    });
    return response.data;
  }

  async getRecentAutomatedEmails(): Promise<AutomatedEmail[]> {
    const response = await authApi.get<AutomatedEmail[]>('/automation/recent-emails/');
    return response.data;
  }

  // Campaign methods
  async getCampaigns(params?: any): Promise<any> {
    const response = await authApi.get('/campaigns/', { params });
    return response.data;
  }

  async getCampaign(id: string): Promise<any> {
    const response = await authApi.get(`/campaigns/${id}/`);
    return response.data;
  }

  async createCampaign(data: any): Promise<any> {
    const response = await authApi.post('/campaigns/', data);
    return response.data;
  }

  async updateCampaign(id: string, data: any): Promise<any> {
    const response = await authApi.put(`/campaigns/${id}/`, data);
    return response.data;
  }

  async deleteCampaign(id: string): Promise<void> {
    await authApi.delete(`/campaigns/${id}/`);
  }

  async sendCampaign(id: string, recipientIds?: string[]): Promise<any> {
    const response = await authApi.post(`/campaigns/${id}/send/`, { recipient_ids: recipientIds });
    return response.data;
  }

  async testCampaign(id: string, testEmails: string[]): Promise<any> {
    const response = await authApi.post(`/campaigns/${id}/test/`, { test_emails: testEmails });
    return response.data;
  }

  async getCampaignRecipients(id: string): Promise<any[]> {
    const response = await authApi.get(`/campaigns/${id}/recipients/`);
    return response.data;
  }

  async addCampaignRecipients(id: string, contactIds: string[]): Promise<any> {
    const response = await authApi.post(`/campaigns/${id}/add_recipients/`, { contact_ids: contactIds });
    return response.data;
  }

  async pauseCampaign(id: string): Promise<any> {
    const response = await authApi.post(`/campaigns/${id}/pause/`);
    return response.data;
  }

  async resumeCampaign(id: string): Promise<any> {
    const response = await authApi.post(`/campaigns/${id}/resume/`);
    return response.data;
  }

  async scheduleCampaign(id: string, scheduledSendDate: string): Promise<any> {
    const response = await authApi.post(`/campaigns/${id}/schedule/`, { scheduled_send_date: scheduledSendDate });
    return response.data;
  }

  // Email Templates
  async getEmailTemplates(params?: any): Promise<any> {
    const response = await authApi.get('/email-templates/', { params });
    return response.data;
  }

  async getEmailTemplate(id: string): Promise<any> {
    const response = await authApi.get(`/email-templates/${id}/`);
    return response.data;
  }

  async createEmailTemplate(data: any): Promise<any> {
    const response = await authApi.post('/email-templates/', data);
    return response.data;
  }

  async updateEmailTemplate(id: string, data: any): Promise<any> {
    const response = await authApi.put(`/email-templates/${id}/`, data);
    return response.data;
  }

  async deleteEmailTemplate(id: string): Promise<void> {
    await authApi.delete(`/email-templates/${id}/`);
  }

  async previewEmailTemplate(id: string): Promise<{ subject: string; body_text: string; body_html?: string }> {
    const response = await authApi.get(`/email-templates/${id}/preview/`);
    return response.data;
  }

  async getTemplateVariables(templateType: string): Promise<string[]> {
    const response = await authApi.get('/email-templates/variables/', { params: { template_type: templateType } });
    return response.data;
  }

  async duplicateEmailTemplate(id: string): Promise<Partial<any>> {
    const response = await authApi.post(`/email-templates/${id}/duplicate/`);
    return response.data;
  }

  async bulkOperateEmailTemplates(action: string, ids: string[]): Promise<{ message: string; count: number }> {
    const response = await authApi.post('/email-templates/bulk_operations/', {
      action,
      ids
    });
    return response.data;
  }

  // Email Sequences
  async getEmailSequences(params?: any): Promise<any> {
    const response = await authApi.get('/email-sequences/', { params });
    return response.data;
  }

  async getEmailSequence(id: string): Promise<any> {
    const response = await authApi.get(`/email-sequences/${id}/`);
    return response.data;
  }

  async createEmailSequence(data: any): Promise<any> {
    const response = await authApi.post('/email-sequences/', data);
    return response.data;
  }

  async updateEmailSequence(id: string, data: any): Promise<any> {
    const response = await authApi.put(`/email-sequences/${id}/`, data);
    return response.data;
  }

  async deleteEmailSequence(id: string): Promise<void> {
    await authApi.delete(`/email-sequences/${id}/`);
  }

  async duplicateEmailSequence(id: string): Promise<any> {
    const original = await this.getEmailSequence(id);
    const duplicate = {
      name: `${original.name} (Copy)`,
      description: original.description,
      status: 'paused' as const,
    };
    return this.createEmailSequence(duplicate);
  }

  // Sequence Steps
  async getSequenceSteps(params?: any): Promise<ApiResponse<any>> {
    const response = await authApi.get('/sequence-steps/', { params });
    return response.data;
  }

  async createSequenceStep(data: Partial<any>): Promise<any> {
    const response = await authApi.post('/sequence-steps/', data);
    return response.data;
  }

  async updateSequenceStep(id: string, data: Partial<any>): Promise<any> {
    const response = await authApi.put(`/sequence-steps/${id}/`, data);
    return response.data;
  }

  async deleteSequenceStep(id: string): Promise<void> {
    await authApi.delete(`/sequence-steps/${id}/`);
  }

  // Sequence Enrollments
  async getSequenceEnrollments(params?: any): Promise<ApiResponse<any>> {
    const response = await authApi.get('/sequence-enrollments/', { params });
    return response.data;
  }

  async createSequenceEnrollment(data: Partial<any>): Promise<any> {
    const response = await authApi.post('/sequence-enrollments/', data);
    return response.data;
  }

  async updateSequenceEnrollment(id: string, data: Partial<any>): Promise<any> {
    const response = await authApi.put(`/sequence-enrollments/${id}/`, data);
    return response.data;
  }

  async deleteSequenceEnrollment(id: string): Promise<void> {
    await authApi.delete(`/sequence-enrollments/${id}/`);
  }

  async pauseSequenceEnrollment(id: string): Promise<any> {
    return this.updateSequenceEnrollment(id, { status: 'paused' });
  }

  async resumeSequenceEnrollment(id: string): Promise<any> {
    return this.updateSequenceEnrollment(id, { status: 'active' });
  }

  // Sequence Step Executions
  async getSequenceStepExecutions(params?: any): Promise<ApiResponse<any>> {
    const response = await authApi.get('/sequence-step-executions/', { params });
    return response.data;
  }
}

export interface EmailSendData {
  recipients: string[];
  subject: string;
  body: string;
}

export interface AutomationStatus {
  enabled: boolean;
  cron_schedule: string;
  cron_description: string;
  last_run: string | null;
  next_run: string;
  recent_stats: {
    renewal_sent: number;
    payment_sent: number;
    quarterly_sent: number;
    total_sent_last_7_days: number;
  };
}

export interface TestRunResult {
  success: boolean;
  dry_run: boolean;
  type: string;
  output: string;
  error: string | null;
}

export interface AutomatedEmail {
  id: string;
  date: string;
  type: string;
  type_code: string;
  recipients: string;
  status: string;
  status_code: string;
  subject: string;
  company: string | null;
  contact: string | null;
}

const apiService = new ApiService();
export default apiService;