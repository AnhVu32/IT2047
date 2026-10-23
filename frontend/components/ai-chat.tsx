"use client"

import { useState, useRef, useEffect, useCallback } from "react"
import { Send, Loader2, Sparkles, Plus, MessageSquare, ThumbsUp, ThumbsDown, SlidersHorizontal, Lightbulb, Scale } from "lucide-react"
import ReactMarkdown, { type Components } from "react-markdown"
import remarkGfm from "remark-gfm"
import { Button } from "@/components/ui/button"
import { PropertyCard } from "@/components/property-card"
import { useAuth, authHeaders } from "@/lib/auth-context"
import { sendInteraction } from "@/lib/feedback"
import { cn } from "@/lib/utils"

interface PropertyResult {
  id: string
  listing_id?: number | string
  explanation?: string
  comparison?: string
  [key: string]: any
}

interface ChatMessage {
  role: "user" | "ai"
  content?: string
  properties?: PropertyResult[]
  timestamp: string
  // Client-side error notices are UI only and must not be replayed as history.
  isError?: boolean
}

interface ConversationSummary {
  id: number
  title: string | null
}

// Mirrors ClientHistoryTurn.content max_length in the backend chat endpoint.
const HISTORY_CONTENT_MAX = 4000

// Chat survives reloads and navigating to a listing and back (per tab).
const STORAGE_PREFIX = "ai-chat:v1:"
const STORED_MESSAGES_MAX = 30

interface StoredChat {
  conversationId?: number | null
  messages?: ChatMessage[]
  guestContextListingIds?: string[]
  guestContextParsedQuery?: any
}

function readStoredChat(key: string): StoredChat | null {
  try {
    const raw = window.sessionStorage.getItem(key)
    return raw ? (JSON.parse(raw) as StoredChat) : null
  } catch {
    return null
  }
}

function writeStoredChat(key: string, value: StoredChat) {
  try {
    window.sessionStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Storage may be full or blocked; the chat still works without persistence.
  }
}

interface AIChatProps {
  filters?: any
  /** Human-readable summary of the applied criteria, shown above the conversation. */
  criteria?: string[]
  onEditCriteria?: () => void
}

const SUGGESTED_PROMPTS = [
  "Căn hộ 2 phòng ngủ dưới 4 tỷ, gần metro",
  "Nhà phố sổ hồng riêng ở Gò Vấp, khoảng 60–80 m²",
  "Căn hộ có hồ bơi, gym, phù hợp gia đình có trẻ nhỏ",
  "Ngân sách 5 tỷ nên mua căn hộ hay nhà đất?",
]

const WELCOME: ChatMessage = {
  role: "ai",
  content:
    "Xin chào! Tôi là trợ lý AI chuyên về bất động sản. Dựa trên các tiêu chí bạn đang nhập, tôi có thể giúp bạn tìm căn hộ hoặc nhà phố phù hợp nhất. Bạn muốn tôi gợi ý Căn hộ/Nhà đất như thế nào?",
  timestamp: "",
}

function nowTime() {
  return new Date().toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })
}

// Format a stored ISO timestamp; fall back to "now" for live messages.
function formatTime(value?: string) {
  if (!value) return nowTime()
  const date = new Date(value)
  return isNaN(date.getTime())
    ? nowTime()
    : date.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })
}

const markdownComponents: Components = {
  a: ({ children, ...props }) => (
    <a
      {...props}
      target="_blank"
      rel="noopener noreferrer"
      className="font-medium text-primary underline underline-offset-2 hover:opacity-80"
    >
      {children}
    </a>
  ),
  blockquote: ({ children, ...props }) => (
    <blockquote {...props} className="border-l-2 border-primary/50 pl-3 italic text-muted-foreground">
      {children}
    </blockquote>
  ),
  code: ({ children, className, ...props }) => {
    const isBlock = className?.startsWith("language-")
    return (
      <code
        {...props}
        className={
          isBlock
            ? `${className} block min-w-max text-xs`
            : "rounded bg-background/80 px-1 py-0.5 font-mono text-[0.85em]"
        }
      >
        {children}
      </code>
    )
  },
  pre: ({ children, ...props }) => (
    <pre {...props} className="overflow-x-auto rounded-lg bg-background p-3 font-mono text-xs">
      {children}
    </pre>
  ),
  table: ({ children, ...props }) => (
    <div className="overflow-x-auto">
      <table {...props} className="w-full border-collapse text-left text-xs">
        {children}
      </table>
    </div>
  ),
  th: ({ children, ...props }) => (
    <th {...props} className="border border-border bg-background/70 px-2 py-1.5 font-semibold">
      {children}
    </th>
  ),
  td: ({ children, ...props }) => (
    <td {...props} className="border border-border px-2 py-1.5 align-top">
      {children}
    </td>
  ),
}

function MarkdownMessage({ content }: { content: string }) {
  return (
    <div className="text-sm leading-relaxed [&>*:first-child]:mt-0 [&>*:last-child]:mb-0 [&_h1]:my-3 [&_h1]:text-lg [&_h1]:font-bold [&_h2]:my-3 [&_h2]:text-base [&_h2]:font-bold [&_h3]:my-2 [&_h3]:font-semibold [&_hr]:my-3 [&_hr]:border-border [&_li]:my-1 [&_ol]:my-2 [&_ol]:list-decimal [&_ol]:pl-5 [&_p]:my-2 [&_ul]:my-2 [&_ul]:list-disc [&_ul]:pl-5">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
        {content}
      </ReactMarkdown>
    </div>
  )
}

export function AIChat({ filters: propFilters = {}, criteria = [], onEditCriteria }: AIChatProps) {
  const { user, loading: authLoading } = useAuth()
  const [messages, setMessages] = useState<ChatMessage[]>([{ ...WELCOME, timestamp: nowTime() }])
  const [inputValue, setInputValue] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [conversationId, setConversationId] = useState<number | null>(null)
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const [guestContextListingIds, setGuestContextListingIds] = useState<string[]>([])
  const [guestContextParsedQuery, setGuestContextParsedQuery] = useState<any>(null)
  const currentFilters = propFilters
  // Logged-in and guest chats are stored separately so switching account never leaks one into the other.
  const identity = user ? `user:${user.id}` : "guest"
  const storageKey = STORAGE_PREFIX + identity
  const [hydratedIdentity, setHydratedIdentity] = useState<string | null>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  // Per-listing thumbs state so the user sees their feedback was recorded.
  const [thumbs, setThumbs] = useState<Record<string, "up" | "down">>({})

  const loadConversations = useCallback(async () => {
    if (!user) return
    try {
      const res = await fetch("/api/chat/conversations", { headers: authHeaders() })
      if (!res.ok) return
      const data = await res.json()
      setConversations(data.data || [])
    } catch {
      // ignore
    }
  }, [user])

  // Load the conversation list when the user logs in.
  useEffect(() => {
    if (user) loadConversations()
    else {
      setConversations([])
      setConversationId(null)
      setGuestContextListingIds([])
      setGuestContextParsedQuery(null)
    }
  }, [user, loadConversations])

  // Auto scroll to bottom
  useEffect(() => {
    // Scroll only the message list; scrollIntoView would also shift the page's overflow-hidden ancestors.
    const container = messagesContainerRef.current
    container?.scrollTo({ top: container.scrollHeight, behavior: "smooth" })
  }, [messages])

  const startNewChat = () => {
    setConversationId(null)
    setGuestContextListingIds([])
    setGuestContextParsedQuery(null)
    setMessages([{ ...WELCOME, timestamp: nowTime() }])
  }

  const openConversation = async (id: number) => {
    try {
      const res = await fetch(`/api/chat/conversations/${id}`, { headers: authHeaders() })
      if (!res.ok) return
      const data = await res.json()
      const rehydrated: ChatMessage[] = (data.data?.messages || []).map((m: any) => ({
        role: m.role === "assistant" ? "ai" : "user",
        content: m.content,
        properties: Array.isArray(m.results) && m.results.length > 0 ? m.results : undefined,
        timestamp: formatTime(m.created_at),
      }))
      setConversationId(id)
      setMessages(rehydrated.length > 0 ? rehydrated : [{ ...WELCOME, timestamp: nowTime() }])
    } catch {
      // ignore
    }
  }

  // Restore the saved chat once auth is known, and start clean when the account changes.
  useEffect(() => {
    if (authLoading || hydratedIdentity === identity) return
    if (hydratedIdentity !== null) {
      setConversationId(null)
      setGuestContextListingIds([])
      setGuestContextParsedQuery(null)
      setMessages([{ ...WELCOME, timestamp: nowTime() }])
    }
    const saved = readStoredChat(storageKey)
    if (saved) {
      if (user) {
        if (saved.conversationId) openConversation(saved.conversationId)
      } else {
        if (saved.messages?.length) setMessages(saved.messages)
        setGuestContextListingIds(saved.guestContextListingIds || [])
        setGuestContextParsedQuery(saved.guestContextParsedQuery ?? null)
      }
    }
    setHydratedIdentity(identity)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoading, identity])

  // Persist after each completed turn (never the transient "Đang xử lý..." placeholder).
  useEffect(() => {
    if (authLoading || hydratedIdentity !== identity || isLoading) return
    writeStoredChat(
      storageKey,
      user
        ? { conversationId }
        : {
            messages: messages.slice(-STORED_MESSAGES_MAX),
            guestContextListingIds,
            guestContextParsedQuery,
          },
    )
  }, [authLoading, hydratedIdentity, identity, isLoading, user, storageKey, conversationId, messages, guestContextListingIds, guestContextParsedQuery])

  const applyResponse = (data: any) => {
    const properties: PropertyResult[] = data.data?.results || []
    const assistantAnswer = data.data?.assistant_answer
    const searchPerformed = Boolean(data.data?.search_performed)
    setMessages((prev) => {
      const updated = [...prev]
      updated[updated.length - 1] = {
        role: "ai",
        content:
          assistantAnswer || "Tôi chưa thể trả lời ngay lúc này. Bạn thử diễn đạt lại giúp tôi nhé.",
        properties: searchPerformed && properties.length > 0 ? properties : undefined,
        timestamp: nowTime(),
      }
      return updated
    })
    if (data.data?.conversation_id) setConversationId(data.data.conversation_id)
    // Guest context is a list of server-issued IDs only. The backend rehydrates
    // those IDs rather than trusting listing fields sent from the browser.
    if (!user && properties.length > 0) {
      setGuestContextListingIds(
        properties
          .map((property) => property.listing_id)
          .filter((id) => id !== undefined && id !== null)
          .slice(0, 20)
          .map(String),
      )
      if (data.data?.parsed_query) setGuestContextParsedQuery(data.data.parsed_query)
    }
  }

  const sendMessage = async (text: string) => {
    if (!text.trim() || isLoading) return

    const userQuestion = text
    const guestHistory = messages
      .filter((item) => item.content && !item.isError && !(item.role === "ai" && item.content === WELCOME.content))
      .slice(-20)
      .map((item) => ({
        role: item.role === "ai" ? "assistant" : "user",
        content: item.content!.slice(0, HISTORY_CONTENT_MAX),
      }))
    setMessages((prev) => [
      ...prev,
      { role: "user", content: userQuestion, timestamp: nowTime() },
      { role: "ai", content: "Đang xử lý...", timestamp: nowTime() },
    ])
    setInputValue("")
    setIsLoading(true)

    try {
      const payload = user
        ? { message: userQuestion, conversation_id: conversationId, top_k: 3, filters: currentFilters }
        : {
            message: userQuestion,
            top_k: 3,
            filters: currentFilters,
            history: guestHistory,
            context_listing_ids: guestContextListingIds,
            context_parsed_query: guestContextParsedQuery,
          }

      const response = await fetch("/api/chat", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify(payload),
      })
      if (!response.ok) throw new Error(`API Error: ${response.status}`)
      const data = await response.json()
      applyResponse(data)
      if (user) loadConversations()
    } catch (error) {
      setMessages((prev) => {
        const updated = [...prev]
        updated[updated.length - 1] = {
          role: "ai",
          content: "Xin lỗi, đã xảy ra lỗi khi xử lý tin nhắn. Vui lòng thử lại sau.",
          timestamp: nowTime(),
          isError: true,
        }
        return updated
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    sendMessage(inputValue)
  }

  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter sends, Shift+Enter inserts a newline; ignore Enter while composing Vietnamese IME input.
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      sendMessage(inputValue)
    }
  }

  const handleThumb = (property: PropertyResult, up: boolean) => {
    setThumbs((prev) => ({ ...prev, [String(property.listing_id ?? property.id)]: up ? "up" : "down" }))
    sendInteraction({
      listing_id: property.listing_id ?? property.id,
      action_type: up ? "thumbs_up" : "thumbs_down",
      source: "chat",
      conversation_id: conversationId ?? undefined,
    })
  }

  const isFreshChat = messages.length === 1 && messages[0].role === "ai" && messages[0].content === WELCOME.content

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Chat Header */}
      <div className="shrink-0 flex items-center gap-3 px-4 py-3 bg-card border-b border-border">
        <div className="w-10 h-10 rounded-full bg-primary text-primary-foreground flex items-center justify-center">
          <Sparkles className="w-5 h-5" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-foreground leading-tight">Trợ lý tư vấn bất động sản</h3>
          <p className="text-xs text-muted-foreground truncate">Mô tả nhu cầu, trợ lý sẽ gợi ý và giải thích lý do</p>
        </div>
        {onEditCriteria && (
          <Button type="button" variant="outline" size="sm" onClick={onEditCriteria} className="lg:hidden">
            <SlidersHorizontal className="h-4 w-4" />
            <span className="hidden sm:inline">Tiêu chí</span>
            {criteria.length > 0 && (
              <span className="rounded-full bg-primary px-1.5 text-xs text-primary-foreground">{criteria.length}</span>
            )}
          </Button>
        )}
        {!isFreshChat && (
          <Button type="button" variant="outline" size="sm" onClick={startNewChat} disabled={isLoading} aria-label="Cuộc trò chuyện mới">
            <Plus className="h-4 w-4" />
            <span className="hidden sm:inline">Cuộc trò chuyện mới</span>
          </Button>
        )}
      </div>

      {/* Conversation history (logged-in only) */}
      {user && conversations.length > 0 && (
        <div className="shrink-0 flex gap-2 overflow-x-auto px-4 py-2 border-b border-border bg-card">
          {conversations.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => openConversation(c.id)}
              // A pending reply is written into the last visible message, so switching
              // conversations mid-request would attach it to the wrong thread.
              disabled={isLoading}
              className={`flex max-w-56 items-center gap-1.5 whitespace-nowrap text-xs px-2.5 py-1.5 rounded-full border transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
                c.id === conversationId
                  ? "bg-primary text-primary-foreground border-primary"
                  : "bg-background text-foreground border-border hover:bg-muted"
              }`}
            >
              <MessageSquare className="h-3 w-3 shrink-0" />
              <span className="truncate">{c.title || `Cuộc trò chuyện ${c.id}`}</span>
            </button>
          ))}
        </div>
      )}

      {/* Applied criteria */}
      {criteria.length > 0 && (
        <div className="shrink-0 flex items-center gap-2 overflow-x-auto px-4 py-2 border-b border-border bg-accent/60 text-xs">
          <span className="shrink-0 font-medium text-accent-foreground">Tiêu chí:</span>
          {criteria.map((item) => (
            <span key={item} className="shrink-0 rounded-full border border-primary/20 bg-card px-2.5 py-1 text-foreground">
              {item}
            </span>
          ))}
        </div>
      )}

      {/* Chat Messages */}
      <div ref={messagesContainerRef} className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl space-y-5 px-4 py-6">
          {messages.map((message, idx) => {
            const isPending = isLoading && message.role === "ai" && idx === messages.length - 1
            return (
              <div key={idx} className={`flex gap-3 ${message.role === "user" ? "justify-end" : "justify-start"}`}>
                {message.role === "ai" && (
                  <div className="mt-0.5 w-8 h-8 rounded-full bg-secondary flex items-center justify-center flex-shrink-0">
                    <Sparkles className="w-4 h-4 text-primary" />
                  </div>
                )}

                <div className={cn("min-w-0", message.role === "user" ? "max-w-[85%] sm:max-w-[75%]" : "flex-1")}>
                  <div
                    className={cn(
                      "rounded-2xl px-4 py-3",
                      message.role === "user"
                        ? "ml-auto w-fit bg-primary text-primary-foreground rounded-tr-sm"
                        : "w-fit max-w-full bg-card border border-border text-foreground rounded-tl-sm",
                      message.isError && "border-destructive/30 bg-destructive/5",
                    )}
                  >
                    {isPending ? (
                      <span className="flex items-center gap-2 py-0.5 text-sm text-muted-foreground" role="status">
                        <span className="flex gap-1">
                          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:-0.3s]" />
                          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:-0.15s]" />
                          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary" />
                        </span>
                        Đang tìm và phân tích...
                      </span>
                    ) : message.role === "ai" ? (
                      <MarkdownMessage content={message.content || ""} />
                    ) : (
                      <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.content}</p>
                    )}
                  </div>

                  {/* Recommended properties */}
                  {message.properties && message.properties.length > 0 && (
                    <div className="mt-3 space-y-4">
                      {message.properties.slice(0, 3).map((property, rank) => {
                        const thumb = thumbs[String(property.listing_id ?? property.id)]
                        return (
                          <div key={property.id} className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
                            <div className="flex items-center justify-between gap-2 border-b border-border px-4 py-2">
                              <span className="text-xs font-semibold uppercase tracking-wide text-primary">Gợi ý #{rank + 1}</span>
                              {/* Explicit feedback on this recommendation */}
                              <div className="flex items-center gap-1">
                                <span className="mr-1 hidden text-xs text-muted-foreground sm:inline">
                                  {thumb ? "Cảm ơn phản hồi của bạn" : "Gợi ý này có phù hợp?"}
                                </span>
                                <button
                                  type="button"
                                  aria-label="Hữu ích"
                                  aria-pressed={thumb === "up"}
                                  className={cn("rounded-md p-1.5 transition-colors hover:bg-muted", thumb === "up" ? "text-primary" : "text-muted-foreground")}
                                  onClick={() => handleThumb(property, true)}
                                >
                                  <ThumbsUp className={cn("h-4 w-4", thumb === "up" && "fill-current")} />
                                </button>
                                <button
                                  type="button"
                                  aria-label="Không phù hợp"
                                  aria-pressed={thumb === "down"}
                                  className={cn("rounded-md p-1.5 transition-colors hover:bg-muted", thumb === "down" ? "text-destructive" : "text-muted-foreground")}
                                  onClick={() => handleThumb(property, false)}
                                >
                                  <ThumbsDown className={cn("h-4 w-4", thumb === "down" && "fill-current")} />
                                </button>
                              </div>
                            </div>

                            <div className="p-2 [&_article]:border-0 [&_article]:hover:translate-y-0 [&_article]:hover:shadow-none">
                              <PropertyCard property={property as any} />
                            </div>

                            {(property.explanation || property.comparison) && (
                              <div className="space-y-3 border-t border-border bg-accent/40 px-4 py-3 text-sm">
                                {property.explanation && (
                                  <div className="flex gap-2.5">
                                    <Lightbulb className="mt-0.5 h-4 w-4 flex-shrink-0 text-primary" />
                                    <div>
                                      <p className="font-semibold text-foreground">Lý do đề xuất</p>
                                      <p className="mt-0.5 text-muted-foreground">{property.explanation}</p>
                                    </div>
                                  </div>
                                )}
                                {property.comparison && (
                                  <div className="flex gap-2.5">
                                    <Scale className="mt-0.5 h-4 w-4 flex-shrink-0 text-primary" />
                                    <div>
                                      <p className="font-semibold text-foreground">Đánh giá</p>
                                      <p className="mt-0.5 text-muted-foreground">{property.comparison}</p>
                                    </div>
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  )}

                  {!isPending && (
                    <p className={`text-[10px] mt-1 text-muted-foreground ${message.role === "user" ? "text-right" : ""}`}>
                      {message.timestamp}
                    </p>
                  )}
                </div>
              </div>
            )
          })}

          {isFreshChat && (
            <div className="grid gap-2 pl-11 sm:grid-cols-2">
              {SUGGESTED_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => sendMessage(prompt)}
                  disabled={isLoading}
                  className="rounded-xl border border-border bg-card px-4 py-3 text-left text-sm text-foreground transition-colors hover:border-primary/40 hover:bg-accent disabled:opacity-50"
                >
                  {prompt}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Input Area */}
      <div className="shrink-0 border-t border-border bg-card px-4 pt-3 pb-2">
        <form
          onSubmit={handleSubmit}
          className="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border border-input bg-background p-1.5 pl-4 focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20"
        >
          <textarea
            rows={1}
            aria-label="Tin nhắn cho trợ lý"
            placeholder="Ví dụ: căn hộ 2PN ở Thủ Đức dưới 4 tỷ, gần trường học..."
            className="max-h-36 min-h-9 flex-1 resize-none bg-transparent py-2 text-sm outline-none [field-sizing:content] placeholder:text-muted-foreground disabled:opacity-50"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleInputKeyDown}
            disabled={isLoading}
          />
          <Button
            type="submit"
            size="icon"
            className="h-9 w-9 rounded-xl flex-shrink-0"
            disabled={isLoading || !inputValue.trim()}
            aria-label="Gửi"
          >
            {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </Button>
        </form>
        <p className="mx-auto mt-1.5 max-w-3xl text-center text-[11px] text-muted-foreground">
          Trợ lý AI có thể sai sót. Hãy kiểm tra pháp lý và thông tin thực tế trước khi giao dịch.
        </p>
      </div>
    </div>
  )
}
