import Link from "next/link";

const ROLES = [
  { key: "national", label: "National Admin", href: "/national" },
  { key: "supplier", label: "Supplier", href: "/supplier" },
  { key: "dealer", label: "Dealer", href: "/dealer" },
  { key: "facility", label: "Facility", href: "/facility" },
  { key: "brics", label: "BRICS", href: "/brics" },
];

export function RoleNav({ current }: { current: string }) {
  return (
    <nav className="flex gap-1 text-xs">
      {ROLES.map((r) => (
        <Link
          key={r.key}
          href={r.href}
          className={`px-3 py-1.5 rounded-md transition-colors ${
            current === r.key ? "bg-sky-600/20 text-sky-300" : "text-slate-500 hover:text-slate-300"
          }`}
        >
          {r.label}
        </Link>
      ))}
    </nav>
  );
}
