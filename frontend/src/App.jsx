import React, { useState } from "react";
import { fetchManager } from "./api.js";
import { downloadCSV, positionsToCSV } from "./csv.js";
import { fmtUSD } from "./format.js";
import HoldingsTable from "./components/HoldingsTable.jsx";
import CompareView from "./components/CompareView.jsx";

const EXAMPLES = [
  { label: "Berkshire Hathaway", id: "0001067983" },
  { label: "Scion (Burry)", id: "0001649339" },
  { label: "Bridgewater", id: "0001350694" },
];

export default function App() {
  const [tab, setTab] = useState("manager");
  const [identifier, setIdentifier] = useState("");
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function load(id, refresh = false) {
    const target = (id ?? identifier).trim();
    if (!target) return;
    setLoading(true);
    setError("");
    try {
      const data = await fetchManager(target, refresh);
      setReport(data);
      setIdentifier(target);
    } catch (err) {
      setError(err.message);
      setReport(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <header className="topbar">
        <h1>13F Viewer</h1>
        <nav className="tabs">
          <button className={tab === "manager" ? "active" : ""} onClick={() => setTab("manager")}>
            Manager
          </button>
          <button className={tab === "compare" ? "active" : ""} onClick={() => setTab("compare")}>
            Compare
          </button>
        </nav>
      </header>

      {tab === "manager" ? (
        <main>
          <form
            className="search"
            onSubmit={(e) => {
              e.preventDefault();
              load();
            }}
          >
            <input
              placeholder="Enter ticker or CIK (e.g. 0001067983 for Berkshire)…"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
            />
            <button type="submit" disabled={loading}>
              {loading ? "Loading…" : "Load"}
            </button>
          </form>

          <div className="examples">
            <span className="muted">Try:</span>
            {EXAMPLES.map((ex) => (
              <button key={ex.id} className="link" onClick={() => load(ex.id)}>
                {ex.label}
              </button>
            ))}
          </div>

          {error && <div className="error">{error}</div>}

          {report && (
            <>
              <section className="report-header">
                <div>
                  <h2>{report.manager_name}</h2>
                  <div className="muted">
                    CIK {report.cik} · {report.period}
                    {report.prev_period ? ` vs ${report.prev_period}` : ""} · filed{" "}
                    {report.filing_date}
                  </div>
                </div>
                <div className="stats">
                  <Stat label="Portfolio Value" value={fmtUSD(report.total_value_usd)} />
                  <Stat label="Positions" value={report.num_positions} />
                  <Stat label="Closed" value={report.num_closed} />
                  <div className="actions">
                    <button onClick={() => load(identifier, true)}>Refresh</button>
                    <button
                      onClick={() =>
                        downloadCSV(`${report.cik}_${report.period}.csv`, positionsToCSV(report))
                      }
                    >
                      Export CSV
                    </button>
                  </div>
                </div>
              </section>

              <HoldingsTable positions={report.positions} />

              {report.closed_positions.length > 0 && (
                <details className="closed-section">
                  <summary>{report.num_closed} closed positions</summary>
                  <HoldingsTable positions={report.closed_positions} />
                </details>
              )}
            </>
          )}
        </main>
      ) : (
        <main>
          <CompareView />
        </main>
      )}

      <footer className="foot muted">
        Data: SEC EDGAR 13F filings · tickers via OpenFIGI · prices via yfinance. Not investment
        advice.
      </footer>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="stat">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}
