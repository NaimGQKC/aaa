import { useState } from 'react'
import { api } from '../api'
import type { User } from '../types'

export default function Login({ onAuth }: { onAuth: (u: User) => void }) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    setBusy(true)
    setError('')
    try {
      const user =
        mode === 'login'
          ? await api.login(email, password)
          : await api.register(email, name, password)
      onAuth(user)
    } catch (e) {
      const msg = String(e)
      setError(
        msg.includes('401')
          ? 'Wrong email or password.'
          : msg.includes('409')
            ? 'An account with this email already exists — sign in instead.'
            : msg,
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-wrap">
      <div className="panel login-card">
        <h2>{mode === 'login' ? 'Sign in' : 'Create your account'}</h2>
        <p className="muted" style={{ marginTop: '-0.4rem' }}>
          Access is per-deal: you only see deals you own or were invited to.
          Every review you make is recorded under your identity.
        </p>
        <div className="login-fields">
          <input
            placeholder="Email"
            type="email"
            value={email}
            autoFocus
            onChange={(e) => setEmail(e.target.value)}
          />
          {mode === 'register' && (
            <input
              placeholder="Full name (appears on reports as reviewer)"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          )}
          <input
            placeholder={mode === 'register' ? 'Password (min 8 characters)' : 'Password'}
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && submit()}
          />
          <button disabled={busy} onClick={submit}>
            {busy ? '…' : mode === 'login' ? 'Sign in' : 'Create account'}
          </button>
        </div>
        {error && <p style={{ color: 'var(--high)' }}>{error}</p>}
        <p className="muted">
          {mode === 'login' ? (
            <>
              New here?{' '}
              <a onClick={() => setMode('register')} style={{ cursor: 'pointer' }}>
                Create an account
              </a>
            </>
          ) : (
            <>
              Already registered?{' '}
              <a onClick={() => setMode('login')} style={{ cursor: 'pointer' }}>
                Sign in
              </a>
            </>
          )}
        </p>
      </div>
    </div>
  )
}
