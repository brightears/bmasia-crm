import { Company, Contact, Opportunity, Contract, ApiResponse } from '../types';

// Mock data for development when backend is not available
export const mockCompanies: Company[] = [
  {
    id: '1',
    name: 'Bangkok Plaza Hotel',
    country: 'Thailand',
    website: 'https://www.bangkokplaza.com',
    industry: 'Hospitality & Tourism',
    location_count: 15,
    music_zone_count: 45,
    avg_zones_per_location: 3,
    annual_revenue: 25000000,
    is_active: true,
    is_corporate_parent: false,
    notes: 'Premium hotel chain in Bangkok with multiple locations',
    address_line1: '123 Sukhumvit Road',
    address_line2: 'Floor 15',
    city: 'Bangkok',
    state: 'Bangkok',
    postal_code: '10110',
    full_address: '123 Sukhumvit Road, Floor 15, Bangkok, Bangkok 10110, Thailand',
    phone: '+66 2 123 4567',
    email: 'info@bangkokplaza.com',
    soundtrack_account_id: 'BPH001',
    total_contract_value: 120000,
    contacts: [],
    subscription_plans: [],
    active_subscription_plans: [],
    subscription_summary: '3 active plans - Soundtrack Unlimited',
    primary_contact: undefined,
    opportunities_count: 2,
    active_contracts_count: 3,
    created_at: '2024-01-15T10:30:00Z',
    updated_at: '2024-09-15T14:20:00Z',
  },
  {
    id: '2',
    name: 'Singapore Retail Group',
    country: 'Singapore',
    website: 'https://www.sgretail.sg',
    industry: 'Retail',
    location_count: 8,
    music_zone_count: 24,
    avg_zones_per_location: 3,
    annual_revenue: 15000000,
    is_active: true,
    is_corporate_parent: false,
    notes: 'Leading retail chain in Singapore',
    address_line1: '456 Orchard Road',
    city: 'Singapore',
    postal_code: '238882',
    full_address: '456 Orchard Road, Singapore 238882',
    phone: '+65 6234 5678',
    email: 'contact@sgretail.sg',
    soundtrack_account_id: 'SRG002',
    total_contract_value: 85000,
    contacts: [],
    subscription_plans: [],
    active_subscription_plans: [],
    subscription_summary: '2 active plans - Soundtrack Essential',
    primary_contact: undefined,
    opportunities_count: 1,
    active_contracts_count: 2,
    created_at: '2024-02-20T09:15:00Z',
    updated_at: '2024-09-10T16:45:00Z',
  },
  {
    id: '3',
    name: 'KL Food Court Network',
    country: 'Malaysia',
    website: 'https://www.klfoodcourt.my',
    industry: 'Restaurant & Food Service',
    location_count: 12,
    music_zone_count: 18,
    avg_zones_per_location: 1.5,
    annual_revenue: 8000000,
    is_active: true,
    is_corporate_parent: false,
    notes: 'Food court operator in Kuala Lumpur',
    address_line1: '789 Jalan Bukit Bintang',
    city: 'Kuala Lumpur',
    state: 'Selangor',
    postal_code: '50450',
    full_address: '789 Jalan Bukit Bintang, Kuala Lumpur, Selangor 50450, Malaysia',
    phone: '+60 3 2345 6789',
    email: 'hello@klfoodcourt.my',
    soundtrack_account_id: 'KFC003',
    total_contract_value: 45000,
    contacts: [],
    subscription_plans: [],
    active_subscription_plans: [],
    subscription_summary: '1 active plan - Beat Breeze',
    primary_contact: undefined,
    opportunities_count: 3,
    active_contracts_count: 1,
    created_at: '2024-03-10T11:00:00Z',
    updated_at: '2024-09-20T13:30:00Z',
  },
];

export const mockContacts: Contact[] = [
  {
    id: '1',
    company: '1',
    company_name: 'Bangkok Plaza Hotel',
    name: 'Somchai Tanaka',
    email: 'somchai@bangkokplaza.com',
    phone: '+66 2 123 4567',
    title: 'General Manager',
    department: 'Operations',
    contact_type: 'Decision Maker',
    is_primary: true,
    is_active: true,
    linkedin_url: 'https://linkedin.com/in/somchai-tanaka',
    notes: 'Primary contact for all music-related decisions',
    last_contacted: '2024-09-15T10:00:00Z',
    created_at: '2024-01-15T10:30:00Z',
    updated_at: '2024-09-15T14:20:00Z',
  },
  {
    id: '2',
    company: '2',
    company_name: 'Singapore Retail Group',
    name: 'Li Wei Chen',
    email: 'liwei@sgretail.sg',
    phone: '+65 6234 5678',
    title: 'Marketing Director',
    department: 'Marketing',
    contact_type: 'Primary',
    is_primary: false,
    is_active: true,
    notes: 'Handles brand experience initiatives',
    preferred_contact_method: 'Phone',
    last_contacted: '2024-09-10T15:30:00Z',
    created_at: '2024-02-20T09:15:00Z',
    updated_at: '2024-09-10T16:45:00Z',
  },
];

export const mockOpportunities: Opportunity[] = [
  {
    id: '1',
    company: '1',
    company_name: 'Bangkok Plaza Hotel',
    name: 'Lobby Music System Upgrade',
    stage: 'Quotation Sent',
    expected_value: 25000,
    probability: 75,
    owner: 'dev-user',
    owner_name: 'Developer User',
    lead_source: 'Referral',
    contact_method: 'Email',
    last_contact_date: '2024-09-15T10:00:00Z',
    follow_up_date: '2024-09-22T10:00:00Z',
    expected_close_date: '2024-10-01T00:00:00Z',
    notes: 'Looking to upgrade music system in main lobby area',
    is_active: true,
    competitors: 'Local AV company',
    pain_points: 'Current system is outdated',
    decision_criteria: 'Quality, cost, ongoing support',
    weighted_value: 18750,
    days_in_stage: 5,
    is_overdue: false,
    activities: [],
    recent_activities: [],
    created_at: '2024-09-01T09:00:00Z',
    updated_at: '2024-09-15T14:20:00Z',
  },
];

export const mockContracts: Contract[] = [
  {
    id: '1',
    company: '1',
    company_name: 'Bangkok Plaza Hotel',
    opportunity: '1',
    opportunity_name: 'Lobby Music System Upgrade',
    contract_number: 'BPH-2024-001',
    contract_type: 'Annual',
    contract_category: 'standard',
    status: 'Active',
    start_date: '2024-01-01T00:00:00Z',
    end_date: '2024-12-31T23:59:59Z',
    value: 120000,
    currency: 'USD',
    tax_rate: 0,
    tax_amount: 0,
    total_value: 120000,
    auto_renew: true,
    renewal_period_months: 12,
    is_active: true,
    payment_terms: 'Net 30',
    billing_frequency: 'Monthly',
    discount_percentage: 0,
    notes: 'Annual contract for music streaming services',
    renewal_notice_sent: false,
    days_until_expiry: 98,
    is_expiring_soon: false,
    monthly_value: 10000,
    invoices: [],
    paid_invoices_count: 8,
    outstanding_amount: 0,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-09-15T14:20:00Z',
  },
];

export class MockApiService {
  // Companies
  static async getCompanies(params?: any): Promise<ApiResponse<Company>> {
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 500));

    let results = [...mockCompanies];

    // Apply search filter
    if (params?.search) {
      const searchTerm = params.search.toLowerCase();
      results = results.filter(company =>
        company.name.toLowerCase().includes(searchTerm) ||
        company.industry?.toLowerCase().includes(searchTerm) ||
        company.country?.toLowerCase().includes(searchTerm)
      );
    }

    // Apply pagination
    const page = params?.page || 1;
    const pageSize = params?.page_size || 25;
    const start = (page - 1) * pageSize;
    const end = start + pageSize;

    return {
      count: results.length,
      next: end < results.length ? `?page=${page + 1}` : undefined,
      previous: page > 1 ? `?page=${page - 1}` : undefined,
      results: results.slice(start, end),
    };
  }

  static async getCompany(id: string): Promise<Company> {
    await new Promise(resolve => setTimeout(resolve, 300));

    const company = mockCompanies.find(c => c.id === id);
    if (!company) {
      throw new Error('Company not found');
    }
    return company;
  }

  static async createCompany(data: Partial<Company>): Promise<Company> {
    await new Promise(resolve => setTimeout(resolve, 800));

    const newCompany: Company = {
      id: String(Date.now()),
      name: data.name || '',
      country: data.country,
      website: data.website,
      industry: data.industry,
      location_count: 0,
      music_zone_count: 0,
      avg_zones_per_location: 0,
      annual_revenue: data.annual_revenue,
      is_active: data.is_active ?? true,
      is_corporate_parent: data.is_corporate_parent ?? false,
      notes: data.notes,
      address_line1: data.address_line1,
      address_line2: data.address_line2,
      city: data.city,
      state: data.state,
      postal_code: data.postal_code,
      full_address: [data.address_line1, data.address_line2, data.city, data.state, data.postal_code, data.country].filter(Boolean).join(', '),
      phone: data.phone,
      email: data.email,
      soundtrack_account_id: data.soundtrack_account_id,
      total_contract_value: 0,
      contacts: [],
      subscription_plans: [],
      active_subscription_plans: [],
      subscription_summary: 'No active subscriptions',
      primary_contact: undefined,
      opportunities_count: 0,
      active_contracts_count: 0,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    mockCompanies.push(newCompany);
    return newCompany;
  }

  static async updateCompany(id: string, data: Partial<Company>): Promise<Company> {
    await new Promise(resolve => setTimeout(resolve, 800));

    const companyIndex = mockCompanies.findIndex(c => c.id === id);
    if (companyIndex === -1) {
      throw new Error('Company not found');
    }

    const updatedCompany = {
      ...mockCompanies[companyIndex],
      ...data,
      updated_at: new Date().toISOString(),
    };

    mockCompanies[companyIndex] = updatedCompany;
    return updatedCompany;
  }

  // Contacts
  static async getContacts(params?: any): Promise<ApiResponse<Contact>> {
    await new Promise(resolve => setTimeout(resolve, 400));

    let results = [...mockContacts];

    if (params?.company) {
      results = results.filter(contact => contact.company === params.company);
    }

    return {
      count: results.length,
      next: undefined,
      previous: undefined,
      results,
    };
  }

  // Opportunities
  static async getOpportunities(params?: any): Promise<ApiResponse<Opportunity>> {
    await new Promise(resolve => setTimeout(resolve, 400));

    let results = [...mockOpportunities];

    if (params?.company) {
      results = results.filter(opp => opp.company === params.company);
    }

    return {
      count: results.length,
      next: undefined,
      previous: undefined,
      results,
    };
  }

  // Contracts
  static async getContracts(params?: any): Promise<ApiResponse<Contract>> {
    await new Promise(resolve => setTimeout(resolve, 400));

    let results = [...mockContracts];

    if (params?.company) {
      results = results.filter(contract => contract.company === params.company);
    }

    return {
      count: results.length,
      next: undefined,
      previous: undefined,
      results,
    };
  }
}