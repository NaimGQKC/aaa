import { Link, Outlet } from 'react-router-dom'

export default function App() {
  return (
    <>
      <header className="topbar">
        <Link to="/">DD Pipeline</Link>
        <span className="sub">
          EU-sovereign due diligence · cross-border ES–FR · every conclusion cites its source
        </span>
      </header>
      <main className="container">
        <Outlet />
      </main>
    </>
  )
}
