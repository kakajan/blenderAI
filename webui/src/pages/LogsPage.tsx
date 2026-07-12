import { useCallback, useEffect, useState } from "react";
import {
  clearLogs,
  getLogs,
  getReports,
  postReport,
  type LogEntry,
  type ReportEntry,
} from "../api/client";
import { t } from "../i18n";
import "./skills.css";
import "./logs.css";

export default function LogsPage() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [reports, setReports] = useState<ReportEntry[]>([]);
  const [level, setLevel] = useState("warning,error,crash");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [note, setNote] = useState("");

  const reload = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const [logRes, reportRes] = await Promise.all([
        getLogs({ level: level || undefined, limit: 200 }),
        getReports(30),
      ]);
      setLogs(logRes.logs);
      setReports(reportRes.reports);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }, [level]);

  useEffect(() => {
    void reload();
    const id = window.setInterval(() => void reload(), 8000);
    return () => window.clearInterval(id);
  }, [reload]);

  async function onClear() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await clearLogs();
      setNotice(t("logs.cleared"));
      await reload();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function onSendReport() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const latest = logs.find((l) => ["error", "crash", "warning"].includes(l.level));
      const report = await postReport({
        kind: latest?.level === "crash" ? "crash" : "error",
        summary: latest?.message || "WebUI error report",
        note,
        detail: {
          url: window.location.href,
          userAgent: navigator.userAgent,
        },
      });
      setNotice(
        report.file_path
          ? `${t("logs.reportSent")}: ${report.file_path}`
          : t("logs.reportSent")
      );
      setNote("");
      await reload();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="skills-page logs-page">
      <div className="skills-header">
        <div>
          <h2 className="page-title">{t("logs.title")}</h2>
          <p className="page-lead">{t("logs.lead")}</p>
        </div>
        <div className="skills-actions">
          <button type="button" onClick={() => void reload()} disabled={busy}>
            {t("logs.refresh")}
          </button>
          <button type="button" onClick={() => void onClear()} disabled={busy}>
            {t("logs.clear")}
          </button>
        </div>
      </div>

      {error ? <p className="skills-banner err">{error}</p> : null}
      {notice ? <p className="skills-banner ok">{notice}</p> : null}

      <div className="logs-filters">
        <label>
          {t("logs.filter")}
          <select value={level} onChange={(e) => setLevel(e.target.value)} disabled={busy}>
            <option value="warning,error,crash">{t("logs.filter.warnError")}</option>
            <option value="error,crash">{t("logs.filter.error")}</option>
            <option value="">{t("logs.filter.all")}</option>
            <option value="info">{t("logs.filter.info")}</option>
          </select>
        </label>
      </div>

      <div className="card logs-report-box">
        <div className="hd-icon-text-row">
          <span className="skills-form-dot" aria-hidden="true" />
          <h3 className="min-w-0" style={{ margin: 0 }}>
            {t("logs.sendReport")}
          </h3>
        </div>
        <p className="muted" style={{ margin: "0.5rem 0 0.75rem" }}>
          {t("logs.sendReportHelp")}
        </p>
        <textarea
          rows={2}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder={t("logs.notePlaceholder")}
          disabled={busy}
        />
        <div className="skills-actions" style={{ marginTop: "0.75rem" }}>
          <button type="button" className="primary" onClick={() => void onSendReport()} disabled={busy}>
            {t("logs.sendReport")}
          </button>
        </div>
      </div>

      <div className="card logs-list">
        <div className="hd-icon-text-row" style={{ marginBottom: "0.75rem" }}>
          <span className="skills-form-dot" aria-hidden="true" />
          <h3 className="min-w-0" style={{ margin: 0 }}>
            {t("logs.entries")}
          </h3>
        </div>
        {logs.length === 0 ? (
          <p className="muted">{t("logs.empty")}</p>
        ) : (
          <ul className="logs-ul">
            {logs.map((l) => (
              <li key={l.id || `${l.ts}-${l.message}`} className={`log-row level-${l.level}`}>
                <span className="log-level">{l.level}</span>
                <span className="log-meta">
                  {l.source}
                  {l.component ? `/${l.component}` : ""}
                </span>
                <span className="log-ts">{formatTs(l.ts)}</span>
                <p className="log-msg">{l.message}</p>
              </li>
            ))}
          </ul>
        )}
      </div>

      {reports.length > 0 ? (
        <div className="card logs-list">
          <div className="hd-icon-text-row" style={{ marginBottom: "0.75rem" }}>
            <span className="skills-form-dot" aria-hidden="true" />
            <h3 className="min-w-0" style={{ margin: 0 }}>
              {t("logs.reports")}
            </h3>
          </div>
          <ul className="logs-ul">
            {reports.map((r) => (
              <li key={r.id} className="log-row level-error">
                <span className="log-level">{r.kind}</span>
                <span className="log-meta">{r.source}</span>
                <span className="log-ts">{formatTs(r.ts)}</span>
                <p className="log-msg">{r.summary}</p>
                {r.file_path ? <p className="muted log-path">{r.file_path}</p> : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function formatTs(ts: string) {
  if (!ts) return "";
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}
