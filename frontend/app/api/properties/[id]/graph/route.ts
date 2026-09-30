import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = process.env.BACKEND_URL || 'http://127.0.0.1:8001'

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params
  if (!id) return NextResponse.json({ error: 'Missing property ID' }, { status: 400 })

  try {
    const response = await fetch(`${BACKEND_URL}/v1/properties/${encodeURIComponent(id)}/graph`, {
      headers: { Accept: 'application/json' },
      cache: 'no-store',
    })
    const data = await response.json().catch(() => ({ error: 'Invalid backend response' }))
    return NextResponse.json(data, { status: response.status })
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Failed to fetch property graph' },
      { status: 500 },
    )
  }
}
