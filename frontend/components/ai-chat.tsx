"use client"

import { useState, useRef, useEffect, useCallback } from "react"
import { Send, Bot, User, Loader2, Sparkles, Plus, MessageSquare, ThumbsUp, ThumbsDown } from "lucide-react"
import ReactMarkdown, { type Components } from "react-markdown"
import remarkGfm from "remark-gfm"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { PropertyCard } from "@/components/property-card"
import { useAuth, authHeaders } from "@/lib/auth-context"
import { sendInteraction } from "@/lib/feedback"

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
}

interface ConversationSummary {
  id: number
  title: string | null
}

interface AIChatProps {
  filters?: any
}

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
      className="text-[#C9342A] underline underline-offset-2 hover:text-[#A92A22]"
    >
      {children}
    </a>
  ),
  blockquote: ({ children, ...props }) => (
    <blockquote {...props} className="border-l-2 border-[#E03C31]/50 pl-3 italic text-muted-foreground">
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

export function AIChat({ filters: propFilters = {} }: AIChatProps) {
  const { user } = useAuth()
  const [messages, setMessages] = useState<ChatMessage[]>([{ ...WELCOME, timestamp: nowTime() }])
  const [inputValue, setInputValue] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [conversationId, setConversationId] = useState<number | null>(null)
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const [guestContextListingIds, setGuestContextListingIds] = useState<string[]>([])
  const [guestContextParsedQuery, setGuestContextParsedQuery] = useState<any>(null)
  const currentFilters = propFilters
  const messagesEndRef = useRef<HTMLDivElement>(null)

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
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!inputValue.trim()) return

    const userQuestion = inputValue
    const guestHistory = messages
      .filter((item) => item.content && !(item.role === "ai" && item.content === WELCOME.content))
      .slice(-20)
      .map((item) => ({ role: item.role === "ai" ? "assistant" : "user", content: item.content! }))
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
        }
        return updated
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleThumb = (property: PropertyResult, up: boolean) => {
    sendInteraction({
      listing_id: property.listing_id ?? property.id,
      action_type: up ? "thumbs_up" : "thumbs_down",
      source: "chat",
      conversation_id: conversationId ?? undefined,
    })
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Chat Header */}
      <div className="shrink-0 flex items-center gap-3 px-4 py-3 bg-background border-b border-border">
        <div className="w-10 h-10 rounded-full bg-[#E03C31]/10 flex items-center justify-center">
          <Bot className="w-5 h-5 text-[#E03C31]" />
        </div>
        <div className="flex-1">
          <h3 className="font-semibold text-foreground">AI Real Estate Assistant</h3>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
            <span className="text-xs text-emerald-600">Đang trực tuyến</span>
          </div>
        </div>
        {user && (
          <Button type="button" variant="outline" size="sm" onClick={startNewChat} className="text-xs">
            <Plus className="h-3.5 w-3.5 mr-1" />
            Cuộc trò chuyện mới
          </Button>
        )}
      </div>

      {/* Conversation history (logged-in only) */}
      {user && conversations.length > 0 && (
        <div className="shrink-0 flex gap-2 overflow-x-auto px-4 py-2 border-b border-border bg-muted/30">
          {conversations.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => openConversation(c.id)}
              className={`flex items-center gap-1.5 whitespace-nowrap text-xs px-2.5 py-1.5 rounded-full border transition-colors ${
                c.id === conversationId
                  ? "bg-[#E03C31] text-white border-[#E03C31]"
                  : "bg-background text-foreground border-border hover:bg-muted"
              }`}
            >
              <MessageSquare className="h-3 w-3" />
              {c.title || `Cuộc trò chuyện ${c.id}`}
            </button>
          ))}
        </div>
      )}

      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message, idx) => (
          <div key={idx} className={`flex gap-3 ${message.role === "user" ? "justify-end" : "justify-start"}`}>
            {message.role === "ai" && (
              <div className="w-8 h-8 rounded-full bg-[#E03C31]/10 flex items-center justify-center flex-shrink-0">
                <Bot className="w-4 h-4 text-[#E03C31]" />
              </div>
            )}

            <div className={`max-w-[75%] ${message.role === "user" ? "order-1" : ""}`}>
              <div
                className={`rounded-2xl px-4 py-3 ${
                  message.role === "user"
                    ? "bg-[#E03C31] text-white rounded-tr-sm"
                    : "bg-muted text-foreground rounded-tl-sm"
                }`}
              >
                {message.role === "ai" ? (
                  <MarkdownMessage content={message.content || ""} />
                ) : (
                  <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.content}</p>
                )}
              </div>

              {/* Properties Grid */}
              {message.properties && message.properties.length > 0 && (
                <div className="mt-3 space-y-3 pr-2">
                  {message.properties.slice(0, 3).map((property) => (
                    <div key={property.id} className="flex flex-col gap-3 mb-6">
                      <PropertyCard property={property as any} />

                      {(property.explanation || property.comparison) && (
                        <div className="bg-muted/50 rounded-lg p-4 text-sm text-foreground border border-border">
                          <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-2">
                              <Sparkles className="w-4 h-4 text-[#E03C31]" />
                              <span className="font-semibold">AI Insights</span>
                            </div>
                            {/* Explicit feedback on this recommendation */}
                            <div className="flex items-center gap-1">
                              <button
                                type="button"
                                aria-label="Hữu ích"
                                className="p-1 rounded hover:bg-muted"
                                onClick={() => handleThumb(property, true)}
                              >
                                <ThumbsUp className="w-4 h-4 text-muted-foreground hover:text-emerald-600" />
                              </button>
                              <button
                                type="button"
                                aria-label="Không phù hợp"
                                className="p-1 rounded hover:bg-muted"
                                onClick={() => handleThumb(property, false)}
                              >
                                <ThumbsDown className="w-4 h-4 text-muted-foreground hover:text-[#E03C31]" />
                              </button>
                            </div>
                          </div>

                          {property.explanation && (
                            <div className="mb-3">
                              <span className="font-semibold">💡 Lý do đề xuất:</span>
                              <p className="mt-1 text-muted-foreground">{property.explanation}</p>
                            </div>
                          )}

                          {property.comparison && (
                            <div>
                              <span className="font-semibold">⚖️ Đánh giá:</span>
                              <p className="mt-1 text-muted-foreground">{property.comparison}</p>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              <p
                className={`text-[10px] mt-1 ${
                  message.role === "user" ? "text-right text-muted-foreground" : "text-muted-foreground"
                }`}
              >
                {message.timestamp}
              </p>
            </div>

            {message.role === "user" && (
              <div className="w-8 h-8 rounded-full bg-[#E03C31] flex items-center justify-center flex-shrink-0">
                <User className="w-4 h-4 text-white" />
              </div>
            )}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="shrink-0 border-t border-border p-4 bg-background">
        <form onSubmit={handleSubmit} className="flex items-center gap-2">
          <Input
            placeholder="Hỏi AI bất cứ điều gì về nhà đất..."
            className="flex-1 h-10"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            disabled={isLoading}
          />
          <Button
            type="submit"
            size="icon"
            className="h-10 w-10 bg-[#E03C31] hover:bg-[#c43428] flex-shrink-0 disabled:opacity-50"
            disabled={isLoading || !inputValue.trim()}
          >
            {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </Button>
        </form>
      </div>
    </div>
  )
}
