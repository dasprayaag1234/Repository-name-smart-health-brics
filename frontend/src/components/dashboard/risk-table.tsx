"use client";

import { Fragment, useState } from "react";
import { StockRisk } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { ChevronDown, ChevronRight } from "lucide-react";

export function RiskTable({ risks }: { risks: StockRisk[] }) {
  const [expanded, setExpanded] = useState<number | null>(null);

  if (risks.length === 0) {
    return <p className="text-sm text-slate-500 py-6 text-center">No risk data yet — run the pipeline first.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-slate-500 border-b border-slate-800">
            <th className="py-2 pr-4 font-normal"></th>
            <th className="py-2 pr-4 font-normal">Facility</th>
            <th className="py-2 pr-4 font-normal">Medicine</th>
            <th className="py-2 pr-4 font-normal">Risk</th>
            <th className="py-2 pr-4 font-normal">Days of Stock</th>
            <th className="py-2 pr-4 font-normal">Shortage</th>
            <th className="py-2 pr-4 font-normal">Stock-out Date</th>
          </tr>
        </thead>
        <tbody>
          {risks.map((r) => (
            <Fragment key={r.id}>
              <tr
                onClick={() => setExpanded(expanded === r.id ? null : r.id)}
                className="border-b border-slate-800/60 hover:bg-slate-800/40 cursor-pointer transition-colors"
              >
                <td className="py-2.5 pr-2 text-slate-500">
                  {expanded === r.id ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                </td>
                <td className="py-2.5 pr-4 text-slate-200">{r.facility_name}</td>
                <td className="py-2.5 pr-4 text-slate-400">{r.medicine_name}</td>
                <td className="py-2.5 pr-4">
                  <Badge riskLevel={r.risk_level}>{r.risk_level}</Badge>
                </td>
                <td className="py-2.5 pr-4 text-slate-300">{r.days_of_stock ?? "—"}</td>
                <td className="py-2.5 pr-4 text-slate-300">{r.shortage_quantity > 0 ? Math.round(r.shortage_quantity) : "—"}</td>
                <td className="py-2.5 pr-4 text-slate-400">{r.expected_stockout_date ?? "—"}</td>
              </tr>
              {expanded === r.id && (
                <tr className="bg-slate-950/60">
                  <td colSpan={7} className="px-4 py-3 text-slate-400 text-xs leading-relaxed">
                    {r.explanation}
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
