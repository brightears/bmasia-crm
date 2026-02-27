// User Management Types
// New role types for User Management system
export type UserRole = 'Sales' | 'Finance' | 'Tech' | 'Music' | 'Admin';

// Legacy role types (still used in some parts of the app)
export type LegacyUserRole = 'Sales' | 'Marketing' | 'Tech Support' | 'Admin';

export interface User {
  id: string;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name?: string;
  role: UserRole | LegacyUserRole; // Support both for backward compatibility
  phone?: string; // Optional for backward compatibility
  department?: string; // Optional for backward compatibility
  is_active: boolean;
  smtp_email?: string | null; // Optional for backward compatibility
  smtp_configured?: boolean; // Optional for backward compatibility
  avatar_url?: string | null; // Profile image (base64 data URL or external URL)
  last_login?: string | null; // Optional for backward compatibility
  date_joined: string;
  permissions?: string[];
  groups?: string[];
}

export interface UserCreateData {
  username: string;
  email: string;
  password: string;
  first_name?: string;
  last_name?: string;
  role: UserRole;
  phone?: string;
  department?: string;
  is_active?: boolean;
}

export interface UserUpdateData {
  email?: string;
  first_name?: string;
  last_name?: string;
  role?: UserRole;
  phone?: string;
  department?: string;
  is_active?: boolean;
  password?: string;  // Optional for updates
}

export interface PasswordChangeData {
  old_password: string;
  new_password: string;
}

export interface SmtpSettingsData {
  smtp_email: string;
  smtp_password: string;
}

export const USER_ROLE_LABELS: Record<UserRole, string> = {
  Sales: 'Sales',
  Finance: 'Finance',
  Tech: 'Tech Support',
  Music: 'Music Design',
  Admin: 'Administrator',
};

export const USER_ROLE_COLORS: Record<UserRole, string> = {
  Sales: '#4CAF50',      // Green
  Finance: '#2196F3',    // Blue
  Tech: '#FF9800',       // Orange
  Music: '#9C27B0',      // Purple
  Admin: '#F44336',      // Red
};

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
  legal_entity_name?: string;
  country?: string;
  billing_entity?: string;
  website?: string;
  industry?: string;
  location_count: number;
  music_zone_count: number;
  avg_zones_per_location: number;
  annual_revenue?: number;
  is_active: boolean;
  seasonal_emails_enabled?: boolean;
  soundtrack_offline_alerts_enabled?: boolean;
  notes?: string;
  it_notes?: string;
  address_line1?: string;
  address_line2?: string;
  city?: string;
  state?: string;
  postal_code?: string;
  full_address?: string;
  phone?: string;
  email?: string;
  tax_id?: string;
  branch?: string;
  soundtrack_account_id?: string;
  total_contract_value: number;
  contacts: Contact[];
  subscription_plans: SubscriptionPlan[];
  active_subscription_plans: SubscriptionPlan[];
  subscription_summary: string;
  primary_contact?: Contact;
  opportunities_count: number;
  active_contracts_count: number;
  parent_company?: string;
  parent_company_name?: string;
  is_corporate_parent?: boolean;
  is_subsidiary?: boolean;
  child_companies_count?: number;
  created_at: string;
  updated_at: string;
}

export interface Contact {
  id: string;
  company: string;
  company_name: string;
  name: string; // Full name stored in backend
  email: string;
  phone?: string;
  title?: string;
  department?: string;
  contact_type: 'Primary' | 'Technical' | 'Billing' | 'Decision Maker' | 'Other';
  is_primary: boolean;
  is_active: boolean;
  linkedin_url?: string;
  notes?: string;
  last_contacted?: string;
  created_at: string;
  updated_at: string;

  // Granular email preferences (all default to true)
  receives_renewal_emails?: boolean;
  receives_seasonal_emails?: boolean;
  receives_payment_emails?: boolean;
  receives_quarterly_emails?: boolean;
  receives_soundtrack_alerts?: boolean;

  // These fields are not in the backend yet but used in frontend for convenience
  first_name?: string; // Computed from name
  last_name?: string; // Computed from name
  mobile?: string; // Not in backend yet
  status?: 'Active' | 'Inactive'; // Mapped from is_active
  is_decision_maker?: boolean; // Derived from contact_type
  preferred_contact_method?: 'Email' | 'Phone' | 'Mobile' | 'LinkedIn' | '';
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

export interface TaskComment {
  id: string;
  task: string;
  user: string;
  user_name: string;
  comment: string;
  created_at: string;
  updated_at: string;
}

export interface Task {
  id: string;
  company: string;
  company_name: string;
  assigned_to?: string;
  assigned_to_name?: string;
  created_by: string;
  created_by_name: string;
  title: string;
  description: string;
  priority: 'Low' | 'Medium' | 'High' | 'Urgent';
  status: 'To Do' | 'In Progress' | 'Done' | 'Cancelled' | 'On Hold';
  task_type?: 'Call' | 'Email' | 'Follow-up' | 'Meeting' | 'Other';
  due_date?: string;
  completed_at?: string;
  is_overdue: boolean;
  related_opportunity?: string;
  related_opportunity_name?: string;
  related_contract?: string;
  related_contract_number?: string;
  related_contact?: string;
  related_contact_name?: string;
  comments?: TaskComment[];
  created_at: string;
  updated_at: string;
}

export interface Opportunity {
  id: string;
  company: string;
  company_name: string;
  company_billing_entity?: string;
  name: string;
  service_type?: 'soundtrack' | 'beatbreeze' | null;
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

export interface ContractLineItem {
  id?: string;
  product_service: string;
  description: string;
  quantity: number;
  unit_price: number;
  discount_percentage: number;
  tax_rate: number;
  line_total?: number;
}

export interface Contract {
  id: string;
  company: string;
  company_name: string;
  opportunity?: string;
  opportunity_name?: string;
  contract_number: string;
  contract_type: 'Annual' | 'Monthly' | 'One-time' | 'Custom';
  status: 'Draft' | 'Sent' | 'Active' | 'Renewed' | 'Expired' | 'Cancelled';
  start_date: string;
  end_date: string;
  value: number;
  currency: string;
  tax_rate: number;
  tax_amount: number;
  total_value: number;
  auto_renew: boolean;
  renewal_period_months: number;
  is_active: boolean;
  payment_terms?: string;
  billing_frequency: string;
  discount_percentage: number;
  notes?: string;
  renewal_notice_sent: boolean;
  renewal_notice_date?: string;
  send_renewal_reminders?: boolean;
  renewed_from?: string;
  renewed_from_contract_number?: string;
  renewal_count?: number;
  days_until_expiry: number;
  is_expiring_soon: boolean;
  monthly_value: number;
  invoices: Invoice[];
  paid_invoices_count: number;
  outstanding_amount: number;
  contract_zones?: ContractZone[];
  active_zone_count?: number;
  total_zone_count?: number;
  contract_category?: 'standard' | 'corporate_master' | 'participation';
  master_contract?: string;
  master_contract_number?: string;
  customer_signatory_name?: string;
  customer_signatory_title?: string;
  additional_customer_signatories?: Array<{ name: string; title: string }>;
  bmasia_signatory_name?: string;
  bmasia_signatory_title?: string;
  custom_terms?: string;
  participation_agreements_count?: number;
  soundtrack_account_id?: string;
  effective_soundtrack_account_id?: string;
  // Contract Content Management fields
  preamble_template?: string;
  preamble_custom?: string;
  payment_template?: string;
  payment_custom?: string;
  activation_template?: string;
  activation_custom?: string;
  service_items?: string[]; // Array of ServicePackageItem IDs
  custom_service_items?: Array<{ name: string; description: string }>;
  show_zone_pricing_detail?: boolean;
  price_per_zone?: number;
  bmasia_contact_name?: string;
  bmasia_contact_email?: string;
  bmasia_contact_title?: string;
  customer_contact_name?: string;
  customer_contact_email?: string;
  customer_contact_title?: string;
  // Quote and Line Items
  quote?: string | null;
  quote_number?: string | null;
  line_items?: ContractLineItem[];
  // Service Locations (replaces zone picker)
  service_locations?: ServiceLocation[];
  created_at: string;
  updated_at: string;
}

export interface ContractZone {
  id: string;
  contract: string;
  contract_number?: string;
  zone: string;
  zone_id?: string;
  zone_name?: string;
  zone_platform?: 'soundtrack' | 'beatbreeze';
  zone_status?: string;
  company_name?: string;
  start_date: string;
  end_date?: string | null;
  is_active: boolean;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface ServiceLocation {
  id?: string;
  location_name: string;
  platform: 'soundtrack' | 'beatbreeze';
  sort_order?: number;
  created_at?: string;
  updated_at?: string;
}

export interface InvoiceLineItem {
  id?: string;
  invoice?: string;
  product_service?: string;
  description: string;
  quantity: number;
  unit_price: number;
  tax_rate: number;
  total: number;
  line_total?: number;
  service_period_start?: string | null;
  service_period_end?: string | null;
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
  contract: string | null;
  contract_number: string | null;
  company: string;
  company_name: string;
  invoice_number: string;
  status: 'Draft' | 'Sent' | 'Paid' | 'Overdue' | 'Cancelled' | 'Refunded';
  issue_date: string;
  due_date: string;
  paid_date?: string;
  service_period_start?: string | null;
  service_period_end?: string | null;
  amount: number;
  tax_amount: number;
  discount_amount: number;
  total_amount: number;
  currency: string;
  property_name?: string;
  payment_method?: string;
  payment_terms?: string;
  payment_terms_text?: string;
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

export interface PipelineStage {
  count: number;
  value: number;
}

export interface RevenueTrendPoint {
  month: string;
  revenue: number;
  new_revenue?: number;
  renewal_revenue?: number;
  churned_revenue?: number;
  net_revenue?: number;
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
  // Enhanced stats
  win_rate: number;
  previous_month_revenue: number;
  previous_win_rate: number;
  total_overdue_amount: number;
  pending_renewal_value: number;
  pipeline_stages: Record<string, PipelineStage>;
  revenue_trend: RevenueTrendPoint[];
  // Revenue breakdown
  new_revenue: number;
  renewal_revenue: number;
  churned_revenue: number;
  churned_count: number;
  net_revenue: number;
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

export interface QuoteLineItem {
  id?: string;
  quote?: string;
  product_service: string;
  description: string;
  quantity: number;
  unit_price: number;
  discount_percentage: number;
  tax_rate: number;
  line_total: number;
  created_at?: string;
  updated_at?: string;
}

export interface QuoteAttachment {
  id: string;
  quote: string;
  name: string;
  file: string;
  size: number;
  uploaded_by: string;
  uploaded_by_name: string;
  created_at: string;
}

export interface QuoteActivity {
  id: string;
  quote: string;
  user: string;
  user_name: string;
  activity_type: 'Created' | 'Sent' | 'Viewed' | 'Accepted' | 'Rejected' | 'Expired' | 'Updated' | 'Converted';
  description: string;
  created_at: string;
}

export interface Quote {
  id: string;
  quote_number: string;
  company: string;
  company_name: string;
  contact?: string;
  contact_name?: string;
  opportunity?: string;
  opportunity_name?: string;
  status: 'Draft' | 'Sent' | 'Accepted' | 'Rejected' | 'Expired';
  quote_type?: 'new' | 'renewal' | 'addon';
  contract_duration_months?: number;
  valid_from: string;
  valid_until: string;
  subtotal: number;
  tax_amount: number;
  discount_amount: number;
  total_value: number;
  currency: string;
  terms_conditions?: string;
  notes?: string;
  is_expired: boolean;
  days_until_expiry: number;
  acceptance_rate?: number;
  sent_date?: string;
  accepted_date?: string;
  rejected_date?: string;
  expired_date?: string;
  line_items: QuoteLineItem[];
  attachments?: QuoteAttachment[];
  activities?: QuoteActivity[];
  created_by: string;
  created_by_name: string;
  created_at: string;
  updated_at: string;
}

// Sales Target Types
export interface SalesTarget {
  id: string;
  name: string;
  period_type: 'Monthly' | 'Quarterly' | 'Yearly';
  period_start: string;
  period_end: string;
  target_type: 'Revenue' | 'Units' | 'Customers' | 'Contracts';
  target_value: number;
  stretch_target?: number;
  currency: string;
  unit_type?: string; // For non-revenue targets
  assigned_to?: string; // User ID for individual targets
  assigned_to_name?: string;
  team_target: boolean;
  team_name?: string;
  status: 'Active' | 'Completed' | 'Cancelled' | 'Draft';
  current_value: number;
  achievement_percentage: number;
  stretch_achievement_percentage?: number;
  is_on_track: boolean;
  forecasted_value: number;
  forecasted_achievement: number;
  risk_level: 'Low' | 'Medium' | 'High';
  notes?: string;
  justification?: string;
  created_by: string;
  created_by_name: string;
  created_at: string;
  updated_at: string;

  // Calculated fields
  days_remaining: number;
  days_total: number;
  expected_daily_progress: number;
  actual_daily_progress: number;
  variance_from_plan: number;

  // Progress tracking
  daily_progress?: DailyProgress[];
  weekly_progress?: WeeklyProgress[];
  monthly_progress?: MonthlyProgress[];

  // Historical comparison
  previous_period_value?: number;
  previous_period_achievement?: number;
  year_over_year_growth?: number;
}

export interface DailyProgress {
  date: string;
  value: number;
  cumulative_value: number;
  achievement_percentage: number;
  target_pace: number;
  variance: number;
}

export interface WeeklyProgress {
  week_start: string;
  week_end: string;
  value: number;
  cumulative_value: number;
  achievement_percentage: number;
  target_pace: number;
  variance: number;
}

export interface MonthlyProgress {
  month: string;
  value: number;
  cumulative_value: number;
  achievement_percentage: number;
  target_pace: number;
  variance: number;
}

export interface TargetPerformanceMetrics {
  target_id: string;
  total_targets: number;
  achieved_targets: number;
  achievement_rate: number;
  average_achievement_percentage: number;
  best_performing_period: string;
  worst_performing_period: string;
  consistency_score: number;
  trend: 'Improving' | 'Declining' | 'Stable';
}

export interface TeamPerformance {
  team_name: string;
  team_id?: string;
  members: TeamMemberPerformance[];
  total_target: number;
  current_value: number;
  achievement_percentage: number;
  rank: number;
  trend: 'Up' | 'Down' | 'Stable';
}

export interface TeamMemberPerformance {
  user_id: string;
  user_name: string;
  individual_target: number;
  current_value: number;
  achievement_percentage: number;
  rank: number;
  contribution_to_team: number;
  trend: 'Up' | 'Down' | 'Stable';
}

export interface TargetAnalytics {
  total_targets: number;
  active_targets: number;
  achieved_targets: number;
  at_risk_targets: number;
  overall_achievement_rate: number;
  revenue_targets: TargetSummary;
  unit_targets: TargetSummary;
  customer_targets: TargetSummary;
  contract_targets: TargetSummary;
  team_performance: TeamPerformance[];
  individual_performance: IndividualPerformance[];
  monthly_trends: MonthlyTrend[];
  predictions: TargetPrediction[];
}

export interface TargetSummary {
  total_target: number;
  current_value: number;
  achievement_percentage: number;
  targets_count: number;
  at_risk_count: number;
}

export interface IndividualPerformance {
  user_id: string;
  user_name: string;
  total_targets: number;
  achieved_targets: number;
  achievement_rate: number;
  average_achievement_percentage: number;
  current_rank: number;
  trend: 'Up' | 'Down' | 'Stable';
  strongest_target_type: string;
  improvement_area: string;
}

export interface MonthlyTrend {
  month: string;
  total_targets: number;
  achieved_targets: number;
  achievement_rate: number;
  revenue_achieved: number;
  units_achieved: number;
  customers_achieved: number;
  contracts_achieved: number;
}

export interface TargetPrediction {
  target_id: string;
  target_name: string;
  predicted_achievement: number;
  confidence_level: number;
  risk_factors: string[];
  recommended_actions: string[];
  probability_of_success: number;
}

// Email Campaign Types
export interface EmailCampaign {
  id: string;
  name: string;
  campaign_type: 'renewal' | 'payment' | 'quarterly' | 'newsletter' | 'promotion' | 'onboarding' | 'engagement';
  campaign_type_display: string;
  subject: string;
  template: string | null;
  template_name: string | null;
  target_audience: Record<string, any> | null;
  audience_count: number;
  recipients_count: number;
  scheduled_send_date: string | null;
  actual_send_date: string | null;
  status: 'draft' | 'scheduled' | 'sending' | 'sent' | 'paused' | 'cancelled';
  status_display: string;
  send_immediately: boolean;
  sender_email: string;
  reply_to_email: string | null;
  total_sent: number;
  total_delivered: number;
  total_bounced: number;
  total_opened: number;
  total_clicked: number;
  total_unsubscribed: number;
  total_complained: number;
  open_rate: number;
  click_rate: number;
  bounce_rate: number;
  pending_count: number;
  sent_count: number;
  failed_count: number;
  created_at: string;
  updated_at: string;
}

export interface CampaignRecipient {
  id: string;
  campaign: string;
  contact: string;
  contact_name: string;
  contact_email: string;
  contact_company: string;
  email_log: string | null;
  status: 'pending' | 'sent' | 'delivered' | 'bounced' | 'opened' | 'clicked' | 'unsubscribed' | 'failed';
  status_display: string;
  sent_at: string | null;
  delivered_at: string | null;
  opened_at: string | null;
  clicked_at: string | null;
  bounced_at: string | null;
  failed_at: string | null;
  error_message: string;
  created_at: string;
  updated_at: string;
}

export interface EmailCampaignDetail extends EmailCampaign {
  recipients: CampaignRecipient[];
}

// Email Template Types
export interface TemplateVariable {
  name: string;
  description: string;
}

export interface EmailTemplate {
  id: string;
  name: string;
  template_type: string;
  template_type_display?: string;
  language: 'en' | 'th';
  subject: string;
  body_text?: string;  // Auto-generated by backend, read-only
  body_html: string;   // User-edited, required
  is_active: boolean;
  department?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
  variable_list?: TemplateVariable[];  // Array of {name, description} objects from backend
  campaigns_using?: number;
}

// Email Sequence Types
export interface SequenceStep {
  id: string;
  sequence: string;
  step_number: number;
  name: string;
  email_template: string;
  email_template_name: string;
  delay_days: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface EmailSequence {
  id: string;
  name: string;
  description: string;
  status: 'active' | 'paused' | 'archived';
  sequence_type: 'manual' | 'auto_renewal' | 'auto_payment' | 'auto_quarterly';
  trigger_days_before?: number;
  is_system_default: boolean;
  steps: SequenceStep[];
  total_steps: number;
  active_enrollments: number;
  created_by: string;
  created_by_name: string;
  created_at: string;
  updated_at: string;
}

export interface SequenceStepExecution {
  id: string;
  enrollment: string;
  step: string;
  step_name: string;
  contact_email: string;
  scheduled_for: string;
  sent_at: string | null;
  email_log: string | null;
  status: 'pending' | 'scheduled' | 'sent' | 'failed' | 'skipped';
  error_message: string;
  attempt_count: number;
  created_at: string;
  updated_at: string;
}

export interface SequenceEnrollment {
  id: string;
  sequence: string;
  sequence_name: string;
  contact: string;
  contact_name: string;
  contact_email: string;
  company: string | null;
  company_name: string | null;
  enrollment_source: 'manual' | 'auto_trigger';
  trigger_entity_type?: string;
  trigger_entity_id?: string;
  enrolled_at: string;
  started_at: string | null;
  completed_at: string | null;
  status: 'active' | 'paused' | 'completed' | 'unsubscribed';
  current_step_number: number;
  progress: string;
  notes: string;
  step_executions: SequenceStepExecution[];
  created_at: string;
  updated_at: string;
}

// Customer Segments
export interface SegmentFilterRule {
  field: string;
  operator: 'equals' | 'not_equals' | 'contains' | 'not_contains' |
           'starts_with' | 'ends_with' | 'greater_than' | 'greater_than_or_equal' |
           'less_than' | 'less_than_or_equal' | 'between' | 'in_list' |
           'is_empty' | 'is_not_empty';
  value: any;
}

export interface SegmentFilterCriteria {
  entity: 'company' | 'contact';
  match_type: 'all' | 'any';  // AND or OR
  rules: SegmentFilterRule[];
}

export interface CustomerSegment {
  id: string;
  name: string;
  description: string;
  segment_type: 'dynamic' | 'static';
  status: 'active' | 'paused' | 'archived';
  filter_criteria: SegmentFilterCriteria;
  member_count: number;
  last_calculated_at: string | null;
  created_by: string;
  created_by_name?: string;
  tags: string;
  last_used_at: string | null;
  times_used: number;
  member_preview?: Contact[];
  can_edit?: boolean;
  created_at: string;
  updated_at: string;
}

export interface SegmentMemberResponse {
  count: number;
  results: Contact[];
  segment_name: string;
  segment_type: string;
}

export interface SegmentValidationResponse {
  valid: boolean;
  estimated_count?: number;
  preview?: Contact[];
  error?: string;
}

export interface EnrollInSequenceResponse {
  message: string;
  enrolled_count: number;
  skipped_count: number;
  total_members: number;
  errors: string[];
  sequence_name: string;
  segment_name: string;
}

// Support Ticket Types
export interface Ticket {
  id: string;
  ticket_number: string;
  subject: string;
  description: string;
  status: 'new' | 'assigned' | 'in_progress' | 'pending' | 'resolved' | 'closed';
  priority: 'low' | 'medium' | 'high' | 'urgent';
  category: 'technical' | 'billing' | 'zone_config' | 'account' | 'feature_request' | 'general';

  company: string;
  company_name: string;
  contact: string | null;
  contact_name: string | null;
  zone?: string | null;
  zone_name?: string | null;
  zone_platform?: string | null;
  assigned_to: string | null;
  assigned_to_name: string | null;
  assigned_team: string;
  created_by: string | null;
  created_by_name: string | null;

  first_response_at: string | null;
  resolved_at: string | null;
  closed_at: string | null;
  due_date: string | null;

  first_response_time_hours: number | null;
  resolution_time_hours: number | null;
  is_overdue: boolean;

  tags: string;
  comments: TicketComment[];
  attachments: TicketAttachment[];
  comments_count: number;
  internal_notes_count: number;

  created_at: string;
  updated_at: string;
}

export interface TicketComment {
  id: string;
  ticket: string;
  author: string | null;
  author_name: string | null;
  author_role: string | null;
  text: string;
  is_internal: boolean;
  created_at: string;
  updated_at: string;
}

export interface TicketAttachment {
  id: string;
  ticket: string;
  file: string;
  name: string;
  size: number;
  uploaded_by: string | null;
  uploaded_by_name: string | null;
  created_at: string;
}

export interface TicketStats {
  total: number;
  by_status: {
    new: number;
    assigned: number;
    in_progress: number;
    pending: number;
    resolved: number;
    closed: number;
  };
  by_priority: {
    urgent: number;
    high: number;
    medium: number;
    low: number;
  };
  my_open_tickets: number;
  unassigned: number;
  overdue: number;
}

// Knowledge Base Types
export interface KBCategory {
  id: string;
  name: string;
  slug: string;
  description: string;
  parent: string | null;
  icon: string;
  display_order: number;
  is_active: boolean;
  article_count: number;
  full_path: string;
  children?: KBCategory[];
}

export interface KBTag {
  id: string;
  name: string;
  slug: string;
  color: string;
  article_count: number;
}

export interface KBArticle {
  id: string;
  article_number: string;
  title: string;
  slug: string;
  content: string;
  excerpt: string;
  category: {
    id: string;
    name: string;
    slug: string;
  };
  tags: KBTag[];
  status: 'draft' | 'published' | 'archived';
  visibility: 'public' | 'internal';
  author: {
    id: string;
    username: string;
    full_name: string;
  };
  featured: boolean;
  view_count: number;
  helpful_count: number;
  not_helpful_count: number;
  helpfulness_ratio: number;
  published_at: string;
  created_at: string;
  updated_at: string;
  related_articles?: KBArticle[];
  attachments?: KBAttachment[];
}

export interface KBAttachment {
  id: string;
  article: string;
  name: string;
  file: string;
  size: number;
  uploaded_by: string;
  uploaded_by_name: string;
  created_at: string;
}

// Device Management Types (simplified - replaces Equipment)
export interface Device {
  id: string;
  company: string;
  company_name?: string;
  name: string;
  device_type: 'pc' | 'tablet' | 'music_player' | 'other';
  model_info: string;
  notes: string;
  zone_count?: number;
  zones?: Array<{ id: string; name: string }>;
  created_at: string;
  updated_at: string;
}

// Device type display labels
export const DEVICE_TYPE_LABELS: Record<string, string> = {
  pc: 'PC / Computer',
  tablet: 'Tablet',
  music_player: 'Music Player Box',
  other: 'Other',
};

export interface ClientTechDetail {
  id: string;
  company: string;
  company_name?: string;
  zone?: string | null;
  zone_name?: string | null;
  outlet_name: string;
  platform_type: 'soundtrack' | 'beatbreeze' | 'bms' | 'dm' | '';
  syb_account_type?: 'essential' | 'unlimited' | '';
  anydesk_id: string;
  teamviewer_id: string;
  ultraviewer_id: string;
  other_remote_id: string;
  system_type: 'single' | 'multi' | '';
  soundcard_channel: string;
  bms_license: string;
  additional_hardware: string;
  install_date?: string | null;
  commencement_date?: string | null;
  activation_date?: string | null;
  lim_source?: string;
  expiry_date?: string | null;
  pc_name: string;
  pc_make: string;
  pc_model: string;
  pc_type: string;
  operating_system: string;
  os_type: string;
  ram: string;
  cpu_type: string;
  cpu_speed: string;
  cpu_cores: string;
  hdd_c: string;
  hdd_d: string;
  network_type: string;
  amplifiers: string;
  distribution: string;
  speakers: string;
  other_equipment: string;
  music_spec_link: string;
  syb_schedules_link: string;
  comments: string;
  created_at: string;
  updated_at: string;
}

export interface Zone {
  id: string;
  company: string; // UUID
  company_name?: string;
  name: string;
  platform: 'soundtrack' | 'beatbreeze';
  status: 'online' | 'offline' | 'no_device' | 'expired' | 'pending';
  status_display?: string;
  soundtrack_zone_id?: string;
  device?: string; // UUID
  device_name?: string;
  notes?: string;
  current_contract?: {
    id: string;
    contract_number: string;
    status: string;
    start_date: string;
    end_date?: string;
  } | null;
  contract_count?: number;
  last_api_sync?: string | null;
  api_raw_data?: {
    currently_playing?: string;
    device_name?: string;
    is_online?: boolean;
  } | null;
  is_orphaned?: boolean;
  orphaned_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface PreviewZone {
  id: string;
  name: string;
  location_name?: string;
  account_name?: string;
  status: 'online' | 'offline' | 'no_device' | 'pending';
  device_name?: string;
  is_paired?: boolean;
  is_online?: boolean;
}

// Contract Content Management Types
export interface ContractTemplate {
  id: string;
  name: string;
  template_type: 'preamble' | 'service_standard' | 'service_managed' | 'service_custom' |
                 'payment_thailand' | 'payment_international' | 'activation';
  pdf_format: 'standard' | 'corporate_master' | 'participation';
  pdf_format_display?: string;
  content: string;
  is_default: boolean;
  is_active: boolean;
  version: string;
  created_at: string;
  updated_at: string;
}

export interface ServicePackageItem {
  id: string;
  name: string;
  description: string;
  is_standard: boolean;
  display_order: number;
  created_at: string;
}

export interface CorporatePdfTemplate {
  id: string;
  name: string;
  template_format: string;
  include_exhibit_d: boolean;
  include_attachment_a: boolean;
  header_text: string;
  legal_terms: string;
  warranty_text: string;
  use_corporate_branding: boolean;
  company: string; // FK to corporate parent company
  company_name?: string;
}

export interface ContractDocument {
  id: string;
  contract: string;
  document_type: 'generated' | 'principal_terms' | 'attachment_a' | 'exhibit_d' |
                 'master_agreement' | 'participation_agreement' | 'standard_terms' |
                 'insurance' | 'other';
  title: string;
  file: string;
  is_official: boolean;
  is_signed: boolean;
  signed_date?: string;
  uploaded_by?: string;
  uploaded_by_name?: string;
  uploaded_at: string;
  notes?: string;
}

// Settings Types
export interface SeasonalTriggerDate {
  id: string;
  holiday_type: 'auto_seasonal_cny' | 'auto_seasonal_ramadan' | 'auto_seasonal_loy_krathong' |
                'auto_seasonal_diwali' | 'auto_seasonal_mid_autumn' | 'auto_seasonal_eid_fitr';
  holiday_type_display?: string;
  year: number;
  trigger_date: string;  // Date when email campaign is sent (2 weeks before holiday)
  holiday_date: string;  // Actual holiday date
  notes?: string;
  updated_by?: string;
  updated_by_name?: string;
  updated_at?: string;
  created_at?: string;
}

// Revenue Dashboard Types
export type RevenueCategory = 'new' | 'renewal' | 'addon' | 'churn';

export interface MonthlyRevenueData {
  month: number;
  month_name: string;
  new: { count: number; value: number };
  renewal: { count: number; value: number };
  addon: { count: number; value: number };
  churn: { count: number; value: number };
}

// ============================================================================
// Expense Module Types (Phase 3 - Finance Module)
// ============================================================================

export type PaymentTerms = 'immediate' | 'net_15' | 'net_30' | 'net_45' | 'net_60';
export type ExpenseCategoryType = 'opex_cogs' | 'opex_gna' | 'opex_sales' | 'capex';
export type ExpenseStatus = 'draft' | 'pending' | 'approved' | 'paid' | 'cancelled';
export type PaymentMethod = 'bank_transfer' | 'credit_card' | 'cash' | 'cheque' | 'auto_debit';

export interface Vendor {
  id: string;
  name: string;
  legal_name?: string;
  tax_id?: string;
  contact_name?: string;
  email?: string;
  phone?: string;
  website?: string;
  address?: string;
  city?: string;
  country?: string;
  payment_terms: PaymentTerms;
  default_currency: string;
  bank_name?: string;
  bank_account_number?: string;
  bank_account_name?: string;
  is_active: boolean;
  notes?: string;
  billing_entity: 'bmasia_th' | 'bmasia_hk' | 'both';
  created_at: string;
  updated_at: string;
}

export interface ExpenseCategory {
  id: string;
  name: string;
  description?: string;
  category_type: ExpenseCategoryType;
  category_type_display?: string;
  parent_category?: string;
  parent_category_name?: string;
  full_path: string;
  is_depreciable: boolean;
  useful_life_months?: number;
  depreciation_rate?: number;
  sort_order: number;
  is_active: boolean;
  children?: ExpenseCategory[];
  created_at: string;
  updated_at: string;
}

export interface RecurringExpense {
  id: string;
  name: string;
  category: string;
  category_name: string;
  category_full_path?: string;
  vendor?: string;
  vendor_name?: string;
  amount: number;
  currency: string;
  billing_entity: 'bmasia_th' | 'bmasia_hk';
  start_date: string;
  end_date?: string;
  payment_day: number;
  is_active: boolean;
  notes?: string;
  last_generated_month?: string;
  created_at: string;
  updated_at: string;
}

export interface ExpenseEntry {
  id: string;
  description: string;
  category: string;
  category_name: string;
  category_full_path?: string;
  category_type?: ExpenseCategoryType;
  vendor?: string;
  vendor_name?: string;
  recurring_expense?: string;
  recurring_expense_name?: string;
  amount: number;
  currency: string;
  tax_amount: number;
  is_tax_inclusive: boolean;
  billing_entity: 'bmasia_th' | 'bmasia_hk';
  expense_date: string;
  due_date?: string;
  payment_date?: string;
  vendor_invoice_number?: string;
  vendor_invoice_date?: string;
  status: ExpenseStatus;
  status_display?: string;
  payment_method?: PaymentMethod;
  payment_reference?: string;
  approved_at?: string;
  approved_by?: string;
  approved_by_name?: string;
  created_by?: string;
  created_by_name?: string;
  receipt_file?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

// AP Aging Types
export interface APAgingSummary {
  total_ap: number;
  current: number;
  '1_30': number;
  '31_60': number;
  '61_90': number;
  '90_plus': number;
  expense_count: number;
}

export interface APExpenseDetail {
  expense_id: string;
  description: string;
  vendor_id: string;
  vendor_name: string;
  category_id: string;
  category_name: string;
  expense_date: string;
  due_date?: string;
  amount: number;
  currency: string;
  days_overdue: number;
  aging_bucket: 'current' | '1_30' | '31_60' | '61_90' | '90_plus';
  status: ExpenseStatus;
  vendor_invoice_number?: string;
}

export interface APVendorDetail {
  vendor_id: string;
  vendor_name: string;
  total: number;
  current: number;
  '1_30': number;
  '31_60': number;
  '61_90': number;
  '90_plus': number;
  expenses: APExpenseDetail[];
}

export interface APCategoryDetail {
  category_id: string;
  category_name: string;
  category_type: ExpenseCategoryType;
  total: number;
  current: number;
  '1_30': number;
  '31_60': number;
  '61_90': number;
  '90_plus': number;
}

export interface APAgingReport {
  as_of_date: string;
  currency: string;
  billing_entity: string;
  summary: APAgingSummary;
  by_vendor: APVendorDetail[];
  by_category: APCategoryDetail[];
  expenses: APExpenseDetail[];
}

export interface OverdueExpense extends APExpenseDetail {
  priority_score?: number;
}

export interface MonthlyExpenseSummary {
  year: number;
  month?: number;
  currency: string;
  billing_entity: string;
  by_category_type: Array<{
    category_type: ExpenseCategoryType;
    total: number;
    count: number;
    categories: Array<{
      category_id: string;
      category_name: string;
      total: number;
      count: number;
    }>;
  }>;
  totals: {
    cogs: number;
    gna: number;
    sales_marketing: number;
    capex: number;
  };
}

// ====================
// P&L Report Types (Phase 4 - Finance Module)
// ====================

export interface PLRevenueBreakdown {
  new_contracts: number;
  renewals: number;
  addons: number;
  churned: number;
  total: number;
}

export interface PLExpenseBreakdown {
  cogs: number;
  gna: number;
  sales_marketing: number;
  total_opex: number;
}

export interface PLSummary {
  revenue: PLRevenueBreakdown;
  expenses: PLExpenseBreakdown;
  gross_profit: number;
  gross_margin: number;
  operating_profit: number;
  operating_margin: number;
  net_profit: number;
  net_margin: number;
}

export interface PLStatement {
  period: {
    year: number;
    month?: number;
    start_date: string;
    end_date: string;
  };
  currency: string;
  billing_entity: string;
  summary: PLSummary;
  revenue_detail: {
    by_category: Array<{
      category: string;
      amount: number;
      contract_count: number;
    }>;
    total: number;
  };
  expense_detail: {
    cogs: Array<{
      category_id: string;
      category_name: string;
      amount: number;
    }>;
    gna: Array<{
      category_id: string;
      category_name: string;
      amount: number;
    }>;
    sales_marketing: Array<{
      category_id: string;
      category_name: string;
      amount: number;
    }>;
  };
}

export interface PLComparative {
  current: PLStatement;
  previous: PLStatement;
  variance: {
    revenue: {
      amount: number;
      percentage: number;
    };
    gross_profit: {
      amount: number;
      percentage: number;
    };
    operating_profit: {
      amount: number;
      percentage: number;
    };
    net_profit: {
      amount: number;
      percentage: number;
    };
  };
}

export interface PLTrendData {
  month: number;
  month_name: string;
  revenue: number;
  cogs: number;
  gross_profit: number;
  opex: number;
  net_profit: number;
  gross_margin: number;
  net_margin: number;
}

export interface EmailLogEntry {
  id: string;
  from_email: string;
  to_email: string;
  cc_emails: string;
  subject: string;
  status: 'pending' | 'sent' | 'failed' | 'bounced' | 'opened' | 'clicked';
  status_display: string;
  email_type: string;
  email_type_display: string;
  sent_at: string | null;
  opened_at: string | null;
  clicked_at: string | null;
  error_message: string;
  company: string;
  company_name: string;
  contact: string | null;
  contact_name: string | null;
  message_id: string;
  created_at: string;
}

// Sales Automation Types
export interface ProspectSequenceStep {
  id: string;
  step_number: number;
  delay_days: number;
  action_type: 'email' | 'ai_email' | 'task' | 'stage_update';
  email_subject_template: string;
  email_body_template: string;
  ai_prompt_instructions: string;
  task_title_template: string;
  task_type: string;
  stage_to_set: string;
}

export interface ProspectSequence {
  id: string;
  name: string;
  description: string;
  trigger_type: 'manual' | 'new_opportunity' | 'quote_sent' | 'stale_deal';
  target_stages: string[];
  is_active: boolean;
  billing_entity: string;
  max_enrollments_per_company: number;
  stale_days_threshold: number;
  steps: ProspectSequenceStep[];
  active_enrollments: number;
  created_at: string;
  updated_at: string;
}

export interface ProspectEnrollment {
  id: string;
  sequence: string;
  sequence_name: string;
  opportunity: string;
  opportunity_name: string;
  contact: string;
  contact_name: string;
  company_name: string;
  status: 'active' | 'paused' | 'completed' | 'cancelled' | 'replied';
  current_step: number;
  total_steps: number;
  enrolled_at: string;
  paused_at: string | null;
  completed_at: string | null;
  cancelled_at: string | null;
  pause_reason: string;
  enrollment_source: string;
  step_executions?: ProspectStepExecution[];
  created_at: string;
  updated_at: string;
}

export interface ProspectStepExecution {
  id: string;
  enrollment: string;
  step: string;
  step_number: number;
  action_type: string;
  scheduled_for: string;
  executed_at: string | null;
  status: 'pending' | 'pending_approval' | 'sent' | 'skipped' | 'failed' | 'expired';
  has_ai_draft: boolean;
  error_message: string;
  created_at: string;
}

export interface ProspectReply {
  id: string;
  enrollment_id: string;
  sequence_name: string;
  contact_name: string;
  company_name: string;
  opportunity_id: string;
  imap_message_id: string;
  from_email: string;
  subject: string;
  body_text: string;
  received_at: string;
  classification: 'interested' | 'not_interested' | 'question' | 'objection' | 'meeting_request' | 'out_of_office' | 'unsubscribe' | 'referral' | 'bounce' | 'other' | 'unclassified';
  classification_confidence: number;
  classification_method: string;
  enrollment_paused: boolean;
  stage_updated: boolean;
  needs_human_review: boolean;
  created_at: string;
}

export interface AIEmailDraft {
  id: string;
  execution: string;
  subject: string;
  body_html: string;
  status: 'pending_review' | 'approved' | 'rejected' | 'edited' | 'expired';
  reviewer: string | null;
  reviewer_name: string;
  reviewed_at: string | null;
  expires_at: string;
  edited_subject: string;
  edited_body_html: string;
  auto_approved: boolean;
  is_expired: boolean;
  // Denormalized from execution chain
  opportunity_name: string;
  contact_name: string;
  contact_email: string;
  company_name: string;
  sequence_name: string;
  step_number: number;
  created_at: string;
}