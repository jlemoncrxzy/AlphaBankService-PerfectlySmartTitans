// 1. Импорт моков УДАЛЕН. Теперь мы работаем только с реальным API.

// Адрес бэкенда. Если переменной нет, используем текущий хост (пустая строка)
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

export const API_ENDPOINTS = {
  dashboard: '/api/dashboard',
  counterparties: '/api/counterparties',
  newsChat: (newsId) => `/api/news/${newsId}/chat`,
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })

  if (!response.ok) {
    let message = `Ошибка API: ${response.status} ${response.statusText}`
    try {
      const payload = await response.json()
      if (typeof payload?.detail === 'string') message = payload.detail
    } catch {
      // Ответ без JSON — оставляем исходное сообщение.
    }
    throw new Error(message)
  }

  return response.json()
}

export async function getDashboard(companyId) {
  // Убрали проверку на if (!API_BASE_URL). Теперь всегда делаем запрос на бэкенд.
  return request(`${API_ENDPOINTS.dashboard}?companyId=${encodeURIComponent(companyId)}`)
}

export async function getCounterparties(companyId) {
  return request(`${API_ENDPOINTS.counterparties}?companyId=${encodeURIComponent(companyId || '')}`)
}

export async function askNewsQuestion(newsId, question) {
  return request(API_ENDPOINTS.newsChat(newsId), {
    method: 'POST',
    body: JSON.stringify({ question }),
  })
}

export async function downloadCompanyReport(companyId, { file, title }) {
  const formData = new FormData()
  formData.append('template', file)
  formData.append('title', title)

  const response = await fetch(`${API_BASE_URL}/api/companies/${companyId}/report`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    let detail = `Ошибка API: ${response.status} ${response.statusText}`
    try {
      const body = await response.json()
      if (body?.detail) detail = body.detail
    } catch {
      // ignore non-JSON error body
    }
    throw new Error(detail)
  }

  return response.blob()
}