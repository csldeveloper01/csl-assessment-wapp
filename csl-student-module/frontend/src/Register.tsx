
import { useState, type FormEvent } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { api } from './api';
import axios from 'axios';
import './index.css';

type RegistrationFields = 'name' | 'email' | 'password';

type RegistrationErrors = Partial<Record<RegistrationFields, string>>;

export function Register() {
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<RegistrationErrors>({});
  const [submitError, setSubmitError] = useState('');
  const [loading, setLoading] = useState(false);

  const navigate = useNavigate();

  const validateField = (
    field: RegistrationFields,
    value: string,
  ): string => {
    const trimmed = value.trim();

    switch (field) {
      case 'name':
        if (!trimmed) return 'Full name is required.';
        if (trimmed.length > 50) {
          return 'Full name cannot exceed 50 characters.';
        }
        if (!/^[A-Za-z]+(?:[ '-][A-Za-z]+)*$/.test(trimmed)) {
          return 'Enter a valid name using letters, spaces, hyphens, or apostrophes.';
        }
        return '';

      case 'email': {
        if (!trimmed) return 'Email address is required.';
        if (trimmed.length > 254) {
          return 'Email address cannot exceed 254 characters.';
        }

        const emailPattern =
          /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

        if (!emailPattern.test(trimmed)) {
          return 'Enter a valid email address, such as student@college.edu.';
        }
        return '';
      }

      case 'password':
        if (!value) return 'Password is required.';
        if (value.length < 8) {
          return 'Password must contain at least 8 characters.';
        }
        return '';
    }
  };

  const handleFieldChange = (
    field: RegistrationFields,
    value: string,
  ) => {
    setSubmitError('');

    switch (field) {
      case 'name':
        setName(value.slice(0, 50));
        break;
      case 'email':
        setEmail(value.slice(0, 254));
        break;
      case 'password':
        setPassword(value);
        break;
    }

    setErrors((previous) => ({
      ...previous,
      [field]: validateField(field, value),
    }));
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setSubmitError('');

    const nextErrors: RegistrationErrors = {
      name: validateField('name', name),
      email: validateField('email', email),
      password: validateField('password', password),
    };

    setErrors(nextErrors);

    if (Object.values(nextErrors).some(Boolean)) {
      const firstInvalidField = (
        Object.keys(nextErrors) as RegistrationFields[]
      ).find((field) => nextErrors[field]);

      if (firstInvalidField) {
        document.getElementById(firstInvalidField)?.focus();
      }

      return;
    }

    setLoading(true);

    try {
      await api.post('/register/', {
        email: email.trim().toLowerCase(),
        name: name.trim(),
        password,
      });

      navigate('/pending');
    } catch (err: unknown) {
      if (axios.isAxiosError(err) && err.response) {
        const data = err.response.data;

        const fieldErrors: RegistrationErrors = {};

        for (const field of ['name', 'email', 'password'] as const) {
          if (data[field]) {
            fieldErrors[field] = Array.isArray(data[field])
              ? data[field][0]
              : String(data[field]);
          }
        }

        setErrors(fieldErrors);

        if (data.detail) {
          setSubmitError(String(data.detail));
        } else if (Object.keys(fieldErrors).length === 0) {
          setSubmitError(
            'Registration failed. Please check your information and try again.',
          );
        }
      } else {
        setSubmitError('Network error. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="registration-page">
      <section className="registration-card">
        <header className="registration-header">
          <div className="registration-logo" aria-label="Creator Space Lab">
            CSL
          </div>

          <h1>Create your account</h1>
          <p>Register for the CSL Student Portal.</p>
        </header>

        {submitError && (
          <div className="registration-error" role="alert">
            {submitError}
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          <div className="registration-field">
            <label htmlFor="name">Full Name</label>
            <input
              id="name"
              name="name"
              type="text"
              autoComplete="name"
              maxLength={50}
              required
              value={name}
              onChange={(e) => handleFieldChange('name', e.target.value)}
              aria-invalid={Boolean(errors.name)}
              aria-describedby={errors.name ? 'name-error' : undefined}
            />
            <div className="registration-field-meta">
              {errors.name ? (
                <span id="name-error" className="field-error" role="alert">
                  {errors.name}
                </span>
              ) : (
                <span />
              )}
              <span className="character-count">{name.length}/50</span>
            </div>
          </div>

          <div className="registration-field">
            <label htmlFor="email">Email Address</label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              maxLength={254}
              required
              value={email}
              onChange={(e) => handleFieldChange('email', e.target.value)}
              aria-invalid={Boolean(errors.email)}
              aria-describedby={errors.email ? 'email-error' : undefined}
            />
            {errors.email && (
              <span id="email-error" className="field-error" role="alert">
                {errors.email}
              </span>
            )}
          </div>

          <div className="registration-field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="new-password"
              minLength={8}
              required
              value={password}
              onChange={(e) =>
                handleFieldChange('password', e.target.value)
              }
              aria-invalid={Boolean(errors.password)}
              aria-describedby={
                errors.password ? 'password-error' : undefined
              }
            />
            {errors.password && (
              <span
                id="password-error"
                className="field-error"
                role="alert"
              >
                {errors.password}
              </span>
            )}
          </div>

          <button
            className="registration-submit"
            type="submit"
            disabled={loading}
          >
            {loading ? 'Submitting...' : 'Register'}
          </button>
        </form>

        <p className="registration-footer">
          Already registered? <Link to="/login">Login</Link>
        </p>
      </section>
    </main>
  );
};