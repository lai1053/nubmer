import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

const API = ''
const CURVE_START_DATE = '2026-04-01'
const BET_PAGE_SIZE = 40
const LINE_LABELS = {
  face: '双面',
  sum: '冠亚和',
  exact: '定位胆'
}

function lineLabel(lineName) {
  return LINE_LABELS[lineName] || lineName || '未知'
}

function slotLabel(lineName, slot) {
  if (lineName === 'face') return `双面槽位 ${slot}`
  return `期位 ${slot}`
}

function fmtNumber(value) {
  const num = Number(value ?? 0)
  return Number.isFinite(num) ? num.toFixed(2) : '-'
}

function fmtIssue(value) {
  if (value == null || value === '') return '—'
  const num = Number(value)
  return Number.isFinite(num) ? String(Math.trunc(num)) : String(value)
}

function fmtBeijingTime(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  const parts = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  }).formatToParts(date)
  const get = (type) => parts.find((part) => part.type === type)?.value || ''
  return `${get('year')}-${get('month')}-${get('day')} ${get('hour')}:${get('minute')}:${get('second')} 北京时间`
}

function parseMaybeJson(value) {
  if (!value) return null
  if (typeof value === 'object') return value
  try {
    return JSON.parse(value)
  } catch {
    return null
  }
}

async function readApiJson(url, options = {}, onUnauthorized) {
  const headers = {
    ...(options.body ? { 'Content-Type': 'application/json' } : {}),
    ...(options.headers || {})
  }
  const response = await fetch(`${API}${url}`, {
    credentials: 'same-origin',
    ...options,
    headers
  })
  const text = await response.text()
  const payload = text ? JSON.parse(text) : {}
  if (response.status === 401) {
    onUnauthorized?.()
    throw new Error(payload.detail || 'unauthorized')
  }
  if (!response.ok) {
    throw new Error(payload.detail || '请求失败')
  }
  return payload
}

function selectionSummary(row) {
  const selection = parseMaybeJson(row.selection_json) || row.selection || {}
  if (row.line_name === 'sum' && selection.sum_value != null) {
    return `和值 ${selection.sum_value}`
  }
  if (row.line_name === 'exact' && selection.number != null) {
    return `位置 ${selection.position_1based} · 号码 ${selection.number}`
  }
  if (row.line_name === 'face') {
    const parts = []
    if (selection.source) parts.push(selection.source)
    if (Array.isArray(selection.big_positions) && selection.big_positions.length) parts.push(`大位 ${selection.big_positions.join(',')}`)
    if (Array.isArray(selection.small_positions) && selection.small_positions.length) parts.push(`小位 ${selection.small_positions.join(',')}`)
    return parts.join(' / ') || '双面票型'
  }
  return '未识别票型'
}

function lineSelection(row, targetLine) {
  if (row.line_name !== targetLine) return '—'
  return selectionSummary(row)
}

function statusLabel(status) {
  if (status === 'settled') return '已结算'
  if (status === 'executed') return '已执行'
  if (status === 'pending') return '待开奖'
  return status || '未知'
}

function broadcastStateLabel(value) {
  if (value === 'broadcasted') return '已播报执行'
  if (value === 'pending_future') return '未触发待执行'
  return '未知'
}

function feedStatusLabel(status) {
  if (status === 'live') return 'SSE 已连接'
  if (status === 'polling') return '轮询兜底中'
  return '连接中'
}

function broadcastStatusLabel(row) {
  const payload = parseMaybeJson(row.payload_json) || {}
  const message = String(payload.message || '')
  if (row.actionable) return '可投'
  if (message.includes('等待前') || message.includes('判窗')) return '等待判窗'
  if (message.includes('窗口已开启')) return '窗口开启'
  if (message.includes('空仓') || message.includes('无可投注选项')) return '无票'
  return '观察中'
}

function broadcastContentSummary(row) {
  const payload = parseMaybeJson(row.payload_json) || {}
  const selection = payload.selection || {}
  if (row.actionable) {
    const parts = []
    if (payload.slot_1based != null) parts.push(slotLabel(row.line_name, payload.slot_1based))
    if (row.line_name === 'sum' && selection.sum_value != null) {
      parts.push(`和值 ${selection.sum_value}`)
    }
    if (row.line_name === 'exact' && selection.position_1based != null && selection.number != null) {
      parts.push(`位置 ${selection.position_1based} · 号码 ${selection.number}`)
    }
    if (row.line_name === 'face') {
      if (selection.source) parts.push(selection.source)
      if (Array.isArray(selection.big_positions) && selection.big_positions.length) parts.push(`大位 ${selection.big_positions.join(',')}`)
      if (Array.isArray(selection.small_positions) && selection.small_positions.length) parts.push(`小位 ${selection.small_positions.join(',')}`)
    }
    if (payload.total_cost != null) parts.push(`${fmtNumber(payload.total_cost)} 分`)
    else if (payload.stake != null) parts.push(`${fmtNumber(payload.stake)} 分`)
    return parts.join(' · ') || '可投'
  }
  return payload.message || '无播报内容'
}

function normalizeProfile(profile, fallbackId) {
  if (!profile) return null
  return {
    id: fallbackId,
    label: fallbackId === 'compare' ? '对照策略' : '主策略',
    is_shadow: fallbackId === 'compare',
    ranges: {},
    totals: {},
    contributions: {},
    today_plan: {},
    current_actions: [],
    daily_curve: [],
    ...profile
  }
}

function extractProfiles(dashboard) {
  if (!dashboard) return []
  const profiles = dashboard.profiles || {}
  const primaryFromProfiles = normalizeProfile(profiles.primary, 'primary')
  const compareFromProfiles = normalizeProfile(profiles.compare, 'compare')
  if (primaryFromProfiles || compareFromProfiles) {
    return [primaryFromProfiles, compareFromProfiles].filter(Boolean)
  }
  return [
    normalizeProfile(
      {
        id: dashboard.active_profile_id || 'primary',
        label: '主策略',
        is_shadow: false,
        ranges: dashboard.ranges || {},
        totals: dashboard.totals || {},
        contributions: dashboard.contributions || {},
        today_plan: dashboard.today_plan || {},
        current_actions: dashboard.current_actions || [],
        daily_curve: dashboard.daily_curve || []
      },
      'primary'
    )
  ]
}

function roleLabel(role) {
  if (role === 'admin') return '管理员'
  return '查看用户'
}

function LoginScreen({ onLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setIsSubmitting(true)
    try {
      const payload = await readApiJson('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password })
      })
      onLogin(payload.user)
    } catch (err) {
      setError(err.message || '登录失败')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-shell">
        <div className="auth-visual" aria-hidden="true">
          <div className="auth-ticker">
            <span>PK10</span>
            <strong>LIVE</strong>
          </div>
          <div className="auth-number-wall">
            {['06', '10', '03', '08', '01', '09', '04', '07', '02', '05'].map((value, index) => (
              <span key={`${value}-${index}`}>{value}</span>
            ))}
          </div>
          <div className="auth-signal">
            <span />
            <span />
            <span />
          </div>
        </div>

        <form className="auth-card" onSubmit={handleSubmit}>
          <div>
            <p className="eyebrow">SECURE CONSOLE</p>
            <h1>PK10 控制台</h1>
          </div>
          <label className="field-label" htmlFor="login-username">用户名</label>
          <input
            id="login-username"
            className="text-input"
            autoComplete="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />
          <label className="field-label" htmlFor="login-password">密码</label>
          <input
            id="login-password"
            className="text-input"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          {error ? <div className="form-error">{error}</div> : null}
          <button type="submit" className="primary-button" disabled={isSubmitting}>
            {isSubmitting ? '登录中' : '登录'}
          </button>
        </form>
      </section>
    </main>
  )
}

function SessionBar({ user, activeView, onOpenDashboard, onOpenAdmin, onLogout }) {
  const [isLoggingOut, setIsLoggingOut] = useState(false)

  async function handleLogout() {
    setIsLoggingOut(true)
    try {
      await readApiJson('/api/auth/logout', { method: 'POST' })
    } finally {
      onLogout()
      setIsLoggingOut(false)
    }
  }

  return (
    <div className="session-bar">
      <div className="session-user">
        <span className="session-dot" />
        <strong>{user?.display_name || user?.username}</strong>
        <span>{roleLabel(user?.role)}</span>
      </div>
      <div className="session-actions">
        <button
          type="button"
          className={`nav-button ${activeView === 'dashboard' ? 'active' : ''}`}
          onClick={onOpenDashboard}
        >
          实时面板
        </button>
        {user?.role === 'admin' ? (
          <button
            type="button"
            className={`nav-button ${activeView === 'admin' ? 'active' : ''}`}
            onClick={onOpenAdmin}
          >
            用户管理
          </button>
        ) : null}
        <button type="button" className="nav-button ghost" onClick={handleLogout} disabled={isLoggingOut}>
          退出
        </button>
      </div>
    </div>
  )
}

function AdminUserRow({ user, currentUser, apiJson, onReload }) {
  const isSelf = user.id === currentUser?.id
  const [displayName, setDisplayName] = useState(user.display_name || user.username)
  const [role, setRole] = useState(user.role || 'viewer')
  const [isActive, setIsActive] = useState(Boolean(user.is_active))
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [isBusy, setIsBusy] = useState(false)

  useEffect(() => {
    setDisplayName(user.display_name || user.username)
    setRole(user.role || 'viewer')
    setIsActive(Boolean(user.is_active))
    setPassword('')
    setMessage('')
    setError('')
  }, [user])

  async function handleSave() {
    setIsBusy(true)
    setMessage('')
    setError('')
    try {
      const body = {
        display_name: displayName,
        role,
        is_active: isActive
      }
      if (password) body.password = password
      await apiJson(`/api/admin/users/${user.id}`, {
        method: 'PATCH',
        body: JSON.stringify(body)
      })
      setPassword('')
      setMessage('已保存')
      onReload()
    } catch (err) {
      setError(err.message || '保存失败')
    } finally {
      setIsBusy(false)
    }
  }

  async function handleDelete() {
    if (isSelf) return
    const ok = window.confirm(`删除用户 ${user.username}？`)
    if (!ok) return
    setIsBusy(true)
    setError('')
    try {
      await apiJson(`/api/admin/users/${user.id}`, { method: 'DELETE' })
      onReload()
    } catch (err) {
      setError(err.message || '删除失败')
    } finally {
      setIsBusy(false)
    }
  }

  return (
    <article className="user-row">
      <div className="user-row-main">
        <div>
          <div className="user-name">{user.username}</div>
          <div className="user-meta">
            {roleLabel(user.role)} · {user.is_active ? '启用中' : '已停用'}
            {user.last_login_at ? ` · 上次登录 ${fmtBeijingTime(user.last_login_at)}` : ''}
          </div>
        </div>
        <span className={`status-pill ${user.is_active ? 'live' : 'muted'}`}>{user.is_active ? 'Active' : 'Paused'}</span>
      </div>

      <div className="user-edit-grid">
        <label>
          <span>显示名</span>
          <input className="text-input compact" value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
        </label>
        <label>
          <span>角色</span>
          <select className="text-input compact" value={role} onChange={(event) => setRole(event.target.value)} disabled={isSelf}>
            <option value="viewer">查看用户</option>
            <option value="admin">管理员</option>
          </select>
        </label>
        <label>
          <span>新密码</span>
          <input
            className="text-input compact"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="留空不改"
          />
        </label>
        <label className="switch-line">
          <input type="checkbox" checked={isActive} onChange={(event) => setIsActive(event.target.checked)} disabled={isSelf} />
          <span>启用账号</span>
        </label>
      </div>

      <div className="row-actions">
        <button type="button" className="secondary-button" onClick={handleSave} disabled={isBusy}>
          保存
        </button>
        <button type="button" className="danger-button" onClick={handleDelete} disabled={isBusy || isSelf}>
          删除
        </button>
        {message ? <span className="form-success">{message}</span> : null}
        {error ? <span className="form-error inline">{error}</span> : null}
      </div>
    </article>
  )
}

function userAgentLabel(value) {
  const text = String(value || '')
  if (!text) return '—'
  if (text.includes('MicroMessenger')) return '微信浏览器'
  if (text.includes('Mobile')) return '移动浏览器'
  if (text.includes('Chrome')) return 'Chrome'
  if (text.includes('Safari')) return 'Safari'
  return text.slice(0, 42)
}

function LoginEventsList({ events, isLoading }) {
  return (
    <section className="admin-card login-events-card">
      <div className="section-head">
        <div>
          <div className="section-eyebrow">LOGIN LOG</div>
          <h2>登录记录</h2>
        </div>
      </div>
      {isLoading ? <div className="empty">正在加载登录记录…</div> : null}
      {!isLoading && events.length === 0 ? <div className="empty">暂无登录记录</div> : null}
      {events.length > 0 ? (
        <div className="login-event-list">
          {events.map((event) => (
            <article className="login-event-row" key={event.id}>
              <div>
                <div className="login-event-user">{event.display_name || event.username}</div>
                <div className="login-event-meta">{event.username} · {roleLabel(event.role)}</div>
              </div>
              <div className="login-event-time">{fmtBeijingTime(event.logged_at)}</div>
              <div className="login-event-meta">{event.ip_address || '—'}</div>
              <div className="login-event-meta">{userAgentLabel(event.user_agent)}</div>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  )
}

function AdminPanel({ user, onLogout, onBack, onUnauthorized }) {
  const [users, setUsers] = useState([])
  const [loginEvents, setLoginEvents] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [isEventsLoading, setIsEventsLoading] = useState(true)
  const [isCreating, setIsCreating] = useState(false)
  const [error, setError] = useState('')
  const [createForm, setCreateForm] = useState({
    username: '',
    display_name: '',
    password: '',
    role: 'viewer',
    is_active: true
  })

  const apiJson = useCallback(
    (url, options) => readApiJson(url, options, onUnauthorized),
    [onUnauthorized]
  )

  const loadUsers = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      const payload = await apiJson('/api/admin/users')
      setUsers(payload.users || [])
    } catch (err) {
      setError(err.message || '加载用户失败')
    } finally {
      setIsLoading(false)
    }
  }, [apiJson])

  const loadLoginEvents = useCallback(async () => {
    setIsEventsLoading(true)
    try {
      const payload = await apiJson('/api/admin/login-events?limit=120')
      setLoginEvents(payload.events || [])
    } catch (err) {
      setError(err.message || '加载登录记录失败')
    } finally {
      setIsEventsLoading(false)
    }
  }, [apiJson])

  useEffect(() => {
    loadUsers()
    loadLoginEvents()
  }, [loadUsers, loadLoginEvents])

  function updateCreateForm(key, value) {
    setCreateForm((prev) => ({ ...prev, [key]: value }))
  }

  async function handleCreate(event) {
    event.preventDefault()
    setIsCreating(true)
    setError('')
    try {
      await apiJson('/api/admin/users', {
        method: 'POST',
        body: JSON.stringify(createForm)
      })
      setCreateForm({
        username: '',
        display_name: '',
        password: '',
        role: 'viewer',
        is_active: true
      })
      await loadUsers()
    } catch (err) {
      setError(err.message || '创建用户失败')
    } finally {
      setIsCreating(false)
    }
  }

  const activeAdmins = users.filter((item) => item.role === 'admin' && item.is_active).length

  return (
    <main className="page admin-page">
      <SessionBar
        user={user}
        activeView="admin"
        onOpenDashboard={onBack}
        onOpenAdmin={() => {}}
        onLogout={onLogout}
      />
      <section className="admin-hero">
        <div>
          <p className="eyebrow">ACCESS CONTROL</p>
          <h1>用户管理</h1>
        </div>
        <div className="admin-stats">
          <MiniStat label="总用户" value={users.length} />
          <MiniStat label="启用管理员" value={activeAdmins} accent="positive" />
        </div>
      </section>

      <section className="admin-grid">
        <form className="admin-card create-user-card" onSubmit={handleCreate}>
          <div className="section-head">
            <div>
              <div className="section-eyebrow">NEW USER</div>
              <h2>新增账号</h2>
            </div>
          </div>
          <label className="field-label" htmlFor="new-username">用户名</label>
          <input
            id="new-username"
            className="text-input"
            value={createForm.username}
            onChange={(event) => updateCreateForm('username', event.target.value)}
          />
          <label className="field-label" htmlFor="new-display-name">显示名</label>
          <input
            id="new-display-name"
            className="text-input"
            value={createForm.display_name}
            onChange={(event) => updateCreateForm('display_name', event.target.value)}
          />
          <label className="field-label" htmlFor="new-password">初始密码</label>
          <input
            id="new-password"
            className="text-input"
            type="password"
            value={createForm.password}
            onChange={(event) => updateCreateForm('password', event.target.value)}
          />
          <label className="field-label" htmlFor="new-role">角色</label>
          <select
            id="new-role"
            className="text-input"
            value={createForm.role}
            onChange={(event) => updateCreateForm('role', event.target.value)}
          >
            <option value="viewer">查看用户</option>
            <option value="admin">管理员</option>
          </select>
          <label className="switch-line">
            <input
              type="checkbox"
              checked={createForm.is_active}
              onChange={(event) => updateCreateForm('is_active', event.target.checked)}
            />
            <span>创建后启用</span>
          </label>
          <button type="submit" className="primary-button" disabled={isCreating}>
            {isCreating ? '创建中' : '创建账号'}
          </button>
          {error ? <div className="form-error">{error}</div> : null}
        </form>

        <section className="admin-card user-list-card">
          <div className="section-head">
            <div>
              <div className="section-eyebrow">USERS</div>
              <h2>账号列表</h2>
            </div>
          </div>
          {isLoading ? <div className="empty">正在加载用户…</div> : null}
          {!isLoading && users.length === 0 ? <div className="empty">暂无用户</div> : null}
          <div className="user-list">
            {users.map((item) => (
              <AdminUserRow key={item.id} user={item} currentUser={user} apiJson={apiJson} onReload={loadUsers} />
            ))}
          </div>
        </section>
        <LoginEventsList events={loginEvents} isLoading={isEventsLoading} />
      </section>
    </main>
  )
}

function useDashboard(onUnauthorized) {
  const [dashboard, setDashboard] = useState(null)
  const [feedStatus, setFeedStatus] = useState('connecting')
  const [betPage, setBetPage] = useState(1)
  const [betScope, setBetScope] = useState('all')
  const [broadcastPage, setBroadcastPage] = useState(1)
  const [broadcastIssueQuery, setBroadcastIssueQuery] = useState('')
  const [broadcastIssueInput, setBroadcastIssueInput] = useState('')
  const [betPageData, setBetPageData] = useState({
    rows: [],
    page: 1,
    page_size: BET_PAGE_SIZE,
    total: 0,
    total_pages: 1,
    has_prev: false,
    has_next: false,
    scope: 'all',
    counts: { all: 0, broadcasted: 0, pending_future: 0 }
  })
  const [broadcastPageData, setBroadcastPageData] = useState({
    rows: [],
    page: 1,
    page_size: BET_PAGE_SIZE,
    total: 0,
    total_pages: 1,
    has_prev: false,
    has_next: false
  })
  const betPageRef = useRef(1)
  const betScopeRef = useRef('all')
  const broadcastPageRef = useRef(1)
  const broadcastIssueRef = useRef('')

  useEffect(() => {
    betPageRef.current = betPage
  }, [betPage])

  useEffect(() => {
    betScopeRef.current = betScope
  }, [betScope])

  useEffect(() => {
    broadcastPageRef.current = broadcastPage
  }, [broadcastPage])

  useEffect(() => {
    broadcastIssueRef.current = broadcastIssueQuery
  }, [broadcastIssueQuery])

  const handleRefreshError = useCallback(
    (error) => {
      if (error?.message === 'unauthorized') return
      setFeedStatus('polling')
    },
    []
  )

  async function refreshSnapshot() {
    const dashboardRes = await readApiJson('/api/dashboard', {}, onUnauthorized)
    setDashboard(dashboardRes)
  }

  async function refreshBets(targetPage, targetScope = betScopeRef.current) {
    const page = Math.max(1, Number(targetPage || 1))
    const query = new URLSearchParams({
      page: String(page),
      page_size: String(BET_PAGE_SIZE),
      scope: String(targetScope || 'all')
    })
    const betRes = await readApiJson(`/api/history/bets?${query.toString()}`, {}, onUnauthorized)
    setBetPageData({
      rows: betRes.rows ?? [],
      page: betRes.page ?? page,
      page_size: betRes.page_size ?? BET_PAGE_SIZE,
      total: betRes.total ?? 0,
      total_pages: betRes.total_pages ?? 1,
      has_prev: Boolean(betRes.has_prev),
      has_next: Boolean(betRes.has_next),
      scope: betRes.scope ?? targetScope ?? 'all',
      counts: betRes.counts ?? { all: 0, broadcasted: 0, pending_future: 0 }
    })
  }

  async function refreshBroadcasts(targetPage, targetIssue = broadcastIssueRef.current) {
    const page = Math.max(1, Number(targetPage || 1))
    const issue = String(targetIssue || '').trim()
    const query = new URLSearchParams({
      page: String(page),
      page_size: String(BET_PAGE_SIZE)
    })
    if (issue) query.set('issue', issue)
    const broadcastRes = await readApiJson(`/api/history/broadcasts?${query.toString()}`, {}, onUnauthorized)
    setBroadcastPageData({
      rows: broadcastRes.rows ?? [],
      page: broadcastRes.page ?? page,
      page_size: broadcastRes.page_size ?? BET_PAGE_SIZE,
      total: broadcastRes.total ?? 0,
      total_pages: broadcastRes.total_pages ?? 1,
      has_prev: Boolean(broadcastRes.has_prev),
      has_next: Boolean(broadcastRes.has_next),
      issue: broadcastRes.issue ?? issue
    })
  }

  useEffect(() => {
    let isClosed = false
    let sse = null

    async function refreshAll() {
      try {
        await Promise.all([
          refreshSnapshot(),
          refreshBets(betPageRef.current, betScopeRef.current),
          refreshBroadcasts(broadcastPageRef.current, broadcastIssueRef.current)
        ])
      } catch (error) {
        handleRefreshError(error)
      }
    }

    function connectSse() {
      if (isClosed) return
      setFeedStatus((prev) => (prev === 'live' ? prev : 'connecting'))
      sse = new EventSource(`${API}/events/stream`, { withCredentials: true })
      sse.onopen = () => {
        if (!isClosed) setFeedStatus('live')
      }
      sse.onmessage = (event) => {
        if (isClosed) return
        setFeedStatus('live')
        try {
          const payload = JSON.parse(event.data)
          if (payload?.payload) {
            setDashboard(payload.payload)
          } else {
            setDashboard(payload)
          }
        } catch {
          // Ignore parse errors and force a full refetch below.
        }
        refreshAll()
      }
      sse.onerror = () => {
        if (!isClosed) setFeedStatus('polling')
      }
    }

    refreshAll()
    connectSse()

    const pollTimer = window.setInterval(() => {
      refreshAll()
    }, 5000)

    return () => {
      isClosed = true
      window.clearInterval(pollTimer)
      if (sse) sse.close()
    }
  }, [handleRefreshError, onUnauthorized])

  useEffect(() => {
    refreshBets(betPage, betScope).catch(handleRefreshError)
  }, [betPage, betScope])

  useEffect(() => {
    refreshBroadcasts(broadcastPage, broadcastIssueQuery).catch(handleRefreshError)
  }, [broadcastPage, broadcastIssueQuery])

  return {
    dashboard,
    feedStatus,
    betPageData,
    betPage,
    setBetPage,
    betScope,
    setBetScope,
    broadcastPageData,
    broadcastPage,
    setBroadcastPage,
    setBroadcastIssueQuery,
    broadcastIssueInput,
    setBroadcastIssueInput
  }
}

function useIsMobile() {
  const [isMobile, setIsMobile] = useState(() => {
    if (typeof window === 'undefined') return false
    return window.matchMedia('(max-width: 760px)').matches
  })

  useEffect(() => {
    const media = window.matchMedia('(max-width: 760px)')
    const handleChange = () => setIsMobile(media.matches)
    handleChange()
    media.addEventListener('change', handleChange)
    return () => media.removeEventListener('change', handleChange)
  }, [])

  return isMobile
}

function MiniStat({ label, value, accent, note }) {
  return (
    <div className="mini-stat">
      <div className="mini-label">{label}</div>
      <div className={`mini-value ${accent || ''}`}>{value}</div>
      {note ? <div className="mini-note">{note}</div> : null}
    </div>
  )
}

function CoreMetrics({ totals }) {
  return (
    <section className="profile-metrics core-metrics">
      <MiniStat label="已结算总积分" value={fmtNumber(totals?.settled_bankroll)} accent="primary" />
      <MiniStat
        label="今日浮盈"
        value={fmtNumber(totals?.today_provisional_pnl)}
        accent={Number(totals?.today_provisional_pnl) >= 0 ? 'positive' : 'negative'}
      />
      <MiniStat label="若此刻收盘" value={fmtNumber(totals?.estimated_close_bankroll)} accent="primary" />
    </section>
  )
}

function MarketChip({ label, value }) {
  return (
    <div className="market-chip">
      <span className="market-chip-label">{label}</span>
      <strong>{value || '—'}</strong>
    </div>
  )
}

function LiveHeader({ market, feedStatus, historyStartDate, simulationStartDate }) {
  return (
    <header className="live-header">
      <div className="live-header-title">
        <p className="eyebrow">PK10 LIVE</p>
        <h1>实时工作台</h1>
      </div>
      <div className="live-header-grid">
        <MarketChip label="当前期开奖" value={fmtIssue(market?.pre_draw_issue)} />
        <MarketChip label="下期开奖" value={fmtIssue(market?.draw_issue)} />
        <MarketChip label="连接状态" value={feedStatusLabel(feedStatus)} />
        <MarketChip label="预热日期" value={`${historyStartDate} 起`} />
        <MarketChip label="模拟投注" value={`${simulationStartDate} 起`} />
        <MarketChip label="服务时间" value={market?.server_time || '—'} />
      </div>
    </header>
  )
}

function MobileHistoryPair({ label, value, tone = '' }) {
  return (
    <div className={`mobile-history-pair ${tone}`.trim()}>
      <span>{label}</span>
      <strong>{value || '—'}</strong>
    </div>
  )
}

function EquityCurve({ rows, startDate }) {
  const data = rows ?? []
  const width = 920
  const height = 280
  const padding = 28

  const { path, bars } = useMemo(() => {
    if (!data.length) return { path: '', bars: [] }
    const values = data.map((row) => Number(row.settled_bankroll ?? 0))
    const min = Math.min(...values)
    const max = Math.max(...values)
    const span = Math.max(1, max - min)
    const x = (index) => padding + ((width - padding * 2) * index) / Math.max(1, data.length - 1)
    const y = (value) => height - padding - ((height - padding * 2) * (value - min)) / span
    const curve = data
      .map((row, index) => `${index === 0 ? 'M' : 'L'} ${x(index).toFixed(2)} ${y(Number(row.settled_bankroll ?? 0)).toFixed(2)}`)
      .join(' ')
    const pnlBars = data.map((row, index) => {
      const pnl = Number(row.total_real_pnl ?? 0)
      const barHeight = Math.min(60, Math.abs(pnl) * 0.9)
      return {
        x: x(index) - 2,
        y: pnl >= 0 ? height - padding - barHeight : height - padding,
        h: barHeight,
        color: pnl >= 0 ? '#cf4f24' : '#111111'
      }
    })
    return { path: curve, bars: pnlBars }
  }, [data])

  if (!data.length) return <div className="empty">暂无资金曲线</div>

  return (
    <div className="curve-shell">
      <div className="curve-meta">展示区间：{startDate} 起</div>
      <svg viewBox={`0 0 ${width} ${height}`} className="curve-svg">
        <rect x="0" y="0" width={width} height={height} rx="18" fill="rgba(255,255,255,0.02)" />
        {[0.2, 0.4, 0.6, 0.8].map((ratio) => (
          <line
            key={ratio}
            x1={padding}
            x2={width - padding}
            y1={padding + (height - padding * 2) * ratio}
            y2={padding + (height - padding * 2) * ratio}
            stroke="rgba(27, 18, 12, 0.12)"
            strokeDasharray="6 6"
          />
        ))}
        {bars.map((bar, index) => (
          <rect key={index} x={bar.x} y={bar.y} width="4" height={bar.h} fill={bar.color} opacity="0.48" rx="2" />
        ))}
        <path d={path} fill="none" stroke="#111111" strokeWidth="3" strokeLinecap="round" />
      </svg>
      <div className="curve-axis">
        {data.filter((_, index) => index % Math.max(1, Math.floor(data.length / 7)) === 0).map((row) => (
          <span key={row.date}>{row.date}</span>
        ))}
      </div>
    </div>
  )
}

function ActionCard({ item }) {
  const selection = item.selection || {}
  return (
    <article className="action-card">
      <div className="action-head">
        <span className="chip chip-alert">{lineLabel(item.line_name)}</span>
        <span className="action-issue">下期 {item.draw_issue}</span>
      </div>
      <div className="action-title">{slotLabel(item.line_name, item.slot_1based)}</div>
      <div className="action-body">
        {'sum_value' in selection ? <span>和值 {selection.sum_value}</span> : null}
        {'number' in selection ? <span>号码 {selection.number}</span> : null}
        {'position_1based' in selection ? <span>位置 {selection.position_1based}</span> : null}
        {'source' in selection ? <span>{selection.source}</span> : null}
        {'big_positions' in selection ? <span>大位 {selection.big_positions.join(',')}</span> : null}
        {'small_positions' in selection ? <span>小位 {selection.small_positions.join(',')}</span> : null}
      </div>
      <div className="action-money">{fmtNumber(item.total_cost)} 分</div>
      <div className="action-note">{item.odds_display}</div>
    </article>
  )
}

function LinePanel({ label, state, fixedStake = false }) {
  const requested = state?.requested_slots ?? 0
  const funded = state?.funded_slots ?? 0
  const executed = state?.executed_slots ?? 0
  const pending = state?.pending_slots ?? 0
  const provisionalPnl = Number(state?.provisional_pnl ?? 0)

  return (
    <section className="line-panel">
      <div className="line-header">
        <div>
          <div className="line-name">{label}</div>
          <div className="line-message">{state?.message || '无数据'}</div>
        </div>
        <div className="line-badge">{state?.status || 'idle'}</div>
      </div>
      <div className="line-summary">
        <div className="line-primary">
          <span>浮动盈亏</span>
          <strong className={provisionalPnl >= 0 ? 'positive-text' : 'negative-text'}>{fmtNumber(provisionalPnl)}</strong>
        </div>
        <div className="line-grid">
          <MobileHistoryPair label="档位" value={fixedStake ? '固定 10' : `${state?.multiplier_value ?? 0}x`} />
          <MobileHistoryPair label="计划/可投" value={`${requested}/${funded}`} />
          <MobileHistoryPair label="已执行/待执行" value={`${executed}/${pending}`} />
        </div>
      </div>
    </section>
  )
}

function ContributionInline({ contribution }) {
  return (
    <section className="contribution-inline">
      <strong>分项贡献：</strong>
      <span>双面已结算 {fmtNumber(contribution?.settled?.face)}</span>
      <span>冠亚和已结算 {fmtNumber(contribution?.settled?.sum)}</span>
      <span>定位胆已结算 {fmtNumber(contribution?.settled?.exact)}</span>
      <span>双面今日浮动 {fmtNumber(contribution?.today_provisional?.face)}</span>
      <span>冠亚和今日浮动 {fmtNumber(contribution?.today_provisional?.sum)}</span>
      <span>定位胆今日浮动 {fmtNumber(contribution?.today_provisional?.exact)}</span>
    </section>
  )
}

function StrategyBadge({ profile }) {
  return (
    <div className={`strategy-badge ${profile?.is_shadow ? 'shadow' : 'live'}`}>
      <div className="strategy-badge-top">
        <span className="strategy-badge-kind">{profile?.is_shadow ? 'Shadow' : 'Live'}</span>
        <span className="strategy-badge-mode">{profile?.is_shadow ? '影子对照' : '真实主策略'}</span>
      </div>
      <div className="strategy-badge-label">{profile?.label || '未命名策略'}</div>
      <div className="strategy-badge-note">{profile?.is_shadow ? '只做页面对照，不写入真实历史表' : '真实投注账本与播报历史的唯一来源'}</div>
    </div>
  )
}

function StrategyPanel({ profile, feedStatus }) {
  const totals = profile?.totals || {}
  const contribution = profile?.contributions || {}
  const todayPlan = profile?.today_plan || {}
  const currentActions = profile?.current_actions || []
  const ranges = profile?.ranges || {}
  const simulationStartDate = ranges.simulation_start_date || CURVE_START_DATE
  const executableActions = currentActions.filter((item) => item.slot_1based)

  return (
    <section className={`strategy-panel ${profile?.is_shadow ? 'shadow' : 'live'}`}>
      <div className="profile-heading">
        <div>
          <div className="section-eyebrow">{profile?.is_shadow ? 'SHADOW PROFILE' : 'LIVE PROFILE'}</div>
          <h2>{profile?.label || '未命名策略'}</h2>
        </div>
        <div className="profile-meta">
          <span className={`profile-chip ${profile?.is_shadow ? 'shadow' : 'live'}`}>{profile?.is_shadow ? 'Shadow' : 'Live'}</span>
          <span>{feedStatusLabel(feedStatus)}</span>
        </div>
      </div>

      <section className="card card-actions">
        <div className="section-head">
          <div>
            <div className="section-eyebrow">CURRENT ACTIONS</div>
            <h2>{profile?.is_shadow ? '对照投注播报' : '当前投注播报'}</h2>
          </div>
          <div className="section-note">
            {profile?.is_shadow ? '只用于同口径比较，不写入真实投注历史。' : '当前可执行动作优先显示。'}
          </div>
        </div>
        <div className="action-grid">
          {executableActions.length ? (
            executableActions.map((item) => <ActionCard key={`${profile?.id}-${item.line_name}-${item.slot_1based}`} item={item} />)
          ) : (
            <div className="empty hero-empty">无可投注选项</div>
          )}
        </div>
      </section>

      <CoreMetrics totals={totals} />

      <div className="three-grid">
        <LinePanel label="双面" state={todayPlan.face} />
        <LinePanel label="冠亚和" state={todayPlan.sum} />
        <LinePanel label="定位胆" state={todayPlan.exact} fixedStake />
      </div>

      <section className="card">
        <div className="section-head">
          <div>
            <div className="section-eyebrow">BANKROLL CURVE</div>
            <h2>日维资金曲线</h2>
          </div>
          <div className="section-note">从 {simulationStartDate} 起展示，含今日 provisional 标记。</div>
        </div>
        <EquityCurve rows={profile?.daily_curve || []} startDate={simulationStartDate} />
      </section>

      <section className="profile-secondary">
        <MiniStat label="峰值回撤" value={fmtNumber(totals.max_drawdown)} accent="negative" />
        <MiniStat label="最低资金" value={fmtNumber(totals.min_bankroll)} />
        <MiniStat label="峰值资金" value={fmtNumber(totals.peak_bankroll)} />
      </section>

      <ContributionInline contribution={contribution} />
    </section>
  )
}

function BroadcastHistory({ pageData, onPageChange, issueInput, onIssueInputChange, onIssueSubmit, onIssueClear }) {
  const rows = pageData.rows || []
  const emptyLabel = pageData.issue ? `未找到与 ${pageData.issue} 相关的播报` : '暂无记录'

  return (
    <section className="history-card history-card-wide">
      <div className="history-heading">
        <div>
          <div className="history-title">播报记录历史</div>
          <div className="history-subhead">仅记录主策略真实线上账本。对照 Shadow 策略不落库，只在上方面板做实时比较。</div>
        </div>
        <form className="history-search" onSubmit={onIssueSubmit}>
          <label className="history-search-label" htmlFor="broadcast-issue-search">按期号直查</label>
          <div className="history-search-row">
            <input
              id="broadcast-issue-search"
              className="history-search-input"
              inputMode="numeric"
              placeholder="输入 33984657 或 33984658"
              value={issueInput}
              onChange={(event) => onIssueInputChange(event.target.value)}
            />
            <button type="submit" className="search-button">检索</button>
            <button type="button" className="search-button ghost" onClick={onIssueClear}>清空</button>
          </div>
        </form>
      </div>
      {rows.length === 0 ? <div className="empty">{emptyLabel}</div> : null}
      {rows.length > 0 ? (
        <>
          <div className="history-table-shell desktop-history-shell">
          <table className="bet-table">
            <thead>
              <tr>
                <th>时间</th>
                <th>日期</th>
                <th>玩法</th>
                <th>触发开奖期号</th>
                <th>播报目标期号</th>
                <th>状态</th>
                <th>播报内容</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={`broadcast-${row.id}`}>
                  <td>{row.server_time || '—'}</td>
                  <td>{row.draw_date || '—'}</td>
                  <td>{lineLabel(row.line_name)}</td>
                  <td>{fmtIssue(row.pre_draw_issue)}</td>
                  <td>{fmtIssue(row.draw_issue)}</td>
                  <td>{broadcastStatusLabel(row)}</td>
                  <td>{broadcastContentSummary(row)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
          <div className="mobile-history-list">
            {rows.map((row) => (
              <article className="mobile-history-card" key={`broadcast-mobile-${row.id}`}>
                <div className="mobile-history-head">
                  <div>
                    <div className="mobile-history-kicker">播报记录</div>
                    <div className="mobile-history-title">{lineLabel(row.line_name)} · {fmtIssue(row.draw_issue)}</div>
                  </div>
                  <span className="mobile-history-status">{broadcastStatusLabel(row)}</span>
                </div>
                <div className="mobile-history-grid">
                  <MobileHistoryPair label="时间" value={row.server_time} />
                  <MobileHistoryPair label="触发期" value={fmtIssue(row.pre_draw_issue)} />
                </div>
                <div className="mobile-history-body">{broadcastContentSummary(row)}</div>
                <details className="mobile-history-details">
                  <summary>更多信息</summary>
                  <div className="mobile-selection-list">
                    <MobileHistoryPair label="日期" value={row.draw_date} />
                    <MobileHistoryPair label="目标期号" value={fmtIssue(row.draw_issue)} />
                  </div>
                </details>
              </article>
            ))}
          </div>
        </>
      ) : null}
      <Pagination
        page={pageData.page || 1}
        totalPages={pageData.total_pages || 1}
        total={pageData.total || 0}
        hasPrev={pageData.has_prev}
        hasNext={pageData.has_next}
        onChange={onPageChange}
      />
    </section>
  )
}

function buildPaginationItems(page, totalPages) {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1)
  }
  if (page <= 4) {
    return [1, 2, 3, 4, 5, 'ellipsis-right', totalPages]
  }
  if (page >= totalPages - 3) {
    return [1, 'ellipsis-left', totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1, totalPages]
  }
  return [1, 'ellipsis-left', page - 1, page, page + 1, 'ellipsis-right', totalPages]
}

function Pagination({ page, totalPages, total, onChange, hasPrev, hasNext }) {
  const pageItems = buildPaginationItems(page, totalPages)

  return (
    <div className="pagination">
      <div className="pagination-summary">第 {page} / {totalPages} 页，共 {total} 条</div>
      <div className="pagination-actions">
        <button type="button" className="page-button" disabled={!hasPrev} onClick={() => onChange(page - 1)}>
          上一页
        </button>
        {pageItems.map((value) =>
          typeof value === 'number' ? (
            <button
              type="button"
              key={value}
              className={`page-button ${value === page ? 'active' : ''}`}
              onClick={() => onChange(value)}
            >
              {value}
            </button>
          ) : (
            <span key={value} className="page-ellipsis">
              …
            </span>
          )
        )}
        <button type="button" className="page-button" disabled={!hasNext} onClick={() => onChange(page + 1)}>
          下一页
        </button>
      </div>
    </div>
  )
}

function BetHistory({ pageData, onPageChange, betScope, onScopeChange }) {
  const rows = pageData.rows || []
  const counts = pageData.counts || { all: 0, broadcasted: 0, pending_future: 0 }

  return (
    <section className="history-card history-card-wide">
      <div className="history-heading">
        <div>
          <div className="history-title">投注历史记录</div>
          <div className="history-subhead">
            仅记录主策略真实线上账本。已播报执行 {counts.broadcasted ?? 0} 条，未触发待执行 {counts.pending_future ?? 0} 条。
          </div>
        </div>
        <div className="scope-tabs">
          {[
            ['all', '全部'],
            ['broadcasted', '已播报'],
            ['pending_future', '未触发待执行']
          ].map(([value, label]) => (
            <button
              type="button"
              key={value}
              className={`scope-tab ${betScope === value ? 'active' : ''}`}
              onClick={() => {
                onPageChange(1)
                onScopeChange(value)
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      {rows.length === 0 ? <div className="empty">暂无记录</div> : null}
      {rows.length > 0 ? (
        <>
          <div className="history-table-shell desktop-history-shell">
          <table className="bet-table">
            <thead>
              <tr>
                <th>日期</th>
                <th>开奖期号</th>
                <th>期位</th>
                <th>双面</th>
                <th>冠亚和</th>
                <th>定位胆</th>
                <th>状态</th>
                <th>播报状态</th>
                <th>播报时间</th>
                <th>开奖时间</th>
                <th>开奖号码</th>
                <th>赔率说明</th>
                <th>投注金额</th>
                <th>盈亏</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={`bet-${row.id}`}>
                  <td>{row.draw_date}</td>
                  <td>{fmtIssue(row.pre_draw_issue)}</td>
                  <td>{slotLabel(row.line_name, row.slot_1based)}</td>
                  <td>{lineSelection(row, 'face')}</td>
                  <td>{lineSelection(row, 'sum')}</td>
                  <td>{lineSelection(row, 'exact')}</td>
                  <td>{statusLabel(row.status)}</td>
                  <td>{broadcastStateLabel(row.broadcast_state)}</td>
                  <td>{row.broadcast_time || '—'}</td>
                  <td>{row.pre_draw_time || '—'}</td>
                  <td>{row.pre_draw_code || '—'}</td>
                  <td>{row.odds_display}</td>
                  <td>{fmtNumber(row.total_cost)} 分</td>
                  <td className={row.pnl == null ? '' : Number(row.pnl) >= 0 ? 'positive-text' : 'negative-text'}>
                    {row.pnl == null ? '—' : `${fmtNumber(row.pnl)} 分`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
          <div className="mobile-history-list">
            {rows.map((row) => (
              <article className="mobile-history-card" key={`bet-mobile-${row.id}`}>
                <div className="mobile-history-head">
                  <div>
                    <div className="mobile-history-kicker">投注历史</div>
                    <div className="mobile-history-title">{fmtIssue(row.pre_draw_issue)} · {slotLabel(row.line_name, row.slot_1based)}</div>
                  </div>
                  <span className="mobile-history-status">{statusLabel(row.status)}</span>
                </div>
                <div className="mobile-history-grid">
                  <MobileHistoryPair label="投注金额" value={`${fmtNumber(row.total_cost)} 分`} />
                  <MobileHistoryPair
                    label="盈亏"
                    value={row.pnl == null ? '—' : `${fmtNumber(row.pnl)} 分`}
                    tone={row.pnl == null ? '' : Number(row.pnl) >= 0 ? 'positive-text' : 'negative-text'}
                  />
                </div>
                <div className="mobile-history-body">{selectionSummary(row)}</div>
                <details className="mobile-history-details">
                  <summary>详细记录</summary>
                  <div className="mobile-selection-list">
                    <MobileHistoryPair label="日期" value={row.draw_date} />
                    <MobileHistoryPair label="播报状态" value={broadcastStateLabel(row.broadcast_state)} />
                    <MobileHistoryPair label="播报时间" value={row.broadcast_time} />
                    <MobileHistoryPair label="开奖时间" value={row.pre_draw_time} />
                    <MobileHistoryPair label="开奖号码" value={row.pre_draw_code} />
                    <MobileHistoryPair label="赔率说明" value={row.odds_display} />
                  </div>
                </details>
              </article>
            ))}
          </div>
        </>
      ) : null}
      <Pagination
        page={pageData.page || 1}
        totalPages={pageData.total_pages || 1}
        total={pageData.total || 0}
        hasPrev={pageData.has_prev}
        hasNext={pageData.has_next}
        onChange={onPageChange}
      />
    </section>
  )
}

function DashboardPage({ user, onLogout, onOpenAdmin, onUnauthorized }) {
  const {
    dashboard,
    feedStatus,
    betPageData,
    betPage,
    setBetPage,
    betScope,
    setBetScope,
    broadcastPageData,
    broadcastPage,
    setBroadcastPage,
    setBroadcastIssueQuery,
    broadcastIssueInput,
    setBroadcastIssueInput
  } = useDashboard(onUnauthorized)

  const profiles = useMemo(() => extractProfiles(dashboard), [dashboard])
  const isMobile = useIsMobile()

  if (!dashboard) {
    return <div className="loading">正在拉取 PK10 实时积分面板…</div>
  }

  const primaryProfile = profiles.find((profile) => profile.id === 'primary') || profiles[0] || normalizeProfile({}, 'primary')
  const compareProfiles = profiles.filter((profile) => profile.id !== primaryProfile.id)
  const historyStartDate = primaryProfile?.ranges?.history_start_date || dashboard?.ranges?.history_start_date || '2026-01-01'
  const simulationStartDate = primaryProfile?.ranges?.simulation_start_date || dashboard?.ranges?.simulation_start_date || CURVE_START_DATE
  const market = dashboard.market || {}

  function handleBroadcastIssueSubmit(event) {
    event.preventDefault()
    setBroadcastPage(1)
    setBroadcastIssueQuery(String(broadcastIssueInput || '').trim())
  }

  function handleBroadcastIssueClear() {
    setBroadcastIssueInput('')
    setBroadcastPage(1)
    setBroadcastIssueQuery('')
  }

  return (
    <main className="page">
      <SessionBar
        user={user}
        activeView="dashboard"
        onOpenDashboard={() => {}}
        onOpenAdmin={onOpenAdmin}
        onLogout={onLogout}
      />
      <LiveHeader
        market={market}
        feedStatus={feedStatus}
        historyStartDate={historyStartDate}
        simulationStartDate={simulationStartDate}
      />

      <section className="layout">
        <div className="main-column">
          {isMobile ? (
            <>
              <StrategyPanel profile={primaryProfile} feedStatus={feedStatus} />
              {compareProfiles.length ? (
                <details className="compare-drawer">
                  <summary>
                    <span>对照策略</span>
                    <strong>{compareProfiles.length} 个</strong>
                  </summary>
                  <div className="compare-drawer-body">
                    {compareProfiles.map((profile) => (
                      <StrategyPanel key={profile.id} profile={profile} feedStatus={feedStatus} />
                    ))}
                  </div>
                </details>
              ) : null}
            </>
          ) : (
            <section className={`strategy-grid strategy-grid-${Math.max(1, profiles.length)}`}>
              {profiles.map((profile) => (
                <StrategyPanel key={profile.id} profile={profile} feedStatus={feedStatus} />
              ))}
            </section>
          )}

          <BetHistory pageData={betPageData} onPageChange={setBetPage} page={betPage} betScope={betScope} onScopeChange={setBetScope} />
          <BroadcastHistory
            pageData={broadcastPageData}
            onPageChange={setBroadcastPage}
            page={broadcastPage}
            issueInput={broadcastIssueInput}
            onIssueInputChange={setBroadcastIssueInput}
            onIssueSubmit={handleBroadcastIssueSubmit}
            onIssueClear={handleBroadcastIssueClear}
          />
        </div>
      </section>
    </main>
  )
}

export default function App() {
  const [authStatus, setAuthStatus] = useState('checking')
  const [user, setUser] = useState(null)
  const [view, setView] = useState('dashboard')

  const handleUnauthorized = useCallback(() => {
    setUser(null)
    setView('dashboard')
    setAuthStatus('unauthenticated')
  }, [])

  useEffect(() => {
    let isMounted = true
    readApiJson('/api/auth/me')
      .then((payload) => {
        if (!isMounted) return
        setUser(payload.user)
        setAuthStatus('authenticated')
      })
      .catch(() => {
        if (!isMounted) return
        setUser(null)
        setAuthStatus('unauthenticated')
      })
    return () => {
      isMounted = false
    }
  }, [])

  function handleLogin(nextUser) {
    setUser(nextUser)
    setView('dashboard')
    setAuthStatus('authenticated')
  }

  function handleLogout() {
    setUser(null)
    setView('dashboard')
    setAuthStatus('unauthenticated')
  }

  if (authStatus === 'checking') {
    return <div className="loading">正在检查登录状态…</div>
  }

  if (!user) {
    return <LoginScreen onLogin={handleLogin} />
  }

  if (view === 'admin' && user.role === 'admin') {
    return (
      <AdminPanel
        user={user}
        onLogout={handleLogout}
        onBack={() => setView('dashboard')}
        onUnauthorized={handleUnauthorized}
      />
    )
  }

  return (
    <DashboardPage
      user={user}
      onLogout={handleLogout}
      onOpenAdmin={() => setView('admin')}
      onUnauthorized={handleUnauthorized}
    />
  )
}
