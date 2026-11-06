// ReQurv KB - Desktop half. Loaded uncompiled as plain ESM: no JSX, no TypeScript.
// One screen, Settings -> Plugins -> ReQurv KB: the connection, the watchdog and its last results.
import {
  Badge, Button, Codicon, ConfirmDialog, Input, SIDEBAR_NAV_PREFS_AREA, THEMES_AREA, cn, haptic, host, requestTheme
} from '@hermes/plugin-sdk'
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
    body,
    h(ThemeSection, {})
  ])
}

function ThemeSection() {
  const apply = () => {
    haptic('tap')
    if (applyTheme()) ok('Tema ReQurv applicato.')
    else host.notify({ kind: 'error', message: 'Tema ReQurv non disponibile: riavvia Hermes Desktop.' })
  }
  return h(Section, { title: 'Aspetto' },
    hs('div', { className: 'flex flex-col items-start gap-2' }, [
      h(Note, {}, 'Il tema ReQurv viene scelto una sola volta, alla prima attivazione. Se ne scegli un altro, '
        + 'qui puoi riapplicarlo.'),
      h(Button, { size: 'sm', variant: 'secondary', onClick: apply }, 'Tema ReQurv')
    ]))
}

// ----------------------------------------------------------------- layout

// "ReQurv minimal" (layout `requrv-kb:minimal`; ctx.register namespaces the id). A plugin layout is the
// tree and nothing else: the app opens every pane the tree DECLARES (it cannot carry the "resting" list
// of bundled/user layouts), so the tree declares only what must be on screen:
//   left  = Bots alone; centre = chat; right = Files and Scheduled jobs as minimized rails.
// Sessions, review and terminal are NOT declared: applying a layout re-adopts them from the previous
// tree in their current state (closed stays closed) instead of opening them. See README "Layout".
const MINIMAL_LAYOUT = {
  type: 'split',
  id: 'spl-requrv-root',
  orientation: 'row',
  children: [
    { type: 'group', id: 'grp-requrv-bots', panes: ['hermes-bots:pane'], active: 'hermes-bots:pane' },
    { type: 'group', id: 'grp-requrv-main', panes: ['workspace'], active: 'workspace' },
    { type: 'group', id: 'grp-requrv-files', panes: ['files'], active: 'files', minimized: true },
    {
      type: 'group',
      id: 'grp-requrv-routines',
      panes: ['hermes-bots:routines'],
      active: 'hermes-bots:routines',
      minimized: true
    }
  ],
  weights: [1, 3.4, 0.3, 0.3]
}

// Sidebar nav rows a ReQurv user does not need. `new-session` and `capabilities` stay (capabilities
// can never be hidden by a plugin); `kanban:nav` is the bundled Kanban row, inert when absent.
// The preference is a contribution: it ends when this plugin is disabled.
const HIDDEN_NAV_ROWS = ['messaging', 'artifacts', 'cron', 'kanban:nav']

// ------------------------------------------------------------------ theme

// ReQurv's look (requrv.io), ported from the ReAgent distribution. The site is a near-black stage with
// neon purple #B81DF5, electric blue #2234DA and lavender #B392EF, set in Syne. The light palette is
// derived: the same hues on a lavender-tinted off-white, purple deepened to #9316D6 for contrast.
const DARK = {
  background: '#06050e', foreground: '#ffffff', card: '#0f0d1f', cardForeground: '#ffffff',
  muted: '#1b1e34', mutedForeground: '#9da5ae', popover: '#14122a', popoverForeground: '#ffffff',
  primary: '#b81df5', primaryForeground: '#ffffff', secondary: '#343451', secondaryForeground: '#ffffff',
  accent: '#241b45', accentForeground: '#ffffff', border: '#252529', input: '#343451', ring: '#b392ef',
  midground: '#b392ef', midgroundForeground: '#06050e', destructive: '#d9534f', destructiveForeground: '#06050e',
  sidebarBackground: '#0a0914', sidebarBorder: '#252529', userBubble: '#1b1e34', userBubbleBorder: '#343451'
}

const LIGHT = {
  background: '#f6f5fb', foreground: '#06050e', card: '#ffffff', cardForeground: '#06050e',
  muted: '#ebe8f6', mutedForeground: '#4d4f63', popover: '#ffffff', popoverForeground: '#06050e',
  primary: '#9316d6', primaryForeground: '#ffffff', secondary: '#e3dff3', secondaryForeground: '#2b2250',
  accent: '#ece8fa', accentForeground: '#2b2250', border: '#d6d1e6', input: '#d6d1e6', ring: '#2234da',
  midground: '#2234da', midgroundForeground: '#ffffff', destructive: '#b3261e', destructiveForeground: '#ffffff',
  sidebarBackground: '#efecf8', sidebarBorder: '#d6d1e6', userBubble: '#e9e5f7', userBubbleBorder: '#d6d1e6'
}

const THEME_NAME = 'requrv'

// No `fontUrl`: the theme loader would add a <link> to a URL, and a plugin has no static files to point
// it at. The two Syne subsets (SIL OFL 1.1, see desktop/OFL-syne.txt; variable weight 400-800) are
// embedded below and injected as a <style> instead, which the SDK guide allows as a plugin side effect.
const REQURV_THEME = {
  name: THEME_NAME,
  label: 'ReQurv',
  description: 'ReQurv brand: near-black stage, neon purple and blue',
  colors: LIGHT,
  darkColors: DARK,
  typography: {
    fontSans:
      '"Syne", -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif, '
      + '"Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", emoji'
  }
}

const SYNE_LATIN =
  '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' +
  ''

const SYNE_LATIN_EXT =
  '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' +
  'fGlTDTlB3Mvigd8XM46qHy//W78XAAAA' +
  ''

const fontFace = (data, range) =>
  `@font-face{font-family:'Syne';font-style:normal;font-weight:400 800;font-display:swap;`
  + `src:url(data:font/woff2;base64,${data}) format('woff2');unicode-range:${range}}`

const SYNE_CSS =
  fontFace(SYNE_LATIN, 'U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,'
    + 'U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD')
  + fontFace(SYNE_LATIN_EXT, 'U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,'
    + 'U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF')

function installFonts(ctx) {
  const style = document.createElement('style')
  style.dataset.requrvKbFonts = 'true'
  style.textContent = SYNE_CSS
  document.head.appendChild(style)
  ctx.onDispose(() => style.remove())
}

/** Select the ReQurv theme. False when the theme is not registered (plugin half off). */
const applyTheme = () => requestTheme(THEME_NAME)

// --------------------------------------------------------------- register

export default {
  id: 'requrv-kb',
  name: 'ReQurv KB',
  register(ctx) {
    const api = createApi(ctx)

    ctx.register({ id: 'minimal', area: 'layouts', title: 'ReQurv minimal', order: 100, data: MINIMAL_LAYOUT })
    ctx.register({ id: 'theme', area: THEMES_AREA, data: REQURV_THEME })
    ctx.register({ id: 'nav-prefs', area: SIDEBAR_NAV_PREFS_AREA, data: { hide: HIDDEN_NAV_ROWS } })
    installFonts(ctx)

    // Select the theme once, the first time this half activates. The flag is plugin-scoped storage, so a
    // user who later picks another theme is never overridden; the settings button re-applies on demand.
    if (!ctx.storage.get('themeApplied', false) && applyTheme()) ctx.storage.set('themeApplied', true)

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
