import type { ReactNode } from 'react'

export function Layout({
  header,
  children,
}: {
  header: ReactNode
  children: ReactNode
}) {
  return (
    <div className="flex h-full min-h-screen flex-col">
      {header}
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-0 lg:grid-cols-2 xl:grid-cols-4 xl:gap-px xl:bg-zinc-800">
        {children}
      </div>
    </div>
  )
}
