"use client";
import { useState, useEffect, useCallback, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, ChevronUp, ChevronDown, X, Activity, Clock, FlaskConical, ThermometerSnowflake, AlertTriangle } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || (process.env.NODE_ENV === "production" ? "" : "http://localhost:8001");

function formatTimeRemaining(seconds) {
  if (!seconds || seconds <= 0) return "Overdue";
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  const day = d.getDate().toString().padStart(2, '0');
  const month = d.toLocaleString("en-IN", { month: "short" });
  const time = d.toLocaleString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false });
  return `${day} ${month} ${time}`;
}

function timeAgo(iso) {
  if (!iso) return "";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}



const SunIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/></svg>
);
const MoonIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>
);

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [samples, setSamples] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [batches, setBatches] = useState([]);
  const [activeTab, setActiveTab] = useState("dashboard");
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState(null);
  


  const [toasts, setToasts] = useState([]);
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [showWebhookModal, setShowWebhookModal] = useState(false);
  


  const [searchQuery, setSearchQuery] = useState("");
  const [sortConfig, setSortConfig] = useState({ key: "received_at", direction: "desc" });
  const [selectedSample, setSelectedSample] = useState(null);
  const [sampleDetails, setSampleDetails] = useState(null);



  const [sampleId, setSampleId] = useState("");
  const [testCode, setTestCode] = useState("BIOC007");
  const [receivedAt, setReceivedAt] = useState("");
  const [userEmail, setUserEmail] = useState("");
  const [sending, setSending] = useState(false);
  const [deleting, setDeleting] = useState(false);



  useEffect(() => {
    const saved = localStorage.getItem('theme');
    const isDark = saved === 'dark'; 
    setIsDarkMode(isDark);
    if (isDark) document.documentElement.classList.add('dark');
  }, []);

  const toggleTheme = () => {
    const newDark = !isDarkMode;
    setIsDarkMode(newDark);
    localStorage.setItem('theme', newDark ? 'dark' : 'light');
    if (newDark) document.documentElement.classList.add('dark');
    else document.documentElement.classList.remove('dark');
  };

  const fetchData = useCallback(async () => {
    try {
      const [statsRes, samplesRes, alertsRes, batchesRes] = await Promise.all([
        fetch(`${API}/api/samples/stats`),
        fetch(`${API}/api/samples?limit=100`),
        fetch(`${API}/api/alerts?limit=20`),
        fetch(`${API}/api/batches`),
      ]);
      const [statsData, samplesData, alertsData, batchesData] = await Promise.all([
        statsRes.json(), samplesRes.json(), alertsRes.json(), batchesRes.json(),
      ]);
      setStats(statsData);
      setSamples(samplesData.samples || []);
      setAlerts(alertsData.alerts || []);
      setBatches(batchesData.batches || []);
      setFetchError(null);
    } catch (err) {
      console.error("Fetch error:", err);
      setFetchError("Failed to load data. API might be unreachable.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [fetchData]);



  useEffect(() => {
    if (selectedSample) {
      setSampleDetails(null); 

      fetch(`${API}/api/samples/${selectedSample.sample_id}`)
        .then(res => res.json())
        .then(data => setSampleDetails(data))
        .catch(err => console.error(err));
    }
  }, [selectedSample]);



  useEffect(() => {
    if (showWebhookModal) {
      const now = new Date();
      now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
      setReceivedAt(now.toISOString().slice(0, 16));
      setSampleId(`SAMP-${String(Date.now()).slice(-4)}`);
      setUserEmail("");
    }
  }, [showWebhookModal]);

  const showToast = (message, type = "success") => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 4000);
  };

  const sendWebhook = async () => {
    if (!sampleId || !testCode || !receivedAt) return;
    setSending(true);
    try {
      const res = await fetch(`${API}/api/webhook/sample`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sample_id: sampleId,
          test_code: testCode,
          user_email: userEmail || undefined,
          received_at: receivedAt + ":00",
        }),
      });
      const data = await res.json();
      if (res.ok) {
        const msg = data.missed_batch
          ? `⚠️ ${data.sample_id} Reassigned: missed original batch`
          : `✅ ${data.sample_id} Assigned to batch ${formatDate(data.batch_cutoff)}`;
        showToast(msg, data.missed_batch ? "error" : "success");
        setShowWebhookModal(false);
        fetchData();
      } else {
        showToast(data.detail || "Error processing webhook", "error");
      }
    } catch (err) {
      showToast("Connection error — is the backend running?", "error");
    }
    setSending(false);
  };

  const acknowledgeAlert = async (alertId) => {
    try {
      await fetch(`${API}/api/alerts/${alertId}/acknowledge`, { method: "POST" });
      fetchData();
    } catch (err) {
      console.error(err);
    }
  };

  const deleteSample = async (sampleId) => {
    if (!confirm(`Are you sure you want to delete sample ${sampleId}? This action cannot be undone.`)) return;
    setDeleting(true);
    try {
      const res = await fetch(`${API}/api/samples/${sampleId}`, { method: "DELETE" });
      if (res.ok) {
        showToast(`Sample ${sampleId} deleted successfully`, "success");
        setSelectedSample(null);
        fetchData();
      } else {
        const data = await res.json();
        showToast(data.detail || "Failed to delete sample", "error");
      }
    } catch (err) {
      showToast("Error connecting to server", "error");
    }
    setDeleting(false);
  };



  const handleSort = (key) => {
    let direction = "asc";
    if (sortConfig.key === key && sortConfig.direction === "asc") {
      direction = "desc";
    }
    setSortConfig({ key, direction });
  };



  const processedSamples = useMemo(() => {
    let result = [...samples];
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      result = result.filter(s => 
        (s.sample_id && s.sample_id.toLowerCase().includes(q)) || 
        (s.test_code && s.test_code.toLowerCase().includes(q)) ||
        (s.test_name && s.test_name.toLowerCase().includes(q)) ||
        (s.status && s.status.toLowerCase().includes(q))
      );
    }
    result.sort((a, b) => {
      let valA = a[sortConfig.key] || "";
      let valB = b[sortConfig.key] || "";
      if (valA < valB) return sortConfig.direction === "asc" ? -1 : 1;
      if (valA > valB) return sortConfig.direction === "asc" ? 1 : -1;
      return 0;
    });
    return result;
  }, [samples, searchQuery, sortConfig]);

  if (loading) {
    return <div style={{ display: "flex", justifyContent: "center", padding: "64px" }}>Loading laboratory data...</div>;
  }

  if (fetchError) {
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "50vh", gap: "16px" }}>
        <AlertTriangle size={48} color="var(--accent-red)" />
        <h2 style={{ color: "var(--accent-red)" }}>Connection Error</h2>
        <p style={{ color: "var(--text-muted)" }}>{fetchError}</p>
        <button className="btn primary" onClick={() => { setLoading(true); fetchData(); }}>Retry Connection</button>
      </div>
    );
  }

  return (
    <div className="app-container">


      <header className="header">
        <div className="header-left">
          <div className="header-logo">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M10 2v6"/><path d="M14 2v6"/><path d="M16 8v8a4 4 0 0 1-4 4v0a4 4 0 0 1-4-4V8"/><path d="M8 2h8"/></svg>
          </div>
          <div>
            <h1>TAT Monitor <span style={{fontSize: "13px", fontWeight: "500", color: "var(--accent-blue)", background: "var(--accent-blue-bg)", padding: "2px 8px", borderRadius: "12px", marginLeft: "8px"}}>Premium</span></h1>
            <div className="header-subtitle">Advanced Lab Operations & Pipeline Analytics</div>
          </div>
        </div>
        <div className="header-right">
          <div className="live-indicator">
            <motion.div animate={{ scale: [1, 1.2, 1] }} transition={{ repeat: Infinity, duration: 2 }} className="live-dot" />
            LIVE
          </div>
          <button className="theme-toggle" onClick={toggleTheme} aria-label="Toggle theme">
            {isDarkMode ? <SunIcon /> : <MoonIcon />}
          </button>
          <button className="btn primary" onClick={() => setShowWebhookModal(true)}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14"/><path d="M12 5v14"/></svg>
            Simulate Sample
          </button>
        </div>
      </header>



      <nav className="nav-tabs">
        {["dashboard", "alerts"].map((tab) => (
          <button
            key={tab}
            className={`nav-tab ${activeTab === tab ? "active" : ""}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab === "dashboard" ? "Live Dashboard" : "Alert Center"}
          </button>
        ))}
      </nav>

      {activeTab === "dashboard" && (
        <>


          <div className="stats-grid">
            <motion.div initial={{y: 20, opacity: 0}} animate={{y: 0, opacity: 1}} transition={{delay: 0.1}} className="stat-card blue">
              <div className="stat-label">Total Volume (24h)</div>
              <div className="stat-value"><Activity size={24} color="var(--accent-blue)" /> {stats?.recent_24h || 0}</div>
              <div className="stat-sub">Samples processed today</div>
            </motion.div>
            <motion.div initial={{y: 20, opacity: 0}} animate={{y: 0, opacity: 1}} transition={{delay: 0.2}} className="stat-card green">
              <div className="stat-label">On Track</div>
              <div className="stat-value"><Clock size={24} color="var(--accent-green)" /> {stats?.on_time || 0}</div>
              <div className="stat-sub">Safely inside TAT window</div>
            </motion.div>
            <motion.div initial={{y: 20, opacity: 0}} animate={{y: 0, opacity: 1}} transition={{delay: 0.3}} className="stat-card yellow">
              <div className="stat-label">Delayed Intakes</div>
              <div className="stat-value"><AlertTriangle size={24} color="var(--accent-yellow)" /> {stats?.delayed || 0}</div>
              <div className="stat-sub">Missed initial cutoff</div>
            </motion.div>
            <motion.div initial={{y: 20, opacity: 0}} animate={{y: 0, opacity: 1}} transition={{delay: 0.4}} className="stat-card red">
              <div className="stat-label">TAT Breaches</div>
              <div className="stat-value"><X size={24} color="var(--accent-red)" /> {stats?.breached || 0}</div>
              <div className="stat-sub">{stats?.active_alerts || 0} active alerts require action</div>
            </motion.div>
          </div>

          <div className="content-grid">


            <div className="panel">
              <div className="table-controls">
                <div className="search-bar">
                  <Search size={16} color="var(--text-muted)" />
                  <input 
                    type="text" 
                    placeholder="Search by Sample ID or Test Code..." 
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>
                <div style={{fontSize: "12px", color: "var(--text-muted)"}}>
                  Showing {processedSamples.length} of {samples.length} samples
                </div>
              </div>
              <div className="table-container">
                {processedSamples.length === 0 ? (
                  <div className="empty-state">
                    <div className="empty-state-icon">🔬</div>
                    <div className="empty-state-text">No samples match your filters</div>
                    <button className="btn" style={{marginTop:"12px"}} onClick={() => setSearchQuery("")}>Clear Search</button>
                  </div>
                ) : (
                  <table>
                    <thead>
                      <tr>
                        <th className="sortable" onClick={() => handleSort("status")}>
                          <div className="th-content">Status {sortConfig.key === "status" ? (sortConfig.direction === "asc" ? <ChevronUp size={14}/> : <ChevronDown size={14}/>) : null}</div>
                        </th>
                        <th className="sortable" onClick={() => handleSort("sample_id")}>
                          <div className="th-content">Sample ID {sortConfig.key === "sample_id" ? (sortConfig.direction === "asc" ? <ChevronUp size={14}/> : <ChevronDown size={14}/>) : null}</div>
                        </th>
                        <th className="sortable" onClick={() => handleSort("test_code")}>
                          <div className="th-content">Test Code {sortConfig.key === "test_code" ? (sortConfig.direction === "asc" ? <ChevronUp size={14}/> : <ChevronDown size={14}/>) : null}</div>
                        </th>
                        <th className="sortable" onClick={() => handleSort("received_at")}>
                          <div className="th-content">Received {sortConfig.key === "received_at" ? (sortConfig.direction === "asc" ? <ChevronUp size={14}/> : <ChevronDown size={14}/>) : null}</div>
                        </th>
                        <th className="sortable" onClick={() => handleSort("eta")}>
                          <div className="th-content">Result ETA {sortConfig.key === "eta" ? (sortConfig.direction === "asc" ? <ChevronUp size={14}/> : <ChevronDown size={14}/>) : null}</div>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      <AnimatePresence>
                        {processedSamples.map((s) => {
                          const etaClass = s.is_overdue ? "overdue" : s.time_remaining_seconds < 7200 ? "at-risk" : "on-time";
                          return (
                            <motion.tr 
                              key={s.sample_id}
                              initial={{ opacity: 0, y: 10 }}
                              animate={{ opacity: 1, y: 0 }}
                              exit={{ opacity: 0, scale: 0.95 }}
                              transition={{ duration: 0.2 }}
                              className="interactive-row"
                              onClick={() => setSelectedSample(s)}
                            >
                              <td><span className={`status-badge ${s.status}`}>{s.status}</span></td>
                              <td><span className="mono highlight-text">{s.sample_id}</span></td>
                              <td>
                                <div className="mono highlight-text">{s.test_code}</div>
                                <div style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "2px", maxWidth:"150px", overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{s.test_name}</div>
                              </td>
                              <td><span className="mono">{formatDate(s.received_at)}</span></td>
                              <td>
                                <span className={`mono eta-text ${etaClass}`}>
                                  {s.is_overdue ? "OVERDUE" : formatTimeRemaining(s.time_remaining_seconds)}
                                </span>
                              </td>
                            </motion.tr>
                          );
                        })}
                      </AnimatePresence>
                    </tbody>
                  </table>
                )}
              </div>
            </div>



            <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
              <div className="panel">
                <div className="panel-header" style={{ background: "var(--accent-red-bg)" }}>
                  <div className="panel-title" style={{ color: "var(--accent-red)" }}>Active Interventions</div>
                  {alerts.filter((a) => !a.acknowledged).length > 0 && (
                    <span className="panel-badge" style={{ borderColor: "var(--accent-red)", color: "var(--accent-red)" }}>
                      {alerts.filter((a) => !a.acknowledged).length} action(s)
                    </span>
                  )}
                </div>
                <div className="alert-list">
                  {alerts.length === 0 ? (
                    <div className="empty-state">
                      <div className="empty-state-icon">✅</div>
                      <div className="empty-state-text">Pipeline healthy. No active alerts.</div>
                    </div>
                  ) : (
                    <AnimatePresence>
                      {alerts.map((a) => (
                        <motion.div key={a.id} initial={{opacity: 0, x: 20}} animate={{opacity: 1, x: 0}} exit={{opacity: 0}} className={`alert-item ${a.acknowledged ? "acknowledged" : ""}`}>
                          <div className={`alert-type ${a.alert_type}`}>{a.alert_type.replace("_", " ")}</div>
                          <div className="alert-message">{a.message}</div>
                          <div className="alert-time">{timeAgo(a.created_at)}</div>
                          {!a.acknowledged && (
                            <button className="btn-acknowledge" onClick={() => acknowledgeAlert(a.id)}>Acknowledge Issue</button>
                          )}
                        </motion.div>
                      ))}
                    </AnimatePresence>
                  )}
                </div>
              </div>

              <div className="panel">
                <div className="panel-header">
                  <div className="panel-title">Batch Processing Queue</div>
                </div>
                <div className="batch-list">
                  {batches.length === 0 ? (
                    <div className="empty-state">
                      <div className="empty-state-icon">⏳</div>
                      <div className="empty-state-text">Queues empty</div>
                    </div>
                  ) : (
                    batches.map((b, i) => (
                      <div key={i} className="batch-item">
                        <div>
                          <div className="batch-test-code mono">{b.test_code}</div>
                          <div className="batch-schedule">Closes {formatDate(b.batch_cutoff)}</div>
                        </div>
                        <div className="batch-counts">
                          <span className="samples" title="Queued Samples">{b.sample_count} pending</span>

                          {b.missed_count > 0 && <span className="missed" title="Delayed intakes">({b.missed_count} delayed)</span>}

                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>
        </>
      )}

      {activeTab === "alerts" && (
        <div className="panel" style={{ marginTop: "24px", maxWidth: "1000px", marginLeft: "auto", marginRight: "auto" }}>
          <div className="panel-header">
            <div className="panel-title">Alert Center Overview</div>
          </div>
          <div className="alert-list" style={{ maxHeight: "none", display: "flex", flexDirection: "column", gap: "12px" }}>
            {alerts.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon">✅</div>
                <div className="empty-state-text">Pipeline healthy. No alerts have been generated yet.</div>
              </div>
            ) : (
              <AnimatePresence>
                {alerts.map((a) => (
                  <motion.div key={a.id} initial={{opacity: 0, y: 10}} animate={{opacity: 1, y: 0}} exit={{opacity: 0}} className={`alert-item ${a.acknowledged ? "acknowledged" : ""}`}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" }}>
                      <div>
                        <div className={`alert-type ${a.alert_type}`}>{a.alert_type.replace("_", " ").toUpperCase()}</div>
                        <div className="alert-message" style={{ fontSize: "14px", marginTop: "4px" }}>{a.message}</div>
                        <div className="alert-time" style={{ marginTop: "8px" }}>{formatDate(a.created_at)} ({timeAgo(a.created_at)})</div>
                      </div>
                      {!a.acknowledged ? (
                        <button className="btn-acknowledge" style={{ flexShrink: 0, marginLeft: "16px", padding: "8px 16px" }} onClick={() => acknowledgeAlert(a.id)}>Acknowledge Issue</button>
                      ) : (
                        <div style={{ fontSize: "12px", color: "var(--accent-green)", fontWeight: "600", padding: "4px 12px", background: "var(--accent-green-bg)", borderRadius: "12px" }}>Resolved</div>
                      )}
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>
            )}
          </div>
        </div>
      )}



      <AnimatePresence>
        {selectedSample && (
          <div className="drawer-overlay" onClick={() => setSelectedSample(null)}>
            <motion.div 
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ type: "spring", damping: 25, stiffness: 200 }}
              className="drawer"
              onClick={e => e.stopPropagation()}
            >
              <div className="drawer-header">
                <div className="drawer-title-group">
                  <span className={`status-badge ${selectedSample.status}`} style={{width: "max-content", marginBottom: "8px"}}>{selectedSample.status}</span>
                  <div style={{fontSize: "20px", fontWeight: "700", fontFamily: "JetBrains Mono"}}>{selectedSample.sample_id}</div>
                  <div style={{fontSize: "13px", color: "var(--text-muted)"}}>{selectedSample.test_name || selectedSample.test_code}</div>
                </div>
                <div style={{display: "flex", gap: "8px", alignItems: "flex-start"}}>
                  <button onClick={() => deleteSample(selectedSample.sample_id)} disabled={deleting} style={{padding: "6px 10px", background: "var(--accent-red-bg)", color: "var(--accent-red)", border: "1px solid var(--accent-red)", borderRadius: "6px", cursor: "pointer", fontSize: "12px", fontWeight: "600"}}>
                    {deleting ? "Deleting..." : "Delete"}
                  </button>
                  <button className="btn-close" onClick={() => setSelectedSample(null)}><X size={20} /></button>
                </div>
              </div>
              
              <div className="drawer-body">


                {sampleDetails && (
                  <div className="drawer-section">
                    <div className="drawer-section-title">Test Parameters (EDOS)</div>
                    <div className="detail-grid">
                      <div className="detail-item">
                        <span className="detail-label">Specimen Type</span>
                        <span className="detail-value" style={{display: "flex", gap: "6px", alignItems:"center"}}>
                          <FlaskConical size={14} color="var(--accent-blue)"/> {sampleDetails.specimen_type || "N/A"}
                        </span>
                      </div>
                      <div className="detail-item">
                        <span className="detail-label">Storage Temp</span>
                        <span className="detail-value" style={{display: "flex", gap: "6px", alignItems:"center"}}>
                          <ThermometerSnowflake size={14} color="var(--accent-blue)"/> {sampleDetails.temperature || "Ambient"}
                        </span>
                      </div>
                      <div className="detail-item">
                        <span className="detail-label">Test Group</span>
                        <span className="detail-value">{sampleDetails.test_group || "N/A"}</span>
                      </div>
                    </div>
                  </div>
                )}



                <div className="drawer-section">
                  <div className="drawer-section-title">Lifecycle Timeline</div>
                  <div className="timeline">
                    
                    <div className="timeline-step">
                      <div className="step-marker completed"></div>
                      <div className="step-line"></div>
                      <div className="step-content">
                        <div className="step-title">Sample Accessioned</div>
                        <div className="step-time">{formatDate(selectedSample.received_at)}</div>
                      </div>
                    </div>

                    <div className="timeline-step">
                      <div className={`step-marker ${selectedSample.missed_batch ? "breached" : "completed"}`}></div>
                      <div className="step-line"></div>
                      <div className="step-content">
                        <div className="step-title" style={{color: selectedSample.missed_batch ? "var(--accent-red)" : "inherit"}}>
                          {selectedSample.missed_batch ? "Batch Target Missed & Reassigned" : "Assigned to Batch"}
                        </div>
                        <div className="step-time">Batch Processing starts at: {formatDate(selectedSample.batch_cutoff)}</div>
                        <div style={{fontSize: "11px", color: "var(--text-muted)", marginTop: "4px", padding: "6px 8px", background: "var(--bg-hover)", borderRadius: "4px"}}>
                          EDOS Schedule: {sampleDetails?.schedule_raw || selectedSample.test_code}
                        </div>
                      </div>
                    </div>

                    <div className="timeline-step">
                      <div className={`step-marker ${(selectedSample.status === 'processing' || selectedSample.status === 'completed') ? "completed" : "active"}`}></div>
                      <div className="step-line"></div>
                      <div className="step-content">
                        <div className="step-title">Processing Result</div>
                        <div className="step-time">Pending Lab Completion</div>
                      </div>
                    </div>

                    <div className="timeline-step">
                      <div className={`step-marker ${selectedSample.is_overdue ? "breached" : selectedSample.status === 'completed' ? "completed" : ""}`}></div>
                      <div className="step-line" style={{display: "none"}}></div>
                      <div className="step-content">
                        <div className="step-title" style={{color: selectedSample.is_overdue ? "var(--accent-red)" : "inherit"}}>Calculated ETA (Target)</div>
                        <div className="step-time">Result Expected By: {formatDate(selectedSample.eta)}</div>
                        <div style={{fontSize: "11px", color: "var(--text-muted)", marginTop: "4px", padding: "6px 8px", background: "var(--bg-hover)", borderRadius: "4px"}}>
                          EDOS TAT Rule: {sampleDetails?.tat_raw || selectedSample.test_code}
                        </div>
                      </div>
                    </div>

                  </div>
                </div>

              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>



      <AnimatePresence>
        {showWebhookModal && (
          <div className="modal-overlay" onClick={() => setShowWebhookModal(false)}>
            <motion.div initial={{scale: 0.95, opacity: 0}} animate={{scale: 1, opacity: 1}} exit={{scale: 0.95, opacity: 0}} className="modal" onClick={e => e.stopPropagation()}>
              <div className="modal-header">
                <div className="modal-title">Simulate Intake</div>
                <button className="btn-close" onClick={() => setShowWebhookModal(false)}><X size={20}/></button>
              </div>
              <div className="modal-body">
                <div className="form-group">
                  <label>Sample ID / Barcode</label>
                  <input className="mono" value={sampleId} onChange={(e) => setSampleId(e.target.value)} placeholder="SAMP-001" />
                </div>
                <div className="form-group">
                  <label>EDOS Test Code</label>
                  <input className="mono" value={testCode} onChange={(e) => setTestCode(e.target.value)} placeholder="BIOC007" />
                </div>
                <div className="form-group">
                  <label>Notification Email (Optional)</label>
                  <input type="email" value={userEmail} onChange={(e) => setUserEmail(e.target.value)} placeholder="patient@example.com" />
                </div>
                <div className="form-group">
                  <label>Accession Time (Received At)</label>
                  <input type="datetime-local" className="mono" value={receivedAt} onChange={(e) => setReceivedAt(e.target.value)} />
                </div>
              </div>
              <div className="modal-footer">
                <button className="btn" onClick={() => setShowWebhookModal(false)}>Cancel</button>
                <button className="btn primary" onClick={sendWebhook} disabled={sending}>{sending ? "Sending..." : "Submit Webhook"}</button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>



      <div className="toast-container">
        <AnimatePresence>
          {toasts.map(t => (
            <motion.div key={t.id} initial={{opacity:0, y: 20}} animate={{opacity:1, y: 0}} exit={{opacity:0, scale: 0.9}} className={`toast ${t.type}`}>{t.message}</motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
