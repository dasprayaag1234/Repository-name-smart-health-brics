import { cn } from "@/lib/utils";
import { HTMLAttributes } from "react";

const RISK_STYLES: Record<string, string> = {
  low: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  medium: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  high: "bg-orange-500/15 text-orange-400 border-orange-500/30",
  critical: "bg-red-500/15 text-red-400 border-red-500/30",
};

export function Badge({
  className,
  riskLevel,
  ...props
}: HTMLAttributes<HTMLSpanElement> & { riskLevel?: string }) {
  const riskClass = riskLevel ? RISK_STYLES[riskLevel] ?? "" : "";
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize",
        riskLevel ? riskClass : "bg-slate-700/40 text-slate-300 border-slate-600/40",
        className
      )}
      {...props}
    />
  );
}
