const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

export async function verifySingle({ file, brand_name, abv, net_contents, require_gov_warning }) {
  const form = new FormData();
  form.append("file", file);
  form.append("brand_name", brand_name);
  if (abv) form.append("abv", abv);
  if (net_contents) form.append("net_contents", net_contents);
  form.append("require_gov_warning", require_gov_warning ? "true" : "false");

  const res = await fetch(`${API_BASE}/api/verify`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return await res.json();
}

export async function verifyBatch({ zipFile, brand_name, abv, net_contents, require_gov_warning }) {
  const form = new FormData();
  form.append("zip_file", zipFile);
  form.append("brand_name", brand_name);
  if (abv) form.append("abv", abv);
  if (net_contents) form.append("net_contents", net_contents);
  form.append("require_gov_warning", require_gov_warning ? "true" : "false");

  const res = await fetch(`${API_BASE}/api/verify-batch`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return await res.json();
}
