export interface User {
  id: string;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  role: 'Sales' | 'Marketing' | 'Tech Support' | 'Admin';
  phone?: string;
  department?: string;
  is_active: boolean;
  date_joined: string;
  permissions?: string[];
  groups?: string[];
}

export interface SubscriptionPlan {
  id: string;
  company: string;
  company_name: string;
  tier: 'Soundtrack Essential (Serviced)' | 'Soundtrack Essential (Self-Managed)' | 
       'Soundtrack Unlimited (Serviced)' | 'Soundtrack Unlimited (Self-Managed)' | 'Beat Breeze';
  zone_count: number;
  billing_period: 'Monthly' | 'Yearly';
  price_per_zone?: number;
  currency: 'USD' | 'THB';
  total_value: number;
  monthly_value: number;
  display_price: string;
  is_active: boolean;
  start_date?: string;
  end_date?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface Company {
  id: string;
  name: string;
  country?: string;
  website?: string;
  industry?: string;
  location_count: number;
  music_zone_count: number;
  avg_zones_per_location: number;
  annual_revenue?: number;
  is_active: boolean;
  notes?: string;
  address_line1?: string;
  address_line2?: string;
  city?: string;
  state?: string;
  postal_code?: string;
  full_address?: string;
  phone?: string;
  email?: string;
  soundtrack_account_id?: string;
  total_contract_value: number;
  contacts: Contact[];
  subscription_plans: SubscriptionPlan[];
  active_subscription_plans: SubscriptionPlan[];
  subscription_summary: string;
  primary_contact?: Contact;
  opportunities_count: number;
  active_contracts_count: number;
  created_at: string;
  updated_at: string;
}

export interface Contact {
  id: string;
  company: string;
  company_name: string;
  first_name: string;
  last_name: string;
  name: string; // computed full name
  email: string;
  phone?: string;
  mobile?: string;
  title?: string;
  department?: string;
  status: 'Active' | 'Inactive';
  is_decision_maker: boolean;
  linkedin_url?: string;
  notes?: string;
  preferred_contact_method?: 'Email' | 'Phone' | 'Mobile' | 'LinkedIn';
  last_contacted?: string;
  created_at: string;
  updated_at: string;
}

export interface Note {
  id: string;
  company: string;
  company_name: string;
  author: string;
  author_name: string;
  contact?: string;
  contact_name?: string;
  note_type: 'General' | 'Meeting' | 'Call' | 'Email' | 'Task' | 'Follow-up' | 'Issue' | 'Resolution';
  priority: 'Low' | 'Medium' | 'High' | 'Urgent';
  title?: string;
  text: string;
  is_private: boolean;
  follow_up_date?: string;
  tags?: string;
  created_at: string;
  updated_at: string;
}

export interface TaskSubtask {
  id?: string;
  task?: string;
  title: string;
  completed: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface TaskComment {
  id: string;
  task: string;
  user: string;
  user_name: string;
  comment: string;
  created_at: string;
  updated_at: string;
}

export interface TaskAttachment {
  id: string;
  task: string;
  name: string;
  file: string;
  size: number;
  uploaded_by: string;
  uploaded_by_name: string;
  created_at: string;
}

export interface Task {
  id: string;
  company: string;
  company_name: string;
  assigned_to?: string;
  assigned_to_name?: string;
  created_by: string;
  created_by_name: string;
  department?: string;
  title: string;
  description: string;
  priority: 'Low' | 'Medium' | 'High' | 'Urgent';
  status: 'To Do' | 'In Progress' | 'Review' | 'Done' | 'Cancelled' | 'On Hold';
  task_type?: 'Follow-up' | 'Meeting' | 'Delivery' | 'Support' | 'Research' | 'Development' | 'Other';
  due_date?: string;
  reminder_date?: string;
  completed_at?: string;
  estimated_hours?: number;
  actual_hours?: number;
  tags?: string;
  is_overdue: boolean;
  related_opportunity?: string;
  related_opportunity_name?: string;
  related_contract?: string;
  related_contract_number?: string;
  related_contact?: string;
  related_contact_name?: string;
  subtasks?: TaskSubtask[];
  comments?: TaskComment[];
  attachments?: TaskAttachment[];
  progress_percentage?: number;
  watchers?: string[];  // user IDs who are watching this task
  created_at: string;
  updated_at: string;
}

export interface Opportunity {
  id: string;
  company: string;
  company_name: string;
  name: string;
  stage: 'Contacted' | 'Quotation Sent' | 'Contract Sent' | 'Won' | 'Lost';
  expected_value?: number;
  probability: number;
  owner: string;
  owner_name: string;
  lead_source?: string;
  contact_method?: string;
  last_contact_date?: string;
  follow_up_date?: string;
  expected_close_date?: string;
  actual_close_date?: string;
  notes?: string;
  is_active: boolean;
  competitors?: string;
  pain_points?: string;
  decision_criteria?: string;
  weighted_value: number;
  days_in_stage: number;
  is_overdue: boolean;
  activities: OpportunityActivity[];
  recent_activities: OpportunityActivity[];
  created_at: string;
  updated_at: string;
}

export interface OpportunityActivity {
  id: string;
  opportunity: string;
  user: string;
  user_name: string;
  contact?: string;
  contact_name?: string;
  activity_type: 'Call' | 'Email' | 'Meeting' | 'Demo' | 'Proposal' | 'Follow-up' | 'Quote' | 'Contract' | 'Other';
  subject: string;
  description: string;
  duration_minutes?: number;
  date: string;
  completed: boolean;
  next_action_date?: string;
  outcome?: string;
  next_steps?: string;
  created_at: string;
  updated_at: string;
}

export interface Contract {
  id: string;
  company: string;
  company_name: string;
  opportunity?: string;
  opportunity_name?: string;
  contract_number: string;
  contract_type: 'Annual' | 'Monthly' | 'One-time' | 'Custom';
  status: 'Draft' | 'Sent' | 'Signed' | 'Active' | 'Expired' | 'Terminated' | 'Renewed';
  start_date: string;
  end_date: string;
  value: number;
  currency: string;
  auto_renew: boolean;
  renewal_period_months: number;
  is_active: boolean;
  payment_terms?: string;
  billing_frequency: string;
  discount_percentage: number;
  notes?: string;
  renewal_notice_sent: boolean;
  renewal_notice_date?: string;
  days_until_expiry: number;
  is_expiring_soon: boolean;
  monthly_value: number;
  invoices: Invoice[];
  paid_invoices_count: number;
  outstanding_amount: number;
  created_at: string;
  updated_at: string;
}

export interface InvoiceLineItem {
  id?: string;
  invoice?: string;
  description: string;
  quantity: number;
  unit_price: number;
  tax_rate: number;
  total: number;
  created_at?: string;
  updated_at?: string;
}

export interface InvoicePayment {
  id: string;
  invoice: string;
  payment_date: string;
  amount: number;
  payment_method: 'Cash' | 'Check' | 'Credit Card' | 'Bank Transfer' | 'Online Payment' | 'Other';
  transaction_id?: string;
  notes?: string;
  created_by: string;
  created_by_name: string;
  created_at: string;
  updated_at: string;
}

export interface Invoice {
  id: string;
  contract: string;
  contract_number: string;
  company: string;
  company_name: string;
  invoice_number: string;
  status: 'Draft' | 'Sent' | 'Paid' | 'Overdue' | 'Cancelled' | 'Refunded' | 'Pending';
  issue_date: string;
  due_date: string;
  paid_date?: string;
  amount: number;
  tax_amount: number;
  discount_amount: number;
  total_amount: number;
  currency: string;
  payment_method?: string;
  payment_terms?: string;
  transaction_id?: string;
  notes?: string;
  days_overdue: number;
  is_overdue: boolean;
  first_reminder_sent: boolean;
  second_reminder_sent: boolean;
  final_notice_sent: boolean;
  line_items: InvoiceLineItem[];
  payments: InvoicePayment[];
  remaining_amount: number;
  created_at: string;
  updated_at: string;
}

export interface DashboardStats {
  total_companies: number;
  active_opportunities: number;
  opportunities_value: number;
  active_contracts: number;
  contracts_value: number;
  overdue_tasks: number;
  overdue_invoices: number;
  pending_renewals: number;
  contacted_count: number;
  quotation_count: number;
  contract_count: number;
  won_count: number;
  lost_count: number;
  monthly_revenue: number;
  monthly_new_opportunities: number;
  monthly_closed_deals: number;
  total_invoices: number;
  total_invoice_amount: number;
  paid_invoice_amount: number;
  pending_invoice_amount: number;
  overdue_invoice_amount: number;
  invoice_collection_rate: number;
}

export interface AuditLog {
  id: string;
  user: string;
  user_name: string;
  action: 'CREATE' | 'UPDATE' | 'DELETE' | 'VIEW' | 'EXPORT' | 'LOGIN' | 'LOGOUT';
  model_name: string;
  record_id: string;
  timestamp: string;
  ip_address?: string;
  user_agent?: string;
  changes?: any;
  additional_data?: any;
}

export interface ApiResponse<T> {
  count: number;
  next?: string;
  previous?: string;
  results: T[];
}

export interface LoginCredentials {
  username: string;
  password: string;
  remember_me?: boolean;
}

export interface AuthResponse {
  access: string;
  refresh: string;
  user: User;
}

export interface RefreshTokenResponse {
  access: string;
}

export interface JWTPayload {
  token_type: string;
  exp: number;
  iat: number;
  jti: string;
  user_id: string;
  username: string;
  role: string;
}

export interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  loading: boolean;
  tokenExpiry: number | null;
}

export interface AuthContextType extends AuthState {
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => Promise<void>;
  refreshAccessToken: () => Promise<void>;
  hasPermission: (permission: string) => boolean;
  hasRole: (role: string | string[]) => boolean;
  isTokenExpired: () => boolean;
}