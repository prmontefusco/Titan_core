import type { ReactNode } from 'react'

type StateTone = 'page' | 'compact'

interface StateProps {
  title?: string
  message: string
  tone?: StateTone
  action?: ReactNode
}

export function LoadingState({ message, tone = 'page' }: Omit<StateProps, 'title' | 'action'>) {
  return (
    <div className={stateClassName(tone, 'loading')} role="status">
      <p>{message}</p>
    </div>
  )
}

export function EmptyState({ title, message, tone = 'page', action }: StateProps) {
  return (
    <section className={stateClassName(tone, 'empty')}>
      {title && <h2>{title}</h2>}
      <p>{message}</p>
      {action}
    </section>
  )
}

export function ErrorState({ title, message, tone = 'page', action }: StateProps) {
  return (
    <section className={stateClassName(tone, 'error')} role="alert">
      {title && <h2>{title}</h2>}
      <p>{message}</p>
      {action}
    </section>
  )
}

export function UnauthorizedState({ title, message, tone = 'page', action }: StateProps) {
  return (
    <section className={stateClassName(tone, 'unauthorized')} role="alert">
      {title && <h2>{title}</h2>}
      <p>{message}</p>
      {action}
    </section>
  )
}

export function NotFoundState({ title, message, tone = 'page', action }: StateProps) {
  return (
    <section className={stateClassName(tone, 'not-found')} role="alert">
      {title && <h2>{title}</h2>}
      <p>{message}</p>
      {action}
    </section>
  )
}

function stateClassName(tone: StateTone, kind: string) {
  return `async-state async-state-${tone} async-state-${kind}`
}
