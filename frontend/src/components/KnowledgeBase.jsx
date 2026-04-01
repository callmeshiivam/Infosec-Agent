import { useState, useEffect, useRef, useMemo } from 'react';
import api from '../api/client';

const FILE_ICONS = {
  '.pdf': { icon: '📄', cls: 'pdf' }, '.docx': { icon: '📝', cls: 'docx' },
  '.xlsx': { icon: '📊', cls: 'xlsx' }, '.xls': { icon: '📊', cls: 'xlsx' },
  '.txt': { icon: '📃', cls: 'txt' }, '.md': { icon: '📃', cls: 'txt' }, '.csv': { icon: '📊', cls: 'xlsx' },
};

function formatBytes(b) { return b < 1024 ? b + ' B' : b < 1048576 ? (b / 1024).toFixed(1) + ' KB' : (b / 1048576).toFixed(1) + ' MB'; }
function formatDate(s) { return new Date(s).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }); }

export default function KnowledgeBase({ onRefreshStats, showToast }) {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [dragActive, setDragActive] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState('all');
  const fileInputRef = useRef(null);

  const fetchDocuments = async () => {
    try { setLoading(true); setDocuments(await api.listDocuments()); }
    catch (err) { showToast('Failed to load documents: ' + err.message, 'error'); }
    finally { setLoading(false); }
  };
  useEffect(() => { fetchDocuments(); }, []);

  const filteredDocs = useMemo(() => {
    let docs = [...documents];
    if (searchQuery.trim()) docs = docs.filter(d => d.filename.toLowerCase().includes(searchQuery.toLowerCase()));
    if (filterType !== 'all') docs = docs.filter(d => d.file_type === filterType);
    return docs.sort((a, b) => new Date(b.uploaded_at) - new Date(a.uploaded_at));
  }, [documents, searchQuery, filterType]);

  const handleUpload = async (files) => {
    if (!files?.length) return;
    setUploading(true);
    setUploadProgress(0);
    for (let i = 0; i < files.length; i++) {
      try {
        await api.uploadDocument(files[i], (pct) => {
          setUploadProgress(Math.round(((i * 100) + pct) / files.length));
        });
      } catch (err) { showToast(`Failed: ${files[i].name} — ${err.message}`, 'error'); }
    }
    setUploadProgress(100);
    await fetchDocuments(); onRefreshStats();
    setUploading(false);
    setUploadProgress(0);
    showToast(`Uploaded ${files.length} file(s)`, 'success');
  };

  const handleDelete = async (filename) => {
    if (!confirm(`Delete "${filename}"?`)) return;
    try { await api.deleteDocument(filename); await fetchDocuments(); onRefreshStats(); showToast('Deleted', 'success'); }
    catch (err) { showToast(err.message, 'error'); }
  };

  const getFileInfo = (f) => FILE_ICONS['.' + f.split('.').pop().toLowerCase()] || { icon: '📎', cls: 'txt' };

  return (
    <div className="page-container">
      <div className="page-header">
        <h2>Knowledge Base</h2>
        <p>Upload security policies, compliance documents, and past questionnaire responses.</p>
      </div>

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-body">
          <div className={`dropzone ${dragActive ? 'active' : ''}`}
            onDrop={(e) => { e.preventDefault(); setDragActive(false); handleUpload(Array.from(e.dataTransfer.files)); }}
            onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
            onDragLeave={() => setDragActive(false)}
            onClick={() => fileInputRef.current?.click()}>
            {uploading
              ? <><div className="upload-progress-bar"><div className="upload-progress-fill" style={{ width: `${uploadProgress}%` }}></div></div><div className="dropzone-text">Uploading... {uploadProgress}%</div><div className="dropzone-hint">Extracting text and creating embeddings</div></>
              : <><div className="dropzone-icon">📁</div><div className="dropzone-text">Drop files here or click to browse</div><div className="dropzone-hint">PDF, DOCX, XLSX, TXT, Images (JPG, PNG, WEBP), Video (MP4)</div></>}
            <input ref={fileInputRef} type="file" multiple accept=".pdf,.docx,.xlsx,.xls,.txt,.md,.csv,.png,.jpg,.jpeg,.webp,.heic,.heif,.mp4,.mov" style={{ display: 'none' }} onChange={(e) => handleUpload(Array.from(e.target.files))} />
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h3>{documents.length} Documents</h3>
          <div style={{ display: 'flex', gap: 6 }}>
            {documents.length > 0 && <button className="btn btn-danger btn-sm" onClick={async () => { if (!confirm('Delete ALL documents? This cannot be undone.')) return; try { await api.deleteAllDocuments(); await fetchDocuments(); onRefreshStats(); showToast('All deleted', 'success'); } catch (e) { showToast(e.message, 'error'); } }}>Delete All</button>}
            <button className="btn btn-secondary btn-sm" onClick={fetchDocuments} disabled={loading}>Refresh</button>
          </div>
        </div>

        {documents.length > 0 && (
          <div className="doc-toolbar">
            <div className="search-box">
              <span className="search-icon">🔍</span>
              <input className="search-input" placeholder="Search..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
              {searchQuery && <button className="search-clear" onClick={() => setSearchQuery('')}>✕</button>}
            </div>
            <select className="select filter-select" value={filterType} onChange={(e) => setFilterType(e.target.value)}>
              <option value="all">All</option>
              <option value=".pdf">PDF</option>
              <option value=".docx">DOCX</option>
              <option value=".xlsx">XLSX</option>
              <option value=".txt">TXT</option>
            </select>
          </div>
        )}

        <div className="card-body">
          {loading ? (
            <div className="empty-state"><div className="loading-spinner" style={{ margin: '0 auto' }}></div></div>
          ) : documents.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">📭</div>
              <h3>No documents yet</h3>
              <p>Upload your first document to get started.</p>
            </div>
          ) : filteredDocs.length === 0 ? (
            <div className="empty-state"><p>No matches. <button className="btn btn-secondary btn-sm" onClick={() => { setSearchQuery(''); setFilterType('all'); }}>Clear</button></p></div>
          ) : (
            <div className="doc-list">
              {filteredDocs.map((doc) => {
                const fi = getFileInfo(doc.filename);
                return (
                  <div key={doc.filename} className="doc-item">
                    <div className={`doc-icon ${fi.cls}`}>{fi.icon}</div>
                    <div className="doc-info">
                      <div className="doc-name">{doc.filename}</div>
                      <div className="doc-meta">{formatBytes(doc.size_bytes)} · {formatDate(doc.uploaded_at)}</div>
                    </div>
                    <button className="btn btn-danger btn-sm" onClick={() => handleDelete(doc.filename)}>Delete</button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
