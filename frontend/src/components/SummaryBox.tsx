export function SummaryBox({ text }: { text: string }) {
  return (
    <div className="border border-zinc-800 bg-zinc-950/60 px-3 py-2 font-sans text-[13px] leading-relaxed text-zinc-200">
      {text || '—'}
    </div>
  )
}
