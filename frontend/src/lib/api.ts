/**
 * API client for the Django REST backend.
 * Set NEXT_PUBLIC_API_URL in .env.local to point elsewhere; defaults to
 * localhost for local dev against `python manage.py runserver`.
 */
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options?.headers || {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${path} failed: ${res.status} ${text}`);
  }
  return res.json();
}

// ---- Types -----------------------------------------------------------

export interface Facility {
  id: number;
  facility_id: string;
  name: string;
  facility_type: "PHC" | "CHC" | "SHC" | "DH";
  state: string;
  district: string;
  latitude: number;
  longitude: number;
  catchment_population: number;
  bed_utilization_pct?: number | null;
}

export interface StockRisk {
  id: number;
  facility: number;
  facility_name: string;
  facility_state: string;
  medicine: number;
  medicine_name: string;
  current_stock: number;
  forecasted_demand_period: number;
  incoming_supply: number;
  projected_stock: number;
  days_of_stock: number;
  expected_stockout_date: string | null;
  shortage_quantity: number;
  risk_score: number;
  risk_level: "low" | "medium" | "high" | "critical";
  explanation: string;
  computed_at: string;
}

export interface RedistributionRecommendation {
  id: number;
  source_facility: number;
  source_facility_name: string;
  destination_facility: number;
  destination_facility_name: string;
  medicine: number;
  medicine_name: string;
  recommended_quantity: number;
  urgency: string;
  reason: string;
  distance_km: number | null;
  status: string;
}

export interface OptimizedRoute {
  id: number;
  origin_facility: number;
  origin_facility_name: string;
  stops: Array<{
    facility_id: string;
    name: string;
    lat: number;
    lon: number;
    eta_hours: number;
    urgency: string;
    medicines: Array<{ medicine: string; quantity: number }>;
  }>;
  total_distance_km: number;
  total_eta_hours: number;
  is_demo_abstraction: boolean;
}

export interface NationalDashboard {
  risk_counts: Record<string, number>;
  total_facilities: number;
  bed_utilization_pct: number;
  doctor_staffing_pct: number;
  top_risks: StockRisk[];
  top_redistribution_recommendations: RedistributionRecommendation[];
  by_state: Array<{ state: string; facility_count: number; critical_risk_count: number }>;
  last_computed: string | null;
}

export interface FederatedRound {
  id: number;
  round_number: number;
  country_updates: Array<{
    country: string;
    local_forecast_error_pct: number;
    sample_size: number;
    delta_vs_previous_round: number;
  }>;
  global_metric: { aggregated_forecast_error_pct: number; method: string };
  is_synthetic_demo: boolean;
}

export interface BricsDashboard {
  rounds: FederatedRound[];
  is_synthetic_demo: boolean;
  disclaimer: string;
}

export interface ForecastPoint {
  date: string;
  predicted_demand: number;
  lower: number;
  upper: number;
}

export interface ForecastResponse {
  facility_id: number;
  medicine_id: number;
  horizon_days: number;
  model_used: string;
  is_demo_fallback: boolean;
  forecast: ForecastPoint[];
}

export interface EmergencySimulationResult {
  surge_pct: number;
  scope_state: string;
  sample_size_facilities: number;
  before: {
    risk_counts: Record<string, number>;
    total_shortage_units: number;
    top_at_risk: Array<{
      facility: string;
      medicine: string;
      risk_level: string;
      risk_score: number;
      days_of_stock: number;
      shortage_quantity: number;
    }>;
  };
  after: EmergencySimulationResult["before"];
  delta: { new_critical: number; new_high: number; additional_shortage_units: number };
}

export interface AiAssistantResponse {
  answer: string;
  source: "gemini" | "fallback";
  grounded_context_size: number;
}

export interface SupplierDashboardResponse {
  suppliers: Array<{
    id: number;
    name: string;
    state: string;
    reliability_score: number;
    avg_lead_time_days: number;
    open_orders: number;
  }>;
}

export interface DealerDashboardResponse {
  shipments: Array<{
    id: number;
    destination_facility_name: string;
    source_facility?: number | null;
    medicine_name: string;
    quantity: number;
    status: string;
    urgency: string;
    distance_km: number | null;
    eta_hours: number | null;
  }>;
}

export interface FacilityDashboardResponse {
  facility: Facility;
  stock_risks: StockRisk[];
}

// ---- API calls ---------------------------------------------------------

export const api = {
  nationalDashboard: () => apiFetch<NationalDashboard>("/dashboard/national/"),
  bricsDashboard: () => apiFetch<BricsDashboard>("/dashboard/brics/"),
  roleDashboard: <T = unknown>(role: string, params?: Record<string, string>) =>
    apiFetch<T>(`/dashboard/${role}/${params ? "?" + new URLSearchParams(params).toString() : ""}`),
  facilities: (params?: Record<string, string>) =>
    apiFetch<{ count: number; results: Facility[] }>(
      `/facilities/${params ? "?" + new URLSearchParams(params).toString() : ""}`
    ),
  stockRisks: (params?: Record<string, string>) =>
    apiFetch<{ count: number; results: StockRisk[] }>(
      `/stock-risks/${params ? "?" + new URLSearchParams(params).toString() : ""}`
    ),
  redistribution: () =>
    apiFetch<{ count: number; results: RedistributionRecommendation[] }>("/redistribution/"),
  routes: () => apiFetch<{ count: number; results: OptimizedRoute[] }>("/routes/"),
  forecast: (facility: number, medicine: number, horizon = 14) =>
    apiFetch<ForecastResponse>(`/forecast/?facility=${facility}&medicine=${medicine}&horizon=${horizon}`),
  runPipeline: (horizonDays = 14) =>
    apiFetch("/pipeline/run/", { method: "POST", body: JSON.stringify({ horizon_days: horizonDays }) }),
  runEmergencySimulation: (surgePct: number, scopeState = "") =>
    apiFetch<EmergencySimulationResult>("/emergency-simulation/", {
      method: "POST",
      body: JSON.stringify({ surge_pct: surgePct, scope_state: scopeState }),
    }),
  askAssistant: (question: string) =>
    apiFetch<AiAssistantResponse>("/ai-assistant/", { method: "POST", body: JSON.stringify({ question }) }),
  datasetStatus: () => apiFetch("/dataset-status/"),
};
