import { NextResponse } from 'next/server'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const dynamic = 'force-dynamic'

export async function GET(_: Request, { params }: { params: { concept: string } }) {
  const response = await fetch(`${API_URL}/api/belief/${encodeURIComponent(params.concept)}`, { cache: 'no-store' })
  const data = await response.json()
  return NextResponse.json(data, { status: response.status })
}
