import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { useUIStore } from '@/stores/uiStore'
import { useTranslation } from 'react-i18next'
import { LayoutDashboard, Network, Cpu, Settings, LogOut, Database } from 'lucide-react'

export default function Layout({ children }: { children: React.ReactNode }) {
  const logout = useAuthStore(s => s.logout)
  const navigate = useNavigate()
  const location = useLocation()
  const { t } = useTranslation()
  const { lang, setLang } = useUIStore()

  const navItems = [
    { to: '/overview', icon: LayoutDashboard, label: t('nav.overview') },
    { to: '/pipelines', icon: Database, label: t('nav.pipelines') },
    { to: '/ontologies', icon: Network, label: t('nav.ontologies') },
    { to: '/models', icon: Cpu, label: t('nav.models') },
    { to: '/settings', icon: Settings, label: t('nav.settings') },
  ]

  return (
    <div className="flex h-screen bg-gray-50">
      <aside className="w-56 bg-white border-r flex flex-col">
        <div className="p-4 border-b flex items-center justify-between">
          <h1 className="font-bold text-lg">OntoPrompt</h1>
          <button onClick={() => setLang(lang === 'zh' ? 'en' : 'zh')}
            className="p-1 rounded hover:bg-gray-100 text-gray-500 text-xs">
            {lang === 'zh' ? 'EN' : '中'}
          </button>
        </div>
        <nav className="flex-1 p-2 space-y-1">
          {navItems.map(({ to, icon: Icon, label }) => (
            <Link key={to} to={to}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors
                ${location.pathname.startsWith(to) ? 'bg-black text-white' : 'hover:bg-gray-100 text-gray-700'}`}>
              <Icon size={16} /> {label}
            </Link>
          ))}
        </nav>
        <button onClick={() => { logout(); navigate('/login') }}
          className="flex items-center gap-2 p-4 text-sm text-gray-500 hover:text-black border-t">
          <LogOut size={16} /> {t('nav.logout')}
        </button>
      </aside>
      <main className="flex-1 overflow-auto p-6">{children}</main>
    </div>
  )
}
