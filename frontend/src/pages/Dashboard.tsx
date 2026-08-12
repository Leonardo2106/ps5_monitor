import { useEffect, useMemo, useState } from 'react'
import type { ChangeEvent } from 'react'
import { PriceChart } from '../components/PriceChart'
import { StatCard } from '../components/StatCard'
import { api } from '../services/api'
import type { BestOffer, Price, StatsResponse } from '../types/api'
import { formatBRL, formatDateTime, installmentLabel } from '../utils'

export function Dashboard() {
  const [stats, setStats] = useState<StatsResponse>({ products: [], last_update: null })
  const [offers, setOffers] = useState<BestOffer[]>([])
  const [history, setHistory] = useState<Price[]>([])
  const [selectedProduct, setSelectedProduct] = useState('')
  const [targetDraft, setTargetDraft] = useState('')
  const [loading, setLoading] = useState(true)
  const [savingTarget, setSavingTarget] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const loadSummary = async () => {
    const [statsData, offersData] = await Promise.all([api.getStats(), api.getBestOffers()])
    setStats(statsData)
    setOffers(offersData)
    if (statsData.products.length > 0) {
      setSelectedProduct((current) => current || statsData.products[0].product)
    }
  }

  useEffect(() => {
    loadSummary()
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    if (!selectedProduct) return
    api.getHistory(selectedProduct, 30).then(setHistory).catch((err: Error) => setError(err.message))
  }, [selectedProduct])

  const currentStats = useMemo(
    () => stats.products.find((item) => item.product === selectedProduct),
    [selectedProduct, stats.products],
  )
  const currentOffer = offers.find((item) => item.product === selectedProduct)

  useEffect(() => {
    setTargetDraft(currentStats ? String(currentStats.target_price) : '')
  }, [currentStats])

  async function saveTarget() {
    if (!currentStats || Number(targetDraft) <= 0) return
    setSavingTarget(true)
    setMessage('')
    setError('')
    try {
      await api.updateProduct(currentStats.product_id, { target_price: Number(targetDraft) })
      await loadSummary()
      setMessage('Preço-alvo atualizado diretamente pelo dashboard.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Não foi possível salvar o preço-alvo.')
    } finally {
      setSavingTarget(false)
    }
  }

  if (loading) return <div className="page-state">Carregando dashboard...</div>

  return (
    <section>
      <header className="page-header">
        <div>
          <span className="eyebrow">MONITORAMENTO NACIONAL</span>
          <h1>Dashboard de preços</h1>
          <p>Compare preço à vista, parcelamento, cupom e abra a página da oferta.</p>
        </div>
        <select value={selectedProduct} onChange={(event: ChangeEvent<HTMLSelectElement>) => setSelectedProduct(event.target.value)}>
          {stats.products.map((product) => <option key={product.product}>{product.product}</option>)}
        </select>
      </header>

      {message && <div className="alert success">{message}</div>}
      {error && <div className="alert error">{error}</div>}

      <div className="stats-grid">
        <StatCard label="Último preço" value={formatBRL(currentStats?.last_price)} helper={currentStats?.best_store ?? 'Sem dados'} />
        <StatCard label="Menor preço registrado" value={formatBRL(currentStats?.minimum_price)} helper={`${currentStats?.samples ?? 0} amostras`} />
        <article className="stat-card editable-stat">
          <span className="stat-label">Preço-alvo</span>
          <div className="inline-edit">
            <input type="number" min="1" step="0.01" value={targetDraft} onChange={(event) => setTargetDraft(event.target.value)} />
            <button className="compact-button" disabled={savingTarget} onClick={saveTarget}>{savingTarget ? '...' : 'Salvar'}</button>
          </div>
          <small>Altere sem sair do dashboard</small>
        </article>
        <StatCard label="Última atualização" value={formatDateTime(currentStats?.last_update)} helper="Horário local" />
      </div>

      <div className="dashboard-grid">
        <article className="panel chart-panel">
          <div className="panel-header"><div><h2>Evolução do preço</h2><p>Histórico dos últimos 30 dias</p></div></div>
          <div className="chart-container"><PriceChart prices={history} /></div>
        </article>

        <article className="panel best-offer-panel">
          <div className="panel-header"><div><h2>Melhor oferta atual</h2><p>Menor preço entre as últimas coletas</p></div></div>
          {currentOffer ? (
            <div className="best-offer">
              <span className="offer-badge">MELHOR PREÇO</span>
              <strong>{formatBRL(currentOffer.cash_price ?? currentOffer.price)}</strong>
              <h3>{currentOffer.store}</h3>
              <div className="offer-details">
                <span><b>Parcelado:</b> {installmentLabel(currentOffer.installment_count, currentOffer.installment_price)}</span>
                <span><b>Cupom:</b> {currentOffer.coupon || 'Não identificado'} {currentOffer.coupon_discount ? `(${currentOffer.coupon_discount})` : ''}</span>
              </div>
              <small>Atualizado em {formatDateTime(currentOffer.date)}</small>
              {currentOffer.url && <a className="primary-button offer-link" href={currentOffer.url} target="_blank" rel="noreferrer">Visitar página da oferta</a>}
            </div>
          ) : <div className="empty-state">Aguardando a primeira coleta de preços.</div>}
        </article>
      </div>

      <article className="panel">
        <div className="panel-header">
          <div><h2>Melhores ofertas por produto</h2><p>Com PIX, parcelamento, cupom e URL original</p></div>
          <a className="secondary-button" href={api.exportUrl}>Exportar CSV</a>
        </div>
        <div className="table-wrapper">
          <table>
            <thead><tr><th>Produto</th><th>Loja</th><th>À vista</th><th>Parcelado</th><th>Cupom</th><th>Atualização</th><th>Link</th></tr></thead>
            <tbody>
              {offers.map((offer) => (
                <tr key={offer.product}>
                  <td>{offer.product}</td>
                  <td>{offer.store}</td>
                  <td className="price-cell">{formatBRL(offer.cash_price ?? offer.price)}</td>
                  <td>{installmentLabel(offer.installment_count, offer.installment_price)}</td>
                  <td>{offer.coupon || '—'} {offer.coupon_discount ? `(${offer.coupon_discount})` : ''}</td>
                  <td>{formatDateTime(offer.date)}</td>
                  <td>{offer.url ? <a className="text-link" href={offer.url} target="_blank" rel="noreferrer">Abrir</a> : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </article>
    </section>
  )
}
