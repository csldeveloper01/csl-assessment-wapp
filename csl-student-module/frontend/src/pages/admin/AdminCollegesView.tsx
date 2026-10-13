import React, { useState, useEffect } from 'react';
import {
  getAdminColleges,
  createAdminCollege,
  toggleAdminCollegeStatus,
  importAdminCollegeCandidates,
  getAdminCollegeDetail,
  type AdminCollege,
  type AdminCollegeDetail,
} from '../../api/admin';

export function AdminCollegesView() {
  const [colleges, setColleges] = useState<AdminCollege[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'true' | 'false'>('all');

  // Modals state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [showDetailModal, setShowDetailModal] = useState(false);

  // Selected college for import or detail
  const [selectedCollege, setSelectedCollege] = useState<AdminCollege | null>(null);
  const [collegeDetail, setCollegeDetail] = useState<AdminCollegeDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Create Form State
  const [createForm, setCreateForm] = useState({
    name: '',
    code: '',
    location: '',
    address: '',
    admin_contact_name: '',
    contact_email: '',
    contact_phone: '',
  });
  const [createError, setCreateError] = useState('');
  const [createSubmitting, setCreateSubmitting] = useState(false);

  // Import State
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importCsvText, setImportCsvText] = useState('');
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<{
    total_rows: number;
    created_count: number;
    updated_count: number;
    errors: string[];
  } | null>(null);
  const [importError, setImportError] = useState('');

  const fetchColleges = async () => {
    setLoading(true);
    try {
      const data = await getAdminColleges({
        search: search.trim() || undefined,
        is_active: statusFilter === 'all' ? undefined : statusFilter,
      });
      setColleges(data);
    } catch (err: unknown) {
      console.error('Failed to fetch colleges:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchColleges();
  }, [search, statusFilter]);

  const handleToggleStatus = async (college: AdminCollege) => {
    try {
      const res = await toggleAdminCollegeStatus(college.id);
      setColleges((prev) =>
        prev.map((c) => (c.id === college.id ? { ...c, is_active: res.is_active } : c))
      );
    } catch (err) {
      console.error('Failed to toggle status:', err);
    }
  };

  const handleOpenDetail = async (college: AdminCollege) => {
    setSelectedCollege(college);
    setShowDetailModal(true);
    setLoadingDetail(true);
    try {
      const detail = await getAdminCollegeDetail(college.id);
      setCollegeDetail(detail);
    } catch (err) {
      console.error('Failed to fetch college detail:', err);
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleOpenImport = (college: AdminCollege) => {
    setSelectedCollege(college);
    setImportFile(null);
    setImportCsvText('');
    setImportResult(null);
    setImportError('');
    setShowImportModal(true);
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError('');
    if (!createForm.name.trim()) {
      setCreateError('Institution name is required.');
      return;
    }
    if (!createForm.code.trim()) {
      setCreateError('Institution code is required.');
      return;
    }
    setCreateSubmitting(true);
    try {
      await createAdminCollege({
        ...createForm,
        code: createForm.code.trim().toUpperCase(),
      });
      setShowCreateModal(false);
      setCreateForm({
        name: '',
        code: '',
        location: '',
        address: '',
        admin_contact_name: '',
        contact_email: '',
        contact_phone: '',
      });
      fetchColleges();
    } catch (err: any) {
      const msg = err.response?.data?.code?.[0] || err.response?.data?.detail || 'Failed to create college.';
      setCreateError(msg);
    } finally {
      setCreateSubmitting(false);
    }
  };

  const handleImportSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCollege) return;
    setImportError('');
    setImportResult(null);

    if (!importFile && !importCsvText.trim()) {
      setImportError('Please select a CSV file or paste CSV text.');
      return;
    }

    setImporting(true);
    try {
      const res = await importAdminCollegeCandidates(
        selectedCollege.id,
        importFile || undefined,
        importCsvText || undefined
      );
      setImportResult(res);
      fetchColleges();
    } catch (err: any) {
      setImportError(err.response?.data?.detail || 'Failed to import candidates.');
    } finally {
      setImporting(false);
    }
  };

  // Metrics
  const totalCount = colleges.length;
  const activeCount = colleges.filter((c) => c.is_active).length;
  const totalCandidates = colleges.reduce((acc, c) => acc + (c.candidates_count || 0), 0);

  return (
    <div style={{ padding: '24px 32px' }}>
      {/* ─── HEADER & ACTIONS ───────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 800, color: '#0B2E6F', margin: 0 }}>
            Colleges & Institutions
          </h1>
          <p style={{ margin: '4px 0 0', color: '#556987', fontSize: '14px' }}>
            Manage participating academic institutions, assigned assessments, and student enrollment rosters.
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          style={{
            backgroundColor: '#0B2E6F',
            color: '#FFFFFF',
            border: 'none',
            borderRadius: '8px',
            padding: '10px 18px',
            fontWeight: 700,
            fontSize: '14px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            cursor: 'pointer',
            boxShadow: '0 2px 4px rgba(11,46,111,0.15)',
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
          Add New Institution
        </button>
      </div>

      {/* ─── KPI SUMMARY CARDS ──────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', marginBottom: '24px' }}>
        <div style={{ background: '#FFFFFF', borderRadius: '10px', padding: '16px 20px', border: '1px solid #E2E8F0', boxShadow: '0 1px 3px rgba(0,0,0,0.03)' }}>
          <div style={{ fontSize: '12px', fontWeight: 700, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Total Colleges</div>
          <div style={{ fontSize: '28px', fontWeight: 800, color: '#0B2E6F', marginTop: '6px' }}>{totalCount}</div>
        </div>
        <div style={{ background: '#FFFFFF', borderRadius: '10px', padding: '16px 20px', border: '1px solid #E2E8F0', boxShadow: '0 1px 3px rgba(0,0,0,0.03)' }}>
          <div style={{ fontSize: '12px', fontWeight: 700, color: '#16A34A', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Active Status</div>
          <div style={{ fontSize: '28px', fontWeight: 800, color: '#16A34A', marginTop: '6px' }}>{activeCount} <span style={{ fontSize: '14px', color: '#64748B', fontWeight: 500 }}>/ {totalCount}</span></div>
        </div>
        <div style={{ background: '#FFFFFF', borderRadius: '10px', padding: '16px 20px', border: '1px solid #E2E8F0', boxShadow: '0 1px 3px rgba(0,0,0,0.03)' }}>
          <div style={{ fontSize: '12px', fontWeight: 700, color: '#2563EB', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Enrolled Students</div>
          <div style={{ fontSize: '28px', fontWeight: 800, color: '#2563EB', marginTop: '6px' }}>{totalCandidates}</div>
        </div>
      </div>

      {/* ─── CONTROLS: SEARCH & STATUS ──────────────────────────────── */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '16px', alignItems: 'center' }}>
        <div style={{ position: 'relative', flex: 1 }}>
          <input
            type="text"
            placeholder="Search by college name, code, location, email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              width: '100%',
              padding: '10px 14px 10px 38px',
              borderRadius: '8px',
              border: '1px solid #CBD5E1',
              fontSize: '14px',
              boxSizing: 'border-box',
              outline: 'none',
              backgroundColor: '#FFFFFF',
            }}
          />
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="#94A3B8"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }}
          >
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          </svg>
        </div>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as any)}
          style={{
            padding: '10px 14px',
            borderRadius: '8px',
            border: '1px solid #CBD5E1',
            fontSize: '14px',
            backgroundColor: '#FFFFFF',
            cursor: 'pointer',
            outline: 'none',
            fontWeight: 500,
          }}
        >
          <option value="all">All Statuses</option>
          <option value="true">Active Only</option>
          <option value="false">Inactive Only</option>
        </select>
      </div>

      {/* ─── COLLEGES TABLE ─────────────────────────────────────────── */}
      <div style={{ backgroundColor: '#FFFFFF', borderRadius: '10px', border: '1px solid #E2E8F0', overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.02)' }}>
        {loading ? (
          <div style={{ padding: '48px', textAlign: 'center', color: '#64748B', fontWeight: 600 }}>
            Loading colleges roster...
          </div>
        ) : colleges.length === 0 ? (
          <div style={{ padding: '48px', textAlign: 'center', color: '#64748B' }}>
            <div style={{ fontWeight: 700, fontSize: '16px', color: '#0B2E6F', marginBottom: '6px' }}>No colleges found</div>
            <p style={{ margin: 0, fontSize: '14px' }}>Try adjusting your search filters or click "Add New Institution" to register one.</p>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '14px' }}>
            <thead>
              <tr style={{ backgroundColor: '#F8FAFC', borderBottom: '1px solid #E2E8F0' }}>
                <th style={{ padding: '12px 16px', fontWeight: 700, color: '#475569', width: '100px' }}>CODE</th>
                <th style={{ padding: '12px 16px', fontWeight: 700, color: '#475569' }}>INSTITUTION NAME</th>
                <th style={{ padding: '12px 16px', fontWeight: 700, color: '#475569' }}>LOCATION</th>
                <th style={{ padding: '12px 16px', fontWeight: 700, color: '#475569' }}>CONTACT / TPO</th>
                <th style={{ padding: '12px 16px', fontWeight: 700, color: '#475569', textAlign: 'center' }}>STUDENTS</th>
                <th style={{ padding: '12px 16px', fontWeight: 700, color: '#475569', textAlign: 'center' }}>ASSESSMENTS</th>
                <th style={{ padding: '12px 16px', fontWeight: 700, color: '#475569', textAlign: 'center' }}>STATUS</th>
                <th style={{ padding: '12px 16px', fontWeight: 700, color: '#475569', textAlign: 'right' }}>ACTIONS</th>
              </tr>
            </thead>
            <tbody>
              {colleges.map((col) => (
                <tr key={col.id} style={{ borderBottom: '1px solid #F1F5F9', transition: 'background-color 0.15s' }}>
                  <td style={{ padding: '14px 16px' }}>
                    <span
                      style={{
                        backgroundColor: '#EEF2FF',
                        color: '#3730A3',
                        fontWeight: 700,
                        fontSize: '12px',
                        padding: '4px 8px',
                        borderRadius: '6px',
                        letterSpacing: '0.02em',
                      }}
                    >
                      {col.code}
                    </span>
                  </td>
                  <td style={{ padding: '14px 16px' }}>
                    <div style={{ fontWeight: 700, color: '#0F172A' }}>{col.name}</div>
                    {col.contact_email && (
                      <div style={{ fontSize: '12px', color: '#64748B', marginTop: '2px' }}>{col.contact_email}</div>
                    )}
                  </td>
                  <td style={{ padding: '14px 16px', color: '#475569' }}>
                    {col.location || '—'}
                  </td>
                  <td style={{ padding: '14px 16px', color: '#475569' }}>
                    <div>{col.admin_contact_name || 'TPO Representative'}</div>
                    {col.contact_phone && (
                      <div style={{ fontSize: '12px', color: '#64748B' }}>{col.contact_phone}</div>
                    )}
                  </td>
                  <td style={{ padding: '14px 16px', textAlign: 'center', fontWeight: 700, color: '#0B2E6F' }}>
                    {col.candidates_count || 0}
                  </td>
                  <td style={{ padding: '14px 16px', textAlign: 'center', fontWeight: 700, color: '#6366F1' }}>
                    {col.assigned_assessments_count || 0}
                  </td>
                  <td style={{ padding: '14px 16px', textAlign: 'center' }}>
                    <span
                      style={{
                        display: 'inline-block',
                        padding: '3px 10px',
                        borderRadius: '12px',
                        fontSize: '12px',
                        fontWeight: 700,
                        backgroundColor: col.is_active ? '#DCFCE7' : '#F1F5F9',
                        color: col.is_active ? '#15803D' : '#64748B',
                      }}
                    >
                      {col.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td style={{ padding: '14px 16px', textAlign: 'right' }}>
                    <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                      <button
                        onClick={() => handleOpenImport(col)}
                        title="Bulk Import Candidates CSV"
                        style={{
                          backgroundColor: '#F8FAFC',
                          color: '#0B2E6F',
                          border: '1px solid #CBD5E1',
                          padding: '6px 10px',
                          borderRadius: '6px',
                          fontSize: '12px',
                          fontWeight: 600,
                          cursor: 'pointer',
                        }}
                      >
                        Import CSV
                      </button>
                      <button
                        onClick={() => handleOpenDetail(col)}
                        title="View details and roster"
                        style={{
                          backgroundColor: '#EFF6FF',
                          color: '#1D4ED8',
                          border: '1px solid #BFDBFE',
                          padding: '6px 10px',
                          borderRadius: '6px',
                          fontSize: '12px',
                          fontWeight: 600,
                          cursor: 'pointer',
                        }}
                      >
                        View
                      </button>
                      <button
                        onClick={() => handleToggleStatus(col)}
                        title={col.is_active ? 'Deactivate Institution' : 'Activate Institution'}
                        style={{
                          backgroundColor: col.is_active ? '#FFF1F2' : '#F0FDF4',
                          color: col.is_active ? '#E11D48' : '#16A34A',
                          border: `1px solid ${col.is_active ? '#FECDD3' : '#BBF7D0'}`,
                          padding: '6px 10px',
                          borderRadius: '6px',
                          fontSize: '12px',
                          fontWeight: 600,
                          cursor: 'pointer',
                        }}
                      >
                        {col.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* ─── CREATE COLLEGE MODAL ────────────────────────────────────── */}
      {showCreateModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
          }}
        >
          <div
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: '12px',
              padding: '28px',
              width: '560px',
              maxWidth: '90vw',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
              <h2 style={{ fontSize: '18px', fontWeight: 800, color: '#0B2E6F', margin: 0 }}>
                Register Participating Institution
              </h2>
              <button
                onClick={() => setShowCreateModal(false)}
                style={{ background: 'none', border: 'none', fontSize: '20px', cursor: 'pointer', color: '#94A3B8' }}
              >
                ✕
              </button>
            </div>

            {createError && (
              <div style={{ padding: '10px 14px', backgroundColor: '#FEF2F2', border: '1px solid #FCA5A5', color: '#B91C1C', borderRadius: '6px', fontSize: '13px', marginBottom: '16px' }}>
                {createError}
              </div>
            )}

            <form onSubmit={handleCreateSubmit}>
              <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '14px', marginBottom: '14px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                    Institution Official Name *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Coimbatore Institute of Technology"
                    value={createForm.name}
                    onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '14px', boxSizing: 'border-box' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                    Unique Code *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. CIT"
                    value={createForm.code}
                    onChange={(e) => setCreateForm({ ...createForm, code: e.target.value.toUpperCase() })}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '14px', boxSizing: 'border-box', textTransform: 'uppercase' }}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '14px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                    City / Campus Location
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Coimbatore, Tamil Nadu"
                    value={createForm.location}
                    onChange={(e) => setCreateForm({ ...createForm, location: e.target.value })}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '14px', boxSizing: 'border-box' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                    TPO / Faculty In-Charge Name
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Dr. Rajesh Kumar"
                    value={createForm.admin_contact_name}
                    onChange={(e) => setCreateForm({ ...createForm, admin_contact_name: e.target.value })}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '14px', boxSizing: 'border-box' }}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '14px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                    Official Contact Email
                  </label>
                  <input
                    type="email"
                    placeholder="e.g. placement@cit.edu.in"
                    value={createForm.contact_email}
                    onChange={(e) => setCreateForm({ ...createForm, contact_email: e.target.value })}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '14px', boxSizing: 'border-box' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                    Contact Phone
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. +91 9876543210"
                    value={createForm.contact_phone}
                    onChange={(e) => setCreateForm({ ...createForm, contact_phone: e.target.value })}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '14px', boxSizing: 'border-box' }}
                  />
                </div>
              </div>

              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                  Campus Address
                </label>
                <textarea
                  rows={2}
                  placeholder="Street, Campus, Pincode"
                  value={createForm.address}
                  onChange={(e) => setCreateForm({ ...createForm, address: e.target.value })}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '14px', boxSizing: 'border-box' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  style={{ backgroundColor: '#F1F5F9', color: '#475569', border: 'none', borderRadius: '6px', padding: '10px 16px', fontWeight: 600, cursor: 'pointer' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createSubmitting}
                  style={{ backgroundColor: '#0B2E6F', color: '#FFFFFF', border: 'none', borderRadius: '6px', padding: '10px 20px', fontWeight: 700, cursor: 'pointer' }}
                >
                  {createSubmitting ? 'Registering...' : 'Save Institution'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─── IMPORT CANDIDATES MODAL ─────────────────────────────────── */}
      {showImportModal && selectedCollege && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
          }}
        >
          <div
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: '12px',
              padding: '28px',
              width: '620px',
              maxWidth: '90vw',
              maxHeight: '90vh',
              overflowY: 'auto',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <div>
                <h2 style={{ fontSize: '18px', fontWeight: 800, color: '#0B2E6F', margin: 0 }}>
                  Import Candidates for {selectedCollege.name}
                </h2>
                <span style={{ fontSize: '12px', color: '#64748B' }}>Code: {selectedCollege.code}</span>
              </div>
              <button
                onClick={() => setShowImportModal(false)}
                style={{ background: 'none', border: 'none', fontSize: '20px', cursor: 'pointer', color: '#94A3B8' }}
              >
                ✕
              </button>
            </div>

            <div style={{ backgroundColor: '#F0F9FF', border: '1px solid #BAE6FD', padding: '12px', borderRadius: '8px', marginBottom: '16px', fontSize: '12px', color: '#0369A1' }}>
              <strong>Required CSV Headers:</strong> <br />
              <code style={{ background: '#E0F2FE', padding: '2px 4px', borderRadius: '4px' }}>
                full_name, register_number, email, department, year_of_study, phone_number
              </code>
              <br />
              Duplicates within {selectedCollege.name} will update existing records automatically.
            </div>

            {importError && (
              <div style={{ padding: '10px 14px', backgroundColor: '#FEF2F2', border: '1px solid #FCA5A5', color: '#B91C1C', borderRadius: '6px', fontSize: '13px', marginBottom: '16px' }}>
                {importError}
              </div>
            )}

            {importResult && (
              <div style={{ padding: '14px', backgroundColor: '#F0FDF4', border: '1px solid #86EFAC', borderRadius: '8px', marginBottom: '16px' }}>
                <div style={{ fontWeight: 700, color: '#15803D', fontSize: '14px', marginBottom: '6px' }}>
                  CSV Import Complete
                </div>
                <div style={{ fontSize: '13px', color: '#166534' }}>
                  Processed <strong>{importResult.total_rows}</strong> rows: Created <strong>{importResult.created_count}</strong> new, Updated <strong>{importResult.updated_count}</strong>.
                </div>
                {importResult.errors && importResult.errors.length > 0 && (
                  <div style={{ marginTop: '8px', padding: '8px', backgroundColor: '#FFF7ED', borderRadius: '4px', fontSize: '12px', color: '#C2410C' }}>
                    <strong>{importResult.errors.length} Warnings/Errors:</strong>
                    <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>
                      {importResult.errors.slice(0, 5).map((e, idx) => (
                        <li key={idx}>{e}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            <form onSubmit={handleImportSubmit}>
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 700, color: '#334155', marginBottom: '6px' }}>
                  Option A: Upload CSV File
                </label>
                <input
                  type="file"
                  accept=".csv"
                  onChange={(e) => setImportFile(e.target.files?.[0] || null)}
                  style={{ fontSize: '13px' }}
                />
              </div>

              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 700, color: '#334155', marginBottom: '6px' }}>
                  Option B: Or Paste CSV Text
                </label>
                <textarea
                  rows={5}
                  placeholder={`full_name,register_number,email,department,year_of_study,phone_number\nArun Kumar,717821L101,arun@cit.edu.in,ECE,Final Year,9876543210`}
                  value={importCsvText}
                  onChange={(e) => setImportCsvText(e.target.value)}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '12px', fontFamily: 'monospace', boxSizing: 'border-box' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="button"
                  onClick={() => setShowImportModal(false)}
                  style={{ backgroundColor: '#F1F5F9', color: '#475569', border: 'none', borderRadius: '6px', padding: '10px 16px', fontWeight: 600, cursor: 'pointer' }}
                >
                  Close
                </button>
                <button
                  type="submit"
                  disabled={importing}
                  style={{ backgroundColor: '#0B2E6F', color: '#FFFFFF', border: 'none', borderRadius: '6px', padding: '10px 20px', fontWeight: 700, cursor: 'pointer' }}
                >
                  {importing ? 'Processing CSV...' : 'Start Import'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─── COLLEGE DETAIL MODAL ───────────────────────────────────── */}
      {showDetailModal && selectedCollege && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
          }}
        >
          <div
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: '12px',
              padding: '28px',
              width: '740px',
              maxWidth: '92vw',
              maxHeight: '90vh',
              overflowY: 'auto',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <h2 style={{ fontSize: '20px', fontWeight: 800, color: '#0B2E6F', margin: 0 }}>
                    {selectedCollege.name}
                  </h2>
                  <span style={{ backgroundColor: '#EEF2FF', color: '#3730A3', fontWeight: 700, fontSize: '12px', padding: '2px 8px', borderRadius: '4px' }}>
                    {selectedCollege.code}
                  </span>
                </div>
                <div style={{ fontSize: '13px', color: '#64748B', marginTop: '4px' }}>
                  {selectedCollege.location || 'Campus'} • Status: {selectedCollege.is_active ? 'Active' : 'Inactive'}
                </div>
              </div>
              <button
                onClick={() => setShowDetailModal(false)}
                style={{ background: 'none', border: 'none', fontSize: '22px', cursor: 'pointer', color: '#94A3B8' }}
              >
                ✕
              </button>
            </div>

            {loadingDetail ? (
              <div style={{ padding: '36px', textAlign: 'center', color: '#64748B' }}>Loading institution details...</div>
            ) : collegeDetail ? (
              <div>
                {/* Contact Card */}
                <div style={{ backgroundColor: '#F8FAFC', borderRadius: '8px', padding: '14px 18px', marginBottom: '20px', fontSize: '13px', border: '1px solid #E2E8F0' }}>
                  <div style={{ fontWeight: 700, color: '#334155', marginBottom: '6px' }}>Administrative Contact</div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px' }}>
                    <div><strong>Representative:</strong> {collegeDetail.admin_contact_name || '—'}</div>
                    <div><strong>Email:</strong> {collegeDetail.contact_email || '—'}</div>
                    <div><strong>Phone:</strong> {collegeDetail.contact_phone || '—'}</div>
                  </div>
                  {collegeDetail.address && (
                    <div style={{ marginTop: '8px' }}><strong>Address:</strong> {collegeDetail.address}</div>
                  )}
                </div>

                {/* Assigned Assessments Section */}
                <div style={{ marginBottom: '24px' }}>
                  <h3 style={{ fontSize: '15px', fontWeight: 700, color: '#0F172A', marginBottom: '10px' }}>
                    Assigned Assessments ({collegeDetail.assigned_assessments?.length || 0})
                  </h3>
                  {collegeDetail.assigned_assessments && collegeDetail.assigned_assessments.length > 0 ? (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '10px' }}>
                      {collegeDetail.assigned_assessments.map((a) => (
                        <div key={a.id} style={{ border: '1px solid #E2E8F0', borderRadius: '6px', padding: '10px 14px', backgroundColor: '#FFFFFF' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontWeight: 700, fontSize: '13px', color: '#0B2E6F' }}>{a.title}</span>
                            <span style={{ fontSize: '11px', fontWeight: 700, padding: '2px 6px', borderRadius: '4px', backgroundColor: a.is_open ? '#DCFCE7' : '#F1F5F9', color: a.is_open ? '#15803D' : '#64748B' }}>
                              {a.status}
                            </span>
                          </div>
                          <div style={{ fontSize: '12px', color: '#64748B', marginTop: '4px' }}>
                            Code: <strong>{a.code}</strong> • {a.duration_minutes} mins • {a.total_marks} marks
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ fontSize: '13px', color: '#94A3B8', fontStyle: 'italic' }}>
                      No assessments currently assigned to this institution.
                    </div>
                  )}
                </div>

                {/* Registered Candidates Preview */}
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                    <h3 style={{ fontSize: '15px', fontWeight: 700, color: '#0F172A', margin: 0 }}>
                      Registered Student Roster ({collegeDetail.candidates?.length || 0})
                    </h3>
                    <button
                      onClick={() => {
                        setShowDetailModal(false);
                        handleOpenImport(selectedCollege);
                      }}
                      style={{ fontSize: '12px', color: '#0B2E6F', background: 'none', border: 'none', fontWeight: 700, cursor: 'pointer' }}
                    >
                      + Import More Students
                    </button>
                  </div>

                  {collegeDetail.candidates && collegeDetail.candidates.length > 0 ? (
                    <div style={{ border: '1px solid #E2E8F0', borderRadius: '6px', overflow: 'hidden', maxHeight: '200px', overflowY: 'auto' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                        <thead>
                          <tr style={{ backgroundColor: '#F8FAFC', borderBottom: '1px solid #E2E8F0' }}>
                            <th style={{ padding: '8px 12px', fontWeight: 700 }}>Reg No</th>
                            <th style={{ padding: '8px 12px', fontWeight: 700 }}>Name</th>
                            <th style={{ padding: '8px 12px', fontWeight: 700 }}>Email</th>
                            <th style={{ padding: '8px 12px', fontWeight: 700 }}>Department</th>
                            <th style={{ padding: '8px 12px', fontWeight: 700 }}>Phone</th>
                          </tr>
                        </thead>
                        <tbody>
                          {collegeDetail.candidates.map((cand) => (
                            <tr key={cand.id} style={{ borderBottom: '1px solid #F1F5F9' }}>
                              <td style={{ padding: '8px 12px', fontWeight: 600 }}>{cand.register_number}</td>
                              <td style={{ padding: '8px 12px' }}>{cand.full_name}</td>
                              <td style={{ padding: '8px 12px', color: '#64748B' }}>{cand.email}</td>
                              <td style={{ padding: '8px 12px' }}>{cand.department}</td>
                              <td style={{ padding: '8px 12px' }}>{cand.phone_number || '—'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div style={{ fontSize: '13px', color: '#94A3B8', fontStyle: 'italic' }}>
                      No students registered yet. Click "Import More Students" to upload a CSV.
                    </div>
                  )}
                </div>
              </div>
            ) : null}

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '24px' }}>
              <button
                onClick={() => setShowDetailModal(false)}
                style={{ backgroundColor: '#0B2E6F', color: '#FFFFFF', border: 'none', borderRadius: '6px', padding: '8px 18px', fontWeight: 700, cursor: 'pointer' }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
