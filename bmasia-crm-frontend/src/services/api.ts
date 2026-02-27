import {
  User, UserCreateData, UserUpdateData, PasswordChangeData, SmtpSettingsData,
  Company, Contact, Note, Task, Opportunity, OpportunityActivity,
  Contract, Invoice, Quote, DashboardStats, ApiResponse,
  CustomerSegment, SegmentMemberResponse, SegmentValidationResponse,
  EnrollInSequenceResponse, SegmentFilterCriteria, Zone, PreviewZone, ContractZone, Device,
  ClientTechDetail,
  ContractTemplate, ServicePackageItem, CorporatePdfTemplate, ContractDocument,
  SeasonalTriggerDate,
  Vendor, ExpenseCategory, RecurringExpense, ExpenseEntry,
  APAgingReport, APAgingSummary, OverdueExpense, MonthlyExpenseSummary,
  PLStatement, PLComparative, PLTrendData,
  EmailLogEntry
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
  async getDashboardStats(params?: { billing_entity?: string }): Promise<DashboardStats> {
    const response = await authApi.get<DashboardStats>('/dashboard/stats/', { params });
    return response.data;
  }

  // Action Center (Today page)
  async getActionCenterItems(): Promise<any> {
    const response = await authApi.get('/action-center/');
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

    const response = await authApi.patch<Company>(`/companies/${id}/`, data);
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

  async duplicateForRenewal(id: string): Promise<{ message: string; new_contract: Contract; original_status: string }> {
    const response = await authApi.post(`/contracts/${id}/duplicate_for_renewal/`);
    return response.data;
  }

  // Contract-Zone Management
  async addZonesToContract(contractId: string, zones: {id?: string; name?: string; platform?: string}[]): Promise<Zone[]> {
    const response = await authApi.post(`/contracts/${contractId}/add-zones/`, { zones });
    return response.data;
  }

  async getContractZones(contractId: string, params?: {active?: boolean; as_of?: string}): Promise<ContractZone[]> {
    const response = await authApi.get(`/contracts/${contractId}/zones/`, { params });
    return response.data;
  }

  async removeZoneFromContract(contractId: string, zoneId: string): Promise<ContractZone> {
    const response = await authApi.post(`/contracts/${contractId}/remove-zone/`, { zone_id: zoneId });
    return response.data;
  }

  async updateContractZones(contractId: string, zoneIds: string[]): Promise<ContractZone[]> {
    const response = await authApi.put(`/contracts/${contractId}/update-zones/`, { zone_ids: zoneIds });
    return response.data;
  }

  async getZoneContracts(zoneId: string, params?: {active?: boolean}): Promise<ContractZone[]> {
    const response = await authApi.get(`/zones/${zoneId}/contracts/`, { params });
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
    const response = await authApi.patch<Invoice>(`/invoices/${id}/`, data);
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

  async getNextInvoiceNumber(entity: string): Promise<string> {
    const response = await authApi.get(`/invoices/next-number/`, { params: { entity } });
    return response.data.invoice_number;
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

  async exportQuickBooks(params: {
    billing_entity?: string;
    status?: string;
    date_from?: string;
    date_to?: string;
    ar_account_thb?: string;
    ar_account_usd?: string;
    income_account_syb?: string;
    income_account_bms?: string;
    income_account_default?: string;
    tax_account?: string;
  }): Promise<Blob> {
    const response = await authApi.get('/invoices/export-quickbooks/', {
      params,
      responseType: 'blob',
    });
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

  // User Management
  async getUsers(params?: any): Promise<ApiResponse<User>> {
    const response = await authApi.get<ApiResponse<User>>('/users/', { params });
    return response.data;
  }

  async getUser(id: string): Promise<User> {
    const response = await authApi.get<User>(`/users/${id}/`);
    return response.data;
  }

  async createUser(data: UserCreateData): Promise<User> {
    const response = await authApi.post<User>('/users/', data);
    return response.data;
  }

  async updateUser(id: string, data: UserUpdateData): Promise<User> {
    const response = await authApi.patch<User>(`/users/${id}/`, data);
    return response.data;
  }

  async deleteUser(id: string): Promise<void> {
    await authApi.delete(`/users/${id}/`);
  }

  async uploadAvatar(file: File): Promise<{ avatar_url: string }> {
    const formData = new FormData();
    formData.append('avatar', file);
    const response = await authApi.post<{ avatar_url: string }>('/users/upload-avatar/', formData, {
      headers: { 'Content-Type': undefined },
    });
    return response.data;
  }

  async deactivateUser(id: string): Promise<User> {
    const response = await authApi.patch<User>(`/users/${id}/`, { is_active: false });
    return response.data;
  }

  async activateUser(id: string): Promise<User> {
    const response = await authApi.patch<User>(`/users/${id}/`, { is_active: true });
    return response.data;
  }

  // Current User Profile
  async getMyProfile(): Promise<User> {
    const response = await authApi.get<User>('/users/me/');
    return response.data;
  }

  async updateMyProfile(data: Partial<UserUpdateData>): Promise<User> {
    const response = await authApi.patch<User>('/users/me/', data);
    return response.data;
  }

  async changePassword(data: PasswordChangeData): Promise<{ message: string }> {
    const response = await authApi.post<{ message: string }>('/users/change_password/', data);
    return response.data;
  }

  async updateSmtpSettings(data: SmtpSettingsData): Promise<{ message: string; smtp_email: string; smtp_configured: boolean }> {
    const response = await authApi.post('/users/update_smtp/', data);
    return response.data;
  }

  async testSmtpConnection(): Promise<{ success: boolean; message?: string; error?: string }> {
    const response = await authApi.post('/users/test_smtp/');
    return response.data;
  }

  async clearSmtpSettings(): Promise<{ message: string; smtp_configured: boolean }> {
    const response = await authApi.post('/users/update_smtp/', { smtp_email: '', smtp_password: '' });
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

  // Corporate Contracts
  async getMasterAgreements(): Promise<Contract[]> {
    const response = await authApi.get<Contract[]>('/contracts/master-agreements/');
    return response.data;
  }

  async getParticipationAgreements(masterId: string): Promise<Contract[]> {
    const response = await authApi.get<Contract[]>(`/contracts/${masterId}/participation-agreements/`);
    return response.data;
  }

  async downloadStandardTerms(contractId: string): Promise<Blob> {
    const response = await authApi.get(`/contracts/${contractId}/standard-terms/`, {
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

  // Customer Segments
  async getSegments(params?: any): Promise<ApiResponse<CustomerSegment>> {
    const response = await authApi.get<ApiResponse<CustomerSegment>>('/segments/', { params });
    return response.data;
  }

  async getSegment(id: string): Promise<CustomerSegment> {
    const response = await authApi.get<CustomerSegment>(`/segments/${id}/`);
    return response.data;
  }

  async createSegment(data: Partial<CustomerSegment>): Promise<CustomerSegment> {
    const response = await authApi.post<CustomerSegment>('/segments/', data);
    return response.data;
  }

  async updateSegment(id: string, data: Partial<CustomerSegment>): Promise<CustomerSegment> {
    const response = await authApi.put<CustomerSegment>(`/segments/${id}/`, data);
    return response.data;
  }

  async deleteSegment(id: string): Promise<void> {
    await authApi.delete(`/segments/${id}/`);
  }

  async getSegmentMembers(id: string, params?: { limit?: number; offset?: number }): Promise<SegmentMemberResponse> {
    const response = await authApi.get<SegmentMemberResponse>(`/segments/${id}/members/`, { params });
    return response.data;
  }

  async recalculateSegment(id: string): Promise<CustomerSegment> {
    const response = await authApi.post<CustomerSegment>(`/segments/${id}/recalculate/`);
    return response.data;
  }

  async enrollSegmentInSequence(id: string, data: { sequence_id: string; notes?: string }): Promise<EnrollInSequenceResponse> {
    const response = await authApi.post<EnrollInSequenceResponse>(`/segments/${id}/enroll_in_sequence/`, data);
    return response.data;
  }

  async duplicateSegment(id: string, data: { name: string }): Promise<CustomerSegment> {
    const response = await authApi.post<CustomerSegment>(`/segments/${id}/duplicate/`, data);
    return response.data;
  }

  async validateSegmentFilters(filter_criteria: SegmentFilterCriteria): Promise<SegmentValidationResponse> {
    const response = await authApi.post<SegmentValidationResponse>('/segments/validate_filters/', { filter_criteria });
    return response.data;
  }

  // Ticket API methods
  async getTickets(params?: any): Promise<ApiResponse<any>> {
    const response = await authApi.get('/tickets/', { params });
    return response.data;
  }

  async getTicket(id: string): Promise<any> {
    const response = await authApi.get(`/tickets/${id}/`);
    return response.data;
  }

  async createTicket(data: Partial<any>): Promise<any> {
    const response = await authApi.post('/tickets/', data);
    return response.data;
  }

  async updateTicket(id: string, data: Partial<any>): Promise<any> {
    const response = await authApi.patch(`/tickets/${id}/`, data);
    return response.data;
  }

  async deleteTicket(id: string): Promise<void> {
    await authApi.delete(`/tickets/${id}/`);
  }

  async assignTicket(id: string, userId: string | null): Promise<any> {
    const response = await authApi.post(`/tickets/${id}/assign/`, { user_id: userId });
    return response.data;
  }

  async addTicketComment(ticketId: string, data: Partial<any>): Promise<any> {
    const response = await authApi.post(`/tickets/${ticketId}/add_comment/`, data);
    return response.data;
  }

  async getTicketStats(): Promise<any> {
    const response = await authApi.get('/tickets/stats/');
    return response.data;
  }

  async uploadTicketAttachment(ticketId: string, file: File): Promise<any> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('ticket', ticketId);

    const response = await authApi.post('/ticket-attachments/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data;
  }

  // Knowledge Base API methods
  async getKBCategories(): Promise<any> {
    const response = await authApi.get('/kb/categories/');
    return response;
  }

  async createKBCategory(data: Partial<any>): Promise<any> {
    const response = await authApi.post('/kb/categories/', data);
    return response.data;
  }

  async updateKBCategory(id: string, data: Partial<any>): Promise<any> {
    const response = await authApi.patch(`/kb/categories/${id}/`, data);
    return response.data;
  }

  async deleteKBCategory(id: string): Promise<void> {
    await authApi.delete(`/kb/categories/${id}/`);
  }

  async getKBTags(): Promise<any> {
    const response = await authApi.get('/kb/tags/');
    return response;
  }

  async createKBTag(data: Partial<any>): Promise<any> {
    const response = await authApi.post('/kb/tags/', data);
    return response.data;
  }

  async updateKBTag(id: string, data: Partial<any>): Promise<any> {
    const response = await authApi.patch(`/kb/tags/${id}/`, data);
    return response.data;
  }

  async deleteKBTag(id: string): Promise<void> {
    await authApi.delete(`/kb/tags/${id}/`);
  }

  async getKBArticles(params?: {
    page?: number;
    page_size?: number;
    search?: string;
    category?: string;
    tags?: string;
    status?: string;
    ordering?: string;
  }): Promise<ApiResponse<any>> {
    const response = await authApi.get('/kb/articles/', { params });
    return response.data;
  }

  async getKBArticle(id: string): Promise<any> {
    const response = await authApi.get(`/kb/articles/${id}/`);
    return response.data;
  }

  async downloadKBArticlePDF(id: string): Promise<Blob> {
    const response = await authApi.get(`/kb/articles/${id}/pdf/`, {
      responseType: 'blob'
    });
    return response.data;
  }

  async searchKBArticles(query: string): Promise<any> {
    const response = await authApi.get('/kb/articles/search/', { params: { q: query } });
    return response.data;
  }

  async getFeaturedArticles(): Promise<any> {
    const response = await authApi.get('/kb/articles/featured/');
    return response;
  }

  async getPopularArticles(limit: number = 5): Promise<any> {
    const response = await authApi.get('/kb/articles/popular/', { params: { limit } });
    return response.data;
  }

  async recordArticleView(id: string): Promise<any> {
    const response = await authApi.post(`/kb/articles/${id}/record_view/`);
    return response.data;
  }

  async rateArticle(id: string, isHelpful: boolean): Promise<any> {
    const response = await authApi.post(`/kb/articles/${id}/rate/`, { is_helpful: isHelpful });
    return response.data;
  }

  // Knowledge Base Article Management (CREATE/UPDATE)
  async createKBArticle(data: Partial<any>): Promise<any> {
    const response = await authApi.post('/kb/articles/', data);
    return response.data;
  }

  async updateKBArticle(id: string, data: Partial<any>): Promise<any> {
    const response = await authApi.put(`/kb/articles/${id}/`, data);
    return response.data;
  }

  async deleteKBArticle(id: string): Promise<void> {
    await authApi.delete(`/kb/articles/${id}/`);
  }

  async uploadKBAttachment(articleId: string, file: File): Promise<any> {
    const formData = new FormData();
    formData.append('file', file);
    const response = await authApi.post(`/kb/articles/${articleId}/add_attachment/`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data;
  }

  // Zone Management
  async getZones(params?: any): Promise<ApiResponse<Zone>> {
    const response = await authApi.get('/zones/', { params });
    return response.data;
  }

  async getZonesByCompany(companyId: string): Promise<Zone[]> {
    const response = await authApi.get(`/zones/by_company/`, {
      params: { company_id: companyId }
    });
    return response.data; // Direct array, not paginated
  }

  async getZone(id: string): Promise<Zone> {
    const response = await authApi.get(`/zones/${id}/`);
    return response.data;
  }

  async createZone(data: Partial<Zone>): Promise<Zone> {
    const response = await authApi.post('/zones/', data);
    return response.data;
  }

  async updateZone(id: string, data: Partial<Zone>): Promise<Zone> {
    const response = await authApi.patch(`/zones/${id}/`, data);
    return response.data;
  }

  async deleteZone(id: string): Promise<void> {
    await authApi.delete(`/zones/${id}/`);
  }

  async syncAllZones(): Promise<{ synced: number; errors: number; message: string }> {
    const response = await authApi.post('/zones/sync-all/');
    return response.data;
  }

  async previewSoundtrackZones(accountId: string): Promise<PreviewZone[]> {
    const response = await authApi.get('/zones/preview-zones/', {
      params: { account_id: accountId }
    });
    return response.data.zones;
  }

  async getOrphanedZones(): Promise<Zone[]> {
    const response = await authApi.get('/zones/orphaned/');
    return response.data;
  }

  async hardDeleteZone(id: string): Promise<void> {
    await authApi.delete(`/zones/${id}/hard-delete/`);
  }

  async getZoneHealthSummary(params?: any): Promise<any> {
    const response = await authApi.get('/zones/health-summary/', { params });
    return response.data;
  }

  async checkZoneOverlaps(zoneIds: string[], excludeContract?: string): Promise<any> {
    const params: any = { zone_ids: zoneIds.join(',') };
    if (excludeContract) params.exclude_contract = excludeContract;
    const response = await authApi.get('/zones/check-overlaps/', { params });
    return response.data;
  }

  // Device Management
  async getDevices(params?: Record<string, string>): Promise<Device[]> {
    const response = await authApi.get<Device[]>('/devices/', { params });
    return response.data;
  }

  async getDevice(id: string): Promise<Device> {
    const response = await authApi.get<Device>(`/devices/${id}/`);
    return response.data;
  }

  async createDevice(data: Partial<Device>): Promise<Device> {
    const response = await authApi.post<Device>('/devices/', data);
    return response.data;
  }

  async updateDevice(id: string, data: Partial<Device>): Promise<Device> {
    const response = await authApi.put<Device>(`/devices/${id}/`, data);
    return response.data;
  }

  async deleteDevice(id: string): Promise<void> {
    await authApi.delete(`/devices/${id}/`);
  }

  async getDevicesByCompany(companyId: string): Promise<Device[]> {
    const response = await authApi.get<Device[]>('/devices/by_company/', {
      params: { company_id: companyId }
    });
    return response.data;
  }

  // Client Tech Details
  async getClientTechDetails(params?: any): Promise<ApiResponse<ClientTechDetail>> {
    const response = await authApi.get<ApiResponse<ClientTechDetail>>('/client-tech-details/', { params });
    return response.data;
  }

  async getClientTechDetail(id: string): Promise<ClientTechDetail> {
    const response = await authApi.get<ClientTechDetail>(`/client-tech-details/${id}/`);
    return response.data;
  }

  async createClientTechDetail(data: Partial<ClientTechDetail>): Promise<ClientTechDetail> {
    const response = await authApi.post<ClientTechDetail>('/client-tech-details/', data);
    return response.data;
  }

  async updateClientTechDetail(id: string, data: Partial<ClientTechDetail>): Promise<ClientTechDetail> {
    const response = await authApi.patch<ClientTechDetail>(`/client-tech-details/${id}/`, data);
    return response.data;
  }

  async deleteClientTechDetail(id: string): Promise<void> {
    await authApi.delete(`/client-tech-details/${id}/`);
  }

  async getClientTechDetailStats(params?: any): Promise<{ total_zones: number; total_clients: number }> {
    const response = await authApi.get<{ total_zones: number; total_clients: number }>('/client-tech-details/stats/', { params });
    return response.data;
  }

  async getClientTechDetailsByCompany(companyId: string): Promise<ClientTechDetail[]> {
    const response = await authApi.get<ClientTechDetail[]>('/client-tech-details/by_company/', {
      params: { company_id: companyId }
    });
    return response.data;
  }

  async downloadClientTechDetailPDF(id: string): Promise<Blob> {
    const response = await authApi.get(`/client-tech-details/${id}/pdf/`, {
      responseType: 'blob'
    });
    return response.data;
  }

  // Contract Content Management
  async getContractTemplates(params?: any): Promise<ApiResponse<any>> {
    const response = await authApi.get('/contract-templates/', { params });
    return response.data;
  }

  async getContractTemplate(id: string): Promise<any> {
    const response = await authApi.get(`/contract-templates/${id}/`);
    return response.data;
  }

  async createContractTemplate(data: any): Promise<any> {
    const response = await authApi.post('/contract-templates/', data);
    return response.data;
  }

  async updateContractTemplate(id: string, data: any): Promise<any> {
    const response = await authApi.put(`/contract-templates/${id}/`, data);
    return response.data;
  }

  async deleteContractTemplate(id: string): Promise<void> {
    await authApi.delete(`/contract-templates/${id}/`);
  }

  async getServicePackageItems(): Promise<any[]> {
    const response = await authApi.get('/service-package-items/', {
      params: { page_size: 1000 }
    });
    return response.data.results || [];
  }

  async getCorporatePdfTemplates(params?: any): Promise<ApiResponse<any>> {
    const response = await authApi.get('/corporate-pdf-templates/', { params });
    return response.data;
  }

  async getContractDocuments(contractId: string): Promise<ContractDocument[]> {
    const response = await authApi.get('/contract-documents/', {
      params: { contract: contractId }
    });
    // Handle both paginated (results array) and non-paginated responses
    return response.data.results || response.data || [];
  }

  async uploadContractDocument(contractId: string, data: FormData): Promise<ContractDocument> {
    const response = await authApi.post('/contract-documents/', data, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data;
  }

  async deleteContractDocument(id: string): Promise<void> {
    await authApi.delete(`/contract-documents/${id}/`);
  }

  // Seasonal Trigger Dates (Settings)
  async getSeasonalTriggerDates(params?: { year?: number }): Promise<SeasonalTriggerDate[]> {
    const response = await authApi.get('/seasonal-trigger-dates/', { params });
    // API returns paginated response {count, results}, extract results array
    return response.data.results || response.data;
  }

  async getSeasonalTriggerDate(id: string): Promise<SeasonalTriggerDate> {
    const response = await authApi.get(`/seasonal-trigger-dates/${id}/`);
    return response.data;
  }

  async createSeasonalTriggerDate(data: Partial<SeasonalTriggerDate>): Promise<SeasonalTriggerDate> {
    const response = await authApi.post('/seasonal-trigger-dates/', data);
    return response.data;
  }

  async updateSeasonalTriggerDate(id: string, data: Partial<SeasonalTriggerDate>): Promise<SeasonalTriggerDate> {
    const response = await authApi.put(`/seasonal-trigger-dates/${id}/`, data);
    return response.data;
  }

  async deleteSeasonalTriggerDate(id: string): Promise<void> {
    await authApi.delete(`/seasonal-trigger-dates/${id}/`);
  }

  // Revenue Dashboard
  async getRevenueMonthly(year: number, currency?: string, billingEntity?: string): Promise<any> {
    const params: any = { year };
    if (currency) params.currency = currency;
    if (billingEntity) params.billing_entity = billingEntity;
    const response = await authApi.get('/revenue/monthly/', { params });
    return response.data;
  }

  async initializeRevenueModule(): Promise<any> {
    const response = await authApi.post('/revenue/initialize/');
    return response.data;
  }

  async classifyContracts(force: boolean = false): Promise<any> {
    const response = await authApi.post('/revenue/classify-contracts/', { force });
    return response.data;
  }

  async generateRevenueSnapshots(year: number, month?: number, force: boolean = false): Promise<any> {
    const data: any = { year, force };
    if (month) data.month = month;
    const response = await authApi.post('/revenue/generate-snapshots/', data);
    return response.data;
  }

  async getRevenueYoY(year: number, compareYear?: number, currency?: string, billingEntity?: string): Promise<any> {
    const params: any = { year };
    if (compareYear) params.compare_year = compareYear;
    if (currency) params.currency = currency;
    if (billingEntity) params.billing_entity = billingEntity;
    const response = await authApi.get('/revenue/year-over-year/', { params });
    return response.data;
  }

  // AR Aging
  async getARAgingReport(currency?: string, billingEntity?: string, asOfDate?: string): Promise<ARAgingReport> {
    const params: any = {};
    if (currency) params.currency = currency;
    if (billingEntity) params.billing_entity = billingEntity;
    if (asOfDate) params.as_of_date = asOfDate;
    const response = await authApi.get('/ar-aging/report/', { params });
    return response.data;
  }

  async getARAgingSummary(currency?: string, billingEntity?: string): Promise<ARAgingSummary> {
    const params: any = {};
    if (currency) params.currency = currency;
    if (billingEntity) params.billing_entity = billingEntity;
    const response = await authApi.get('/ar-aging/summary/', { params });
    return response.data;
  }

  async getAROverdueInvoices(minDays?: number, currency?: string, billingEntity?: string): Promise<OverdueInvoice[]> {
    const params: any = {};
    if (minDays) params.min_days = minDays;
    if (currency) params.currency = currency;
    if (billingEntity) params.billing_entity = billingEntity;
    const response = await authApi.get('/ar-aging/overdue/', { params });
    return response.data;
  }

  async getCollectionPriorityList(currency?: string, billingEntity?: string, limit?: number): Promise<OverdueInvoice[]> {
    const params: any = {};
    if (currency) params.currency = currency;
    if (billingEntity) params.billing_entity = billingEntity;
    if (limit) params.limit = limit;
    const response = await authApi.get('/ar-aging/collection-priority/', { params });
    return response.data;
  }

  // ============================================================================
  // Expense Module (Phase 3 - Finance Module)
  // ============================================================================

  // Vendors
  async getVendors(): Promise<Vendor[]> {
    const response = await authApi.get('/vendors/');
    return response.data.results || response.data;
  }

  async getVendor(id: string): Promise<Vendor> {
    const response = await authApi.get(`/vendors/${id}/`);
    return response.data;
  }

  async createVendor(data: Partial<Vendor>): Promise<Vendor> {
    const response = await authApi.post('/vendors/', data);
    return response.data;
  }

  async updateVendor(id: string, data: Partial<Vendor>): Promise<Vendor> {
    const response = await authApi.patch(`/vendors/${id}/`, data);
    return response.data;
  }

  async deleteVendor(id: string): Promise<void> {
    await authApi.delete(`/vendors/${id}/`);
  }

  async getActiveVendors(): Promise<Vendor[]> {
    const response = await authApi.get('/vendors/active/');
    return response.data;
  }

  async getVendorsByEntity(entity: string): Promise<Vendor[]> {
    const response = await authApi.get('/vendors/by-entity/', { params: { entity } });
    return response.data;
  }

  // Expense Categories
  async getExpenseCategories(): Promise<ExpenseCategory[]> {
    const response = await authApi.get('/expense-categories/');
    return response.data.results || response.data;
  }

  async getExpenseCategory(id: string): Promise<ExpenseCategory> {
    const response = await authApi.get(`/expense-categories/${id}/`);
    return response.data;
  }

  async createExpenseCategory(data: Partial<ExpenseCategory>): Promise<ExpenseCategory> {
    const response = await authApi.post('/expense-categories/', data);
    return response.data;
  }

  async updateExpenseCategory(id: string, data: Partial<ExpenseCategory>): Promise<ExpenseCategory> {
    const response = await authApi.patch(`/expense-categories/${id}/`, data);
    return response.data;
  }

  async deleteExpenseCategory(id: string): Promise<void> {
    await authApi.delete(`/expense-categories/${id}/`);
  }

  async getExpenseCategoryTree(): Promise<ExpenseCategory[]> {
    const response = await authApi.get('/expense-categories/tree/');
    return response.data;
  }

  async getExpenseCategoriesByType(type: string): Promise<ExpenseCategory[]> {
    const response = await authApi.get('/expense-categories/by-type/', { params: { type } });
    return response.data;
  }

  async initializeDefaultCategories(): Promise<{ success: boolean; created: number; message: string }> {
    const response = await authApi.post('/expense-categories/initialize-defaults/');
    return response.data;
  }

  // Recurring Expenses
  async getRecurringExpenses(): Promise<RecurringExpense[]> {
    const response = await authApi.get('/recurring-expenses/');
    return response.data.results || response.data;
  }

  async getRecurringExpense(id: string): Promise<RecurringExpense> {
    const response = await authApi.get(`/recurring-expenses/${id}/`);
    return response.data;
  }

  async createRecurringExpense(data: Partial<RecurringExpense>): Promise<RecurringExpense> {
    const response = await authApi.post('/recurring-expenses/', data);
    return response.data;
  }

  async updateRecurringExpense(id: string, data: Partial<RecurringExpense>): Promise<RecurringExpense> {
    const response = await authApi.patch(`/recurring-expenses/${id}/`, data);
    return response.data;
  }

  async deleteRecurringExpense(id: string): Promise<void> {
    await authApi.delete(`/recurring-expenses/${id}/`);
  }

  async getActiveRecurringExpenses(): Promise<RecurringExpense[]> {
    const response = await authApi.get('/recurring-expenses/active/');
    return response.data;
  }

  async generateRecurringExpenseEntry(id: string, year: number, month: number): Promise<{ success: boolean; expense_entry_id: string; message: string }> {
    const response = await authApi.post(`/recurring-expenses/${id}/generate-entries/`, { year, month });
    return response.data;
  }

  // Expense Entries
  async getExpenses(filters?: { category?: string; vendor?: string; billing_entity?: string; status?: string; currency?: string }): Promise<ExpenseEntry[]> {
    const response = await authApi.get('/expenses/', { params: filters });
    return response.data.results || response.data;
  }

  async getExpense(id: string): Promise<ExpenseEntry> {
    const response = await authApi.get(`/expenses/${id}/`);
    return response.data;
  }

  async createExpense(data: Partial<ExpenseEntry>): Promise<ExpenseEntry> {
    const response = await authApi.post('/expenses/', data);
    return response.data;
  }

  async updateExpense(id: string, data: Partial<ExpenseEntry>): Promise<ExpenseEntry> {
    const response = await authApi.patch(`/expenses/${id}/`, data);
    return response.data;
  }

  async deleteExpense(id: string): Promise<void> {
    await authApi.delete(`/expenses/${id}/`);
  }

  async approveExpense(id: string): Promise<ExpenseEntry> {
    const response = await authApi.post(`/expenses/${id}/approve/`);
    return response.data;
  }

  async payExpense(id: string, data: { payment_date?: string; payment_method?: string; payment_reference?: string }): Promise<ExpenseEntry> {
    const response = await authApi.post(`/expenses/${id}/pay/`, data);
    return response.data;
  }

  async cancelExpense(id: string): Promise<ExpenseEntry> {
    const response = await authApi.post(`/expenses/${id}/cancel/`);
    return response.data;
  }

  async getPendingExpenses(): Promise<ExpenseEntry[]> {
    const response = await authApi.get('/expenses/pending/');
    return response.data;
  }

  async getExpensesByMonth(year: number, month: number, currency?: string, billingEntity?: string): Promise<{ year: number; month: number; count: number; expenses: ExpenseEntry[] }> {
    const params: any = { year, month };
    if (currency) params.currency = currency;
    if (billingEntity) params.billing_entity = billingEntity;
    const response = await authApi.get('/expenses/by-month/', { params });
    return response.data;
  }

  // AP Aging
  async getAPAgingReport(currency?: string, billingEntity?: string, asOfDate?: string): Promise<APAgingReport> {
    const params: any = {};
    if (currency) params.currency = currency;
    if (billingEntity) params.billing_entity = billingEntity;
    if (asOfDate) params.as_of_date = asOfDate;
    const response = await authApi.get('/ap-aging/report/', { params });
    return response.data;
  }

  async getAPAgingSummary(currency?: string, billingEntity?: string): Promise<APAgingSummary> {
    const params: any = {};
    if (currency) params.currency = currency;
    if (billingEntity) params.billing_entity = billingEntity;
    const response = await authApi.get('/ap-aging/summary/', { params });
    return response.data;
  }

  async getAPOverdueExpenses(minDays?: number, currency?: string, billingEntity?: string): Promise<{ count: number; min_days_overdue: number; expenses: OverdueExpense[] }> {
    const params: any = {};
    if (minDays) params.min_days = minDays;
    if (currency) params.currency = currency;
    if (billingEntity) params.billing_entity = billingEntity;
    const response = await authApi.get('/ap-aging/overdue/', { params });
    return response.data;
  }

  async getPaymentPriorityList(currency?: string, billingEntity?: string, limit?: number): Promise<{ count: number; expenses: OverdueExpense[] }> {
    const params: any = {};
    if (currency) params.currency = currency;
    if (billingEntity) params.billing_entity = billingEntity;
    if (limit) params.limit = limit;
    const response = await authApi.get('/ap-aging/payment-priority/', { params });
    return response.data;
  }

  async getMonthlyExpenseSummary(year: number, month?: number, currency?: string, billingEntity?: string): Promise<MonthlyExpenseSummary> {
    const params: any = { year };
    if (month) params.month = month;
    if (currency) params.currency = currency;
    if (billingEntity) params.billing_entity = billingEntity;
    const response = await authApi.get('/ap-aging/monthly-summary/', { params });
    return response.data;
  }

  // ====================
  // P&L Report Methods (Phase 4 - Finance Module)
  // ====================

  async getPLMonthly(year: number, month: number, currency?: string, billingEntity?: string): Promise<PLStatement> {
    const params: any = { year, month };
    if (currency) params.currency = currency;
    if (billingEntity) params.billing_entity = billingEntity;
    const response = await authApi.get('/profit-loss/monthly/', { params });
    return response.data;
  }

  async getPLYTD(year: number, throughMonth?: number, currency?: string, billingEntity?: string): Promise<PLStatement> {
    const params: any = { year };
    if (throughMonth) params.through_month = throughMonth;
    if (currency) params.currency = currency;
    if (billingEntity) params.billing_entity = billingEntity;
    const response = await authApi.get('/profit-loss/ytd/', { params });
    return response.data;
  }

  async getPLComparative(year: number, month: number, compareYear: number, currency?: string, billingEntity?: string): Promise<PLComparative> {
    const params: any = { year, month, compare_year: compareYear };
    if (currency) params.currency = currency;
    if (billingEntity) params.billing_entity = billingEntity;
    const response = await authApi.get('/profit-loss/comparative/', { params });
    return response.data;
  }

  async getPLTrend(year: number, currency?: string, billingEntity?: string): Promise<PLTrendData[]> {
    const params: any = { year };
    if (currency) params.currency = currency;
    if (billingEntity) params.billing_entity = billingEntity;
    const response = await authApi.get('/profit-loss/trend/', { params });
    return response.data;
  }

  // Email Logs
  async getEmailLogs(params?: { quote?: string; invoice?: string; contract?: string; company?: string }): Promise<EmailLogEntry[]> {
    const response = await authApi.get('/email-logs/', { params });
    return response.data.results || response.data;
  }

  // Prospect Sequences
  async getProspectSequences(): Promise<any> {
    const response = await authApi.get('/prospect-sequences/');
    return response.data;
  }

  async getProspectSequence(id: string): Promise<any> {
    const response = await authApi.get(`/prospect-sequences/${id}/`);
    return response.data;
  }

  async createProspectSequence(data: any): Promise<any> {
    const response = await authApi.post('/prospect-sequences/', data);
    return response.data;
  }

  async updateProspectSequence(id: string, data: any): Promise<any> {
    const response = await authApi.patch(`/prospect-sequences/${id}/`, data);
    return response.data;
  }

  async deleteProspectSequence(id: string): Promise<void> {
    await authApi.delete(`/prospect-sequences/${id}/`);
  }

  async enrollInSequence(sequenceId: string, data: { opportunity_id: string; contact_id: string }): Promise<any> {
    const response = await authApi.post(`/prospect-sequences/${sequenceId}/enroll/`, data);
    return response.data;
  }

  // Prospect Enrollments
  async getProspectEnrollments(params?: any): Promise<any> {
    const response = await authApi.get('/prospect-enrollments/', { params });
    return response.data;
  }

  async pauseEnrollment(id: string): Promise<any> {
    const response = await authApi.post(`/prospect-enrollments/${id}/pause/`);
    return response.data;
  }

  async resumeEnrollment(id: string): Promise<any> {
    const response = await authApi.post(`/prospect-enrollments/${id}/resume/`);
    return response.data;
  }

  async cancelEnrollment(id: string): Promise<any> {
    const response = await authApi.post(`/prospect-enrollments/${id}/cancel/`);
    return response.data;
  }

  // Prospect Replies
  async getProspectReplies(params?: any): Promise<any> {
    const response = await authApi.get('/prospect-replies/', { params });
    return response.data;
  }

  // AI Email Drafts
  async getAIEmailDrafts(params?: any): Promise<any> {
    const response = await authApi.get('/ai-email-drafts/', { params });
    return response.data;
  }

  async approveAIEmailDraft(id: string): Promise<any> {
    const response = await authApi.post(`/ai-email-drafts/${id}/approve/`);
    return response.data;
  }

  async rejectAIEmailDraft(id: string, data?: { pause_sequence?: boolean }): Promise<any> {
    const response = await authApi.post(`/ai-email-drafts/${id}/reject/`, data);
    return response.data;
  }

  async editAndApproveAIEmailDraft(id: string, data: { subject: string; body_html: string }): Promise<any> {
    const response = await authApi.post(`/ai-email-drafts/${id}/edit_and_approve/`, data);
    return response.data;
  }

  async getAIEmailDraftPendingCount(): Promise<{ count: number }> {
    const response = await authApi.get('/ai-email-drafts/pending_count/');
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

// AR Aging Types
export interface ARAgingSummary {
  total_ar: number;
  current: number;
  '1_30': number;
  '31_60': number;
  '61_90': number;
  '90_plus': number;
  invoice_count: number;
}

export interface ARInvoiceDetail {
  invoice_id: string;
  invoice_number: string;
  company_id: string;
  company_name: string;
  issue_date: string;
  due_date: string;
  amount: number;
  currency: string;
  days_overdue: number;
  aging_bucket: string;
  status: string;
}

export interface ARCompanyDetail {
  company_id: string;
  company_name: string;
  total: number;
  current: number;
  '1_30': number;
  '31_60': number;
  '61_90': number;
  '90_plus': number;
  invoices: ARInvoiceDetail[];
}

export interface ARAgingReport {
  as_of_date: string;
  currency: string;
  billing_entity: string;
  summary: ARAgingSummary;
  by_company: ARCompanyDetail[];
  invoices: ARInvoiceDetail[];
}

export interface OverdueInvoice {
  invoice_id: string;
  invoice_number: string;
  company_name: string;
  company_id: string;
  due_date: string;
  amount: number;
  currency: string;
  days_overdue: number;
  aging_bucket: string;
  contact_email: string;
  contact_phone: string;
  priority_score?: number;
}

const apiService = new ApiService();
export default apiService;