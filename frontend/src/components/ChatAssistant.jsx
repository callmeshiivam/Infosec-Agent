import { useState, useRef, useEffect } from 'react';
import api from '../api/client';

function renderMarkdown(text) {
  if (!text) return text;
  const lines = text.split('\n');
  const elements = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.trim().startsWith('```')) {
      const code = []; i++;
      while (i < lines.length && !lines[i].trim().startsWith('```')) { code.push(lines[i]); i++; }
      i++;
      elements.push(<pre key={elements.length} className="md-code-block"><code>{code.join('\n')}</code></pre>);
      continue;
    }
    if (line.startsWith('### ')) elements.push(<h4 key={elements.length} className="md-h4">{line.slice(4)}</h4>);
    else if (line.startsWith('## ')) elements.push(<h3 key={elements.length} className="md-h3">{line.slice(3)}</h3>);
    else if (/^[\-\*]\s/.test(line.trim())) {
      const items = [line.trim().slice(2)];
      while (i + 1 < lines.length && /^[\-\*]\s/.test(lines[i + 1].trim())) { i++; items.push(lines[i].trim().slice(2)); }
      elements.push(<ul key={elements.length} className="md-ul">{items.map((it, j) => <li key={j}>{it}</li>)}</ul>);
    }
    else if (/^\d+\.\s/.test(line.trim())) {
      const items = [line.trim().replace(/^\d+\.\s/, '')];
      while (i + 1 < lines.length && /^\d+\.\s/.test(lines[i + 1].trim())) { i++; items.push(lines[i].trim().replace(/^\d+\.\s/, '')); }
      elements.push(<ol key={elements.length} className="md-ol">{items.map((it, j) => <li key={j}>{it}</li>)}</ol>);
    }
    else if (!line.trim()) elements.push(<br key={elements.length} />);
    else elements.push(<p key={elements.length} className="md-p">{line}</p>);
    i++;
  }
  return elements;
}

const HISTORY_KEY = 'infosec_chat_sessions';
const loadSessions = () => { try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]'); } catch { return []; } };
const saveSessions = (s) => localStorage.setItem(HISTORY_KEY, JSON.stringify(s.slice(0, 20)));

export default function ChatAssistant({ showToast }) {
  const [sessions, setSessions] = useState(loadSessions);
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [topK, setTopK] = useState(3);
  const endRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);
  useEffect(() => { inputRef.current?.focus(); }, []);

  useEffect(() => {
    if (!messages.length) return;
    const updated = [...sessions];
    const idx = updated.findIndex(s => s.id === sessionId);
    const session = { id: sessionId || Date.now(), title: messages[0]?.content?.slice(0, 50) || 'Chat', messages, updatedAt: new Date().toISOString() };
    if (idx >= 0) updated[idx] = session; else { updated.unshift(session); setSessionId(session.id); }
    setSessions(updated); saveSessions(updated);
  }, [messages]);

  const handleSend = async () => {
    const q = input.trim(); if (!q || loading) return;
    setMessages(p => [...p, { role: 'user', content: q }]); setInput(''); setLoading(true);
    try {
      const r = await api.chatQuery(q, [], topK);
      setMessages(p => [...p, { role: 'ai', content: r.answer, sources: r.sources, confidence: r.confidence }]);
    } catch (err) {
      showToast('Query failed: ' + err.message, 'error');
      setMessages(p => [...p, { role: 'ai', content: 'Error — check that the backend is running.', sources: [], confidence: 'error' }]);
    } finally { setLoading(false); inputRef.current?.focus(); }
  };

  return (
    <div className="page-container">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div><h2>Ask Questions</h2><p>Get AI-powered answers from your knowledge base.</p></div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button className="btn btn-secondary btn-sm" onClick={() => setShowHistory(p => !p)}>History</button>
          <button className="btn btn-secondary btn-sm" onClick={() => { setMessages([]); setSessionId(null); setShowHistory(false); }}>New</button>
        </div>
      </div>

      {showHistory && (
        <div className="card" style={{ marginBottom: 12 }}>
          <div className="card-body" style={{ maxHeight: 240, overflowY: 'auto', padding: 12 }}>
            {sessions.length === 0 ? <p style={{ color: 'var(--text-3)', fontSize: 13, textAlign: 'center', padding: 16 }}>No history yet.</p> :
              sessions.map(s => (
                <div key={s.id} className={`history-item ${s.id === sessionId ? 'active' : ''}`} onClick={() => { setMessages(s.messages); setSessionId(s.id); setShowHistory(false); }}>
                  <div className="history-title">{s.title}</div>
                  <div className="history-meta">{s.messages.length} msg</div>
                  <button className="history-delete" onClick={(e) => { e.stopPropagation(); const u = sessions.filter(x => x.id !== s.id); setSessions(u); saveSessions(u); if (sessionId === s.id) { setMessages([]); setSessionId(null); } }}>✕</button>
                </div>
              ))}
          </div>
        </div>
      )}

      <div className="card" style={{ height: showHistory ? 'calc(100vh - 400px)' : 'calc(100vh - 160px)', display: 'flex', flexDirection: 'column' }}>
        <div className="card-body" style={{ flex: 1, overflowY: 'auto', padding: 20 }}>
          {messages.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">💬</div>
              <h3>Ask anything about your InfoSec docs</h3>
              <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 6, alignItems: 'center' }}>
                {['What is our encryption policy?', 'Do we have a DR plan?', 'How is access control handled?'].map(q => (
                  <button key={q} className="btn btn-secondary btn-sm suggested-q" onClick={() => { setInput(q); inputRef.current?.focus(); }}>💡 {q}</button>
                ))}
              </div>
            </div>
          ) : (
            <div className="chat-messages">
              {messages.map((msg, i) => (
                <div key={i} className={`chat-message ${msg.role}`}>
                  <div className={`chat-avatar ${msg.role}`}>{msg.role === 'user' ? '👤' : '🤖'}</div>
                  <div className="chat-bubble">
                    <div className="bubble-content">{msg.role === 'ai' ? renderMarkdown(msg.content) : msg.content}</div>
                    {msg.role === 'ai' && msg.confidence && msg.confidence !== 'error' && (
                      <div style={{ marginTop: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span className={`confidence-badge ${msg.confidence}`}>{msg.confidence}</span>
                        <button className="btn btn-secondary btn-sm" onClick={() => { navigator.clipboard.writeText(msg.content); showToast('Copied', 'success'); }} style={{ marginLeft: 'auto', fontSize: 11 }}>Copy</button>
                      </div>
                    )}
                    {msg.sources?.length > 0 && (
                      <div className="chat-sources">
                        <div className="chat-sources-title">Sources</div>
                        {msg.sources.map((s, j) => <a key={j} className="chat-source-tag" href={api.getDocumentDownloadUrl(s.filename)} download title="Download source document">📎 {s.filename}</a>)}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {loading && <div className="chat-message ai"><div className="chat-avatar ai">🤖</div><div className="chat-bubble"><div className="bubble-content"><div className="loading-dots"><span></span><span></span><span></span></div></div></div></div>}
              <div ref={endRef} />
            </div>
          )}
        </div>
        <div style={{ padding: '12px 20px', borderTop: '1px solid var(--border)' }}>
          <div className="chat-input-wrapper">
            <select className="select topk-select" value={topK} onChange={e => setTopK(Number(e.target.value))} title="Number of source chunks to reference">
              {[1,3,5,10].map(n => <option key={n} value={n}>{n} sources</option>)}
            </select>
            <input ref={inputRef} className="input" placeholder="Ask a question..." value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }} disabled={loading} />
            <button className="btn btn-primary" onClick={handleSend} disabled={!input.trim() || loading}>
              {loading ? <span className="loading-spinner" style={{ width: 14, height: 14 }}></span> : 'Ask'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
