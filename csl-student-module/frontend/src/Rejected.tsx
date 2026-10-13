import { Link } from 'react-router-dom';

export function Rejected() {
  return (
    <div style={{ maxWidth: 500, margin: '60px auto', textAlign: 'center' }}>
      <h2>Request Declined</h2>
      <p style={{ margin: '20px 0', color: '#c00' }}>Your registration request has been declined.</p>
      <div style={{ display: 'flex', gap: 16, justifyContent: 'center' }}>
        <Link to="/login">Back to Login</Link>
        <Link to="/register">Register Again</Link>
      </div>
    </div>
  );
}
