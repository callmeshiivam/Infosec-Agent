const API_BASE = 'http://localhost:8000/api';

/**
 * API Client for the InfoSec Agent backend
 */
const api = {
  // ===== Documents =====

  uploadDocument(file, onProgress) {
    return new Promise((resolve, reject) => {
      const formData = new FormData();
      formData.append('file', file);
      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${API_BASE}/documents/upload`);
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && onProgress) {
          onProgress(Math.round((e.loaded / e.total) * 100));
        }
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.response));
        } else {
          try {
            const err = JSON.parse(xhr.response);
            reject(new Error(err.detail || 'Upload failed'));
          } catch {
            reject(new Error('Upload failed'));
          }
        }
      };
      xhr.onerror = () => reject(new Error('Network error during upload.'));
      xhr.send(formData);
    });
  },

  async listDocuments() {
    const res = await fetch(`${API_BASE}/documents/list`);
    if (!res.ok) throw new Error('Failed to fetch documents');
    return res.json();
  },

  async deleteDocument(filename) {
    const res = await fetch(`${API_BASE}/documents/delete/${encodeURIComponent(filename)}`, {
      method: 'DELETE',
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Delete failed');
    }
    return res.json();
  },

  async deleteAllDocuments() {
    const res = await fetch(`${API_BASE}/documents/delete_all`, {
      method: 'DELETE',
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Delete all failed');
    }
    return res.json();
  },

  async getStats() {
    const res = await fetch(`${API_BASE}/documents/stats`);
    if (!res.ok) throw new Error('Failed to fetch stats');
    return res.json();
  },

  // ===== Questionnaire =====

  async chatQuery(question, history = [], topK = 5) {
    const res = await fetch(`${API_BASE}/questionnaire/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, history, top_k: topK }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Query failed');
    }
    return res.json();
  },

  async uploadExcel(file) {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_BASE}/questionnaire/excel/upload`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Excel upload failed');
    }
    return res.json();
  },

  async processExcel({ filename, questionColumn, answerColumn, startRow, confidenceColumn, sourceColumn }) {
    const formData = new FormData();
    formData.append('filename', filename);
    formData.append('question_column', questionColumn);
    formData.append('answer_column', answerColumn);
    formData.append('start_row', startRow.toString());
    if (confidenceColumn) formData.append('confidence_column', confidenceColumn);
    if (sourceColumn) formData.append('source_column', sourceColumn);

    const res = await fetch(`${API_BASE}/questionnaire/excel/process`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Processing failed');
    }
    return res.json();
  },

  getExcelDownloadUrl(filename) {
    return `${API_BASE}/questionnaire/excel/download/${encodeURIComponent(filename)}`;
  },

  getDocumentDownloadUrl(filename) {
    return `${API_BASE}/documents/download/${encodeURIComponent(filename)}`;
  },

  async healthCheck() {
    try {
      const res = await fetch(`${API_BASE}/health`);
      if (!res.ok) return { status: 'unhealthy' };
      return res.json();
    } catch {
      return { status: 'offline' };
    }
  },
};

export default api;
