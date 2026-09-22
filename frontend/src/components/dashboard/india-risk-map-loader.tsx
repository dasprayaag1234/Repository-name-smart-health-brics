"use client";

import dynamic from "next/dynamic";
import { Facility, StockRisk } from "@/lib/api";

const IndiaRiskMap = dynamic(() => import("./india-risk-map").then((m) => m.IndiaRiskMap), {
  ssr: false,
  loading: () => (
    <div className="h-[420px] rounded-lg border border-slate-800 flex items-center justify-center text-slate-600 text-sm">
      Loading map...
    </div>
  ),
});

export function IndiaRiskMapLoader(props: { facilities: Facility[]; risksByFacility: Record<number, StockRisk[]> }) {
  return <IndiaRiskMap {...props} />;
}
