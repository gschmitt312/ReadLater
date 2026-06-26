export function fmtUSD(value, { compact = true } = {}) {
  if (value === null || value === undefined) return "—";
  const opts = compact
    ? { notation: "compact", maximumFractionDigits: 2 }
    : { maximumFractionDigits: 0 };
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", ...opts }).format(value);
}

export function fmtNum(value, { compact = false } = {}) {
  if (value === null || value === undefined) return "—";
  const opts = compact
    ? { notation: "compact", maximumFractionDigits: 2 }
    : { maximumFractionDigits: 0 };
  return new Intl.NumberFormat("en-US", opts).format(value);
}

export function fmtPct(value) {
  if (value === null || value === undefined) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
}

export function fmtSignedNum(value) {
  if (value === null || value === undefined || value === 0) return value === 0 ? "0" : "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${fmtNum(value, { compact: true })}`;
}

export function fmtPrice(value) {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(value);
}

const ACTIVITY_LABELS = {
  NEW: "New",
  ADD: "Added",
  REDUCE: "Reduced",
  UNCHANGED: "Held",
  CLOSED: "Closed",
};

export function activityLabel(activity) {
  return ACTIVITY_LABELS[activity] || activity;
}
