export async function DELETE(_: Request, { params }: { params: { session_id: string } }) {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
  const res = await fetch(`${baseUrl}/api/sessions/${params.session_id}`, { method: 'DELETE' })
  const text = await res.text()
  return new Response(text, { status: res.status, headers: { 'content-type': 'application/json' } })
}

