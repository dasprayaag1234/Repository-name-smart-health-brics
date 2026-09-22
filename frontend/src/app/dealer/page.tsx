"use client";

import { useEffect, useState } from "react";
import { api, DealerDashboardResponse } from "@/lib/api";
import { RoleNav } from "@/components/dashboard/role-nav";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PackageSearch } from "lucide-react";

type ShipmentRow = DealerDashboardResponse["shipments"][number];

export default function DealerPage() {
  const [shipments, setShipments] = useState<ShipmentRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .roleDashboard<DealerDashboardResponse>("dealer")
      .then((res) => setShipments(res.shipments))
      .catch(() => setError("Could not reach the backend."));
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Dealer / Distributor Dashboard</h1>
          <p className="text-xs text-slate-500">Active and recent shipments</p>
        </div>
        <RoleNav current="dealer" />
      </header>

      <main className="p-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <PackageSearch className="h-4 w-4 text-sky-400" />
              Shipments
            </CardTitle>
          </CardHeader>
          <CardContent>
            {error && <p className="text-sm text-red-400">{error}</p>}
            {shipments.length === 0 && !error && (
              <p className="text-sm text-slate-500 py-6 text-center">
                No shipments yet. Approve redistribution recommendations from the National Admin dashboard to
                generate shipments.
              </p>
            )}
            <div className="space-y-2">
              {shipments.map((s) => (
                <div
                  key={s.id}
                  className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-950/40 px-4 py-3"
                >
                  <div>
                    <p className="text-sm font-medium text-slate-200">
                      {s.medicine_name} → {s.destination_facility_name}
                    </p>
                    <p className="text-xs text-slate-500">{s.quantity} units</p>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-slate-400">
                    {s.distance_km != null && <span>{s.distance_km} km</span>}
                    <Badge riskLevel={s.urgency}>{s.urgency}</Badge>
                    <Badge>{s.status}</Badge>
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
