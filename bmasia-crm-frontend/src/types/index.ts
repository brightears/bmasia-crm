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

  // These fields are not in the backend yet but used in frontend for convenience
  first_name?: string; // Computed from name
  last_name?: string; // Computed from name
  mobile?: string; // Not in backend yet
  status?: 'Active' | 'Inactive'; // Mapped from is_active
  is_decision_maker?: boolean; // Derived from contact_type
  preferred_contact_method?: 'Email' | 'Phone' | 'Mobile' | 'LinkedIn'; // Not in backend yet
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

// Equipment Management Types
export interface EquipmentType {
  id: string;
  name: string;
  description: string;
  icon: string;
  equipment_count?: number;
  created_at: string;
  updated_at: string;
}

export interface Equipment {
  id: string;
  equipment_number: string;
  equipment_type: string; // UUID
  equipment_type_name?: string;
  company: string; // UUID
  company_name?: string;
  serial_number: string;
  model_name: string;
  manufacturer: string;
  status: 'active' | 'inactive' | 'maintenance' | 'retired';
  remote_username: string;
  remote_password: string;
  ip_address: string;
  mac_address: string;
  setup_details: string;
  notes: string;
  installed_date: string | null;
  warranty_expiry: string | null;
  history?: EquipmentHistory[];
  created_at: string;
  updated_at: string;
}

export interface EquipmentHistory {
  id: string;
  equipment: string; // UUID
  action: 'installed' | 'maintenance' | 'repair' | 'upgrade' | 'replaced' | 'retired' | 'note';
  description: string;
  performed_by: string | null; // UUID
  performed_by_name?: string;
  performed_at: string;
}