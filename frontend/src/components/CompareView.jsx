import React, { useMemo, useState } from "react";
import { fetchCompare } from "../api.js";
import { fmtNum, fmtPct } from "../format.js";

export default function CompareView() {
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function run(e) {
    e.preventDefault();
    if (!a.trim() || !b.trim()) return;
    setLoading(true);
    setError("");
    try {
      setData(await fetchCompare(a.trim(), b.trim()));
    } catch (err) {
      setError(err.message);
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="compare">
      <form className="compare-form" onSubmit={run}>
        <input placeholder="Manager A (ticker / CIK)" value={a} onChange={(e) => setA(e.target.value)} />
        <span className="vs">vs</span>
        <input placeholder="Manager B (ticker / CIK)" value={b} onChange={(e) => setB(e.target.value)} />
        <button type="submit" disabled={loading}>{loading ? "Comparing…" : "Compare"}</button>
      </form>

      {error && <div className="error">{error}</div>}
      {data && <CompareResult data={data} />}
    </div>
  );
}

function CompareResult({ data }) {
  const aColor = "#4f8cff";
  const bColor = "#c084fc";

  // Composition: how many names are unique vs shared.
  const total = data.a_only_count + data.overlap_count + data.b_only_count;
  const seg = (n) => (total ? (n / total) * 100 : 0);

  const maxWeight = useMemo(
    () =>
      Math.max(
        1e-9,
        ...data.overlap.map((r) => Math.max(r.a_pct_of_portfolio, r.b_pct_of_portfolio))
      ),
    [data]
  );

  return (
    <>
      <div className="cmp-titles">
        <span className="cmp-name" style={{ color: aColor }}>
          {data.a.name} <span className="muted">{data.a.period}</span>
        </span>
        <span className="cmp-name right" style={{ color: bColor }}>
          <span className="muted">{data.b.period}</span> {data.b.name}
        </span>
      </div>

      {/* Composition bar: unique-A | shared | unique-B */}
      <div className="composition">
        <div className="comp-bar">
          <div className="comp-seg a-only" style={{ width: `${seg(data.a_only_count)}%`, background: aColor }}>
            {data.a_only_count > 0 && data.a_only_count}
          </div>
          <div className="comp-seg shared" style={{ width: `${seg(data.overlap_count)}%` }}>
            {data.overlap_count}
          </div>
          <div className="comp-seg b-only" style={{ width: `${seg(data.b_only_count)}%`, background: bColor }}>
            {data.b_only_count > 0 && data.b_only_count}
          </div>
        </div>
        <div className="comp-legend muted">
          <span>{data.a_only_count} only {data.a.name.split(" ")[0]}</span>
          <span><strong>{data.overlap_count}</strong> shared</span>
          <span>{data.b_only_count} only {data.b.name.split(" ")[0]}</span>
        </div>
      </div>

      {/* Mirrored conviction bars per overlapping name */}
      <div className="mirror">
        <div className="mirror-head">
          <span className="muted">{data.a.name} weight</span>
          <span className="muted">Shared holdings (by portfolio weight)</span>
          <span className="muted right">{data.b.name} weight</span>
        </div>
        {data.overlap.map((r) => {
          const aw = (r.a_pct_of_portfolio / maxWeight) * 100;
          const bw = (r.b_pct_of_portfolio / maxWeight) * 100;
          const lean = r.a_pct_of_portfolio - r.b_pct_of_portfolio;
          return (
            <div className="mirror-row" key={r.cusip} title={`${r.name}\nA: ${fmtNum(r.a_shares)} sh\nB: ${fmtNum(r.b_shares)} sh`}>
              <div className="mirror-val left">{r.a_pct_of_portfolio.toFixed(1)}%</div>
              <div className="mirror-side left">
                <div className="mirror-bar" style={{ width: `${aw}%`, background: aColor }} />
              </div>
              <div className="mirror-ticker mono">{r.ticker || "—"}</div>
              <div className="mirror-side right">
                <div className="mirror-bar" style={{ width: `${bw}%`, background: bColor }} />
              </div>
              <div className="mirror-val right">{r.b_pct_of_portfolio.toFixed(1)}%</div>
              <div className={`mirror-lean ${lean >= 0 ? "lean-a" : "lean-b"}`}>
                {lean >= 0 ? "◀" : "▶"} {fmtPct(Math.abs(lean)).replace("+", "")}
              </div>
            </div>
          );
        })}
        {data.overlap.length === 0 && (
          <div className="muted" style={{ padding: "16px 0" }}>No overlapping holdings.</div>
        )}
      </div>
    </>
  );
}
