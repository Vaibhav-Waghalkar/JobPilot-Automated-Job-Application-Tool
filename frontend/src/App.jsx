import React, { useState, useEffect } from 'react';
import './App.css';

const API_BASE = '/api';

export default function App() {
  // Navigation: 5 items only (Home, Jobs, Profile, Documents, Settings)
  const [navTab, setNavTab] = useState('home');

  // Engine Status & Stats
  const [engineStatus, setEngineStatus] = useState({
    status: 'Stopped',
    mode: 'REVIEW',
    current_job_id: null,
    current_job_title: null,
    current_company: null,
    current_step: null,
    stats: { found: 0, matched: 0, applied: 0, skipped: 0, needs_you: 0 },
    waiting_for_approval: [],
    needs_you_questions: [],
    test_run_jobs: []
  });

  // Platforms login status
  const [platformStatus, setPlatformStatus] = useState({
    internshala: { logged_in: false, details: 'Checking session...' },
    naukri: { logged_in: false, details: 'Checking session...' }
  });
  const [loginActionStatus, setLoginActionStatus] = useState({ internshala: null, naukri: null });

  // Settings / Preferences
  const [preferences, setPreferences] = useState({
    target_roles: ['Backend Developer', 'Python Developer', 'Software Developer'],
    min_salary: 500000,
    preferred_locations: ['Pune', 'Bengaluru', 'Remote'],
    allow_undisclosed_salary: true,
    max_experience_years: 2.0,
    default_match_threshold: 70,
    blacklisted_companies: ['CryptoScamCo']
  });

  // Fixed Profile & Details
  const [fixedProfile, setFixedProfile] = useState({});
  const [vaultFacts, setVaultFacts] = useState([]);
  const [missingInfo, setMissingInfo] = useState({ missing_count: 0, items: [] });
  const [projectTiers, setProjectTiers] = useState([]);
  const [savedAnswers, setSavedAnswers] = useState([]);
  const [reviewItems, setReviewItems] = useState([]);
  const [conflicts, setConflicts] = useState([]);

  // Jobs table & drawer
  const [jobs, setJobs] = useState([]);
  const [jobsFilter, setJobsFilter] = useState('all');
  const [selectedJobDrawer, setSelectedJobDrawer] = useState(null);
  const [isPreviewingMatches, setIsPreviewingMatches] = useState(false);
  const [previewResults, setPreviewResults] = useState(null);

  // Documents
  const [resumes, setResumes] = useState([]);
  const [documents, setDocuments] = useState([]);

  // Activity logs
  const [activityLogs, setActivityLogs] = useState([]);

  // Interactive controls
  const [engineMode, setEngineMode] = useState('DRY_RUN');
  const [statusMessage, setStatusMessage] = useState('');
  const [profileSubtab, setProfileSubtab] = useState('basics');

  // Inline edit state
  const [editingFactId, setEditingFactId] = useState(null);
  const [editingFactData, setEditingFactData] = useState({ title: '', content: '' });
  const [newFactData, setNewFactData] = useState({ title: '', content: '', section: 'skill' });
  const [showAddFact, setShowAddFact] = useState(false);

  // Needs you countdown and input
  const [needsYouAnswer, setNeedsYouAnswer] = useState({});
  const [countdownSeconds, setCountdownSeconds] = useState(300);

  // Poll Engine Status, Missing Info, Activity Logs, and Platforms Login Status
  useEffect(() => {
    fetchAllData();
    const interval = setInterval(() => {
      fetchEngineStatus();
      fetchPlatformStatus();
    }, 2500);
    return () => clearInterval(interval);
  }, []);

  // 5-minute countdown timer for active Needs You questions
  useEffect(() => {
    if (engineStatus.needs_you_questions && engineStatus.needs_you_questions.length > 0) {
      const timer = setInterval(() => {
        setCountdownSeconds((prev) => (prev > 0 ? prev - 1 : 0));
      }, 1000);
      return () => clearInterval(timer);
    } else {
      setCountdownSeconds(300);
    }
  }, [engineStatus.needs_you_questions]);

  const fetchAllData = async () => {
    try {
      fetchEngineStatus();
      fetchPlatformStatus();
      fetchProfileData();
      fetchJobs();
      fetchDocuments();
      fetchSettings();
      fetchActivityLogs();
    } catch (e) {
      console.error('Error fetching dashboard data:', e);
    }
  };

  const fetchPlatformStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/workflow/platform-status`);
      if (res.ok) {
        const data = await res.json();
        setPlatformStatus(data);
      }
    } catch (e) {
      console.error('Failed to fetch platform status', e);
    }
  };

  const fetchEngineStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/engine/status`);
      if (res.ok) {
        const data = await res.json();
        setEngineStatus(data);
      }
    } catch (e) {
      console.error('Failed to fetch engine status', e);
    }
  };

  const fetchProfileData = async () => {
    try {
      const [pRes, fRes, mRes, ptRes, qaRes, revRes, confRes] = await Promise.all([
        fetch(`${API_BASE}/vault/fixed-profile`),
        fetch(`${API_BASE}/vault/facts`),
        fetch(`${API_BASE}/vault/missing-info`),
        fetch(`${API_BASE}/vault/project-tiers`),
        fetch(`${API_BASE}/vault/saved-answers`),
        fetch(`${API_BASE}/vault/import/review-items?status=pending`),
        fetch(`${API_BASE}/vault/conflicts`)
      ]);
      if (pRes.ok) setFixedProfile(await pRes.json());
      if (fRes.ok) setVaultFacts(await fRes.json());
      if (mRes.ok) setMissingInfo(await mRes.json());
      if (ptRes.ok) setProjectTiers(await ptRes.json());
      if (qaRes.ok) setSavedAnswers(await qaRes.json());
      if (revRes.ok) setReviewItems(await revRes.json());
      if (confRes.ok) setConflicts(await confRes.json());
    } catch (e) {
      console.error('Error fetching profile data', e);
    }
  };

  const fetchJobs = async () => {
    try {
      const res = await fetch(`${API_BASE}/discovery/jobs`);
      if (res.ok) setJobs(await res.json());
    } catch (e) {
      console.error('Failed to fetch jobs', e);
    }
  };

  const fetchDocuments = async () => {
    try {
      const [rRes, dRes] = await Promise.all([
        fetch(`${API_BASE}/vault/resumes`),
        fetch(`${API_BASE}/vault/documents`)
      ]);
      if (rRes.ok) setResumes(await rRes.json());
      if (dRes.ok) setDocuments(await dRes.json());
    } catch (e) {
      console.error('Failed to fetch documents', e);
    }
  };

  const fetchSettings = async () => {
    try {
      const res = await fetch(`${API_BASE}/vault/preferences`);
      if (res.ok) setPreferences(await res.json());
    } catch (e) {
      console.error('Failed to fetch preferences', e);
    }
  };

  const fetchActivityLogs = async () => {
    try {
      const res = await fetch(`${API_BASE}/workflow/activity-logs`);
      if (res.ok) setActivityLogs(await res.json());
    } catch (e) {
      console.error('Failed to fetch activity logs', e);
    }
  };

  // Engine Actions
  const handleStartEngine = async () => {
    if (engineMode === 'AUTO') {
      const confirmed = window.confirm(
        'Confirmation required: You have selected AUTO mode. The tool will automatically submit applications without human approval on final forms. Do you wish to proceed?'
      );
      if (!confirmed) return;
    }

    setStatusMessage('Starting engine...');
    try {
      const res = await fetch(`${API_BASE}/engine/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: engineMode, platform: 'internshala', max_applications: 2 })
      });
      const data = await res.json();
      if (!res.ok) {
        alert(data.detail || 'Could not start engine');
        setStatusMessage(data.detail || 'Start failed');
      } else {
        setStatusMessage(data.message || 'Engine started');
        fetchEngineStatus();
      }
    } catch (e) {
      alert('Error starting engine: ' + e);
    }
  };

  const handlePauseEngine = async () => {
    try {
      await fetch(`${API_BASE}/engine/pause`, { method: 'POST' });
      fetchEngineStatus();
    } catch (e) {
      console.error(e);
    }
  };

  const handleResumeEngine = async () => {
    try {
      await fetch(`${API_BASE}/engine/resume`, { method: 'POST' });
      fetchEngineStatus();
    } catch (e) {
      console.error(e);
    }
  };

  const handleStopEngine = async () => {
    try {
      await fetch(`${API_BASE}/engine/stop`, { method: 'POST' });
      fetchEngineStatus();
    } catch (e) {
      console.error(e);
    }
  };

  // Review approval/skip
  const handleApproveApplication = async (appId) => {
    try {
      const res = await fetch(`${API_BASE}/engine/approve-application/${appId}`, { method: 'POST' });
      if (res.ok) {
        fetchEngineStatus();
        fetchJobs();
      }
    } catch (e) {
      alert('Approval failed: ' + e);
    }
  };

  const handleSkipApplication = async (appId) => {
    try {
      const res = await fetch(`${API_BASE}/engine/skip-application/${appId}`, { method: 'POST' });
      if (res.ok) {
        fetchEngineStatus();
        fetchJobs();
      }
    } catch (e) {
      alert('Skip failed: ' + e);
    }
  };

  // Needs you answer submission
  const handleSubmitNeedsYouAnswer = async (appId, question) => {
    const ans = needsYouAnswer[appId];
    if (!ans || !ans.trim()) {
      alert('Please enter an answer or click Skip.');
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/workflow/needs-you/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          application_id: appId,
          question: question,
          answer: ans
        })
      });
      if (res.ok) {
        setNeedsYouAnswer({ ...needsYouAnswer, [appId]: '' });
        fetchEngineStatus();
        fetchProfileData();
      }
    } catch (e) {
      alert('Failed to submit answer: ' + e);
    }
  };

  // Project Tier and Usage Update
  const handleProjectTierChange = async (projId, newTier) => {
    try {
      await fetch(`${API_BASE}/vault/project-tiers/${projId}/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tier: newTier })
      });
      fetchProfileData();
    } catch (e) {
      console.error('Failed to update project tier', e);
    }
  };

  const handleProjectUseToggle = async (projId, currentVal) => {
    try {
      await fetch(`${API_BASE}/vault/project-tiers/${projId}/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ use_in_applications: !currentVal })
      });
      fetchProfileData();
    } catch (e) {
      console.error('Failed to toggle project usage', e);
    }
  };

  // Staged Review Items: Approve All / Reject All
  const handleBulkApproveReviewItems = async () => {
    const confirmed = window.confirm(`Approve all ${reviewItems.length} pending staged review items into verified vault facts?`);
    if (!confirmed) return;
    try {
      const res = await fetch(`${API_BASE}/vault/import/review-items/bulk-approve`, { method: 'POST' });
      const data = await res.json();
      alert(data.message);
      fetchProfileData();
    } catch (e) {
      alert('Bulk approve failed: ' + e);
    }
  };

  const handleBulkRejectReviewItems = async () => {
    const confirmed = window.confirm(`Reject all ${reviewItems.length} pending staged review items?`);
    if (!confirmed) return;
    try {
      const res = await fetch(`${API_BASE}/vault/import/review-items/bulk-reject`, { method: 'POST' });
      const data = await res.json();
      alert(data.message);
      fetchProfileData();
    } catch (e) {
      alert('Bulk reject failed: ' + e);
    }
  };

  const handleDecideReviewItem = async (itemId, action) => {
    try {
      await fetch(`${API_BASE}/vault/import/review-items/${itemId}/decide`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action })
      });
      fetchProfileData();
    } catch (e) {
      alert('Action failed: ' + e);
    }
  };

  // Fact Editing
  const handleSaveFact = async (factId) => {
    try {
      await fetch(`${API_BASE}/vault/facts/${factId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editingFactData)
      });
      setEditingFactId(null);
      fetchProfileData();
    } catch (e) {
      alert('Error updating fact: ' + e);
    }
  };

  const handleDeleteFact = async (factId) => {
    if (!window.confirm('Delete this fact from vault?')) return;
    try {
      await fetch(`${API_BASE}/vault/facts/${factId}`, { method: 'DELETE' });
      fetchProfileData();
    } catch (e) {
      alert('Error deleting fact: ' + e);
    }
  };

  const handleCreateFact = async () => {
    if (!newFactData.title || !newFactData.content) {
      alert('Title and content are required.');
      return;
    }
    try {
      await fetch(`${API_BASE}/vault/facts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newFactData)
      });
      setShowAddFact(false);
      setNewFactData({ title: '', content: '', section: 'skill' });
      fetchProfileData();
    } catch (e) {
      alert('Error adding fact: ' + e);
    }
  };

  // Live Listing Match Preview (No applying)
  const handlePreviewMatches = async () => {
    setIsPreviewingMatches(true);
    try {
      const res = await fetch(`${API_BASE}/discovery/test-live-listing`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ limit: 5, job_type: 'job' })
      });
      const data = await res.json();
      setPreviewResults(data.results || []);
    } catch (e) {
      alert('Preview matches error: ' + e);
    } finally {
      setIsPreviewingMatches(false);
    }
  };

  // Saved Answers Delete
  const handleDeleteSavedAnswer = async (qaId) => {
    if (!window.confirm('Delete this saved answer?')) return;
    try {
      await fetch(`${API_BASE}/vault/saved-answers/${qaId}`, { method: 'DELETE' });
      fetchProfileData();
    } catch (e) {
      alert('Failed to delete answer: ' + e);
    }
  };

  // Fixed Profile Save
  const handleSaveFixedProfile = async () => {
    try {
      await fetch(`${API_BASE}/vault/fixed-profile`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(fixedProfile)
      });
      alert('Profile details saved.');
      fetchProfileData();
    } catch (e) {
      alert('Failed to save profile: ' + e);
    }
  };

  // Preferences Save
  const handleSavePreferences = async () => {
    try {
      await fetch(`${API_BASE}/vault/preferences`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(preferences)
      });
      alert('Settings saved.');
      fetchSettings();
    } catch (e) {
      alert('Failed to save settings: ' + e);
    }
  };

  // Open browser login in detached subprocess & detect login
  const handleOpenLogin = async (platform) => {
    setLoginActionStatus((prev) => ({
      ...prev,
      [platform]: `Launching browser for ${platform}...`
    }));
    try {
      const res = await fetch(`${API_BASE}/workflow/browser/open-login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ platform })
      });
      const data = await res.json();
      if (!res.ok || data.status === 'error') {
        const errorDetail = data.detail || data.error || data.message || 'Failed to open browser';
        setLoginActionStatus((prev) => ({
          ...prev,
          [platform]: `Error: ${errorDetail}`
        }));
        alert(`Failed to open ${platform} login browser:\n${errorDetail}`);
      } else {
        setLoginActionStatus((prev) => ({
          ...prev,
          [platform]: `Browser window opened. Please log in; status will update to "Logged in" automatically.`
        }));
        fetchPlatformStatus();
      }
    } catch (e) {
      const errorMsg = e.message || String(e);
      setLoginActionStatus((prev) => ({
        ...prev,
        [platform]: `Error: ${errorMsg}`
      }));
      alert(`Error connecting to server:\n${errorMsg}`);
    }
  };

  // Format plain-language skip reasons for Jobs view
  const formatPlainLanguageReason = (job) => {
    if (job.status !== 'skipped') {
      if (job.status === 'applied') return 'Applied successfully';
      if (job.status === 'needs_you') return job.needs_you_reason || 'Requires user input';
      if (job.status === 'matched') return `Matched (Score: ${job.match_score}/100)`;
      return '-';
    }

    const raw = job.skip_reason || '';
    const titleLower = (job.title || '').toLowerCase();

    // 1. Non-tech role
    if (raw.toLowerCase().includes('non-tech') || 
        titleLower.includes('content') || 
        titleLower.includes('graphic') || 
        titleLower.includes('marketing') || 
        titleLower.includes('sales')) {
      return `Non-tech role (${job.title})`;
    }

    // 2. Empty profile / No verified facts
    if (raw.includes('No verified') || raw.includes('Match score 0') || (job.match_score === 0)) {
      return 'No verified facts in profile';
    }

    // 3. Salary below threshold
    if (raw.toLowerCase().includes('salary') || raw.toLowerCase().includes('lpa')) {
      return 'Salary below 5 LPA';
    }

    // 4. Stipend below threshold
    if (raw.toLowerCase().includes('stipend')) {
      return 'Stipend below ₹10,000/month';
    }

    // 5. Experience
    if (raw.toLowerCase().includes('experience')) {
      return 'Experience exceeds fresher cap (2.0 years)';
    }

    // 6. Blacklisted
    if (raw.toLowerCase().includes('blacklist')) {
      return `Blacklisted company (${job.company})`;
    }

    // 7. General score below threshold
    if (raw.includes('below threshold')) {
      return `Match score ${job.match_score || 0}/100 below threshold`;
    }

    return raw || 'Skipped by filters';
  };

  const filteredJobs = jobs.filter((j) => {
    if (jobsFilter === 'all') return true;
    return j.status === jobsFilter;
  });

  return (
    <div className="app-container">
      {/* Top Navigation Bar */}
      <header className="top-header">
        <div className="brand-section">
          <span className="brand-title">JobPilot</span>
          <span className="brand-version">v1.0</span>
        </div>

        <nav className="nav-tabs">
          <button
            className={`nav-tab-btn ${navTab === 'home' ? 'active' : ''}`}
            onClick={() => setNavTab('home')}
          >
            Home
          </button>
          <button
            className={`nav-tab-btn ${navTab === 'jobs' ? 'active' : ''}`}
            onClick={() => setNavTab('jobs')}
          >
            Jobs
          </button>
          <button
            className={`nav-tab-btn ${navTab === 'profile' ? 'active' : ''}`}
            onClick={() => setNavTab('profile')}
          >
            Profile
          </button>
          <button
            className={`nav-tab-btn ${navTab === 'documents' ? 'active' : ''}`}
            onClick={() => setNavTab('documents')}
          >
            Documents
          </button>
          <button
            className={`nav-tab-btn ${navTab === 'settings' ? 'active' : ''}`}
            onClick={() => setNavTab('settings')}
          >
            Settings
          </button>
        </nav>

        <div className="header-status-section">
          <div className="status-badge">
            <span
              className={`status-dot ${
                engineStatus.status === 'Running'
                  ? 'running'
                  : engineStatus.status === 'Paused'
                  ? 'paused'
                  : 'stopped'
              }`}
            />
            <span>Engine: {engineStatus.status}</span>
          </div>

          <button
            className="needs-you-btn"
            onClick={() => setNavTab('home')}
          >
            Needs you ({engineStatus.stats.needs_you})
          </button>
        </div>
      </header>

      {/* Main Container */}
      <main className="main-content">
        {/* ======================= HOME (DASHBOARD) ======================= */}
        {navTab === 'home' && (
          <div>
            {/* Engine Panel */}
            <div className="panel">
              {/* Engine Readiness Banner */}
              {(() => {
                const isInternshalaLoggedIn = platformStatus.internshala?.logged_in;
                const verifiedFactsCount = vaultFacts.filter((f) => f.verified).length;
                const hasResume = resumes.length > 0;
                const isReady = isInternshalaLoggedIn && verifiedFactsCount > 0 && hasResume;

                return (
                  <div
                    style={{
                      marginBottom: '16px',
                      padding: '12px 16px',
                      background: isReady ? 'rgba(34, 197, 94, 0.08)' : 'rgba(234, 179, 8, 0.08)',
                      borderLeft: isReady ? '4px solid var(--success)' : '4px solid var(--warning)',
                      borderRadius: '4px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: '12px'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <span
                        style={{
                          width: '10px',
                          height: '10px',
                          borderRadius: '50%',
                          background: isReady ? 'var(--success)' : 'var(--warning)',
                          display: 'inline-block'
                        }}
                      />
                      <div>
                        <strong style={{ fontSize: '13px', color: 'var(--text-main)', marginRight: '8px' }}>
                          {isReady ? 'Ready to apply' : 'Ready State: Action Required'}
                        </strong>
                        <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                          {isReady
                            ? '• Internshala logged in • Verified facts loaded • Resume ready'
                            : !isInternshalaLoggedIn
                            ? '• Internshala not logged in (Log in via Settings > Platforms)'
                            : verifiedFactsCount === 0
                            ? '• No verified profile facts (Approve in Profile > Review imported data)'
                            : '• No resumes uploaded (Add in Documents)'}
                        </span>
                      </div>
                    </div>
                    {!isInternshalaLoggedIn && (
                      <button
                        className="secondary"
                        style={{ padding: '4px 10px', fontSize: '11px', whiteSpace: 'nowrap' }}
                        onClick={() => setNavTab('settings')}
                      >
                        Go to Settings &gt; Platforms
                      </button>
                    )}
                  </div>
                );
              })()}

              <div className="engine-panel">
                <div className="engine-control-row">
                  <div className="engine-buttons">
                    <button
                      className="primary engine-start-btn"
                      onClick={handleStartEngine}
                      disabled={engineStatus.status === 'Running'}
                    >
                      Start applying
                    </button>
                    {engineStatus.status === 'Running' ? (
                      <button className="secondary" onClick={handlePauseEngine}>
                        Pause
                      </button>
                    ) : engineStatus.status === 'Paused' ? (
                      <button className="secondary" onClick={handleResumeEngine}>
                        Resume
                      </button>
                    ) : null}
                    <button
                      className="secondary"
                      onClick={handleStopEngine}
                      disabled={engineStatus.status === 'Stopped'}
                    >
                      Stop
                    </button>
                  </div>

                  {/* Mode Selector */}
                  <div className="mode-selector">
                    <button
                      className={`mode-option ${engineMode === 'DRY_RUN' ? 'active' : ''}`}
                      onClick={() => setEngineMode('DRY_RUN')}
                    >
                      Dry run
                    </button>
                    <button
                      className={`mode-option ${engineMode === 'REVIEW' ? 'active' : ''}`}
                      onClick={() => setEngineMode('REVIEW')}
                    >
                      Review
                    </button>
                    <button
                      className={`mode-option ${engineMode === 'AUTO' ? 'active' : ''}`}
                      onClick={() => setEngineMode('AUTO')}
                    >
                      Auto
                    </button>
                  </div>
                </div>

                {/* Live Step Progress Banner */}
                {engineStatus.current_step && (
                  <div
                    style={{
                      marginTop: '12px',
                      padding: '10px 14px',
                      background: engineStatus.current_step.toLowerCase().includes('log in') || engineStatus.current_step.toLowerCase().includes('failed') || engineStatus.current_step.toLowerCase().includes('error')
                        ? 'rgba(239, 68, 68, 0.1)'
                        : 'rgba(59, 130, 246, 0.08)',
                      borderLeft: engineStatus.current_step.toLowerCase().includes('log in') || engineStatus.current_step.toLowerCase().includes('failed') || engineStatus.current_step.toLowerCase().includes('error')
                        ? '3px solid var(--danger)'
                        : '3px solid var(--primary)',
                      borderRadius: '4px',
                      fontSize: '13px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: '12px'
                    }}
                  >
                    <div>
                      <strong style={{ color: 'var(--text-main)', marginRight: '8px' }}>
                        {engineStatus.status === 'Running' ? 'Progress:' : 'Status:'}
                      </strong>
                      <span style={{ color: 'var(--text-main)' }}>{engineStatus.current_step}</span>
                    </div>
                    {engineStatus.current_step.toLowerCase().includes('log in') && (
                      <button
                        className="secondary"
                        style={{ padding: '4px 10px', fontSize: '12px' }}
                        onClick={() => setNavTab('settings')}
                      >
                        Go to Settings &gt; Platforms
                      </button>
                    )}
                  </div>
                )}

                {/* One-line summary */}
                <div className="engine-summary-line" style={{ marginTop: '12px' }}>
                  <span>
                    Internshala | Roles: {(preferences.target_roles || []).join(', ')} | Type: Job &amp; Internship | Min salary: ₹5 LPA job | First run: max 2 jobs (Dry run)
                  </span>
                  <button className="link-btn" onClick={() => setNavTab('settings')}>
                    Edit
                  </button>
                </div>
              </div>
            </div>

            {/* Today Stats */}
            <div className="stats-grid">
              <div className="stat-box">
                <div className="stat-label">Found</div>
                <div className="stat-value">{engineStatus.stats.found}</div>
              </div>
              <div className="stat-box">
                <div className="stat-label">Matched</div>
                <div className="stat-value">{engineStatus.stats.matched}</div>
              </div>
              <div className="stat-box">
                <div className="stat-label">Applied</div>
                <div className="stat-value">{engineStatus.stats.applied}</div>
              </div>
              <div className="stat-box">
                <div className="stat-label">Skipped</div>
                <div className="stat-value">{engineStatus.stats.skipped}</div>
              </div>
              <div className="stat-box">
                <div className="stat-label">Needs you</div>
                <div className="stat-value" style={{ color: 'var(--warning)' }}>
                  {engineStatus.stats.needs_you}
                </div>
              </div>
            </div>

            {/* Test Run Result Panel */}
            <div className="panel">
              <div className="panel-header">
                <div>
                  <span className="panel-title">Test run</span>
                  <div className="panel-subtitle">
                    Live job pipeline tracking each listing with its active step as it happens
                  </div>
                </div>
                {engineStatus.status === 'Running' && (
                  <span
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      fontSize: '12px',
                      color: 'var(--primary)',
                      fontWeight: 600
                    }}
                  >
                    <span className="status-dot running" /> Live run active
                  </span>
                )}
              </div>

              {engineStatus.test_run_jobs && engineStatus.test_run_jobs.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {engineStatus.test_run_jobs.map((tj, idx) => (
                    <div
                      key={idx}
                      style={{
                        padding: '12px 14px',
                        background: 'var(--bg-surface-elevated)',
                        borderRadius: '6px',
                        borderLeft:
                          tj.status === 'dry_run_complete' || tj.status === 'applied'
                            ? '4px solid var(--success)'
                            : tj.status === 'review_pending' || tj.status === 'needs_you'
                            ? '4px solid var(--warning)'
                            : tj.status === 'skipped'
                            ? '4px solid var(--text-muted)'
                            : '4px solid var(--primary)',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '8px'
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div>
                          <strong style={{ fontSize: '14px', marginRight: '8px' }}>
                            {tj.company}
                          </strong>
                          <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                            — {tj.title}
                          </span>
                          {tj.salary && (
                            <span style={{ marginLeft: '8px', fontSize: '12px', color: 'var(--text-muted)' }}>
                              ({tj.salary})
                            </span>
                          )}
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          {tj.score !== null && tj.score !== undefined && (
                            <span
                              style={{
                                padding: '2px 8px',
                                borderRadius: '4px',
                                fontSize: '11px',
                                fontWeight: 600,
                                background: tj.score >= 70 ? 'rgba(34, 197, 94, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                                color: tj.score >= 70 ? 'var(--success)' : 'var(--danger)'
                              }}
                            >
                              Score: {tj.score}/100
                            </span>
                          )}

                          <span
                            style={{
                              padding: '2px 8px',
                              borderRadius: '4px',
                              fontSize: '11px',
                              fontWeight: 600,
                              background:
                                tj.status === 'dry_run_complete' || tj.status === 'applied'
                                  ? 'var(--success-soft)'
                                  : tj.status === 'review_pending' || tj.status === 'needs_you'
                                  ? 'var(--warning-soft)'
                                  : 'var(--bg-surface)',
                              color:
                                tj.status === 'dry_run_complete' || tj.status === 'applied'
                                  ? 'var(--success)'
                                  : tj.status === 'review_pending' || tj.status === 'needs_you'
                                  ? 'var(--warning)'
                                  : tj.status === 'skipped'
                                  ? 'var(--text-muted)'
                                  : 'var(--primary)'
                            }}
                          >
                            {tj.status.replace('_', ' ').toUpperCase()}
                          </span>
                        </div>
                      </div>

                      {/* Current Step */}
                      <div
                        style={{
                          fontSize: '12px',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                          padding: '6px 10px',
                          background: 'var(--bg-surface)',
                          borderRadius: '4px'
                        }}
                      >
                        <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Current step:</span>
                        <span style={{ color: 'var(--text-main)' }}>{tj.current_step || 'In queue'}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
                  No active test run. Click <strong>Start applying</strong> to launch evaluation; each job and its current step will appear here live.
                </div>
              )}
            </div>

            {/* Needs You Questions */}
            {engineStatus.needs_you_questions && engineStatus.needs_you_questions.length > 0 && (
              <div className="panel" style={{ borderLeft: '3px solid var(--warning)' }}>
                <div className="panel-header">
                  <span className="panel-title">Needs you (Interactive Blocker)</span>
                  <span className="countdown-badge">
                    Timeout in: {Math.floor(countdownSeconds / 60)}:
                    {(countdownSeconds % 60).toString().padStart(2, '0')}
                  </span>
                </div>
                {engineStatus.needs_you_questions.map((q) => (
                  <div key={q.id} className="needs-you-card">
                    <div className="needs-you-header">
                      <strong>{q.company} - {q.title}</strong>
                      <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{q.reason}</span>
                    </div>
                    <div style={{ marginBottom: '8px', fontSize: '13px' }}>
                      Question: <em>"{q.question}"</em>
                    </div>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <input
                        type="text"
                        placeholder="Type answer here..."
                        value={needsYouAnswer[q.id] || ''}
                        onChange={(e) => setNeedsYouAnswer({ ...needsYouAnswer, [q.id]: e.target.value })}
                        style={{ flex: 1 }}
                      />
                      <button
                        className="primary"
                        onClick={() => handleSubmitNeedsYouAnswer(q.id, q.question)}
                      >
                        Save & Continue
                      </button>
                      <button
                        className="secondary"
                        onClick={() => handleSkipApplication(q.id)}
                      >
                        Skip
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Waiting for approval (Review Mode) */}
            {engineStatus.waiting_for_approval && engineStatus.waiting_for_approval.length > 0 && (
              <div className="panel">
                <div className="panel-header">
                  <span className="panel-title">Waiting for approval (Review mode)</span>
                  <span className="panel-subtitle">
                    {engineStatus.waiting_for_approval.length} prepared application(s) awaiting review
                  </span>
                </div>
                {engineStatus.waiting_for_approval.map((app) => (
                  <div key={app.id} className="approval-card">
                    <div className="approval-grid">
                      <div>
                        {app.screenshot ? (
                          <img
                            src={`/data/${app.screenshot.split(/[\\/]/).pop()}`}
                            alt="Application form"
                            className="screenshot-preview"
                          />
                        ) : (
                          <div className="screenshot-preview" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                            Screenshot ready
                          </div>
                        )}
                        <div style={{ marginTop: '8px', fontSize: '12px', color: 'var(--text-muted)' }}>
                          Resume: {app.resume_version_used}
                        </div>
                      </div>

                      <div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                          <div>
                            <strong>{app.company}</strong> — {app.title} ({app.salary_raw})
                          </div>
                          <div style={{ display: 'flex', gap: '8px' }}>
                            <button
                              className="primary"
                              onClick={() => handleApproveApplication(app.id)}
                            >
                              Approve
                            </button>
                            <button
                              className="secondary"
                              onClick={() => handleSkipApplication(app.id)}
                            >
                              Skip
                            </button>
                          </div>
                        </div>

                        <div style={{ fontSize: '12px', marginBottom: '4px', fontWeight: 600 }}>
                          Filled answers and sources:
                        </div>
                        <div style={{ maxHeight: '110px', overflowY: 'auto', background: 'var(--bg-surface-elevated)', padding: '8px', borderRadius: '4px', fontSize: '12px' }}>
                          {Object.keys(app.answers_submitted).length > 0 ? (
                            Object.entries(app.answers_submitted).map(([k, v]) => (
                              <div key={k} style={{ marginBottom: '4px' }}>
                                <strong>{k}:</strong> {v.answer} <span style={{ color: 'var(--text-muted)' }}>({v.source})</span>
                              </div>
                            ))
                          ) : (
                            <span style={{ color: 'var(--text-muted)' }}>Form inputs mapped from verified profile.</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Live Activity Log Feed */}
            <div className="panel">
              <div className="panel-header">
                <span className="panel-title">Activity log</span>
                <span className="panel-subtitle">Live events</span>
              </div>
              <div className="activity-feed">
                {activityLogs.slice(0, 25).map((log, idx) => (
                  <div key={idx} className="activity-item">
                    <span className="activity-time">
                      {new Date(log.timestamp).toLocaleTimeString()}
                    </span>
                    <span>{log.message}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ======================= JOBS ======================= */}
        {navTab === 'jobs' && (
          <div>
            <div className="panel">
              <div className="panel-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <span className="panel-title">Jobs</span>
                  <div style={{ display: 'flex', gap: '6px' }}>
                    {['all', 'matched', 'needs_you', 'applied', 'skipped'].map((st) => (
                      <button
                        key={st}
                        className={`secondary ${jobsFilter === st ? 'primary' : ''}`}
                        onClick={() => setJobsFilter(st)}
                        style={{ fontSize: '12px', padding: '4px 8px' }}
                      >
                        {st.charAt(0).toUpperCase() + st.slice(1).replace('_', ' ')}
                      </button>
                    ))}
                  </div>
                </div>

                <button
                  className="secondary"
                  onClick={handlePreviewMatches}
                  disabled={isPreviewingMatches}
                >
                  {isPreviewingMatches ? 'Previewing...' : 'Preview matches'}
                </button>
              </div>

              {/* Preview Matches Sandbox Results if active */}
              {previewResults && (
                <div style={{ marginBottom: '16px', padding: '12px', background: 'var(--bg-surface-elevated)', borderRadius: '4px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                    <strong>Live listing preview (no applying, match evaluation only):</strong>
                    <button className="link-btn" onClick={() => setPreviewResults(null)}>
                      Close
                    </button>
                  </div>
                  <table>
                    <thead>
                      <tr>
                        <th>Company</th>
                        <th>Role</th>
                        <th>Salary</th>
                        <th>Score</th>
                        <th>Status</th>
                        <th>Reason / Best resume</th>
                      </tr>
                    </thead>
                    <tbody>
                      {previewResults.map((pr, idx) => (
                        <tr key={idx}>
                          <td>{pr.company}</td>
                          <td>{pr.role}</td>
                          <td>{pr.salary}</td>
                          <td>{pr.match_score ?? '-'}</td>
                          <td>{pr.action}</td>
                          <td>{pr.skip_reason || pr.recommended_resume}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Main Jobs Table */}
              <table>
                <thead>
                  <tr>
                    <th>Company</th>
                    <th>Role</th>
                    <th>Platform</th>
                    <th>Salary (Raw / Parsed)</th>
                    <th>Score</th>
                    <th>Status</th>
                    <th>Reason / Details</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredJobs.map((job) => (
                    <tr
                      key={job.id}
                      onClick={() => setSelectedJobDrawer(job)}
                      style={{ cursor: 'pointer' }}
                    >
                      <td><strong>{job.company}</strong></td>
                      <td>{job.title}</td>
                      <td>{job.platform}</td>
                      <td>
                        <div>{job.salary_raw || 'Not Disclosed'}</div>
                        {job.salary_raw && (
                          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                            Min: ₹5 LPA / ₹10k pm
                          </div>
                        )}
                      </td>
                      <td>{job.match_score ?? '-'}</td>
                      <td>
                        <span
                          style={{
                            padding: '2px 6px',
                            borderRadius: '4px',
                            fontSize: '11px',
                            background:
                              job.status === 'applied'
                                ? 'var(--success-soft)'
                                : job.status === 'needs_you'
                                ? 'var(--warning-soft)'
                                : 'var(--bg-surface-elevated)',
                            color:
                              job.status === 'applied'
                                ? 'var(--success)'
                                : job.status === 'needs_you'
                                ? 'var(--warning)'
                                : 'var(--text-secondary)'
                          }}
                        >
                          {job.status}
                        </span>
                      </td>
                      <td style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                        {formatPlainLanguageReason(job)}
                      </td>
                    </tr>
                  ))}
                  {filteredJobs.length === 0 && (
                    <tr>
                      <td colSpan="7" style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '24px' }}>
                        No job applications recorded yet. Click 'Start applying' on Home or 'Preview matches'.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Job Details Drawer */}
            {selectedJobDrawer && (
              <div className="drawer-backdrop" onClick={() => setSelectedJobDrawer(null)}>
                <div className="drawer-panel" onClick={(e) => e.stopPropagation()}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <h3 style={{ fontSize: '16px', fontWeight: 600 }}>{selectedJobDrawer.title}</h3>
                    <button className="secondary" onClick={() => setSelectedJobDrawer(null)}>
                      Close
                    </button>
                  </div>

                  <div>
                    <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>Company</div>
                    <div><strong>{selectedJobDrawer.company}</strong> ({selectedJobDrawer.platform})</div>
                  </div>

                  <div>
                    <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>Salary / Compensation</div>
                    <div>{selectedJobDrawer.salary_raw || 'Not Disclosed'}</div>
                  </div>

                  <div>
                    <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>Match Score</div>
                    <div style={{ fontSize: '18px', fontWeight: 700 }}>
                      {selectedJobDrawer.match_score ? `${selectedJobDrawer.match_score} / 100` : 'Not scored'}
                    </div>
                  </div>

                  {Array.isArray(selectedJobDrawer.match_reasons) && selectedJobDrawer.match_reasons.length > 0 && (
                    <div>
                      <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '4px' }}>
                        Matched Skills
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                        {selectedJobDrawer.match_reasons.map((sk, idx) => (
                          <span
                            key={idx}
                            style={{
                              padding: '2px 8px',
                              background: 'var(--accent-soft)',
                              color: 'var(--accent)',
                              borderRadius: '4px',
                              fontSize: '12px'
                            }}
                          >
                            {sk}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {Array.isArray(selectedJobDrawer.skill_gaps) && selectedJobDrawer.skill_gaps.length > 0 && (
                    <div>
                      <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '4px' }}>
                        Identified Gaps
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                        {selectedJobDrawer.skill_gaps.map((gap, idx) => (
                          <span
                            key={idx}
                            style={{
                              padding: '2px 8px',
                              background: 'var(--danger-soft)',
                              color: 'var(--danger)',
                              borderRadius: '4px',
                              fontSize: '12px'
                            }}
                          >
                            {gap}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {selectedJobDrawer.answers_submitted && Object.keys(selectedJobDrawer.answers_submitted).length > 0 && (
                    <div>
                      <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '4px' }}>
                        Submitted Answers
                      </div>
                      <div style={{ background: 'var(--bg-surface-elevated)', padding: '10px', borderRadius: '4px', fontSize: '12px' }}>
                        {Object.entries(selectedJobDrawer.answers_submitted).map(([k, v]) => (
                          <div key={k} style={{ marginBottom: '6px' }}>
                            <strong>{k}:</strong> {v.answer}
                            <div style={{ color: 'var(--text-muted)', fontSize: '11px' }}>Source: {v.source}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div>
                    <a
                      href={selectedJobDrawer.apply_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="link-btn"
                      style={{ fontSize: '13px' }}
                    >
                      Open job listing URL
                    </a>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ======================= PROFILE ======================= */}
        {navTab === 'profile' && (
          <div>
            {/* Missing Information Banner at the top */}
            {missingInfo.missing_count > 0 && (
              <div className="missing-banner">
                <div className="missing-title">Missing information ({missingInfo.missing_count})</div>
                <ul className="missing-list">
                  {missingInfo.items.map((it, idx) => (
                    <li key={idx}>
                      <a
                        onClick={() => {
                          if (it.category === 'Fixed Profile') setProfileSubtab('basics');
                          else if (it.category === 'Documents & Resumes') setNavTab('documents');
                          else setProfileSubtab('skills');
                        }}
                      >
                        {it.label}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Sub-tabs inside Profile */}
            <div className="subtabs-bar">
              {[
                { id: 'basics', label: 'Basics' },
                { id: 'app_details', label: 'Application details' },
                { id: 'education', label: 'Education' },
                { id: 'experience', label: 'Experience' },
                { id: 'projects', label: 'Projects' },
                { id: 'skills', label: 'Skills' },
                { id: 'links', label: 'Links' },
                { id: 'saved_answers', label: 'Saved answers' },
                {
                  id: 'review_data',
                  label: 'Review imported data',
                  badge: reviewItems.length
                }
              ].map((st) => (
                <button
                  key={st.id}
                  className={`subtab-btn ${profileSubtab === st.id ? 'active' : ''}`}
                  onClick={() => setProfileSubtab(st.id)}
                >
                  {st.label}
                  {st.badge > 0 && <span className="badge-count">{st.badge}</span>}
                </button>
              ))}
            </div>

            {/* Profile Subtab: Basics */}
            {profileSubtab === 'basics' && (
              <div className="panel">
                <div className="panel-header">
                  <span className="panel-title">Basic Information</span>
                  <button className="primary" onClick={handleSaveFixedProfile}>
                    Save basics
                  </button>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
                  <div>
                    <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Full Name</label>
                    <input
                      type="text"
                      value={fixedProfile.full_name || ''}
                      onChange={(e) => setFixedProfile({ ...fixedProfile, full_name: e.target.value })}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Email</label>
                    <input
                      type="email"
                      value={fixedProfile.email || ''}
                      onChange={(e) => setFixedProfile({ ...fixedProfile, email: e.target.value })}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Phone</label>
                    <input
                      type="text"
                      value={fixedProfile.phone || ''}
                      onChange={(e) => setFixedProfile({ ...fixedProfile, phone: e.target.value })}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>City / Location</label>
                    <input
                      type="text"
                      value={fixedProfile.location || ''}
                      onChange={(e) => setFixedProfile({ ...fixedProfile, location: e.target.value })}
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Profile Subtab: Application Details */}
            {profileSubtab === 'app_details' && (
              <div className="panel">
                <div className="panel-header">
                  <span className="panel-title">Application Details</span>
                  <button className="primary" onClick={handleSaveFixedProfile}>
                    Save details
                  </button>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
                  <div>
                    <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Current CTC</label>
                    <input
                      type="text"
                      value={fixedProfile.current_ctc || ''}
                      onChange={(e) => setFixedProfile({ ...fixedProfile, current_ctc: e.target.value })}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Expected CTC</label>
                    <input
                      type="text"
                      value={fixedProfile.expected_ctc || ''}
                      onChange={(e) => setFixedProfile({ ...fixedProfile, expected_ctc: e.target.value })}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Notice Period (days)</label>
                    <input
                      type="number"
                      value={fixedProfile.notice_period_days ?? 0}
                      onChange={(e) => setFixedProfile({ ...fixedProfile, notice_period_days: parseInt(e.target.value) || 0 })}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Total Experience (years)</label>
                    <input
                      type="number"
                      step="0.1"
                      value={fixedProfile.total_experience_years ?? 0.5}
                      onChange={(e) => setFixedProfile({ ...fixedProfile, total_experience_years: parseFloat(e.target.value) || 0 })}
                    />
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                      Answer forms with 0.5 years. Free-text fields explain that it is internship experience.
                    </div>
                  </div>
                  <div>
                    <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Employment Status</label>
                    <input
                      type="text"
                      value={fixedProfile.employment_status || ''}
                      onChange={(e) => setFixedProfile({ ...fixedProfile, employment_status: e.target.value })}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Availability</label>
                    <input
                      type="text"
                      value={fixedProfile.availability || ''}
                      onChange={(e) => setFixedProfile({ ...fixedProfile, availability: e.target.value })}
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Profile Subtab: Projects */}
            {profileSubtab === 'projects' && (
              <div className="panel">
                <div className="panel-header">
                  <span className="panel-title">Project Tiers & Portfolio</span>
                  <span className="panel-subtitle">
                    Evidence analyzed from test suites, Dockerfile, scripts, and dependencies
                  </span>
                </div>
                <table>
                  <thead>
                    <tr>
                      <th>Project / Repository</th>
                      <th>Tier</th>
                      <th>Use in applications</th>
                      <th>Evidence / Rubric</th>
                    </tr>
                  </thead>
                  <tbody>
                    {projectTiers.map((proj) => (
                      <tr key={proj.id}>
                        <td>
                          <strong>{proj.project_name}</strong>
                          {proj.parent_project && (
                            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                              Grouped under: {proj.parent_project}
                            </div>
                          )}
                        </td>
                        <td>
                          <select
                            value={proj.tier}
                            onChange={(e) => handleProjectTierChange(proj.id, e.target.value)}
                            style={{ width: '100px' }}
                          >
                            <option value="Tier A">Tier A</option>
                            <option value="Tier B">Tier B</option>
                            <option value="Tier C">Tier C</option>
                          </select>
                        </td>
                        <td>
                          <input
                            type="checkbox"
                            checked={proj.use_in_applications !== false}
                            onChange={() => handleProjectUseToggle(proj.id, proj.use_in_applications !== false)}
                          />
                        </td>
                        <td style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                          {proj.rubric_summary}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Profile Subtab: Skills */}
            {profileSubtab === 'skills' && (
              <div className="panel">
                <div className="panel-header">
                  <span className="panel-title">Skills Inventory</span>
                  <button className="secondary" onClick={() => setShowAddFact(true)}>
                    Add skill
                  </button>
                </div>
                {showAddFact && (
                  <div style={{ marginBottom: '16px', padding: '12px', background: 'var(--bg-surface-elevated)', borderRadius: '4px' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr 100px', gap: '8px' }}>
                      <input
                        type="text"
                        placeholder="Skill title (e.g. Python)"
                        value={newFactData.title}
                        onChange={(e) => setNewFactData({ ...newFactData, title: e.target.value })}
                      />
                      <input
                        type="text"
                        placeholder="Proficiency / experience description"
                        value={newFactData.content}
                        onChange={(e) => setNewFactData({ ...newFactData, content: e.target.value })}
                      />
                      <button className="primary" onClick={handleCreateFact}>
                        Save
                      </button>
                    </div>
                  </div>
                )}
                <table>
                  <thead>
                    <tr>
                      <th>Skill</th>
                      <th>Content</th>
                      <th>Status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {vaultFacts
                      .filter((f) => f.section === 'skill')
                      .map((f) => (
                        <tr key={f.id}>
                          <td>
                            {editingFactId === f.id ? (
                              <input
                                type="text"
                                value={editingFactData.title}
                                onChange={(e) => setEditingFactData({ ...editingFactData, title: e.target.value })}
                              />
                            ) : (
                              <strong>{f.title}</strong>
                            )}
                          </td>
                          <td>
                            {editingFactId === f.id ? (
                              <input
                                type="text"
                                value={editingFactData.content}
                                onChange={(e) => setEditingFactData({ ...editingFactData, content: e.target.value })}
                              />
                            ) : (
                              f.content
                            )}
                          </td>
                          <td>
                            <span style={{ fontSize: '11px', color: f.verified ? 'var(--success)' : 'var(--warning)' }}>
                              {f.verified ? 'Verified' : 'Unverified'}
                            </span>
                          </td>
                          <td>
                            {editingFactId === f.id ? (
                              <button className="primary" onClick={() => handleSaveFact(f.id)}>
                                Save
                              </button>
                            ) : (
                              <div style={{ display: 'flex', gap: '6px' }}>
                                <button
                                  className="secondary"
                                  onClick={() => {
                                    setEditingFactId(f.id);
                                    setEditingFactData({ title: f.title, content: f.content });
                                  }}
                                >
                                  Edit
                                </button>
                                <button className="danger" onClick={() => handleDeleteFact(f.id)}>
                                  Delete
                                </button>
                              </div>
                            )}
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Profile Subtab: Education & Experience */}
            {(profileSubtab === 'education' || profileSubtab === 'experience') && (
              <div className="panel">
                <div className="panel-header">
                  <span className="panel-title">{profileSubtab === 'education' ? 'Education' : 'Experience'}</span>
                  <button
                    className="secondary"
                    onClick={() => {
                      setNewFactData({ title: '', content: '', section: profileSubtab });
                      setShowAddFact(true);
                    }}
                  >
                    Add entry
                  </button>
                </div>
                <table>
                  <thead>
                    <tr>
                      <th>Title</th>
                      <th>Details</th>
                      <th>Verification</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {vaultFacts
                      .filter((f) => f.section === profileSubtab)
                      .map((f) => (
                        <tr key={f.id}>
                          <td><strong>{f.title}</strong></td>
                          <td>{f.content}</td>
                          <td>
                            <span style={{ fontSize: '11px', color: f.verified ? 'var(--success)' : 'var(--warning)' }}>
                              {f.verified ? 'Verified' : 'Unverified'}
                            </span>
                          </td>
                          <td>
                            <button className="danger" onClick={() => handleDeleteFact(f.id)}>
                              Delete
                            </button>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Profile Subtab: Links */}
            {profileSubtab === 'links' && (
              <div className="panel">
                <div className="panel-header">
                  <span className="panel-title">Links & Profiles</span>
                  <button className="primary" onClick={handleSaveFixedProfile}>
                    Save links
                  </button>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px' }}>
                  <div>
                    <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>LinkedIn</label>
                    <input
                      type="text"
                      value={fixedProfile.links?.linkedin || ''}
                      onChange={(e) =>
                        setFixedProfile({
                          ...fixedProfile,
                          links: { ...fixedProfile.links, linkedin: e.target.value }
                        })
                      }
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>GitHub</label>
                    <input
                      type="text"
                      value={fixedProfile.links?.github || ''}
                      onChange={(e) =>
                        setFixedProfile({
                          ...fixedProfile,
                          links: { ...fixedProfile.links, github: e.target.value }
                        })
                      }
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Portfolio Website</label>
                    <input
                      type="text"
                      value={fixedProfile.links?.portfolio || ''}
                      onChange={(e) =>
                        setFixedProfile({
                          ...fixedProfile,
                          links: { ...fixedProfile.links, portfolio: e.target.value }
                        })
                      }
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Profile Subtab: Saved Answers */}
            {profileSubtab === 'saved_answers' && (
              <div className="panel">
                <div className="panel-header">
                  <span className="panel-title">Saved Answers</span>
                  <span className="panel-subtitle">Every answer learned from interactive forms</span>
                </div>
                <table>
                  <thead>
                    <tr>
                      <th>Question</th>
                      <th>Saved Answer</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {savedAnswers.map((qa) => (
                      <tr key={qa.id}>
                        <td>{qa.raw_question}</td>
                        <td>{qa.answer}</td>
                        <td>
                          <button className="danger" onClick={() => handleDeleteSavedAnswer(qa.id)}>
                            Delete
                          </button>
                        </td>
                      </tr>
                    ))}
                    {savedAnswers.length === 0 && (
                      <tr>
                        <td colSpan="3" style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '20px' }}>
                          No saved answers recorded yet. Any answer given during a Needs You blocker is automatically saved here.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {/* Profile Subtab: Review Imported Data & Conflicts */}
            {profileSubtab === 'review_data' && (
              <div>
                <div className="panel">
                  <div className="panel-header">
                    <div>
                      <span className="panel-title">Pending Staged Items ({reviewItems.length})</span>
                      <div className="panel-subtitle">Audit items before they are indexed into verified facts</div>
                    </div>
                    {reviewItems.length > 0 && (
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button className="primary" onClick={handleBulkApproveReviewItems}>
                          Approve all
                        </button>
                        <button className="danger" onClick={handleBulkRejectReviewItems}>
                          Reject all
                        </button>
                      </div>
                    )}
                  </div>
                  <table>
                    <thead>
                      <tr>
                        <th>Title</th>
                        <th>Proposed Content</th>
                        <th>Source</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {reviewItems.map((item) => (
                        <tr key={item.id}>
                          <td><strong>{item.title}</strong></td>
                          <td>{item.proposed_content}</td>
                          <td style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{item.source}</td>
                          <td>
                            <div style={{ display: 'flex', gap: '6px' }}>
                              <button className="primary" onClick={() => handleDecideReviewItem(item.id, 'approve')}>
                                Approve
                              </button>
                              <button className="danger" onClick={() => handleDecideReviewItem(item.id, 'reject')}>
                                Reject
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                      {reviewItems.length === 0 && (
                        <tr>
                          <td colSpan="4" style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '20px' }}>
                            No pending staged items. All imported facts are verified.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                {/* Pre-resolved Conflicts */}
                <div className="panel">
                  <div className="panel-header">
                    <span className="panel-title">Resolved Conflicts & Discrepancies</span>
                    <span className="panel-subtitle">Pre-resolved historical discrepancies</span>
                  </div>
                  <table>
                    <thead>
                      <tr>
                        <th>Field</th>
                        <th>Resolved Decision</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {conflicts.map((c) => (
                        <tr key={c.id}>
                          <td><strong>{c.title}</strong></td>
                          <td>{c.chosen_value || 'Pending resolution'}</td>
                          <td>
                            <span style={{ fontSize: '11px', color: c.resolved ? 'var(--success)' : 'var(--warning)' }}>
                              {c.resolved ? 'Resolved' : 'Needs resolution'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ======================= DOCUMENTS ======================= */}
        {navTab === 'documents' && (
          <div>
            <div className="panel">
              <div className="panel-header">
                <span className="panel-title">Resumes</span>
                <span className="panel-subtitle">Role-tagged versioned resumes</span>
              </div>
              <table>
                <thead>
                  <tr>
                    <th>Role Tag</th>
                    <th>File Name</th>
                    <th>Version</th>
                    <th>Uploaded At</th>
                  </tr>
                </thead>
                <tbody>
                  {resumes.map((r) => (
                    <tr key={r.id}>
                      <td><strong>{r.role_tag}</strong></td>
                      <td>{r.file_name}</td>
                      <td>v{r.version}</td>
                      <td>{new Date(r.uploaded_at).toLocaleDateString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="panel">
              <div className="panel-header">
                <span className="panel-title">Optional Documents</span>
                <span className="panel-subtitle">Requested only when a specific job form needs them</span>
              </div>
              <table>
                <thead>
                  <tr>
                    <th>Type</th>
                    <th>Name</th>
                    <th>File Name</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.map((d) => (
                    <tr key={d.id}>
                      <td>{d.doc_type}</td>
                      <td>{d.name}</td>
                      <td>{d.file_name}</td>
                    </tr>
                  ))}
                  {documents.length === 0 && (
                    <tr>
                      <td colSpan="3" style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '20px' }}>
                        No optional documents uploaded. They will only be requested if a form requires them.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ======================= SETTINGS ======================= */}
        {navTab === 'settings' && (
          <div>
            <div className="panel">
              <div className="panel-header">
                <span className="panel-title">Job Search & Filter Preferences</span>
                <button className="primary" onClick={handleSavePreferences}>
                  Save settings
                </button>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
                <div>
                  <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Target Roles (comma separated)</label>
                  <input
                    type="text"
                    value={(preferences.target_roles || []).join(', ')}
                    onChange={(e) =>
                      setPreferences({
                        ...preferences,
                        target_roles: e.target.value.split(',').map((s) => s.trim())
                      })
                    }
                  />
                </div>
                <div>
                  <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Minimum Salary (Annual INR)</label>
                  <input
                    type="number"
                    value={preferences.min_salary || 500000}
                    onChange={(e) => setPreferences({ ...preferences, min_salary: parseFloat(e.target.value) || 500000 })}
                  />
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                    Job minimum: ₹5 LPA. Internship minimum: ₹10,000/month.
                  </div>
                </div>
                <div>
                  <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Locations</label>
                  <input
                    type="text"
                    value={(preferences.preferred_locations || []).join(', ')}
                    onChange={(e) =>
                      setPreferences({
                        ...preferences,
                        preferred_locations: e.target.value.split(',').map((s) => s.trim())
                      })
                    }
                  />
                </div>
                <div>
                  <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Max Required Experience (Years)</label>
                  <input
                    type="number"
                    step="0.5"
                    value={preferences.max_experience_years || 2.0}
                    onChange={(e) => setPreferences({ ...preferences, max_experience_years: parseFloat(e.target.value) || 2.0 })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Match Score Threshold</label>
                  <input
                    type="number"
                    value={preferences.default_match_threshold || 70}
                    onChange={(e) => setPreferences({ ...preferences, default_match_threshold: parseInt(e.target.value) || 70 })}
                  />
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', paddingTop: '20px' }}>
                  <input
                    type="checkbox"
                    checked={preferences.allow_undisclosed_salary !== false}
                    onChange={(e) => setPreferences({ ...preferences, allow_undisclosed_salary: e.target.checked })}
                  />
                  <label style={{ fontSize: '13px' }}>Allow listings with undisclosed salary</label>
                </div>
              </div>
            </div>

            {/* Platforms */}
            <div className="panel">
              <div className="panel-header">
                <div>
                  <span className="panel-title">Platforms & Sessions</span>
                  <div className="panel-subtitle">Manual login in dedicated persistent browser profile (JobPilot never stores passwords)</div>
                </div>
              </div>
              <div style={{ display: 'flex', gap: '16px' }}>
                {/* Internshala Card */}
                <div style={{ flex: 1, padding: '16px', background: 'var(--bg-surface-elevated)', borderRadius: '6px', border: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <strong style={{ fontSize: '15px' }}>Internshala</strong>
                    <span
                      style={{
                        padding: '3px 8px',
                        borderRadius: '12px',
                        fontSize: '11px',
                        fontWeight: 600,
                        background: platformStatus.internshala?.logged_in ? 'rgba(34, 197, 94, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                        color: platformStatus.internshala?.logged_in ? 'var(--success)' : 'var(--danger)',
                        border: platformStatus.internshala?.logged_in ? '1px solid rgba(34, 197, 94, 0.3)' : '1px solid rgba(239, 68, 68, 0.3)'
                      }}
                    >
                      {platformStatus.internshala?.logged_in ? '● Logged in' : '○ Not logged in'}
                    </span>
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '12px' }}>
                    {platformStatus.internshala?.details || 'Persistent session saved locally in data/browser_profile.'}
                  </div>
                  {loginActionStatus.internshala && (
                    <div style={{ fontSize: '12px', marginBottom: '10px', color: loginActionStatus.internshala.startsWith('Error') ? 'var(--danger)' : 'var(--primary)' }}>
                      {loginActionStatus.internshala}
                    </div>
                  )}
                  <button
                    className="secondary"
                    onClick={() => handleOpenLogin('internshala')}
                  >
                    {platformStatus.internshala?.logged_in ? 'Re-open Internshala session' : 'Open Internshala login'}
                  </button>
                </div>

                {/* Naukri Card */}
                <div style={{ flex: 1, padding: '16px', background: 'var(--bg-surface-elevated)', borderRadius: '6px', border: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <strong style={{ fontSize: '15px' }}>Naukri</strong>
                    <span
                      style={{
                        padding: '3px 8px',
                        borderRadius: '12px',
                        fontSize: '11px',
                        fontWeight: 600,
                        background: platformStatus.naukri?.logged_in ? 'rgba(34, 197, 94, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                        color: platformStatus.naukri?.logged_in ? 'var(--success)' : 'var(--danger)',
                        border: platformStatus.naukri?.logged_in ? '1px solid rgba(34, 197, 94, 0.3)' : '1px solid rgba(239, 68, 68, 0.3)'
                      }}
                    >
                      {platformStatus.naukri?.logged_in ? '● Logged in' : '○ Not logged in'}
                    </span>
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '12px' }}>
                    {platformStatus.naukri?.details || 'Login session saved locally.'}
                  </div>
                  {loginActionStatus.naukri && (
                    <div style={{ fontSize: '12px', marginBottom: '10px', color: loginActionStatus.naukri.startsWith('Error') ? 'var(--danger)' : 'var(--primary)' }}>
                      {loginActionStatus.naukri}
                    </div>
                  )}
                  <button
                    className="secondary"
                    onClick={() => handleOpenLogin('naukri')}
                  >
                    {platformStatus.naukri?.logged_in ? 'Re-open Naukri session' : 'Open Naukri login'}
                  </button>
                </div>
              </div>
            </div>

            {/* AI Models Compact Health Check */}
            <div className="panel">
              <div className="panel-header">
                <span className="panel-title">AI Models (Health Check)</span>
              </div>
              <div style={{ fontSize: '13px', display: 'flex', gap: '20px' }}>
                <div>Gemini: <span style={{ color: 'var(--success)' }}>Connected (gemini-2.5-flash)</span></div>
                <div>Groq: <span style={{ color: 'var(--success)' }}>Connected (llama-3.3-70b-versatile)</span></div>
                <div>Ollama: <span style={{ color: 'var(--success)' }}>Connected (qwen2.5:7b-instruct)</span></div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
