import { useState, useEffect, useCallback, useRef } from 'react';
import './index.css';
import KnowledgeBase from './components/KnowledgeBase';
import ChatAssistant from './components/ChatAssistant';
import ExcelProcessor from './components/ExcelProcessor';
import api from './api/client';

const TABS = [
  { id: 'knowledge', label: 'Knowledge Base', icon: '📚' },
  { id: 'chat', label: 'Ask Questions', icon: '💬' },
  { id: 'excel', label: 'Excel Processor', icon: '📊' },
];

function formatTokens(n) {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
  return n;
}

function App() {
  const [activeTab, setActiveTab] = useState('knowledge');
  const [stats, setStats] = useState({ total_documents: 0, total_chunks: 0, status: 'loading' });
  const [health, setHealth] = useState(null);
  const [toast, setToast] = useState(null);
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'dark');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const toastTimeoutRef = useRef(null);

  useEffect(() => { document.documentElement.setAttribute('data-theme', theme); localStorage.setItem('theme', theme); }, [theme]);

  const refreshStats = useCallback(async () => {
    try { setStats(await api.getStats()); } catch { setStats(p => ({ ...p, status: 'offline' })); }
  }, []);
  const refreshHealth = useCallback(async () => {
    try { setHealth(await api.healthCheck()); } catch { setHealth(null); }
  }, []);

  useEffect(() => {
    refreshStats(); refreshHealth();
    const id = setInterval(() => { refreshStats(); refreshHealth(); }, 15000);
    return () => clearInterval(id);
  }, [refreshStats, refreshHealth]);

  const showToast = useCallback((message, type = 'info') => {
    if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
    setToast({ message, type, id: Date.now() });
    toastTimeoutRef.current = setTimeout(() => setToast(null), 4000);
  }, []);

  const switchTab = useCallback((tabId) => {
    if (tabId === activeTab) return;
    setActiveTab(tabId);
    setMobileMenuOpen(false);
  }, [activeTab]);

  useEffect(() => {
    const onResize = () => { if (window.innerWidth > 768) setMobileMenuOpen(false); };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  return (
    <div className="app-layout">
      {mobileMenuOpen && <div className="mobile-overlay" onClick={() => setMobileMenuOpen(false)} />}
      <button className="mobile-hamburger" onClick={() => setMobileMenuOpen(p => !p)} aria-label="Toggle menu">
        {mobileMenuOpen ? '✕' : '☰'}
      </button>

      <aside className={`sidebar ${mobileMenuOpen ? 'mobile-open' : ''}`}>
        <div className="sidebar-header">
          <div className="sidebar-logo">
            <div className="logo-icon">🛡️</div>
            <div>
              <h1>InfoSec Agent</h1>
              <span className="logo-subtitle">AI Questionnaire Assistant</span>
            </div>
          </div>
        </div>

        <nav className="sidebar-nav">
          {TABS.map(tab => (
            <div key={tab.id} className={`nav-item ${activeTab === tab.id ? 'active' : ''}`} onClick={() => switchTab(tab.id)}>
              <span className="nav-icon">{tab.icon}</span>
              <span className="nav-label">{tab.label}</span>
            </div>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-info-row">
            <span className="info-label">{stats.total_documents} docs · {stats.total_chunks} chunks</span>
          </div>
          {health && health.status === 'healthy' && (
            <div className="sidebar-info-row model-row">
              <span className="model-dot"></span>
              <span className="info-label">{(health.usage?.last_provider || health.provider)?.toUpperCase()} · {formatTokens(health.usage?.tokens_today || 0)} tokens</span>
            </div>
          )}
          {health?.status === 'healthy' && (
            <div className="sidebar-info-row">
              <span className="info-label">💰 ${(health.usage?.cost_usd || 0) < 0.01 ? (health.usage?.cost_usd || 0).toFixed(6) : (health.usage?.cost_usd || 0).toFixed(4)} spent</span>
            </div>
          )}
          <button className="theme-toggle-btn" onClick={() => setTheme(p => p === 'dark' ? 'light' : 'dark')} aria-label="Toggle theme">
            {theme === 'dark' ? '☀️ Light' : '🌙 Dark'}
          </button>
        </div>
      </aside>

      <main className="main-content">
        <div className="page-transition" key={activeTab}>
          {activeTab === 'knowledge' && <KnowledgeBase onRefreshStats={refreshStats} showToast={showToast} />}
          {activeTab === 'chat' && <ChatAssistant showToast={showToast} />}
          {activeTab === 'excel' && <ExcelProcessor showToast={showToast} onComplete={() => {}} />}
        </div>
      </main>

      {toast && (
        <div className={`toast ${toast.type}`} key={toast.id}>
          <span>{toast.message}</span>
          <button className="toast-close" onClick={() => setToast(null)}>✕</button>
        </div>
      )}
    </div>
  );
}

export default App;
