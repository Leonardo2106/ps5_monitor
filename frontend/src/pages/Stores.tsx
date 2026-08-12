import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../services/api'
import type { Product, ProductStoreLink, Store, StorePayload } from '../types/api'

const emptyStore: StorePayload = {
  name: '',
  base_url: '',
  search_url: '',
  active: true,
  card_selectors: '',
  title_selectors: '',
  price_selectors: '',
  link_selectors: '',
  cash_selectors: '',
  installment_selectors: '',
  coupon_selectors: '',
}

export function Stores() {
  const [stores, setStores] = useState<Store[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [links, setLinks] = useState<ProductStoreLink[]>([])
  const [storeForm, setStoreForm] = useState<StorePayload>(emptyStore)
  const [linkForm, setLinkForm] = useState({ product_id: 0, store_id: 0, url: '', active: true })
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const load = async () => {
    const [storesData, productsData, linksData] = await Promise.all([
      api.getStores(), api.getProducts(), api.getProductLinks(),
    ])
    setStores(storesData)
    setProducts(productsData)
    setLinks(linksData)
    setLinkForm((current) => ({
      ...current,
      product_id: current.product_id || productsData[0]?.id || 0,
      store_id: current.store_id || storesData[0]?.id || 0,
    }))
  }

  useEffect(() => { load().catch((err: Error) => setError(err.message)) }, [])

  async function addStore(event: FormEvent) {
    event.preventDefault()
    setError('')
    try {
      await api.createStore({
        ...storeForm,
        card_selectors: storeForm.card_selectors || null,
        title_selectors: storeForm.title_selectors || null,
        price_selectors: storeForm.price_selectors || null,
        link_selectors: storeForm.link_selectors || null,
        cash_selectors: storeForm.cash_selectors || null,
        installment_selectors: storeForm.installment_selectors || null,
        coupon_selectors: storeForm.coupon_selectors || null,
      })
      setStoreForm(emptyStore)
      setMessage('Loja personalizada adicionada.')
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha ao adicionar loja.')
    }
  }

  async function addLink(event: FormEvent) {
    event.preventDefault()
    setError('')
    try {
      await api.createProductLink(linkForm)
      setLinkForm({ ...linkForm, url: '' })
      setMessage('URL direta vinculada ao produto e à loja.')
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha ao salvar URL direta.')
    }
  }

  async function toggleStore(store: Store) {
    await api.updateStore(store.id, { active: !store.active })
    await load()
  }

  async function removeStore(store: Store) {
    if (!window.confirm(`Excluir a loja ${store.name}?`)) return
    try {
      await api.deleteStore(store.id)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível excluir a loja.')
    }
  }

  async function removeLink(link: ProductStoreLink) {
    await api.deleteProductLink(link.id)
    await load()
  }

  return (
    <section>
      <header className="page-header">
        <div><span className="eyebrow">FONTES DE PREÇO</span><h1>Lojas e URLs diretas</h1><p>Adicione qualquer loja e vincule a página exata de um produto quando a busca genérica não funcionar.</p></div>
      </header>
      {message && <div className="alert success">{message}</div>}
      {error && <div className="alert error">{error}</div>}

      <div className="two-column-grid">
        <article className="panel">
          <div className="panel-header"><div><h2>Adicionar loja</h2><p>A URL de busca aceita <code>{'{query}'}</code> e <code>{'{slug}'}</code>.</p></div></div>
          <form className="form-grid" onSubmit={addStore}>
            <label>Nome<input required value={storeForm.name} onChange={(event) => setStoreForm({ ...storeForm, name: event.target.value })} placeholder="Ex.: Loja oficial Sony" /></label>
            <label>URL base<input required value={storeForm.base_url} onChange={(event) => setStoreForm({ ...storeForm, base_url: event.target.value })} placeholder="https://www.loja.com.br" /></label>
            <label>URL de busca<input required value={storeForm.search_url} onChange={(event) => setStoreForm({ ...storeForm, search_url: event.target.value })} placeholder="https://www.loja.com.br/busca?q={query}" /></label>
            <button type="button" className="secondary-button" onClick={() => setShowAdvanced(!showAdvanced)}>{showAdvanced ? 'Ocultar seletores CSS' : 'Configurar seletores CSS (opcional)'}</button>
            {showAdvanced && (
              <div className="advanced-fields">
                <label>Cards de produto<textarea value={storeForm.card_selectors ?? ''} onChange={(event) => setStoreForm({ ...storeForm, card_selectors: event.target.value })} placeholder="article.product-card" /></label>
                <label>Título<textarea value={storeForm.title_selectors ?? ''} onChange={(event) => setStoreForm({ ...storeForm, title_selectors: event.target.value })} placeholder="h2, .product-name" /></label>
                <label>Preço<textarea value={storeForm.price_selectors ?? ''} onChange={(event) => setStoreForm({ ...storeForm, price_selectors: event.target.value })} placeholder=".price, [data-testid='price']" /></label>
                <label>Link<textarea value={storeForm.link_selectors ?? ''} onChange={(event) => setStoreForm({ ...storeForm, link_selectors: event.target.value })} placeholder="a[href]" /></label>
                <label>Preço PIX<textarea value={storeForm.cash_selectors ?? ''} onChange={(event) => setStoreForm({ ...storeForm, cash_selectors: event.target.value })} placeholder=".pix-price" /></label>
                <label>Parcelamento<textarea value={storeForm.installment_selectors ?? ''} onChange={(event) => setStoreForm({ ...storeForm, installment_selectors: event.target.value })} placeholder=".installments" /></label>
                <label>Cupom<textarea value={storeForm.coupon_selectors ?? ''} onChange={(event) => setStoreForm({ ...storeForm, coupon_selectors: event.target.value })} placeholder=".coupon" /></label>
              </div>
            )}
            <button className="primary-button" type="submit">Adicionar loja</button>
          </form>
        </article>

        <article className="panel">
          <div className="panel-header"><div><h2>URL direta do produto</h2><p>Prioriza a página informada em vez da busca da loja.</p></div></div>
          <form className="form-grid" onSubmit={addLink}>
            <label>Produto<select value={linkForm.product_id} onChange={(event) => setLinkForm({ ...linkForm, product_id: Number(event.target.value) })}>{products.map((product) => <option key={product.id} value={product.id}>{product.name}</option>)}</select></label>
            <label>Loja<select value={linkForm.store_id} onChange={(event) => setLinkForm({ ...linkForm, store_id: Number(event.target.value) })}>{stores.map((store) => <option key={store.id} value={store.id}>{store.name}</option>)}</select></label>
            <label>URL do produto<input required value={linkForm.url} onChange={(event) => setLinkForm({ ...linkForm, url: event.target.value })} placeholder="https://loja.com.br/produto/ps5" /></label>
            <button className="primary-button" type="submit">Vincular URL</button>
          </form>
          <div className="link-list">
            {links.map((link) => (
              <div className="compact-row" key={link.id}>
                <div><strong>{link.product_name}</strong><small>{link.store_name}</small></div>
                <a className="text-link" href={link.url} target="_blank" rel="noreferrer">Abrir</a>
                <button className="danger-button" onClick={() => removeLink(link)}>Excluir</button>
              </div>
            ))}
          </div>
        </article>
      </div>

      <article className="panel">
        <div className="panel-header"><div><h2>Lojas cadastradas</h2><p>As nativas podem ser pausadas; as personalizadas também podem ser excluídas.</p></div></div>
        <div className="cards-grid">
          {stores.map((store) => (
            <div className="source-card" key={store.id}>
              <div className="source-card-header"><strong>{store.name}</strong><span className={store.active ? 'pill active' : 'pill'}>{store.active ? 'Ativa' : 'Pausada'}</span></div>
              <small>{store.is_builtin ? 'Loja nativa' : 'Loja personalizada'}</small>
              <a className="source-url" href={store.base_url} target="_blank" rel="noreferrer">{store.base_url}</a>
              <div className="row-actions"><button onClick={() => toggleStore(store)}>{store.active ? 'Pausar' : 'Ativar'}</button>{!store.is_builtin && <button className="danger" onClick={() => removeStore(store)}>Excluir</button>}</div>
            </div>
          ))}
        </div>
      </article>
    </section>
  )
}
