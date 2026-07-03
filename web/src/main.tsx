import React from 'react'
import ReactDOM from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import App from './App'
import DealDashboard from './pages/DealDashboard'
import DealList from './pages/DealList'
import DocumentReview from './pages/DocumentReview'
import './styles.css'

const router = createBrowserRouter([
  {
    path: '/',
    element: <App />,
    children: [
      { index: true, element: <DealList /> },
      { path: 'deals/:dealId', element: <DealDashboard /> },
      { path: 'deals/:dealId/documents/:documentId', element: <DocumentReview /> },
    ],
  },
])

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>,
)
