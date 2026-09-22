"use client";

import { useEffect, useState } from "react";
import { api, Facility, StockRisk, FacilityDashboardResponse } from "@/lib/api";
import { RoleNav } from "@/components/dashboard/role-nav";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { RiskTable } from "@/components/dashboard/risk-table";
import { Hospital } from "lucide-react";

export default function FacilityPage() {
  const [search, setSearch] = useState("");
  const [results, setResults] = useState<Facility[]>([]);
  const [selected, setSelected] = useState<Facility | null>(null);
  const [risks, setRisks] = useState<StockRisk[]>([]);

  useEffect(() => {
    const t = setTimeout(() => {
      if (search.trim().length >= 2) {
        api.facilities({ search }).then((res) => setResults(res.results.slice(0, 8)));
      } else {
        setResults([]);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [search]);

  const selectFacility = async (f: Facility) => {
    setSelected(f);
    setResults([]);
    setSearch("");
    const res = await api.roleDashboard<FacilityDashboardResponse>("facility", { facility: String(f.id) });
    setRisks(res.stock_risks || []);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Facility / Hospital Dashboard</h1>
          <p className="text-xs text-slate-500">Search a facility to see its own stock risk picture</p>
        </div>
        <RoleNav current="facility" />
      </header>

      <main className="p-6 space-y-4">
        <div className="relative max-w-md">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search facility name, state or district..."
            className="w-full rounded-lg bg-slate-900 border border-slate-800 px-3 py-2 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-sky-600"
          />
          {results.length > 0 && (
            <div className="absolute z-10 mt-1 w-full rounded-lg border border-slate-800 bg-slate-900 shadow-xl">
              {results.map((f) => (
                <button
                  key={f.id}
                  onClick={() => selectFacility(f)}
                  className="block w-full text-left px-3 py-2 text-sm text-slate-300 hover:bg-slate-800"
                >
                  {f.name} <span className="text-slate-500 text-xs">— {f.state}, {f.district}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {selected ? (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Hospital className="h-4 w-4 text-sky-400" />
                {selected.name}
              </CardTitle>
              <p className="text-xs text-slate-500">
                {selected.facility_type} · {selected.state}, {selected.district} · Catchment population{" "}
                {selected.catchment_population.toLocaleString()}
              </p>
            </CardHeader>
            <CardContent>
              <RiskTable risks={risks} />
            </CardContent>
          </Card>
        ) : (
          <p className="text-sm text-slate-500">Search for a facility above to view its dashboard.</p>
        )}
      </main>
    </div>
  );
}
