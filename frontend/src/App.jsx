import React, { useState, useEffect } from 'react';

const API_BASE = '/api/vault';
const DISC_BASE = '/api/discovery';

export default function App() {
  const [activeTab, setActiveTab] = useState('discovery');
  const [summary, setSummary] = useState(null);
  const [fixedProfile, setFixedProfile] = useState({});
  const [facts, setFacts] = useState([]);
  const [selectedSection, setSelectedSection] = useState('all');
  const [missingInfo, setMissingInfo] = useState(null);
  const [resumes, setResumes] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [reviewItems, setReviewItems] = useState([]);
  const [preferences, setPreferences] = useState({});
  const [statusMsg, setStatusMsg] = useState('');
  const [editingFact, setEditingFact] = useState(null);

  // Form states
  const [resumeRoleTag, setResumeRoleTag] = useState('Full Stack');
  const [resumeFile, setResumeFile] = useState(null);
  const [docType, setDocType] = useState('degree');
  const [docName, setDocName] = useState('');
  const [docFile, setDocFile] = useState(null);
  const [portfolioUrl, setPortfolioUrl] = useState('');
  const [pasteData, setPasteData] = useState({ section: 'experience', title: '', text: '' });

  // Phase 2 & 3 states
  const [jobs, setJobs] = useState([]);
  const [discoveryPlatform, setDiscoveryPlatform] = useState('internshala');
  const [jobTypeFilter, setJobTypeFilter] = useState('job');
  const [discoveryKeywords, setDiscoveryKeywords] = useState('python');
  const [careerUrlInput, setCareerUrlInput] = useState('');
  const [isDiscovering, setIsDiscovering] = useState(false);
  const [jobsFilter, setJobsFilter] = useState('all');

  // Conflicts and Project Tiers state
  const [conflicts, setConflicts] = useState([]);
  const [projectTiers, setProjectTiers] = useState([]);
  const [naukriProposal, setNaukriProposal] = useState(null);
  const [customConflictInputs, setCustomConflictInputs] = useState({});
  const [isIngestingFull, setIsIngestingFull] = useState(false);

  // LLM Health state
  const [llmHealth, setLlmHealth] = useState(null);
  const [isCheckingLlm, setIsCheckingLlm] = useState(false);

  // Live Listing Test Sandbox state
  const [isTestingLive, setIsTestingLive] = useState(false);
  const [liveTestResults, setLiveTestResults] = useState(null);

  // Blocker / Needs You real-time resolving state
  const [resolvingBlockerId, setResolvingBlockerId] = useState(null);
  const [blockerAnswerText, setBlockerAnswerText] = useState('');

  // Answer Engine Interactive State
  const [testQuestion, setTestQuestion] = useState('What is your experience with high throughput APIs and databases?');
  const [testJd, setTestJd] = useState('Looking for a Python Backend Developer with FastAPI experience.');
  const [generatedAnswer, setGeneratedAnswer] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [userFallbackAnswer, setUserFallbackAnswer] = useState('');

  const loadData = async () => {
    try {
      const [sumRes, fixRes, factRes, missRes, resRes, docRes, revRes, prefRes, jobsRes, confRes, tiersRes] = await Promise.all([
        fetch(`${API_BASE}/summary`).then(r => r.json()),
        fetch(`${API_BASE}/fixed-profile`).then(r => r.json()),
        fetch(`${API_BASE}/facts`).then(r => r.json()),
        fetch(`${API_BASE}/missing-info`).then(r => r.json()),
        fetch(`${API_BASE}/resumes`).then(r => r.json()),
        fetch(`${API_BASE}/documents`).then(r => r.json()),
        fetch(`${API_BASE}/import/review-items`).then(r => r.json()),
        fetch(`${API_BASE}/preferences`).then(r => r.json()),
        fetch(`${DISC_BASE}/jobs`).then(r => r.json()),
        fetch(`${API_BASE}/conflicts`).then(r => r.json()).catch(() => []),
        fetch(`${API_BASE}/project-tiers`).then(r => r.json()).catch(() => []),
      ]);

      setSummary(sumRes);
      setFixedProfile(fixRes);
      setFacts(factRes);
      setMissingInfo(missRes);
      setResumes(resRes);
      setDocuments(docRes);
      setReviewItems(revRes);
      setPreferences(prefRes);
      setJobs(jobsRes);
      setConflicts(confRes || []);
      setProjectTiers(tiersRes || []);
    } catch (err) {
      console.error('Failed to load vault data', err);
    }
  };

  const checkLlmHealth = async () => {
    setIsCheckingLlm(true);
    setStatusMsg('Checking LLM providers health...');
    try {
      const res = await fetch('/api/llm/health');
      const data = await res.json();
      setLlmHealth(data);
      setStatusMsg(data.all_healthy ? 'All LLM providers are healthy!' : 'Some LLM providers reported issues.');
    } catch (err) {
      setStatusMsg(`LLM health check failed: ${err.message}`);
    } finally {
      setIsCheckingLlm(false);
    }
  };

  useEffect(() => {
    loadData();
    checkLlmHealth();
  }, []);

  const handleTestLiveListing = async () => {
    setIsTestingLive(true);
    setLiveTestResults(null);
    setStatusMsg('Scraping real Internshala listings and running hard filters + matching...');
    try {
      const payload = {
        platform: 'internshala',
        keywords: discoveryKeywords.split(',').map(s => s.trim()).filter(Boolean),
        locations: ['Remote'],
        job_type: jobTypeFilter,
        limit: 5,
      };
      const res = await fetch(`${DISC_BASE}/test-live-listing`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      setLiveTestResults(data);
      setStatusMsg(data.message || 'Live listing test completed.');
    } catch (err) {
      setStatusMsg(`Live test error: ${err.message}`);
    } finally {
      setIsTestingLive(false);
    }
  };

  const handleOpenBrowserLogin = async (platform = 'internshala') => {
    setStatusMsg(`Launching persistent browser for ${platform} manual login...`);
    try {
      const res = await fetch(`/api/workflow/browser/open-login?platform=${platform}`, { method: 'POST' });
      const data = await res.json();
      setStatusMsg(data.message);
    } catch (err) {
      setStatusMsg(`Browser login launch failed: ${err.message}`);
    }
  };

  const handleRunFullIngestion = async () => {
    setIsIngestingFull(true);
    setStatusMsg('Ingesting inbox PDFs, portfolio site, LinkedIn export, and analyzing 18 GitHub repositories...');
    try {
      const res = await fetch(`${API_BASE}/full-ingestion/run`, { method: 'POST' });
      const data = await res.json();
      setStatusMsg(`Full ingestion completed: ${data.resumes_registered.length} resumes, ${data.conflicts_count} conflicts seeded, ${data.projects_analyzed} projects analyzed.`);
      loadData();
    } catch (err) {
      setStatusMsg(`Ingestion failed: ${err.message}`);
    } finally {
      setIsIngestingFull(false);
    }
  };

  const handleResolveConflict = async (conflictId, chosenVal, chosenSrc) => {
    try {
      const res = await fetch(`${API_BASE}/conflicts/${conflictId}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chosen_value: chosenVal, chosen_source: chosenSrc || 'User confirmed' })
      });
      const data = await res.json();
      setStatusMsg(`Conflict resolved: ${data.chosen_value}`);
      loadData();
    } catch (err) {
      setStatusMsg(`Failed to resolve conflict: ${err.message}`);
    }
  };

  const handleConfirmProjectTier = async (projectId, tierVal) => {
    try {
      const res = await fetch(`${API_BASE}/project-tiers/${projectId}/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tier: tierVal })
      });
      const data = await res.json();
      setStatusMsg(`Project tier updated to ${data.tier}`);
      loadData();
    } catch (err) {
      setStatusMsg(`Failed to update tier: ${err.message}`);
    }
  };

  const handleFetchNaukriProposal = async () => {
    setStatusMsg('Generating Naukri profile update proposal from verified facts only...');
    try {
      const res = await fetch('/api/workflow/naukri/profile-proposal');
      const data = await res.json();
      setNaukriProposal(data);
      setStatusMsg('Naukri profile update diff generated from verified vault facts.');
    } catch (err) {
      setStatusMsg(`Proposal generation failed: ${err.message}`);
    }
  };

  const handleResolveBlocker = async (appId, questionText) => {
    if (!blockerAnswerText.trim()) return;
    setStatusMsg(`Submitting answer for application ${appId}...`);
    try {
      const res = await fetch('/api/workflow/needs-you/resolve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          application_id: appId,
          question: questionText,
          answer: blockerAnswerText
        })
      });
      const data = await res.json();
      setStatusMsg(data.message);
      setResolvingBlockerId(null);
      setBlockerAnswerText('');
      loadData();
    } catch (err) {
      setStatusMsg(`Error resolving blocker: ${err.message}`);
    }
  };

  const handleRunDiscovery = async () => {
    setIsDiscovering(true);
    setStatusMsg('Running job discovery and hard filtering...');
    try {
      const payload = {
        platform: discoveryPlatform,
        career_url: careerUrlInput,
        job_type: jobTypeFilter,
        keywords: discoveryKeywords.split(',').map(s => s.trim()).filter(Boolean),
        limit: 10,
      };
      const res = await fetch(`${DISC_BASE}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      setStatusMsg(data.message);
      loadData();
    } catch (err) {
      setStatusMsg(`Discovery error: ${err.message}`);
    } finally {
      setIsDiscovering(false);
    }
  };

  const handleTestAnswerEngine = async (e) => {
    e.preventDefault();
    setIsGenerating(true);
    setGeneratedAnswer(null);
    try {
      const res = await fetch(`${DISC_BASE}/answer-engine/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: testQuestion, job_description: testJd }),
      });
      const data = await res.json();
      setGeneratedAnswer(data);
    } catch (err) {
      setStatusMsg(`Answer engine error: ${err.message}`);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSaveUserAnswer = async (e) => {
    e.preventDefault();
    if (!userFallbackAnswer) return;
    try {
      const res = await fetch(`${DISC_BASE}/answer-engine/save-user-answer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: testQuestion,
          answer: userFallbackAnswer,
        }),
      });
      const data = await res.json();
      setStatusMsg(data.message);
      setUserFallbackAnswer('');
      loadData();
    } catch (err) {
      setStatusMsg(`Failed to save answer: ${err.message}`);
    }
  };

  const handleImportMaster = async () => {
    setStatusMsg('Importing master_profile.json...');
    try {
      const res = await fetch(`${API_BASE}/import-master-profile`, { method: 'POST' });
      const data = await res.json();
      setStatusMsg(`Master profile imported: ${data.stats.facts_created} created, ${data.stats.facts_updated} updated.`);
      loadData();
    } catch (err) {
      setStatusMsg(`Import error: ${err.message}`);
    }
  };

  const handleSaveFixedProfile = async (e) => {
    e.preventDefault();
    try {
      await fetch(`${API_BASE}/fixed-profile`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(fixedProfile),
      });
      setStatusMsg('Fixed profile updated.');
      loadData();
    } catch (err) {
      setStatusMsg(`Failed to save: ${err.message}`);
    }
  };

  const handleUpdateFact = async (e) => {
    e.preventDefault();
    if (!editingFact) return;
    try {
      await fetch(`${API_BASE}/facts/${editingFact.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: editingFact.title,
          content: editingFact.content,
          section: editingFact.section,
        }),
      });
      setEditingFact(null);
      setStatusMsg(`Fact [${editingFact.id}] updated.`);
      loadData();
    } catch (err) {
      setStatusMsg(`Update failed: ${err.message}`);
    }
  };

  const handleDeleteFact = async (factId) => {
    if (!window.confirm(`Delete fact [${factId}]?`)) return;
    try {
      await fetch(`${API_BASE}/facts/${factId}`, { method: 'DELETE' });
      setStatusMsg(`Fact [${factId}] deleted.`);
      loadData();
    } catch (err) {
      setStatusMsg(`Delete failed: ${err.message}`);
    }
  };

  const handleResumeUpload = async (e) => {
    e.preventDefault();
    if (!resumeFile) return;
    const formData = new FormData();
    formData.append('role_tag', resumeRoleTag);
    formData.append('file', resumeFile);

    try {
      const res = await fetch(`${API_BASE}/resumes/upload`, {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      setStatusMsg(data.message);
      setResumeFile(null);
      loadData();
    } catch (err) {
      setStatusMsg(`Upload error: ${err.message}`);
    }
  };

  const handleDocUpload = async (e) => {
    e.preventDefault();
    if (!docFile || !docName) return;
    const formData = new FormData();
    formData.append('doc_type', docType);
    formData.append('name', docName);
    formData.append('file', docFile);

    try {
      const res = await fetch(`${API_BASE}/documents/upload`, {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      setStatusMsg(data.message);
      setDocFile(null);
      setDocName('');
      loadData();
    } catch (err) {
      setStatusMsg(`Document upload failed: ${err.message}`);
    }
  };

  const handleReviewDecision = async (itemId, action, editedTitle, editedContent) => {
    try {
      await fetch(`${API_BASE}/import/review-items/${itemId}/decide`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action,
          edited_title: editedTitle,
          edited_content: editedContent,
        }),
      });
      setStatusMsg(`Item review saved (${action}).`);
      loadData();
    } catch (err) {
      setStatusMsg(`Decision failed: ${err.message}`);
    }
  };

  const handleScrapePortfolio = async (e) => {
    e.preventDefault();
    if (!portfolioUrl) return;
    setStatusMsg(`Scraping ${portfolioUrl}...`);
    try {
      const res = await fetch(`${API_BASE}/import/scrape-portfolio`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: portfolioUrl }),
      });
      const data = await res.json();
      setStatusMsg(data.message);
      setPortfolioUrl('');
      setActiveTab('review');
      loadData();
    } catch (err) {
      setStatusMsg(`Scrape failed: ${err.message}`);
    }
  };

  const handlePasteImport = async (e) => {
    e.preventDefault();
    if (!pasteData.title || !pasteData.text) return;
    try {
      const res = await fetch(`${API_BASE}/import/paste-text`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source: 'pasted_text',
          section: pasteData.section,
          title: pasteData.title,
          text: pasteData.text,
        }),
      });
      const data = await res.json();
      setStatusMsg(data.message);
      setPasteData({ section: 'experience', title: '', text: '' });
      setActiveTab('review');
      loadData();
    } catch (err) {
      setStatusMsg(`Import error: ${err.message}`);
    }
  };

  const handleSavePreferences = async (e) => {
    e.preventDefault();
    try {
      await fetch(`${API_BASE}/preferences`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(preferences),
      });
      setStatusMsg('Job preferences updated.');
      loadData();
    } catch (err) {
      setStatusMsg(`Save preferences failed: ${err.message}`);
    }
  };

  const filteredFacts = selectedSection === 'all'
    ? facts
    : facts.filter(f => f.section === selectedSection);

  const sectionsList = ['all', 'personal', 'education', 'experience', 'project', 'skill', 'star_story', 'certification', 'standard_qa'];

  const filteredJobs = jobsFilter === 'all'
    ? jobs
    : jobs.filter(j => j.status === jobsFilter);

  return (
    <div style={{ display: 'flex', minHeight: '100vh', flexDirection: 'column' }}>
      {/* Top Header */}
      <header style={{
        backgroundColor: 'var(--bg-surface)',
        borderBottom: '1px solid var(--border-subtle)',
        padding: '12px 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <span style={{ fontWeight: 700, fontSize: '16px', letterSpacing: '0.5px' }}>JobPilot</span>
          <span style={{
            fontSize: '11px',
            backgroundColor: 'var(--bg-surface-elevated)',
            color: 'var(--text-muted)',
            padding: '2px 8px',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border-subtle)',
          }}>
            Phases 1-3 Active
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {statusMsg && (
            <span style={{ fontSize: '12px', color: 'var(--warning)', marginRight: '8px' }}>
              {statusMsg}
            </span>
          )}
          <button className="secondary" onClick={handleImportMaster}>
            Re-import Master Profile
          </button>
          <a
            href={`${API_BASE}/export/biodata-pdf`}
            download="JobPilot_Biodata.pdf"
            style={{ textDecoration: 'none' }}
          >
            <button className="primary">Export Biodata PDF</button>
          </a>
        </div>
      </header>

      {/* Main Container */}
      <div style={{ display: 'flex', flex: 1 }}>
        {/* Left Sidebar */}
        <nav style={{
          width: '240px',
          backgroundColor: 'var(--bg-surface)',
          borderRight: '1px solid var(--border-subtle)',
          padding: '20px 12px',
          display: 'flex',
          flexDirection: 'column',
          gap: '4px',
        }}>
          {[
            { id: 'discovery', label: 'Discovery & Matching', count: jobs.length },
            { id: 'conflicts', label: 'Conflicts Screen', count: conflicts.filter(c => !c.resolved).length, badge: conflicts.filter(c => !c.resolved).length > 0 ? `${conflicts.filter(c => !c.resolved).length} Pending` : null },
            { id: 'project_tiers', label: 'Project Tiers', count: projectTiers.length },
            { id: 'llm_health', label: 'LLM Health', badge: llmHealth?.all_healthy ? 'OK' : (llmHealth ? 'ALERT' : null) },
            { id: 'answer_engine', label: 'Answer Engine' },
            { id: 'overview', label: 'Vault Overview', count: summary?.facts_count },
            { id: 'fixed', label: 'Fixed Profile' },
            { id: 'facts', label: 'Authoritative Facts', count: facts.length },
            { id: 'resumes', label: 'Resume Library', count: resumes.length },
            { id: 'documents', label: 'Document Vault', count: documents.length },
            { id: 'importers', label: 'Data Importers' },
            { id: 'review', label: 'Staged Reviews', count: reviewItems.length },
            { id: 'preferences', label: 'Job Preferences' },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => { setActiveTab(tab.id); setStatusMsg(''); }}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                textAlign: 'left',
                backgroundColor: activeTab === tab.id ? 'var(--bg-surface-elevated)' : 'transparent',
                borderColor: activeTab === tab.id ? 'var(--border-strong)' : 'transparent',
                color: activeTab === tab.id ? 'var(--text-primary)' : 'var(--text-secondary)',
                padding: '8px 12px',
              }}
            >
              <span>{tab.label}</span>
              {tab.badge && (
                <span className="mono" style={{
                  fontSize: '10px',
                  fontWeight: 700,
                  padding: '2px 6px',
                  borderRadius: 'var(--radius-sm)',
                  backgroundColor: tab.badge === 'OK' ? 'var(--success-soft)' : 'var(--danger-soft)',
                  color: tab.badge === 'OK' ? 'var(--success)' : 'var(--danger)',
                }}>
                  {tab.badge}
                </span>
              )}
              {tab.count !== undefined && !tab.badge && (
                <span className="mono" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  {tab.count}
                </span>
              )}
            </button>
          ))}

          {/* Missing Info Box */}
          {missingInfo && missingInfo.missing_count > 0 && (
            <div style={{
              marginTop: 'auto',
              backgroundColor: 'var(--danger-soft)',
              border: '1px solid rgba(239, 68, 68, 0.2)',
              borderRadius: 'var(--radius-sm)',
              padding: '12px',
            }}>
              <div style={{ color: 'var(--danger)', fontWeight: 600, fontSize: '12px', marginBottom: '6px' }}>
                {missingInfo.missing_count} Missing Items
              </div>
              <ul style={{ paddingLeft: '16px', fontSize: '11px', color: 'var(--text-secondary)' }}>
                {missingInfo.items.slice(0, 3).map((it, idx) => (
                  <li key={idx} style={{ marginBottom: '4px' }}>{it.label}</li>
                ))}
              </ul>
            </div>
          )}
        </nav>

        {/* Content Area */}
        <main style={{ flex: 1, padding: '24px 32px', overflowY: 'auto' }}>
          {/* TAB: DISCOVERY & MATCHING (PHASE 2) */}
          {activeTab === 'discovery' && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
                <div>
                  <h2 style={{ fontSize: '18px', fontWeight: 600 }}>Job Discovery & Matching (Phase 2)</h2>
                  <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                    Hard filters run in deterministic code first (salary, location, blacklist). LLM match scores (0-100) run only on valid jobs.
                  </p>
                </div>

                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                  <select
                    value={discoveryPlatform}
                    onChange={e => setDiscoveryPlatform(e.target.value)}
                    style={{ width: '130px' }}
                  >
                    <option value="internshala">Internshala</option>
                    <option value="naukri">Naukri.com</option>
                    <option value="career_page">Career Page</option>
                  </select>

                  <select
                    value={jobTypeFilter}
                    onChange={e => setJobTypeFilter(e.target.value)}
                    style={{ width: '130px' }}
                  >
                    <option value="job">Jobs Only</option>
                    <option value="internship">Internships Only</option>
                  </select>

                  <input
                    type="text"
                    placeholder="Keywords (e.g. python, react)"
                    value={discoveryKeywords}
                    onChange={e => setDiscoveryKeywords(e.target.value)}
                    style={{ width: '160px' }}
                  />

                  {discoveryPlatform === 'career_page' && (
                    <input
                      type="url"
                      placeholder="https://company.com/careers"
                      value={careerUrlInput}
                      onChange={e => setCareerUrlInput(e.target.value)}
                      style={{ width: '200px' }}
                    />
                  )}

                  <button
                    className="secondary"
                    onClick={handleTestLiveListing}
                    disabled={isTestingLive}
                    title="Scrapes real live listings with hard filters and matching only (no applying)."
                    style={{ fontWeight: 600, border: '1px solid var(--accent-primary)', color: 'var(--accent-primary)' }}
                  >
                    {isTestingLive ? 'Scraping Live...' : 'Test with live listing'}
                  </button>

                  <button
                    className="secondary"
                    onClick={() => handleOpenBrowserLogin('internshala')}
                    title="Opens persistent browser window to log in to Internshala manually once."
                  >
                    Open Internshala login
                  </button>

                  <button
                    className="secondary"
                    onClick={() => handleOpenBrowserLogin('naukri')}
                    title="Opens persistent browser window to log in to Naukri manually once (including OTP). Password never stored."
                  >
                    Open Naukri login
                  </button>

                  <button
                    className="primary"
                    onClick={handleRunDiscovery}
                    disabled={isDiscovering}
                  >
                    {isDiscovering ? 'Discovering...' : 'Run Discovery'}
                  </button>
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '6px' }}>
                  Note: Click "Open Internshala login" or "Open Naukri login" to open a browser window and log in manually. You can close it once logged in.
                </div>
              </div>

              {/* Live Listing Test Sandbox Display */}
              {liveTestResults && (
                <div style={{
                  backgroundColor: 'var(--bg-surface-elevated)',
                  border: '1px solid var(--accent-primary)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '16px',
                  marginBottom: '20px'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                    <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--accent-primary)' }}>
                      Live Listing Test Sandbox (No Form Fill, Inspection Only)
                    </div>
                    <button
                      className="secondary"
                      onClick={() => setLiveTestResults(null)}
                      style={{ fontSize: '11px', padding: '2px 8px' }}
                    >
                      Close Sandbox
                    </button>
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '12px' }}>
                    {liveTestResults.message} (Threshold: {liveTestResults.threshold})
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {liveTestResults.results.map((r, i) => (
                      <div key={i} style={{
                        backgroundColor: 'var(--bg-surface)',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: 'var(--radius-sm)',
                        padding: '12px'
                      }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontWeight: 600, fontSize: '13px' }}>{r.title} at {r.company}</span>
                          <div style={{ display: 'flex', gap: '6px' }}>
                            <span style={{
                              fontSize: '11px',
                              padding: '2px 6px',
                              borderRadius: 'var(--radius-sm)',
                              backgroundColor: r.action === 'MATCHED' ? 'var(--success-soft)' : 'var(--danger-soft)',
                              color: r.action === 'MATCHED' ? 'var(--success)' : 'var(--danger)'
                            }}>
                              {r.action}
                            </span>
                            {r.match_score !== null && (
                              <span style={{ fontSize: '11px', padding: '2px 6px', backgroundColor: 'var(--bg-surface-elevated)' }}>
                                Score: {r.match_score}
                              </span>
                            )}
                          </div>
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                          Type: {r.job_type} | Location: {r.location} | Comp: {r.salary}
                        </div>
                        {r.skip_reason && (
                          <div style={{ fontSize: '11px', color: 'var(--danger)', marginTop: '4px' }}>
                            Skip Reason: {r.skip_reason}
                          </div>
                        )}
                        {r.analysis && (
                          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                            Analysis: {r.analysis} (Fit Resume: {r.recommended_resume})
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Status filter bar */}
              <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
                {['all', 'matched', 'skipped', 'needs_you', 'applied'].map(st => (
                  <button
                    key={st}
                    onClick={() => setJobsFilter(st)}
                    className={jobsFilter === st ? 'primary' : 'secondary'}
                    style={{ fontSize: '12px', textTransform: 'capitalize', padding: '4px 10px' }}
                  >
                    {st}
                  </button>
                ))}
              </div>

              {/* Jobs List */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {filteredJobs.length === 0 ? (
                  <div style={{
                    backgroundColor: 'var(--bg-surface)',
                    border: '1px solid var(--border-subtle)',
                    padding: '32px',
                    textAlign: 'center',
                    color: 'var(--text-muted)',
                    borderRadius: 'var(--radius-sm)'
                  }}>
                    No jobs recorded matching this filter. Click "Run Discovery" to fetch jobs.
                  </div>
                ) : (
                  filteredJobs.map(j => (
                    <div
                      key={j.id}
                      style={{
                        backgroundColor: 'var(--bg-surface)',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: 'var(--radius-sm)',
                        padding: '16px',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                        <div>
                          <span style={{
                            fontSize: '11px',
                            color: 'var(--text-muted)',
                            textTransform: 'uppercase',
                            marginRight: '8px',
                          }}>
                            [{j.platform}]
                          </span>
                          <span style={{ fontWeight: 600, fontSize: '14px' }}>{j.title}</span>
                          <span style={{ color: 'var(--text-secondary)', marginLeft: '8px' }}>at {j.company}</span>
                        </div>

                        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                          {j.match_score !== null && (
                            <span className="mono" style={{
                              fontSize: '12px',
                              fontWeight: 600,
                              backgroundColor: j.match_score >= 70 ? 'var(--success-soft)' : 'var(--warning-soft)',
                              color: j.match_score >= 70 ? 'var(--success)' : 'var(--warning)',
                              padding: '2px 8px',
                              borderRadius: 'var(--radius-sm)',
                            }}>
                              Score: {j.match_score}/100
                            </span>
                          )}

                          <span style={{
                            fontSize: '11px',
                            textTransform: 'uppercase',
                            padding: '2px 8px',
                            borderRadius: 'var(--radius-sm)',
                            backgroundColor: j.status === 'matched' ? 'var(--success-soft)' : (j.status === 'skipped' ? 'var(--bg-surface-elevated)' : 'var(--accent-soft)'),
                            color: j.status === 'matched' ? 'var(--success)' : (j.status === 'skipped' ? 'var(--text-muted)' : 'var(--accent-primary)'),
                            border: '1px solid var(--border-subtle)',
                          }}>
                            {j.status}
                          </span>
                        </div>
                      </div>

                      <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                        <span>Location: {j.location || 'N/A'}</span> &bull; <span>Compensation: {j.salary_raw || 'Undisclosed'}</span>
                      </div>

                      {j.skip_reason && (
                        <div style={{
                          fontSize: '11px',
                          color: 'var(--danger)',
                          backgroundColor: 'var(--danger-soft)',
                          padding: '6px 10px',
                          borderRadius: 'var(--radius-sm)',
                          marginBottom: '8px',
                        }}>
                          Skipped: {j.skip_reason}
                        </div>
                      )}

                      {j.match_reasons && (
                        <div style={{
                          fontSize: '12px',
                          color: 'var(--text-secondary)',
                          backgroundColor: 'var(--bg-surface-elevated)',
                          padding: '10px 12px',
                          borderRadius: 'var(--radius-sm)',
                          marginBottom: '8px',
                        }}>
                          {j.match_reasons.analysis && <div><b>Analysis:</b> {j.match_reasons.analysis}</div>}
                          {j.match_reasons.matched_skills?.length > 0 && (
                            <div style={{ marginTop: '4px' }}>
                              <b>Matched Skills:</b> {j.match_reasons.matched_skills.join(', ')}
                            </div>
                          )}
                          {j.match_reasons.gaps?.length > 0 && (
                            <div style={{ marginTop: '4px' }}>
                              <b>Identified Gaps:</b> {j.match_reasons.gaps.join(', ')}
                            </div>
                          )}
                        </div>
                      )}

                      {j.status === 'needs_you' && (
                        <div style={{
                          backgroundColor: 'var(--danger-soft)',
                          border: '1px solid rgba(239, 68, 68, 0.4)',
                          borderRadius: 'var(--radius-sm)',
                          padding: '12px',
                          marginTop: '8px',
                          marginBottom: '8px'
                        }}>
                          <div style={{ fontWeight: 600, color: 'var(--danger)', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <span>[BLOCKER / NEEDS YOU ALERT]</span>
                          </div>
                          <div style={{ fontSize: '12px', color: 'var(--text-primary)', marginTop: '4px' }}>
                            <b>Reason:</b> {j.needs_you_reason}
                          </div>
                          {j.needs_you_question && (
                            <div style={{ fontSize: '12px', color: 'var(--text-primary)', marginTop: '2px' }}>
                              <b>Question:</b> {j.needs_you_question}
                            </div>
                          )}
                          {j.needs_you_state && (
                            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                              Saved State: Page {j.needs_you_state.page_num || 1} &bull; {Object.keys(j.needs_you_state.filled_fields || {}).length} fields preserved
                            </div>
                          )}

                          {resolvingBlockerId === j.id ? (
                            <div style={{ marginTop: '10px', display: 'flex', gap: '8px' }}>
                              <input
                                type="text"
                                placeholder="Type your answer to save to vault and resume..."
                                value={blockerAnswerText}
                                onChange={e => setBlockerAnswerText(e.target.value)}
                                style={{ flex: 1, fontSize: '12px' }}
                              />
                              <button
                                className="primary"
                                onClick={() => handleResolveBlocker(j.id, j.needs_you_question || j.needs_you_reason)}
                                style={{ fontSize: '12px' }}
                              >
                                Submit & Resume Immediately
                              </button>
                              <button
                                className="secondary"
                                onClick={() => setResolvingBlockerId(null)}
                                style={{ fontSize: '12px' }}
                              >
                                Cancel
                              </button>
                            </div>
                          ) : (
                            <div style={{ marginTop: '8px' }}>
                              <button
                                className="primary"
                                onClick={() => { setResolvingBlockerId(j.id); setBlockerAnswerText(''); }}
                                style={{ fontSize: '11px', padding: '4px 10px' }}
                              >
                                Answer Now & Continue
                              </button>
                            </div>
                          )}
                        </div>
                      )}

                      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '8px' }}>
                        <a href={j.apply_url} target="_blank" rel="noreferrer" style={{ textDecoration: 'none' }}>
                          <button className="secondary" style={{ fontSize: '11px', padding: '4px 8px' }}>View Job URL</button>
                        </a>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          {/* TAB: CONFLICTS SCREEN */}
          {activeTab === 'conflicts' && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
                <div>
                  <h2 style={{ fontSize: '18px', fontWeight: 600 }}>Conflicts Screen</h2>
                  <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                    When data sources disagree, JobPilot never guesses. Review each conflicting fact across all versions, and select or type the authoritative value.
                  </p>
                </div>
                <button
                  className="secondary"
                  onClick={handleRunFullIngestion}
                  disabled={isIngestingFull}
                >
                  {isIngestingFull ? 'Ingesting Sources...' : 'Re-Run Data Ingestion'}
                </button>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {conflicts.length === 0 ? (
                  <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)', backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)' }}>
                    No conflicts detected.
                  </div>
                ) : (
                  conflicts.map(c => (
                    <div key={c.id} style={{
                      backgroundColor: 'var(--bg-surface)',
                      border: c.resolved ? '1px solid var(--border-subtle)' : '1px solid var(--warning)',
                      borderRadius: 'var(--radius-sm)',
                      padding: '20px',
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                        <div style={{ fontWeight: 600, fontSize: '14px' }}>
                          {c.title}
                        </div>
                        <span style={{
                          fontSize: '11px',
                          fontWeight: 700,
                          padding: '2px 8px',
                          borderRadius: 'var(--radius-sm)',
                          backgroundColor: c.resolved ? 'var(--success-soft)' : 'var(--warning-soft)',
                          color: c.resolved ? 'var(--success)' : 'var(--warning)'
                        }}>
                          {c.resolved ? 'RESOLVED' : 'UNRESOLVED'}
                        </span>
                      </div>

                      <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '12px' }}>
                        {c.description}
                      </div>

                      {/* Versions comparison */}
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '16px' }}>
                        {(c.versions || []).map((v, vIdx) => (
                          <div key={vIdx} style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            backgroundColor: 'var(--bg-surface-elevated)',
                            padding: '10px 14px',
                            borderRadius: 'var(--radius-sm)',
                            border: '1px solid var(--border-subtle)'
                          }}>
                            <div>
                              <div style={{ fontWeight: 600, fontSize: '13px' }}>{v.value}</div>
                              <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                                Source: {v.source} {v.notes ? `(${v.notes})` : ''}
                              </div>
                            </div>
                            {!c.resolved && (
                              <button
                                className="primary"
                                style={{ fontSize: '11px', padding: '4px 10px' }}
                                onClick={() => handleResolveConflict(c.id, v.value, v.source)}
                              >
                                Select This Value
                              </button>
                            )}
                          </div>
                        ))}
                      </div>

                      {c.resolved ? (
                        <div style={{
                          fontSize: '12px',
                          color: 'var(--success)',
                          backgroundColor: 'var(--success-soft)',
                          padding: '10px 14px',
                          borderRadius: 'var(--radius-sm)',
                        }}>
                          <b>Chosen Value:</b> {c.chosen_value} <br />
                          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Authority: {c.chosen_source}</span>
                        </div>
                      ) : (
                        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                          <input
                            type="text"
                            placeholder="Or type custom verified value..."
                            value={customConflictInputs[c.id] || ''}
                            onChange={e => setCustomConflictInputs({ ...customConflictInputs, [c.id]: e.target.value })}
                            style={{ flex: 1, fontSize: '12px' }}
                          />
                          <button
                            className="primary"
                            style={{ fontSize: '12px' }}
                            disabled={!customConflictInputs[c.id]}
                            onClick={() => {
                              handleResolveConflict(c.id, customConflictInputs[c.id], 'User typed manually');
                              setCustomConflictInputs({ ...customConflictInputs, [c.id]: '' });
                            }}
                          >
                            Save Custom Value
                          </button>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          {/* TAB: PROJECT TIERS */}
          {activeTab === 'project_tiers' && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
                <div>
                  <h2 style={{ fontSize: '18px', fontWeight: 600 }}>Project Tier Rubric & Selection</h2>
                  <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                    Each repository is analyzed by evidence (tests, Docker, CI, author status, and dependencies). Max 2-3 projects per application. Tier C is never volunteered in cover letters.
                  </p>
                </div>
                <button
                  className="secondary"
                  onClick={handleFetchNaukriProposal}
                >
                  Generate Naukri Profile Diff
                </button>
              </div>

              {naukriProposal && (
                <div style={{
                  backgroundColor: 'var(--bg-surface-elevated)',
                  border: '1px solid var(--accent-primary)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '16px',
                  marginBottom: '24px'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                    <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--accent-primary)' }}>
                      Proposed Naukri Profile Update (Generated ONLY From Verified Vault Facts)
                    </div>
                    <button className="secondary" style={{ fontSize: '11px', padding: '2px 8px' }} onClick={() => setNaukriProposal(null)}>
                      Close Diff
                    </button>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '12px' }}>
                    {Object.entries(naukriProposal.diff || {}).map(([k, val]) => (
                      <div key={k} style={{
                        backgroundColor: 'var(--bg-surface)',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: 'var(--radius-sm)',
                        padding: '12px'
                      }}>
                        <div style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '4px' }}>
                          {k.replace('_', ' ')}
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--danger)', marginBottom: '4px' }}>
                          <b>Current:</b> {Array.isArray(val.current) ? (val.current.join(', ') || 'None') : String(val.current)}
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--success)' }}>
                          <b>Proposed:</b> {Array.isArray(val.proposed) ? val.proposed.join(', ') : String(val.proposed)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {projectTiers.length === 0 ? (
                  <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)', backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)' }}>
                    No project tiers loaded yet. Run Data Ingestion to analyze GitHub repositories.
                  </div>
                ) : (
                  projectTiers.map(p => (
                    <div key={p.id} style={{
                      backgroundColor: 'var(--bg-surface)',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: 'var(--radius-sm)',
                      padding: '16px',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center'
                    }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <span style={{ fontWeight: 600, fontSize: '14px' }}>{p.project_name}</span>
                          <span style={{
                            fontSize: '11px',
                            fontWeight: 700,
                            padding: '2px 8px',
                            borderRadius: 'var(--radius-sm)',
                            backgroundColor: p.tier === 'Tier A' ? 'rgba(59, 130, 246, 0.2)' : (p.tier === 'Tier B' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(156, 163, 175, 0.2)'),
                            color: p.tier === 'Tier A' ? '#60a5fa' : (p.tier === 'Tier B' ? '#34d399' : '#9ca3af')
                          }}>
                            {p.tier}
                          </span>
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                          {p.rubric_summary}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                          Tech: {(p.tech_stack || []).join(', ')} &bull; <a href={p.repo_url} target="_blank" rel="noreferrer" style={{ color: 'var(--accent-primary)' }}>GitHub Repo</a>
                        </div>
                      </div>

                      <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                        <select
                          value={p.tier}
                          onChange={e => handleConfirmProjectTier(p.id, e.target.value)}
                          style={{ fontSize: '12px', padding: '4px 8px' }}
                        >
                          <option value="Tier A">Tier A (Lead)</option>
                          <option value="Tier B">Tier B (Domain-specific)</option>
                          <option value="Tier C">Tier C (Basic/Generic)</option>
                        </select>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          {/* TAB: LLM HEALTH PANEL */}
          {activeTab === 'llm_health' && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
                <div>
                  <h2 style={{ fontSize: '18px', fontWeight: 600 }}>LLM Provider Health & Diagnostics</h2>
                  <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                    Sends a tiny live test prompt to each provider (Gemini, Groq, Ollama) and shows operational status or exact error. Keys are masked.
                  </p>
                </div>
                <button
                  className="primary"
                  onClick={checkLlmHealth}
                  disabled={isCheckingLlm}
                >
                  {isCheckingLlm ? 'Testing Providers...' : 'Re-run Health Check'}
                </button>
              </div>

              {llmHealth ? (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
                  {/* Gemini Card */}
                  <div style={{
                    backgroundColor: 'var(--bg-surface)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '20px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '12px'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontWeight: 600, fontSize: '15px' }}>Google Gemini</span>
                      <span style={{
                        fontSize: '11px',
                        fontWeight: 700,
                        padding: '3px 8px',
                        borderRadius: 'var(--radius-sm)',
                        backgroundColor: llmHealth.providers?.gemini?.status === 'OK' ? 'var(--success-soft)' : 'var(--danger-soft)',
                        color: llmHealth.providers?.gemini?.status === 'OK' ? 'var(--success)' : 'var(--danger)',
                      }}>
                        {llmHealth.providers?.gemini?.status}
                      </span>
                    </div>

                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                      <div><b>Configured Model:</b> <code className="mono">{llmHealth.providers?.gemini?.model}</code></div>
                      <div style={{ marginTop: '4px' }}><b>API Key:</b> <code className="mono">{llmHealth.providers?.gemini?.masked_key}</code></div>
                    </div>

                    {llmHealth.providers?.gemini?.status === 'OK' ? (
                      <div style={{
                        fontSize: '11px',
                        color: 'var(--success)',
                        backgroundColor: 'var(--success-soft)',
                        padding: '8px 12px',
                        borderRadius: 'var(--radius-sm)'
                      }}>
                        Response: "{llmHealth.providers?.gemini?.response}"
                      </div>
                    ) : (
                      <div style={{
                        fontSize: '11px',
                        color: 'var(--danger)',
                        backgroundColor: 'var(--danger-soft)',
                        padding: '8px 12px',
                        borderRadius: 'var(--radius-sm)'
                      }}>
                        Error: {llmHealth.providers?.gemini?.error}
                      </div>
                    )}
                  </div>

                  {/* Groq Card */}
                  <div style={{
                    backgroundColor: 'var(--bg-surface)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '20px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '12px'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontWeight: 600, fontSize: '15px' }}>Groq Cloud</span>
                      <span style={{
                        fontSize: '11px',
                        fontWeight: 700,
                        padding: '3px 8px',
                        borderRadius: 'var(--radius-sm)',
                        backgroundColor: llmHealth.providers?.groq?.status === 'OK' ? 'var(--success-soft)' : 'var(--danger-soft)',
                        color: llmHealth.providers?.groq?.status === 'OK' ? 'var(--success)' : 'var(--danger)',
                      }}>
                        {llmHealth.providers?.groq?.status}
                      </span>
                    </div>

                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                      <div><b>Configured Model:</b> <code className="mono">{llmHealth.providers?.groq?.model}</code></div>
                      <div style={{ marginTop: '4px' }}><b>API Key:</b> <code className="mono">{llmHealth.providers?.groq?.masked_key}</code></div>
                    </div>

                    {llmHealth.providers?.groq?.status === 'OK' ? (
                      <div style={{
                        fontSize: '11px',
                        color: 'var(--success)',
                        backgroundColor: 'var(--success-soft)',
                        padding: '8px 12px',
                        borderRadius: 'var(--radius-sm)'
                      }}>
                        Response: "{llmHealth.providers?.groq?.response}"
                      </div>
                    ) : (
                      <div style={{
                        fontSize: '11px',
                        color: 'var(--danger)',
                        backgroundColor: 'var(--danger-soft)',
                        padding: '8px 12px',
                        borderRadius: 'var(--radius-sm)'
                      }}>
                        Error: {llmHealth.providers?.groq?.error}
                      </div>
                    )}
                  </div>

                  {/* Ollama Card */}
                  <div style={{
                    backgroundColor: 'var(--bg-surface)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '20px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '12px'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontWeight: 600, fontSize: '15px' }}>Ollama Local</span>
                      <span style={{
                        fontSize: '11px',
                        fontWeight: 700,
                        padding: '3px 8px',
                        borderRadius: 'var(--radius-sm)',
                        backgroundColor: llmHealth.providers?.ollama?.status === 'OK' ? 'var(--success-soft)' : 'var(--danger-soft)',
                        color: llmHealth.providers?.ollama?.status === 'OK' ? 'var(--success)' : 'var(--danger)',
                      }}>
                        {llmHealth.providers?.ollama?.status}
                      </span>
                    </div>

                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                      <div><b>Configured Model:</b> <code className="mono">{llmHealth.providers?.ollama?.model}</code></div>
                      <div style={{ marginTop: '4px' }}><b>Base URL:</b> <code className="mono">{llmHealth.providers?.ollama?.base_url}</code></div>
                    </div>

                    {llmHealth.providers?.ollama?.status === 'OK' ? (
                      <div style={{
                        fontSize: '11px',
                        color: 'var(--success)',
                        backgroundColor: 'var(--success-soft)',
                        padding: '8px 12px',
                        borderRadius: 'var(--radius-sm)'
                      }}>
                        Response: "{llmHealth.providers?.ollama?.response}"
                      </div>
                    ) : (
                      <div style={{
                        fontSize: '11px',
                        color: 'var(--danger)',
                        backgroundColor: 'var(--danger-soft)',
                        padding: '8px 12px',
                        borderRadius: 'var(--radius-sm)'
                      }}>
                        Error: {llmHealth.providers?.ollama?.error}
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)' }}>
                  Loading LLM health status...
                </div>
              )}
            </div>
          )}

          {/* TAB: GROUNDED ANSWER ENGINE (PHASE 3) */}
          {activeTab === 'answer_engine' && (
            <div>
              <div style={{ marginBottom: '16px' }}>
                <h2 style={{ fontSize: '18px', fontWeight: 600 }}>Grounded Answer Engine (Phase 3)</h2>
                <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  Strict anti-hallucination. Closed-book generation citing authoritative Fact IDs (`[FACT-*]`), verified by a second LLM pass and code allowlist check.
                </p>
              </div>

              {/* Interactive Q&A Form */}
              <form onSubmit={handleTestAnswerEngine} style={{
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border-subtle)',
                padding: '20px',
                borderRadius: 'var(--radius-sm)',
                marginBottom: '20px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
              }}>
                <div>
                  <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Target Job Description / Context</label>
                  <textarea
                    rows={2}
                    value={testJd}
                    onChange={e => setTestJd(e.target.value)}
                    placeholder="Paste job description or relevant snippet..."
                  />
                </div>
                <div>
                  <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Application Question</label>
                  <input
                    type="text"
                    value={testQuestion}
                    onChange={e => setTestQuestion(e.target.value)}
                    placeholder="e.g. Why should we hire you? or What is your notice period?"
                  />
                </div>
                <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <button type="submit" className="primary" disabled={isGenerating}>
                    {isGenerating ? 'Generating & Verifying Claims...' : 'Generate Grounded Answer'}
                  </button>
                </div>
              </form>

              {/* Generated Answer Display */}
              {generatedAnswer && (
                <div style={{
                  backgroundColor: 'var(--bg-surface)',
                  border: generatedAnswer.status === 'needs_you' ? '1px solid var(--warning)' : '1px solid var(--success)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '20px',
                  marginBottom: '20px',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                    <span style={{
                      fontWeight: 600,
                      fontSize: '13px',
                      color: generatedAnswer.status === 'needs_you' ? 'var(--warning)' : 'var(--success)'
                    }}>
                      {generatedAnswer.status === 'needs_you' ? 'Needs You Alert' : 'Strictly Grounded & Verified'}
                    </span>
                    <span className="mono" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                      Attempts: {generatedAnswer.attempts} &bull; Citations: {generatedAnswer.citations?.length || 0}
                    </span>
                  </div>

                  <pre style={{
                    fontFamily: 'var(--font-sans)',
                    fontSize: '13px',
                    color: 'var(--text-primary)',
                    whiteSpace: 'pre-wrap',
                    backgroundColor: 'var(--bg-surface-elevated)',
                    padding: '12px',
                    borderRadius: 'var(--radius-sm)',
                    marginBottom: '12px',
                  }}>
                    {generatedAnswer.answer}
                  </pre>

                  {generatedAnswer.citations?.length > 0 && (
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                      <b>Citations:</b> {generatedAnswer.citations.map(c => (
                        <span key={c} className="mono" style={{
                          backgroundColor: 'var(--accent-soft)',
                          color: 'var(--accent-primary)',
                          padding: '2px 6px',
                          borderRadius: 'var(--radius-sm)',
                          marginRight: '6px',
                          fontSize: '11px',
                        }}>
                          {c}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Fallback Input when Vault lacks information */}
                  {generatedAnswer.status === 'needs_you' && (
                    <div style={{
                      marginTop: '16px',
                      padding: '16px',
                      backgroundColor: 'var(--warning-soft)',
                      borderRadius: 'var(--radius-sm)',
                    }}>
                      <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--warning)', marginBottom: '8px' }}>
                        Provide Your Authoritative Answer (Saved to Vault to never be asked again):
                      </div>
                      <form onSubmit={handleSaveUserAnswer} style={{ display: 'flex', gap: '8px' }}>
                        <input
                          type="text"
                          value={userFallbackAnswer}
                          onChange={e => setUserFallbackAnswer(e.target.value)}
                          placeholder="Your answer..."
                        />
                        <button type="submit" className="primary" disabled={!userFallbackAnswer}>
                          Save to Vault
                        </button>
                      </form>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* TAB: OVERVIEW */}
          {activeTab === 'overview' && (
            <div>
              <h2 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '16px' }}>Vault Overview</h2>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '24px' }}>
                <div style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', padding: '16px', borderRadius: 'var(--radius-sm)' }}>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Indexed Facts</div>
                  <div className="mono" style={{ fontSize: '24px', fontWeight: 600, marginTop: '4px' }}>{summary?.facts_count || 0}</div>
                </div>
                <div style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', padding: '16px', borderRadius: 'var(--radius-sm)' }}>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Tagged Resumes</div>
                  <div className="mono" style={{ fontSize: '24px', fontWeight: 600, marginTop: '4px' }}>{summary?.resumes_count || 0}</div>
                </div>
                <div style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', padding: '16px', borderRadius: 'var(--radius-sm)' }}>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Document Proofs</div>
                  <div className="mono" style={{ fontSize: '24px', fontWeight: 600, marginTop: '4px' }}>{summary?.documents_count || 0}</div>
                </div>
                <div style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', padding: '16px', borderRadius: 'var(--radius-sm)' }}>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Application Readiness</div>
                  <div style={{
                    fontSize: '13px',
                    fontWeight: 600,
                    marginTop: '8px',
                    color: summary?.is_ready_for_application ? 'var(--success)' : 'var(--warning)',
                  }}>
                    {summary?.is_ready_for_application ? 'Ready to Apply' : `${summary?.missing_items_count} Action(s) Needed`}
                  </div>
                </div>
              </div>

              {/* Missing items detailed breakdown */}
              <div style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', padding: '20px' }}>
                <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '12px' }}>Checklist of Required Items for Applications</h3>
                {missingInfo?.items?.length === 0 ? (
                  <p style={{ color: 'var(--success)', fontSize: '13px' }}>All required fixed profile facts, sections, and proof documents are present in your vault.</p>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {missingInfo?.items?.map((item, idx) => (
                      <div key={idx} style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        padding: '10px 14px',
                        backgroundColor: 'var(--bg-surface-elevated)',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: 'var(--radius-sm)',
                      }}>
                        <div>
                          <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', marginRight: '8px' }}>[{item.category}]</span>
                          <span style={{ fontWeight: 600 }}>{item.label}</span>
                          <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>{item.description}</div>
                        </div>
                        <span style={{ fontSize: '11px', color: 'var(--danger)', alignSelf: 'center' }}>Required</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB: FIXED PROFILE */}
          {activeTab === 'fixed' && (
            <div>
              <div style={{ marginBottom: '16px' }}>
                <h2 style={{ fontSize: '18px', fontWeight: 600 }}>Fixed Profile</h2>
                <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  Authoritative applicant facts stored in SQLite. These are never generated or hallucinated by LLM.
                </p>
              </div>

              <form onSubmit={handleSaveFixedProfile} style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', padding: '24px', borderRadius: 'var(--radius-sm)', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div>
                  <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Full Name</label>
                  <input
                    type="text"
                    value={fixedProfile.full_name || ''}
                    onChange={e => setFixedProfile({ ...fixedProfile, full_name: e.target.value })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Date of Birth (YYYY-MM-DD)</label>
                  <input
                    type="text"
                    value={fixedProfile.date_of_birth || ''}
                    onChange={e => setFixedProfile({ ...fixedProfile, date_of_birth: e.target.value })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Email Address</label>
                  <input
                    type="email"
                    value={fixedProfile.email || ''}
                    onChange={e => setFixedProfile({ ...fixedProfile, email: e.target.value })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Phone Number</label>
                  <input
                    type="text"
                    value={fixedProfile.phone || ''}
                    onChange={e => setFixedProfile({ ...fixedProfile, phone: e.target.value })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Current Location</label>
                  <input
                    type="text"
                    value={fixedProfile.location || ''}
                    onChange={e => setFixedProfile({ ...fixedProfile, location: e.target.value })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Notice Period (Days)</label>
                  <input
                    type="number"
                    value={fixedProfile.notice_period_days || 0}
                    onChange={e => setFixedProfile({ ...fixedProfile, notice_period_days: parseInt(e.target.value, 10) })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Current CTC</label>
                  <input
                    type="text"
                    value={fixedProfile.current_ctc || ''}
                    onChange={e => setFixedProfile({ ...fixedProfile, current_ctc: e.target.value })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Expected CTC</label>
                  <input
                    type="text"
                    value={fixedProfile.expected_ctc || ''}
                    onChange={e => setFixedProfile({ ...fixedProfile, expected_ctc: e.target.value })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Total Experience (Years)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={fixedProfile.total_experience_years || 0}
                    onChange={e => setFixedProfile({ ...fixedProfile, total_experience_years: parseFloat(e.target.value) })}
                  />
                </div>

                <div style={{ gridColumn: 'span 2', display: 'flex', justifyContent: 'flex-end', marginTop: '12px' }}>
                  <button type="submit" className="primary">Save Fixed Profile</button>
                </div>
              </form>
            </div>
          )}

          {/* TAB: FACTS */}
          {activeTab === 'facts' && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <div>
                  <h2 style={{ fontSize: '18px', fontWeight: 600 }}>Authoritative Facts</h2>
                  <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                    Each item has a stable ID, SHA-256 hash, and vector embedding in ChromaDB.
                  </p>
                </div>

                {/* Section filter */}
                <select
                  value={selectedSection}
                  onChange={e => setSelectedSection(e.target.value)}
                  style={{ width: '180px' }}
                >
                  {sectionsList.map(s => (
                    <option key={s} value={s}>Section: {s}</option>
                  ))}
                </select>
              </div>

              {/* Edit modal / block */}
              {editingFact && (
                <div style={{
                  backgroundColor: 'var(--bg-surface)',
                  border: '1px solid var(--accent-primary)',
                  padding: '20px',
                  borderRadius: 'var(--radius-sm)',
                  marginBottom: '20px',
                }}>
                  <h3 style={{ fontSize: '14px', marginBottom: '12px' }}>Edit Fact: [{editingFact.id}]</h3>
                  <form onSubmit={handleUpdateFact} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <div>
                      <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Title</label>
                      <input
                        type="text"
                        value={editingFact.title}
                        onChange={e => setEditingFact({ ...editingFact, title: e.target.value })}
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Content</label>
                      <textarea
                        rows={6}
                        value={editingFact.content}
                        onChange={e => setEditingFact({ ...editingFact, content: e.target.value })}
                      />
                    </div>
                    <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                      <button type="button" className="secondary" onClick={() => setEditingFact(null)}>Cancel</button>
                      <button type="submit" className="primary">Save Changes</button>
                    </div>
                  </form>
                </div>
              )}

              {/* Facts list */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {filteredFacts.map(fact => (
                  <div
                    key={fact.id}
                    style={{
                      backgroundColor: 'var(--bg-surface)',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: 'var(--radius-sm)',
                      padding: '16px',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                      <div>
                        <span className="mono" style={{
                          fontSize: '11px',
                          color: 'var(--accent-primary)',
                          backgroundColor: 'var(--accent-soft)',
                          padding: '2px 6px',
                          borderRadius: 'var(--radius-sm)',
                          marginRight: '8px',
                        }}>
                          {fact.id}
                        </span>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', marginRight: '8px' }}>
                          [{fact.section}]
                        </span>
                        <span style={{ fontWeight: 600 }}>{fact.title}</span>
                      </div>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button className="secondary" onClick={() => setEditingFact(fact)} style={{ padding: '4px 8px', fontSize: '12px' }}>
                          Edit
                        </button>
                        <button className="danger" onClick={() => handleDeleteFact(fact.id)} style={{ padding: '4px 8px', fontSize: '12px' }}>
                          Delete
                        </button>
                      </div>
                    </div>
                    <pre style={{
                      fontFamily: 'var(--font-sans)',
                      fontSize: '12px',
                      color: 'var(--text-secondary)',
                      whiteSpace: 'pre-wrap',
                      backgroundColor: 'var(--bg-surface-elevated)',
                      padding: '10px 12px',
                      borderRadius: 'var(--radius-sm)',
                    }}>
                      {fact.content}
                    </pre>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB: RESUME LIBRARY */}
          {activeTab === 'resumes' && (
            <div>
              <div style={{ marginBottom: '16px' }}>
                <h2 style={{ fontSize: '18px', fontWeight: 600 }}>Resume Library</h2>
                <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  Upload role-tagged resumes. Uploading an existing role creates a new version while preserving prior versions.
                </p>
              </div>

              {/* Upload form */}
              <form onSubmit={handleResumeUpload} style={{
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border-subtle)',
                padding: '20px',
                borderRadius: 'var(--radius-sm)',
                marginBottom: '24px',
                display: 'flex',
                gap: '16px',
                alignItems: 'flex-end',
              }}>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Role Tag</label>
                  <input
                    type="text"
                    value={resumeRoleTag}
                    placeholder="e.g. Backend, Full Stack, Python"
                    onChange={e => setResumeRoleTag(e.target.value)}
                  />
                </div>
                <div style={{ flex: 1.5 }}>
                  <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Resume PDF</label>
                  <input
                    type="file"
                    accept=".pdf"
                    onChange={e => setResumeFile(e.target.files[0])}
                  />
                </div>
                <button type="submit" className="primary" disabled={!resumeFile}>
                  Upload Resume
                </button>
              </form>

              {/* Resumes table */}
              <div style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)', fontSize: '11px', textTransform: 'uppercase' }}>
                      <th style={{ padding: '12px 16px' }}>Role Tag</th>
                      <th style={{ padding: '12px 16px' }}>Version</th>
                      <th style={{ padding: '12px 16px' }}>Filename</th>
                      <th style={{ padding: '12px 16px' }}>Extracted Text</th>
                    </tr>
                  </thead>
                  <tbody>
                    {resumes.length === 0 ? (
                      <tr>
                        <td colSpan={4} style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)' }}>
                          No resumes uploaded yet.
                        </td>
                      </tr>
                    ) : (
                      resumes.map(r => (
                        <tr key={r.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                          <td style={{ padding: '12px 16px', fontWeight: 600 }}>{r.role_tag}</td>
                          <td className="mono" style={{ padding: '12px 16px' }}>v{r.version}</td>
                          <td className="mono" style={{ padding: '12px 16px', color: 'var(--text-secondary)' }}>{r.file_name}</td>
                          <td style={{ padding: '12px 16px', color: 'var(--text-muted)', fontSize: '11px' }}>
                            {r.parsed_text ? `${r.parsed_text.slice(0, 80)}...` : 'None'}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB: DOCUMENT VAULT */}
          {activeTab === 'documents' && (
            <div>
              <div style={{ marginBottom: '16px' }}>
                <h2 style={{ fontSize: '18px', fontWeight: 600 }}>Document Vault</h2>
                <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  Marksheets, certificates, and government ID proofs. Audited before every job application.
                </p>
              </div>

              {/* Upload form */}
              <form onSubmit={handleDocUpload} style={{
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border-subtle)',
                padding: '20px',
                borderRadius: 'var(--radius-sm)',
                marginBottom: '24px',
                display: 'grid',
                gridTemplateColumns: '1fr 1fr 1.5fr auto',
                gap: '16px',
                alignItems: 'flex-end',
              }}>
                <div>
                  <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Document Type</label>
                  <select value={docType} onChange={e => setDocType(e.target.value)}>
                    <option value="degree">Degree Certificate</option>
                    <option value="10th_marksheet">10th Marksheet</option>
                    <option value="12th_marksheet">12th Marksheet</option>
                    <option value="id_proof">Government ID Proof</option>
                    <option value="experience_letter">Experience Letter</option>
                    <option value="certificate">Certification Proof</option>
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Document Title / Name</label>
                  <input
                    type="text"
                    value={docName}
                    placeholder="e.g. BTech Degree Certificate"
                    onChange={e => setDocName(e.target.value)}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>File (PDF / Image)</label>
                  <input
                    type="file"
                    onChange={e => setDocFile(e.target.files[0])}
                  />
                </div>
                <button type="submit" className="primary" disabled={!docFile || !docName}>
                  Upload Proof
                </button>
              </form>

              {/* Documents table */}
              <div style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)', fontSize: '11px', textTransform: 'uppercase' }}>
                      <th style={{ padding: '12px 16px' }}>Type</th>
                      <th style={{ padding: '12px 16px' }}>Name</th>
                      <th style={{ padding: '12px 16px' }}>File Path</th>
                    </tr>
                  </thead>
                  <tbody>
                    {documents.length === 0 ? (
                      <tr>
                        <td colSpan={3} style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)' }}>
                          No documents uploaded yet.
                        </td>
                      </tr>
                    ) : (
                      documents.map(d => (
                        <tr key={d.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                          <td style={{ padding: '12px 16px' }}>
                            <span style={{
                              fontSize: '11px',
                              backgroundColor: 'var(--bg-surface-elevated)',
                              padding: '2px 6px',
                              borderRadius: 'var(--radius-sm)',
                              border: '1px solid var(--border-subtle)'
                            }}>
                              {d.doc_type}
                            </span>
                          </td>
                          <td style={{ padding: '12px 16px', fontWeight: 600 }}>{d.name}</td>
                          <td className="mono" style={{ padding: '12px 16px', color: 'var(--text-secondary)', fontSize: '12px' }}>
                            {d.file_name}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB: IMPORTERS */}
          {activeTab === 'importers' && (
            <div>
              <div style={{ marginBottom: '16px' }}>
                <h2 style={{ fontSize: '18px', fontWeight: 600 }}>Data Importers</h2>
                <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  All external imports are staged into a Review screen. Conflicts with existing vault facts are detected and flagged.
                </p>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                {/* Portfolio Scraper */}
                <div style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', padding: '20px' }}>
                  <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '8px' }}>Portfolio Website Scraper</h3>
                  <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
                    Scrape projects and experience from your personal site URL.
                  </p>
                  <form onSubmit={handleScrapePortfolio} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <input
                      type="url"
                      placeholder="https://yourportfolio.dev"
                      value={portfolioUrl}
                      onChange={e => setPortfolioUrl(e.target.value)}
                    />
                    <button type="submit" className="primary" disabled={!portfolioUrl}>
                      Scrape and Stage for Review
                    </button>
                  </form>
                </div>

                {/* Paste Text / LinkedIn text */}
                <div style={{ backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', padding: '20px' }}>
                  <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '8px' }}>Paste Profile or Job Text</h3>
                  <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
                    Paste LinkedIn text or portfolio snippet for staging and review.
                  </p>
                  <form onSubmit={handlePasteImport} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <select
                        value={pasteData.section}
                        onChange={e => setPasteData({ ...pasteData, section: e.target.value })}
                        style={{ width: '140px' }}
                      >
                        <option value="experience">Experience</option>
                        <option value="project">Project</option>
                        <option value="skill">Skill</option>
                        <option value="education">Education</option>
                      </select>
                      <input
                        type="text"
                        placeholder="Item Title"
                        value={pasteData.title}
                        onChange={e => setPasteData({ ...pasteData, title: e.target.value })}
                      />
                    </div>
                    <textarea
                      rows={4}
                      placeholder="Paste text snippet here..."
                      value={pasteData.text}
                      onChange={e => setPasteData({ ...pasteData, text: e.target.value })}
                    />
                    <button type="submit" className="primary" disabled={!pasteData.title || !pasteData.text}>
                      Stage for Review
                    </button>
                  </form>
                </div>
              </div>
            </div>
          )}

          {/* TAB: STAGED REVIEWS */}
          {activeTab === 'review' && (
            <div>
              <div style={{ marginBottom: '16px' }}>
                <h2 style={{ fontSize: '18px', fontWeight: 600 }}>Import Review Queue</h2>
                <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  Approve, edit, or reject imported items before they enter your authoritative vault.
                </p>
              </div>

              {reviewItems.length === 0 ? (
                <div style={{
                  backgroundColor: 'var(--bg-surface)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '32px',
                  textAlign: 'center',
                  color: 'var(--text-muted)'
                }}>
                  No items currently awaiting review.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  {reviewItems.map(item => (
                    <div
                      key={item.id}
                      style={{
                        backgroundColor: 'var(--bg-surface)',
                        border: item.conflict_detected ? '1px solid var(--warning)' : '1px solid var(--border-subtle)',
                        borderRadius: 'var(--radius-sm)',
                        padding: '20px',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                        <div>
                          <span style={{
                            fontSize: '11px',
                            color: 'var(--text-muted)',
                            textTransform: 'uppercase',
                            marginRight: '8px',
                          }}>
                            [{item.source}] &bull; {item.section}
                          </span>
                          <span style={{ fontWeight: 600 }}>{item.title}</span>
                        </div>
                        {item.conflict_detected && (
                          <span style={{
                            fontSize: '11px',
                            color: 'var(--warning)',
                            backgroundColor: 'var(--warning-soft)',
                            padding: '2px 8px',
                            borderRadius: 'var(--radius-sm)',
                          }}>
                            Conflict Flagged
                          </span>
                        )}
                      </div>

                      {item.conflict_details && (
                        <div style={{
                          fontSize: '12px',
                          color: 'var(--warning)',
                          backgroundColor: 'var(--warning-soft)',
                          padding: '8px 12px',
                          borderRadius: 'var(--radius-sm)',
                          marginBottom: '12px',
                        }}>
                          {item.conflict_details}
                        </div>
                      )}

                      <pre style={{
                        fontFamily: 'var(--font-sans)',
                        fontSize: '12px',
                        color: 'var(--text-secondary)',
                        whiteSpace: 'pre-wrap',
                        backgroundColor: 'var(--bg-surface-elevated)',
                        padding: '12px',
                        borderRadius: 'var(--radius-sm)',
                        marginBottom: '16px',
                      }}>
                        {item.proposed_content}
                      </pre>

                      <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                        <button
                          className="danger"
                          onClick={() => handleReviewDecision(item.id, 'reject')}
                        >
                          Reject
                        </button>
                        <button
                          className="primary"
                          onClick={() => handleReviewDecision(item.id, 'approve')}
                        >
                          Approve and Enter Vault
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB: JOB PREFERENCES */}
          {activeTab === 'preferences' && (
            <div>
              <div style={{ marginBottom: '16px' }}>
                <h2 style={{ fontSize: '18px', fontWeight: 600 }}>Job Preferences</h2>
                <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  Target roles, salary bounds, daily limits, and company blacklists used by Phase 2 Discovery and Matching.
                </p>
              </div>

              <form onSubmit={handleSavePreferences} style={{
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border-subtle)',
                padding: '24px',
                borderRadius: 'var(--radius-sm)',
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '16px',
              }}>
                <div>
                  <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Minimum Salary (INR / Annual)</label>
                  <input
                    type="number"
                    value={preferences.min_salary || ''}
                    onChange={e => setPreferences({ ...preferences, min_salary: parseFloat(e.target.value) })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Maximum Salary</label>
                  <input
                    type="number"
                    value={preferences.max_salary || ''}
                    onChange={e => setPreferences({ ...preferences, max_salary: parseFloat(e.target.value) })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Default Match Threshold (0 - 100)</label>
                  <input
                    type="number"
                    value={preferences.default_match_threshold || 70}
                    onChange={e => setPreferences({ ...preferences, default_match_threshold: parseInt(e.target.value, 10) })}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Preferred Locations (comma separated)</label>
                  <input
                    type="text"
                    value={(preferences.preferred_locations || []).join(', ')}
                    onChange={e => setPreferences({ ...preferences, preferred_locations: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })}
                  />
                </div>
                <div style={{ gridColumn: 'span 2' }}>
                  <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Target Roles (comma separated)</label>
                  <input
                    type="text"
                    value={(preferences.target_roles || []).join(', ')}
                    onChange={e => setPreferences({ ...preferences, target_roles: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })}
                  />
                </div>
                <div style={{ gridColumn: 'span 2' }}>
                  <label style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Blacklisted Companies (comma separated)</label>
                  <input
                    type="text"
                    value={(preferences.blacklisted_companies || []).join(', ')}
                    onChange={e => setPreferences({ ...preferences, blacklisted_companies: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })}
                  />
                </div>

                <div style={{ gridColumn: 'span 2', display: 'flex', justifyContent: 'flex-end', marginTop: '12px' }}>
                  <button type="submit" className="primary">Save Preferences</button>
                </div>
              </form>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
