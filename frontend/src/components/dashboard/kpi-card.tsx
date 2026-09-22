import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LucideIcon } from "lucide-react";

export function KpiCard({
  title,
  value,
  suffix,
  icon: Icon,
  tone = "default",
}: {
  title: string;
  value: string | number;
  suffix?: string;
  icon?: LucideIcon;
  tone?: "default" | "critical" | "good";
}) {
  const toneColor =
    tone === "critical" ? "text-red-400" : tone === "good" ? "text-emerald-400" : "text-slate-100";
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-1">
        <CardTitle>{title}</CardTitle>
        {Icon && <Icon className="h-4 w-4 text-slate-500" />}
      </CardHeader>
      <CardContent>
        <div className={`text-2xl font-semibold ${toneColor}`}>
          {value}
          {suffix && <span className="text-sm font-normal text-slate-400 ml-1">{suffix}</span>}
        </div>
      </CardContent>
    </Card>
  );
}
