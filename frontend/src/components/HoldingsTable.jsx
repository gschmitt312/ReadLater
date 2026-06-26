import React, { useMemo, useState } from "react";
import {
  activityLabel,
  fmtNum,
  fmtPct,
  fmtPrice,
  fmtSignedNum,
  fmtUSD,
} from "../format.js";

const COLUMNS = [
  { key: "ticker", label: "Ticker", align: "left" },
  { key: "name", label: "Name", align: "left" },
  { key: "shares", label: "Shares", align: "right", num: true },
  { key: "value_usd", label: "Value", align: "right", num: true },
  { key: "pct_of_portfolio", label: "% Port.", align: "right", num: true },
  { key: "price", label: "Price", align: "right", num: true },
  { key: "implied_value", label: "Implied Value", align: "right", num: true },
  { key: "price_change_pct", label: "Δ Price", align: "right", num: true },
  { key: "activity", label: "Activity", align: "left" },
  { key: "shares_delta", label: "Δ Shares", align: "right", num: true },
];

const ACTIVITY_FILTERS = ["ALL", "NEW", "ADD", "REDUCE", "UNCHANGED"];

export default function HoldingsTable({ positions }) {
  const [sortKey, setSortKey] = useState("value_usd");
  const [sortDir, setSortDir] = useState("desc");
  const [query, setQuery] = useState("");
  const [activity, setActivity] = useState("ALL");

  const filtered = useMemo(() => {
    let rows = positions;
    if (activity !== "ALL") rows = rows.filter((r) => r.activity === activity);
    const q = query.trim().toLowerCase();
    if (q) {
      rows = rows.filter(
        (r) =>
          (r.ticker || "").toLowerCase().includes(q) ||
          (r.name || "").toLowerCase().includes(q) ||
          (r.cusip || "").toLowerCase().includes(q)
      );
    }
    const sorted = [...rows].sort((a, b) => {
      const va = a[sortKey];
      const vb = b[sortKey];
      if (va === null || va === undefined) return 1;
      if (vb === null || vb === undefined) return -1;
      if (typeof va === "string") return va.localeCompare(vb);
      return va - vb;
    });
    if (sortDir === "desc") sorted.reverse();
    return sorted;
  }, [positions, sortKey, sortDir, query, activity]);

  function toggleSort(key) {
    if (key === sortKey) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  return (
    <div className="table-wrap">
      <div className="table-controls">
        <input
          className="filter-input"
          placeholder="Filter by ticker, name, or CUSIP…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div className="activity-tabs">
          {ACTIVITY_FILTERS.map((a) => (
            <button
              key={a}
              className={`pill ${activity === a ? "pill-active" : ""}`}
              onClick={() => setActivity(a)}
            >
              {a === "ALL" ? "All" : activityLabel(a)}
            </button>
          ))}
        </div>
        <span className="row-count">{filtered.length} positions</span>
      </div>

      <table className="holdings">
        <thead>
          <tr>
            {COLUMNS.map((c) => (
              <th
                key={c.key}
                className={c.align === "right" ? "right" : ""}
                onClick={() => toggleSort(c.key)}
              >
                {c.label}
                {sortKey === c.key ? (sortDir === "desc" ? " ▾" : " ▴") : ""}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filtered.map((p) => (
            <tr key={p.cusip + p.put_call}>
              <td className="mono">{p.ticker || "—"}{p.put_call ? ` (${p.put_call})` : ""}</td>
              <td className="name-cell">{p.name}</td>
              <td className="right">{fmtNum(p.shares)}</td>
              <td className="right">{fmtUSD(p.value_usd)}</td>
              <td className="right">{p.pct_of_portfolio.toFixed(1)}%</td>
              <td className="right">{fmtPrice(p.price)}</td>
              <td className="right">{fmtUSD(p.implied_value)}</td>
              <td className={`right ${changeClass(p.price_change_pct)}`}>
                {fmtPct(p.price_change_pct)}
              </td>
              <td>
                <span className={`badge badge-${p.activity.toLowerCase()}`}>
                  {activityLabel(p.activity)}
                </span>
              </td>
              <td className={`right ${changeClass(p.shares_delta)}`}>
                {fmtSignedNum(p.shares_delta)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function changeClass(v) {
  if (v === null || v === undefined || v === 0) return "";
  return v > 0 ? "pos" : "neg";
}
