import { useLayoutEffect, useRef, useState, type ReactNode } from 'react'

// B-212 verification page — dev-only, not part of the shipped app UI.
// Every swatch renders through a real generated Tailwind utility class
// (never an inline var() style), then reads back getComputedStyle so the
// theme.css -> tokens.css mapping is eyeball-verifiable without any hex
// literal appearing in this file.

type ColorKind = 'bg' | 'text' | 'border'

interface SwatchProps {
  label: string
  className: string
  kind?: ColorKind
}

function Swatch({ label, className, kind = 'bg' }: SwatchProps) {
  const ref = useRef<HTMLDivElement>(null)
  const [computed, setComputed] = useState('')

  // useLayoutEffect (not useEffect): reads a computed style off the DOM node
  // after layout but before paint, avoiding a "reading…" flash. The lint
  // rule below flags any setState call inside an effect as likely-derivable
  // during render; that doesn't apply here — getComputedStyle needs the node
  // painted, which cannot happen during render — so this is the "read from
  // an external system" case the rule's own message calls out as legitimate.
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const style = getComputedStyle(el)
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setComputed(kind === 'text' ? style.color : kind === 'border' ? style.borderTopColor : style.backgroundColor)
  }, [kind])

  const boxClassName =
    kind === 'border'
      ? `flex h-12 items-center justify-center rounded-control border-4 bg-surface ${className}`
      : kind === 'text'
        ? `flex h-12 items-center justify-center rounded-control border border-border-hairline bg-surface ${className}`
        : `h-12 rounded-control border border-border-hairline ${className}`

  return (
    <div className="flex w-40 flex-col gap-1.5">
      <div ref={ref} className={boxClassName}>
        {kind === 'text' && <span className="text-body font-medium">Aa 123</span>}
        {kind === 'border' && <span className="text-meta text-ink-muted">border</span>}
      </div>
      <div className="text-meta leading-tight">
        <div className="font-medium text-ink">{label}</div>
        <div className="font-mono text-ink-muted">{className}</div>
        <div className="font-mono text-ink-muted">{computed || 'reading…'}</div>
      </div>
    </div>
  )
}

interface SpacingSwatchProps {
  step: string
  className: string
}

function SpacingSwatch({ step, className }: SpacingSwatchProps) {
  return (
    <div className="flex flex-col items-center gap-1">
      <div className={`border border-border-hairline bg-surface-sunken ${className}`}>
        <div className="h-3 w-3 bg-brand" />
      </div>
      <span className="text-meta text-ink-muted">p-{step}</span>
    </div>
  )
}

interface SectionProps {
  title: string
  note?: string
  children: ReactNode
}

function Section({ title, note, children }: SectionProps) {
  return (
    <section className="flex flex-col gap-3 border-b border-border-hairline pb-8">
      <div>
        <h2 className="text-title text-ink">{title}</h2>
        {note && <p className="text-meta text-ink-muted">{note}</p>}
      </div>
      <div className="flex flex-wrap gap-4">{children}</div>
    </section>
  )
}

export function TokenSpecimen() {
  return (
    <div className="min-h-screen bg-canvas px-8 py-8">
      <header className="mb-8">
        <h1 className="text-hero text-ink">Design Tokens Specimen</h1>
        <p className="text-body text-ink-secondary">
          B-212 verification page. Every swatch below renders through a real generated Tailwind
          utility class, then reports the computed style it actually resolved to.
        </p>
      </header>

      <div className="flex flex-col gap-10">
        <Section title="1. Brand & structure" note='Proves "brand navy/blue" from the acceptance criteria.'>
          <Swatch label="brand" className="bg-brand" />
          <Swatch label="brand-secondary" className="bg-brand-secondary" />
          <Swatch label="brand-hover" className="bg-brand-hover" />
          <Swatch label="canvas" className="bg-canvas" />
          <Swatch label="surface" className="bg-surface" />
          <Swatch label="surface-sunken" className="bg-surface-sunken" />
          <Swatch label="surface-inset" className="bg-surface-inset" />
          <Swatch label="surface-hover" className="bg-surface-hover" />
          <Swatch label="surface-selected" className="bg-surface-selected" />
          <Swatch label="border-hairline" className="border-border-hairline" kind="border" />
          <Swatch label="border-strong" className="border-border-strong" kind="border" />
          <Swatch label="border-input" className="border-border-input" kind="border" />
          <Swatch label="link" className="text-link" kind="text" />
          <Swatch label="ink" className="text-ink" kind="text" />
          <Swatch label="ink-secondary" className="text-ink-secondary" kind="text" />
          <Swatch label="ink-muted" className="text-ink-muted" kind="text" />
        </Section>

        <Section title="2. Typography" note="Each line uses one text-* utility — size, line-height and weight all come from the same class.">
          <div className="flex flex-col gap-3">
            <p className="text-hero text-ink">text-hero — Schedule health</p>
            <p className="text-kpi text-ink">text-kpi — 2,054 critical</p>
            <p className="text-tile text-ink">text-tile — 17.2%</p>
            <p className="text-title text-ink">text-title — Section heading</p>
            <p className="text-body text-ink">text-body — Default UI text and narratives run here.</p>
            <p className="text-header uppercase text-ink-muted">text-header — column header</p>
            <p className="text-meta text-ink-muted">text-meta — captions, timestamps</p>
            <p className="text-micro uppercase text-ink-muted">text-micro — tile micro-label</p>
          </div>
        </Section>

        <Section title="3. Progress axis" note="Completed / Active / Not started.">
          <Swatch label="complete" className="bg-progress-complete-bg text-progress-complete-fg" kind="text" />
          <Swatch label="active" className="bg-progress-active-bg text-progress-active-fg" kind="text" />
          <Swatch label="notstarted" className="bg-progress-notstarted-bg text-progress-notstarted-fg" kind="text" />
        </Section>

        <Section title="4. Variance axis" note="Watching / At risk / Delayed — tint fills only, never solid.">
          <Swatch label="watching" className="bg-variance-watching-bg text-variance-watching-fg" kind="text" />
          <Swatch label="atrisk" className="bg-variance-atrisk-bg text-variance-atrisk-fg" kind="text" />
          <Swatch label="delayed" className="bg-variance-delayed-bg text-variance-delayed-fg" kind="text" />
        </Section>

        <Section
          title="5. Criticality axis"
          note="critical-bg is the ONE allowed solid red fill; the band pair is a separate tint treatment for percentages and must stay visually distinct from it."
        >
          <Swatch label="critical (solid)" className="bg-critical-bg text-critical-fg" kind="text" />
          <Swatch label="critical-band" className="bg-critical-band-bg text-critical-band-fg" kind="text" />
          <Swatch label="critical-band-max" className="bg-critical-band-max-bg text-critical-band-fg" kind="text" />
        </Section>

        <Section title="6. Judge pills" note="Derived-judgement pills — severity separated by hue.">
          <Swatch label="ok" className="bg-judge-ok-bg text-judge-ok-fg" kind="text" />
          <Swatch label="caution" className="bg-judge-caution-bg text-judge-caution-fg" kind="text" />
          <Swatch label="adverse" className="bg-judge-adverse-bg text-judge-adverse-fg" kind="text" />
        </Section>

        <Section
          title="7. On-navy band"
          note="These tokens are only meaningful against navy — the second half of the acceptance criteria's brand-navy requirement."
        >
          <div className="flex w-full flex-wrap gap-6 rounded-card bg-brand p-6">
            <Swatch label="onnavy-warm" className="text-onnavy-warm" kind="text" />
            <Swatch label="onnavy-positive" className="text-onnavy-positive" kind="text" />
            <Swatch label="onnavy-zero" className="text-onnavy-zero" kind="text" />
            <Swatch label="onnavy-adverse" className="text-onnavy-adverse" kind="text" />
          </div>
        </Section>

        <Section title="8. Float pills" note="Positive / zero / negative float.">
          <Swatch label="pos" className="bg-float-pos-bg text-float-pos-fg" kind="text" />
          <Swatch label="zero" className="bg-float-zero-bg text-float-zero-fg" kind="text" />
          <Swatch label="neg" className="bg-float-neg-bg text-float-neg-fg" kind="text" />
        </Section>

        <Section title="9. KPI value colors" note="Value text colour — never the only carrier of meaning, a trend glyph is required alongside it.">
          <Swatch label="favourable" className="text-value-favourable" kind="text" />
          <Swatch label="unfavourable" className="text-value-unfavourable" kind="text" />
          <Swatch label="adverse (deep rust)" className="text-adverse" kind="text" />
        </Section>

        <Section title="10. Data-quality caveat" note="Reserved amber pair — data reliability caveats only, never schedule state.">
          <Swatch label="caveat" className="bg-caveat-bg text-caveat-fg" kind="text" />
        </Section>

        <Section title="11. Radius">
          <Swatch label="rounded-card" className="rounded-card bg-surface-sunken" />
          <Swatch label="rounded-control" className="rounded-control bg-surface-sunken" />
          <Swatch label="rounded-label" className="rounded-label bg-surface-sunken" />
          <Swatch label="rounded-pill" className="rounded-pill bg-surface-sunken" />
        </Section>

        <Section title="12. Shadow">
          <Swatch label="shadow-card" className="shadow-card bg-surface" />
          <Swatch label="shadow-overlay" className="shadow-overlay bg-surface" />
          <Swatch label="shadow-drawer" className="shadow-drawer bg-surface" />
          <Swatch label="shadow-row-selected" className="shadow-row-selected bg-surface" />
        </Section>

        <Section title="13. Spacing" note="Named steps from tailwind.theme.js only (1,2,3,4,5,6,10) — not tokens.css's fuller 10-step scale.">
          <div className="flex flex-wrap items-end gap-4">
            <SpacingSwatch step="1" className="p-1" />
            <SpacingSwatch step="2" className="p-2" />
            <SpacingSwatch step="3" className="p-3" />
            <SpacingSwatch step="4" className="p-4" />
            <SpacingSwatch step="5" className="p-5" />
            <SpacingSwatch step="6" className="p-6" />
            <SpacingSwatch step="10" className="p-10" />
          </div>
        </Section>
      </div>

      <footer className="mt-10 text-meta text-ink-muted">
        <p>
          Not shown above, by design: filter chips (chip-crit/-neg/-del/-risk/-watch) and score
          bands (score-high/-mid/-low). Both exist in tokens.css but tailwind.theme.js never wires
          them up as Tailwind utilities — same treatment as the RETIRED ai-accent tokens. They're
          only reachable today via a direct var() reference, matching how the reference 06-source
          components already consume most tokens.
        </p>
      </footer>
    </div>
  )
}
