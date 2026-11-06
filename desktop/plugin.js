// ReQurv KB - Desktop half. Loaded uncompiled as plain ESM: no JSX, no TypeScript.
// One screen, Settings -> Plugins -> ReQurv KB: the connection, the watchdog and its last results.
import { Badge, Button, Codicon, ConfirmDialog, Input, cn, haptic, host } from '@hermes/plugin-sdk'
import { useCallback, useEffect, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

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
    watchdog: () => ctx.rest('/watchdog'),
    setInterval: minutes => post('/watchdog', { minutes }),
    reconcile: () => post('/watchdog/reconcile', {})
  }
}

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

// --------------------------------------------------------------- watchdog

const ACTION = {
  installed: { label: 'installato', variant: 'success' },
  updated: { label: 'aggiornato', variant: 'success' },
  error: { label: 'errore', variant: 'destructive' },
  'source-unavailable': { label: 'sorgente non disponibile', variant: 'destructive' },
  'pending-removal': { label: 'non più abilitato, sarà rimosso', variant: 'default' },
  removed: { label: 'rimosso (non più abilitato)', variant: 'default' }
}

const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`

function whenText(epochSeconds) {
  return new Date(epochSeconds * 1000).toLocaleString('it-IT', { dateStyle: 'short', timeStyle: 'short' })
}

/** Toast after a manual or launch-time check; null when there is nothing worth saying. */
function summarize(res) {
  if (res.busy) return info('Un controllo è già in corso su questo computer.')
  const run = res.last_run
  if (!run) return null
  const s = run.summary
  if (run.error) return host.notify({ kind: 'error', message: run.error })
  if (s.installed || s.updated || s.removed) {
    const parts = []
    if (s.installed) parts.push(`${plural(s.installed, 'bot installato', 'bot installati')}`)
    if (s.updated) parts.push(`${plural(s.updated, 'bot aggiornato', 'bot aggiornati')}`)
    if (s.removed) parts.push(`${plural(s.removed, 'bot rimosso', 'bot rimossi')}`)
    ok(`${parts.join(' e ')} dalla libreria.`)
  }
  for (const r of run.results.filter(r => r.action === 'error' || r.action === 'source-unavailable')) {
    host.notify({ kind: 'error', message: `${r.bot}: ${r.error || ACTION[r.action].label}` })
  }
  return null
}

function ResultRows({ run }) {
  const rows = run.results.filter(r => r.action !== 'unchanged')
  if (!rows.length) return h(Note, {}, 'Tutti i bot sono allineati alla libreria.')
  return hs('div', { className: 'flex flex-col gap-1' }, rows.map((r, i) => {
    const meta = ACTION[r.action] || { label: r.action, variant: 'default' }
    const version = r.to && r.action !== 'error' ? ` v${r.to}` : ''
    return hs('div', { key: i, className: 'flex flex-wrap items-center gap-2 text-xs' }, [
      h('span', { className: 'font-medium text-(--ui-text-primary)' }, r.bot),
      h(Badge, { variant: meta.variant }, meta.label + version),
      r.error ? h('span', { className: 'text-destructive' }, r.error) : null
    ])
  }))
}

function WatchdogSection({ api, status, onChanged }) {
  const [minutes, setMinutes] = useState(String(status.interval_minutes))
  const [busy, setBusy] = useState(false)
  const run = status.last_run
  const s = run && run.summary

  const check = async () => {
    haptic('tap')
    setBusy(true)
    try {
      const res = await api.reconcile()
      summarize(res)
      await onChanged()
    } catch (e) {
      fail(e)
    } finally {
      setBusy(false)
    }
  }

  const save = async () => {
    try {
      await api.setInterval(Number(minutes))
      ok('Intervallo salvato.')
      await onChanged()
    } catch (e) {
      fail(e)
    }
  }

  return h(Section, { title: 'Allineamento automatico' },
    hs('div', { className: 'flex flex-col gap-3' }, [
      h(Note, {}, 'Mentre Hermes è aperto, la libreria viene controllata a intervalli: i bot con una nuova versione si '
        + 'aggiornano, quelli abilitati ma mancanti (eliminati o mai installati) tornano senza le loro chat, e i bot '
        + 'aziendali non più abilitati vengono rimossi con chat e memoria. I bot che hai creato o duplicato restano.'),
      hs('div', { className: 'flex flex-wrap items-center gap-2' }, [
        h('span', { className: 'text-xs text-(--ui-text-secondary)' }, 'Controlla ogni'),
        h(Input, {
          className: 'w-20', type: 'number', min: status.min_minutes, value: minutes,
          'aria-label': 'Minuti tra due controlli', onChange: e => setMinutes(e.target.value)
        }),
        h('span', { className: 'text-xs text-(--ui-text-secondary)' }, 'minuti'),
        h(Button, {
          size: 'sm', variant: 'secondary', disabled: busy || Number(minutes) === status.interval_minutes, onClick: save
        }, 'Salva')
      ]),
      run
        ? hs('div', { className: 'flex flex-col gap-2' }, [
            h(Note, {}, `Ultimo controllo: ${whenText(run.at)} · ${plural(s.installed, 'installato', 'installati')}, `
              + `${plural(s.updated, 'aggiornato', 'aggiornati')}, ${plural(s.removed, 'rimosso', 'rimossi')}, ${plural(s.errors, 'errore', 'errori')}`),
            run.error ? h(Note, { tone: 'error' }, run.error) : h(ResultRows, { run })
          ])
        : h(Note, {}, 'Nessun controllo eseguito finora.'),
      h('div', {}, h(Button, { size: 'sm', disabled: busy, loading: busy, onClick: check },
        busy ? 'Controllo in corso…' : 'Controlla ora'))
    ]))
}

// --------------------------------------------------------------- settings

function ConnectionHeader({ connection, onEdit, onDisconnect }) {
  const roots = connection.roots || []
  return hs('div', { className: 'flex flex-wrap items-start justify-between gap-3' }, [
    hs('div', { className: 'flex min-w-0 flex-col gap-1' }, [
      h(Note, {}, connection.operator ? `Operatore: ${connection.operator}` : 'Operatore non indicato'),
      ...roots.map((r, i) => h('div', { key: i, className: cn('truncate font-mono text-xs', MUTED), title: r }, r)),
      connection.personal ? h(Note, {}, `Cartella personale: ${connection.personal}`) : null
    ]),
    hs('div', { className: 'flex gap-2' }, [
      h(Button, { size: 'sm', variant: 'secondary', onClick: onEdit }, 'Modifica collegamento'),
      h(Button, { size: 'sm', variant: 'outline', onClick: onDisconnect }, 'Scollega')
    ])
  ])
}

function SettingsPage({ ctx, api }) {
  const [state, setState] = useState({ loading: true })
  const [editing, setEditing] = useState(false)
  const [confirmDisconnect, setConfirmDisconnect] = useState(false)

  const load = useCallback(async () => {
    try {
      const conn = await api.connection()
      const status = conn.connection ? await api.watchdog() : null
      setState({ conn, status })
    } catch (e) {
      setState({ error: errText(e) })
    }
  }, [api])

  useEffect(() => {
    void load()
  }, [load])

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
    body = hs('div', { className: 'flex flex-col gap-6' }, [
      h(ConnectionHeader, {
        connection: state.conn.connection,
        onEdit: () => setEditing(true),
        onDisconnect: () => setConfirmDisconnect(true)
      }),
      h(CheckNotes, { check: state.conn.check }),
      state.status ? h(WatchdogSection, { key: state.status.last_run?.at ?? 'none', api, status: state.status, onChanged: load }) : null,
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

  return hs('div', { className: 'flex max-w-xl flex-col gap-4 p-4' }, [
    hs('div', { className: 'flex items-center gap-2' }, [
      h(Codicon, { name: 'library' }),
      h('h1', { className: 'text-base font-semibold text-(--ui-text-primary)' }, 'ReQurv KB')
    ]),
    body
  ])
}

// ----------------------------------------------------------------- layout

// "ReQurv minimal": the saved layout the setup steps apply with set_theme (layout `requrv-kb:minimal`,
// the id after ctx.register namespaces it). Pane ids are stock Hermes panes.
const MINIMAL_LAYOUT = {
  "type": "split",
  "id": "spl-root",
  "orientation": "row",
  "children": [
    {
      "type": "group",
      "id": "grp-sessions",
      "panes": [
        "sessions",
        "hermes-bots:pane"
      ],
      "active": "sessions"
    },
    {
      "type": "group",
      "id": "grp-main",
      "panes": [
        "workspace"
      ],
      "active": "workspace"
    },
    {
      "type": "group",
      "id": "g-mw57cwcc-1p",
      "panes": [
        "hermes-bots:routines"
      ],
      "active": "hermes-bots:routines",
      "minimized": true
    },
    {
      "type": "split",
      "id": "spl-right",
      "orientation": "column",
      "children": [
        {
          "type": "split",
          "id": "spl-rail",
          "orientation": "row",
          "children": [
            {
              "type": "group",
              "id": "grp-review",
              "panes": [
                "review"
              ],
              "active": "review"
            },
            {
              "type": "group",
              "id": "grp-files",
              "panes": [
                "files"
              ],
              "active": "files"
            }
          ],
          "weights": [
            1,
            1.2
          ]
        },
        {
          "type": "group",
          "id": "grp-terminal",
          "panes": [
            "terminal"
          ],
          "active": "terminal",
          "minimized": true
        }
      ],
      "weights": [
        1.6,
        1
      ]
    }
  ],
  "weights": [
    1,
    0.85,
    0.85,
    1.25
  ]
}

// --------------------------------------------------------------- register

export default {
  id: 'requrv-kb',
  name: 'ReQurv KB',
  register(ctx) {
    const api = createApi(ctx)

    ctx.register({ id: 'minimal', area: 'layouts', title: 'ReQurv minimal', order: 100, data: MINIMAL_LAYOUT })

    ctx.registerSettingsPage?.({
      id: 'settings',
      title: 'ReQurv KB',
      icon: 'library',
      render: () => jsx(SettingsPage, { ctx, api })
    })

    // Launch-time check (installs what is missing, updates the rest): fire-and-forget, never blocks registration.
    api
      .reconcile()
      .then(res => {
        if (!res.busy) summarize(res)
      })
      .catch(e => console.warn('[requrv-kb] controllo all’avvio non riuscito:', errText(e)))
  }
}
