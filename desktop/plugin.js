// ReQurv KB - Desktop half. Loaded uncompiled as plain ESM: no JSX, no TypeScript.
import {
  Badge,
  Button,
  Codicon,
  ConfirmDialog,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Input,
  PALETTE_AREA,
  ROUTES_AREA,
  SIDEBAR_NAV_AREA,
  cn,
  haptic,
  host
} from '@hermes/plugin-sdk'
import { useCallback, useEffect, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const PAGE_PATH = '/requrv-kb'
const MUTED = 'text-(--ui-text-tertiary)'

// ---------------------------------------------------------------- helpers

/** Best-effort user-facing text from a failed ctx.rest call. The backend sends
 *  an Italian sentence in `detail`; the bridge may wrap it in an HTTP prefix or JSON. */
function errText(error) {
  const raw = String((error && error.message) || error || '').trim()
  if (!raw) return 'Operazione non riuscita.'
  const json = raw.slice(raw.indexOf('{'))
  if (raw.includes('{')) {
    try {
      const detail = JSON.parse(json).detail
      if (typeof detail === 'string' && detail) return detail
    } catch {
      /* not JSON, fall through */
    }
  }
  return raw.replace(/^(HTTP\s*)?\d{3}\s*[:\-]?\s*/i, '')
}

function createApi(ctx) {
  const post = (path, body) => ctx.rest(path, { method: 'POST', body })

  return {
    connection: () => ctx.rest('/connection'),
    connect: body => post('/connection', body),
    disconnect: () => ctx.rest('/connection', { method: 'DELETE' }),
    library: () => ctx.rest('/library'),
    install: name => post('/library/install', { name }),
    update: profile => post('/library/update', { profile }),
    rollback: profile => post('/library/rollback', { profile }),
    duplicate: (profile, name) => post('/library/duplicate', { profile, name }),
    sync: () => post('/library/sync', {})
  }
}

const countUpdated = results => (results || []).filter(r => r.status === 'updated').length

const h = (tag, props, ...children) =>
  jsx(tag, { ...props, children: children.length === 1 ? children[0] : children })

const hs = (tag, props, children) => jsxs(tag, { ...props, children })

const ok = message => host.notify({ kind: 'success', message })
const info = message => host.notify({ kind: 'info', message })
const fail = error => host.notify({ kind: 'error', message: errText(error) })

// ------------------------------------------------------------ small views

function Note({ tone, children }) {
  const color = tone === 'error' ? 'text-destructive' : tone === 'warn' ? 'text-(--ui-text-secondary)' : MUTED
  return h('div', { className: cn('text-xs leading-5', color) }, children)
}

function Section({ title, children }) {
  return hs('section', { className: 'flex flex-col gap-2' }, [
    h('h2', { className: 'text-sm font-semibold text-(--ui-text-primary)' }, title),
    children
  ])
}

function CheckNotes({ check }) {
  if (!check) return null
  const problems = check.problems || []
  const warnings = check.warnings || []
  if (!problems.length && !warnings.length) return null
  return hs('div', { className: 'flex flex-col gap-1' }, [
    ...problems.map((p, i) => h(Note, { key: `p${i}`, tone: 'error' }, p)),
    ...warnings.map((w, i) => h(Note, { key: `w${i}`, tone: 'warn' }, w))
  ])
}

function StatusBadge({ entry }) {
  const { status } = entry
  if (status === 'installed') return h(Badge, { variant: 'success' }, 'Installato')
  if (status === 'update') {
    const label = `Aggiornamento disponibile v${entry.installed_version || '?'} → v${entry.version}`
    return h(Badge, { variant: 'warn' }, label)
  }
  if (status === 'error') return h(Badge, { variant: 'destructive' }, 'Errore')
  return h(Badge, { variant: 'default' }, 'Nuovo')
}

// ----------------------------------------------------------- connect form

function FolderRow({ value, onChange, onRemove, canRemove }) {
  return hs('div', { className: 'flex items-center gap-2' }, [
    h(Input, {
      className: 'flex-1',
      placeholder: 'Percorso della cartella della KB',
      value,
      onChange: e => onChange(e.target.value)
    }),
    canRemove
      ? h(Button, { variant: 'ghost', size: 'icon-xs', 'aria-label': 'Rimuovi cartella', onClick: onRemove },
          h(Codicon, { name: 'trash' }))
      : null
  ])
}

function ConnectForm({ ctx, api, initial, check, onConnected, onCancel }) {
  const [roots, setRoots] = useState(initial?.roots?.length ? initial.roots : [''])
  const [operator, setOperator] = useState(initial?.operator || '')
  const [personal, setPersonal] = useState(initial?.personal || '')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(check || null)
  const [error, setError] = useState('')
  const canPick = Boolean(ctx.files && ctx.files.requestFolder)

  const setRoot = (i, v) => setRoots(rs => rs.map((r, j) => (j === i ? v : r)))
  const removeRoot = i => setRoots(rs => (rs.length > 1 ? rs.filter((_, j) => j !== i) : ['']))

  const pick = async () => {
    const res = await ctx.files.requestFolder()
    const path = res && res.ok && res.folder && res.folder.path
    if (!path) return
    setRoots(rs => [...rs.filter(r => r.trim()), path])
  }

  const submit = async () => {
    const clean = roots.map(r => r.trim()).filter(Boolean)
    if (!clean.length) {
      setError('Indica almeno una cartella della KB.')
      return
    }
    setBusy(true)
    setError('')
    try {
      const body = { roots: clean }
      if (operator.trim()) body.operator = operator.trim()
      if (personal.trim()) body.personal = personal.trim()
      const res = await api.connect(body)
      setResult(res.check)
      if (res.connection) {
        ok('KB collegata.')
        onConnected()
      }
    } catch (e) {
      setError(errText(e))
    } finally {
      setBusy(false)
    }
  }

  return hs('div', { className: 'flex max-w-xl flex-col gap-4' }, [
    h(Note, {}, 'Indica le cartelle della KB condivisa. La libreria mostrerà i bot che la tua area può installare.'),
    h(Section, { title: 'Cartelle della KB' },
      hs('div', { className: 'flex flex-col gap-2' }, [
        ...roots.map((r, i) =>
          h(FolderRow, {
            key: i,
            value: r,
            canRemove: roots.length > 1 || r !== '',
            onChange: v => setRoot(i, v),
            onRemove: () => removeRoot(i)
          })
        ),
        hs('div', { className: 'flex gap-2' }, [
          canPick ? h(Button, { variant: 'secondary', size: 'sm', onClick: pick }, 'Scegli cartella…') : null,
          h(Button, { variant: 'ghost', size: 'sm', onClick: () => setRoots(rs => [...rs, '']) }, 'Aggiungi cartella')
        ])
      ])),
    h(Section, { title: 'Operatore (facoltativo)' },
      h(Input, { placeholder: 'Il tuo nome', value: operator, onChange: e => setOperator(e.target.value) })),
    h(Section, { title: 'Cartella personale (facoltativa)' },
      h(Input, { placeholder: 'Percorso della tua cartella personale', value: personal, onChange: e => setPersonal(e.target.value) })),
    error ? h(Note, { tone: 'error' }, error) : null,
    h(CheckNotes, { check: result }),
    hs('div', { className: 'flex gap-2' }, [
      h(Button, { disabled: busy, loading: busy, onClick: submit }, busy ? 'Collegamento…' : 'Collega'),
      onCancel ? h(Button, { variant: 'ghost', disabled: busy, onClick: onCancel }, 'Annulla') : null
    ])
  ])
}

// ---------------------------------------------------------------- library

function DuplicateDialog({ entry, onClose, onSubmit }) {
  const [name, setName] = useState(entry ? `${entry.name}-personale` : '')
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    if (!name.trim() || busy) return
    setBusy(true)
    try {
      await onSubmit(name.trim())
    } finally {
      setBusy(false)
    }
  }

  return h(Dialog, { open: true, onOpenChange: open => !open && !busy && onClose() },
    hs(DialogContent, {}, [
      hs(DialogHeader, {}, [
        h(DialogTitle, {}, 'Duplica come bot personale'),
        h(DialogDescription, {}, `Crea una copia modificabile di "${entry.name}". La copia non viene più aggiornata dalla KB.`)
      ]),
      h(Input, {
        autoFocus: true,
        value: name,
        onChange: e => setName(e.target.value),
        onKeyDown: e => e.key === 'Enter' && submit()
      }),
      hs(DialogFooter, {}, [
        h(Button, { variant: 'ghost', disabled: busy, onClick: onClose }, 'Annulla'),
        h(Button, { disabled: busy || !name.trim(), loading: busy, onClick: submit }, 'Duplica')
      ])
    ]))
}

function EntryActions({ entry, busy, onInstall, onUpdate, onRollback, onDuplicate }) {
  const buttons = []
  if (entry.status === 'new') {
    buttons.push(h(Button, { key: 'i', size: 'sm', disabled: busy, loading: busy, onClick: onInstall }, 'Installa'))
  }
  if (entry.status === 'update') {
    buttons.push(h(Button, { key: 'u', size: 'sm', disabled: busy, loading: busy, onClick: onUpdate }, 'Aggiorna'))
  }
  if (entry.can_rollback) {
    buttons.push(h(Button, { key: 'r', size: 'sm', variant: 'outline', disabled: busy, onClick: onRollback },
      'Torna alla versione precedente'))
  }
  if (entry.installed_profile) {
    buttons.push(h(Button, { key: 'd', size: 'sm', variant: 'secondary', disabled: busy, onClick: onDuplicate },
      'Duplica come bot personale'))
  }
  return buttons.length ? hs('div', { className: 'flex flex-wrap gap-2' }, buttons) : null
}

function EntryCard({ entry, busy, actions }) {
  const skills = (entry.skills || []).length
  return hs('div', {
    className: 'flex flex-col gap-2 rounded-md p-3 shadow-[inset_0_0_0_1px_color-mix(in_srgb,var(--ui-stroke-secondary)_50%,transparent)]'
  }, [
    hs('div', { className: 'flex flex-wrap items-center gap-2' }, [
      h('span', { className: 'text-sm font-medium text-(--ui-text-primary)' }, entry.name),
      h('span', { className: cn('text-xs', MUTED) }, `v${entry.version}`),
      h(StatusBadge, { entry })
    ]),
    entry.description ? h('div', { className: 'text-xs text-(--ui-text-secondary)' }, entry.description) : null,
    h(Note, {}, `${skills} ${skills === 1 ? 'competenza' : 'competenze'}${entry.has_cron ? ' · con attività pianificate' : ''}`),
    entry.status === 'error' && entry.error ? h(Note, { tone: 'error' }, entry.error) : null,
    entry.installed_profile
      ? h(Note, {}, 'Bot di libreria: non modificabile, viene aggiornato dalla KB.')
      : null,
    actions
  ])
}

function AllowlistNotes({ allowlist, empty }) {
  const al = allowlist || {}
  const notes = []
  if (empty) {
    notes.push(h(Note, { key: 'e' }, 'La libreria non ti offre bot: chiedi all’IT di abilitarli nel bots.yaml della tua area.'))
  }
  if ((al.missing || []).length) {
    notes.push(h(Note, { key: 'm', tone: 'warn' }, `Bot abilitati ma non trovati nella KB: ${al.missing.join(', ')}.`))
  }
  if ((al.unreadable || []).length) {
    notes.push(h(Note, { key: 'u', tone: 'warn' }, `Elenchi non leggibili: ${al.unreadable.join(', ')}.`))
  }
  return notes.length ? hs('div', { className: 'flex flex-col gap-1' }, notes) : null
}

const SYNC_LABEL = { unchanged: null, updated: 'aggiornato', 'source-unavailable': 'sorgente non disponibile', error: 'errore' }

function summarizeSync(results) {
  const rows = results || []
  if (!rows.length) return info('Nessun bot di libreria da aggiornare.')
  const updated = countUpdated(rows)
  const problems = rows.filter(r => r.status === 'error' || r.status === 'source-unavailable')
  if (updated) ok(updated === 1 ? "Aggiornato 1 bot dalla libreria." : `Aggiornati ${updated} bot dalla libreria.`)
  else if (!problems.length) info('Tutti i bot sono già aggiornati.')
  for (const r of problems) {
    host.notify({ kind: 'error', message: `${r.profile}: ${r.error || SYNC_LABEL[r.status]}` })
  }
}

function Library({ api, data, busyKey, onChanged, setBusyKey }) {
  const [confirm, setConfirm] = useState(null)
  const [dup, setDup] = useState(null)
  const entries = data.entries || []

  const run = async (key, work, message) => {
    haptic('tap')
    setBusyKey(key)
    try {
      await work()
      ok(message)
      await onChanged()
    } catch (e) {
      fail(e)
    } finally {
      setBusyKey('')
    }
  }

  const appears = 'Lo trovi nella sezione Bot.'

  return hs('div', { className: 'flex flex-col gap-3' }, [
    h(AllowlistNotes, { allowlist: data.allowlist, empty: !entries.length }),
    ...entries.map(entry => {
      const key = entry.installed_profile || entry.name
      return h(EntryCard, {
        key: entry.name,
        entry,
        busy: busyKey === key,
        actions: h(EntryActions, {
          entry,
          busy: Boolean(busyKey),
          onInstall: () => run(key, () => api.install(entry.name), `${entry.name} installato. ${appears}`),
          onUpdate: () => run(key, () => api.update(entry.installed_profile), `${entry.name} aggiornato.`),
          onRollback: () => setConfirm(entry),
          onDuplicate: () => setDup(entry)
        })
      })
    }),
    confirm
      ? h(ConfirmDialog, {
          open: true,
          destructive: true,
          title: 'Tornare alla versione precedente?',
          description: `Il bot "${confirm.name}" tornerà alla versione precedente. Potrai aggiornarlo di nuovo dalla libreria.`,
          confirmLabel: 'Torna indietro',
          cancelLabel: 'Annulla',
          onClose: () => setConfirm(null),
          onConfirm: async () => {
            const entry = confirm
            await run(entry.installed_profile, () => api.rollback(entry.installed_profile),
              `${entry.name} riportato alla versione precedente.`)
          }
        })
      : null,
    dup
      ? h(DuplicateDialog, {
          entry: dup,
          onClose: () => setDup(null),
          onSubmit: async name => {
            const entry = dup
            try {
              await api.duplicate(entry.installed_profile, name)
              ok(`Creato "${name}". ${appears}`)
              setDup(null)
              await onChanged()
            } catch (e) {
              fail(e)
            }
          }
        })
      : null
  ])
}

// ------------------------------------------------------------------- page

function ConnectionHeader({ connection, onEdit, onDisconnect, disabled }) {
  const roots = connection.roots || []
  return hs('div', { className: 'flex flex-wrap items-start justify-between gap-3' }, [
    hs('div', { className: 'flex min-w-0 flex-col gap-1' }, [
      h(Note, {}, connection.operator ? `Operatore: ${connection.operator}` : 'Operatore non indicato'),
      ...roots.map((r, i) => h('div', { key: i, className: cn('truncate font-mono text-xs', MUTED), title: r }, r)),
      connection.personal ? h(Note, {}, `Cartella personale: ${connection.personal}`) : null
    ]),
    hs('div', { className: 'flex gap-2' }, [
      h(Button, { size: 'sm', variant: 'secondary', disabled, onClick: onEdit }, 'Modifica collegamento'),
      h(Button, { size: 'sm', variant: 'outline', disabled, onClick: onDisconnect }, 'Scollega')
    ])
  ])
}

function KbPage({ ctx, api }) {
  const [state, setState] = useState({ loading: true })
  const [editing, setEditing] = useState(false)
  const [busyKey, setBusyKey] = useState('')
  const [syncing, setSyncing] = useState(false)
  const [confirmDisconnect, setConfirmDisconnect] = useState(false)

  const load = useCallback(async () => {
    try {
      const conn = await api.connection()
      const data = conn.connection ? await api.library() : null
      setState({ conn, data })
    } catch (e) {
      setState({ error: errText(e) })
    }
  }, [api])

  useEffect(() => {
    void load()
  }, [load])

  const syncAll = async () => {
    setSyncing(true)
    try {
      summarizeSync((await api.sync()).results)
      await load()
    } catch (e) {
      fail(e)
    } finally {
      setSyncing(false)
    }
  }

  let body
  if (state.loading) {
    body = h(Note, {}, 'Caricamento…')
  } else if (state.error) {
    body = hs('div', { className: 'flex flex-col items-start gap-2' }, [
      h(Note, { tone: 'error' }, state.error),
      h(Button, { size: 'sm', variant: 'secondary', onClick: () => { setState({ loading: true }); void load() } }, 'Riprova')
    ])
  } else if (!state.conn.connection || editing) {
    body = h(ConnectForm, {
      ctx,
      api,
      initial: state.conn.connection,
      check: state.conn.check,
      onCancel: state.conn.connection ? () => setEditing(false) : null,
      onConnected: () => { setEditing(false); void load() }
    })
  } else {
    body = hs('div', { className: 'flex flex-col gap-4' }, [
      h(ConnectionHeader, {
        connection: state.conn.connection,
        disabled: Boolean(busyKey) || syncing,
        onEdit: () => setEditing(true),
        onDisconnect: () => setConfirmDisconnect(true)
      }),
      h(CheckNotes, { check: state.conn.check }),
      hs('div', { className: 'flex items-center justify-between' }, [
        h('h2', { className: 'text-sm font-semibold text-(--ui-text-primary)' }, 'Bot disponibili'),
        h(Button, { size: 'sm', variant: 'secondary', disabled: syncing || Boolean(busyKey), loading: syncing, onClick: syncAll },
          'Aggiorna tutti')
      ]),
      state.data ? h(Library, { api, data: state.data, busyKey, setBusyKey, onChanged: load }) : null,
      confirmDisconnect
        ? h(ConfirmDialog, {
            open: true,
            destructive: true,
            title: 'Scollegare la KB?',
            description: 'I bot già installati restano, ma non verranno più aggiornati finché non ricolleghi la KB.',
            confirmLabel: 'Scollega',
            cancelLabel: 'Annulla',
            onClose: () => setConfirmDisconnect(false),
            onConfirm: async () => {
              await api.disconnect()
              ok('KB scollegata.')
              await load()
            }
          })
        : null
    ])
  }

  return hs('div', { className: 'flex h-full flex-col gap-4 overflow-y-auto p-6' }, [
    hs('div', { className: 'flex items-center gap-2' }, [
      h(Codicon, { name: 'library' }),
      h('h1', { className: 'text-base font-semibold text-(--ui-text-primary)' }, 'Libreria bot')
    ]),
    body
  ])
}

// --------------------------------------------------------------- settings

function SettingsPage({ api }) {
  const [conn, setConn] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.connection().then(setConn, e => setError(errText(e)))
  }, [api])

  const c = conn && conn.connection
  let summary = 'Caricamento…'
  if (error) summary = error
  else if (conn) summary = c ? `Collegata a ${(c.roots || []).length} cartella/e${c.operator ? ` · operatore ${c.operator}` : ''}.` : 'KB non collegata.'

  return hs('div', { className: 'flex max-w-xl flex-col gap-3 p-4' }, [
    h('div', { className: 'text-sm text-(--ui-text-secondary)' }, summary),
    h('div', {}, h(Button, { size: 'sm', onClick: () => host.navigate(PAGE_PATH) }, 'Apri la libreria bot'))
  ])
}

// --------------------------------------------------------------- register

export default {
  id: 'requrv-kb',
  name: 'ReQurv KB',
  register(ctx) {
    const api = createApi(ctx)

    ctx.registerMany([
      { id: 'page', area: ROUTES_AREA, data: { path: PAGE_PATH }, render: () => jsx(KbPage, { ctx, api }) },
      { id: 'nav', area: SIDEBAR_NAV_AREA, data: { path: PAGE_PATH, label: 'Libreria', codicon: 'library' } },
      {
        id: 'open',
        area: PALETTE_AREA,
        data: {
          id: 'requrv-kb.open',
          label: 'Apri la libreria bot',
          keywords: ['libreria', 'bot', 'kb', 'requrv'],
          run: () => host.navigate(PAGE_PATH)
        }
      }
    ])

    ctx.registerSettingsPage?.({
      id: 'settings',
      title: 'ReQurv KB',
      icon: 'library',
      render: () => jsx(SettingsPage, { api })
    })

    // Launch-time sync: fire-and-forget, never blocks registration.
    api
      .sync()
      .then(res => {
        const n = countUpdated(res && res.results)
        if (n) info(n === 1 ? "Aggiornato 1 bot dalla libreria." : `Aggiornati ${n} bot dalla libreria.`)
      })
      .catch(e => console.warn('[requrv-kb] sync all’avvio non riuscita:', errText(e)))
  }
}
