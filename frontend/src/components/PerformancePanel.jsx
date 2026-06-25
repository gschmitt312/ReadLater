import React from "react";
import { fmtPct, fmtUSD } from "../format.js";

export default function PerformancePanel({ performance, period }) {
  if (!performance || performance.coverage_pct === 0) {
    return (
      <section className="perf-panel">
        <div className="muted">No live prices available to estimate performance.</div>
      </section>
    );
  }

  const {
    estimated_return_pct: ret,
    coverage_pct: coverage,
    reported_value_priced: reported,
    implied_value_priced: implied,
    contributors,
    detractors,
  } = performance;

  const maxAbs = Math.max(
    1e-9,
    ...contributors.map((c) => c.contribution_pct),
    ...detractors.map((c) => Math.abs(c.contribution_pct))
  );

  return (
    <section className="perf-panel">
      <div className="perf-head">
        <div className="perf-headline">
          <div className={`perf-return ${ret >= 0 ? "pos" : "neg"}`}>{fmtPct(ret)}</div>
          <div className="perf-sub muted">
            est. mark-to-market return of the reported book since {period} quarter-end
          </div>
        </div>
        <div className="perf-meta">
          <Meta label="Reported value (priced)" value={fmtUSD(reported)} />
          <Meta label="Implied value now" value={fmtUSD(implied)} cls={ret >= 0 ? "pos" : "neg"} />
          <Meta label="Price coverage" value={`${coverage.toFixed(0)}%`} />
        </div>
      </div>

      <div className="perf-cols">
        <ContribColumn title="Top contributors" rows={contributors} maxAbs={maxAbs} positive />
        <ContribColumn title="Top detractors" rows={detractors} maxAbs={maxAbs} positive={false} />
      </div>

      <div className="perf-note muted">
        Price-only estimate from disclosed long holdings. Excludes cash, shorts, non-13F assets, and
        intra-quarter trades — not the fund's reported return.
      </div>
    </section>
  );
}

function Meta({ label, value, cls = "" }) {
  return (
    <div className="perf-meta-item">
      <div className={`perf-meta-value ${cls}`}>{value}</div>
      <div className="perf-meta-label">{label}</div>
    </div>
  );
}

function ContribColumn({ title, rows, maxAbs, positive }) {
  return (
    <div className="contrib-col">
      <div className="contrib-title">{title}</div>
      {rows.length === 0 && <div className="muted contrib-empty">None</div>}
      {rows.map((c) => {
        const width = Math.max(2, (Math.abs(c.contribution_pct) / maxAbs) * 100);
        return (
          <div className="contrib-row" key={c.ticker}>
            <div className="contrib-label mono">{c.ticker}</div>
            <div className="contrib-bar-track">
              <div
                className={`contrib-bar ${positive ? "pos-bg" : "neg-bg"}`}
                style={{ width: `${width}%` }}
                title={`${c.name} · ${fmtPct(c.price_change_pct)} price move · ${c.weight_pct.toFixed(1)}% of book`}
              />
            </div>
            <div className={`contrib-val ${positive ? "pos" : "neg"}`}>
              {fmtPct(c.contribution_pct)}
            </div>
          </div>
        );
      })}
    </div>
  );
}
