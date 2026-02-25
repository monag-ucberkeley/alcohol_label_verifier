import React, { useState } from "react";
import { verifySingle, verifyBatch } from "./api.js";

export default function App() {
  const [mode, setMode] = useState("single"); // single | batch
  const [file, setFile] = useState(null);
  const [zipFile, setZipFile] = useState(null);

  const [brand, setBrand] = useState("STONE'S THROW");
  const [abv, setAbv] = useState("12.5%");
  const [net, setNet] = useState("750 mL");
  const [warn, setWarn] = useState(true);

  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [batch, setBatch] = useState(null);
  const [err, setErr] = useState("");

  async function run() {
    setErr("");
    setResult(null);
    setBatch(null);
    setBusy(true);
    try {
      if (mode === "single") {
        if (!file) throw new Error("Please choose a label image.");
        const r = await verifySingle({ file, brand_name: brand, abv, net_contents: net, require_gov_warning: warn });
        setResult(r);
      } else {
        if (!zipFile) throw new Error("Please choose a ZIP file of images.");
        const r = await verifyBatch({ zipFile, brand_name: brand, abv, net_contents: net, require_gov_warning: warn });
        setBatch(r);
      }
    } catch (e) {
      setErr(e.message || String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <header className="header">
        <h1>Alcohol Label Verification</h1>
        <div className="mode">
          <button className={mode==="single" ? "active" : ""} onClick={() => setMode("single")}>Single</button>
          <button className={mode==="batch" ? "active" : ""} onClick={() => setMode("batch")}>Batch</button>
        </div>
      </header>

      <div className="grid">
        <section className="card">
          <h2>1) Upload</h2>
          {mode === "single" ? (
            <input type="file" accept=".png,.jpg,.jpeg" onChange={(e) => setFile(e.target.files?.[0] || null)} />
          ) : (
            <input type="file" accept=".zip" onChange={(e) => setZipFile(e.target.files?.[0] || null)} />
          )}
          <p className="hint">Tip: keep images reasonably sized for speed.</p>
        </section>

        <section className="card">
          <h2>2) Application Fields</h2>
          <label>Brand name <input value={brand} onChange={(e) => setBrand(e.target.value)} /></label>
          <label>ABV <input value={abv} onChange={(e) => setAbv(e.target.value)} /></label>
          <label>Net contents <input value={net} onChange={(e) => setNet(e.target.value)} /></label>
          <label className="row">
            <input type="checkbox" checked={warn} onChange={(e) => setWarn(e.target.checked)} />
            Government warning required
          </label>
          <button className="run" onClick={run} disabled={busy}>
            {busy ? "Running..." : "Run Check"}
          </button>
          {err && <div className="error">{err}</div>}
        </section>

        <section className="card wide">
          <h2>Results</h2>

          {result && (
            <>
              <div className={"pill " + (result.overall_status === "PASS" ? "pass" : "review")}>
                {result.overall_status}
              </div>
              <ul className="list">
                {result.items.map((it) => (
                  <li key={it.field} className={"item " + it.status.toLowerCase()}>
                    <div className="itemTitle">
                      <b>{it.field}</b> — {it.status}
                    </div>
                    <div className="itemBody">
                      {it.expected && <div><span className="k">Expected:</span> {it.expected}</div>}
                      {it.found && <div><span className="k">Found:</span> {it.found}</div>}
                      {typeof it.confidence === "number" && <div><span className="k">Confidence:</span> {it.confidence}</div>}
                      {it.notes && <div className="note">{it.notes}</div>}
                    </div>
                  </li>
                ))}
              </ul>
              <div className="timings">
                {Object.entries(result.timings_ms).map(([k,v]) => <span key={k}>{k}: {v}ms</span>)}
              </div>
            </>
          )}

          {batch && (
            <>
              <div className="pill review">Batch results: {batch.count}</div>
              <table className="table">
                <thead><tr><th>File</th><th>Status</th><th>Mismatches</th></tr></thead>
                <tbody>
                  {batch.results.map((r) => {
                    const mism = r.items.filter(i => i.status !== "PASS").length;
                    return (
                      <tr key={r.filename}>
                        <td>{r.filename}</td>
                        <td>{r.overall_status}</td>
                        <td>{mism}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </>
          )}

          {!result && !batch && <p className="hint">Upload a file and click “Run Check”.</p>}
        </section>
      </div>
    </div>
  );
}
