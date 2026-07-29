import React, { useState, useEffect } from 'react';
import { GoogleLogin, GoogleOAuthProvider } from '@react-oauth/google';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { loginUser, registerUser, loginWithGoogle } from '../api/client';
import './Auth.css';

const Auth = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [isLogin, setIsLogin] = useState(location.pathname !== '/register');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setIsLogin(location.pathname !== '/register');
    setError('');
  }, [location.pathname]);

  const handleSuccess = () => {
    navigate('/dashboard', { replace: true });
  };

  const handleGoogleSuccess = async (credentialResponse) => {
    setError('');
    setIsLoading(true);
    try {
      const success = await loginWithGoogle(credentialResponse.credential);
      if (success) {
        handleSuccess();
      } else {
        setError('Google Login failed. Please try again.');
      }
    } catch (err) {
      console.error('Google Auth error:', err);
      setError('An error occurred during Google authentication.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    const normalizedEmail = email.trim().toLowerCase();
    const normalizedFullName = fullName.trim();

    if (!normalizedEmail || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizedEmail)) {
      setError('Please enter a valid email address.');
      return;
    }

    if (!password) {
      setError('Password is required.');
      return;
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters long.');
      return;
    }

    if (!isLogin && !normalizedFullName) {
      setError('Please enter your full name when signing up.');
      return;
    }

    setIsLoading(true);

    try {
      if (isLogin) {
        const success = await loginUser(normalizedEmail, password);
        if (success) {
          handleSuccess();
        } else {
          setError('Invalid credentials');
        }
      } else {
        const registeredUser = await registerUser(normalizedEmail, password, normalizedFullName);
        if (!registeredUser) {
          setError('Registration failed. Please try again.');
          setIsLoading(false);
          return;
        }

        const success = await loginUser(normalizedEmail, password);
        if (success) {
          handleSuccess();
        } else {
          setError('Registration successful, but login failed. Please try logging in manually.');
          navigate('/login');
        }
      }
    } catch (err) {
      console.error('Auth error:', err);
      let detail = 'Authentication failed. Please check your credentials.';
      if (err?.response?.data) {
        detail = err.response.data.detail;
      } else if (err?.message) {
        detail = err.message;
      }

      if (Array.isArray(detail)) {
         setError(detail.map(d => d.msg).join(', '));
      } else {
         setError(typeof detail === 'string' ? detail : 'Authentication failed.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <div className="auth-header">
          <div className="auth-logo">
            <img src="./src/assets/logo.png" alt="NovaCut AI" style={{ height: '48px', objectFit: 'contain' }} />
          </div>
          <h2>{isLogin ? 'Welcome Back' : 'Create Account'}</h2>
          <p>{isLogin ? 'Log in to continue editing' : 'Sign up to start creating'}</p>
        </div>

        {error && <div className="auth-error">{error}</div>}

        <form className="auth-form" onSubmit={handleSubmit}>
          {!isLogin && (
            <div className="form-group">
              <label>Full Name</label>
              <input 
                type="text" 
                value={fullName} 
                onChange={(e) => setFullName(e.target.value)} 
                placeholder="John Doe"
                required={!isLogin}
              />
            </div>
          )}
          <div className="form-group">
            <label>Email</label>
            <input 
              type="email" 
              value={email} 
              onChange={(e) => setEmail(e.target.value)} 
              placeholder="you@example.com"
              required
            />
          </div>
          <div className="form-group">
            <label>Password</label>
            <input 
              type="password" 
              value={password} 
              onChange={(e) => setPassword(e.target.value)} 
              placeholder="••••••••"
              required
            />
          </div>
          <button type="submit" className="primary auth-submit" disabled={isLoading}>
            {isLoading ? 'Please wait...' : (isLogin ? 'Log In' : 'Sign Up')}
          </button>
        </form>

        <div className="auth-divider" style={{ display: 'flex', alignItems: 'center', textAlign: 'center', margin: '20px 0', color: 'var(--text-muted)', fontSize: '12px' }}>
          <div style={{ flex: 1, height: '1px', background: 'var(--border-light)' }}></div>
          <span style={{ padding: '0 10px' }}>OR</span>
          <div style={{ flex: 1, height: '1px', background: 'var(--border-light)' }}></div>
        </div>

        <div className="google-auth-wrapper" style={{ display: 'flex', justifyContent: 'center' }}>
          <GoogleOAuthProvider clientId={import.meta.env.VITE_GOOGLE_CLIENT_ID || 'dummy-client-id'}>
            <GoogleLogin
              onSuccess={handleGoogleSuccess}
              onError={() => {
                console.error('Google Login Failed');
                setError('Google Login Failed. Please try again.');
              }}
              theme="filled_black"
              shape="rectangular"
              text="continue_with"
            />
          </GoogleOAuthProvider>
        </div>

        <div className="auth-footer">
          <p>
            {isLogin ? "Don't have an account? " : "Already have an account? "}
            <Link to={isLogin ? '/register' : '/login'} className="auth-toggle">
              {isLogin ? 'Sign up' : 'Log in'}
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
};

export default Auth;
