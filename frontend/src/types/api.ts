export interface Product {
  id: number
  name: string
  search_query: string
  target_price: number
  active: boolean
  created_at: string
}

export interface ProductPayload {
  name: string
  search_query: string
  target_price: number
  active: boolean
}

export interface Store {
  id: number
  name: string
  base_url: string
  search_url: string
  active: boolean
  is_builtin: boolean
  card_selectors: string | null
  title_selectors: string | null
  price_selectors: string | null
  link_selectors: string | null
  cash_selectors: string | null
  installment_selectors: string | null
  coupon_selectors: string | null
  created_at: string
}

export interface StorePayload {
  name: string
  base_url: string
  search_url: string
  active: boolean
  card_selectors?: string | null
  title_selectors?: string | null
  price_selectors?: string | null
  link_selectors?: string | null
  cash_selectors?: string | null
  installment_selectors?: string | null
  coupon_selectors?: string | null
}

export interface ProductStoreLink {
  id: number
  product_id: number
  product_name: string
  store_id: number
  store_name: string
  url: string
  active: boolean
  created_at: string
}

export interface ProductStoreLinkPayload {
  product_id: number
  store_id: number
  url: string
  active: boolean
}

export interface Price {
  id: number
  date: string
  store: string
  product: string
  price: number
  title: string | null
  url: string | null
  cash_price: number | null
  installment_price: number | null
  installment_count: number | null
  coupon: string | null
  coupon_discount: string | null
  coupon_conditions: string | null
  coupon_confidence: number | null
  source_type: string
}

export interface BestOffer {
  product: string
  store: string
  price: number
  cash_price: number | null
  installment_price: number | null
  installment_count: number | null
  coupon: string | null
  coupon_discount: string | null
  coupon_conditions: string | null
  coupon_confidence: number | null
  title: string | null
  date: string
  url: string | null
  source_type: string
}

export interface ProductStats {
  product_id: number
  product: string
  last_price: number | null
  minimum_price: number | null
  best_store: string | null
  last_update: string | null
  target_price: number
  samples: number
}

export interface StatsResponse {
  products: ProductStats[]
  last_update: string | null
}

export type PromotionSourceType = 'web' | 'telegram_public' | 'telegram_bot' | 'whatsapp_cloud'

export interface PromotionSource {
  id: number
  name: string
  source_type: PromotionSourceType
  url: string
  external_id: string | null
  product_id: number | null
  product_name: string | null
  store_id: number | null
  store_name: string | null
  keywords: string | null
  active: boolean
  created_at: string
}

export interface PromotionSourcePayload {
  name: string
  source_type: PromotionSourceType
  url: string
  external_id: string | null
  product_id: number | null
  store_id: number | null
  keywords: string | null
  active: boolean
}

export interface Promotion {
  id: number
  date: string
  source: string
  store: string | null
  product: string
  title: string
  price: number
  cash_price: number | null
  installment_price: number | null
  installment_count: number | null
  coupon: string | null
  coupon_discount: string | null
  coupon_conditions: string | null
  coupon_confidence: number | null
  url: string
}

export interface Settings {
  check_interval: number
  telegram_configured: boolean
  telegram_webhook_configured: boolean
  whatsapp_webhook_configured: boolean
  timezone: string
  stores: string[]
  alert_cooldown_seconds: number
  alert_best_offer: boolean
  scan_promotion_sources: boolean
  promotion_max_age_hours: number
}

export interface SettingsPayload {
  check_interval?: number
  alert_best_offer?: boolean
  scan_promotion_sources?: boolean
  promotion_max_age_hours?: number
}

export interface MonitorResult {
  success: boolean
  collected: number
  errors: number
  alerts: number
  promotions: number
}
