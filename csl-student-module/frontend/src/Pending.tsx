import { Link } from 'react-router-dom';

export function Pending() {
  return (
    <div style={{ maxWidth: 500, margin: '60px auto', textAlign: 'center' }}>
      <h2>Registration Submitted</h2>
      <p style={{ margin: '20px 0' }}>Your request is currently awaiting approval.</p>
      <Link to="/login">Back to Login</Link>
    </div>
  );
}
