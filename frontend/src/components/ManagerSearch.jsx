import React, { useEffect, useRef, useState } from "react";
import { searchManagers } from "../api.js";

// Pure digits (4+) looks like a CIK; don't run a name search for those.
const looksLikeCik = (s) => /^\d{4,}$/.test(s.trim());

export default function ManagerSearch({ onLoad, loading }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [searching, setSearching] = useState(false);
  const [err, setErr] = useState("");
  const boxRef = useRef(null);

  // Debounced name search as the user types.
  useEffect(() => {
    const term = q.trim();
    if (term.length < 3 || looksLikeCik(term)) {
      setResults([]);
      setSearching(false);
      return;
    }
    let cancelled = false;
    setSearching(true);
    setErr("");
    const timer = setTimeout(async () => {
      try {
        const r = await searchManagers(term);
        if (!cancelled) {
          setResults(r);
          setOpen(true);
        }
      } catch (e) {
        if (!cancelled) {
          setResults([]);
          setErr(e.message);
        }
      } finally {
        if (!cancelled) setSearching(false);
      }
    }, 350);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [q]);

  // Close the dropdown on an outside click.
  useEffect(() => {
    function onDoc(e) {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  function pick(r) {
    setQ(r.name);
    setResults([]);
    setOpen(false);
    onLoad(r.cik);
  }

  function submit(e) {
    e.preventDefault();
    const term = q.trim();
    if (!term) return;
    // A name with matches -> load the top hit; otherwise treat as CIK/ticker.
    if (results.length && !looksLikeCik(term)) pick(results[0]);
    else onLoad(term);
  }

  return (
    <div className="search-wrap" ref={boxRef}>
      <form className="search" onSubmit={submit}>
        <input
          placeholder="Search by fund name (e.g. Scion), or enter a CIK / ticker…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onFocus={() => results.length && setOpen(true)}
          autoComplete="off"
        />
        <button type="submit" disabled={loading}>
          {loading ? "Loading…" : "Load"}
        </button>
      </form>

      {open && (searching || results.length > 0 || err) && (
        <div className="suggest">
          {searching && <div className="suggest-msg muted">Searching EDGAR…</div>}
          {!searching && err && <div className="suggest-msg err-text">{err}</div>}
          {!searching && !err && results.length === 0 && (
            <div className="suggest-msg muted">No 13F filers match that name.</div>
          )}
          {results.map((r) => (
            <button type="button" className="suggest-item" key={r.cik} onClick={() => pick(r)}>
              <span className="suggest-name">{r.name}</span>
              <span className="suggest-cik mono">CIK {r.cik}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
