interface DetailSectionProps {
  title: string
  description?: string
  id?: string
  action?: React.ReactNode
  children: React.ReactNode
}

export function DetailSection({ title, description, id, action, children }: DetailSectionProps) {
  return (
    <section id={id} className="scroll-mt-24 rounded-xl border border-border bg-card p-5 md:p-6">
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-lg font-bold text-foreground">{title}</h2>
          {description && <p className="mt-0.5 text-sm text-muted-foreground">{description}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  )
}
