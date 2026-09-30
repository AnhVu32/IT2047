// Client helper for recording user interactions (view/save/unsave/contact/share/thumbs).
// Attaches the bearer token when logged in; otherwise sends a stable anonymous
// session_id so the signal is still grouped. Fire-and-forget, never throws.
import { authHeaders, getStoredToken } from "./auth-context"

export type InteractionAction =
  | "view"
  | "save"
  | "unsave"
  | "contact"
  | "share"
  | "thumbs_up"
  | "thumbs_down"

const SESSION_KEY = "feedback_session_id"

function getSessionId(): string {
  if (typeof window === "undefined") return "server"
  let sid = window.localStorage.getItem(SESSION_KEY)
  if (!sid) {
    sid =
      (typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : Math.random().toString(36).slice(2)) as string
    window.localStorage.setItem(SESSION_KEY, sid)
  }
  return sid
}

export interface InteractionInput {
  listing_id: number | string
  action_type: InteractionAction
  source?: string
  dwell_time_seconds?: number
  raw_query?: string
  conversation_id?: number
}

export async function sendInteraction(input: InteractionInput): Promise<void> {
  const listingId = Number(input.listing_id)
  // A non-numeric id (e.g. a slug) would 400 the backend on a fire-and-forget
  // call and be lost silently — drop it here with a dev warning instead.
  if (!Number.isFinite(listingId)) {
    if (typeof console !== "undefined") {
      console.warn("[feedback] skipped interaction with non-numeric listing_id:", input.listing_id)
    }
    return
  }
  try {
    const token = getStoredToken()
    const body: Record<string, unknown> = { ...input, listing_id: listingId }
    if (!token) body.session_id = getSessionId()

    await fetch("/api/feedback", {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify(body),
      keepalive: true, // allow the request to complete during page unload
    })
  } catch {
    // Feedback is best-effort; ignore network errors.
  }
}

// --- Saved-listing state (backs the heart button's initial filled state) -------

// Cached per token so a login/logout refetches; a list of many cards then shares
// one request instead of one per card.
let cacheToken: string | null = null
let savedCache: Promise<Set<number>> | null = null

export async function getSavedListingIds(): Promise<Set<number>> {
  if (typeof window === "undefined") return new Set()
  const token = getStoredToken()
  if (!token) {
    savedCache = null
    cacheToken = null
    return new Set()
  }
  if (!savedCache || cacheToken !== token) {
    cacheToken = token
    savedCache = fetch("/api/feedback/saved", { headers: authHeaders() })
      .then(async (res) => {
        if (!res.ok) return new Set<number>()
        const data = await res.json()
        const ids: unknown = data?.data
        return new Set<number>(Array.isArray(ids) ? ids.map(Number) : [])
      })
      .catch(() => new Set<number>())
  }
  return savedCache
}

// Toggle a listing's saved state: records save/unsave and keeps the cache in sync.
export async function setSavedListing(
  listingId: number | string,
  saved: boolean,
  source?: string,
): Promise<void> {
  const id = Number(listingId)
  if (!Number.isFinite(id)) return
  if (savedCache) {
    const set = await savedCache
    if (saved) set.add(id)
    else set.delete(id)
  }
  await sendInteraction({ listing_id: id, action_type: saved ? "save" : "unsave", source })
}
