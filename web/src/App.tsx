import { useEffect, useState } from 'react'
import { Link, Outlet } from 'react-router-dom'
import { api } from './api'

export default function App() {
  const [provider, setProvider] = useState<string | null>(null)

  useEffect(() => {
    api.health().then((h) => setProvider(h.provider)).catch(() => setProvider('offline'))
  }, [])

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
      </header>
      <main className="container">
        <Outlet />
      </main>
    </>
  )
}
