import { useEffect, useState } from 'react';
import { getStudentSkills } from '../../api/student';
import type { StudentSkillsResponse } from '../../types/student';

/**
 * Student Skills Page:
 * Displays required skills and subskills derived from StudentProfile -> Course -> CourseSkill.
 * If not assigned, prompts the student clearly.
 */
export function StudentSkillsPage() {
  const [data, setData] = useState<StudentSkillsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getStudentSkills()
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return <p>Loading skills...</p>;
  }

  if (error || !data) {
    return <p>Unable to load skills.</p>;
  }

  // Unassigned course/batch state
  if (!data.course) {
    return (
      <div>
        <h2>My Skills</h2>
        <p>Course: Not assigned</p>
        <p>Batch: Not assigned</p>
        <p style={{ marginTop: '16px', color: '#4b5563' }}>
          Your skill matrix will appear after you are assigned to a course and batch.
        </p>
      </div>
    );
  }

  const formatStatus = (status: string) => {
    if (status === 'UNASSESSED') return 'Unassessed';
    return status;
  };

  return (
    <div>
      <h2>My Skills</h2>
      <p>Course: {data.course.name} ({data.course.code})</p>
      <p>Batch: {data.batch ? data.batch.name : 'Not assigned'}</p>

      <div style={{ marginTop: '24px' }}>
        {data.skills.length === 0 ? (
          <p style={{ color: '#4b5563' }}>No required skills have been mapped for your course yet.</p>
        ) : (
          data.skills.map((skill) => (
            <div key={skill.id} style={{ marginBottom: '20px' }}>
              <h3 style={{ margin: '0 0 8px 0', fontSize: '1.1rem' }}>{skill.name}</h3>
              {skill.subskills.length === 0 ? (
                <div style={{ paddingLeft: '16px', color: '#6b7280' }}>
                  <span>(entire skill)</span>
                  <span style={{ marginLeft: '24px' }}>{formatStatus(skill.status)}</span>
                </div>
              ) : (
                <ul style={{ listStyle: 'none', paddingLeft: '16px', margin: 0 }}>
                  {skill.subskills.map((sub) => (
                    <li
                      key={sub.id}
                      style={{
                        display: 'flex',
                        maxWidth: '400px',
                        justifyContent: 'space-between',
                        padding: '4px 0',
                      }}
                    >
                      <span>{sub.name}</span>
                      <span style={{ color: '#6b7280' }}>{formatStatus(sub.status)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
