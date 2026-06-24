import { NextRequest, NextResponse } from 'next/server'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const dynamic = 'force-dynamic'

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url)
  const concept = searchParams.get('concept') || ''
  const response = await fetch(`${API_URL}/api/timeline/${encodeURIComponent(concept)}`, { cache: 'no-store' })
  const data = await response.json()
  return NextResponse.json(data, { status: response.status })
}
