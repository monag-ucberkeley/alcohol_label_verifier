import React, { useEffect, useMemo, useState } from "react";
import { verifySingle, verifyWithApplicationJson, verifyBatchPairs } from "./api";

const STATUS_META = {
  PASS: { label: "Pass", tone: "pass" },
  REVIEW: { label: "Needs review", tone: "review" },
  NEEDS_REVIEW: { label: "Needs review", tone: "review" },
  FAIL: { label: "Fail", tone: "fail" },
  MISSING: { label: "Missing", tone: "fail" },
};

function Badge({ status }) {
  const meta = STATUS_META[status] || { label: status || "—", tone: "neutral" };
  return <span className={`badge ${meta.tone}`}>{meta.label}</span>;
}

function formatMs(ms) {
  if (ms === undefined || ms === null) return "—";
  return `${ms} ms`;
}

function pickItem(items, field) {
  if (!Array.isArray(items)) return null;
  return items.find((x) => (x.field || x.name) === field) || null;
}

export default function App() {
  const [mode, setMode] = useState("single"); // single | batch

  // uploads
  const [labelFile, setLabelFile] = useState(null);
  const [labelPreviewUrl, setLabelPreviewUrl] = useState(null);
  const [batchZip, setBatchZip] = useState(null);
  const [appJsonFile, setAppJsonFile] = useState(null);

  // application fields (manual or auto-filled)
  const [brandName, setBrandName] = useState("STONE'S THROW");
  const [abv, setAbv] = useState("12.5%");
  const [netContents, setNetContents] = useState("750 mL");
  const [requireWarning, setRequireWarning] = useState(true);

  // results
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [singleResult, setSingleResult] = useState(null);
  const [batchResult, setBatchResult] = useState(null);

  // cleanup object URL
  useEffect(() => {
    return () => {
      if (labelPreviewUrl) URL.revokeObjectURL(labelPreviewUrl);
    };
  }, [labelPreviewUrl]);

  const hasSingleInput = mode === "single" && !!labelFile;
  const hasBatchInput = mode === "batch" && !!batchZip;

  const overallBadge = useMemo(() => {
    const res = singleResult;
    if (!res) return null;
    return res.overall_status || res.overall || "—";
  }, [singleResult]);

  const timing = useMemo(() => singleResult?.timings_ms || null, [singleResult]);

  async function onSelectLabelFile(f) {
    setLabelFile(f);
    setSingleResult(null);
    setError("");
    if (labelPreviewUrl) URL.revokeObjectURL(labelPreviewUrl);
    setLabelPreviewUrl(f ? URL.createObjectURL(f) : null);
  }

  async function onSelectApplicationJson(f) {
    setAppJsonFile(f || null);
    setSingleResult(null);
    setError("");

    if (!f) return;

    try {
      const txt = await f.text();
      const data = JSON.parse(txt);
      if (typeof data.brand_name === "string") setBrandName(data.brand_name);
      if (typeof data.abv === "string") setAbv(data.abv);
      if (typeof data.net_contents === "string") setNetContents(data.net_contents);
      setRequireWarning(data.government_warning_required !== false);
    } catch {
      setError("Could not read application.json (invalid JSON).");
    }
  }

  async function runSingle() {
    if (!labelFile) {
      setError("Upload a label image to continue.");
      return;
    }

    setLoading(true);
    setError("");
    setSingleResult(null);

    try {
      let res;
      if (appJsonFile) {
        res = await verifyWithApplicationJson({ file: labelFile, applicationJsonFile: appJsonFile });
      } else {
        res = await verifySingle({
          file: labelFile,
          brand_name: brandName,
          abv,
          net_contents: netContents,
          require_gov_warning: requireWarning,
        });
      }
      setSingleResult(res);
    } catch (e) {
      setError(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  }

  async function runBatch() {
    if (!batchZip) {
      setError("Upload a ZIP containing label + application.json pairs.");
      return;
    }

    setLoading(true);
    setError("");
    setBatchResult(null);

    try {
      const res = await verifyBatchPairs({ zipFile: batchZip });
      setBatchResult(res);
    } catch (e) {
      setError(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  }

  const checks = useMemo(() => {
    const items = singleResult?.items || singleResult?.checks || singleResult?.results || [];
    return (Array.isArray(items) ? items : []).map((x) => ({
      ...x,
      field: x.field || x.name,
    }));
  }, [singleResult]);

  const checkBrand = pickItem(checks, "brand_name");
  const checkAbv = pickItem(checks, "abv");
  const checkNet = pickItem(checks, "net_contents");
  const checkWarn = pickItem(checks, "government_warning");
  const checkImg = pickItem(checks, "image_quality");

  return (
    <div className="page">
      <header className="topbar">
        <div className="brand">
          <div className="logo">ALV</div>
          <div>
            <div className="title">Alcohol Label Verifier</div>
            <div className="subtitle">Fast, local, agent-friendly prototype (no external APIs)</div>
          </div>
        </div>

        <div className="modeToggle" role="tablist" aria-label="Mode">
          <button
            className={`tab ${mode === "single" ? "active" : ""}`}
            onClick={() => {
              setMode("single");
              setError("");
              setBatchResult(null);
            }}
            type="button"
          >
            Single
          </button>
          <button
            className={`tab ${mode === "batch" ? "active" : ""}`}
            onClick={() => {
              setMode("batch");
              setError("");
              setSingleResult(null);
              setLabelFile(null);
              setLabelPreviewUrl(null);
              setAppJsonFile(null);
            }}
            type="button"
          >
            Batch
          </button>
        </div>
      </header>

      <main className="content">
        <div className="grid">
          {/* LEFT: Inputs */}
          <section className="card">
            <h2 className="cardTitle">1) Upload</h2>

            {mode === "single" ? (
              <>
                <label className="fileDrop">
                  <input
                    type="file"
                    accept=".png,.jpg,.jpeg"
                    onChange={(e) => onSelectLabelFile(e.target.files?.[0] || null)}
                  />
                  <div className="fileDropInner">
                    <div className="fileDropTitle">Choose a label image</div>
                    <div className="fileDropHint">PNG / JPG • keep images reasonably sized for speed</div>
                    {labelFile ? (
                      <div className="fileName">
                        Selected: <b>{labelFile.name}</b>
                      </div>
                    ) : null}
                  </div>
                </label>

                {labelPreviewUrl ? (
                  <div className="previewWrap" aria-label="Label preview">
                    <div className="previewHeader">
                      <div className="hint">Label preview</div>
                      <button className="linkBtn" onClick={() => onSelectLabelFile(null)} type="button">
                        Clear
                      </button>
                    </div>
                    <img className="previewImg" src={labelPreviewUrl} alt="Uploaded label preview" />
                  </div>
                ) : null}
              </>
            ) : (
              <>
                <label className="fileDrop">
                  <input type="file" accept=".zip" onChange={(e) => setBatchZip(e.target.files?.[0] || null)} />
                  <div className="fileDropInner">
                    <div className="fileDropTitle">Choose a ZIP of label/application pairs</div>
                    <div className="fileDropHint">Structure: each folder contains label.png (or .jpg) + application.json</div>
                    {batchZip ? (
                      <div className="fileName">
                        Selected: <b>{batchZip.name}</b>
                      </div>
                    ) : null}
                  </div>
                </label>
              </>
            )}

            <div className="divider" />
            {mode === "single" ? (
  <>
    <div className="divider" />

    <h2 className="cardTitle">2) Application data</h2>
            <div className="twoCol">
              <div className="field">
                <label>Brand Name</label>
                <input value={brandName} onChange={(e) => setBrandName(e.target.value)} placeholder="e.g., STONE'S THROW" />
              </div>

              <div className="field">
                <label>ABV</label>
                <input value={abv} onChange={(e) => setAbv(e.target.value)} placeholder="e.g., 12.5%" />
              </div>

              <div className="field">
                <label>Net Contents</label>
                <input value={netContents} onChange={(e) => setNetContents(e.target.value)} placeholder="e.g., 750 mL" />
              </div>

              <div className="field checkboxField">
                <label>Government Warning Required</label>
                <label className="checkbox">
                  <input type="checkbox" checked={requireWarning} onChange={(e) => setRequireWarning(e.target.checked)} />
                  <span>Yes</span>
                </label>
              </div>
            </div>

            {mode === "single" ? (
              <>
                <div className="hint" style={{ marginTop: 10 }}>
                  Optional: upload a COLA application <b>JSON</b>. If provided, verification uses the uploaded application file.
                </div>

                <div className="row">
                  <input
                    className="fileInline"
                    type="file"
                    accept=".json,application/json"
                    onChange={(e) => onSelectApplicationJson(e.target.files?.[0] || null)}
                  />
                  {appJsonFile ? (
                    <button className="secondaryBtn" type="button" onClick={() => onSelectApplicationJson(null)}>
                      Clear application
                    </button>
                  ) : null}
                </div>

                {appJsonFile ? (
                  <div className="hint">
                    Using application: <b>{appJsonFile.name}</b>
                  </div>
                ) : null}
              </>
            ) : null}
  </>
) : null}

<div className="divider" />

<h2 className="cardTitle">3) Run check</h2>

            <div className="actions">
              {mode === "single" ? (
                <button className="primaryBtn" onClick={runSingle} disabled={loading || !hasSingleInput} type="button">
                  {loading ? "Running…" : "Verify label"}
                </button>
              ) : (
                <button className="primaryBtn" onClick={runBatch} disabled={loading || !hasBatchInput} type="button">
                  {loading ? "Running…" : "Verify batch"}
                </button>
              )}

              <div className="hint">Goal: results in ~5 seconds for typical labels.</div>
            </div>

            {error ? <div className="errorBox">{error}</div> : null}
          </section>

          {/* RIGHT: Output */}
          <section className="card">
            <div className="cardHeaderRow">
              <h2 className="cardTitle">Results</h2>
              {mode === "single" && overallBadge ? <Badge status={overallBadge} /> : null}
            </div>

            {mode === "single" ? (
              <>
                {!singleResult ? (
                  <div className="emptyState">
                    Upload a label, enter application data (or upload application JSON), then click <b>Verify label</b>.
                  </div>
                ) : (
                  <>
                    <div className="checklist">
                      <ChecklistRow title="Brand name" item={checkBrand} />
                      <ChecklistRow title="ABV" item={checkAbv} />
                      <ChecklistRow title="Net contents" item={checkNet} />
                      <ChecklistRow title="Government warning (full text)" item={checkWarn} />
                      <ChecklistRow title="Image quality" item={checkImg} />
                    </div>

                    <div className="divider" />

                    <h3 className="sectionTitle">Details</h3>
                    <details className="details">
                      <summary>Show raw JSON</summary>
                      <pre className="code">{JSON.stringify(singleResult, null, 2)}</pre>
                    </details>

                    <div className="divider" />

                    <h3 className="sectionTitle">Timing</h3>
                    <div className="timingGrid">
                      <TimingRow label="OCR" value={formatMs(timing?.ocr_total_ms)} />
                      <TimingRow label="Extract+Compare" value={formatMs(timing?.extract_compare_ms)} />
                      <TimingRow label="Total" value={formatMs(timing?.total_ms)} />
                    </div>
                  </>
                )}
              </>
            ) : (
              <>
                {!batchResult ? (
                  <div className="emptyState">
                    Upload a ZIP of label/application pairs, then click <b>Verify batch</b>.
                  </div>
                ) : (
                  <>
                    <div className="hint" style={{ marginBottom: 10 }}>
                      Processed: <b>{batchResult?.count ?? (batchResult?.results?.length || "—")}</b>
                    </div>

                    <BatchTable data={batchResult} />

                    <div className="divider" />

                    <details className="details">
                      <summary>Show raw JSON</summary>
                      <pre className="code">{JSON.stringify(batchResult, null, 2)}</pre>
                    </details>
                  </>
                )}
              </>
            )}
          </section>
        </div>
      </main>

      <footer className="footer">
        Prototype notes: local OCR, no external network calls; designed for simple, high-throughput agent workflow.
      </footer>
    </div>
  );
}

function ChecklistRow({ title, item }) {
  const status = item?.status || "—";
  const found = item?.found ?? item?.value ?? "";
  const expected = item?.expected ?? "";
  const confidence = item?.confidence;

  return (
    <div className="checkRow">
      <div className="checkLeft">
        <div className="checkTitle">{title}</div>
        <div className="checkMeta">
          {expected ? (
            <span>
              <span className="muted">Expected:</span> {String(expected)}
            </span>
          ) : null}
          {found ? (
            <span>
              <span className="muted">Found:</span> {String(found)}
            </span>
          ) : null}
          {confidence !== undefined && confidence !== null ? (
            <span>
              <span className="muted">Confidence:</span> {Number(confidence).toFixed(2)}
            </span>
          ) : null}
        </div>
      </div>
      <div className="checkRight">
        <Badge status={status} />
      </div>
    </div>
  );
}

function TimingRow({ label, value }) {
  return (
    <div className="timingRow">
      <div className="muted">{label}</div>
      <div className="timingVal">{value}</div>
    </div>
  );
}

function BatchTable({ data }) {
  const rows = data?.results || [];
  if (!Array.isArray(rows) || rows.length === 0) {
    return <div className="emptyState">No batch results returned.</div>;
  }

  return (
    <div className="tableWrap">
      <table className="table">
        <thead>
          <tr>
            <th style={{ width: 110 }}>Label</th>
            <th>Pair</th>
            <th>Application values</th>
            <th>Overall</th>
            <th>Notes</th>
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 300).map((r, idx) => {
            const res = r.result || {};
            const items = res.items || res.checks || res.results || [];
            const checks = (Array.isArray(items) ? items : []).map((x) => ({ ...x, field: x.field || x.name }));

            const brand = checks.find((x) => x.field === "brand_name");
            const abv = checks.find((x) => x.field === "abv");
            const net = checks.find((x) => x.field === "net_contents");
            const warn = checks.find((x) => x.field === "government_warning");
            const imgq = checks.find((x) => x.field === "image_quality");

            const overall = res.overall_status || res.overall || "—";
            const app = r.application || {};
            const thumbSrc = r.thumbnail_b64 ? `data:image/jpeg;base64,${r.thumbnail_b64}` : null;

            return (
              <tr key={idx}>
                <td>
                  {thumbSrc ? (
                    <img
                      src={thumbSrc}
                      alt="label thumbnail"
                      style={{
                        width: 96,
                        height: 96,
                        objectFit: "contain",
                        borderRadius: 10,
                        border: "1px solid rgba(255,255,255,0.10)",
                        background: "rgba(0,0,0,0.18)",
                      }}
                    />
                  ) : (
                    <div className="hint">No preview</div>
                  )}
                </td>

                <td className="mono">
                  <div>
                    <b>{r.folder}</b>
                  </div>
                  <div className="hint">{r.label_filename}</div>
                </td>

                <td>
                  <div className="mono">Brand: {app.brand_name || "—"}</div>
                  <div className="mono">ABV: {app.abv || "—"}</div>
                  <div className="mono">Net: {app.net_contents || "—"}</div>
                  <div className="mono">Warn req: {String(app.government_warning_required ?? true)}</div>
                </td>

                <td>
                  <Badge status={overall} />
                  <div className="hint" style={{ marginTop: 6 }}>
                    Img: {imgq?.status || "—"}
                  </div>
                </td>

                <td>
                  <div className="hint">
                    Brand: {brand?.status || "—"} • ABV: {abv?.status || "—"} • Net: {net?.status || "—"}
                    <br />
                    Warning: {warn?.status || "—"}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {rows.length > 300 ? (
        <div className="hint" style={{ marginTop: 8 }}>
          Showing first 300 results.
        </div>
      ) : null}
    </div>
  );
}
