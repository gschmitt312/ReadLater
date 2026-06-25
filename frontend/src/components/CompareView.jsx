import React, { useState } from "react";
import { fetchCompare } from "../api.js";
import { fmtNum, fmtUSD } from "../format.js";

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

      {data && (
        <>
          <div className="compare-summary">
            <div>
              <strong>{data.a.name}</strong> <span className="muted">{data.a.period}</span>
              <div className="muted">{data.a_only_count} unique positions</div>
            </div>
            <div className="overlap-stat">
              <span className="big">{data.overlap_count}</span>
              <span className="muted">shared</span>
            </div>
            <div>
              <strong>{data.b.name}</strong> <span className="muted">{data.b.period}</span>
              <div className="muted">{data.b_only_count} unique positions</div>
            </div>
          </div>

          <table className="holdings">
            <thead>
              <tr>
                <th>Ticker</th>
                <th>Name</th>
                <th className="right">{data.a.name} shares</th>
                <th className="right">{data.a.name} %</th>
                <th className="right">{data.b.name} shares</th>
                <th className="right">{data.b.name} %</th>
              </tr>
            </thead>
            <tbody>
              {data.overlap.map((r) => (
                <tr key={r.cusip}>
                  <td className="mono">{r.ticker || "—"}</td>
                  <td className="name-cell">{r.name}</td>
                  <td className="right">{fmtNum(r.a_shares)}</td>
                  <td className="right">{r.a_pct_of_portfolio.toFixed(1)}%</td>
                  <td className="right">{fmtNum(r.b_shares)}</td>
                  <td className="right">{r.b_pct_of_portfolio.toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
