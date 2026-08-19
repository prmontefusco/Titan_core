import { useState, type ReactNode } from 'react'
import { TopBar } from './TopBar'
import { Sidebar, type NavigationItem } from './Sidebar'
import type { UserAccountMenuProps } from './UserAccountMenu'

export interface ApplicationShellProps {
  organizationId: string
  userMenuProps: UserAccountMenuProps
  navigationItems: NavigationItem[]
  children: ReactNode
}

export function ApplicationShell({
  organizationId,
  userMenuProps,
  navigationItems,
  children,
}: ApplicationShellProps) {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)

  const toggleSidebar = () => setIsSidebarOpen((prev) => !prev)
  const closeSidebar = () => setIsSidebarOpen(false)

  return (
    <div className="app-shell">
      <TopBar
        organizationId={organizationId}
        userMenuProps={userMenuProps}
        onToggleSidebar={toggleSidebar}
        isSidebarOpen={isSidebarOpen}
      />

      <div className="app-body-layout">
        <Sidebar
          isOpen={isSidebarOpen}
          onClose={closeSidebar}
          items={navigationItems}
        />

        <main className="app-main-content" id="main-content" tabIndex={-1}>
          <div className="app-content-container">
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}
