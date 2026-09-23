"use client";

import { MapContainer, TileLayer, CircleMarker, Popup } from "react-leaflet";
import { Facility, StockRisk } from "@/lib/api";
import "leaflet/dist/leaflet.css";

const RISK_COLOR: Record<string, string> = {
  low: "#10b981",
  medium: "#f59e0b",
  high: "#f97316",
  critical: "#ef4444",
};

export function IndiaRiskMap({ facilities, risksByFacility }: {
  facilities: Facility[];
  risksByFacility: Record<number, StockRisk[]>;
}) {
  return (
    <div className="h-[420px] rounded-lg overflow-hidden border border-slate-800">
      <MapContainer center={[22.5, 80]} zoom={4.5} style={{ height: "100%", width: "100%", background: "#0f172a" }}>
<TileLayer
  url={`https://{s}.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}.png?key=${process.env.NEXT_PUBLIC_CARTO_API_KEY}`}
  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
  subdomains={["a", "b", "c", "d"]}
  maxZoom={20}
/>
        {facilities.map((f) => {
          const risks = risksByFacility[f.id] || [];
          const worst = risks.reduce<string>((acc, r) => {
            const order = ["low", "medium", "high", "critical"];
            return order.indexOf(r.risk_level) > order.indexOf(acc) ? r.risk_level : acc;
          }, "low");
          return (
            <CircleMarker
              key={f.id}
              center={[f.latitude, f.longitude]}
              radius={5}
              pathOptions={{ color: RISK_COLOR[worst], fillColor: RISK_COLOR[worst], fillOpacity: 0.7, weight: 1 }}
            >
              <Popup>
                <div className="text-xs">
                  <strong>{f.name}</strong>
                  <br />
                  {f.state}, {f.district}
                  <br />
                  {risks.length > 0 ? `${risks.length} medicine(s) at risk` : "No risk data"}
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>
    </div>
  );
}
