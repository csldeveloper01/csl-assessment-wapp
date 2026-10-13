import { useState } from 'react';
import type {
  ActivityOptions,
  StaffActivityCreatePayload,
  SkillMappingPayload,
  SectionPayload,
} from '../../types/staffActivity';

interface CreateActivityModalProps {
  options: ActivityOptions;
  onClose: () => void;
  onSubmit: (data: StaffActivityCreatePayload) => Promise<void>;
}

export function CreateActivityModal({ options, onClose, onSubmit }: CreateActivityModalProps) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [type, setType] = useState<'ASSESSMENT' | 'TASK' | 'PROJECT'>('TASK');
  const [courseId, setCourseId] = useState<number | ''>(
    options.courses[0] ? options.courses[0].id : ''
  );
  const [batchId, setBatchId] = useState<number | ''>('');
  const [maxMarks, setMaxMarks] = useState<number>(100);
  const [deadline, setDeadline] = useState('');
  const [statusVal, setStatusVal] = useState<'DRAFT' | 'ACTIVE'>('DRAFT');

  // For TASK and PROJECT: selected skills and their subskills
  const [selectedSkills, setSelectedSkills] = useState<{ [skillId: number]: number[] }>({});

  // For ASSESSMENT: dynamic sections and questions
  const [sections, setSections] = useState<SectionPayload[]>([
    {
      title: 'Section 1',
      description: '',
      questions: [{ question_text: '', marks: 10, skill_id: null, subskill_id: null }],
    },
  ]);

  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const selectedCourse = options.courses.find((c) => c.id === Number(courseId));
  const availableBatches = selectedCourse ? selectedCourse.batches : [];

  const handleTypeChange = (newType: 'ASSESSMENT' | 'TASK' | 'PROJECT') => {
    setType(newType);
    if (newType === 'ASSESSMENT') {
      if (maxMarks > 200 || maxMarks === 0) setMaxMarks(200);
    } else {
      if (maxMarks > 100 || maxMarks === 0) setMaxMarks(100);
    }
  };

  const toggleSkill = (skillId: number) => {
    setSelectedSkills((prev) => {
      const next = { ...prev };
      if (next[skillId] !== undefined) {
        delete next[skillId];
      } else {
        next[skillId] = [];
      }
      return next;
    });
  };

  const toggleSubSkill = (skillId: number, subSkillId: number) => {
    setSelectedSkills((prev) => {
      const currentSub = prev[skillId] || [];
      const nextSub = currentSub.includes(subSkillId)
        ? currentSub.filter((id) => id !== subSkillId)
        : [...currentSub, subSkillId];
      return {
        ...prev,
        [skillId]: nextSub,
      };
    });
  };

  // Section / Question helpers
  const addSection = () => {
    setSections((prev) => [
      ...prev,
      {
        title: `Section ${prev.length + 1}`,
        description: '',
        questions: [{ question_text: '', marks: 10, skill_id: null, subskill_id: null }],
      },
    ]);
  };

  const removeSection = (index: number) => {
    setSections((prev) => prev.filter((_, i) => i !== index));
  };

  const updateSectionTitle = (index: number, val: string) => {
    setSections((prev) => {
      const copy = [...prev];
      copy[index].title = val;
      return copy;
    });
  };

  const addQuestion = (secIndex: number) => {
    setSections((prev) => {
      const copy = [...prev];
      copy[secIndex].questions.push({
        question_text: '',
        marks: 10,
        skill_id: null,
        subskill_id: null,
      });
      return copy;
    });
  };

  const removeQuestion = (secIndex: number, qIndex: number) => {
    setSections((prev) => {
      const copy = [...prev];
      copy[secIndex].questions = copy[secIndex].questions.filter((_, i) => i !== qIndex);
      return copy;
    });
  };

  const updateQuestion = (
    secIndex: number,
    qIndex: number,
    field: 'question_text' | 'marks' | 'skill_id' | 'subskill_id',
    val: any
  ) => {
    setSections((prev) => {
      const copy = [...prev];
      const q = { ...copy[secIndex].questions[qIndex] };
      if (field === 'skill_id') {
        q.skill_id = val ? Number(val) : null;
        q.subskill_id = null;
      } else if (field === 'subskill_id') {
        q.subskill_id = val ? Number(val) : null;
      } else if (field === 'marks') {
        q.marks = Number(val);
      } else {
        q[field] = val;
      }
      copy[secIndex].questions[qIndex] = q;
      return copy;
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    if (!title.trim()) {
      setErrorMsg('Title is required.');
      return;
    }
    if (!courseId) {
      setErrorMsg('Target Course is required.');
      return;
    }
    if (statusVal === 'ACTIVE' && !deadline) {
      setErrorMsg('A deadline is required to publish an activity as Active.');
      return;
    }

    const payload: StaffActivityCreatePayload = {
      title: title.trim(),
      description: description.trim(),
      type,
      course_id: Number(courseId),
      batch_id: batchId ? Number(batchId) : null,
      max_marks: Number(maxMarks),
      deadline: deadline ? new Date(deadline).toISOString() : null,
      status: statusVal,
    };

    if (type === 'TASK' || type === 'PROJECT') {
      const skillList: SkillMappingPayload[] = Object.entries(selectedSkills).map(
        ([sId, subIds]) => ({
          skill_id: Number(sId),
          subskill_ids: subIds,
        })
      );
      if (skillList.length === 0) {
        setErrorMsg('Please select at least one skill covered by this activity.');
        return;
      }
      payload.skills = skillList;
    } else if (type === 'ASSESSMENT') {
      if (sections.length === 0) {
        setErrorMsg('Assessments must have at least one section.');
        return;
      }
      for (const sec of sections) {
        if (!sec.title.trim()) {
          setErrorMsg('All sections must have a title.');
          return;
        }
        if (!sec.questions || sec.questions.length === 0) {
          setErrorMsg(`Section "${sec.title}" has no questions.`);
          return;
        }
        for (const q of sec.questions) {
          if (!q.question_text.trim()) {
            setErrorMsg(`All questions in section "${sec.title}" must have text.`);
            return;
          }
        }
      }
      payload.sections = sections;
    }

    try {
      setSubmitting(true);
      await onSubmit(payload);
    } catch (err: any) {
      const msg =
        err?.response?.data?.detail ||
        err?.response?.data?.message ||
        JSON.stringify(err?.response?.data) ||
        'Failed to create activity.';
      setErrorMsg(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={modalOverlayStyle}>
      <div style={modalContentStyle}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h2 style={{ margin: 0 }}>Create New Activity</h2>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', fontSize: 20, cursor: 'pointer' }}
          >
            ✕
          </button>
        </div>

        {errorMsg && (
          <div style={{ padding: 12, backgroundColor: '#fee2e2', color: '#b91c1c', borderRadius: 6, marginBottom: 16 }}>
            {errorMsg}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {/* Title */}
          <div>
            <label style={labelStyle}>Activity Title *</label>
            <input
              type="text"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g., Module 2 Practical Assessment"
              style={inputStyle}
            />
          </div>

          {/* Description */}
          <div>
            <label style={labelStyle}>Description</label>
            <textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Detailed instructions or objectives..."
              style={inputStyle}
            />
          </div>

          {/* Type & Status Row */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label style={labelStyle}>Activity Type *</label>
              <select
                value={type}
                onChange={(e) => handleTypeChange(e.target.value as any)}
                style={inputStyle}
              >
                <option value="TASK">Task (Max 100 Marks)</option>
                <option value="PROJECT">Project (Max 100 Marks)</option>
                <option value="ASSESSMENT">Assessment (Max 200 Marks)</option>
              </select>
            </div>
            <div>
              <label style={labelStyle}>Initial Lifecycle Status *</label>
              <select
                value={statusVal}
                onChange={(e) => setStatusVal(e.target.value as any)}
                style={inputStyle}
              >
                <option value="DRAFT">Draft (Hidden from students)</option>
                <option value="ACTIVE">Active (Published to students)</option>
              </select>
            </div>
          </div>

          {/* Course & Batch Row */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label style={labelStyle}>Target Course *</label>
              <select
                value={courseId}
                onChange={(e) => {
                  setCourseId(Number(e.target.value));
                  setBatchId('');
                }}
                style={inputStyle}
                required
              >
                <option value="">-- Select Course --</option>
                {options.courses.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.code})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label style={labelStyle}>Target Batch (Optional)</label>
              <select
                value={batchId}
                onChange={(e) => setBatchId(e.target.value ? Number(e.target.value) : '')}
                style={inputStyle}
                disabled={!courseId}
              >
                <option value="">Course-wide (All Batches)</option>
                {availableBatches.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Max Marks & Deadline */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label style={labelStyle}>Max Marks (Max {type === 'ASSESSMENT' ? 200 : 100}) *</label>
              <input
                type="number"
                min={1}
                max={type === 'ASSESSMENT' ? 200 : 100}
                value={maxMarks}
                onChange={(e) => setMaxMarks(Number(e.target.value))}
                style={inputStyle}
                required
              />
            </div>
            <div>
              <label style={labelStyle}>Deadline {statusVal === 'ACTIVE' && '*'}</label>
              <input
                type="datetime-local"
                value={deadline}
                onChange={(e) => setDeadline(e.target.value)}
                style={inputStyle}
                required={statusVal === 'ACTIVE'}
              />
            </div>
          </div>

          {/* SKILL / SUBSKILL SECTION (For Task & Project) */}
          {(type === 'TASK' || type === 'PROJECT') && (
            <div style={{ marginTop: 10 }}>
              <label style={labelStyle}>Target Skills & Subskills *</label>
              <div style={{ maxHeight: 200, overflowY: 'auto', border: '1px solid #d1d5db', borderRadius: 6, padding: 8 }}>
                {options.skills.length === 0 && (
                  <div style={{ color: '#6b7280', fontSize: 13 }}>No skills available in system.</div>
                )}
                {options.skills.map((skill) => {
                  const isChecked = selectedSkills[skill.id] !== undefined;
                  const currentSubIds = selectedSkills[skill.id] || [];
                  return (
                    <div key={skill.id} style={{ marginBottom: 10, paddingBottom: 6, borderBottom: '1px solid #f3f4f6' }}>
                      <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 600, cursor: 'pointer' }}>
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => toggleSkill(skill.id)}
                        />
                        {skill.name}
                      </label>
                      {isChecked && skill.subskills && skill.subskills.length > 0 && (
                        <div style={{ paddingLeft: 24, marginTop: 4, display: 'flex', flexWrap: 'wrap', gap: 10 }}>
                          {skill.subskills.map((sub) => (
                            <label key={sub.id} style={{ fontSize: 13, display: 'flex', alignItems: 'center', gap: 4 }}>
                              <input
                                type="checkbox"
                                checked={currentSubIds.includes(sub.id)}
                                onChange={() => toggleSubSkill(skill.id, sub.id)}
                              />
                              {sub.name}
                            </label>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* SECTIONS & QUESTIONS BUILDER (For Assessment) */}
          {type === 'ASSESSMENT' && (
            <div style={{ marginTop: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <label style={labelStyle}>Assessment Sections & Questions</label>
                <button
                  type="button"
                  onClick={addSection}
                  style={{ fontSize: 12, padding: '4px 8px', background: '#e0e7ff', color: '#3730a3', border: 'none', borderRadius: 4, cursor: 'pointer' }}
                >
                  + Add Section
                </button>
              </div>

              <div style={{ maxHeight: 260, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 12 }}>
                {sections.map((sec, secIdx) => (
                  <div key={secIdx} style={{ border: '1px solid #e5e7eb', borderRadius: 6, padding: 10, background: '#fafafa' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <input
                        type="text"
                        value={sec.title}
                        onChange={(e) => updateSectionTitle(secIdx, e.target.value)}
                        placeholder="Section Title"
                        style={{ ...inputStyle, width: '70%', fontWeight: 600 }}
                      />
                      {sections.length > 1 && (
                        <button
                          type="button"
                          onClick={() => removeSection(secIdx)}
                          style={{ fontSize: 12, color: '#ef4444', background: 'none', border: 'none', cursor: 'pointer' }}
                        >
                          Remove Section
                        </button>
                      )}
                    </div>

                    <div style={{ paddingLeft: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
                      {sec.questions.map((q, qIdx) => (
                        <div key={qIdx} style={{ display: 'grid', gridTemplateColumns: '2fr 70px 1.5fr 1fr 30px', gap: 6, alignItems: 'center' }}>
                          <input
                            type="text"
                            placeholder="Question text..."
                            value={q.question_text}
                            onChange={(e) => updateQuestion(secIdx, qIdx, 'question_text', e.target.value)}
                            style={inputStyle}
                            required
                          />
                          <input
                            type="number"
                            placeholder="Marks"
                            value={q.marks}
                            onChange={(e) => updateQuestion(secIdx, qIdx, 'marks', e.target.value)}
                            style={inputStyle}
                            min={1}
                          />
                          {/* Skill Selector */}
                          <select
                            value={q.skill_id || ''}
                            onChange={(e) => updateQuestion(secIdx, qIdx, 'skill_id', e.target.value)}
                            style={inputStyle}
                          >
                            <option value="">Skill (Optional)</option>
                            {options.skills.map((s) => (
                              <option key={s.id} value={s.id}>
                                {s.name}
                              </option>
                            ))}
                          </select>
                          {/* Subskill Selector */}
                          <select
                            value={q.subskill_id || ''}
                            onChange={(e) => updateQuestion(secIdx, qIdx, 'subskill_id', e.target.value)}
                            style={inputStyle}
                            disabled={!q.skill_id}
                          >
                            <option value="">SubSkill</option>
                            {q.skill_id &&
                              options.skills
                                .find((s) => s.id === q.skill_id)
                                ?.subskills.map((sub) => (
                                  <option key={sub.id} value={sub.id}>
                                    {sub.name}
                                  </option>
                                ))}
                          </select>
                          {sec.questions.length > 1 && (
                            <button
                              type="button"
                              onClick={() => removeQuestion(secIdx, qIdx)}
                              style={{ color: '#ef4444', background: 'none', border: 'none', cursor: 'pointer', fontWeight: 'bold' }}
                            >
                              ✕
                            </button>
                          )}
                        </div>
                      ))}
                      <button
                        type="button"
                        onClick={() => addQuestion(secIdx)}
                        style={{ alignSelf: 'flex-start', fontSize: 11, padding: '3px 8px', background: '#f3f4f6', border: '1px solid #d1d5db', borderRadius: 4, cursor: 'pointer' }}
                      >
                        + Add Question
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Action Buttons */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 16 }}>
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              style={{ padding: '8px 16px', background: '#f3f4f6', border: '1px solid #d1d5db', borderRadius: 6, cursor: 'pointer' }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              style={{ padding: '8px 18px', background: '#2563eb', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontWeight: 600 }}
            >
              {submitting ? 'Creating...' : 'Create Activity'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

const modalOverlayStyle: React.CSSProperties = {
  position: 'fixed',
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  backgroundColor: 'rgba(0,0,0,0.5)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 1000,
  padding: 16,
};

const modalContentStyle: React.CSSProperties = {
  backgroundColor: '#ffffff',
  borderRadius: 8,
  width: '100%',
  maxWidth: 720,
  maxHeight: '90vh',
  overflowY: 'auto',
  padding: 24,
  boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
};

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: 13,
  fontWeight: 600,
  marginBottom: 4,
  color: '#374151',
};

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '7px 10px',
  borderRadius: 6,
  border: '1px solid #d1d5db',
  fontSize: 14,
  boxSizing: 'border-box',
};
