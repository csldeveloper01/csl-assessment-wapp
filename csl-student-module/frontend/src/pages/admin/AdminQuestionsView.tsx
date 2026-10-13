import { useState, useEffect } from 'react';
import {
  getAdminQuestions,
  createAdminQuestion,
  updateAdminQuestion,
  toggleAdminQuestion,
  bulkUpdateAdminQuestions,
  importAdminQuestionsCSV,
  getAdminAssessments,
  type AdminQuestion,
  type AdminAssessment,
} from '../../api/admin';
import { AdminQuestionEditorModal } from './AdminQuestionEditorModal';

export function AdminQuestionsView() {
  const [questions, setQuestions] = useState<AdminQuestion[]>([]);
  const [assessments, setAssessments] = useState<AdminAssessment[]>([]);
  const [loading, setLoading] = useState(true);

  // Hierarchy Navigation: Question Bank -> Assessment Selection -> Questions
  const [selectedAssessment, setSelectedAssessment] = useState<AdminAssessment | null>(null);
  const [assessmentSearch, setAssessmentSearch] = useState('');
  const [importAssessmentId, setImportAssessmentId] = useState<string>('');
  const [viewAllQuestions, setViewAllQuestions] = useState(false);
  const [assessmentFilterStatus, setAssessmentFilterStatus] = useState<'ALL' | 'SUFFICIENT' | 'INSUFFICIENT'>('ALL');

  // Filters
  const [sectionFilter, setSectionFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [difficultyFilter, setDifficultyFilter] = useState('');
  const [activeFilter, setActiveFilter] = useState('');
  const [assessmentFilter, setAssessmentFilter] = useState('');
  const [search, setSearch] = useState('');

  // Bulk Selection State
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [showBulkModal, setShowBulkModal] = useState(false);
  const [bulkUpdating, setBulkUpdating] = useState(false);

  // Bulk edit field checkboxes & values
  const [bulkFields, setBulkFields] = useState({
    section_type: false,
    category: false,
    difficulty: false,
    is_active: false,
  });
  const [bulkValues, setBulkValues] = useState<{
    section_type: 'APTITUDE' | 'CODING';
    category: string;
    difficulty: 'EASY' | 'MEDIUM' | 'HARD';
    is_active: boolean;
  }>({
    section_type: 'APTITUDE',
    category: '',
    difficulty: 'MEDIUM',
    is_active: true,
  });

  // Dedicated Editor Modal state
  const [showEditorModal, setShowEditorModal] = useState(false);
  const [editingQuestion, setEditingQuestion] = useState<AdminQuestion | null>(null);
  const [savingQuestion, setSavingQuestion] = useState(false);

  // CSV Import Modal state
  const [showImportModal, setShowImportModal] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importResult, setImportResult] = useState<{
    success_count: number;
    error_count: number;
    errors: string[];
  } | null>(null);
  const [importing, setImporting] = useState(false);

  // Pagination state (client-side for smooth UX)
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 15;

  const loadQuestions = async () => {
    try {
      setLoading(true);
      const data = await getAdminQuestions({
        section_type: sectionFilter || undefined,
        category: categoryFilter || undefined,
        difficulty: difficultyFilter || undefined,
        is_active: activeFilter || undefined,
        search: search || undefined,
        assessment_id: assessmentFilter || undefined,
      });
      setQuestions(data);
      setCurrentPage(1);
    } catch {
      alert('Failed to load question bank.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    getAdminAssessments().then(setAssessments).catch(() => {});
  }, []);

  useEffect(() => {
    loadQuestions();
  }, [sectionFilter, categoryFilter, difficultyFilter, activeFilter, assessmentFilter]);

  const handleSelectAssessment = (a: AdminAssessment) => {
    setSelectedAssessment(a);
    setViewAllQuestions(false);
    setAssessmentFilter(a.id);
    setImportAssessmentId(a.id);
  };

  const handleClearAssessment = () => {
    setSelectedAssessment(null);
    setViewAllQuestions(false);
    setAssessmentFilter('');
    setImportAssessmentId('');
  };

  const handleViewAllQuestions = () => {
    setSelectedAssessment(null);
    setViewAllQuestions(true);
    setAssessmentFilter('');
    setImportAssessmentId('');
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadQuestions();
  };

  // Pagination computations
  const totalQuestions = questions.length;
  const totalPages = Math.max(1, Math.ceil(totalQuestions / pageSize));
  const startIndex = (currentPage - 1) * pageSize;
  const endIndex = Math.min(startIndex + pageSize, totalQuestions);
  const paginatedQuestions = questions.slice(startIndex, endIndex);

  // Selection handlers
  const handleSelectAllCurrentPage = (checked: boolean) => {
    if (checked) {
      const pageIds = paginatedQuestions.map((q) => q.id);
      setSelectedIds((prev) => Array.from(new Set([...prev, ...pageIds])));
    } else {
      const pageIds = new Set(paginatedQuestions.map((q) => q.id));
      setSelectedIds((prev) => prev.filter((id) => !pageIds.has(id)));
    }
  };

  const isCurrentPageAllSelected =
    paginatedQuestions.length > 0 &&
    paginatedQuestions.every((q) => selectedIds.includes(q.id));
  const isCurrentPagePartiallySelected =
    paginatedQuestions.some((q) => selectedIds.includes(q.id)) && !isCurrentPageAllSelected;

  const handleToggleSelectRow = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const handleToggleActive = async (id: number) => {
    try {
      const res = await toggleAdminQuestion(id);
      setQuestions((prev) =>
        prev.map((q) => (q.id === id ? { ...q, is_active: res.is_active } : q))
      );
    } catch {
      alert('Failed to toggle question status.');
    }
  };

  const handleQuickBulkActive = async (newStatus: boolean) => {
    if (selectedIds.length === 0) return;
    const confirmMsg = `Are you sure you want to ${
      newStatus ? 'activate' : 'deactivate'
    } ${selectedIds.length} question(s)?`;
    if (!window.confirm(confirmMsg)) return;

    try {
      setBulkUpdating(true);
      const res = await bulkUpdateAdminQuestions(selectedIds, { is_active: newStatus });
      alert(res.message);
      setSelectedIds([]);
      loadQuestions();
    } catch {
      alert('Failed to apply bulk status update.');
    } finally {
      setBulkUpdating(false);
    }
  };

  const openBulkModal = () => {
    setBulkFields({
      section_type: false,
      category: false,
      difficulty: false,
      is_active: false,
    });
    setBulkValues({
      section_type: 'APTITUDE',
      category: '',
      difficulty: 'MEDIUM',
      is_active: true,
    });
    setShowBulkModal(true);
  };

  const handleBulkSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const hasField =
      bulkFields.section_type ||
      bulkFields.category ||
      bulkFields.difficulty ||
      bulkFields.is_active;

    if (!hasField) {
      alert('Please check at least one field to update across the selected questions.');
      return;
    }

    const payload: {
      section_type?: 'APTITUDE' | 'CODING';
      category?: string;
      difficulty?: 'EASY' | 'MEDIUM' | 'HARD';
      is_active?: boolean;
    } = {};

    if (bulkFields.section_type) payload.section_type = bulkValues.section_type;
    if (bulkFields.category) {
      if (!bulkValues.category.trim()) {
        alert('Please enter a category value or uncheck the Category field.');
        return;
      }
      payload.category = bulkValues.category.trim();
    }
    if (bulkFields.difficulty) payload.difficulty = bulkValues.difficulty;
    if (bulkFields.is_active) payload.is_active = bulkValues.is_active;

    try {
      setBulkUpdating(true);
      const res = await bulkUpdateAdminQuestions(selectedIds, payload);
      alert(res.message);
      setShowBulkModal(false);
      setSelectedIds([]);
      loadQuestions();
    } catch (err: unknown) {
      if (typeof err === 'object' && err !== null && 'response' in err) {
        const axErr = err as { response?: { data?: Record<string, string[]> } };
        alert(`Bulk update error: ${JSON.stringify(axErr.response?.data || 'Failed')}`);
      } else {
        alert('Failed to execute bulk update.');
      }
    } finally {
      setBulkUpdating(false);
    }
  };

  // Editor Modal actions
  const openCreateModal = () => {
    setEditingQuestion(null);
    setShowEditorModal(true);
  };

  const openEditModal = (q: AdminQuestion) => {
    setEditingQuestion(q);
    setShowEditorModal(true);
  };

  const handleSaveQuestion = async (formData: Partial<AdminQuestion> & { assessment_id: string }) => {
    try {
      setSavingQuestion(true);
      if (editingQuestion) {
        await updateAdminQuestion(editingQuestion.id, formData);
        alert('Question updated successfully. Changes will apply to future assessments.');
      } else {
        await createAdminQuestion(formData);
        alert('New question created successfully.');
      }
      setShowEditorModal(false);
      setEditingQuestion(null);
      await loadQuestions();
      const freshAssessments = await getAdminAssessments();
      setAssessments(freshAssessments);
      if (selectedAssessment) {
        const updated = freshAssessments.find((a) => a.id === selectedAssessment.id);
        if (updated) {
          setSelectedAssessment(updated);
        }
      }
    } finally {
      setSavingQuestion(false);
    }
  };

  // CSV Import handler
  const handleImportSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!importAssessmentId) {
      alert('Please select a target assessment before importing questions.');
      return;
    }
    if (!importFile) {
      alert('Please select a CSV file.');
      return;
    }
    setImporting(true);
    setImportResult(null);
    try {
      const res = await importAdminQuestionsCSV(importAssessmentId, importFile);
      setImportResult(res);
      loadQuestions();
      getAdminAssessments().then(setAssessments).catch(() => {});
    } catch (err: unknown) {
      if (typeof err === 'object' && err !== null && 'response' in err) {
        const axErr = err as { response?: { data?: { detail?: string; assessment_id?: string[] } } };
        alert(`CSV import error: ${axErr.response?.data?.detail || axErr.response?.data?.assessment_id?.[0] || 'Import failed.'}`);
      } else {
        alert('CSV import failed.');
      }
    } finally {
      setImporting(false);
    }
  };

  const filteredAssessments = assessments.filter((a) => {
    const matchesSearch =
      !assessmentSearch ||
      a.title.toLowerCase().includes(assessmentSearch.toLowerCase()) ||
      a.code.toLowerCase().includes(assessmentSearch.toLowerCase());
    const matchesStatus =
      assessmentFilterStatus === 'ALL'
        ? true
        : assessmentFilterStatus === 'SUFFICIENT'
        ? a.pool_sufficient
        : !a.pool_sufficient;
    return matchesSearch && matchesStatus;
  });

  const totalAssessmentsCount = assessments.length;
  const sufficientAssessmentsCount = assessments.filter((a) => a.pool_sufficient).length;
  const actionRequiredAssessmentsCount = assessments.filter((a) => !a.pool_sufficient).length;
  const totalPoolQuestionsCount = assessments.reduce((sum, a) => sum + (a.pool_questions_count || 0), 0);

  return (
    <div>
      {!selectedAssessment && !viewAllQuestions ? (
        /* ─── LEVEL 1: QUESTION BANK LANDING & ASSESSMENT SELECTION ── */
        <div>
          {/* Banner Header */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '20px',
              flexWrap: 'wrap',
              gap: '12px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
              <div
                style={{
                  width: '44px',
                  height: '44px',
                  borderRadius: '12px',
                  backgroundColor: 'rgba(20, 85, 184, 0.08)',
                  border: '1px solid rgba(20, 85, 184, 0.2)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#1455B8',
                }}
              >
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
                  <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
                </svg>
              </div>
              <div>
                <h2
                  style={{
                    fontSize: '22px',
                    fontWeight: 800,
                    color: '#0B2E6F',
                    margin: '0 0 2px 0',
                    letterSpacing: '-0.02em',
                  }}
                >
                  Question Bank Repository
                </h2>
                <p style={{ fontSize: '13px', color: '#64748B', margin: 0 }}>
                  Select an assessment below to manage its question pool, author curriculum items, or import questions via CSV.
                </p>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '10px' }}>
              <button
                onClick={() => {
                  setImportResult(null);
                  setShowImportModal(true);
                }}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '9px 18px',
                  backgroundColor: '#FFFFFF',
                  border: '1px solid #CBD5E1',
                  borderRadius: '8px',
                  fontSize: '13px',
                  fontWeight: 700,
                  color: '#0B2E6F',
                  cursor: 'pointer',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
                  transition: 'all 0.15s ease',
                }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                  <polyline points="7 10 12 15 17 10"></polyline>
                  <line x1="12" y1="15" x2="12" y2="3"></line>
                </svg>
                <span>Import CSV</span>
              </button>

              <button
                onClick={openCreateModal}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '9px 20px',
                  backgroundColor: '#1455B8',
                  color: '#FFFFFF',
                  border: 'none',
                  borderRadius: '8px',
                  fontSize: '13px',
                  fontWeight: 700,
                  cursor: 'pointer',
                  boxShadow: '0 2px 8px rgba(20, 85, 184, 0.25)',
                  transition: 'background-color 0.15s ease',
                }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="12" y1="5" x2="12" y2="19"></line>
                  <line x1="5" y1="12" x2="19" y2="12"></line>
                </svg>
                <span>Create New Question</span>
              </button>
            </div>
          </div>

          {/* ─── METRICS CARDS ────────────────────────────────────────── */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
              gap: '14px',
              marginBottom: '20px',
            }}
          >
            <div
              style={{
                backgroundColor: '#FFFFFF',
                borderRadius: '12px',
                border: '1px solid #E2E8F0',
                padding: '16px 18px',
                boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
              }}
            >
              <div style={{ fontSize: '12px', fontWeight: 700, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                Total Assessments
              </div>
              <div style={{ fontSize: '26px', fontWeight: 800, color: '#0B2E6F', marginTop: '4px' }}>
                {totalAssessmentsCount}
              </div>
              <div style={{ fontSize: '11.5px', color: '#94A3B8', marginTop: '2px' }}>
                Configured curriculum tracks
              </div>
            </div>

            <div
              style={{
                backgroundColor: '#FFFFFF',
                borderRadius: '12px',
                border: '1px solid #E2E8F0',
                padding: '16px 18px',
                boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
              }}
            >
              <div style={{ fontSize: '12px', fontWeight: 700, color: '#166534', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                Sufficient Pools
              </div>
              <div style={{ fontSize: '26px', fontWeight: 800, color: '#16A34A', marginTop: '4px' }}>
                {sufficientAssessmentsCount}
              </div>
              <div style={{ fontSize: '11.5px', color: '#64748B', marginTop: '2px' }}>
                Ready for exam compilation
              </div>
            </div>

            <div
              style={{
                backgroundColor: '#FFFFFF',
                borderRadius: '12px',
                border: '1px solid #E2E8F0',
                padding: '16px 18px',
                boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
              }}
            >
              <div style={{ fontSize: '12px', fontWeight: 700, color: '#B45309', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                Action Required
              </div>
              <div style={{ fontSize: '26px', fontWeight: 800, color: '#D97706', marginTop: '4px' }}>
                {actionRequiredAssessmentsCount}
              </div>
              <div style={{ fontSize: '11.5px', color: '#64748B', marginTop: '2px' }}>
                Pool below required count
              </div>
            </div>

            <div
              style={{
                backgroundColor: '#FFFFFF',
                borderRadius: '12px',
                border: '1px solid #E2E8F0',
                padding: '16px 18px',
                boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
              }}
            >
              <div style={{ fontSize: '12px', fontWeight: 700, color: '#0B2E6F', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                Total Questions in Pools
              </div>
              <div style={{ fontSize: '26px', fontWeight: 800, color: '#1455B8', marginTop: '4px' }}>
                {totalPoolQuestionsCount}
              </div>
              <div style={{ fontSize: '11.5px', color: '#64748B', marginTop: '2px' }}>
                Assigned across all tracks
              </div>
            </div>
          </div>

          {/* ─── ASSESSMENT SELECTION TOOLBAR ─────────────────────────── */}
          <div
            style={{
              backgroundColor: '#FFFFFF',
              borderRadius: '12px',
              border: '1px solid #E2E8F0',
              padding: '12px 18px',
              marginBottom: '18px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '12px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1, minWidth: '280px' }}>
              <div style={{ position: 'relative', width: '100%', maxWidth: '360px' }}>
                <svg
                  width="15"
                  height="15"
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
                <input
                  type="text"
                  value={assessmentSearch}
                  onChange={(e) => setAssessmentSearch(e.target.value)}
                  placeholder="Search assessments by code or title..."
                  style={{
                    padding: '9px 12px 9px 36px',
                    borderRadius: '8px',
                    border: '1px solid #CBD5E1',
                    fontSize: '13px',
                    width: '100%',
                    boxSizing: 'border-box',
                    outlineColor: '#1455B8',
                  }}
                />
              </div>

              <div style={{ display: 'flex', gap: '6px' }}>
                <button
                  onClick={() => setAssessmentFilterStatus('ALL')}
                  style={{
                    padding: '6px 12px',
                    borderRadius: '6px',
                    border: assessmentFilterStatus === 'ALL' ? '1px solid #1455B8' : '1px solid #E2E8F0',
                    backgroundColor: assessmentFilterStatus === 'ALL' ? 'rgba(20, 85, 184, 0.08)' : '#FFFFFF',
                    color: assessmentFilterStatus === 'ALL' ? '#1455B8' : '#64748B',
                    fontSize: '12px',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  All ({totalAssessmentsCount})
                </button>
                <button
                  onClick={() => setAssessmentFilterStatus('SUFFICIENT')}
                  style={{
                    padding: '6px 12px',
                    borderRadius: '6px',
                    border: assessmentFilterStatus === 'SUFFICIENT' ? '1px solid #16A34A' : '1px solid #E2E8F0',
                    backgroundColor: assessmentFilterStatus === 'SUFFICIENT' ? 'rgba(22, 163, 74, 0.08)' : '#FFFFFF',
                    color: assessmentFilterStatus === 'SUFFICIENT' ? '#166534' : '#64748B',
                    fontSize: '12px',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  Sufficient ({sufficientAssessmentsCount})
                </button>
                <button
                  onClick={() => setAssessmentFilterStatus('INSUFFICIENT')}
                  style={{
                    padding: '6px 12px',
                    borderRadius: '6px',
                    border: assessmentFilterStatus === 'INSUFFICIENT' ? '1px solid #D97706' : '1px solid #E2E8F0',
                    backgroundColor: assessmentFilterStatus === 'INSUFFICIENT' ? 'rgba(217, 119, 6, 0.08)' : '#FFFFFF',
                    color: assessmentFilterStatus === 'INSUFFICIENT' ? '#B45309' : '#64748B',
                    fontSize: '12px',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  Action Required ({actionRequiredAssessmentsCount})
                </button>
              </div>
            </div>

            <button
              onClick={handleViewAllQuestions}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 14px',
                backgroundColor: '#F8FAFC',
                border: '1px solid #CBD5E1',
                borderRadius: '8px',
                fontSize: '12px',
                fontWeight: 700,
                color: '#0B2E6F',
                cursor: 'pointer',
                transition: 'background-color 0.15s',
              }}
            >
              <span>Browse Global Pool (All Questions) →</span>
            </button>
          </div>

          {/* ─── ASSESSMENT CARDS GRID ─────────────────────────────────── */}
          {filteredAssessments.length === 0 ? (
            <div
              style={{
                backgroundColor: '#FFFFFF',
                borderRadius: '12px',
                border: '1px solid #E2E8F0',
                padding: '48px 24px',
                textAlign: 'center',
                color: '#64748B',
              }}
            >
              <div style={{ fontSize: '15px', fontWeight: 700, color: '#0B2E6F', marginBottom: '4px' }}>
                No assessments found
              </div>
              <div style={{ fontSize: '13px' }}>
                No assessments match your current search and filter criteria.
              </div>
            </div>
          ) : (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))',
                gap: '18px',
              }}
            >
              {filteredAssessments.map((a) => (
                <div
                  key={a.id}
                  style={{
                    backgroundColor: '#FFFFFF',
                    borderRadius: '14px',
                    border: '1.5px solid #E2E8F0',
                    padding: '20px',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    boxShadow: '0 2px 6px rgba(11, 46, 111, 0.03)',
                    transition: 'all 0.15s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = '#1455B8';
                    e.currentTarget.style.boxShadow = '0 6px 18px rgba(20, 85, 184, 0.08)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = '#E2E8F0';
                    e.currentTarget.style.boxShadow = '0 2px 6px rgba(11, 46, 111, 0.03)';
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                      <span
                        style={{
                          fontFamily: 'monospace',
                          fontWeight: 800,
                          fontSize: '13px',
                          color: '#0B2E6F',
                          backgroundColor: '#EEF2FF',
                          border: '1px solid #C7D2FE',
                          padding: '3px 8px',
                          borderRadius: '6px',
                        }}
                      >
                        {a.code}
                      </span>

                      <div style={{ display: 'flex', gap: '6px' }}>
                        <span
                          style={{
                            fontSize: '11px',
                            fontWeight: 700,
                            padding: '2px 8px',
                            borderRadius: '12px',
                            backgroundColor:
                              a.status === 'OPEN'
                                ? '#DCFCE7'
                                : a.status === 'READY'
                                ? '#DBEAFE'
                                : a.status === 'CLOSED'
                                ? '#F1F5F9'
                                : '#FEF3C7',
                            color:
                              a.status === 'OPEN'
                                ? '#166534'
                                : a.status === 'READY'
                                ? '#1E40AF'
                                : a.status === 'CLOSED'
                                ? '#475569'
                                : '#92400E',
                          }}
                        >
                          {a.status}
                        </span>
                      </div>
                    </div>

                    <h3
                      style={{
                        fontSize: '16px',
                        fontWeight: 800,
                        color: '#0B2E6F',
                        margin: '0 0 6px 0',
                        letterSpacing: '-0.01em',
                      }}
                    >
                      {a.title}
                    </h3>

                    <p
                      style={{
                        fontSize: '12.5px',
                        color: '#64748B',
                        margin: '0 0 16px 0',
                        lineHeight: '1.45',
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden',
                      }}
                    >
                      {a.description || 'No detailed assessment curriculum description provided.'}
                    </p>

                    {/* Pool & Requirement Box */}
                    <div
                      style={{
                        backgroundColor: '#FAF7F3',
                        border: '1px solid #E2E8F0',
                        borderRadius: '10px',
                        padding: '12px 14px',
                        marginBottom: '16px',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '6px' }}>
                        <span style={{ color: '#64748B', fontWeight: 600 }}>Test Requirement:</span>
                        <span style={{ color: '#0B2E6F', fontWeight: 700 }}>
                          {a.aptitude_count} Aptitude + {a.coding_count} Coding ({a.aptitude_count + a.coding_count} Total)
                        </span>
                      </div>

                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '8px' }}>
                        <span style={{ color: '#64748B', fontWeight: 600 }}>Assigned Pool:</span>
                        <span style={{ color: '#1455B8', fontWeight: 700 }}>
                          {a.pool_questions_count ?? 0} Questions ({a.pool_aptitude_count ?? 0} Apt / {a.pool_coding_count ?? 0} Cod)
                        </span>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '8px', borderTop: '1px dashed #CBD5E1' }}>
                        <span style={{ fontSize: '11.5px', color: '#64748B' }}>Pool Status:</span>
                        {a.pool_sufficient ? (
                          <span
                            style={{
                              fontSize: '11px',
                              fontWeight: 700,
                              padding: '2px 8px',
                              borderRadius: '12px',
                              backgroundColor: '#DCFCE7',
                              color: '#166534',
                            }}
                          >
                            ✓ Sufficient Pool
                          </span>
                        ) : (
                          <span
                            style={{
                              fontSize: '11px',
                              fontWeight: 700,
                              padding: '2px 8px',
                              borderRadius: '12px',
                              backgroundColor: '#FEF3C7',
                              color: '#92400E',
                            }}
                          >
                            ⚠ Needs Questions
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={() => handleSelectAssessment(a)}
                    style={{
                      width: '100%',
                      padding: '10px 16px',
                      backgroundColor: '#1455B8',
                      color: '#FFFFFF',
                      border: 'none',
                      borderRadius: '8px',
                      fontSize: '13px',
                      fontWeight: 700,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '6px',
                      transition: 'background-color 0.15s ease',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#0B2E6F')}
                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = '#1455B8')}
                  >
                    <span>Manage Question Pool</span>
                    <span>→</span>
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        /* ─── LEVEL 2: ASSESSMENT SCOPED QUESTIONS VIEW ─────────────── */
        <div>
          {/* Breadcrumb & Assessment Context Bar */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '18px',
              padding: '12px 18px',
              backgroundColor: '#FFFFFF',
              borderRadius: '12px',
              border: '1px solid #E2E8F0',
              flexWrap: 'wrap',
              gap: '12px',
              boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
              <button
                onClick={handleClearAssessment}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '7px 14px',
                  borderRadius: '8px',
                  border: '1px solid #CBD5E1',
                  backgroundColor: '#F8FAFC',
                  color: '#0B2E6F',
                  fontSize: '13px',
                  fontWeight: 700,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#EEF2FF')}
                onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = '#F8FAFC')}
              >
                <span>← Back to Assessments</span>
              </button>

              <span style={{ color: '#CBD5E1', fontSize: '16px' }}>/</span>

              {selectedAssessment ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                  <span
                    style={{
                      fontFamily: 'monospace',
                      fontWeight: 800,
                      fontSize: '13px',
                      color: '#0B2E6F',
                      backgroundColor: '#EEF2FF',
                      border: '1px solid #C7D2FE',
                      padding: '3px 8px',
                      borderRadius: '6px',
                    }}
                  >
                    {selectedAssessment.code}
                  </span>
                  <span style={{ fontSize: '15px', fontWeight: 800, color: '#0B2E6F' }}>
                    {selectedAssessment.title}
                  </span>
                  <span
                    style={{
                      fontSize: '11px',
                      fontWeight: 700,
                      padding: '2px 8px',
                      borderRadius: '12px',
                      backgroundColor: selectedAssessment.pool_sufficient ? '#DCFCE7' : '#FEF3C7',
                      color: selectedAssessment.pool_sufficient ? '#166534' : '#92400E',
                    }}
                  >
                    {selectedAssessment.pool_sufficient ? '✓ Sufficient Pool' : '⚠ Pool Needs Questions'}
                  </span>
                </div>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '15px', fontWeight: 800, color: '#0B2E6F' }}>
                    Global Question Bank (All Assessments)
                  </span>
                </div>
              )}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ fontSize: '12px', color: '#64748B', fontWeight: 600 }}>Switch Assessment:</span>
                <select
                  value={selectedAssessment?.id || ''}
                  onChange={(e) => {
                    if (!e.target.value) {
                      handleViewAllQuestions();
                    } else {
                      const found = assessments.find((a) => a.id === e.target.value);
                      if (found) handleSelectAssessment(found);
                    }
                  }}
                  style={{
                    padding: '7px 10px',
                    borderRadius: '6px',
                    border: '1px solid #CBD5E1',
                    fontSize: '12.5px',
                    backgroundColor: '#FFFFFF',
                    fontWeight: 600,
                    color: '#1E293B',
                  }}
                >
                  <option value="">-- All Assessments (Global) --</option>
                  {assessments.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.code} — {a.title}
                    </option>
                  ))}
                </select>
              </div>

              <button
                onClick={() => {
                  setImportResult(null);
                  setShowImportModal(true);
                }}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '7px 14px',
                  backgroundColor: '#FFFFFF',
                  border: '1px solid #CBD5E1',
                  borderRadius: '8px',
                  fontSize: '12.5px',
                  fontWeight: 700,
                  color: '#0B2E6F',
                  cursor: 'pointer',
                }}
              >
                <span>Import CSV</span>
              </button>

              <button
                onClick={openCreateModal}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '7px 16px',
                  backgroundColor: '#1455B8',
                  color: '#FFFFFF',
                  border: 'none',
                  borderRadius: '8px',
                  fontSize: '12.5px',
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                <span>+ Add Question</span>
              </button>
            </div>
          </div>

          {/* Assessment Pool Summary Card (if selectedAssessment) */}
          {selectedAssessment && (
            <div
              style={{
                backgroundColor: '#FFFFFF',
                borderRadius: '12px',
                border: '1.5px solid rgba(20, 85, 184, 0.15)',
                padding: '14px 20px',
                marginBottom: '16px',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: '12px',
                background: 'linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%)',
              }}
            >
              <div>
                <div style={{ fontSize: '13px', fontWeight: 800, color: '#0B2E6F', marginBottom: '2px' }}>
                  Question Pool Composition: {selectedAssessment.title}
                </div>
                <div style={{ fontSize: '12px', color: '#64748B' }}>
                  Exam Requirement: <strong>{selectedAssessment.aptitude_count} Aptitude</strong> +{' '}
                  <strong>{selectedAssessment.coding_count} Coding</strong> questions (Total:{' '}
                  <strong>{selectedAssessment.aptitude_count + selectedAssessment.coding_count}</strong>)
                </div>
              </div>

              <div style={{ display: 'flex', gap: '14px', alignItems: 'center' }}>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '11px', color: '#64748B', fontWeight: 600 }}>Available in Pool</div>
                  <div style={{ fontSize: '14px', fontWeight: 800, color: '#1455B8' }}>
                    {questions.filter((q) => q.section_type === 'APTITUDE').length} Aptitude /{' '}
                    {questions.filter((q) => q.section_type === 'CODING').length} Coding ({questions.length} total)
                  </div>
                </div>

                <div
                  style={{
                    padding: '6px 12px',
                    borderRadius: '8px',
                    backgroundColor: selectedAssessment.pool_sufficient ? '#DCFCE7' : '#FEF3C7',
                    border: `1px solid ${selectedAssessment.pool_sufficient ? '#86EFAC' : '#FCD34D'}`,
                    color: selectedAssessment.pool_sufficient ? '#166534' : '#92400E',
                    fontSize: '12px',
                    fontWeight: 700,
                  }}
                >
                  {selectedAssessment.pool_sufficient
                    ? '✓ Pool is Sufficient'
                    : `⚠ Shortage (${Math.max(0, selectedAssessment.aptitude_count - questions.filter((q) => q.section_type === 'APTITUDE').length)} Apt, ${Math.max(0, selectedAssessment.coding_count - questions.filter((q) => q.section_type === 'CODING').length)} Cod)`}
                </div>
              </div>
            </div>
          )}

      {/* ─── FILTER TOOLBAR ────────────────────────────────────────── */}
      <div
        style={{
          backgroundColor: '#FFFFFF',
          borderRadius: '12px',
          border: '1px solid #E2E8F0',
          padding: '12px 18px',
          marginBottom: '16px',
          display: 'flex',
          gap: '12px',
          flexWrap: 'wrap',
          alignItems: 'center',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.02)',
        }}
      >
        <form onSubmit={handleSearchSubmit} style={{ display: 'flex', gap: '8px', flex: 1, minWidth: '240px' }}>
          <div style={{ position: 'relative', width: '100%' }}>
            <svg
              width="15"
              height="15"
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
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search question prompt or category..."
              style={{
                padding: '9px 12px 9px 36px',
                borderRadius: '8px',
                border: '1px solid #CBD5E1',
                fontSize: '13px',
                width: '100%',
                boxSizing: 'border-box',
                outlineColor: '#1455B8',
              }}
            />
          </div>
          <button
            type="submit"
            style={{
              padding: '9px 16px',
              backgroundColor: '#1455B8',
              color: '#FFFFFF',
              border: 'none',
              borderRadius: '8px',
              fontSize: '13px',
              fontWeight: 700,
              cursor: 'pointer',
              boxShadow: '0 1px 3px rgba(20, 85, 184, 0.2)',
            }}
          >
            Filter
          </button>
        </form>

        <select
          value={sectionFilter}
          onChange={(e) => setSectionFilter(e.target.value)}
          style={{
            padding: '9px 12px',
            borderRadius: '8px',
            border: '1px solid #CBD5E1',
            fontSize: '13px',
            backgroundColor: '#FFFFFF',
            fontWeight: 600,
            color: '#1E293B',
            outlineColor: '#1455B8',
          }}
        >
          <option value="">All Sections</option>
          <option value="APTITUDE">Aptitude</option>
          <option value="CODING">Coding Fundamentals</option>
        </select>

        <input
          type="text"
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          placeholder="Topic / Category..."
          style={{
            padding: '9px 12px',
            borderRadius: '8px',
            border: '1px solid #CBD5E1',
            fontSize: '13px',
            width: '160px',
            outlineColor: '#1455B8',
          }}
        />

        <select
          value={difficultyFilter}
          onChange={(e) => setDifficultyFilter(e.target.value)}
          style={{
            padding: '9px 12px',
            borderRadius: '8px',
            border: '1px solid #CBD5E1',
            fontSize: '13px',
            backgroundColor: '#FFFFFF',
            fontWeight: 600,
            color: '#1E293B',
            outlineColor: '#1455B8',
          }}
        >
          <option value="">All Difficulties</option>
          <option value="EASY">Easy</option>
          <option value="MEDIUM">Medium</option>
          <option value="HARD">Hard</option>
        </select>

        <select
          value={activeFilter}
          onChange={(e) => setActiveFilter(e.target.value)}
          style={{
            padding: '9px 12px',
            borderRadius: '8px',
            border: '1px solid #CBD5E1',
            fontSize: '13px',
            backgroundColor: '#FFFFFF',
            fontWeight: 600,
            color: '#1E293B',
            outlineColor: '#1455B8',
          }}
        >
          <option value="">All Statuses</option>
          <option value="true">Active Only</option>
          <option value="false">Inactive Only</option>
        </select>

        <select
          value={assessmentFilter}
          onChange={(e) => setAssessmentFilter(e.target.value)}
          style={{
            padding: '9px 12px',
            borderRadius: '8px',
            border: '1px solid #CBD5E1',
            fontSize: '13px',
            backgroundColor: '#FFFFFF',
            fontWeight: 600,
            color: '#1E293B',
            outlineColor: '#1455B8',
          }}
        >
          <option value="">All Assessments</option>
          {assessments.map((a) => (
            <option key={a.id} value={a.id}>
              {a.code} — {a.title}
            </option>
          ))}
        </select>

        {(sectionFilter || difficultyFilter || activeFilter || categoryFilter || assessmentFilter || search) && (
          <button
            onClick={() => {
              setSectionFilter('');
              setCategoryFilter('');
              setDifficultyFilter('');
              setActiveFilter('');
              setAssessmentFilter('');
              setSearch('');
              loadQuestions();
            }}
            style={{
              padding: '9px 12px',
              backgroundColor: '#F1F5F9',
              border: 'none',
              borderRadius: '8px',
              fontSize: '12px',
              fontWeight: 600,
              color: '#475569',
              cursor: 'pointer',
            }}
          >
            Reset
          </button>
        )}
      </div>

      {/* ─── BULK ACTIONS BAR (DURING SELECTION) ───────────────────── */}
      {selectedIds.length > 0 && (
        <div
          style={{
            backgroundColor: '#FFFDF5',
            border: '1.5px solid #F5B83D',
            borderRadius: '12px',
            padding: '12px 20px',
            marginBottom: '16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            boxShadow: '0 4px 14px rgba(245, 184, 61, 0.15)',
            flexWrap: 'wrap',
            gap: '12px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '8px',
                backgroundColor: '#FFD45C',
                color: '#0B2E6F',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '16px',
                fontWeight: 800,
              }}
            >
              ✓
            </div>
            <div>
              <div style={{ fontSize: '13.5px', fontWeight: 800, color: '#0B2E6F' }}>
                {selectedIds.length} questions selected
              </div>
              <div style={{ fontSize: '11px', color: '#64748B' }}>
                You can apply bulk actions to the selected questions.
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <button
              onClick={openBulkModal}
              disabled={bulkUpdating}
              style={{
                padding: '7px 14px',
                backgroundColor: '#FFFFFF',
                color: '#0B2E6F',
                border: '1px solid #CBD5E1',
                borderRadius: '8px',
                fontSize: '12px',
                fontWeight: 700,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"></path>
                <line x1="7" y1="7" x2="7.01" y2="7"></line>
              </svg>
              <span>Change Category</span>
            </button>

            <button
              onClick={openBulkModal}
              disabled={bulkUpdating}
              style={{
                padding: '7px 14px',
                backgroundColor: '#FFFFFF',
                color: '#0B2E6F',
                border: '1px solid #CBD5E1',
                borderRadius: '8px',
                fontSize: '12px',
                fontWeight: 700,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="20" x2="18" y2="10"></line>
                <line x1="12" y1="20" x2="12" y2="4"></line>
                <line x1="6" y1="20" x2="6" y2="14"></line>
              </svg>
              <span>Change Difficulty</span>
            </button>

            <button
              onClick={() => handleQuickBulkActive(true)}
              disabled={bulkUpdating}
              style={{
                padding: '7px 14px',
                backgroundColor: '#DCFCE7',
                color: '#166534',
                border: '1px solid #86EFAC',
                borderRadius: '8px',
                fontSize: '12px',
                fontWeight: 700,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
              }}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
              <span>Activate</span>
            </button>

            <button
              onClick={() => handleQuickBulkActive(false)}
              disabled={bulkUpdating}
              style={{
                padding: '7px 14px',
                backgroundColor: '#FEE2E2',
                color: '#991B1B',
                border: '1px solid #FECACA',
                borderRadius: '8px',
                fontSize: '12px',
                fontWeight: 700,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
              }}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="8" y1="12" x2="16" y2="12"></line>
              </svg>
              <span>Deactivate</span>
            </button>

            <button
              onClick={() => setSelectedIds([])}
              style={{
                padding: '7px 12px',
                backgroundColor: 'transparent',
                color: '#64748B',
                border: '1px solid #CBD5E1',
                borderRadius: '8px',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Clear Selection
            </button>
          </div>
        </div>
      )}

      {/* ─── QUESTIONS TABLE ───────────────────────────────────────── */}
      <div
        style={{
          backgroundColor: '#FFFFFF',
          borderRadius: '14px',
          border: '1.5px solid rgba(245, 184, 61, 0.25)',
          overflow: 'hidden',
          boxShadow: '0 4px 14px rgba(11, 46, 111, 0.04)',
        }}
      >
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
          <thead>
            <tr style={{ backgroundColor: '#FAF7F3', borderBottom: '1.5px solid #E2E8F0', color: '#475569' }}>
              <th style={{ padding: '12px 14px', width: '40px', textAlign: 'center' }}>
                <input
                  type="checkbox"
                  checked={isCurrentPageAllSelected}
                  ref={(input) => {
                    if (input) input.indeterminate = isCurrentPagePartiallySelected;
                  }}
                  onChange={(e) => handleSelectAllCurrentPage(e.target.checked)}
                  style={{ width: '16px', height: '16px', accentColor: '#1455B8', cursor: 'pointer' }}
                  title="Select all on this page"
                />
              </th>
              <th style={{ padding: '12px 14px', width: '60px' }}>ID ↕</th>
              <th style={{ padding: '12px 14px', width: '100px' }}>Section ↕</th>
              <th style={{ padding: '12px 14px', width: '160px' }}>Category ↕</th>
              <th style={{ padding: '12px 14px' }}>Question Prompt</th>
              <th style={{ padding: '12px 14px', width: '70px', textAlign: 'center' }}>Correct ↕</th>
              <th style={{ padding: '12px 14px', width: '90px', textAlign: 'center' }}>Difficulty ↕</th>
              <th style={{ padding: '12px 14px', width: '80px', textAlign: 'center' }}>Active ↕</th>
              <th style={{ padding: '12px 14px', width: '90px', textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={9} style={{ padding: '36px', textAlign: 'center', color: '#6B7280' }}>
                  Loading questions from bank...
                </td>
              </tr>
            ) : paginatedQuestions.length === 0 ? (
              <tr>
                <td colSpan={9} style={{ padding: '36px', textAlign: 'center', color: '#6B7280' }}>
                  No questions found matching your filter criteria.
                </td>
              </tr>
            ) : (
              paginatedQuestions.map((q) => {
                const isSelected = selectedIds.includes(q.id);

                return (
                  <tr
                    key={q.id}
                    style={{
                      borderBottom: '1px solid #F1F5F9',
                      backgroundColor: isSelected ? 'rgba(20, 85, 184, 0.05)' : 'transparent',
                      transition: 'background-color 0.1s ease',
                    }}
                    onMouseEnter={(e) => {
                      if (!isSelected) e.currentTarget.style.backgroundColor = '#F8FAFC';
                    }}
                    onMouseLeave={(e) => {
                      if (!isSelected) e.currentTarget.style.backgroundColor = 'transparent';
                    }}
                  >
                    <td style={{ padding: '12px 14px', textAlign: 'center' }}>
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => handleToggleSelectRow(q.id)}
                        style={{ width: '16px', height: '16px', accentColor: '#1455B8', cursor: 'pointer' }}
                      />
                    </td>
                    <td style={{ padding: '12px 14px', fontFamily: 'monospace', color: '#64748B', fontWeight: 600 }}>
                      #{q.id}
                    </td>
                    <td style={{ padding: '12px 14px' }}>
                      <span
                        style={{
                          padding: '3px 10px',
                          borderRadius: '9999px',
                          fontSize: '11px',
                          fontWeight: 700,
                          backgroundColor: q.section_type === 'CODING' ? '#ECFDF5' : '#EFF6FF',
                          color: q.section_type === 'CODING' ? '#059669' : '#1455B8',
                          border: `1px solid ${q.section_type === 'CODING' ? '#A7F3D0' : '#BFDBFE'}`,
                        }}
                      >
                        {q.section_type === 'CODING' ? 'Coding' : 'Aptitude'}
                      </span>
                    </td>
                    <td style={{ padding: '12px 14px', fontWeight: 600, color: '#334155' }}>
                      {q.category}
                    </td>
                    <td style={{ padding: '12px 14px', color: '#0F172A' }}>
                      <div style={{ fontWeight: 600, marginBottom: '2px', lineHeight: 1.45 }}>
                        {q.prompt.length > 110 ? `${q.prompt.slice(0, 110)}...` : q.prompt}
                      </div>
                      <div style={{ fontSize: '11px', color: '#64748B' }}>
                        A: {q.option_a.slice(0, 24)} | B: {q.option_b.slice(0, 24)} | C: {q.option_c.slice(0, 24)} | D: {q.option_d.slice(0, 24)}
                      </div>
                      {q.assigned_assessments && q.assigned_assessments.length > 0 && (
                        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginTop: '4px' }}>
                          {q.assigned_assessments.map((ass) => (
                            <span
                              key={ass.id}
                              style={{
                                fontSize: '10px',
                                fontWeight: 700,
                                backgroundColor: '#F5F8FF',
                                color: '#0B2E6F',
                                border: '1px solid #DCE4F2',
                                padding: '1px 6px',
                                borderRadius: '4px',
                              }}
                              title={ass.title}
                            >
                              {ass.code}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td style={{ padding: '12px 14px', textAlign: 'center' }}>
                      <span
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          width: '24px',
                          height: '24px',
                          borderRadius: '6px',
                          backgroundColor: '#DCFCE7',
                          color: '#166534',
                          fontWeight: 800,
                          fontFamily: 'monospace',
                          border: '1px solid #86EFAC',
                        }}
                      >
                        {q.correct_option}
                      </span>
                    </td>
                    <td style={{ padding: '12px 14px', textAlign: 'center' }}>
                      <span
                        style={{
                          padding: '3px 8px',
                          borderRadius: '6px',
                          fontSize: '11px',
                          fontWeight: 700,
                          backgroundColor:
                            q.difficulty === 'EASY'
                              ? '#EFF6FF'
                              : q.difficulty === 'MEDIUM'
                              ? '#FEF3C7'
                              : '#FEE2E2',
                          color:
                            q.difficulty === 'EASY'
                              ? '#1455B8'
                              : q.difficulty === 'MEDIUM'
                              ? '#B45309'
                              : '#DC2626',
                        }}
                      >
                        {q.difficulty}
                      </span>
                    </td>
                    <td style={{ padding: '12px 14px', textAlign: 'center' }}>
                      <button
                        onClick={() => handleToggleActive(q.id)}
                        style={{
                          padding: '3px 10px',
                          borderRadius: '9999px',
                          border: 'none',
                          fontSize: '11px',
                          fontWeight: 700,
                          backgroundColor: q.is_active ? '#DCFCE7' : '#F1F5F9',
                          color: q.is_active ? '#166534' : '#64748B',
                          cursor: 'pointer',
                        }}
                        title="Click to toggle status"
                      >
                        {q.is_active ? 'Active' : 'Inactive'}
                      </button>
                    </td>
                    <td style={{ padding: '12px 14px', textAlign: 'right' }}>
                      <button
                        onClick={() => openEditModal(q)}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          padding: '5px 12px',
                          backgroundColor: '#FFFFFF',
                          border: '1.5px solid #CBD5E1',
                          borderRadius: '8px',
                          color: '#0B2E6F',
                          fontSize: '12px',
                          fontWeight: 700,
                          cursor: 'pointer',
                          transition: 'all 0.15s ease',
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.backgroundColor = '#EFF6FF';
                          e.currentTarget.style.borderColor = '#BFDBFE';
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.backgroundColor = '#FFFFFF';
                          e.currentTarget.style.borderColor = '#CBD5E1';
                        }}
                      >
                        <span>✏️</span>
                        <span>Edit</span>
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>

        {/* ─── PAGINATION FOOTER ─────────────────────────────────────── */}
        <div
          style={{
            padding: '14px 20px',
            backgroundColor: '#FAF7F3',
            borderTop: '1px solid #E2E8F0',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            fontSize: '12.5px',
            color: '#64748B',
          }}
        >
          <div>
            Showing <strong>{totalQuestions > 0 ? startIndex + 1 : 0}</strong> to{' '}
            <strong>{endIndex}</strong> of <strong>{totalQuestions}</strong> questions
          </div>

          <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              style={{
                padding: '5px 10px',
                borderRadius: '6px',
                border: '1px solid #CBD5E1',
                backgroundColor: '#FFFFFF',
                color: currentPage === 1 ? '#94A3B8' : '#0B2E6F',
                cursor: currentPage === 1 ? 'not-allowed' : 'pointer',
                fontSize: '12px',
                fontWeight: 700,
              }}
            >
              &lt;
            </button>

            {Array.from({ length: totalPages }, (_, i) => i + 1)
              .filter((page) => {
                // Show first, last, and window around current
                return (
                  page === 1 ||
                  page === totalPages ||
                  Math.abs(page - currentPage) <= 2
                );
              })
              .map((page, idx, arr) => {
                const prev = arr[idx - 1];
                const showEllipsis = prev && page - prev > 1;

                return (
                  <span key={page} style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                    {showEllipsis && <span style={{ color: '#94A3B8' }}>...</span>}
                    <button
                      onClick={() => setCurrentPage(page)}
                      style={{
                        padding: '5px 10px',
                        borderRadius: '6px',
                        border: page === currentPage ? 'none' : '1px solid #CBD5E1',
                        backgroundColor: page === currentPage ? '#0B2E6F' : '#FFFFFF',
                        color: page === currentPage ? '#FFFFFF' : '#475569',
                        cursor: 'pointer',
                        fontSize: '12px',
                        fontWeight: page === currentPage ? 800 : 600,
                      }}
                    >
                      {page}
                    </button>
                  </span>
                );
              })}

            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages || totalPages === 0}
              style={{
                padding: '5px 10px',
                borderRadius: '6px',
                border: '1px solid #CBD5E1',
                backgroundColor: '#FFFFFF',
                color: currentPage === totalPages ? '#94A3B8' : '#0B2E6F',
                cursor: currentPage === totalPages ? 'not-allowed' : 'pointer',
                fontSize: '12px',
                fontWeight: 700,
              }}
            >
              &gt;
            </button>
          </div>
        </div>
      </div>
    </div>
  )}

      {/* ─── DEDICATED SPACIOUS QUESTION EDITOR MODAL ─────────────── */}
      <AdminQuestionEditorModal
        isOpen={showEditorModal}
        question={editingQuestion}
        assessments={assessments}
        defaultAssessmentId={selectedAssessment?.id || assessmentFilter || ''}
        onClose={() => {
          setShowEditorModal(false);
          setEditingQuestion(null);
        }}
        onSave={handleSaveQuestion}
        saving={savingQuestion}
      />

      {/* ─── BULK EDIT PROPERTIES MODAL ────────────────────────────── */}
      {showBulkModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(11, 46, 111, 0.5)',
            backdropFilter: 'blur(3px)',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            zIndex: 1000,
            padding: '20px',
          }}
        >
          <div
            style={{
              maxWidth: '560px',
              width: '100%',
              backgroundColor: '#FFFFFF',
              borderRadius: '16px',
              padding: '28px',
              boxShadow: '0 20px 40px -10px rgba(11, 46, 111, 0.25)',
              border: '1.5px solid rgba(245, 184, 61, 0.4)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div>
                <h3 style={{ fontSize: '18px', fontWeight: 800, color: '#0B2E6F', margin: '0 0 2px 0' }}>
                  Bulk Edit {selectedIds.length} Question(s)
                </h3>
                <p style={{ fontSize: '12px', color: '#64748B', margin: 0 }}>
                  Select which properties to update. Only checked fields will be modified.
                </p>
              </div>
              <button
                onClick={() => setShowBulkModal(false)}
                style={{ background: 'none', border: 'none', fontSize: '20px', color: '#94A3B8', cursor: 'pointer' }}
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleBulkSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {/* Field 1: Section Type */}
              <div
                style={{
                  padding: '12px 14px',
                  borderRadius: '10px',
                  border: `1.5px solid ${bulkFields.section_type ? '#1455B8' : '#E2E8F0'}`,
                  backgroundColor: bulkFields.section_type ? 'rgba(20, 85, 184, 0.03)' : '#FAF7F3',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', fontWeight: 700, color: '#0B2E6F', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={bulkFields.section_type}
                      onChange={(e) => setBulkFields({ ...bulkFields, section_type: e.target.checked })}
                      style={{ width: '16px', height: '16px', accentColor: '#1455B8' }}
                    />
                    <span>Update Section Type</span>
                  </label>
                </div>
                <select
                  disabled={!bulkFields.section_type}
                  value={bulkValues.section_type}
                  onChange={(e) => setBulkValues({ ...bulkValues, section_type: e.target.value as any })}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: '6px',
                    border: '1px solid #CBD5E1',
                    fontSize: '13px',
                    backgroundColor: bulkFields.section_type ? '#FFFFFF' : '#F1F5F9',
                  }}
                >
                  <option value="APTITUDE">Aptitude</option>
                  <option value="CODING">Coding Fundamentals</option>
                </select>
              </div>

              {/* Field 2: Category */}
              <div
                style={{
                  padding: '12px 14px',
                  borderRadius: '10px',
                  border: `1.5px solid ${bulkFields.category ? '#1455B8' : '#E2E8F0'}`,
                  backgroundColor: bulkFields.category ? 'rgba(20, 85, 184, 0.03)' : '#FAF7F3',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', fontWeight: 700, color: '#0B2E6F', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={bulkFields.category}
                      onChange={(e) => setBulkFields({ ...bulkFields, category: e.target.checked })}
                      style={{ width: '16px', height: '16px', accentColor: '#1455B8' }}
                    />
                    <span>Update Category / Topic</span>
                  </label>
                </div>
                <input
                  type="text"
                  disabled={!bulkFields.category}
                  value={bulkValues.category}
                  onChange={(e) => setBulkValues({ ...bulkValues, category: e.target.value })}
                  placeholder="e.g. Data Structures, Verbal Reasoning"
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: '6px',
                    border: '1px solid #CBD5E1',
                    fontSize: '13px',
                    boxSizing: 'border-box',
                    backgroundColor: bulkFields.category ? '#FFFFFF' : '#F1F5F9',
                  }}
                />
              </div>

              {/* Field 3: Difficulty */}
              <div
                style={{
                  padding: '12px 14px',
                  borderRadius: '10px',
                  border: `1.5px solid ${bulkFields.difficulty ? '#1455B8' : '#E2E8F0'}`,
                  backgroundColor: bulkFields.difficulty ? 'rgba(20, 85, 184, 0.03)' : '#FAF7F3',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', fontWeight: 700, color: '#0B2E6F', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={bulkFields.difficulty}
                      onChange={(e) => setBulkFields({ ...bulkFields, difficulty: e.target.checked })}
                      style={{ width: '16px', height: '16px', accentColor: '#1455B8' }}
                    />
                    <span>Update Difficulty Level</span>
                  </label>
                </div>
                <select
                  disabled={!bulkFields.difficulty}
                  value={bulkValues.difficulty}
                  onChange={(e) => setBulkValues({ ...bulkValues, difficulty: e.target.value as any })}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: '6px',
                    border: '1px solid #CBD5E1',
                    fontSize: '13px',
                    backgroundColor: bulkFields.difficulty ? '#FFFFFF' : '#F1F5F9',
                  }}
                >
                  <option value="EASY">Easy</option>
                  <option value="MEDIUM">Medium</option>
                  <option value="HARD">Hard</option>
                </select>
              </div>

              {/* Field 4: Status */}
              <div
                style={{
                  padding: '12px 14px',
                  borderRadius: '10px',
                  border: `1.5px solid ${bulkFields.is_active ? '#1455B8' : '#E2E8F0'}`,
                  backgroundColor: bulkFields.is_active ? 'rgba(20, 85, 184, 0.03)' : '#FAF7F3',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', fontWeight: 700, color: '#0B2E6F', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={bulkFields.is_active}
                      onChange={(e) => setBulkFields({ ...bulkFields, is_active: e.target.checked })}
                      style={{ width: '16px', height: '16px', accentColor: '#1455B8' }}
                    />
                    <span>Update Active Status</span>
                  </label>
                </div>
                <select
                  disabled={!bulkFields.is_active}
                  value={bulkValues.is_active ? 'true' : 'false'}
                  onChange={(e) => setBulkValues({ ...bulkValues, is_active: e.target.value === 'true' })}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: '6px',
                    border: '1px solid #CBD5E1',
                    fontSize: '13px',
                    backgroundColor: bulkFields.is_active ? '#FFFFFF' : '#F1F5F9',
                  }}
                >
                  <option value="true">Active (Eligible for tests)</option>
                  <option value="false">Inactive (Excluded from tests)</option>
                </select>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '12px' }}>
                <button
                  type="button"
                  onClick={() => setShowBulkModal(false)}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '8px',
                    border: '1.5px solid #CBD5E1',
                    backgroundColor: '#FFFFFF',
                    color: '#475569',
                    fontSize: '13px',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={bulkUpdating}
                  style={{
                    padding: '8px 22px',
                    borderRadius: '8px',
                    border: 'none',
                    backgroundColor: '#0B2E6F',
                    color: '#FFFFFF',
                    fontSize: '13px',
                    fontWeight: 700,
                    cursor: 'pointer',
                    opacity: bulkUpdating ? 0.7 : 1,
                  }}
                >
                  {bulkUpdating ? 'Applying Updates...' : `Apply to ${selectedIds.length} Question(s)`}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─── CSV IMPORT MODAL ──────────────────────────────────────── */}
      {showImportModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(11, 46, 111, 0.45)',
            backdropFilter: 'blur(3px)',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            zIndex: 100,
            padding: '20px',
          }}
        >
          <div
            style={{
              maxWidth: '540px',
              width: '100%',
              backgroundColor: '#FFFFFF',
              borderRadius: '16px',
              padding: '28px',
              boxShadow: '0 20px 35px -10px rgba(11, 46, 111, 0.15)',
              border: '1.5px solid rgba(245, 184, 61, 0.3)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ fontSize: '18px', fontWeight: 800, color: '#0B2E6F', margin: 0 }}>
                Bulk CSV Question Import
              </h3>
              <button
                onClick={() => setShowImportModal(false)}
                style={{ background: 'none', border: 'none', fontSize: '18px', color: '#94A3B8', cursor: 'pointer' }}
              >
                ✕
              </button>
            </div>

            <p style={{ fontSize: '13px', color: '#64748B', lineHeight: 1.5, margin: '0 0 16px 0' }}>
              Upload a valid CSV file with columns:{' '}
              <code>prompt, section_type, category, difficulty, option_a, option_b, option_c, option_d, correct_option, explanation</code>.
            </p>

            <form onSubmit={handleImportSubmit}>
              {/* Target Assessment Selector */}
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#0B2E6F', marginBottom: '6px' }}>
                  Target Assessment *
                </label>
                <select
                  value={importAssessmentId}
                  onChange={(e) => setImportAssessmentId(e.target.value)}
                  required
                  style={{
                    width: '100%',
                    padding: '9px 12px',
                    borderRadius: '8px',
                    border: !importAssessmentId ? '1.5px solid #DC2626' : '1px solid #CBD5E1',
                    fontSize: '13px',
                    color: '#0F172A',
                    backgroundColor: '#FFFFFF',
                    boxSizing: 'border-box',
                    outlineColor: '#1455B8',
                  }}
                >
                  <option value="">-- Choose Target Assessment for Question Pool --</option>
                  {assessments.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.title} ({a.code}) — Status: {a.status}
                    </option>
                  ))}
                </select>
                {!importAssessmentId && (
                  <span style={{ color: '#DC2626', fontSize: '11px', marginTop: '4px', display: 'block' }}>
                    * Selecting a target assessment is required before importing questions.
                  </span>
                )}
              </div>

              {/* Assessment Context Preview */}
              {(() => {
                const target = assessments.find((a) => a.id === importAssessmentId);
                if (!target) return null;
                return (
                  <div
                    style={{
                      backgroundColor: '#EFF6FF',
                      border: '1px solid #BFDBFE',
                      borderRadius: '8px',
                      padding: '10px 14px',
                      marginBottom: '16px',
                      fontSize: '12px',
                      color: '#1E40AF',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      flexWrap: 'wrap',
                      gap: '8px',
                    }}
                  >
                    <div>
                      <strong>Pool Context:</strong> {target.title} ({target.code})
                      <div style={{ color: '#3B82F6', marginTop: '2px' }}>
                        Configured: {target.aptitude_count} Aptitude + {target.coding_count} Coding ({target.total_marks} Marks)
                      </div>
                    </div>
                    <span
                      style={{
                        backgroundColor: '#DBEAFE',
                        color: '#1E40AF',
                        padding: '3px 8px',
                        borderRadius: '4px',
                        fontWeight: 700,
                        fontSize: '11px',
                      }}
                    >
                      {target.pool_questions_count ?? 0} Questions In Pool
                    </span>
                  </div>
                );
              })()}

              <div
                style={{
                  border: '2px dashed #CBD5E1',
                  borderRadius: '10px',
                  padding: '24px',
                  textAlign: 'center',
                  marginBottom: '16px',
                  backgroundColor: '#FAF7F3',
                }}
              >
                <input
                  type="file"
                  accept=".csv"
                  onChange={(e) => setImportFile(e.target.files?.[0] || null)}
                  style={{ display: 'block', margin: '0 auto' }}
                />
              </div>

              {importResult && (
                <div
                  style={{
                    backgroundColor: importResult.error_count > 0 ? '#FEF2F2' : '#F0FDF4',
                    border: `1px solid ${importResult.error_count > 0 ? '#FECACA' : '#BBF7D0'}`,
                    padding: '12px',
                    borderRadius: '8px',
                    marginBottom: '16px',
                    fontSize: '13px',
                  }}
                >
                  <strong style={{ color: importResult.error_count > 0 ? '#DC2626' : '#16A34A' }}>
                    Import Complete: {importResult.success_count} questions imported successfully.
                  </strong>
                  {importResult.error_count > 0 && (
                    <div style={{ marginTop: '8px', color: '#991B1B' }}>
                      Errors ({importResult.error_count}):
                      <ul style={{ margin: '4px 0 0 16px', padding: 0, fontSize: '12px' }}>
                        {importResult.errors.map((err, i) => (
                          <li key={i}>{err}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="button"
                  onClick={() => setShowImportModal(false)}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '8px',
                    border: '1.5px solid #CBD5E1',
                    backgroundColor: '#FFFFFF',
                    color: '#475569',
                    fontSize: '13px',
                    cursor: 'pointer',
                  }}
                >
                  Close
                </button>
                <button
                  type="submit"
                  disabled={importing || !importFile || !importAssessmentId}
                  style={{
                    padding: '8px 20px',
                    borderRadius: '8px',
                    border: 'none',
                    backgroundColor: importing || !importFile || !importAssessmentId ? '#94A3B8' : '#1455B8',
                    color: '#FFFFFF',
                    fontSize: '13px',
                    fontWeight: 700,
                    cursor: importing ? 'not-allowed' : 'pointer',
                  }}
                >
                  {importing ? 'Importing CSV...' : 'Start Import'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
