import React, { useState, useEffect } from 'react';
import {
  getAdminUsers,
  createAdminUser,
  toggleAdminUserStatus,
  deleteAdminUser,
  type AdminStaffUser,
} from '../../api/admin';

export function AdminUsersView() {
  const [users, setUsers] = useState<AdminStaffUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createForm, setCreateForm] = useState({
    name: '',
    email: '',
    password: '',
    is_superuser: true,
  });
  const [createError, setCreateError] = useState('');
  const [createSuccess, setCreateSuccess] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const data = await getAdminUsers();
      setUsers(data);
    } catch (err: any) {
      console.error('Failed to fetch administrator accounts:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleToggleStatus = async (user: AdminStaffUser) => {
    const action = user.is_active ? 'deactivate' : 'activate';
    const confirmed = window.confirm(
      `Are you sure you want to ${action} user "${user.name || user.username}" (${user.email})?`
    );
    if (!confirmed) return;

    try {
      const res = await toggleAdminUserStatus(user.id);
      alert(res.message);
      fetchUsers();
    } catch (err: any) {
      const msg = err.response?.data?.error || err.message || 'Failed to toggle user status.';
      alert(`Action Blocked: ${msg}`);
    }
  };

  const handleDeleteUser = async (user: AdminStaffUser) => {
    const confirmed = window.confirm(
      `Are you sure you want to permanently delete administrator account "${user.name || user.username}" (${user.email})?\n\nThis action cannot be undone.`
    );
    if (!confirmed) return;

    try {
      const res = await deleteAdminUser(user.id);
      alert(res.message);
      fetchUsers();
    } catch (err: any) {
      const msg = err.response?.data?.error || err.message || 'Failed to delete user account.';
      alert(`Deletion Denied: ${msg}`);
    }
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError('');
    setCreateSuccess('');
    if (!createForm.email.trim()) {
      setCreateError('Email is required.');
      return;
    }
    if (!createForm.password.trim() || createForm.password.length < 8) {
      setCreateError('Password must be at least 8 characters long.');
      return;
    }

    setSubmitting(true);
    try {
      const res = await createAdminUser({
        email: createForm.email.trim(),
        password: createForm.password.trim(),
        name: createForm.name.trim() || undefined,
        is_superuser: createForm.is_superuser,
      });
      setCreateSuccess(res.message);
      setShowCreateModal(false);
      setCreateForm({ name: '', email: '', password: '', is_superuser: true });
      fetchUsers();
    } catch (err: any) {
      const msg = err.response?.data?.detail || err.message || 'Failed to create administrator account.';
      setCreateError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ padding: '24px 32px' }}>
      {/* ─── HEADER & ACTIONS ───────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 800, color: '#0B2E6F', margin: 0 }}>
            Administrator & Staff Accounts
          </h1>
          <p style={{ margin: '4px 0 0', color: '#556987', fontSize: '14px' }}>
            Manage privileged user credentials, superusers, and institutional administrator accounts.
          </p>
        </div>
        <button
          onClick={() => {
            setCreateError('');
            setCreateSuccess('');
            setShowCreateModal(true);
          }}
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
          Add New Superuser
        </button>
      </div>

      {createSuccess && (
        <div style={{ padding: '12px 16px', backgroundColor: '#F0FDF4', border: '1px solid #BBF7D0', color: '#15803D', borderRadius: '8px', marginBottom: '20px', fontSize: '13px' }}>
          ✓ {createSuccess}
        </div>
      )}

      {/* ─── USERS TABLE ────────────────────────────────────────────── */}
      <div style={{ backgroundColor: '#FFFFFF', borderRadius: '10px', border: '1px solid #E2E8F0', overflowX: 'auto', boxShadow: '0 1px 3px rgba(0,0,0,0.02)' }}>
        {loading ? (
          <div style={{ padding: '48px', textAlign: 'center', color: '#64748B', fontWeight: 600 }}>
            Loading administrators...
          </div>
        ) : users.length === 0 ? (
          <div style={{ padding: '48px', textAlign: 'center', color: '#64748B' }}>
            No staff accounts found.
          </div>
        ) : (
          <table style={{ width: '100%', minWidth: '850px', borderCollapse: 'collapse', textAlign: 'left', fontSize: '14px' }}>
            <thead>
              <tr style={{ backgroundColor: '#F8FAFC', borderBottom: '1px solid #E2E8F0' }}>
                <th style={{ padding: '12px 16px', fontWeight: 700, color: '#475569' }}>USER / NAME</th>
                <th style={{ padding: '12px 16px', fontWeight: 700, color: '#475569' }}>LOGIN EMAIL</th>
                <th style={{ padding: '12px 16px', fontWeight: 700, color: '#475569', textAlign: 'center' }}>ROLE</th>
                <th style={{ padding: '12px 16px', fontWeight: 700, color: '#475569', textAlign: 'center' }}>SUPERUSER</th>
                <th style={{ padding: '12px 16px', fontWeight: 700, color: '#475569', textAlign: 'center' }}>STATUS</th>
                <th style={{ padding: '12px 16px', fontWeight: 700, color: '#475569', textAlign: 'center' }}>DATE CREATED</th>
                <th style={{ padding: '12px 16px', fontWeight: 700, color: '#475569', textAlign: 'right' }}>ACTIONS</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} style={{ borderBottom: '1px solid #F1F5F9', transition: 'background-color 0.15s' }}>
                  <td style={{ padding: '14px 16px' }}>
                    <div style={{ fontWeight: 700, color: '#0F172A' }}>{u.name || u.username}</div>
                    <div style={{ fontSize: '12px', color: '#64748B' }}>@{u.username}</div>
                  </td>
                  <td style={{ padding: '14px 16px', fontWeight: 600, color: '#0B2E6F' }}>
                    {u.email}
                  </td>
                  <td style={{ padding: '14px 16px', textAlign: 'center' }}>
                    <span style={{ backgroundColor: '#EEF2FF', color: '#3730A3', fontWeight: 700, fontSize: '12px', padding: '3px 8px', borderRadius: '4px' }}>
                      {u.role}
                    </span>
                  </td>
                  <td style={{ padding: '14px 16px', textAlign: 'center' }}>
                    <span style={{ backgroundColor: u.is_superuser ? '#DCFCE7' : '#F1F5F9', color: u.is_superuser ? '#15803D' : '#64748B', fontWeight: 700, fontSize: '12px', padding: '3px 8px', borderRadius: '4px' }}>
                      {u.is_superuser ? 'Superuser' : 'Staff'}
                    </span>
                  </td>
                  <td style={{ padding: '14px 16px', textAlign: 'center' }}>
                    <span style={{ backgroundColor: u.is_active ? '#DCFCE7' : '#FEE2E2', color: u.is_active ? '#15803D' : '#991B1B', fontWeight: 700, fontSize: '12px', padding: '3px 8px', borderRadius: '4px' }}>
                      {u.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td style={{ padding: '14px 16px', textAlign: 'center', color: '#64748B', fontSize: '13px' }}>
                    {u.date_joined ? new Date(u.date_joined).toLocaleDateString() : '—'}
                  </td>
                  <td style={{ padding: '14px 16px', textAlign: 'right' }}>
                    <div style={{ display: 'inline-flex', gap: '8px', justifyContent: 'flex-end' }}>
                      <button
                        onClick={() => handleToggleStatus(u)}
                        style={{
                          padding: '4px 10px',
                          backgroundColor: u.is_active ? '#FEF3C7' : '#DCFCE7',
                          color: u.is_active ? '#92400E' : '#15803D',
                          border: `1px solid ${u.is_active ? '#FDE68A' : '#BBF7D0'}`,
                          borderRadius: '6px',
                          fontSize: '12px',
                          fontWeight: 700,
                          cursor: 'pointer',
                        }}
                        title={u.is_active ? 'Deactivate user' : 'Activate user'}
                      >
                        {u.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                      <button
                        onClick={() => handleDeleteUser(u)}
                        style={{
                          padding: '4px 10px',
                          backgroundColor: '#FFF1F2',
                          color: '#BE123C',
                          border: '1px solid #FDA4AF',
                          borderRadius: '6px',
                          fontSize: '12px',
                          fontWeight: 600,
                          cursor: 'pointer',
                        }}
                        title="Permanently delete user"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* ─── CREATE SUPERUSER MODAL ─────────────────────────────────── */}
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
              padding: '24px 28px',
              width: '460px',
              maxWidth: '92vw',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h2 style={{ fontSize: '18px', fontWeight: 800, color: '#0B2E6F', margin: 0 }}>
                Create Administrator Account
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
              <div style={{ marginBottom: '14px' }}>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                  Full Name
                </label>
                <input
                  type="text"
                  placeholder="e.g. Lead Administrator"
                  value={createForm.name}
                  onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '14px', boxSizing: 'border-box' }}
                />
              </div>

              <div style={{ marginBottom: '14px' }}>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                  Login Email *
                </label>
                <input
                  type="email"
                  required
                  placeholder="e.g. admin@csl.edu"
                  value={createForm.email}
                  onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '14px', boxSizing: 'border-box' }}
                />
              </div>

              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                  Password * (Min 8 characters)
                </label>
                <input
                  type="password"
                  required
                  placeholder="Secure administrator password"
                  value={createForm.password}
                  onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '14px', boxSizing: 'border-box' }}
                />
              </div>

              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: '#334155', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={createForm.is_superuser}
                    onChange={(e) => setCreateForm({ ...createForm, is_superuser: e.target.checked })}
                  />
                  <span>Grant full <strong>Superuser & Staff privileges</strong></span>
                </label>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  style={{ backgroundColor: '#F1F5F9', color: '#475569', border: 'none', borderRadius: '6px', padding: '8px 16px', fontWeight: 600, cursor: 'pointer' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  style={{ backgroundColor: '#0B2E6F', color: '#FFFFFF', border: 'none', borderRadius: '6px', padding: '8px 18px', fontWeight: 700, cursor: 'pointer' }}
                >
                  {submitting ? 'Creating...' : 'Create Account'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
