import { UserButton } from '@clerk/react'
import {
  ChartNoAxesColumnIncreasing,
  FileText,
  House,
  Menu,
  Settings,
  Users,
  X,
} from 'lucide-react'
import { useCallback, useEffect, useId, useRef, useState, useSyncExternalStore } from 'react'
import { NavLink, Outlet } from 'react-router'

import { useMe } from './api/users'
import { authEnabled } from './auth/authConfig'
import { STATIC_DEMO_CLOCK_LABEL_JST, staticDemoEnabled } from './demoMode'

const NAV_ITEMS = [
  { to: '/', label: 'ダッシュボード', icon: House, end: true },
  { to: '/customers', label: '顧客', icon: Users, end: false },
  { to: '/visits', label: '活動記録', icon: FileText, end: false },
  { to: '/map', label: 'エリア別', icon: ChartNoAxesColumnIncreasing, end: false },
]

const DESKTOP_VIEWPORT_QUERY = '(min-width: 768px)'

function subscribeDesktopViewport(onChange: () => void) {
  const mediaQuery = window.matchMedia(DESKTOP_VIEWPORT_QUERY)
  mediaQuery.addEventListener('change', onChange)
  return () => mediaQuery.removeEventListener('change', onChange)
}

function getDesktopViewportSnapshot() {
  return window.matchMedia(DESKTOP_VIEWPORT_QUERY).matches
}

export function AppLayout() {
  const me = useMe()
  const navId = useId()
  const openButtonRef = useRef<HTMLButtonElement>(null)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const desktopViewport = useSyncExternalStore(
    subscribeDesktopViewport,
    getDesktopViewportSnapshot,
    () => false,
  )
  const navItems =
    me.data?.role === 'manager'
      ? [...NAV_ITEMS, { to: '/admin/users', label: '管理', icon: Settings, end: false }]
      : NAV_ITEMS

  const closeMobileNav = useCallback(() => {
    if (!mobileNavOpen) return
    setMobileNavOpen(false)
    openButtonRef.current?.focus()
  }, [mobileNavOpen])

  useEffect(() => {
    if (!mobileNavOpen) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        closeMobileNav()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [closeMobileNav, mobileNavOpen])

  return (
    <div className="flex min-h-screen">
      {mobileNavOpen && (
        <button
          type="button"
          aria-label="メニューを閉じる"
          className="fixed inset-0 z-30 bg-slate-900/40 md:hidden"
          onClick={closeMobileNav}
        />
      )}

      <aside
        id={navId}
        inert={!desktopViewport && !mobileNavOpen}
        className={`fixed inset-y-0 left-0 z-40 flex w-[220px] flex-col bg-[#1E2432] transition-transform duration-200 md:translate-x-0 ${
          mobileNavOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between gap-2.5 border-b border-white/[0.06] px-5 py-[15px]">
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[6px] bg-[#1D4ED8] text-sm font-bold text-white">
              S
            </div>
            <span className="text-sm font-semibold tracking-[-0.01em] text-white">
              Saleslog
            </span>
          </div>
          <button
            type="button"
            className="rounded-[6px] p-1.5 text-[#D6DEEF] hover:bg-white/[0.08] md:hidden"
            aria-label="メニューを閉じる"
            onClick={closeMobileNav}
          >
            <X aria-hidden="true" className="h-4 w-4" strokeWidth={2} />
          </button>
        </div>

        <nav aria-label="メイン" className="flex flex-1 flex-col gap-0.5 overflow-y-auto p-2.5">
          <p className="mt-1 px-2.5 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-[0.1em] text-[#B8C4DD]">
            メイン
          </p>
          {navItems.map((item) => {
            const Icon = item.icon
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                onClick={closeMobileNav}
                className={({ isActive }) =>
                  `flex items-center gap-2.5 rounded-[7px] py-2 text-[13px] font-medium transition-colors duration-100 ${
                    isActive
                      ? 'border-l-[3px] border-[#1D4ED8] bg-[rgba(61,111,255,0.18)] pl-[7px] pr-2.5 text-[#D7E2FF]'
                      : 'px-2.5 text-[#D6DEEF] hover:bg-white/[0.06] hover:text-white'
                  }`
                }
              >
                <Icon aria-hidden="true" className="h-[15px] w-[15px] shrink-0" strokeWidth={2} />
                {item.label}
              </NavLink>
            )
          })}
        </nav>

        {authEnabled && (
          <div className="flex items-center gap-2.5 border-t border-white/[0.07] p-3.5">
            <UserButton />
            {me.data !== undefined && (
              <div className="min-w-0">
                <p className="truncate text-xs font-medium text-[#E2E8F0]">
                  {me.data.name}
                </p>
                <p className="mt-0.5 text-[10px] text-[#B8C4DD]">
                  {me.data.role === 'manager' ? 'Manager' : 'Sales'}
                </p>
              </div>
            )}
          </div>
        )}
      </aside>

      <div className="flex min-h-screen w-full min-w-0 flex-1 flex-col bg-[#F5F7FA] md:ml-[220px]">
        <div className="flex items-center gap-3 border-b border-slate-200/80 bg-white px-4 py-3 md:hidden">
          <button
            ref={openButtonRef}
            type="button"
            className="rounded-[7px] border border-slate-200 bg-white p-2 text-slate-700"
            aria-label="メニューを開く"
            aria-expanded={mobileNavOpen}
            aria-controls={navId}
            onClick={() => setMobileNavOpen(true)}
          >
            <Menu aria-hidden="true" className="h-4 w-4" strokeWidth={2} />
          </button>
          <span className="text-sm font-semibold text-slate-800">Saleslog</span>
        </div>
        {staticDemoEnabled && (
          <div className="border-b border-blue-100 bg-blue-50 px-4 py-2 text-[12px] text-blue-900 md:px-10">
            静的UIデモです。保存・認証・外部LLM実行は行わず、合成データとデモ用応答で画面遷移を確認できます。画面上の「今日」はデモ基準日{' '}
            {STATIC_DEMO_CLOCK_LABEL_JST} です。
          </div>
        )}
        <main className="min-w-0 px-4 py-6 md:px-10 md:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
