import type {
  BestOffer,
  MonitorResult,
  Price,
  Product,
  ProductPayload,
  ProductStoreLink,
  ProductStoreLinkPayload,
  Promotion,
  PromotionSource,
  PromotionSourcePayload,
  Settings,
  SettingsPayload,
  StatsResponse,
  Store,
  StorePayload,
} from '../types/api'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })

  if (!response.ok) {
    let detail = `Erro HTTP ${response.status}`
    try {
      const body = (await response.json()) as { detail?: string | Array<{ msg?: string }> }
      detail = typeof body.detail === 'string'
        ? body.detail
        : body.detail?.map((item) => item.msg).filter(Boolean).join(', ') || detail
    } catch {
      // Keep the generic error when the response has no JSON body.
    }
    throw new Error(detail)
  }

  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const api = {
  getProducts: () => request<Product[]>('/products'),
  createProduct: (payload: ProductPayload) =>
    request<Product>('/products', { method: 'POST', body: JSON.stringify(payload) }),
  updateProduct: (id: number, payload: Partial<ProductPayload>) =>
    request<Product>(`/products/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  deleteProduct: (id: number) => request<void>(`/products/${id}`, { method: 'DELETE' }),

  getStores: () => request<Store[]>('/stores'),
  createStore: (payload: StorePayload) =>
    request<Store>('/stores', { method: 'POST', body: JSON.stringify(payload) }),
  updateStore: (id: number, payload: Partial<StorePayload>) =>
    request<Store>(`/stores/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  deleteStore: (id: number) => request<void>(`/stores/${id}`, { method: 'DELETE' }),

  getProductLinks: () => request<ProductStoreLink[]>('/product-links'),
  createProductLink: (payload: ProductStoreLinkPayload) =>
    request<ProductStoreLink>('/product-links', { method: 'POST', body: JSON.stringify(payload) }),
  updateProductLink: (id: number, payload: Partial<ProductStoreLinkPayload>) =>
    request<ProductStoreLink>(`/product-links/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  deleteProductLink: (id: number) => request<void>(`/product-links/${id}`, { method: 'DELETE' }),

  getStats: () => request<StatsResponse>('/stats'),
  getBestOffers: () => request<BestOffer[]>('/best-offers'),
  getHistory: (product?: string, days = 30) => {
    const params = new URLSearchParams({ days: String(days) })
    if (product) params.set('product', product)
    return request<Price[]>(`/prices/history?${params.toString()}`)
  },

  getPromotionSources: () => request<PromotionSource[]>('/promotion-sources'),
  createPromotionSource: (payload: PromotionSourcePayload) =>
    request<PromotionSource>('/promotion-sources', { method: 'POST', body: JSON.stringify(payload) }),
  updatePromotionSource: (id: number, payload: Partial<PromotionSourcePayload>) =>
    request<PromotionSource>(`/promotion-sources/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  deletePromotionSource: (id: number) => request<void>(`/promotion-sources/${id}`, { method: 'DELETE' }),
  getPromotions: () => request<Promotion[]>('/promotions?limit=200'),
  scanPromotions: () => request<MonitorResult>('/promotions/scan', { method: 'POST' }),

  getSettings: () => request<Settings>('/settings'),
  updateSettings: (payload: SettingsPayload) =>
    request<Settings>('/settings', { method: 'PUT', body: JSON.stringify(payload) }),
  testTelegram: (message: string, url?: string) =>
    request<{ success: boolean; detail: string }>('/telegram/test', {
      method: 'POST',
      body: JSON.stringify({ message, url: url || null }),
    }),
  runMonitor: () => request<MonitorResult>('/monitor/run', { method: 'POST' }),
  exportUrl: `${API_URL}/prices/export`,
}
