import { UserButton } from '@clerk/react'
import { ChartNoAxesColumnIncreasing, FileText, House, Settings, Users } from 'lucide-react'
import { NavLink, Outlet } from 'react-router'

import { useMe } from './api/users'
import { authEnabled } from './auth/authConfig'

const NAV_ITEMS = [
  { to: '/', label: 'ダッシュボード', icon: House, end: true },
  { to: '/customers', label: '顧客', icon: Users, end: false },
  { to: '/visits', label: '活動記録', icon: FileText, end: false },
  { to: '/map', label: 'エリア別', icon: ChartNoAxesColumnIncreasing, end: false },
]

export function AppLayout() {
  const me = useMe()
  const navItems =
    me.data?.role === 'manager'
      ? [...NAV_ITEMS, { to: '/admin/users', label: '管理', icon: Settings, end: false }]
      : NAV_ITEMS

  return (
    <div className="flex min-h-screen">
      {/* ── Sidebar ── */}
      <aside className="fixed inset-y-0 left-0 z-20 flex w-[220px] flex-col bg-[#1E2432]">
        {/* Logo */}
        <div className="flex items-center gap-2.5 border-b border-white/[0.06] px-5 py-[15px]">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[6px] bg-[#1D4ED8] text-sm font-bold text-white">
            S
          </div>
          <span className="text-sm font-semibold tracking-[-0.01em] text-white">
            Saleslog
          </span>
        </div>

        {/* Nav */}
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

        {/* User */}
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

      {/* ── Main ── */}
      <div className="ml-[220px] flex min-h-screen flex-1 flex-col bg-[#F5F7FA]">
        <main className="px-10 py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
