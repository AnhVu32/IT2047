'use client'

interface DescriptionSectionProps {
  description: string
}

export function DescriptionSection({ description }: DescriptionSectionProps) {
  return (
    <div className="space-y-3 pb-4 border-b border-border">
      <h2 className="text-xl font-bold text-foreground">Mô tả chi tiết</h2>
      <div className="prose prose-sm max-w-none text-muted-foreground leading-relaxed whitespace-pre-wrap">
        {description}
      </div>
    </div>
  )
}
