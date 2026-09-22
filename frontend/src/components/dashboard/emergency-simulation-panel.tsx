"use client";

import { useState } from "react";
import { api, EmergencySimulationResult } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AlertTriangle } from "lucide-react";

export function EmergencySimulationPanel() {
  const [surgePct, setSurgePct] = useState(30);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<EmergencySimulationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.runEmergencySimulation(surgePct);
      setResult(res);
    } catch {
      setError("Could not reach the backend. Is the Django server running?");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-amber-400" />
          Emergency Simulation
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-xs text-slate-500 mb-4">
          Simulate a patient-footfall surge and recalculate demand, stock-out risk and shortages
          across a sample of facilities (before vs. after).
        </p>
        <div className="flex items-center gap-3 mb-4">
          <input
            type="range"
            min={10}
            max={100}
            step={5}
            value={surgePct}
            onChange={(e) => setSurgePct(Number(e.target.value))}
            className="flex-1 accent-sky-500"
          />
          <span className="text-sm font-medium text-slate-200 w-14">+{surgePct}%</span>
          <Button onClick={run} disabled={loading}>
            {loading ? "Simulating..." : "Run"}
          </Button>
        </div>

        {error && <p className="text-sm text-red-400">{error}</p>}

        {result && (
          <div className="grid grid-cols-2 gap-4 mt-2">
            <div className="rounded-lg border border-slate-800 p-3">
              <p className="text-xs text-slate-500 mb-2">Before ({result.sample_size_facilities} facilities sampled)</p>
              <RiskCountRow counts={result.before.risk_counts} />
              <p className="text-xs text-slate-500 mt-2">
                Total shortage: <span className="text-slate-300">{result.before.total_shortage_units} units</span>
              </p>
            </div>
            <div className="rounded-lg border border-amber-900/50 bg-amber-500/5 p-3">
              <p className="text-xs text-slate-500 mb-2">After +{result.surge_pct}% surge</p>
              <RiskCountRow counts={result.after.risk_counts} />
              <p className="text-xs text-slate-500 mt-2">
                Total shortage: <span className="text-amber-300">{result.after.total_shortage_units} units</span>
              </p>
            </div>
            <div className="col-span-2 flex gap-4 text-xs text-slate-400 pt-1">
              <span>New critical: <span className="text-red-400 font-medium">+{result.delta.new_critical}</span></span>
              <span>New high: <span className="text-orange-400 font-medium">+{result.delta.new_high}</span></span>
              <span>Additional shortage: <span className="text-amber-400 font-medium">{result.delta.additional_shortage_units} units</span></span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function RiskCountRow({ counts }: { counts: Record<string, number> }) {
  const order = ["low", "medium", "high", "critical"];
  const colors: Record<string, string> = {
    low: "text-emerald-400", medium: "text-amber-400", high: "text-orange-400", critical: "text-red-400",
  };
  return (
    <div className="flex gap-3 text-xs">
      {order.map((level) => (
        <span key={level} className={colors[level]}>
          {counts[level] ?? 0} {level}
        </span>
      ))}
    </div>
  );
}
