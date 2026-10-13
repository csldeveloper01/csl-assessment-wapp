import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getStudentDashboard } from '../../api/student';
import type { StudentDashboardResponse } from '../../types/student';

/**
 * Student Dashboard — Phase 1
 * Consumes real authenticated student identity and required skills data.
 * Presents clean cards with honest placeholders for performance and activities.
 */
export function StudentDashboardPage() {
  const [data, setData] = useState<StudentDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const loadDashboard = () => {
    setLoading(true);
    setError(false);
    getStudentDashboard()
      .then((res) => {
        setData(res);
      })
      .catch(() => {
        setError(true);
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    loadDashboard();
  }, []);

  if (loading) {
    return <p>Loading dashboard...</p>;
  }

  if (error || !data) {
    return (
      <div>
        <p>Unable to load dashboard.</p>
        <button type="button" onClick={loadDashboard} style={{ marginTop: '8px', padding: '6px 12px' }}>
          Try again.
        </button>
      </div>
    );
  }

  const { student, skills, performance, activities } = data;
  const isCourseAssigned = Boolean(student.course);
  const isBatchAssigned = Boolean(student.batch);

  return (
    <div style={{ maxWidth: '800px' }}>
      {/* 1. Welcome / Student Identity Card */}
      <section
        style={{
          backgroundColor: '#ffffff',
          border: '1px solid #e5e7eb',
          borderRadius: '8px',
          padding: '20px',
          marginBottom: '20px',
        }}
      >
        <h2 style={{ margin: '0 0 8px 0', fontSize: '1.4rem' }}>
          Welcome back, {student.name}.
        </h2>
        <p style={{ margin: '0', color: '#6b7280', fontSize: '0.95rem' }}>
          Student ID: <span style={{ color: '#111827', fontWeight: 500 }}>{student.student_id}</span>
        </p>
      </section>

      {/* Grid for Cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: '20px',
          marginBottom: '20px',
        }}
      >
        {/* 2. Course / Batch Status Card */}
        <div
          style={{
            backgroundColor: '#ffffff',
            border: '1px solid #e5e7eb',
            borderRadius: '8px',
            padding: '20px',
          }}
        >
          <h3 style={{ margin: '0 0 12px 0', fontSize: '1.1rem' }}>Course & Batch</h3>
          <div style={{ marginBottom: '8px' }}>
            <span style={{ color: '#6b7280', display: 'block', fontSize: '0.85rem' }}>Course</span>
            <span style={{ fontWeight: 500 }}>
              {isCourseAssigned
                ? `${student.course} (${student.course_code})`
                : 'Not assigned'}
            </span>
          </div>
          <div style={{ marginBottom: '12px' }}>
            <span style={{ color: '#6b7280', display: 'block', fontSize: '0.85rem' }}>Batch</span>
            <span style={{ fontWeight: 500 }}>{isBatchAssigned ? student.batch : 'Not assigned'}</span>
          </div>

          {!isCourseAssigned && !isBatchAssigned ? (
            <p style={{ margin: '8px 0 0 0', fontSize: '0.85rem', color: '#6b7280' }}>
              Your dashboard will update once you are assigned to a course and batch.
            </p>
          ) : !isBatchAssigned ? (
            <p style={{ margin: '8px 0 0 0', fontSize: '0.85rem', color: '#6b7280' }}>
              Your batch assignment is pending.
            </p>
          ) : null}
        </div>

        {/* 3. Skill Overview Card */}
        <div
          style={{
            backgroundColor: '#ffffff',
            border: '1px solid #e5e7eb',
            borderRadius: '8px',
            padding: '20px',
          }}
        >
          <h3 style={{ margin: '0 0 12px 0', fontSize: '1.1rem' }}>Skills</h3>
          {skills.available ? (
            skills.total_skills === 0 ? (
              <p style={{ margin: 0, color: '#6b7280', fontSize: '0.9rem' }}>
                No required skills have been mapped yet.
              </p>
            ) : (
              <div>
                <div style={{ display: 'flex', gap: '24px', marginBottom: '8px' }}>
                  <div>
                    <span style={{ display: 'block', fontSize: '1.3rem', fontWeight: 600 }}>
                      {skills.total_skills}
                    </span>
                    <span style={{ color: '#6b7280', fontSize: '0.85rem' }}>Required Skills</span>
                  </div>
                  <div>
                    <span style={{ display: 'block', fontSize: '1.3rem', fontWeight: 600, color: '#16a34a' }}>
                      {skills.assessed}
                    </span>
                    <span style={{ color: '#6b7280', fontSize: '0.85rem' }}>Assessed</span>
                  </div>
                  <div>
                    <span style={{ display: 'block', fontSize: '1.3rem', fontWeight: 600, color: '#d97706' }}>
                      {skills.unassessed}
                    </span>
                    <span style={{ color: '#6b7280', fontSize: '0.85rem' }}>Unassessed</span>
                  </div>
                </div>
                {skills.total_subskills > 0 && (
                  <p style={{ margin: '8px 0 0 0', color: '#6b7280', fontSize: '0.85rem' }}>
                    {skills.total_subskills} total sub-skills required
                  </p>
                )}
              </div>
            )
          ) : (
            <div>
              <p style={{ margin: '0 0 4px 0', fontWeight: 500, color: '#6b7280' }}>Not available</p>
              <p style={{ margin: 0, fontSize: '0.85rem', color: '#6b7280' }}>
                Assign a course and batch to view your skill progress.
              </p>
            </div>
          )}
        </div>

        {/* 4. Overall Performance Card */}
        <div
          style={{
            backgroundColor: '#ffffff',
            border: '1px solid #e5e7eb',
            borderRadius: '8px',
            padding: '20px',
          }}
        >
          <h3 style={{ margin: '0 0 12px 0', fontSize: '1.1rem' }}>Overall Performance</h3>
          <div style={{ fontSize: '1.8rem', fontWeight: 600, color: '#9ca3af', marginBottom: '4px' }}>
            —
          </div>
          <p style={{ margin: 0, color: '#6b7280', fontSize: '0.9rem' }}>
            {performance.message}
          </p>
        </div>

        {/* 5. Activities Card */}
        <div
          style={{
            backgroundColor: '#ffffff',
            border: '1px solid #e5e7eb',
            borderRadius: '8px',
            padding: '20px',
          }}
        >
          <h3 style={{ margin: '0 0 12px 0', fontSize: '1.1rem' }}>Activities</h3>
          <p style={{ margin: '0 0 4px 0', fontWeight: 500, color: '#374151' }}>
            {activities.message}.
          </p>
          <p style={{ margin: 0, color: '#6b7280', fontSize: '0.85rem' }}>
            Your assigned activities will appear here.
          </p>
        </div>
      </div>

      {/* 6. Quick Navigation */}
      <section
        style={{
          backgroundColor: '#ffffff',
          border: '1px solid #e5e7eb',
          borderRadius: '8px',
          padding: '20px',
        }}
      >
        <h3 style={{ margin: '0 0 12px 0', fontSize: '1.1rem' }}>Quick Actions</h3>
        <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
          <Link
            to="/student/skills"
            style={{
              padding: '8px 16px',
              backgroundColor: '#2563eb',
              color: '#ffffff',
              borderRadius: '6px',
              textDecoration: 'none',
              fontSize: '0.9rem',
              fontWeight: 500,
            }}
          >
            View Skills
          </Link>
          <Link
            to="/student/activities"
            style={{
              padding: '8px 16px',
              backgroundColor: '#2563eb',
              color: '#ffffff',
              borderRadius: '6px',
              textDecoration: 'none',
              fontSize: '0.9rem',
              fontWeight: 500,
            }}
          >
            View Activities
          </Link>
          <Link
            to="/student/profile"
            style={{
              padding: '8px 16px',
              backgroundColor: '#f3f4f6',
              color: '#1f2937',
              borderRadius: '6px',
              border: '1px solid #d1d5db',
              textDecoration: 'none',
              fontSize: '0.9rem',
              fontWeight: 500,
            }}
          >
            View Profile
          </Link>
        </div>
      </section>
    </div>
  );
}
