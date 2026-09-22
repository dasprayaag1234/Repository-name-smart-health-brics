"use client";

import { useEffect, useState } from "react";
import { api, NationalDashboard, Facility, StockRisk } from "@/lib/api";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { RiskTable } from "@/components/dashboard/risk-table";
import { RedistributionTable } from "@/components/dashboard/redistribution-table";
import { EmergencySimulationPanel } from "@/components/dashboard/emergency-simulation-panel";
import { AiAssistantPanel } from "@/components/dashboard/ai-assistant-panel";
import { IndiaRiskMapLoader } from "@/components/dashboard/india-risk-map-loader";
import { RoleNav } from "@/components/dashboard/role-nav";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Activity, Building2, BedDouble, Stethoscope, RefreshCw } from "lucide-react";

export default function NationalAdminPage() {
  const [dashboard, setDashboard] = useState<NationalDashboard | null>(null);
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [risksByFacility, setRisksByFacility] = useState<Record<number, StockRisk[]>>({});
  const [error, setError] = useState<string | null>(null);
  const [pipelineRunning, setPipelineRunning] = useState(false);

  const load = async () => {
    setError(null);
    try {
      const [dash, facRes, riskRes] = await Promise.all([
        api.nationalDashboard(),
        api.facilities(),
        api.stockRisks({ risk_level: "high" }), // trimmed below with critical too
      ]);
      const criticalRes = await api.stockRisks({ risk_level: "critical" });
      const allRisks = [...riskRes.results, ...criticalRes.results];
      const grouped: Record<number, StockRisk[]> = {};
      for (const r of allRisks) {
        grouped[r.facility] = grouped[r.facility] || [];
        grouped[r.facility].push(r);
      }
      setDashboard(dash);
      setFacilities(facRes.results);
      setRisksByFacility(grouped);
    } catch {
      setError(
        "Could not reach the backend at " +
          (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api") +
          " — make sure `python manage.py runserver` is running."
      );
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initial data fetch on mount
    load();
  }, []);

  const runPipeline = async () => {
    setPipelineRunning(true);
    try {
      await api.runPipeline();
      await load();
    } finally {
      setPipelineRunning(false);
    }
  };

  if (error) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center p-6">
        <Card className="max-w-md">
          <CardContent className="pt-5 text-sm text-slate-400">{error}</CardContent>
        </Card>
      </div>
    );
  }

  if (!dashboard) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center text-slate-500 text-sm">
        Loading national dashboard...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">National Health Command Center</h1>
          <p className="text-xs text-slate-500">Smart Health & Supply Chain Resilience — Track 3</p>
        </div>
        <div className="flex items-center gap-3">
          <RoleNav current="national" />
          <Button variant="outline" onClick={runPipeline} disabled={pipelineRunning}>
            <RefreshCw className={`h-3.5 w-3.5 ${pipelineRunning ? "animate-spin" : ""}`} />
            {pipelineRunning ? "Recomputing..." : "Recompute Pipeline"}
          </Button>
        </div>
      </header>

      <main className="p-6 space-y-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KpiCard title="Facilities" value={dashboard.total_facilities} icon={Building2} />
          <KpiCard
            title="Critical Risk Items"
            value={dashboard.risk_counts.critical ?? 0}
            icon={Activity}
            tone="critical"
          />
          <KpiCard title="Bed Utilization" value={dashboard.bed_utilization_pct} suffix="%" icon={BedDouble} />
          <KpiCard title="Doctor Staffing" value={dashboard.doctor_staffing_pct} suffix="%" icon={Stethoscope} />
        </div>

        <Card>
          <CardHeader>
            <CardTitle>National Facility Risk Map</CardTitle>
          </CardHeader>
          <CardContent>
            <IndiaRiskMapLoader facilities={facilities} risksByFacility={risksByFacility} />
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Top Stock-Out Risks</CardTitle>
            </CardHeader>
            <CardContent>
              <RiskTable risks={dashboard.top_risks} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Redistribution Recommendations</CardTitle>
            </CardHeader>
            <CardContent>
              <RedistributionTable recs={dashboard.top_redistribution_recommendations} />
            </CardContent>
          </Card>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <EmergencySimulationPanel />
          <AiAssistantPanel />
        </div>
      </main>
    </div>
  );
}
