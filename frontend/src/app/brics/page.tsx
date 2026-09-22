"use client";

import { useEffect, useState } from "react";
import { api, BricsDashboard } from "@/lib/api";
import { RoleNav } from "@/components/dashboard/role-nav";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { Globe2, ShieldAlert } from "lucide-react";

const COUNTRY_LABELS: Record<string, string> = {
  india: "India",
  brazil: "Brazil",
  russia: "Russia",
  china: "China",
  south_africa: "South Africa",
};

const COUNTRY_COLORS: Record<string, string> = {
  india: "#38bdf8",
  brazil: "#4ade80",
  russia: "#f87171",
  china: "#fbbf24",
  south_africa: "#c084fc",
};

export default function BricsPage() {
  const [dashboard, setDashboard] = useState<BricsDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.bricsDashboard().then(setDashboard).catch(() => setError("Could not reach the backend."));
  }, []);

  const chartData =
    dashboard?.rounds
      .slice()
      .sort((a, b) => a.round_number - b.round_number)
      .map((r) => {
        const row: Record<string, number | string> = { round: `Round ${r.round_number}` };
        for (const u of r.country_updates) {
          row[u.country] = u.local_forecast_error_pct;
        }
        row.global = r.global_metric.aggregated_forecast_error_pct;
        return row;
      }) ?? [];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">BRICS / Federated Intelligence</h1>
          <p className="text-xs text-slate-500">Cross-nation federated forecasting demo</p>
        </div>
        <RoleNav current="brics" />
      </header>

      <main className="p-6 space-y-6">
        {error && <p className="text-sm text-red-400">{error}</p>}

        {dashboard && (
          <Card className="border-amber-900/40 bg-amber-500/5">
            <CardContent className="pt-5 flex items-start gap-3">
              <ShieldAlert className="h-4 w-4 text-amber-400 mt-0.5 shrink-0" />
              <p className="text-xs text-amber-200/80 leading-relaxed">{dashboard.disclaimer}</p>
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Globe2 className="h-4 w-4 text-sky-400" />
              Federated Forecast Error by Round
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="round" tick={{ fill: "#64748b", fontSize: 11 }} />
                <YAxis tick={{ fill: "#64748b", fontSize: 11 }} unit="%" />
                <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 8, fontSize: 12 }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                {Object.keys(COUNTRY_LABELS).map((c) => (
                  <Line key={c} type="monotone" dataKey={c} name={COUNTRY_LABELS[c]} stroke={COUNTRY_COLORS[c]} strokeWidth={1.5} dot={{ r: 3 }} />
                ))}
                <Line type="monotone" dataKey="global" name="Global (aggregated)" stroke="#e2e8f0" strokeWidth={2.5} dot={{ r: 3 }} strokeDasharray="4 2" />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {dashboard?.rounds
            .slice()
            .sort((a, b) => a.round_number - b.round_number)
            .map((r) => (
              <Card key={r.id}>
                <CardHeader>
                  <CardTitle>Round {r.round_number}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {r.country_updates.map((u) => (
                    <div key={u.country} className="flex items-center justify-between text-xs">
                      <span className="text-slate-300">{COUNTRY_LABELS[u.country]}</span>
                      <span className="text-slate-500">
                        {u.local_forecast_error_pct}% error · {u.sample_size.toLocaleString()} samples
                      </span>
                    </div>
                  ))}
                  <div className="pt-2 border-t border-slate-800 flex items-center justify-between text-xs">
                    <span className="text-slate-200 font-medium">Global aggregate</span>
                    <Badge>{r.global_metric.aggregated_forecast_error_pct}% error</Badge>
                  </div>
                </CardContent>
              </Card>
            ))}
        </div>
      </main>
    </div>
  );
}
