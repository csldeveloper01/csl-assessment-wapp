import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getStudentActivities } from '../../api/student';
import type { StudentActivitySummary } from '../../types/student';

/**
 * Student Activities Page:
 * Displays assigned activities (Tasks, Assessments, Projects) for the student's Course & Batch.
 */
export function StudentActivitiesPage() {
  const [activities, setActivities] = useState<StudentActivitySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const loadActivities = () => {
    setLoading(true);
    setError(false);
    getStudentActivities()
      .then((res) => {
        setActivities(res.activities || []);
      })
      .catch(() => {
        setError(true);
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    loadActivities();
  }, []);

  if (loading) {
    return <p>Loading activities...</p>;
  }

  if (error) {
    return (
      <div>
        <p>Unable to load activities.</p>
        <button
          type="button"
          onClick={loadActivities}
          style={{ marginTop: '8px', padding: '6px 12px' }}
        >
          Try again
        </button>
      </div>
    );
  }

  const formatDueDate = (dateStr: string | null) => {
    if (!dateStr) return 'No deadline';
    const date = new Date(dateStr);
    return date.toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
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

  return (
    <div style={{ maxWidth: '800px' }}>
      <h2 style={{ fontSize: '1.4rem', marginBottom: '16px' }}>Activities</h2>

      {activities.length === 0 ? (
        <div
          style={{
            backgroundColor: '#ffffff',
            border: '1px solid #e5e7eb',
            borderRadius: '8px',
            padding: '24px',
            textAlign: 'center',
            color: '#6b7280',
          }}
        >
          <p style={{ margin: '0 0 8px 0', fontWeight: 500, color: '#374151', fontSize: '1.05rem' }}>
            No activities yet.
          </p>
          <p style={{ margin: 0, fontSize: '0.9rem' }}>
            Your assigned activities will appear here.
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {activities.map((act) => (
            <div
              key={act.id}
              style={{
                backgroundColor: '#ffffff',
                border: '1px solid #e5e7eb',
                borderRadius: '8px',
                padding: '20px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <h3 style={{ margin: '0 0 6px 0', fontSize: '1.15rem' }}>{act.title}</h3>
                  <span
                    style={{
                      display: 'inline-block',
                      backgroundColor: '#eff6ff',
                      color: '#1d4ed8',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      padding: '2px 8px',
                      borderRadius: '4px',
                      marginBottom: '8px',
                    }}
                  >
                    {formatType(act.type)}
                  </span>
                </div>
                <span
                  style={{
                    fontSize: '0.85rem',
                    fontWeight: 500,
                    color: act.status === 'PENDING' ? '#d97706' : '#16a34a',
                  }}
                >
                  Status: {formatStatus(act.status)}
                </span>
              </div>

              {act.description && (
                <p style={{ margin: '4px 0 12px 0', color: '#4b5563', fontSize: '0.9rem' }}>
                  {act.description}
                </p>
              )}

              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginTop: '12px',
                  paddingTop: '12px',
                  borderTop: '1px solid #f3f4f6',
                  fontSize: '0.85rem',
                  color: '#6b7280',
                }}
              >
                <div>
                  <span>Due: {formatDueDate(act.due_date)}</span>
                  {act.max_marks > 0 && <span style={{ marginLeft: '16px' }}>Max marks: {act.max_marks}</span>}
                </div>

                <Link
                  to={`/student/activities/${act.id}`}
                  style={{
                    backgroundColor: '#2563eb',
                    color: '#ffffff',
                    padding: '6px 14px',
                    borderRadius: '4px',
                    textDecoration: 'none',
                    fontWeight: 500,
                  }}
                >
                  View Activity
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
