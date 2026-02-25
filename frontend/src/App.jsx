import React, { useMemo, useState } from "react";
import { verifySingle, verifyBatch } from "./api.js";

function statusIcon(status) {
  if (status === "PASS") return "✅";
  if (status === "REVIEW" || status === "NEEDS_REVIEW") return "⚠️";
  if (status === "MISSING") return "❓";
  if (status === "FAIL") return "❌";
  return "•";
}

function prettyField(field) {
  const map = {
    brand_name: "Brand name",
    abv: "ABV",
    net_contents: "Net contents",
    government_warning_present: "Government warning present",
    government_warning_header: "Warning header format",
    government_warning_text: "Warning text exactness",
    image_quality: "Image quality",
  };
  return map[field] || field.replaceAll("_", " ");
}

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
        if (!file) throw new Error("Step 1: choose a label image.");
        const r = await verifySingle({ file, brand_name: brand, abv, net_contents: net, require_gov_warning: warn });
        setResult(r);
      } else {
        if (!zipFile) throw new Error("Step 1: choose a ZIP file of images.");
        const r = await verifyBatch({ zipFile, brand_name: brand, abv, net_contents: net, require_gov_warning: warn });
        setBatch(r);
      }
    } catch (e) {
      setErr(e.message || String(e));
    } finally {
      setBusy(false);
    }
  }

  const singleChecklist = useMemo(() => {
    if (!result) return [];
    // Keep a stable order for older users
    const order = ["image_quality","brand_name","abv","net_contents","government_warning_present","government_warning_header","government_warning_text"];
    const by = new Map(result.items.map(i => [i.field, i]));
    return order.filter(k => by.has(k)).map(k => by.get(k));
  }, [result]);

  return (
    <div className="page">
      <header className="header">
        <div>
          <h1>Alcohol Label Verification</h1>
          <div className="sub">Fast, standalone prototype for checking label artwork against application fields.</div>
        </div>
        <div className="mode" role="tablist" aria-label="Mode">
          <button className={mode==="single" ? "active" : ""} onClick={() => setMode("single")}>Single</button>
          <button className={mode==="batch" ? "active" : ""} onClick={() => setMode("batch")}>Batch (ZIP)</button>
        </div>
      </header>

      <div className="grid">
        <section className="card">
          <h2>Step 1 — Upload</h2>
          {mode === "single" ? (
            <>
              <input type="file" accept=".png,.jpg,.jpeg" onChange={(e) => setFile(e.target.files?.[0] || null)} />
              <div className="hint">Tip: Use a well-lit photo (avoid glare). Faster processing with smaller images.</div>
            </>
          ) : (
            <>
              <input type="file" accept=".zip" onChange={(e) => setZipFile(e.target.files?.[0] || null)} />
              <div className="hint">Upload a ZIP of label images (200+ supported). Results are shown in a table.</div>
            </>
          )}
        </section>

        <section className="card">
          <h2>Step 2 — Application Fields</h2>
          <label className="lbl">Brand name
            <input value={brand} onChange={(e) => setBrand(e.target.value)} />
          </label>

          <div className="row2">
            <label className="lbl">ABV
              <input value={abv} onChange={(e) => setAbv(e.target.value)} />
            </label>
            <label className="lbl">Net contents
              <input value={net} onChange={(e) => setNet(e.target.value)} />
            </label>
          </div>

          <label className="rowChk">
            <input type="checkbox" checked={warn} onChange={(e) => setWarn(e.target.checked)} />
            Government warning required
          </label>

          <button className="run" onClick={run} disabled={busy}>
            {busy ? "Running..." : "Step 3 — Run Check"}
          </button>

          {err && <div className="error">{err}</div>}
        </section>

        <section className="card wide">
          <h2>Results</h2>

          {result && (
            <>
              <div className={"pill " + (result.overall_status === "PASS" ? "pass" : "review")}>
                {statusIcon(result.overall_status)} {result.overall_status}
              </div>

              {result.image_quality && (
                <div className={"quality " + result.image_quality.rating.toLowerCase()}>
                  <div className="qualityTitle">Image quality: <b>{result.image_quality.rating}</b></div>
                  <div className="qualityBody">{result.image_quality.recommendation}</div>
                  <div className="qualityMeta">
                    avg OCR conf: {result.image_quality.avg_ocr_confidence} • low-conf ratio: {result.image_quality.low_conf_ratio} • text chars: {result.image_quality.total_text_chars}
                  </div>
                </div>
              )}

              <div className="checklistTitle">Checklist</div>
              <ul className="checklist">
                {singleChecklist.map((it) => (
                  <li key={it.field} className={"check " + it.status.toLowerCase()}>
                    <div className="checkTop">
                      <span className="checkIcon">{statusIcon(it.status)}</span>
                      <span className="checkName">{prettyField(it.field)}</span>
                      <span className={"badge " + it.status.toLowerCase()}>{it.status}</span>
                    </div>
                    <div className="checkDetails">
                      {it.expected && <div><span className="k">Expected:</span> {it.expected}</div>}
                      {it.found && <div><span className="k">Found:</span> {it.found}</div>}
                      {typeof it.confidence === "number" && <div><span className="k">Score:</span> {it.confidence}</div>}
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
              <div className="pill review">⚠️ Batch processed: {batch.count}</div>
              <table className="table">
                <thead><tr><th>File</th><th>Status</th><th>Mismatches</th><th>Image</th></tr></thead>
                <tbody>
                  {batch.results.map((r) => {
                    const mism = r.items.filter(i => i.status !== "PASS").length;
                    return (
                      <tr key={r.filename}>
                        <td>{r.filename}</td>
                        <td><span className={"badge " + (r.overall_status === "PASS" ? "pass" : "review")}>
                          {statusIcon(r.overall_status)} {r.overall_status}
                        </span></td>
                        <td>{mism}</td>
                        <td>{r.image_quality ? r.image_quality.rating : "-"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <div className="hint">Tip: click a row in a future iteration to expand per-label details (prototype keeps UI minimal).</div>
            </>
          )}

          {!result && !batch && (
            <div className="empty">
              Upload a label and run the check. The results appear as a simple checklist (designed for low-tech users).
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
