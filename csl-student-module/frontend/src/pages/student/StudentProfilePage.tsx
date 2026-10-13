import { useEffect, useState } from 'react';
import { getStudentProfile } from '../../api/student';
import type { StudentProfile } from '../../types/student';

/**
 * Student profile page. Read-only today: fetches the authenticated student's
 * profile from the backend (which resolves the student from the session).
 */
export function StudentProfilePage() {
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getStudentProfile()
      .then((data) => {
        if (!cancelled) setProfile(data);
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
    return <p>Loading profile...</p>;
  }

  if (error || !profile) {
    return <p>Unable to load profile.</p>;
  }

  return (
    <div>
      <h2>My Profile</h2>
      <dl>
        <dt>Name</dt>
        <dd>{profile.name}</dd>

        <dt>Email</dt>
        <dd>{profile.email}</dd>

        <dt>Student ID</dt>
        <dd>{profile.student_id}</dd>

        <dt>Course</dt>
        <dd>{profile.course ?? 'Not assigned'}</dd>

        <dt>Batch</dt>
        <dd>{profile.batch ?? 'Not assigned'}</dd>
      </dl>
    </div>
  );
}
