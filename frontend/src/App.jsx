import { useEffect, useMemo, useRef, useState } from 'react'
import { askNewsQuestion, downloadCompanyReport, getDashboard } from './api/client.js'

const ALL_INDUSTRIES = 'Все отрасли'
const PLACEHOLDER_HINT = '{{company_name}}, {{industry}}, {{revenue}}, {{region}}, {{products}}, {{date}}, {{report_title}}'

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

function Sidebar({ activePage, setActivePage }) {
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
      <a className="brand" href="#main" aria-label="Альфа-Бизнес">
        <img className="brand-mark" src="/icons/alfa-logo.png" alt="" />
        <span>Альфа-Бизнес</span>
      </a>
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

function MobileNavigation() {
  const items = [
    { label: 'Главная', icon: 'home', active: true },
    { label: 'История', icon: 'history' },
    { label: 'Платежи', icon: 'payments' },
    { label: 'Сервисы', icon: 'services' },
    { label: 'Связь', icon: 'contact' },
  ]

  return (
    <nav className="mobile-navigation" aria-label="Нижняя навигация">
      {items.map((item) => (
        <button className={item.active ? 'active' : ''} key={item.label} type="button">
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
      setMessages((current) => [...current, { role: 'assistant', text: response.answer }])
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

function WatchlistCard({ company }) {
  return (
    <section className="side-card watchlist-card">
      <h3>Ваша повестка</h3>
      <p className="side-card-description">Лента настроена под отрасль и операции вашей компании.</p>
      <dl>
        <div><dt>Отрасль</dt><dd>{company?.industry || '—'}</dd></div>
        <div><dt>География</dt><dd>{company?.region || '—'}</dd></div>
        <div><dt>Операции</dt><dd>{company?.products?.length ? company.products.join(' · ') : '—'}</dd></div>
      </dl>
      <button type="button" className="text-action preferences-action" onClick={() => window.alert('Настройки интересов появятся здесь.')}>
        <img className="settings-action-icon" src="/icons/news-settings.png" alt="" />Настроить интересы
      </button>
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
  const [activePage, setActivePage] = useState('Сводка')
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

  const filteredNews = useMemo(() => {
    const items = dashboard?.news || []
    return items.filter((item) => {
      if (activeTab === 'Риски' && item.type !== 'risk') return false
      if (activeTab === 'Возможности' && item.type !== 'opportunity') return false
      if (!vedEnabled && item.tags?.includes('ВЭД')) return false
      if (industryFilter && industryFilter !== ALL_INDUSTRIES && !(item.industries || []).includes(industryFilter)) return false
      return true
    })
  }, [activeTab, dashboard, industryFilter, vedEnabled])

  function changeCompany(nextCompanyId) {
    setIndustryFilter('')
    setSelectedNews(null)
    setChatNews(null)
    setReportOpen(false)
    setReportError('')
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
      <Sidebar activePage={activePage} setActivePage={setActivePage} />
      <main className="main-content" id="main">
        <header className="top-header">
          <div>
            <div className="eyebrow">БИЗНЕС В КОНТЕКСТЕ</div>
            <h1>Новостная аналитика для бизнеса</h1>
          </div>
          <div className="header-actions">
            <button className="header-icon icon-button" type="button" aria-label="Уведомления"><Icon name="bell" /><i /></button>
            <button className="header-icon icon-button" type="button" aria-label="Сообщения"><Icon name="mail" /></button>
            <button className="profile-button" type="button"><span className="profile-avatar">ЮС</span><span>Юлия С.</span><Icon name="chevron" size={12} /></button>
          </div>
        </header>

        <div className="company-toolbar">
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
        </div>

        <PrioritySummary
          company={company}
          news={dashboard?.news || []}
          companiesCount={dashboard?.meta?.companiesWithInsights ?? null}
          updatedAt={dashboard?.meta?.generatedAt}
        />

        {loadError && <div className="load-error" role="alert">{loadError} <button type="button" onClick={() => setReloadKey((key) => key + 1)}>Обновить</button></div>}

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
                <button type="button" className="filter-pill filter-icon" aria-label="Другие фильтры"><img src="/icons/filter-settings.png" alt="" /></button>
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
              <div className="empty-state">В этой категории пока нет новостей.</div>
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
            <WatchlistCard company={company} />
          </aside>
        </div>
        <footer className="page-footer"><span>© 2026 АО «Альфа-Банк»</span><span>Конфиденциальность · О сервисе</span></footer>
      </main>
      <MobileNavigation />
      <NewsDetails item={selectedNews} onClose={() => setSelectedNews(null)} onAsk={openChat} />
      <ReportModal
        open={reportOpen}
        onClose={() => { setReportOpen(false); setReportError('') }}
        company={company}
        onDownload={handleReportDownload}
        downloading={reportDownloading}
        error={reportError}
      />
    </div>
  )
}

export default App
