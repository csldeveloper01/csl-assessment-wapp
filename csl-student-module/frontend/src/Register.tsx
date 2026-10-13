import { useState, type FormEvent } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { api } from './api';
import axios from 'axios';

export function Register() {
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await api.post('/register/', { email, name, password });
      navigate('/pending');
    } catch (err: unknown) {
      if (axios.isAxiosError(err) && err.response) {
        const data = err.response.data;
        if (data.email) {
          setError(Array.isArray(data.email) ? data.email[0] : data.email);
        } else if (data.name) {
          setError(Array.isArray(data.name) ? data.name[0] : data.name);
        } else if (data.password) {
          setError(Array.isArray(data.password) ? data.password[0] : data.password);
        } else if (data.detail) {
          setError(data.detail);
        } else {
          setError('Registration failed. Please check your information.');
        }
      } else {
        setError('Network error. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 400, margin: '50px auto', textAlign: 'left' }}>
      <h2>Register</h2>
      {error && <p style={{ color: 'red', marginBottom: 12 }}>{error}</p>}
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div>
          <label htmlFor="email" style={{ display: 'block', marginBottom: 4 }}>Email</label>
          <input
            id="email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            style={{ width: '100%', padding: '8px', boxSizing: 'border-box' }}
          />
        </div>
        <div>
          <label htmlFor="name" style={{ display: 'block', marginBottom: 4 }}>Name</label>
          <input
            id="name"
            type="text"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            style={{ width: '100%', padding: '8px', boxSizing: 'border-box' }}
          />
        </div>
        <div>
          <label htmlFor="password" style={{ display: 'block', marginBottom: 4 }}>Password</label>
          <input
            id="password"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={{ width: '100%', padding: '8px', boxSizing: 'border-box' }}
          />
        </div>
        <button type="submit" disabled={loading} style={{ padding: '8px 16px', marginTop: 8 }}>
          {loading ? 'Submitting...' : 'Register'}
        </button>
      </form>
      <p style={{ marginTop: 16 }}>
        Already registered? <Link to="/login">Login</Link>
      </p>
    </div>
  );
}
