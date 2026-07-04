import { useEffect, useState } from 'react'
import { Link, Outlet } from 'react-router-dom'
import { api } from './api'
import Login from './pages/Login'
import type { User } from './types'

export default function App() {
  const [provider, setProvider] = useState<string | null>(null)
  const [user, setUser] = useState<User | null | 'loading'>('loading')

  useEffect(() => {
    api.health().then((h) => setProvider(h.provider)).catch(() => setProvider('offline'))
    api.me().then(setUser).catch(() => setUser(null))
  }, [])

  const logout = async () => {
    await api.logout().catch(() => {})
    setUser(null)
  }

  const isMistral = provider === 'mistral'
  return (
    <>
      <header className="topbar">
        <Link to="/">DD Pipeline</Link>
        <span className="sub">
          EU-sovereign due diligence · cross-border ES–FR · every conclusion cites its source
        </span>
        <span className="spacer" />
        {provider && (
          <span
            className="badge chip"
            title={
              isMistral
                ? 'Running the Mistral EU-sovereign engine'
                : 'Running the offline demo engine — set DD_PROVIDER=mistral in .env for real documents'
            }
            style={{
              background: isMistral ? '#1e7d43' : '#b26a00',
              color: '#fff',
            }}
          >
            engine: {isMistral ? 'Mistral (EU)' : `${provider} (offline)`}
          </span>
        )}
        {user && user !== 'loading' && (
          <>
            <span className="badge chip" title={user.email}>
              {user.name}
            </span>
            <button
              className="secondary"
              style={{ padding: '0.2rem 0.6rem', fontSize: '0.75rem' }}
              onClick={logout}
            >
              Sign out
            </button>
          </>
        )}
      </header>
      <main className="container">
        {user === 'loading' ? (
          <p className="muted">Loading…</p>
        ) : user === null ? (
          <Login onAuth={setUser} />
        ) : (
          <Outlet context={{ user }} />
        )}
      </main>
    </>
  )
}
