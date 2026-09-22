import { RedistributionRecommendation } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { ArrowRight } from "lucide-react";

export function RedistributionTable({ recs }: { recs: RedistributionRecommendation[] }) {
  if (recs.length === 0) {
    return <p className="text-sm text-slate-500 py-6 text-center">No redistribution opportunities found.</p>;
  }
  return (
    <div className="space-y-3">
      {recs.map((r) => (
        <div key={r.id} className="rounded-lg border border-slate-800 bg-slate-950/40 p-3.5">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-2 text-sm text-slate-200">
              <span className="font-medium">{r.source_facility_name}</span>
              <ArrowRight className="h-3.5 w-3.5 text-slate-500" />
              <span className="font-medium">{r.destination_facility_name}</span>
            </div>
            <Badge riskLevel={r.urgency}>{r.urgency}</Badge>
          </div>
          <div className="mt-1.5 text-xs text-slate-400">
            <span className="text-slate-300">{r.medicine_name}</span> · {r.recommended_quantity} units
            {r.distance_km != null && <> · {r.distance_km} km</>}
          </div>
          <p className="mt-2 text-xs text-slate-500 leading-relaxed">{r.reason}</p>
        </div>
      ))}
    </div>
  );
}
