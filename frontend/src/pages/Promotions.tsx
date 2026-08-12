import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../services/api'
import type { Product, Promotion, PromotionSource, PromotionSourcePayload, PromotionSourceType, Store } from '../types/api'
import { formatBRL, formatDateTime, installmentLabel } from '../utils'

const emptySource: PromotionSourcePayload = {
  name: '',
  source_type: 'web',
  url: '',
  external_id: null,
  product_id: null,
  store_id: null,
  keywords: '',
  active: true,
}

export function Promotions() {
  const [sources, setSources] = useState<PromotionSource[]>([])
  const [promotions, setPromotions] = useState<Promotion[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [stores, setStores] = useState<Store[]>([])
  const [form, setForm] = useState<PromotionSourcePayload>(emptySource)
  const [scanning, setScanning] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const webhookSource = form.source_type === 'telegram_bot' || form.source_type === 'whatsapp_cloud'

  const sourceLabel = (type: PromotionSourceType) => ({
    web: 'Página pública',
    telegram_public: 'Telegram público',
    telegram_bot: 'Grupo/canal via bot',
    whatsapp_cloud: 'WhatsApp Cloud API',
  })[type]

  const load = async () => {
    const [sourcesData, promotionsData, productsData, storesData] = await Promise.all([
      api.getPromotionSources(), api.getPromotions(), api.getProducts(), api.getStores(),
    ])
    setSources(sourcesData)
    setPromotions(promotionsData)
    setProducts(productsData)
    setStores(storesData)
  }

  useEffect(() => { load().catch((err: Error) => setError(err.message)) }, [])

  async function addSource(event: FormEvent) {
    event.preventDefault()
    setError('')
    try {
      await api.createPromotionSource({ ...form, keywords: form.keywords || null })
      setForm(emptySource)
      setMessage('Fonte pública adicionada. Ela será analisada nas próximas verificações.')
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha ao adicionar fonte.')
    }
  }

  async function toggle(source: PromotionSource) {
    await api.updatePromotionSource(source.id, { active: !source.active })
    await load()
  }

  async function remove(source: PromotionSource) {
    if (!window.confirm(`Excluir a fonte ${source.name}?`)) return
    await api.deletePromotionSource(source.id)
    await load()
  }

  async function scanNow() {
    setScanning(true)
    setMessage('')
    setError('')
    try {
      const result = await api.scanPromotions()
      setMessage(`Verificação concluída: ${result.promotions} promoção(ões) nova(s), ${result.alerts} alerta(s) e ${result.errors} falha(s).`)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha ao pesquisar promoções.')
    } finally {
      setScanning(false)
    }
  }

  return (
    <section>
      <header className="page-header">
        <div><span className="eyebrow">CUPONS E GRUPOS</span><h1>Fontes de promoção</h1><p>Monitore páginas públicas ou receba mensagens autenticadas do Telegram e WhatsApp, com deduplicação automática.</p></div>
        <button className="primary-button" disabled={scanning} onClick={scanNow}>{scanning ? 'Pesquisando...' : 'Pesquisar agora'}</button>
      </header>
      {message && <div className="alert success">{message}</div>}
      {error && <div className="alert error">{error}</div>}

      <div className="two-column-grid">
        <article className="panel">
          <div className="panel-header"><div><h2>Nova fonte</h2><p>Use URL para páginas públicas; para webhooks, informe o ID exato do chat, grupo, remetente ou número Business autorizado.</p></div></div>
          <form className="form-grid" onSubmit={addSource}>
            <label>Nome<input required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="Ex.: Canal Promoções Gamer" /></label>
            <label>Tipo<select value={form.source_type} onChange={(event) => setForm({ ...form, source_type: event.target.value as PromotionSourceType })}><option value="web">Página pública</option><option value="telegram_public">Canal público do Telegram</option><option value="telegram_bot">Grupo/canal via bot</option><option value="whatsapp_cloud">WhatsApp Cloud API</option></select></label>
            <label>URL {webhookSource ? '(opcional)' : ''}<input required={!webhookSource} value={form.url} onChange={(event) => setForm({ ...form, url: event.target.value })} placeholder={form.source_type === 'telegram_public' ? 'https://t.me/s/canal' : 'https://...'} /></label>
            {webhookSource && <label>ID externo<input required value={form.external_id ?? ''} onChange={(event) => setForm({ ...form, external_id: event.target.value })} placeholder={form.source_type === 'telegram_bot' ? '-1001234567890' : 'ID do grupo, telefone ou phone_number_id'} /></label>}
            <label>Produto específico<select value={form.product_id ?? ''} onChange={(event) => setForm({ ...form, product_id: event.target.value ? Number(event.target.value) : null })}><option value="">Todos os produtos</option>{products.map((product) => <option key={product.id} value={product.id}>{product.name}</option>)}</select></label>
            <label>Loja associada<select value={form.store_id ?? ''} onChange={(event) => setForm({ ...form, store_id: event.target.value ? Number(event.target.value) : null })}><option value="">Detectar automaticamente</option>{stores.map((store) => <option key={store.id} value={store.id}>{store.name}</option>)}</select></label>
            <label>Palavras-chave adicionais<input value={form.keywords ?? ''} onChange={(event) => setForm({ ...form, keywords: event.target.value })} placeholder="ps5, slim, cupom, pix" /></label>
            <button className="primary-button" type="submit">Adicionar fonte</button>
          </form>
        </article>

        <article className="panel">
          <div className="panel-header"><div><h2>Fontes configuradas</h2><p>{sources.length} fonte(s)</p></div></div>
          <div className="source-list">
            {sources.map((source) => (
              <div className="source-card" key={source.id}>
                <div className="source-card-header"><strong>{source.name}</strong><span className={source.active ? 'pill active' : 'pill'}>{source.active ? 'Ativa' : 'Pausada'}</span></div>
                <small>{sourceLabel(source.source_type)} · {source.product_name || 'Todos os produtos'}{source.external_id ? ` · ID ${source.external_id}` : ''}</small>
                {source.url && <a className="source-url" href={source.url} target="_blank" rel="noreferrer">{source.url}</a>}
                <div className="row-actions"><button onClick={() => toggle(source)}>{source.active ? 'Pausar' : 'Ativar'}</button><button className="danger" onClick={() => remove(source)}>Excluir</button></div>
              </div>
            ))}
            {sources.length === 0 && <div className="empty-state small-empty">Nenhuma fonte adicionada.</div>}
          </div>
        </article>
      </div>

      <article className="panel">
        <div className="panel-header"><div><h2>Promoções descobertas</h2><p>Um mesmo preço, cupom e URL não é salvo nem enviado novamente.</p></div></div>
        <div className="table-wrapper">
          <table>
            <thead><tr><th>Produto</th><th>Fonte/Loja</th><th>À vista</th><th>Parcelado</th><th>Cupom</th><th>Encontrado</th><th>Link</th></tr></thead>
            <tbody>
              {promotions.map((promotion) => (
                <tr key={promotion.id}>
                  <td>{promotion.product}</td>
                  <td>{promotion.store || promotion.source}<small className="table-subtitle">{promotion.source}</small></td>
                  <td className="price-cell">{formatBRL(promotion.cash_price ?? promotion.price)}</td>
                  <td>{installmentLabel(promotion.installment_count, promotion.installment_price)}</td>
                  <td>{promotion.coupon || '—'} {promotion.coupon_discount ? `(${promotion.coupon_discount})` : ''}{promotion.coupon_conditions && <small className="table-subtitle">{promotion.coupon_conditions}</small>}</td>
                  <td>{formatDateTime(promotion.date)}</td>
                  <td><a className="text-link" href={promotion.url} target="_blank" rel="noreferrer">Abrir</a></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </article>
    </section>
  )
}
