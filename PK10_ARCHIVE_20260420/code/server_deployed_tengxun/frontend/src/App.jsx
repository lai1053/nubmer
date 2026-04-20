import { useEffect, useMemo, useRef, useState } from 'react'

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

function fmtNumber(value) {
  const num = Number(value ?? 0)
  return Number.isFinite(num) ? num.toFixed(2) : '-'
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
    if (payload.slot_1based != null) parts.push(`期位 ${payload.slot_1based}`)
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

function useDashboard() {
  const [dashboard, setDashboard] = useState(null)
  const [curveRows, setCurveRows] = useState([])
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

  async function refreshSnapshot() {
    const [dashboardRes, curveRes] = await Promise.all([
      fetch(`${API}/api/dashboard`).then((res) => res.json()),
      fetch(`${API}/api/curve/daily?start_date=${CURVE_START_DATE}`).then((res) => res.json())
    ])
    setDashboard(dashboardRes)
    setCurveRows(curveRes.rows ?? [])
  }

  async function refreshBets(targetPage, targetScope = betScopeRef.current) {
    const page = Math.max(1, Number(targetPage || 1))
    const query = new URLSearchParams({
      page: String(page),
      page_size: String(BET_PAGE_SIZE),
      scope: String(targetScope || 'all')
    })
    const betRes = await fetch(`${API}/api/history/bets?${query.toString()}`).then((res) => res.json())
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
    const broadcastRes = await fetch(`${API}/api/history/broadcasts?${query.toString()}`).then((res) => res.json())
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
    refreshSnapshot()
    refreshBets(1, 'all')
    refreshBroadcasts(1, '')
    const sse = new EventSource(`${API}/events/stream`)
    sse.onmessage = (event) => {
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
      refreshSnapshot()
      refreshBets(betPageRef.current, betScopeRef.current)
      refreshBroadcasts(broadcastPageRef.current, broadcastIssueRef.current)
    }
    return () => sse.close()
  }, [])

  useEffect(() => {
    refreshBets(betPage, betScope)
  }, [betPage, betScope])

  useEffect(() => {
    refreshBroadcasts(broadcastPage, broadcastIssueQuery)
  }, [broadcastPage, broadcastIssueQuery])

  return {
    dashboard,
    curveRows,
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

function MiniStat({ label, value, accent, note }) {
  return (
    <div className="mini-stat">
      <div className="mini-label">{label}</div>
      <div className={`mini-value ${accent || ''}`}>{value}</div>
      {note ? <div className="mini-note">{note}</div> : null}
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
      <div className="action-title">期位 {item.slot_1based}</div>
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

  return (
    <section className="line-panel">
      <div className="line-header">
        <div>
          <div className="line-name">{label}</div>
          <div className="line-message">{state?.message || '无数据'}</div>
        </div>
        <div className="line-badge">{state?.status || 'idle'}</div>
      </div>
      <div className="line-grid">
        <MiniStat label="档位" value={fixedStake ? '固定 10' : `${state?.multiplier_value ?? 0}x`} />
        <MiniStat label="请求" value={requested} />
        <MiniStat label="成交" value={funded} />
        <MiniStat label="已执行" value={executed} />
        <MiniStat label="待执行" value={pending} />
        <MiniStat label="浮动盈亏" value={fmtNumber(state?.provisional_pnl)} accent={Number(state?.provisional_pnl) >= 0 ? 'positive' : 'negative'} />
      </div>
    </section>
  )
}

function BroadcastHistory({ pageData, onPageChange, issueInput, onIssueInputChange, onIssueSubmit, onIssueClear }) {
  const rows = pageData.rows || []

  return (
    <section className="history-card history-card-wide">
      <div className="history-heading">
        <div>
          <div className="history-title">播报记录历史</div>
          <div className="history-subhead">这里只保留 2026-04-20 起真实可执行的投注播报，不再记录窗口开启、空仓或等待判窗这类状态快照。</div>
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
      <div className="history-table-shell">
        {rows.length === 0 ? <div className="empty">{pageData.issue ? `未找到与 ${pageData.issue} 相关的播报` : '暂无记录'}</div> : null}
        {rows.length > 0 ? (
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
              {rows.map((row) => {
                const payload = parseMaybeJson(row.payload_json) || {}
                return (
                  <tr key={`broadcast-${row.id}`}>
                    <td>{row.server_time || '—'}</td>
                    <td>{row.draw_date || '—'}</td>
                    <td>{lineLabel(row.line_name)}</td>
                    <td>{row.pre_draw_issue || '—'}</td>
                    <td>{row.draw_issue || '—'}</td>
                    <td>{broadcastStatusLabel(row)}</td>
                    <td>{broadcastContentSummary(row)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        ) : null}
      </div>
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
            只展示 2026-04-20 起的模拟账本。已播报执行 {counts.broadcasted ?? 0} 条，未触发待执行 {counts.pending_future ?? 0} 条。
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
      <div className="history-table-shell">
        {rows.length === 0 ? <div className="empty">暂无记录</div> : null}
        {rows.length > 0 ? (
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
                  <td>{row.pre_draw_issue || '—'}</td>
                  <td>期位 {row.slot_1based}</td>
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
        ) : null}
      </div>
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

export default function App() {
  const {
    dashboard,
    curveRows,
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
  } = useDashboard()

  if (!dashboard) {
    return <div className="loading">正在拉取 PK10 实时积分面板…</div>
  }

  const currentActions = dashboard.current_actions || []
  const todayPlan = dashboard.today_plan || {}
  const totals = dashboard.totals || {}
  const market = dashboard.market || {}
  const contribution = dashboard.contributions || {}
  const ranges = dashboard.ranges || {}
  const simulationStartDate = ranges.simulation_start_date || CURVE_START_DATE
  const historyStartDate = ranges.history_start_date || '2026-01-01'

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
      <div className="ambient ambient-left" />
      <div className="ambient ambient-right" />
      <header className="hero">
        <div className="hero-copy">
          <p className="eyebrow">PK10 LIVE / SHARED BANKROLL</p>
          <h1>三线共享资金池实时面板</h1>
          <p className="hero-text">
            双面与冠亚和都走日级马丁 1-2-4-5，定位胆固定 10。窗口预热从 {historyStartDate} 开始，模拟投注从 {simulationStartDate} 开始；页面每次拿到最新开奖后，都会同步刷新当前积分、待执行动作和真实可投播报。
          </p>
        </div>
        <div className="hero-right">
          <div className="hero-badge">blackout 06:00-07:00</div>
          <div className="hero-market">
            <span>当前期开奖 {market.pre_draw_issue}</span>
            <span>下期开奖 {market.draw_issue}</span>
            <span>serverTime {market.server_time}</span>
            <span>窗口预热 {historyStartDate} 起</span>
            <span>模拟投注 {simulationStartDate} 起</span>
          </div>
        </div>
      </header>

      <section className="hero-metrics">
        <MiniStat label="已结算总积分" value={fmtNumber(totals.settled_bankroll)} accent="primary" />
        <MiniStat label="今日浮盈" value={fmtNumber(totals.today_provisional_pnl)} accent={Number(totals.today_provisional_pnl) >= 0 ? 'positive' : 'negative'} />
        <MiniStat label="若此刻收盘" value={fmtNumber(totals.estimated_close_bankroll)} accent="primary" />
        <MiniStat label="峰值回撤" value={fmtNumber(totals.max_drawdown)} accent="negative" />
        <MiniStat label="最低资金" value={fmtNumber(totals.min_bankroll)} />
        <MiniStat label="峰值资金" value={fmtNumber(totals.peak_bankroll)} />
      </section>

      <ContributionInline contribution={contribution} />

      <section className="layout">
        <div className="main-column">
          <section className="card card-actions">
            <div className="section-head">
              <div>
                <div className="section-eyebrow">CURRENT ACTIONS</div>
                <h2>投注播报</h2>
              </div>
              <div className="section-note">如果当前没有可执行窗口，这里会明确显示“无可投注选项”。</div>
            </div>
            <div className="action-grid">
              {currentActions.some((item) => item.slot_1based) ? (
                currentActions.filter((item) => item.slot_1based).map((item) => <ActionCard key={`${item.line_name}-${item.slot_1based}`} item={item} />)
              ) : (
                <div className="empty hero-empty">无可投注选项</div>
              )}
            </div>
          </section>

          <section className="card">
            <div className="section-head">
              <div>
                <div className="section-eyebrow">BANKROLL CURVE</div>
                <h2>日维资金曲线</h2>
              </div>
              <div className="section-note">从 {simulationStartDate} 起展示，含今日 provisional 标记。</div>
            </div>
            <EquityCurve rows={curveRows} startDate={simulationStartDate} />
          </section>

          <div className="three-grid">
            <LinePanel label="双面" state={todayPlan.face} />
            <LinePanel label="冠亚和" state={todayPlan.sum} />
            <LinePanel label="定位胆" state={todayPlan.exact} fixedStake />
          </div>

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
