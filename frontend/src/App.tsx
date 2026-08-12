import { useEffect, useState, type ReactNode } from 'react'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { NotFound } from './pages/NotFound'
import { Products } from './pages/Products'
import { Promotions } from './pages/Promotions'
import { SettingsPage } from './pages/Settings'
import { Stores } from './pages/Stores'

export default function App() {
  const [path, setPath] = useState(window.location.pathname)

  useEffect(() => {
    const handlePopState = () => setPath(window.location.pathname)
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  function navigate(to: string) {
    if (to !== window.location.pathname) {
      window.history.pushState(null, '', to)
    }
    setPath(to)
  }

  const pages: Record<string, ReactNode> = {
    '/': <Dashboard />,
    '/products': <Products />,
    '/stores': <Stores />,
    '/promotions': <Promotions />,
    '/settings': <SettingsPage />,
  }

  return (
    <Layout currentPath={path} onNavigate={navigate}>
      {pages[path] ?? <NotFound onNavigate={navigate} />}
    </Layout>
  )
}
