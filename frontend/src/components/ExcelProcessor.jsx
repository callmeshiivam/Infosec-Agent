import { useState, useRef } from 'react';
import api from '../api/client';

export default function ExcelProcessor({ showToast, onComplete }) {
  const [step, setStep] = useState(1);
  const [excelData, setExcelData] = useState(null);
  const [config, setConfig] = useState({ questionColumn: '', answerColumn: '', startRow: 2, confidenceColumn: '', sourceColumn: '' });
  const [results, setResults] = useState(null);
  const [processing, setProcessing] = useState(false);
  const fileInputRef = useRef(null);

  const handleUpload = async (file) => {
    if (!file) return;
    try {
      const data = await api.uploadExcel(file);
      setExcelData(data);
      if (data.columns.length >= 2) setConfig(p => ({ ...p, questionColumn: data.columns[0].letter, answerColumn: data.columns[1].letter }));
      setStep(2);
    } catch (err) { showToast('Upload failed: ' + err.message, 'error'); }
  };

  const handleProcess = async () => {
    if (!config.questionColumn || !config.answerColumn || config.questionColumn === config.answerColumn) {
      showToast('Select different question and answer columns.', 'error'); return;
    }
    setStep(3); setProcessing(true);
    try {
      const r = await api.processExcel({ filename: excelData.filename, questionColumn: config.questionColumn, answerColumn: config.answerColumn, startRow: config.startRow, confidenceColumn: config.confidenceColumn || undefined, sourceColumn: config.sourceColumn || undefined });
      setResults(r); setStep(4); showToast(`${r.answered}/${r.total_questions} answered`, 'success'); if (onComplete) onComplete();
    } catch (err) { showToast('Failed: ' + err.message, 'error'); setStep(2); }
    finally { setProcessing(false); }
  };

  const reset = () => { setStep(1); setExcelData(null); setConfig({ questionColumn: '', answerColumn: '', startRow: 2, confidenceColumn: '', sourceColumn: '' }); setResults(null); };
  const steps = ['Upload', 'Configure', 'Processing', 'Results'];

  return (
    <div className="page-container">
      <div className="page-header">
        <h2>Excel Processor</h2>
        <p>Upload a questionnaire, map columns, and let AI fill in answers.</p>
      </div>

      <div className="excel-steps">
        {steps.map((label, i) => (
          <div key={label} className={`step ${step > i + 1 ? 'completed' : ''} ${step === i + 1 ? 'active' : ''}`}>
            <span className="step-number">{step > i + 1 ? '✓' : i + 1}</span> {label}
          </div>
        ))}
      </div>

      {step === 1 && (
        <div className="card"><div className="card-body">
          <div className="dropzone" onClick={() => fileInputRef.current?.click()}>
            <div className="dropzone-icon">📊</div>
            <div className="dropzone-text">Click to upload an Excel file</div>
            <div className="dropzone-hint">.xlsx or .xls</div>
            <input ref={fileInputRef} type="file" accept=".xlsx,.xls" style={{ display: 'none' }} onChange={e => handleUpload(e.target.files[0])} />
          </div>
        </div></div>
      )}

      {step === 2 && excelData && (<>
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-header"><h3>Column Mapping</h3><button className="btn btn-secondary btn-sm" onClick={reset}>Start Over</button></div>
          <div className="card-body">
            <div className="column-mapping">
              {[{ label: 'Question Column', key: 'questionColumn', required: true }, { label: 'Answer Column', key: 'answerColumn', required: true }, { label: 'Confidence Column', key: 'confidenceColumn' }, { label: 'Source Column', key: 'sourceColumn' }].map(f => (
                <div className="input-group" key={f.key}>
                  <label>{f.label}{f.required ? ' *' : ''}</label>
                  <select className="select" value={config[f.key]} onChange={e => setConfig(p => ({ ...p, [f.key]: e.target.value }))}>
                    <option value="">{f.required ? 'Select...' : 'None'}</option>
                    {excelData.columns.map(c => <option key={c.letter} value={c.letter}>{c.letter} — {c.name}</option>)}
                  </select>
                </div>
              ))}
            </div>
            <div className="input-group" style={{ maxWidth: 160 }}>
              <label>Start Row</label>
              <input className="input" type="number" min={1} value={config.startRow} onChange={e => setConfig(p => ({ ...p, startRow: parseInt(e.target.value) || 2 }))} />
            </div>
          </div>
        </div>

        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-header"><h3>Preview</h3></div>
          <div style={{ overflowX: 'auto' }}>
            <table className="excel-preview" style={{ margin: 0 }}>
              <thead><tr>{excelData.columns.map(c => <th key={c.letter} className={c.letter === config.questionColumn ? 'col-question' : c.letter === config.answerColumn ? 'col-answer' : ''}>{c.letter}: {c.name}</th>)}</tr></thead>
              <tbody>{excelData.preview.slice(1).map((row, i) => <tr key={i}>{excelData.columns.map(c => <td key={c.letter} className={c.letter === config.questionColumn ? 'col-question' : c.letter === config.answerColumn ? 'col-answer' : ''}>{row[c.letter] || '—'}</td>)}</tr>)}</tbody>
            </table>
          </div>
        </div>

        <div style={{ textAlign: 'right' }}>
          <button className="btn btn-primary" onClick={handleProcess} disabled={!config.questionColumn || !config.answerColumn}>Process Questionnaire</button>
        </div>
      </>)}

      {step === 3 && (
        <div className="card"><div className="card-body" style={{ textAlign: 'center', padding: 60 }}>
          <div className="processing-spinner" style={{ margin: '0 auto 16px' }}></div>
          <div style={{ fontSize: 15, fontWeight: 600 }}>Processing...</div>
          <div style={{ fontSize: 13, color: 'var(--text-3)', marginTop: 4 }}>Running each question through the AI</div>
        </div></div>
      )}

      {step === 4 && results && (<>
        <div className="results-summary">
          {[{ n: results.total_questions, l: 'Questions' }, { n: results.answered, l: 'Answered' }, { n: results.total_questions > 0 ? Math.round((results.answered / results.total_questions) * 100) + '%' : '0%', l: 'Success' }].map(s => (
            <div className="result-stat" key={s.l}><div className="stat-number">{s.n}</div><div className="stat-label">{s.l}</div></div>
          ))}
        </div>
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-header"><h3>Download</h3>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-secondary btn-sm" onClick={reset}>Process Another</button>
              <a href={api.getExcelDownloadUrl(results.output_filename)} className="btn btn-primary btn-sm" download>Download Excel</a>
            </div>
          </div>
        </div>
        <div className="card"><div className="card-header"><h3>Answers</h3></div><div className="card-body">
          {results.results.map((r, i) => (
            <div key={i} className="result-row">
              <div className="result-question">Row {r.row}: {r.question}</div>
              <div className="result-answer" style={{ display: 'flex', gap: 8 }}>
                <span style={{ flex: 1 }}>{r.answer}</span>
                <span className={`confidence-badge ${r.confidence}`}>{r.confidence}</span>
              </div>
            </div>
          ))}
        </div></div>
      </>)}
    </div>
  );
}
