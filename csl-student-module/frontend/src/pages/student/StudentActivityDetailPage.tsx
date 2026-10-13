import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getStudentActivityDetail } from '../../api/student';
import type { StudentActivityDetail } from '../../types/student';

/**
 * Student Activity Detail Page:
 * Shows full instructions, due date, max marks, course, and covered skills.
 */
export function StudentActivityDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [activity, setActivity] = useState<StudentActivityDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const loadDetail = () => {
    if (!id) return;
    setLoading(true);
    setError(false);
    getStudentActivityDetail(id)
      .then((res) => {
        setActivity(res);
      })
      .catch(() => {
        setError(true);
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    loadDetail();
  }, [id]);

  if (loading) {
    return <p>Loading activity details...</p>;
  }

  if (error || !activity) {
    return (
      <div>
        <p>Activity not found or not accessible.</p>
        <div style={{ marginTop: '8px', display: 'flex', gap: '12px', alignItems: 'center' }}>
          <button
            type="button"
            onClick={loadDetail}
            style={{ padding: '6px 12px' }}
          >
            Try again
          </button>
          <Link to="/student/activities" style={{ color: '#2563eb', textDecoration: 'underline' }}>
            Back to Activities
          </Link>
        </div>
      </div>
    );
  }

  const formatDueDate = (dateStr: string | null) => {
    if (!dateStr) return 'No deadline specified';
    const date = new Date(dateStr);
    return date.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatType = (typeStr: string) => {
    switch (typeStr) {
      case 'TASK':
        return 'Task';
      case 'ASSESSMENT':
        return 'Assessment';
      case 'PROJECT':
        return 'Project';
      default:
        return typeStr;
    }
  };

  const formatStatus = (status: string) => {
    switch (status) {
      case 'PENDING':
        return 'Pending';
      case 'SUBMITTED':
        return 'Submitted';
      case 'EVALUATED':
        return 'Evaluated';
      case 'DRAFT':
        return 'Draft';
      case 'WITHDRAWN':
        return 'Withdrawn';
      default:
        return status;
    }
  };

  return (
    <div style={{ maxWidth: '800px' }}>
      <div style={{ marginBottom: '16px' }}>
        <Link
          to="/student/activities"
          style={{ color: '#2563eb', textDecoration: 'none', fontSize: '0.9rem', fontWeight: 500 }}
        >
          ← Back to Activities
        </Link>
      </div>

      <div
        style={{
          backgroundColor: '#ffffff',
          border: '1px solid #e5e7eb',
          borderRadius: '8px',
          padding: '24px',
          marginBottom: '20px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h2 style={{ margin: '0 0 8px 0', fontSize: '1.4rem' }}>{activity.title}</h2>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '12px' }}>
              <span
                style={{
                  backgroundColor: '#eff6ff',
                  color: '#1d4ed8',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  padding: '2px 8px',
                  borderRadius: '4px',
                }}
              >
                {formatType(activity.type)}
              </span>
              <span style={{ fontSize: '0.85rem', color: '#6b7280' }}>
                Course: {activity.course} ({activity.course_code})
              </span>
              {activity.batch && (
                <span style={{ fontSize: '0.85rem', color: '#6b7280' }}>
                  • Batch: {activity.batch}
                </span>
              )}
            </div>
          </div>
          <span
            style={{
              fontSize: '0.9rem',
              fontWeight: 500,
              color: activity.status === 'PENDING' ? '#d97706' : '#16a34a',
            }}
          >
            Status: {formatStatus(activity.status)}
          </span>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '12px',
            padding: '12px 16px',
            backgroundColor: '#f9fafb',
            borderRadius: '6px',
            marginBottom: '20px',
            fontSize: '0.9rem',
          }}
        >
          <div>
            <span style={{ color: '#6b7280', display: 'block', fontSize: '0.8rem' }}>Due Date</span>
            <span style={{ fontWeight: 500 }}>{formatDueDate(activity.due_date)}</span>
          </div>
          <div>
            <span style={{ color: '#6b7280', display: 'block', fontSize: '0.8rem' }}>Maximum Marks</span>
            <span style={{ fontWeight: 500 }}>{activity.max_marks}</span>
          </div>
        </div>

        {/* Description / Instructions */}
        <div style={{ marginBottom: '24px' }}>
          <h3 style={{ fontSize: '1.05rem', margin: '0 0 8px 0' }}>Instructions & Description</h3>
          {activity.description ? (
            <p style={{ margin: 0, color: '#374151', lineHeight: '1.5', whiteSpace: 'pre-wrap' }}>
              {activity.description}
            </p>
          ) : (
            <p style={{ margin: 0, color: '#9ca3af', fontStyle: 'italic' }}>
              No detailed instructions provided.
            </p>
          )}
        </div>

        {/* Skills Covered */}
        <div>
          <h3 style={{ fontSize: '1.05rem', margin: '0 0 12px 0' }}>Skills Covered</h3>
          {activity.skills_covered && activity.skills_covered.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {activity.skills_covered.map((sk) => (
                <div
                  key={sk.id}
                  style={{
                    border: '1px solid #f3f4f6',
                    borderRadius: '6px',
                    padding: '12px',
                    backgroundColor: '#fafafa',
                  }}
                >
                  <strong style={{ fontSize: '0.95rem' }}>{sk.name}</strong>
                  {sk.subskills && sk.subskills.length > 0 ? (
                    <ul style={{ margin: '6px 0 0 0', paddingLeft: '20px', color: '#4b5563', fontSize: '0.85rem' }}>
                      {sk.subskills.map((sub) => (
                        <li key={sub.id}>{sub.name}</li>
                      ))}
                    </ul>
                  ) : (
                    <p style={{ margin: '4px 0 0 0', color: '#6b7280', fontSize: '0.85rem' }}>(Entire skill)</p>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <p style={{ margin: 0, color: '#6b7280', fontSize: '0.9rem' }}>
              No explicit skill mappings recorded for this activity.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
