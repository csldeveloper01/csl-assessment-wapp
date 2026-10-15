import { useState, type FormEvent, type FocusEvent } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { api } from './api';
import axios from 'axios';
import cslTypographyLogo from './assets/CSL-TYPOGRAPHY.png';
import './index.css';

type RegistrationFields = 'name' | 'registration_number' | 'email' | 'password';

type RegistrationErrors = Partial<Record<RegistrationFields, string>>;

export function Register() {
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [registrationNumber, setRegistrationNumber] = useState('');
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

      case 'registration_number':
        if (!trimmed) return 'Register / roll number is required.';
        if (trimmed.length > 25) {
          return 'Register / roll number cannot exceed 25 characters.';
        }
        if (!/^[A-Za-z0-9][A-Za-z0-9\s\-_/]*$/.test(trimmed)) {
          return 'Register / roll number must contain only letters, numbers, hyphens, slashes, or spaces.';
        }
        return '';

      case 'email': {
        if (!trimmed) return 'College email is required.';
        if (trimmed.length > 254) {
          return 'College email cannot exceed 254 characters.';
        }
        if (/\s/.test(trimmed)) {
          return 'Enter a valid college email address without spaces.';
        }

        // Email syntax validation: local part, @, domain, and valid TLD
        const emailPattern =
          /^[a-zA-Z0-9_\-\.\+]+@[a-zA-Z0-9\-\.]+\.[a-zA-Z0-9\-]+$/;

        if (!emailPattern.test(trimmed)) {
          return 'Enter a valid college email address (e.g. student@college.edu).';
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
      case 'registration_number':
        setRegistrationNumber(value.slice(0, 25));
        break;
      case 'email':
        setEmail(value.slice(0, 254));
        break;
      case 'password':
        setPassword(value);
        break;
    }

    setErrors((previous) => {
      const fieldError = validateField(field, value);
      if (!fieldError) {
        const updated = { ...previous };
        delete updated[field];
        return updated;
      }
      return {
        ...previous,
        [field]: fieldError,
      };
    });
  };

  const handleBlur = (
    field: RegistrationFields,
    value: string,
  ) => {
    const errorMsg = validateField(field, value);
    setErrors((previous) => {
      if (!errorMsg) {
        const updated = { ...previous };
        delete updated[field];
        return updated;
      }
      return {
        ...previous,
        [field]: errorMsg,
      };
    });
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setSubmitError('');

    const nextErrors: RegistrationErrors = {
      name: validateField('name', name),
      registration_number: validateField('registration_number', registrationNumber),
      email: validateField('email', email),
      password: validateField('password', password),
    };

    // Filter out empty errors
    const activeErrors: RegistrationErrors = {};
    (Object.keys(nextErrors) as RegistrationFields[]).forEach((field) => {
      if (nextErrors[field]) {
        activeErrors[field] = nextErrors[field];
      }
    });

    setErrors(activeErrors);

    if (Object.keys(activeErrors).length > 0) {
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
        registration_number: registrationNumber.trim(),
        password,
      });

      navigate('/pending');
    } catch (err: unknown) {
      if (axios.isAxiosError(err) && err.response) {
        const data = err.response.data;

        const fieldErrors: RegistrationErrors = {};

        const fieldsToCheck: RegistrationFields[] = [
          'name',
          'registration_number',
          'email',
          'password',
        ];

        for (const field of fieldsToCheck) {
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
          <div className="registration-logo">
            <img
              src={cslTypographyLogo}
              alt="CSL Creator Space Lab"
              className="registration-logo-img"
            />
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
              onBlur={(e: FocusEvent<HTMLInputElement>) => handleBlur('name', e.target.value)}
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
            <label htmlFor="registration_number">Register / Roll Number</label>
            <input
              id="registration_number"
              name="registration_number"
              type="text"
              autoComplete="off"
              maxLength={25}
              required
              value={registrationNumber}
              onChange={(e) => handleFieldChange('registration_number', e.target.value)}
              onBlur={(e: FocusEvent<HTMLInputElement>) =>
                handleBlur('registration_number', e.target.value)
              }
              aria-invalid={Boolean(errors.registration_number)}
              aria-describedby={
                errors.registration_number ? 'registration_number-error' : undefined
              }
            />
            <div className="registration-field-meta">
              {errors.registration_number ? (
                <span id="registration_number-error" className="field-error" role="alert">
                  {errors.registration_number}
                </span>
              ) : (
                <span />
              )}
              <span className="character-count">{registrationNumber.length}/25</span>
            </div>
          </div>

          <div className="registration-field">
            <label htmlFor="email">College Email</label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              maxLength={254}
              required
              value={email}
              onChange={(e) => handleFieldChange('email', e.target.value)}
              onBlur={(e: FocusEvent<HTMLInputElement>) => handleBlur('email', e.target.value)}
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
              onBlur={(e: FocusEvent<HTMLInputElement>) => handleBlur('password', e.target.value)}
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
}