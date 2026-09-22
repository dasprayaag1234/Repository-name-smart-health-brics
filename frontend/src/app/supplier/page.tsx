"use client";

import { useEffect, useState } from "react";
import { api, SupplierDashboardResponse } from "@/lib/api";
import { RoleNav } from "@/components/dashboard/role-nav";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Truck } from "lucide-react";

type SupplierRow = SupplierDashboardResponse["suppliers"][number];

export default function SupplierPage() {
  const [suppliers, setSuppliers] = useState<SupplierRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .roleDashboard<SupplierDashboardResponse>("supplier")
      .then((res) => setSuppliers(res.suppliers))
      .catch(() => setError("Could not reach the backend."));
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Supplier Dashboard</h1>
          <p className="text-xs text-slate-500">Reliability, lead time and open order volume</p>
        </div>
        <RoleNav current="supplier" />
      </header>

      <main className="p-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Truck className="h-4 w-4 text-sky-400" />
              Suppliers
            </CardTitle>
          </CardHeader>
          <CardContent>
            {error && <p className="text-sm text-red-400">{error}</p>}
            <div className="space-y-2">
              {suppliers.map((s) => (
                <div
                  key={s.id}
                  className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-950/40 px-4 py-3"
                >
                  <div>
                    <p className="text-sm font-medium text-slate-200">{s.name}</p>
                    <p className="text-xs text-slate-500">{s.state}</p>
                  </div>
                  <div className="flex items-center gap-6 text-xs text-slate-400">
                    <span>Reliability: <span className="text-slate-200">{Math.round(s.reliability_score * 100)}%</span></span>
                    <span>Lead time: <span className="text-slate-200">{s.avg_lead_time_days}d</span></span>
                    <Badge>{s.open_orders} open orders</Badge>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
