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
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-0 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.9fr)_minmax(0,1.05fr)] lg:gap-px lg:bg-zinc-800">
        {children}
      </div>
    </div>
  )
}
