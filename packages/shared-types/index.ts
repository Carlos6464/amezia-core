export type UserRole = 'user' | 'admin';
export type UserLanguage = 'pt-BR' | 'en';

export interface User {
  id: string;
  name: string;
  email: string;
  phone: string | null;
  role: UserRole;
  language: UserLanguage;
  oauth_provider: string | null;
  has_password: boolean;
  onboarding_completed: boolean;
  last_login_at: string | null;
  created_at: string;
}

export interface SetPasswordRequest {
  new_password: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  name: string;
  email: string;
  password: string;
}

export interface GoogleLoginRequest {
  id_token: string;
}

export interface AuthTokensResponse {
  user: User;
  access_token: string;
  token_type: string;
}

export interface RefreshResponse {
  access_token: string;
  token_type: string;
}

export interface UpdateProfileRequest {
  name?: string;
  phone?: string;
  language?: UserLanguage;
}

export interface UpdateOnboardingRequest {
  onboarding_completed: boolean;
}

export interface BotInfo {
  phone_number: string | null;
  is_available: boolean;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export interface RequestPasswordResetRequest {
  email: string;
}

export interface ResetPasswordRequest {
  token: string;
  new_password: string;
}

export type CategoryScope = 'global' | 'private';

export interface Category {
  public_id: string;
  name: string;
  color: string;
  icon: string;
  scope: CategoryScope;
  is_system: boolean;
  created_at: string;
  transaction_count: number;
  total_amount: string;
}

export interface CategoryCreateRequest {
  name: string;
  color: string;
  icon: string;
}

export interface CategoryUpdateRequest {
  name?: string;
  color?: string;
  icon?: string;
}

export type TransactionType = 'income' | 'expense';
export type PaymentStatus = 'pending' | 'paid';
export type RecurrenceFrequency = 'weekly' | 'monthly' | 'yearly';

export interface CategorySummary {
  public_id: string;
  name: string;
  color: string;
}

export interface Installment {
  group_id: string;
  number: number;
  total: number;
}

export interface Transaction {
  public_id: string;
  type: TransactionType;
  amount: string;
  description: string;
  date: string;
  status: PaymentStatus;
  payment_method: string | null;
  paid_at: string | null;
  category: CategorySummary;
  receipt_url: string | null;
  installment: Installment | null;
  is_recurring: boolean;
  created_at: string;
  updated_at: string;
}

export interface InstallmentInput {
  total: number;
}

export interface RecurrenceInput {
  frequency: RecurrenceFrequency;
  end_date: string | null;
}

export interface TransactionCreateRequest {
  category_id: string;
  amount: string;
  description: string;
  date: string;
  status?: PaymentStatus;
  payment_method?: string | null;
  installment?: InstallmentInput;
  recurrence?: RecurrenceInput;
}

export interface TransactionUpdateRequest {
  category_id?: string;
  amount?: string;
  description?: string;
  date?: string;
  status?: PaymentStatus;
  payment_method?: string | null;
  paid_at?: string | null;
}

export interface PaginationInfo {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface TransactionSummary {
  total_amount: string;
  count: number;
  budget_limit: string | null;
  budget_used_percentage: number | null;
}

export interface TransactionListResponse {
  items: Transaction[];
  pagination: PaginationInfo;
  summary: TransactionSummary;
}

export interface BulkDeleteRequest {
  public_ids: string[];
}

export interface BulkDeleteResponse {
  deleted_count: number;
  requested_count: number;
}

export interface RecurrenceRule {
  public_id: string;
  type: TransactionType;
  amount: string;
  description: string;
  category: CategorySummary;
  frequency: RecurrenceFrequency;
  start_date: string;
  end_date: string | null;
  next_occurrence_date: string;
}

export interface BudgetResponse {
  monthly_budget: string | null;
}

export interface BudgetUpdateRequest {
  monthly_budget: string | null;
}

export type ConversationChannel = 'web' | 'whatsapp';
export type MessageRole = 'user' | 'assistant';
export type AiProvider = 'gemini' | 'grok';

export interface Conversation {
  public_id: string;
  title: string | null;
  channel: ConversationChannel;
  last_message_at: string | null;
  last_message_preview: string | null;
  created_at: string;
}

export interface ConversationMessage {
  public_id: string;
  role: MessageRole;
  content: string;
  provider_used: AiProvider | null;
  created_at: string;
}

export interface ConversationListResponse {
  items: Conversation[];
  pagination: PaginationInfo;
}

export interface MessageListResponse {
  items: ConversationMessage[];
  pagination: PaginationInfo;
}

export interface MessageCreateRequest {
  content: string;
}

export interface MessageAcceptedResponse {
  conversation_public_id: string;
  message_id: string;
  status: string;
}

export interface AiMessageReadyEvent {
  event: 'ai_message_ready';
  conversation_public_id: string;
  message: ConversationMessage;
}

export interface AiResponseFailedEvent {
  event: 'ai_response_failed';
  conversation_public_id: string;
  user_message_id: string;
  error: string;
}

export interface ReportsPeriodRange {
  date_from: string;
  date_to: string;
}

export interface ReportsTopCategory {
  category_id: string;
  name: string;
  total: string;
  percentage: number;
}

export interface ReportsBiggestTransaction {
  public_id: string;
  description: string;
  amount: string;
  category_name: string;
  occurred_at: string;
}

export interface FinancialSummary {
  period: ReportsPeriodRange;
  total_expense: string;
  transaction_count: number;
  top_category: ReportsTopCategory | null;
  biggest_transaction: ReportsBiggestTransaction | null;
}

export interface MonthlyEvolutionPoint {
  year: number;
  month: number;
  total_expense: string;
}

export interface CategoryDistributionItem {
  category_id: string;
  name: string;
  color: string;
  total: string;
  percentage: number;
}

export interface MonthlyPaidPendingPoint {
  year: number;
  month: number;
  total_paid: string;
  total_pending: string;
}

export interface PaymentMethodDistributionItem {
  payment_method: string;
  total: string;
  percentage: number;
}

export type DashboardCard =
  | 'monthly_trend'
  | 'category_composition'
  | 'category_distribution'
  | 'recent_transactions'
  | 'payment_method_distribution'
  | 'paid_pending';

export interface DashboardCardPreference {
  card: DashboardCard;
  visible: boolean;
}

export interface DashboardLayoutResponse {
  layout: DashboardCardPreference[] | null;
}

export interface UpdateDashboardLayoutRequest {
  layout: DashboardCardPreference[];
}

export interface ReportTransaction {
  public_id: string;
  occurred_at: string;
  description: string;
  category_id: string;
  category_name: string;
  amount: string;
}

export interface ReportsPaginationInfo {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface PaginatedTransactionsResponse {
  items: ReportTransaction[];
  pagination: ReportsPaginationInfo;
}

export interface NarrativeRequest {
  date_from: string;
  date_to: string;
  category_id?: string | null;
}

export interface NarrativeQueuedResponse {
  status: string;
}

export interface ReportNarrativeReadyEvent {
  event: 'report.narrative.ready';
  payload: {
    narrative: string;
    period: ReportsPeriodRange;
    language: UserLanguage;
    generated_at: string;
  };
}

export interface ReportNarrativeFailedEvent {
  event: 'report.narrative.failed';
  payload: {
    reason: string;
  };
}

// --- Admin (build-context-06) ---

export interface AdminPaginatedResponse<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface AdminLoginRequest {
  email: string;
  password: string;
}

export interface MonthlyUserPoint {
  month: string;
  count: number;
}

export interface PlanDistribution {
  free: number;
  pro: number;
  premium: number;
  trial_pro: number;
}

export interface UsageByChannel {
  web: number;
  whatsapp: number;
}

export interface AdminStats {
  total_users: number;
  users_with_phone: number;
  total_feedbacks: number;
  new_users_by_month: MonthlyUserPoint[];
  active_users_daily: number;
  active_users_monthly: number;
  subscriptions_by_plan: PlanDistribution;
  mrr_cents: number;
  churn_rate: number;
  usage_by_channel: UsageByChannel;
}

// --- Admin: atividade recente (build-context-11) ---

export interface AdminActivityEvent {
  id: string;
  event_type: string;
  user_id: string | null;
  message: string;
  created_at: string;
}

export interface AdminActivityListResponse {
  items: AdminActivityEvent[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

// --- Admin: pagamentos (build-context-11) ---

export interface AdminPaymentEvent {
  id: string;
  stripe_event_id: string;
  event_type: string;
  user_id: string | null;
  amount_cents: number | null;
  currency: string | null;
  created_at: string;
}

export interface AdminPaymentsResponse {
  mrr_cents: number;
  arr_cents: number;
  churn_rate: number;
  average_ticket_cents: number;
  past_due_count: number;
  recent_payments: AdminPaymentEvent[];
  recent_stripe_events: AdminPaymentEvent[];
}

export interface AdminUser {
  id: string;
  name: string;
  email: string;
  phone: string | null;
  role: UserRole;
  language: UserLanguage;
  created_at: string;
  last_login_at: string | null;
  effective_plan: Plan | null;
  is_admin_test_access: boolean;
}

export interface ChangeUserRoleRequest {
  role: UserRole;
}

export interface SetTestAccessRequest {
  enabled: boolean;
}

export type EvolutionConnectionStatus = 'connecting' | 'connected' | 'disconnected';

export interface EvolutionInstance {
  public_id: string;
  name: string;
  phone_number: string | null;
  status: EvolutionConnectionStatus;
  qr_code: string | null;
  qr_code_expires_at: string | null;
  webhook_url: string;
  webhook_secret_masked: string;
  webhook_events: string[];
  is_active: boolean;
  connected_at: string | null;
  last_message_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface EvolutionInstanceCreateRequest {
  name: string;
  webhook_url: string;
}

export interface EvolutionInstanceUpdateRequest {
  name?: string;
  webhook_url?: string;
  is_active?: boolean;
}

export type FeedbackChannel = 'web' | 'whatsapp';
export type FeedbackType = 'praise' | 'suggestion' | 'bug' | 'other';

export interface FeedbackUserSummary {
  id: string;
  name: string;
  email: string;
}

export interface AdminFeedback {
  id: string;
  message: string;
  channel: FeedbackChannel;
  type: FeedbackType;
  nps_score: number | null;
  subject: string | null;
  user: FeedbackUserSummary | null;
  created_at: string;
}

export interface Feedback {
  id: string;
  channel: FeedbackChannel;
  type: FeedbackType;
  nps_score: number | null;
  subject: string | null;
  message: string;
  created_at: string;
}

export interface FeedbackCreateRequest {
  message: string;
  type?: FeedbackType;
  nps_score?: number;
  subject?: string;
}

export interface FeedbackListResponse {
  items: Feedback[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

// --- Subscription (build-context-09) ---

export type Plan = 'free' | 'pro' | 'premium';
export type PaidPlan = 'pro' | 'premium';
export type BillingCycle = 'monthly' | 'annual';
export type SubscriptionStatus = 'trialing' | 'active' | 'past_due' | 'canceled' | 'incomplete';

export interface Subscription {
  id: string;
  plan: Plan;
  effective_plan: Plan;
  billing_cycle: BillingCycle | null;
  status: SubscriptionStatus;
  current_period_end: string | null;
  trial_ends_at: string | null;
  is_admin_test_access: boolean;
}

export interface PlanLimits {
  plan: Plan;
  ai_conversations_per_month: number | null;
  ai_reports_per_month: number | null;
  whatsapp_bot_messages_per_month: number | null;
  csv_exports_per_month: number | null;
  priority_support_enabled: boolean;
}

export interface GetMySubscriptionResponse {
  subscription: Subscription;
  plan_limits: PlanLimits;
}

export interface CheckoutRequest {
  plan: PaidPlan;
  billing_cycle: BillingCycle;
}

export interface CheckoutResponse {
  checkout_url: string | null;
  subscription: Subscription | null;
}

export interface BillingPortalResponse {
  url: string;
}

export interface PlanCatalogPrice {
  unit_amount_cents: number;
  currency: string;
}

export interface PlanCatalogEntry {
  plan: Plan;
  limits: PlanLimits;
  monthly: PlanCatalogPrice | null;
  annual: PlanCatalogPrice | null;
}

export interface PlanCatalogResponse {
  free: PlanCatalogEntry;
  pro: PlanCatalogEntry;
  premium: PlanCatalogEntry;
}

// --- Admin: gestão de preços dos planos (build-context-09, painel Admin) ---

export interface AdminPlanPrice {
  id: string;
  plan: PaidPlan;
  billing_cycle: BillingCycle;
  stripe_price_id: string;
  unit_amount_cents: number;
  currency: string;
  active: boolean;
  created_at: string;
}

export interface CreatePlanPriceRequest {
  billing_cycle: BillingCycle;
  unit_amount_cents: number;
  currency?: string;
}

export interface AdminPlanPricesCatalogResponse {
  pro: AdminPlanPrice[];
  premium: AdminPlanPrice[];
}

// --- AI Usage (build-context-10) ---

export type AiFeature =
  | 'agent_chat'
  | 'report_narrative'
  | 'bot_expense_parsing'
  | 'bot_audio_transcription';

export interface MonthlyUsagePoint {
  month: string;
  ai_conversations: number;
  ai_reports: number;
}

export interface GetMyAiUsageResponse {
  plan: Plan;
  cycle_start: string;
  ai_conversations_used: number;
  ai_conversations_limit: number | null;
  ai_reports_used: number;
  ai_reports_limit: number | null;
  history: MonthlyUsagePoint[];
}

// --- Admin: uso e custo de IA (build-context-10) ---

export interface FeatureUsageTotal {
  feature: AiFeature;
  event_count: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_cents: number;
}

export interface ProviderUsageTotal {
  provider: AiProvider;
  event_count: number;
  estimated_cost_cents: number;
}

export interface AdminTopConsumer {
  user_id: string;
  name: string;
  email: string;
  plan: Plan;
  ai_conversations: number;
  ai_reports: number;
  estimated_cost_cents: number;
}

export interface AdminAiUsageOverviewResponse {
  since: string;
  total_input_tokens: number;
  total_output_tokens: number;
  total_estimated_cost_cents: number;
  by_feature: FeatureUsageTotal[];
  by_provider: ProviderUsageTotal[];
  top_consumers: AdminTopConsumer[];
}
