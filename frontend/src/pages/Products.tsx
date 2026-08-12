import { useEffect, useState } from 'react'
import type { ChangeEvent, FormEvent } from 'react'
import { api } from '../services/api'
import type { Product, ProductPayload } from '../types/api'
import { formatBRL } from '../utils'

const initialForm: ProductPayload = { name: '', search_query: '', target_price: 0, active: true }

export function Products() {
  const [products, setProducts] = useState<Product[]>([])
  const [form, setForm] = useState<ProductPayload>(initialForm)
  const [targetDrafts, setTargetDrafts] = useState<Record<number, string>>({})
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const loadProducts = async () => {
    const data = await api.getProducts()
    setProducts(data)
    setTargetDrafts(Object.fromEntries(data.map((product) => [product.id, String(product.target_price)])))
  }

  useEffect(() => { loadProducts().catch((err: Error) => setError(err.message)) }, [])

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    setMessage('')
    try {
      await api.createProduct(form)
      setForm(initialForm)
      setMessage('Produto adicionado com sucesso.')
      await loadProducts()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível cadastrar o produto.')
    }
  }

  async function toggle(product: Product) {
    await api.updateProduct(product.id, { active: !product.active })
    await loadProducts()
  }

  async function saveTarget(product: Product) {
    const value = Number(targetDrafts[product.id])
    if (value <= 0) return
    await api.updateProduct(product.id, { target_price: value })
    setMessage(`Preço-alvo de ${product.name} atualizado para ${formatBRL(value)}.`)
    await loadProducts()
  }

  async function remove(product: Product) {
    if (!window.confirm(`Remover ${product.name}?`)) return
    await api.deleteProduct(product.id)
    await loadProducts()
  }

  return (
    <section>
      <header className="page-header"><div><span className="eyebrow">CATÁLOGO</span><h1>Produtos monitorados</h1><p>Cadastre produtos e altere o preço-alvo diretamente na lista.</p></div></header>
      {message && <div className="alert success">{message}</div>}
      {error && <div className="alert error">{error}</div>}

      <div className="products-layout">
        <article className="panel">
          <div className="panel-header"><div><h2>Novo produto</h2><p>Defina o termo de busca e o valor de alerta.</p></div></div>
          <form className="form-grid" onSubmit={submit}>
            <label>Nome do produto<input required value={form.name} onChange={(e: ChangeEvent<HTMLInputElement>) => setForm({ ...form, name: e.target.value })} placeholder="Ex.: PlayStation 5 Pro" /></label>
            <label>Termo de busca<input required value={form.search_query} onChange={(e: ChangeEvent<HTMLInputElement>) => setForm({ ...form, search_query: e.target.value })} placeholder="Ex.: PS5 Pro 2TB" /></label>
            <label>Preço-alvo (R$)<input required type="number" min="1" step="0.01" value={form.target_price || ''} onChange={(e: ChangeEvent<HTMLInputElement>) => setForm({ ...form, target_price: Number(e.target.value) })} /></label>
            <label className="checkbox-label"><input type="checkbox" checked={form.active} onChange={(e) => setForm({ ...form, active: e.target.checked })} />Monitorar imediatamente</label>
            <button className="primary-button" type="submit">Adicionar produto</button>
          </form>
        </article>

        <article className="panel">
          <div className="panel-header"><div><h2>Lista atual</h2><p>{products.length} produto(s) cadastrado(s)</p></div></div>
          <div className="product-list">
            {products.map((product) => (
              <div className="product-row product-row-expanded" key={product.id}>
                <div><strong>{product.name}</strong><small>Busca: {product.search_query}</small></div>
                <div className="target-editor">
                  <label>Preço-alvo</label>
                  <div className="inline-edit">
                    <input type="number" min="1" step="0.01" value={targetDrafts[product.id] ?? ''} onChange={(event) => setTargetDrafts({ ...targetDrafts, [product.id]: event.target.value })} />
                    <button className="compact-button" onClick={() => saveTarget(product)}>Salvar</button>
                  </div>
                </div>
                <span className={product.active ? 'pill active' : 'pill'}>{product.active ? 'Ativo' : 'Pausado'}</span>
                <div className="row-actions"><button onClick={() => toggle(product)}>{product.active ? 'Pausar' : 'Ativar'}</button><button className="danger" onClick={() => remove(product)}>Excluir</button></div>
              </div>
            ))}
          </div>
        </article>
      </div>
    </section>
  )
}
