import { useEffect, useMemo, useRef, useState } from 'react'
import { askNewsQuestion, downloadCompanyReport, getDashboard } from './api/client.js'

const ALL_INDUSTRIES = 'Все отрасли'
const PLACEHOLDER_HINT = '{{company_name}}, {{industry}}, {{revenue}}, {{region}}, {{products}}, {{date}}, {{report_title}}'

const HOME_PAGE = 'Главная'
const ANALYTICS_PAGE = 'Аналитика'

const CHART_SERIES = [
  { key: 'risks', label: 'Риски', color: '#ef3124' },
  { key: 'opportunities', label: 'Возможности', color: '#ea9f2f' },
  { key: 'events', label: 'События', color: '#9a9ca2' },
]
const CHART_WIDTH = 760
const CHART_HEIGHT = 300

const PREVIEW_INTERESTS = {
  industries: ['Оптовая торговля', 'Логистика и перевозки', 'Промышленное производство'],
  regions: ['Россия', 'Китай', 'СНГ'],
  products: ['РКО', 'Кредиты', 'Лизинг'],
  keywords: ['ВЭД', 'Ликвидность', 'Логистика'],
}

const NOTIFICATIONS = [
  { id: 'n1', type: 'risk', label: 'РИСК', title: 'Задержка оплаты импорта может создать кассовый разрыв', time: '12 минут назад' },
  { id: 'n2', type: 'opportunity', label: 'ВОЗМОЖНОСТЬ', title: 'Единый платёжный календарь высвободит оборотные средства', time: '1 час назад' },
  { id: 'n3', type: 'neutral', label: 'СОБЫТИЕ', title: 'Отчёт по компании готов к выгрузке', time: 'вчера, 18:20' },
]

function formatMoney(value) {
  const amount = Number(value)
  if (!Number.isFinite(amount) || amount <= 0) return '—'
  const format = (scaled, unit) => `${scaled.toLocaleString('ru-RU', { maximumFractionDigits: 1 })} ${unit}`
  if (amount >= 1e9) return format(amount / 1e9, 'млрд ₽')
  if (amount >= 1e6) return format(amount / 1e6, 'млн ₽')
  if (amount >= 1e3) return format(amount / 1e3, 'тыс ₽')
  return format(amount, '₽')
}

function formatCount(value) {
  if (value === null || value === undefined) return '—'
  const amount = Number(value)
  return Number.isFinite(amount) ? amount.toLocaleString('ru-RU') : '—'
}

function parseDate(value) {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

function formatDateTime(value) {
  const date = parseDate(value)
  if (!date) return '—'
  const day = date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })
  const time = date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  return `${day}, ${time}`
}

function formatCardDate(value, fallback = '') {
  const date = parseDate(value)
  if (!date) return fallback
  const day = date.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' })
  const time = date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  return `${day}, ${time}`
}

function formatFeedTimestamp(value) {
  const date = parseDate(value)
  if (!date) return 'Нет данных'
  const day = date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })
  const time = date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  return `${day} ${date.getFullYear()} · Обновлено в ${time}`
}

function companiesLabel(count) {
  const absolute = Math.abs(count) % 100
  const lastDigit = absolute % 10
  if (absolute > 10 && absolute < 20) return `${count} компаниях`
  if (lastDigit === 1) return `${count} компании`
  return `${count} компаниях`
}

function Icon({ name, size = 18 }) {
  const common = {
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.7,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    'aria-hidden': true,
  }

  const paths = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
    files: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6M8 13h8M8 17h8" /></>,
    wallet: <><rect x="3" y="5" width="18" height="15" rx="2" /><path d="M3 9h18M16 14h.01" /><path d="M6 5V3h12v2" /></>,
    users: <><path d="M16 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M10 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM20 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" /></>,
    chart: <><path d="M3 3v18h18" /><path d="m19 9-5 5-4-4-5 5" /></>,
    bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4" /></>,
    mail: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3 7 9 6 9-6" /></>,
    chevron: <path d="m7 10 5 5 5-5" />,
    arrow: <><path d="M5 12h14M13 6l6 6-6 6" /></>,
    arrowUpRight: <><path d="M7 17 17 7M8 7h9v9" /></>,
    sparkle: <><path d="m12 3 1.9 5.8L20 11l-6.1 2.2L12 19l-1.9-5.8L4 11l6.1-2.2L12 3Z" /><path d="m19 14 1.2 2.8L23 18l-2.8 1.2L19 22l-1.2-2.8L15 18l2.8-1.2L19 14Z" /></>,
    bookmark: <path d="M6 4h12v17l-6-4-6 4V4Z" />,
    check: <path d="m5 12 4 4L19 6" />,
    download: <><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><path d="m7 10 5 5 5-5M12 15V3" /></>,
    upload: <><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><path d="m17 8-5-5-5 5M12 3v12" /></>,
    chevronRight: <path d="m9 18 6-6-6-6" />,
    close: <><path d="m18 6-12 12M6 6l12 12" /></>,
    send: <><path d="m22 2-7 20-4-9-9-4Z" /><path d="M22 2 11 13" /></>,
    search: <><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></>,
    plus: <><path d="M12 5v14M5 12h14" /></>,
    home: <><path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1V10Z" /></>,
    history: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
    payments: <><rect x="4" y="3" width="16" height="18" rx="3" /><path d="M8 8h8M8 12h8M12 16h4" /></>,
    services: <><rect x="3" y="3" width="8" height="8" rx="2" /><rect x="13" y="3" width="8" height="8" rx="2" /><rect x="3" y="13" width="8" height="8" rx="2" /><rect x="13" y="13" width="8" height="8" rx="2" /></>,
    contact: <><path d="M21 11.5a8.5 8.5 0 0 1-12.6 7.4L3 20l1.2-4.6A8.5 8.5 0 1 1 21 11.5Z" /><path d="M8 11.5h8" /></>,
  }

  return <svg {...common}>{paths[name] || paths.sparkle}</svg>
}

function NotificationsPanel({ onMarkRead }) {
  return (
    <div className="notification-popover" role="dialog" aria-label="Уведомления">
      <div className="notification-head">
        <strong>Уведомления</strong>
        <span className="demo-badge">ЗАГЛУШКА</span>
      </div>
      <ul className="notification-list">
        {NOTIFICATIONS.map((item) => (
          <li key={item.id}>
            <span className={`news-badge ${item.type}`}><span className="badge-dot" />{item.label}</span>
            <p>{item.title}</p>
            <small>{item.time}</small>
          </li>
        ))}
      </ul>
      <div className="notification-foot">
        <span>Это пример. Персональные оповещения появятся позже.</span>
        <button type="button" onClick={onMarkRead}>Прочитать все</button>
      </div>
    </div>
  )
}

function ComingSoonPage({ title, onHome }) {
  return (
    <div className="coming-soon">
      <span className="coming-soon-icon"><Icon name="sparkle" size={24} /></span>
      <span className="coming-soon-kicker">РАЗДЕЛ «{title.toUpperCase()}»</span>
      <h2>Всё ещё впереди!</h2>
      <p>Этот раздел уже в разработке — мы покажем его в одном из ближайших обновлений сервиса.</p>
      <button className="primary-button" type="button" onClick={onHome}>
        Вернуться на главную <Icon name="arrow" size={15} />
      </button>
    </div>
  )
}

function emptyFilters() {
  return { regions: [], tags: [], sources: [], minRelevance: 0 }
}

function activeFilterCount(filters) {
  return filters.regions.length + filters.tags.length + filters.sources.length + (filters.minRelevance > 0 ? 1 : 0)
}

function FilterGroup({ title, values, selected, onToggle }) {
  if (!values.length) return null
  return (
    <div className="filter-group">
      <h4>{title}</h4>
      <div className="filter-options">
        {values.map((value) => {
          const isActive = selected.includes(value)
          return (
            <button
              key={value}
              type="button"
              className={`filter-option ${isActive ? 'selected' : ''}`}
              aria-pressed={isActive}
              onClick={() => onToggle(value)}
            >
              <span className="filter-check">{isActive && <Icon name="check" size={10} />}</span>
              <span>{value}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

function FilterPanel({ options, filters, onChange, onReset, onClose, resultCount, total }) {
  const hasOptions = Boolean(options.regions.length || options.tags.length || options.sources.length)

  function toggle(group, value) {
    onChange({
      ...filters,
      [group]: filters[group].includes(value)
        ? filters[group].filter((item) => item !== value)
        : [...filters[group], value],
    })
  }

  return (
    <div className="filter-panel" role="dialog" aria-label="Фильтры ленты">
      <div className="filter-panel-head">
        <strong>Фильтры</strong>
        <span>{resultCount} из {total}</span>
      </div>

      {hasOptions ? (
        <div className="filter-body">
          <FilterGroup title="Регионы" values={options.regions} selected={filters.regions} onToggle={(value) => toggle('regions', value)} />
          <FilterGroup title="Темы" values={options.tags} selected={filters.tags} onToggle={(value) => toggle('tags', value)} />
          <FilterGroup title="Источники" values={options.sources} selected={filters.sources} onToggle={(value) => toggle('sources', value)} />
          <label className="filter-range">
            <span>Релевантность от <b>{filters.minRelevance}%</b></span>
            <input
              type="range"
              min="0"
              max="90"
              step="10"
              value={filters.minRelevance}
              onChange={(event) => onChange({ ...filters, minRelevance: Number(event.target.value) })}
            />
          </label>
        </div>
      ) : (
        <div className="filter-empty">
          <span className="filter-empty-icon"><Icon name="sparkle" size={18} /></span>
          <p>Пока недостаточно данных для фильтров. Как только сервис соберёт события с регионами и темами, здесь появятся рабочие фильтры.</p>
          <div className="filter-example" aria-hidden="true">
            <span>Пример отображения</span>
            <div><em>Регионы</em><i>Москва</i><i>Санкт-Петербург</i></div>
            <div><em>Темы</em><i>ВЭД</i><i>Ликвидность</i></div>
          </div>
        </div>
      )}

      <div className="filter-panel-foot">
        <button type="button" className="filter-reset" onClick={onReset} disabled={!activeFilterCount(filters)}>Сбросить</button>
        <button type="button" className="filter-done" onClick={onClose}>Готово</button>
      </div>
    </div>
  )
}

function chartDelta(current, previous) {
  if (previous == null) return 'первый запуск'
  const diff = current - previous
  if (diff === 0) return 'без изменений'
  return `${diff > 0 ? '+' : '−'}${Math.abs(diff)} к прошлому запуску`
}

function formatAxisDate(date) {
  return date ? date.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' }) : ''
}

function monthTitle(points) {
  const date = parseDate(points[0]?.at)
  if (!date) return ''
  const label = date.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })
  return label.charAt(0).toUpperCase() + label.slice(1)
}

function smoothPath(coords) {
  if (!coords.length) return ''
  if (coords.length === 1) return `M ${coords[0].x} ${coords[0].y}`

  const xs = coords.map((point) => point.x)
  const ys = coords.map((point) => point.y)
  const dx = []
  const slope = []
  for (let index = 0; index < coords.length - 1; index += 1) {
    dx[index] = xs[index + 1] - xs[index] || 1
    slope[index] = (ys[index + 1] - ys[index]) / dx[index]
  }

  // Монотонная интерполяция: линия сглаживается, но не «ныряет» под ноль.
  const tangent = new Array(coords.length)
  tangent[0] = slope[0]
  tangent[coords.length - 1] = slope[slope.length - 1]
  for (let index = 1; index < coords.length - 1; index += 1) {
    if (slope[index - 1] * slope[index] <= 0) {
      tangent[index] = 0
    } else {
      const first = 2 * dx[index] + dx[index - 1]
      const second = dx[index] + 2 * dx[index - 1]
      tangent[index] = (first + second) / (first / slope[index - 1] + second / slope[index])
    }
  }

  let path = `M ${xs[0]} ${ys[0]}`
  for (let index = 0; index < coords.length - 1; index += 1) {
    const width = dx[index]
    const controlOneX = xs[index] + width / 3
    const controlOneY = ys[index] + (tangent[index] * width) / 3
    const controlTwoX = xs[index + 1] - width / 3
    const controlTwoY = ys[index + 1] - (tangent[index + 1] * width) / 3
    path += ` C ${controlOneX.toFixed(2)} ${controlOneY.toFixed(2)}, ${controlTwoX.toFixed(2)} ${controlTwoY.toFixed(2)}, ${xs[index + 1]} ${ys[index + 1]}`
  }
  return path
}

function buildMonthSeries(monthDays, generatedAt) {
  const days = Array.isArray(monthDays) ? monthDays : []
  if (!days.length) return []

  const dataByDate = new Map(days.map((day) => [day.date, day]))
  const first = parseDate(`${days[0].date}T12:00:00`)
  const last = parseDate(`${days[days.length - 1].date}T12:00:00`) || parseDate(generatedAt)
  if (!first || !last) return []

  const points = []
  const cursor = new Date(first.getFullYear(), first.getMonth(), first.getDate(), 12)
  while (cursor <= last) {
    const key = `${cursor.getFullYear()}-${String(cursor.getMonth() + 1).padStart(2, '0')}-${String(cursor.getDate()).padStart(2, '0')}`
    const entry = dataByDate.get(key)
    points.push({
      at: cursor.toISOString(),
      risks: entry ? entry.risks : null,
      opportunities: entry ? entry.opportunities : null,
      events: entry ? entry.events : null,
      hasData: Boolean(entry),
      monthLabel: formatAxisDate(cursor),
    })
    cursor.setDate(cursor.getDate() + 1)
  }

  return points
}

function TrendChart({ points, mode = 'runs' }) {
  const [hidden, setHidden] = useState({})
  const [activeIndex, setActiveIndex] = useState(null)

  const padding = { top: 20, right: 30, bottom: 38, left: 36 }
  const plotWidth = CHART_WIDTH - padding.left - padding.right
  const plotHeight = CHART_HEIGHT - padding.top - padding.bottom
  const visible = CHART_SERIES.filter((series) => !hidden[series.key])

  const rawMax = Math.max(
    1,
    ...points.flatMap((point) => visible.map((series) => {
      const value = point[series.key]
      return value == null ? 0 : Number(value) || 0
    })),
  )
  const tickStep = rawMax <= 6 ? 1 : Math.ceil(rawMax / 5)
  const axisMax = Math.max(tickStep, Math.ceil(rawMax / tickStep) * tickStep)
  const ticks = []
  for (let value = 0; value <= axisMax; value += tickStep) ticks.push(value)

  const stepX = points.length > 1 ? plotWidth / (points.length - 1) : 0
  const positionX = (index) => (points.length > 1 ? padding.left + index * stepX : padding.left + plotWidth / 2)
  const positionY = (value) => padding.top + plotHeight - (value / axisMax) * plotHeight
  const activePoint = activeIndex != null ? points[activeIndex] : null
  const hasActiveData = Boolean(activePoint) && activePoint.hasData !== false
  const tooltipLeft = activeIndex != null ? Math.min(86, Math.max(14, (positionX(activeIndex) / CHART_WIDTH) * 100)) : 50
  const labelStep = Math.max(1, Math.ceil(points.length / 7))

  function legendValue(series) {
    if (mode === 'month') {
      return points.reduce((sum, point) => sum + (point[series.key] ?? 0), 0)
    }
    return points[points.length - 1]?.[series.key] ?? 0
  }

  function axisLabel(index) {
    const point = points[index]
    if (mode === 'month') return point.monthLabel || formatAxisDate(parseDate(point.at))
    const date = parseDate(point.at)
    if (!date) return ''
    const previous = index > 0 ? parseDate(points[index - 1].at) : null
    if (!previous || previous.toDateString() !== date.toDateString()) return formatAxisDate(date)
    return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  }

  function seriesSegments(series) {
    const segments = []
    let current = []
    points.forEach((point, index) => {
      const value = point[series.key]
      if (point.hasData === false || value == null) {
        if (current.length) segments.push(current)
        current = []
        return
      }
      current.push({ x: positionX(index), y: positionY(Number(value) || 0) })
    })
    if (current.length) segments.push(current)
    return segments
  }

  return (
    <div className="trend-chart">
      <div className="trend-legend" role="group" aria-label="Серии графика">
        {CHART_SERIES.map((series) => (
          <button
            key={series.key}
            type="button"
            className={`trend-legend-item ${hidden[series.key] ? 'muted' : ''}`}
            aria-pressed={!hidden[series.key]}
            onClick={() => setHidden((current) => ({ ...current, [series.key]: !current[series.key] }))}
          >
            <span className="legend-dot" style={{ background: series.color }} />
            {series.label}
            <b>{legendValue(series)}</b>
          </button>
        ))}
      </div>

      <div className="trend-canvas">
        <svg
          viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
          role="img"
          aria-label={mode === 'month'
            ? `График за ${monthTitle(points)}: риски, возможности и события`
            : `График по ${points.length} запускам: риски, возможности и события`}
        >
          {ticks.map((value) => (
            <g key={value}>
              <line
                x1={padding.left}
                x2={CHART_WIDTH - padding.right}
                y1={positionY(value)}
                y2={positionY(value)}
                className="trend-grid"
              />
              <text x={padding.left - 9} y={positionY(value) + 3} textAnchor="end" className="trend-axis-label">{value}</text>
            </g>
          ))}

          {points.map((point, index) => (
            (index % labelStep === 0 || index === points.length - 1) && (
              <text key={`label-${index}`} x={positionX(index)} y={CHART_HEIGHT - 13} textAnchor="middle" className="trend-axis-label">
                {axisLabel(index)}
              </text>
            )
          ))}

          {activeIndex != null && (
            <line
              x1={positionX(activeIndex)}
              x2={positionX(activeIndex)}
              y1={padding.top}
              y2={padding.top + plotHeight}
              className="trend-guide"
            />
          )}

          {visible.map((series) => {
            const segments = seriesSegments(series)
            return (
              <g key={series.key}>
                {segments.map((segment, segmentIndex) => (
                  <path
                    key={`glow-${segmentIndex}`}
                    d={smoothPath(segment)}
                    fill="none"
                    stroke={series.color}
                    strokeWidth="9"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    opacity="0.09"
                  />
                ))}
                {segments.map((segment, segmentIndex) => (
                  <path
                    key={`line-${segmentIndex}`}
                    d={smoothPath(segment)}
                    fill="none"
                    stroke={series.color}
                    strokeWidth="3.2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                ))}
                {points.map((point, index) => {
                  if (point.hasData === false || point[series.key] == null) return null
                  return (
                    <circle
                      key={`dot-${index}`}
                      cx={positionX(index)}
                      cy={positionY(Number(point[series.key]) || 0)}
                      r={activeIndex === index ? 5.4 : 3.2}
                      fill="#fff"
                      stroke={series.color}
                      strokeWidth="2.2"
                    />
                  )
                })}
              </g>
            )
          })}

          {points.map((point, index) => (
            <rect
              key={`hit-${index}`}
              x={positionX(index) - (points.length > 1 ? stepX / 2 : plotWidth / 2)}
              y={padding.top}
              width={points.length > 1 ? stepX : plotWidth}
              height={plotHeight}
              fill="transparent"
              onMouseEnter={() => setActiveIndex(index)}
              onMouseLeave={() => setActiveIndex(null)}
              onClick={() => setActiveIndex(index)}
            />
          ))}
        </svg>

        {activePoint && (
          <div className="trend-tooltip" style={{ left: `${tooltipLeft}%` }}>
            <small>{formatDateTime(activePoint.at)}</small>
            {hasActiveData ? CHART_SERIES.filter((series) => !hidden[series.key]).map((series) => (
              <div key={series.key}>
                <span className="legend-dot" style={{ background: series.color }} />
                {series.label}
                <b>{activePoint[series.key] ?? 0}</b>
              </div>
            )) : <span className="trend-tooltip-empty">Нет данных за день</span>}
          </div>
        )}
      </div>
    </div>
  )
}

function ChatChart({ chart, focus }) {
  const points = chart?.series || []
  if (points.length < 2) return null

  const width = 300
  const height = 96
  const padding = { top: 10, right: 10, bottom: 8, left: 10 }
  const plotWidth = width - padding.left - padding.right
  const plotHeight = height - padding.top - padding.bottom
  const max = Math.max(1, ...points.flatMap((point) => CHART_SERIES.map((series) => Number(point[series.key]) || 0)))
  const stepX = plotWidth / (points.length - 1)
  const positionX = (index) => padding.left + index * stepX
  const positionY = (value) => padding.top + plotHeight - (value / max) * plotHeight
  const focusKey = focus === 'risk'
    ? 'risks'
    : focus === 'opportunity'
      ? 'opportunities'
      : focus === 'neutral'
        ? 'events'
        : null
  const last = points[points.length - 1]

  return (
    <figure className="chat-chart">
      <figcaption>
        <span>{chart.title || 'Динамика сигналов'}</span>
        <small>{formatAxisDate(parseDate(points[0].at))} — {formatAxisDate(parseDate(last.at))}</small>
      </figcaption>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Мини-график динамики рисков, возможностей и событий">
        {CHART_SERIES.map((series) => {
          const dimmed = Boolean(focusKey) && focusKey !== series.key
          const coords = points.map((point, index) => ({
            x: positionX(index),
            y: positionY(Number(point[series.key]) || 0),
          }))
          return (
            <path
              key={series.key}
              d={smoothPath(coords)}
              fill="none"
              stroke={series.color}
              strokeWidth={dimmed ? 1.8 : 2.8}
              strokeLinecap="round"
              strokeLinejoin="round"
              opacity={dimmed ? 0.3 : 1}
            />
          )
        })}
      </svg>
      <div className="chat-chart-legend">
        {CHART_SERIES.map((series) => (
          <span key={series.key} className={focusKey && focusKey !== series.key ? 'muted' : ''}>
            <i className="legend-dot" style={{ background: series.color }} />
            {series.label}
            <b>{last?.[series.key] ?? 0}</b>
          </span>
        ))}
      </div>
    </figure>
  )
}

function DistributionCard({ latest, caption }) {
  const total = latest ? latest.risks + latest.opportunities + latest.events : 0
  const rows = CHART_SERIES.map((series) => {
    const value = latest ? latest[series.key] || 0 : 0
    return { ...series, value, share: total ? Math.round((value / total) * 100) : 0 }
  })

  return (
    <section className="side-card distribution-card">
      <h3>Структура ленты</h3>
      <p className="side-card-description">{caption || 'Доля каждого типа сигналов в последнем запуске аналитики.'}</p>
      {total ? (
        <div className="distribution-list">
          {rows.map((row) => (
            <div className="distribution-row" key={row.key}>
              <div className="distribution-caption">
                <span><i className="legend-dot" style={{ background: row.color }} />{row.label}</span>
                <b>{row.share}%</b>
              </div>
              <div className="distribution-track"><span style={{ width: `${row.share}%`, background: row.color }} /></div>
            </div>
          ))}
        </div>
      ) : (
        <p className="distribution-empty">Пока нет данных для расчёта структуры.</p>
      )}
    </section>
  )
}

function AnalyticsPage({ company, dashboard, series, monthSeries, range, onRangeChange, loading, onOpenNews }) {
  const latest = series.length ? series[series.length - 1] : null
  const previous = series.length > 1 ? series[series.length - 2] : null
  const news = dashboard?.news || []
  const monthPoints = Array.isArray(monthSeries) ? monthSeries : []
  const isMonth = range === 'month'
  const monthTotals = monthPoints.reduce((totals, point) => {
    if (point.hasData === false) return totals
    totals.risks += point.risks || 0
    totals.opportunities += point.opportunities || 0
    totals.events += point.events || 0
    return totals
  }, { risks: 0, opportunities: 0, events: 0 })
  const monthDaysWithData = monthPoints.filter((point) => point.hasData !== false).length
  const monthLabel = monthTitle(monthPoints) || 'Текущий месяц'
  const metricPoint = isMonth ? (monthDaysWithData ? monthTotals : null) : latest
  const chartPoints = isMonth ? monthPoints : series
  const hasChartData = isMonth ? monthDaysWithData > 0 : series.length > 0

  return (
    <div className="analytics-page">
      <section className="analytics-hero">
        <div className="analytics-hero-copy">
          <span className="analytics-kicker">АНАЛИТИКА · {company?.name || 'КОМПАНИЯ'}</span>
          <h2>Риски, возможности и события</h2>
          <p>Каждая точка на графике — запуск аналитики или день месяца. Так видно, как меняется структура ленты.</p>
        </div>
        <div className="analytics-metrics">
          {CHART_SERIES.map((seriesItem) => (
            <div className={`analytics-metric ${seriesItem.key}`} key={seriesItem.key}>
              <span><i className="legend-dot" style={{ background: seriesItem.color }} />{seriesItem.label}</span>
              <strong>{metricPoint ? metricPoint[seriesItem.key] : '—'}</strong>
              <small>
                {isMonth
                  ? (metricPoint ? 'итого за месяц' : 'нет данных')
                  : metricPoint ? chartDelta(metricPoint[seriesItem.key], previous ? previous[seriesItem.key] : null) : 'нет данных'}
              </small>
            </div>
          ))}
        </div>
      </section>

      <div className="analytics-layout">
        <div className="analytics-main">
          <section className="analytics-chart-card">
            <div className="analytics-chart-head">
              <div>
                <h3>{isMonth ? 'Все сигналы за месяц' : 'Динамика по запускам'}</h3>
                <small>
                  {isMonth
                    ? `${monthLabel} · ${monthDaysWithData} дн. с данными`
                    : latest ? `Последнее обновление: ${formatDateTime(latest.at)}` : 'Данные появятся после первого запуска'}
                </small>
              </div>
              <div className="analytics-switch" role="group" aria-label="Период графика">
                <button type="button" className={isMonth ? '' : 'active'} aria-pressed={!isMonth} onClick={() => onRangeChange('runs')}>По запускам</button>
                <button type="button" className={isMonth ? 'active' : ''} aria-pressed={isMonth} onClick={() => onRangeChange('month')}>За месяц</button>
              </div>
            </div>
            {loading ? (
              <div className="loading-card">Загружаем аналитику компании…</div>
            ) : hasChartData ? (
              <TrendChart points={chartPoints} mode={range} />
            ) : (
              <div className="empty-state">{isMonth ? 'За этот месяц данных пока нет.' : 'Недостаточно данных для построения графика.'}</div>
            )}
          </section>

          {news.length > 0 && (
            <section className="side-card analytics-events">
              <div className="side-card-heading">
                <h3>Ключевые события</h3>
                <span className="analytics-events-count">{news.length}</span>
              </div>
              <p className="side-card-description">Последние карточки ленты, которые формируют динамику.</p>
              <ul>
                {news.slice(0, 4).map((item) => (
                  <li key={item.id}>
                    <span className={`news-badge ${item.type}`}><span className="badge-dot" />{item.typeLabel}</span>
                    <button type="button" onClick={() => onOpenNews(item)}>{item.title}</button>
                    <small>{formatCardDate(item.publishedAt, item.date)}</small>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>

        <aside className="analytics-side">
          <DistributionCard
            latest={metricPoint}
            caption={isMonth ? 'Доля каждого типа сигналов за месяц.' : 'Доля каждого типа сигналов в последнем запуске аналитики.'}
          />
          <FocusCard items={dashboard?.focusItems || []} updatedAt={dashboard?.meta?.generatedAt} />
        </aside>
      </div>
    </div>
  )
}

function splitKeywords(values = []) {
  const seen = new Set()
  const result = []
  values.forEach((value) => {
    String(value).split(',').forEach((part) => {
      const cleaned = part.trim()
      if (cleaned && !seen.has(cleaned.toLowerCase())) {
        seen.add(cleaned.toLowerCase())
        result.push(cleaned)
      }
    })
  })
  return result
}

function InterestsModal({ open, onClose, company, industryOptions, initial, onSave }) {
  const sources = useMemo(() => {
    const industries = [...new Set([company?.industry, ...(industryOptions || [])].filter((value) => value && value !== 'Не указана'))]
    const regions = company?.regions || []
    const products = company?.products || []
    const keywords = splitKeywords(company?.keywords || [])
    return {
      industries,
      regions,
      products,
      keywords,
      hasData: Boolean(industries.length || regions.length || products.length || keywords.length),
    }
  }, [company, industryOptions])

  const [selected, setSelected] = useState(PREVIEW_INTERESTS)

  useEffect(() => {
    if (!open) return
    if (!sources.hasData) {
      setSelected(PREVIEW_INTERESTS)
      return
    }
    setSelected({
      industries: initial?.industries?.length ? initial.industries : sources.industries.slice(0, 1),
      regions: initial?.regions?.length ? initial.regions : sources.regions,
      products: initial?.products?.length ? initial.products : sources.products,
      keywords: initial?.keywords?.length ? initial.keywords : sources.keywords.slice(0, 3),
    })
  }, [open, sources, initial])

  if (!open) return null

  const preview = !sources.hasData
  const display = preview ? PREVIEW_INTERESTS : sources
  const groups = [
    { key: 'industries', title: 'Отрасли', values: display.industries },
    { key: 'regions', title: 'География', values: display.regions },
    { key: 'products', title: 'Продукты банка', values: display.products },
    { key: 'keywords', title: 'Ключевые темы', values: display.keywords },
  ].filter((group) => group.values.length)

  function toggle(group, value) {
    if (preview) return
    setSelected((current) => ({
      ...current,
      [group]: current[group].includes(value)
        ? current[group].filter((item) => item !== value)
        : [...current[group], value],
    }))
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="details-modal interests-modal" role="dialog" aria-modal="true" aria-labelledby="interests-title">
        <button className="modal-close icon-button" type="button" onClick={onClose} aria-label="Закрыть"><Icon name="close" /></button>
        <p className="modal-eyebrow">НАСТРОЙКА ИНТЕРЕСОВ</p>
        <h2 id="interests-title">Настройте свою повестку</h2>
        <p className="report-company">{company?.name || 'Компания не выбрана'}</p>

        {preview && (
          <p className="interests-preview-note">
            <Icon name="sparkle" size={14} />
            <span>Это пример отображения. Данные о вашей компании ещё не загружены — настройка станет доступна, когда сервис получит профиль.</span>
          </p>
        )}

        {groups.map((group) => (
          <div className="interest-group" key={group.key}>
            <h3>{group.title}</h3>
            <div className="interest-chips">
              {group.values.map((value) => {
                const isSelected = preview
                  ? group.key === 'industries' || group.key === 'products'
                  : selected[group.key].includes(value)
                return (
                  <button
                    key={value}
                    type="button"
                    className={`interest-chip ${isSelected ? 'selected' : ''} ${preview ? 'example' : ''}`}
                    aria-pressed={preview ? undefined : isSelected}
                    disabled={preview}
                    onClick={() => toggle(group.key, value)}
                  >
                    {isSelected && <Icon name="check" size={12} />}{value}
                  </button>
                )
              })}
            </div>
          </div>
        ))}

        <div className="report-actions">
          {preview ? (
            <button type="button" className="primary-button" onClick={onClose}>Понятно</button>
          ) : (
            <>
              <button type="button" className="report-cancel" onClick={onClose}>Отмена</button>
              <button type="button" className="primary-button" onClick={() => onSave(selected)}>Сохранить интересы</button>
            </>
          )}
        </div>
      </section>
    </div>
  )
}

function Sidebar({ activePage, setActivePage, onHome }) {
  const items = [
    { id: 'Сводка', icon: 'image', image: '/icons/sidebar-summary.png' },
    { id: 'Заявки', icon: 'image', image: '/icons/sidebar-requests.png', badge: true },
    { id: 'Счета', icon: 'image', image: '/icons/sidebar-wallet.png' },
    { id: 'Контрагенты', icon: 'image', image: '/icons/sidebar-counterparties.png' },
    { id: 'Аналитика', icon: 'image', image: '/icons/sidebar-analytics.png' },
    { id: 'Настройки', icon: 'image', image: '/icons/sidebar-settings.png' },
  ]

  return (
    <aside className="sidebar">
      <button className="brand" type="button" onClick={onHome} aria-label="Альфа-Бизнес — на главную">
        <img className="brand-mark" src="/icons/alfa-logo.png" alt="" />
        <span>Альфа-Бизнес</span>
      </button>
      <nav className="side-nav" aria-label="Основная навигация">
        {items.map((item) => (
          <button
            className={`nav-item ${activePage === item.id ? 'active' : ''}`}
            key={item.id}
            onClick={() => setActivePage(item.id)}
            type="button"
          >
            {item.image ? <img className="nav-image-icon" src={item.image} alt="" /> : <Icon name={item.icon} size={19} />}
            <span>{item.id}</span>
            {item.badge && <img className="nav-badge" src="/icons/new-badge.png" alt="Новое" />}
          </button>
        ))}
      </nav>
      <button className="support-link" type="button" onClick={() => window.alert('Напишите вашему менеджеру Альфа-Бизнес.')}>
        <img className="nav-image-icon support-image-icon" src="/icons/sidebar-support.png" alt="" />
        <span>Поддержка 24/7</span>
      </button>
      <p className="sidebar-note">Ваш бизнес под защитой<br />Альфа-Банка</p>
      <div className="sidebar-bottom">© 2026 Альфа-Банк</div>
    </aside>
  )
}

function MobileNavigation({ activePage, onHome }) {
  const items = [
    { label: 'Главная', icon: 'home' },
    { label: 'История', icon: 'history' },
    { label: 'Платежи', icon: 'payments' },
    { label: 'Сервисы', icon: 'services' },
    { label: 'Связь', icon: 'contact' },
  ]

  return (
    <nav className="mobile-navigation" aria-label="Нижняя навигация">
      {items.map((item) => (
        <button
          className={item.label === 'Главная' && activePage === HOME_PAGE ? 'active' : ''}
          key={item.label}
          type="button"
          onClick={item.label === 'Главная' ? onHome : undefined}
        >
          <Icon name={item.icon} size={21} />
          <span>{item.label}</span>
        </button>
      ))}
    </nav>
  )
}

function StatCard({ label, value }) {
  return (
    <div className="stat-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function PrioritySummary({ company, news, companiesCount, updatedAt }) {
  const [workSummaryExpanded, setWorkSummaryExpanded] = useState(false)
  const payments = company?.payments || {}
  const risksCount = news.filter((item) => item.type === 'risk').length
  const opportunitiesCount = news.filter((item) => item.type === 'opportunity').length
  const counterpartiesCount = payments.hasData
    ? (payments.incomingCounterparties || 0) + (payments.outgoingCounterparties || 0)
    : null

  const cards = [
    { label: 'Выручка компании', value: formatMoney(company?.revenueRub) },
    { label: 'Поступления', value: formatMoney(payments.incomingRub) },
    { label: 'Списания', value: formatMoney(payments.outgoingRub) },
    { label: 'Контрагенты', value: formatCount(counterpartiesCount) },
  ]

  return (
    <section className="priority-summary">
      <div className="summary-stat-area">
        <div className="summary-heading">
          {companiesCount == null ? 'Аналитика компаний' : `В ${companiesLabel(companiesCount)}`}
          <Icon name="chevronRight" size={14} />
        </div>
        <div className="summary-stats">
          {cards.map((card) => <StatCard key={card.label} label={card.label} value={card.value} />)}
        </div>
      </div>
      <div className={`work-summary ${workSummaryExpanded ? 'expanded' : ''}`}>
        <button
          className="summary-heading work-summary-toggle"
          type="button"
          aria-expanded={workSummaryExpanded}
          onClick={() => setWorkSummaryExpanded((expanded) => !expanded)}
        >
          Дела в работе
          <Icon name="chevron" size={14} />
        </button>
        <ul>
          <li><span>{risksCount}</span>Рисков в ленте <Icon name="chevron" size={13} /></li>
          <li><span>{opportunitiesCount}</span>Возможностей <Icon name="chevron" size={13} /></li>
          <li><span>{news.length}</span>Событий в аналитике <Icon name="chevron" size={13} /></li>
        </ul>
        <small>Данные на {formatDateTime(updatedAt)}</small>
      </div>
      <div className="promo-card">
        <img className="promo-art" src="/promo-analytics.png" alt="" />
        <div className="promo-copy">
          <span className="promo-eyebrow">АЛЬФА ДЛЯ БИЗНЕСА</span>
          <strong>Умная аналитика<br />для всех</strong>
          <span>От новостей рынка — к решениям<br />для вашего бизнеса.</span>
          <button type="button" onClick={() => document.getElementById('feed')?.scrollIntoView({ behavior: 'smooth' })}>Подробнее <Icon name="arrowUpRight" size={16} /></button>
        </div>
      </div>
    </section>
  )
}

function NewsCard({ item, onAsk, onOpen, companyName }) {
  return (
    <article className="news-card">
      <div className="news-card-top">
        <span className={`news-badge ${item.type}`}>
          <span className="badge-dot" />{item.typeLabel}
        </span>
        <span className="news-date">{formatCardDate(item.publishedAt, item.date)}</span>
        <button className="icon-button bookmark-button" type="button" aria-label="Сохранить новость" onClick={(event) => event.currentTarget.classList.toggle('saved')}>
          <Icon name="bookmark" size={16} />
        </button>
      </div>
      <button className="news-title-button" type="button" onClick={() => onOpen(item)}>
        <h3>{item.title}</h3>
      </button>
      <p className="news-summary"><img className="news-ai-icon" src="/icons/news-sparkle.png" alt="" />{item.summary}</p>
      <div className="tag-list">
        {item.tags.map((tag) => <span key={tag}>#{tag}</span>)}
      </div>
      <div className="bank-opinion">
        <div className="bank-opinion-title"><img className="mini-brand-mark" src="/icons/alfa-logo.png" alt="" /> Мнение Альфа-Банка</div>
        <p>«{item.bankOpinion}»</p>
        <div className="bank-opinion-meta">
          <span>{item.bankTeam}</span>
          <button type="button" onClick={() => onOpen(item)}><img className="pdf-mark" src="/icons/news-pdf.png" alt="" />{item.bankSource}</button>
        </div>
      </div>
      <div className="news-card-footer">
        <button type="button" className="text-action" onClick={() => onAsk(item)}>
          {item.cta || item.recommendation} <Icon name="arrow" size={14} />
        </button>
        <span>{companyName ? `Для ${companyName}` : 'Для вашей компании'}</span>
      </div>
    </article>
  )
}

function ChatPanel({ item, expanded, setExpanded }) {
  const [messages, setMessages] = useState([])
  const [question, setQuestion] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const listRef = useRef(null)

  useEffect(() => {
    if (expanded && listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [messages, expanded])

  async function handleSubmit(event) {
    event.preventDefault()
    const text = question.trim()
    if (!text || sending || !item?.id) return

    setQuestion('')
    setError('')
    setExpanded(true)
    setMessages((current) => [...current, { role: 'user', text }])
    setSending(true)

    try {
      const response = await askNewsQuestion(item.id, text)
      setMessages((current) => [...current, { role: 'assistant', text: response.answer, chart: response.chart }])
    } catch (requestError) {
      setError(requestError.message || 'Не удалось получить ответ. Попробуйте ещё раз.')
    } finally {
      setSending(false)
    }
  }

  return (
    <section className={`chat-panel ${expanded ? 'expanded' : ''}`}>
      <button className="chat-heading" type="button" onClick={() => setExpanded(!expanded)} aria-expanded={expanded}>
        {expanded && <span className="chat-icon"><img src="/icons/chat-robot.png" alt="" /></span>}
        <span className="chat-heading-copy">
          <strong>AI-чат по новости</strong>
          {expanded && <small>Быстрый разбор по карточке</small>}
        </span>
        <span className={`chat-chevron ${expanded ? 'rotated' : ''}`}><Icon name="chevron" size={18} /></span>
      </button>
      {expanded ? (
        <>
          <div className="chat-messages" ref={listRef} aria-live="polite">
            {!messages.length && !sending && (
              <p className="chat-empty">
                {item
                  ? 'Задайте вопрос по выбранному документу — подготовлю сводку, риски и действия.'
                  : 'Выберите новость в ленте, чтобы задать вопрос.'}
              </p>
            )}
            {messages.map((message, index) => (
              <div className={`chat-message-row ${message.role}`} key={`${index}-${message.text}`}>
                <div className="chat-bubble">{message.text}</div>
                {message.role === 'assistant' && message.chart?.series?.length > 1 && (
                  <ChatChart chart={message.chart} focus={item?.type} />
                )}
                <span>{message.role === 'user' ? 'Юлия С.' : 'AI-Чат'}</span>
              </div>
            ))}
            {sending && <div className="chat-typing"><span /><span /><span /> AI-Чат готовит ответ</div>}
          </div>
          {error && <p className="chat-error" role="alert">{error}</p>}
          <form className="chat-form expanded-form" onSubmit={handleSubmit}>
            <textarea
              aria-label="Вопрос по новости"
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  event.currentTarget.form.requestSubmit()
                }
              }}
              placeholder={item ? 'Напишите вопрос по карточке' : 'Сначала выберите новость в ленте'}
              rows={2}
              disabled={!item}
              value={question}
            />
            <button className="send-button" type="submit" disabled={!item || !question.trim() || sending}>
              {sending ? 'Отправка…' : 'Отправить'}
            </button>
          </form>
        </>
      ) : (
        <form className="chat-form compact-form" onSubmit={handleSubmit}>
          <input
            aria-label="Задать вопрос по новости"
            onChange={(event) => setQuestion(event.target.value)}
            onFocus={() => item && setExpanded(true)}
            placeholder={item ? 'Просто напишите, что вас интересует' : 'Сначала выберите новость в ленте'}
            disabled={!item}
            value={question}
          />
          <button className="compact-send" type="submit" aria-label="Отправить вопрос" disabled={!item || !question.trim() || sending}>
            <Icon name="search" size={19} />
          </button>
        </form>
      )}
    </section>
  )
}

function FocusCard({ items, updatedAt }) {
  return (
    <section className="side-card focus-card">
      <div className="side-card-heading"><h3>В фокусе сегодня</h3><img className="focus-target-icon" src="/icons/focus-target.png" alt="" /></div>
      <p className="side-card-description">События с наибольшим влиянием на ваши компании</p>
      <div className="focus-list">
        {items.map((item) => (
          <div className="focus-row" key={item.label}>
            <span>{item.label}</span>
            <strong className={item.color}>{item.value}</strong>
          </div>
        ))}
      </div>
      <div className="updated-note"><span />Обновлено {formatDateTime(updatedAt)}</div>
    </section>
  )
}

function WatchlistCard({ company, onOpenInterests, interestsCount = 0 }) {
  return (
    <section className="side-card watchlist-card">
      <h3>Ваша повестка</h3>
      <p className="side-card-description">Лента настроена под отрасль и операции вашей компании.</p>
      <dl>
        <div><dt>Отрасль</dt><dd>{company?.industry || '—'}</dd></div>
        <div><dt>География</dt><dd>{company?.region || '—'}</dd></div>
        <div><dt>Операции</dt><dd>{company?.products?.length ? company.products.join(' · ') : '—'}</dd></div>
      </dl>
      <button type="button" className="text-action preferences-action" onClick={onOpenInterests}>
        <img className="settings-action-icon" src="/icons/news-settings.png" alt="" />Настроить интересы
      </button>
      {interestsCount > 0 && <p className="interests-saved">Сохранено направлений: {interestsCount}</p>}
    </section>
  )
}

function NewsDetails({ item, onClose, onAsk }) {
  if (!item) return null

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="details-modal" role="dialog" aria-modal="true" aria-labelledby="details-title">
        <button className="modal-close icon-button" type="button" onClick={onClose} aria-label="Закрыть"><Icon name="close" /></button>
        <span className={`news-badge ${item.type}`}><span className="badge-dot" />{item.typeLabel}</span>
        <p className="modal-eyebrow">Подробный разбор · {formatCardDate(item.publishedAt, item.date)}</p>
        <h2 id="details-title">{item.title}</h2>
        <div className="detail-section"><h3>Что произошло</h3><p>{item.facts || 'Нет данных.'}</p></div>
        <div className="detail-section"><h3>Почему это важно для компании</h3><p>{item.impact || 'Нет данных.'}</p></div>
        <div className="detail-section recommendation-box">
          <h3>Что можно сделать</h3>
          {item.actions?.length ? (
            <ul className="action-list">
              {item.actions.map((action) => <li key={action}>{action}</li>)}
            </ul>
          ) : (
            <p>{item.action || 'Нет рекомендаций.'}</p>
          )}
        </div>
        <div className="detail-section bank-detail"><h3><img className="mini-brand-mark" src="/icons/alfa-logo.png" alt="" /> Мнение Альфа-Банка</h3><p>{item.bankOpinion || 'Нет данных.'}</p><span className="source-link"><img className="pdf-mark" src="/icons/news-pdf.png" alt="" />{item.bankSource}</span></div>
        <div className="traceability">
          {item.relevance != null && <span><Icon name="sparkle" size={15} />Релевантность: {item.relevance}%</span>}
          {item.confidence != null && <span>Уверенность: {item.confidence}%</span>}
          <span>Источник: {item.source}</span>
        </div>
        <button className="primary-button modal-chat-button" type="button" onClick={() => { onAsk(item); onClose() }}>
          Спросить AI по новости <Icon name="arrow" size={15} />
        </button>
      </section>
    </div>
  )
}

function ReportModal({ open, onClose, company, onDownload, downloading, error }) {
  const [title, setTitle] = useState('')
  const [file, setFile] = useState(null)

  useEffect(() => {
    if (!open) return
    setTitle(company?.name ? `Отчёт по компании «${company.name}»` : 'Отчёт по компании')
    setFile(null)
  }, [open, company?.name])

  if (!open) return null

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="details-modal report-modal" role="dialog" aria-modal="true" aria-labelledby="report-title">
        <button className="modal-close icon-button" type="button" onClick={onClose} aria-label="Закрыть"><Icon name="close" /></button>
        <p className="modal-eyebrow">ВЫГРУЗКА ОТЧЁТА</p>
        <h2 id="report-title">Скачать отчёт по компании</h2>
        <p className="report-company">{company?.name || 'Компания не выбрана'}</p>

        <label className="report-field">
          <span>Название документа</span>
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Например, Отчёт по компании за октябрь"
          />
        </label>

        <label className={`report-dropzone ${file ? 'filled' : ''}`}>
          <input
            type="file"
            accept=".doc,.docx,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            onChange={(event) => setFile(event.target.files?.[0] || null)}
          />
          <Icon name="upload" size={22} />
          <span>{file ? file.name : 'Загрузите шаблон DOC или DOCX (титульный лист)'}</span>
          <small>
            DOC автоматически конвертируется в DOCX. Поддерживаются плейсхолдеры: {PLACEHOLDER_HINT}
          </small>
        </label>

        {error && <p className="report-error" role="alert">{error}</p>}

        <div className="report-actions">
          <button type="button" className="report-cancel" onClick={onClose}>Отмена</button>
          <button
            type="button"
            className="primary-button"
            disabled={!file || downloading}
            onClick={() => onDownload({ file, title: title.trim() || 'Отчёт по компании' })}
          >
            {downloading ? 'Формируем…' : 'Скачать отчёт'}
          </button>
        </div>
      </section>
    </div>
  )
}

function App() {
  const [companyId, setCompanyId] = useState('')
  const [activePage, setActivePage] = useState(HOME_PAGE)
  const [activeTab, setActiveTab] = useState('Сводка')
  const [industryFilter, setIndustryFilter] = useState('')
  const [industryDropdownOpen, setIndustryDropdownOpen] = useState(false)
  const [vedEnabled, setVedEnabled] = useState(true)
  const [selectedNews, setSelectedNews] = useState(null)
  const [chatNews, setChatNews] = useState(null)
  const [chatExpanded, setChatExpanded] = useState(false)
  const [dashboard, setDashboard] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)
  const [reportOpen, setReportOpen] = useState(false)
  const [reportDownloading, setReportDownloading] = useState(false)
  const [reportError, setReportError] = useState('')
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const [notificationsRead, setNotificationsRead] = useState(false)
  const [interestsOpen, setInterestsOpen] = useState(false)
  const [interests, setInterests] = useState(null)
  const [filters, setFilters] = useState(emptyFilters)
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [analyticsRange, setAnalyticsRange] = useState('runs')
  const headerActionsRef = useRef(null)
  const filtersRef = useRef(null)

  useEffect(() => {
    let isCurrent = true
    setLoading(true)
    setLoadError('')

    getDashboard(companyId)
      .then((data) => {
        if (isCurrent) setDashboard(data)
      })
      .catch((error) => {
        if (isCurrent) setLoadError(error.message || 'Не удалось загрузить данные.')
      })
      .finally(() => {
        if (isCurrent) setLoading(false)
      })

    return () => { isCurrent = false }
  }, [companyId, reloadKey])

  const company = dashboard?.company
  const industryOptions = useMemo(() => {
    const values = new Set()
    ;(dashboard?.news || []).forEach((item) => {
      (item.industries || []).forEach((industry) => values.add(industry))
    })
    return [...values].sort((left, right) => left.localeCompare(right, 'ru'))
  }, [dashboard])

  const isHome = activePage === HOME_PAGE
  const isAnalytics = activePage === ANALYTICS_PAGE
  const pageEyebrow = isHome ? 'БИЗНЕС В КОНТЕКСТЕ' : isAnalytics ? 'ДИНАМИКА И ТРЕНДЫ' : 'РАЗДЕЛ В РАЗРАБОТКЕ'
  const pageTitle = isHome ? 'Новостная аналитика для бизнеса' : isAnalytics ? 'Аналитика' : activePage
  const interestsCount = interests
    ? interests.industries.length + interests.regions.length + interests.products.length + interests.keywords.length
    : 0
  const activeFilters = activeFilterCount(filters)

  const filteredNews = useMemo(() => {
    const items = dashboard?.news || []
    return items.filter((item) => {
      if (activeTab === 'Риски' && item.type !== 'risk') return false
      if (activeTab === 'Возможности' && item.type !== 'opportunity') return false
      if (!vedEnabled && item.tags?.includes('ВЭД')) return false
      if (industryFilter && industryFilter !== ALL_INDUSTRIES && !(item.industries || []).includes(industryFilter)) return false
      if (filters.regions.length && !(item.regions || []).some((region) => filters.regions.includes(region))) return false
      if (filters.tags.length && !(item.tags || []).some((tag) => filters.tags.includes(tag))) return false
      if (filters.sources.length && !filters.sources.includes(item.source)) return false
      if (filters.minRelevance > 0 && (Number(item.relevance) || 0) < filters.minRelevance) return false
      return true
    })
  }, [activeTab, dashboard, industryFilter, filters, vedEnabled])

  const filterOptions = useMemo(() => {
    const regions = new Set()
    const tags = new Set()
    const sources = new Set()
    ;(dashboard?.news || []).forEach((item) => {
      (item.regions || []).forEach((region) => regions.add(region))
      ;(item.tags || []).forEach((tag) => tags.add(tag))
      if (item.source) sources.add(item.source)
    })
    const sorted = (values) => [...values].sort((left, right) => left.localeCompare(right, 'ru'))
    return { regions: sorted(regions), tags: sorted(tags), sources: sorted(sources) }
  }, [dashboard])

  const analyticsSeries = useMemo(() => {
    const fromApi = dashboard?.analytics?.series
    if (Array.isArray(fromApi) && fromApi.length) return fromApi

    // Фоллбэк для старого ответа API: собираем один срез по датам публикации.
    const items = dashboard?.news || []
    if (!items.length) return []
    const buckets = new Map()
    items.forEach((item) => {
      const date = parseDate(item.publishedAt)
      const key = date ? date.toISOString().slice(0, 10) : 'unknown'
      const bucket = buckets.get(key) || { at: item.publishedAt, risks: 0, opportunities: 0, events: 0 }
      if (item.type === 'risk') bucket.risks += 1
      else if (item.type === 'opportunity') bucket.opportunities += 1
      else bucket.events += 1
      buckets.set(key, bucket)
    })
    return [...buckets.values()].sort((left, right) => new Date(left.at) - new Date(right.at))
  }, [dashboard])

  const analyticsMonth = useMemo(
    () => buildMonthSeries(dashboard?.analytics?.month, dashboard?.meta?.generatedAt),
    [dashboard],
  )

  useEffect(() => {
    if (!notificationsOpen) return undefined
    const handlePointer = (event) => {
      if (!headerActionsRef.current?.contains(event.target)) setNotificationsOpen(false)
    }
    const handleKey = (event) => {
      if (event.key === 'Escape') setNotificationsOpen(false)
    }
    document.addEventListener('mousedown', handlePointer)
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('mousedown', handlePointer)
      document.removeEventListener('keydown', handleKey)
    }
  }, [notificationsOpen])

  useEffect(() => {
    if (!filtersOpen) return undefined
    const handlePointer = (event) => {
      if (!filtersRef.current?.contains(event.target)) setFiltersOpen(false)
    }
    const handleKey = (event) => {
      if (event.key === 'Escape') setFiltersOpen(false)
    }
    document.addEventListener('mousedown', handlePointer)
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('mousedown', handlePointer)
      document.removeEventListener('keydown', handleKey)
    }
  }, [filtersOpen])

  function navigate(page) {
    setActivePage(page)
    setNotificationsOpen(false)
    document.getElementById('main')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  function goHome() {
    navigate(HOME_PAGE)
  }

  function changeCompany(nextCompanyId) {
    setIndustryFilter('')
    setSelectedNews(null)
    setChatNews(null)
    setReportOpen(false)
    setReportError('')
    setInterests(null)
    setFilters(emptyFilters())
    setFiltersOpen(false)
    setCompanyId(nextCompanyId)
  }

  function openChat(item) {
    setChatNews(item)
    setChatExpanded(true)
    document.getElementById('ai-chat')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  async function handleReportDownload({ file, title }) {
    if (!file || !company?.id) return

    setReportDownloading(true)
    setReportError('')
    try {
      const blob = await downloadCompanyReport(company.id, { file, title })
      const url = URL.createObjectURL(blob)
      const filename = `${title || 'Отчёт по компании'}`.replace(/[\\/:*?"<>|]/g, '_')
      const link = document.createElement('a')
      link.href = url
      link.download = `${filename}.docx`
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
      setReportOpen(false)
    } catch (error) {
      setReportError(error.message || 'Не удалось сформировать отчёт.')
    } finally {
      setReportDownloading(false)
    }
  }

  return (
    <div className="app-shell">
      <Sidebar activePage={activePage} setActivePage={navigate} onHome={goHome} />
      <main className="main-content" id="main">
        <header className="top-header">
          <div>
            <div className="eyebrow">{pageEyebrow}</div>
            <h1>{pageTitle}</h1>
          </div>
          <div className="header-actions" ref={headerActionsRef}>
            <button
              className="header-icon icon-button"
              type="button"
              aria-label="Уведомления"
              aria-expanded={notificationsOpen}
              onClick={() => setNotificationsOpen((open) => !open)}
            >
              <Icon name="bell" />{!notificationsRead && <i />}
            </button>
            <button className="header-icon icon-button" type="button" aria-label="Сообщения"><Icon name="mail" /></button>
            <button className="profile-button" type="button"><span className="profile-avatar">ЮС</span><span>Юлия С.</span><Icon name="chevron" size={12} /></button>
            {notificationsOpen && (
              <NotificationsPanel
                onMarkRead={() => {
                  setNotificationsRead(true)
                  setNotificationsOpen(false)
                }}
              />
            )}
          </div>
        </header>

        {(isHome || isAnalytics) && <div className="company-toolbar">
          <label className="company-picker">
            <span className="company-icon"><img src="/icons/company-building.png" alt="" /></span>
            <span><small>Моя компания</small>
              <select value={companyId || company?.id || ''} onChange={(event) => changeCompany(event.target.value)} aria-label="Выбрать компанию">
                {(dashboard?.companies || []).map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}{item.revenueRub > 0 ? ` · ${formatMoney(item.revenueRub)}` : ''}
                  </option>
                ))}
              </select>
            </span>
          </label>
          <div className="toolbar-actions">
            <button type="button" className="toolbar-button" onClick={() => { setReportError(''); setReportOpen(true) }}><Icon name="download" size={15} /><span>Скачать выписку</span></button>
            <button type="button" className="toolbar-button" onClick={() => window.alert('Выберите файл CSV для импорта платежей.')}><Icon name="upload" size={15} /><span>Импорт платежей</span></button>
            <button type="button" className="toolbar-button" onClick={() => window.alert('Создание платежа скоро будет доступно.')}><Icon name="plus" size={14} /><span>Создать платёж</span></button>
          </div>
        </div>}

        {loadError && <div className="load-error" role="alert">{loadError} <button type="button" onClick={() => setReloadKey((key) => key + 1)}>Обновить</button></div>}

        {isHome && (
          <>
            <PrioritySummary
              company={company}
              news={dashboard?.news || []}
              companiesCount={dashboard?.meta?.companiesWithInsights ?? null}
              updatedAt={dashboard?.meta?.generatedAt}
            />

            <div className="content-grid">
          <section className="feed-column" id="feed">
            <div className="tab-filter-row">
              <div className="tabs" role="tablist" aria-label="Фильтр новостей">
                {['Сводка', 'Риски', 'Возможности'].map((tab) => (
                  <button className={activeTab === tab ? 'selected' : ''} key={tab} onClick={() => setActiveTab(tab)} role="tab" aria-selected={activeTab === tab} type="button">{tab}</button>
                ))}
              </div>
              <div className="filter-pills">
                <div className="industry-control">
                  <button
                    type="button"
                    className={`filter-pill industry-pill ${industryDropdownOpen ? 'open' : ''}`}
                    aria-expanded={industryDropdownOpen}
                    onClick={() => setIndustryDropdownOpen((open) => !open)}
                  >
                    <Icon name="chevron" size={14} />
                    <span>Отрасль: {industryFilter || ALL_INDUSTRIES}</span>
                  </button>
                  {industryDropdownOpen && (
                    <div className="industry-menu" role="listbox" aria-label="Выберите отрасль">
                      {[ALL_INDUSTRIES, ...industryOptions].map((industry) => (
                        <button
                          type="button"
                          className={`industry-option ${(industryFilter || ALL_INDUSTRIES) === industry ? 'selected' : ''}`}
                          key={industry}
                          role="option"
                          aria-selected={(industryFilter || ALL_INDUSTRIES) === industry}
                          onClick={() => {
                            setIndustryFilter(industry)
                            setIndustryDropdownOpen(false)
                          }}
                        >
                          <span>{industry}</span>
                          {(industryFilter || ALL_INDUSTRIES) === industry && <Icon name="check" size={15} />}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <button
                  type="button"
                  className={`filter-pill ved-pill ${vedEnabled ? 'active' : ''}`}
                  aria-pressed={vedEnabled}
                  onClick={() => setVedEnabled((enabled) => !enabled)}
                >
                  {vedEnabled && <Icon name="check" size={17} />}<span>ВЭД</span>
                </button>
                <div className="filters-control" ref={filtersRef}>
                  <button
                    type="button"
                    className={`filter-pill filter-icon ${activeFilters ? 'has-active' : ''}`}
                    aria-label="Дополнительные фильтры"
                    aria-expanded={filtersOpen}
                    onClick={() => setFiltersOpen((open) => !open)}
                  >
                    <img src="/icons/filter-settings.png" alt="" />
                    {activeFilters > 0 && <span className="filter-count">{activeFilters}</span>}
                  </button>
                  {filtersOpen && (
                    <FilterPanel
                      options={filterOptions}
                      filters={filters}
                      onChange={setFilters}
                      onReset={() => setFilters(emptyFilters())}
                      onClose={() => setFiltersOpen(false)}
                      resultCount={filteredNews.length}
                      total={(dashboard?.news || []).length}
                    />
                  )}
                </div>
              </div>
            </div>
            <div className="feed-heading">
              <div><h2>Умная лента</h2><span className="demo-badge">ДЕМО</span></div>
              <small>{formatFeedTimestamp(dashboard?.meta?.generatedAt)}</small>
            </div>
            {loading ? (
              <div className="loading-card">Загружаем новости компании…</div>
            ) : filteredNews.length ? (
              <div className="news-list">
                {filteredNews.map((item) => (
                  <NewsCard key={item.id} item={item} onAsk={openChat} onOpen={setSelectedNews} companyName={company?.name} />
                ))}
              </div>
            ) : (
              <div className="empty-state">
                {activeFilters || industryFilter || activeTab !== 'Сводка'
                  ? 'Нет событий по выбранным фильтрам.'
                  : 'В этой категории пока нет новостей.'}
              </div>
            )}
            <div className="read-all"><img src="/icons/read-check.png" alt="" />Вы прочитали все важные события</div>
          </section>

          <aside className="right-column">
            <div id="ai-chat">
              <ChatPanel
                key={chatNews?.id || filteredNews[0]?.id || 'empty'}
                item={chatNews || filteredNews[0] || null}
                expanded={chatExpanded}
                setExpanded={setChatExpanded}
              />
            </div>
            <FocusCard items={dashboard?.focusItems || []} updatedAt={dashboard?.meta?.generatedAt} />
            <WatchlistCard
              company={company}
              interestsCount={interestsCount}
              onOpenInterests={() => setInterestsOpen(true)}
            />
          </aside>
        </div>
          </>
        )}

        {isAnalytics && (
          <AnalyticsPage
            company={company}
            dashboard={dashboard}
            series={analyticsSeries}
            monthSeries={analyticsMonth}
            range={analyticsRange}
            onRangeChange={setAnalyticsRange}
            loading={loading}
            onOpenNews={setSelectedNews}
          />
        )}

        {!isHome && !isAnalytics && <ComingSoonPage title={activePage} onHome={goHome} />}

        <footer className="page-footer"><span>© 2026 АО «Альфа-Банк»</span><span>Конфиденциальность · О сервисе</span></footer>
      </main>
      <MobileNavigation activePage={activePage} onHome={goHome} />
      <NewsDetails item={selectedNews} onClose={() => setSelectedNews(null)} onAsk={openChat} />
      <ReportModal
        open={reportOpen}
        onClose={() => { setReportOpen(false); setReportError('') }}
        company={company}
        onDownload={handleReportDownload}
        downloading={reportDownloading}
        error={reportError}
      />
      <InterestsModal
        open={interestsOpen}
        onClose={() => setInterestsOpen(false)}
        company={company}
        industryOptions={industryOptions}
        initial={interests}
        onSave={(next) => {
          setInterests(next)
          setInterestsOpen(false)
        }}
      />
    </div>
  )
}

export default App
