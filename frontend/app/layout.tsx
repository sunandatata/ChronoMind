import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'ChronoMind — Temporal Memory Engine',
  description: 'Query your personal memory graph across time',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  )
}
