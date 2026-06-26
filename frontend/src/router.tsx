import { createBrowserRouter } from 'react-router'

import { AppLayout } from './AppLayout'
import { AdminUsersPage } from './pages/admin/AdminUsersPage'
import { DashboardPage } from './pages/DashboardPage'
import { CustomerDetailPage } from './pages/customers/CustomerDetailPage'
import { CustomersListPage } from './pages/customers/CustomersListPage'
import { MapBoardPage } from './pages/map/MapBoardPage'
import { VisitFormPage } from './pages/visits/VisitFormPage'
import { VisitsListPage } from './pages/visits/VisitsListPage'

// ルート構成は公開仕様の画面一覧に合わせる
export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'customers', element: <CustomersListPage /> },
      { path: 'customers/:id', element: <CustomerDetailPage /> },
      { path: 'visits', element: <VisitsListPage /> },
      { path: 'visits/new', element: <VisitFormPage /> },
      { path: 'visits/:id/edit', element: <VisitFormPage /> },
      { path: 'map', element: <MapBoardPage /> },
      { path: 'admin/users', element: <AdminUsersPage /> },
    ],
  },
])
