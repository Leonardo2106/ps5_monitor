import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../services/api'
import type { Settings } from '../types/api'

export function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null)
  const [interval, setIntervalValue] = useState(1800)
  const [alertBest, setAlertBest] = useState(true)
  const [scanPromotions, setScanPromotions] = useState(true)
  const [maxAge, setMaxAge] = useState(72)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [running, setRunning] = useState(false)

  useEffect(() => {
    api.getSettings().then((data) => {
      setSettings(data)
      setIntervalValue(data.check_interval)
      setAlertBest(data.alert_best_offer)
      setScanPromotions(data.scan_promotion_sources)
      setMaxAge(data.promotion_max_age_hours)
    }).catch((err: Error) => setError(err.message))
  }, [])

  async function save(event: FormEvent) {
    event.preventDefault()
    try {
      const data = await api.updateSettings({
        check_interval: interval,
        alert_best_offer: alertBest,
        scan_promotion_sources: scanPromotions,
        promotion_max_age_hours: maxAge,
      })
      setSettings(data)
      setMessage('Configurações atualizadas.')
      setError('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao salvar.')
    }
  }

  async function testTelegram() {
    try {
      const result = await api.testTelegram('✅ <b>Teste do monitor concluído.</b>\nO botão abaixo confirma que links clicáveis estão funcionando.', 'https://www.playstation.com/pt-br/ps5/')
      setMessage(result.detail)
      setError('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha no Telegram.')
    }
  }

  async function runNow() {
    setRunning(true)
    setMessage('')
    try {
      const result = await api.runMonitor()
      setMessage(`Coleta concluída: ${result.collected} preços, ${result.promotions} promoções, ${result.errors} falhas e ${result.alerts} alertas.`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha ao executar o monitor.')
    } finally {
      setRunning(false)
    }
  }

  return (
    <section>
      <header className="page-header"><div><span className="eyebrow">SISTEMA</span><h1>Configurações</h1><p>Controle frequência, alertas de menor preço e pesquisa em fontes públicas.</p></div></header>
      {message && <div className="alert success">{message}</div>}
      {error && <div className="alert error">{error}</div>}

      <div className="settings-grid">
        <article className="panel">
          <div className="panel-header"><div><h2>Monitor e alertas</h2><p>O mínimo permitido é 60 segundos.</p></div></div>
          <form className="form-grid" onSubmit={save}>
            <label>Intervalo em segundos<input type="number" min="60" max="86400" value={interval} onChange={(event) => setIntervalValue(Number(event.target.value))} /></label>
            <label>Idade máxima de promoções (horas)<input type="number" min="1" max="720" value={maxAge} onChange={(event) => setMaxAge(Number(event.target.value))} /></label>
            <label className="checkbox-label"><input type="checkbox" checked={alertBest} onChange={(event) => setAlertBest(event.target.checked)} />Enviar todo novo menor preço sem repetir a mesma oferta</label>
            <label className="checkbox-label"><input type="checkbox" checked={scanPromotions} onChange={(event) => setScanPromotions(event.target.checked)} />Pesquisar cupons e fontes públicas de promoções</label>
            <button className="primary-button" type="submit">Salvar configurações</button>
          </form>
        </article>

        <article className="panel">
          <div className="panel-header"><div><h2>Telegram</h2><p>O alerta inclui PIX, parcelas, cupom e botão para abrir a oferta.</p></div></div>
          <div className="integration-status"><span className={settings?.telegram_configured ? 'status-dot' : 'status-dot offline'} /><strong>{settings?.telegram_configured ? 'Configurado' : 'Não configurado'}</strong></div>
          <div className="integration-status"><span className={settings?.telegram_webhook_configured ? 'status-dot' : 'status-dot offline'} /><strong>{settings?.telegram_webhook_configured ? 'Webhook de entrada configurado' : 'Webhook de entrada sem segredo'}</strong></div>
          <button className="secondary-button" onClick={testTelegram}>Testar mensagem com link</button>
        </article>

        <article className="panel">
          <div className="panel-header"><div><h2>WhatsApp Cloud API</h2><p>Recebe promoções encaminhadas e mensagens de conversas autorizadas pela Meta.</p></div></div>
          <div className="integration-status"><span className={settings?.whatsapp_webhook_configured ? 'status-dot' : 'status-dot offline'} /><strong>{settings?.whatsapp_webhook_configured ? 'Webhook configurado' : 'Tokens do webhook não configurados'}</strong></div>
        </article>

        <article className="panel full-width">
          <div className="panel-header"><div><h2>Execução manual</h2><p>Verifica lojas, URLs diretas e fontes públicas. O Playwright é usado quando necessário.</p></div></div>
          <button className="primary-button" disabled={running} onClick={runNow}>{running ? 'Executando...' : 'Verificar tudo agora'}</button>
        </article>

        <article className="panel full-width">
          <div className="panel-header"><div><h2>Lojas ativas</h2><p>Gerencie lojas e páginas diretas no menu Lojas.</p></div></div>
          <div className="store-grid">{settings?.stores.map((store) => <span className="store-chip" key={store}>{store}</span>)}</div>
        </article>
      </div>
    </section>
  )
}
