"use client"

import { Search, X } from "lucide-react"
import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"

interface SearchBarProps {
  /** The query currently applied to the listings; the input follows it when it is cleared elsewhere. */
  query?: string
  onSearch?: (query: string) => void
}

export function SearchBar({ query = "", onSearch }: SearchBarProps) {
  const [searchInput, setSearchInput] = useState(query)

  useEffect(() => {
    setSearchInput(query)
  }, [query])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    // An empty submit clears the keyword filter instead of being ignored.
    onSearch?.(searchInput.trim())
  }

  return (
    <form
      onSubmit={handleSubmit}
      role="search"
      className="flex items-center gap-2 rounded-xl bg-card p-2 shadow-lg ring-1 ring-black/5"
    >
      <div className="relative flex flex-1 items-center">
        <Search className="pointer-events-none absolute left-3 h-5 w-5 text-muted-foreground" />
        <input
          type="text"
          aria-label="Tìm kiếm bất động sản"
          placeholder="Tên dự án, đường, phường hoặc từ khóa..."
          className="h-11 w-full rounded-lg bg-transparent pl-11 pr-9 text-[15px] text-foreground outline-none placeholder:text-muted-foreground"
          suppressHydrationWarning
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
        />
        {searchInput && (
          <button
            type="button"
            aria-label="Xóa từ khóa"
            className="absolute right-2 rounded-full p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
            onClick={() => {
              setSearchInput("")
              if (query) onSearch?.("")
            }}
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
      <Button type="submit" className="h-11 px-6">
        Tìm kiếm
      </Button>
    </form>
  )
}
