# PS5 Price Monitor Brasil — versão 2

Sistema full stack para monitorar preços do **PlayStation 5 Slim Digital**, do **PlayStation 5 Slim com leitor** e de outros produtos cadastrados pelo usuário. O projeto coleta preços em lojas brasileiras, mantém histórico em SQLite, pesquisa cupons em páginas públicas, acompanha canais públicos de promoções e envia alertas completos pelo Telegram.

## Novidades desta versão

- Cadastro de lojas pelo frontend.
- Ativação e pausa de lojas nativas ou personalizadas.
- URL direta por combinação de produto e loja.
- Preço-alvo editável no Dashboard e na página de Produtos.
- Link clicável para a página original da oferta.
- Captura de preço à vista/PIX.
- Captura de parcelamento, incluindo quantidade e valor das parcelas.
- Identificação de código e desconto de cupom quando estiverem visíveis na página.
- Alertas do Telegram com botão **Abrir oferta**.
- Deduplicação por produto, loja, preço, parcelas, cupom e URL.
- Novo alerta de menor preço somente quando o valor é igual ou inferior ao menor já alertado e a oferta ainda não foi enviada.
- Cadastro de páginas públicas de promoções.
- Leitura de visualizações públicas de canais do Telegram no formato `https://t.me/s/nome_do_canal`.
- Histórico separado de promoções e cupons encontrados.
- Migração automática do banco da versão anterior, sem apagar o histórico.

## Lojas nativas

- Amazon Brasil
- Kabum
- Magazine Luiza
- Mercado Livre
- Casas Bahia
- Ponto
- Fast Shop

Novas lojas podem ser adicionadas na página **Lojas**.

## Como funciona o alerta de menor preço

Em cada rodada, o sistema coleta as ofertas disponíveis e identifica o menor preço atual de cada produto.

O primeiro menor preço encontrado gera um alerta. Depois disso:

- um preço maior que o menor já alertado não é enviado;
- um preço menor gera um novo alerta;
- um preço igual pode gerar alerta quando a loja, URL, cupom ou condição de parcelamento mudou;
- a mesma combinação nunca é enviada novamente;
- todas as promoções públicas novas são salvas; somente a melhor promoção nova de cada produto entra na disputa por alerta;
- promoções e preços usam a mesma deduplicação, evitando que a mesma URL e condição seja enviada duas vezes por fontes diferentes.

O evento é salvo em `alert_events`, mesmo quando o Telegram não está configurado, para evitar repetições no terminal e no log.

## Exemplo de alerta

```text
🚨 NOVO MENOR PREÇO ENCONTRADO!

Produto: PlayStation 5 Slim com Leitor de Disco
Loja: Amazon Brasil
À vista/PIX: R$ 3.499,00
Parcelado: 10x de R$ 379,90 (total R$ 3.799,00)
Cupom: PS5OFF (5%)
Preço-alvo: R$ 3.500,00
Status: Atingiu o preço-alvo
Data: 30/07/2026 15:20

https://www.amazon.com.br/...
```

Além do link no texto, o Telegram recebe um botão **🛒 Abrir oferta**.

## Limitações importantes

A identificação de PIX, parcelas e cupons é feita com base no conteúdo disponível publicamente no HTML. Algumas lojas exibem essas condições somente após login, seleção de CEP, uso do aplicativo ou inclusão do produto no carrinho. Nesses casos, o campo aparecerá como não identificado.

O sistema não entra em grupos privados nem usa uma conta pessoal do Telegram. Ele pode analisar:

- páginas públicas de promoções;
- visualizações públicas de canais do Telegram;
- grupos ou canais próprios em uma futura integração, desde que o bot seja adicionado e tenha permissão para receber as mensagens.

Seletores e páginas de lojas podem mudar. O sistema usa extração genérica, JSON-LD, seletores específicos e fallback para Playwright, mas uma loja personalizada pode exigir a configuração manual dos seletores CSS.

## Arquitetura

```text
ps5_monitor/
├── backend/
│   ├── tests/
│   ├── __init__.py
│   ├── config.py
│   ├── database.py
│   ├── logging_setup.py
│   ├── main.py
│   ├── models.py
│   ├── monitor.py
│   ├── promotions.py
│   ├── scheduler_fallback.py
│   ├── schemas.py
│   ├── scraper.py
│   ├── telegram_notifier.py
│   ├── utils.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Products.tsx
│   │   │   ├── Promotions.tsx
│   │   │   ├── Settings.tsx
│   │   │   └── Stores.tsx
│   │   ├── services/
│   │   ├── types/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── styles.css
│   ├── package.json
│   └── vite.config.ts
├── .env.example
├── docker-compose.yml
├── Dockerfile
└── README.md
```

## Tecnologias

### Backend

- Python 3.13
- FastAPI
- SQLAlchemy
- Pydantic
- SQLite
- Requests
- BeautifulSoup4
- Playwright
- Schedule
- python-telegram-bot
- Logging

### Frontend

- React 19
- Vite
- TypeScript
- React Router
- Chart.js

## Automações no GitHub

O repositório inclui workflows para manter cada parte do projeto verificável e
publicável sem depender do ambiente local:

- **CI:** roda os testes do backend em Python 3.13, valida o TypeScript e o bundle
  do frontend em Node 22 e confirma que a imagem Docker da API continua compilando.
- **Security audit:** toda segunda-feira, verifica vulnerabilidades conhecidas nas
  dependências Python e npm; também pode ser executado manualmente.
- **Publish API image:** ao enviar uma tag como `v2.1.0`, publica a API em
  `ghcr.io/OWNER/REPOSITORY`, com tags semânticas, cache de build e atestado de
  proveniência em repositórios públicos. A execução manual publica uma tag baseada
  no SHA do commit.
- **Dependabot:** agrupa atualizações semanais de GitHub Actions, pip, npm e da
  imagem-base Docker para reduzir o ruido de pull requests.

Para publicar uma versão:

```bash
git tag v2.1.0
git push origin v2.1.0
```

## Instalação local

### 1. Configuração

Copie o arquivo de exemplo para `.env`.

**Windows PowerShell**

```powershell
Copy-Item .env.example .env
```

**Linux e macOS**

```bash
cp .env.example .env
```

Edite o arquivo:

```env
TELEGRAM_TOKEN=SEU_TOKEN
CHAT_ID=SEU_CHAT_ID
TELEGRAM_WEBHOOK_SECRET=SEGREDO_ALEATORIO
WHATSAPP_VERIFY_TOKEN=TOKEN_DE_VERIFICACAO
WHATSAPP_APP_SECRET=SEGREDO_DO_APP_META
CHECK_INTERVAL=1800
DIGITAL_TARGET=3100
DISK_TARGET=3500
TIMEZONE=America/Sao_Paulo
DATABASE_PATH=./ps5_prices.db
LOG_FILE=./backend/monitor.log
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
START_MONITOR_WITH_API=true
RUN_ON_STARTUP=true
PLAYWRIGHT_HEADLESS=true
REQUEST_TIMEOUT=20
PLAYWRIGHT_TIMEOUT=30000
```

### 2. Backend no Windows

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
playwright install chromium
python -m uvicorn backend.main:app --reload
```

### 3. Backend no Linux ou macOS

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
playwright install chromium
python -m uvicorn backend.main:app --reload
```

API: `http://localhost:8000`

Swagger: `http://localhost:8000/docs`

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

Dashboard: `http://localhost:5173`

Para usar outro endereço de backend, crie `frontend/.env.local`:

```env
VITE_API_URL=http://localhost:8000
```

## Configuração do Telegram

1. Abra o Telegram e converse com `@BotFather`.
2. Envie `/newbot`.
3. Crie o nome e o usuário do bot.
4. Copie o token para `TELEGRAM_TOKEN`.
5. Envie uma mensagem para o seu bot.
6. Consulte `getUpdates` na API do Telegram.
7. Localize `message.chat.id`.
8. Copie o valor para `CHAT_ID`.
9. Reinicie o backend.
10. Abra **Configurações** e clique em **Testar mensagem com link**.

Nunca envie o arquivo `.env` para o GitHub.

## Adicionando uma loja

Abra **Lojas > Adicionar loja**.

Campos principais:

- **Nome:** nome exibido no dashboard.
- **URL base:** domínio principal.
- **URL de busca:** endereço usado para localizar produtos.

A URL pode conter:

- `{query}`: termo codificado para URL;
- `{slug}`: termo convertido para texto com hífens.

Exemplos:

```text
https://loja.com.br/busca?q={query}
https://loja.com.br/produtos/{slug}
```

### Seletores CSS opcionais

Para lojas que não funcionem com a extração genérica, configure um ou mais seletores separados por vírgula ou linha:

```text
Cards: article.product-card
Título: h2.product-name
Preço: .selling-price
Link: a.product-link
Preço PIX: .pix-price
Parcelamento: .installment-info
Cupom: .coupon-badge
```

## URL direta do produto

Uma URL direta é útil quando:

- a loja não possui busca pública;
- a busca retorna produtos incorretos;
- existe uma página específica da oferta;
- a loja exige um endereço diferente para cada edição do console.

Na página **Lojas**, selecione produto, loja e informe a URL. O monitor passa a priorizar essa página.

## Fontes de promoção

Abra **Promoções > Nova fonte**.

Tipos:

### Página pública

Pode ser uma página de promoções, cupons ou ofertas que mostre produto e preço no HTML.

### Canal público do Telegram

Use a visualização pública:

```text
https://t.me/s/nome_do_canal
```

É possível associar a fonte a um produto e a uma loja, além de informar palavras-chave como:

```text
ps5, slim, cupom, pix, leitor
```

O sistema ignora publicações mais antigas que o limite configurado em **Configurações** quando a página fornece data da postagem.

### Grupo ou canal via bot do Telegram

1. Adicione o bot ao grupo ou canal. Em grupos, torne-o administrador ou desative o Privacy Mode no `@BotFather` e adicione-o novamente.
2. Em **Promoções**, escolha **Grupo/canal via bot** e cadastre o `chat.id` exato, normalmente negativo em grupos e canais.
3. Publique a API em HTTPS e registre o webhook:

```bash
curl -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d "{\"url\":\"https://seu-dominio.com/webhooks/telegram\",\"secret_token\":\"${TELEGRAM_WEBHOOK_SECRET}\",\"allowed_updates\":[\"message\",\"edited_message\",\"channel_post\",\"edited_channel_post\"]}"
```

O endpoint só processa IDs cadastrados e valida `X-Telegram-Bot-Api-Secret-Token`. Não use `getUpdates` enquanto o webhook estiver ativo.

### WhatsApp Cloud API

1. Crie ou configure um app na Meta com WhatsApp Business Platform.
2. Configure `https://seu-dominio.com/webhooks/whatsapp` como callback e use `WHATSAPP_VERIFY_TOKEN` na verificação.
3. Copie o segredo do app para `WHATSAPP_APP_SECRET`; toda notificação recebida é validada por `X-Hub-Signature-256`.
4. Em **Promoções**, escolha **WhatsApp Cloud API** e informe como ID externo o identificador autorizado: ID do grupo quando disponível, telefone do remetente ou `phone_number_id` do número Business.

O acesso a grupos depende da elegibilidade liberada pela Meta para a conta. Sem Groups API, uma alternativa oficial é encaminhar a oferta para o número Business cadastrado. O sistema não automatiza WhatsApp Web nem sessões pessoais.

### Extração de cupons

O parser reconhece código, percentual ou valor de desconto, compra mínima, validade e restrições como primeira compra, clientes selecionados, PIX ou uso exclusivo no aplicativo. Cada cupom recebe uma confiança e a mensagem externa é deduplicada antes do processamento.

## Banco de dados

O banco `ps5_prices.db` é criado automaticamente.

A tabela original é preservada e expandida:

```sql
CREATE TABLE prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    store TEXT,
    product TEXT,
    price REAL,
    title TEXT,
    url TEXT,
    cash_price REAL,
    installment_price REAL,
    installment_count INTEGER,
    coupon TEXT,
    coupon_discount TEXT,
    coupon_conditions TEXT,
    coupon_confidence REAL,
    source_type TEXT
);
```

Tabelas auxiliares:

- `products`
- `stores`
- `product_store_links`
- `promotion_sources`
- `promotions`
- `received_messages`
- `alert_events`
- `app_settings`

Ao iniciar, bancos antigos são atualizados automaticamente com `ALTER TABLE`. Faça backup do arquivo antes de qualquer atualização em produção.

## Endpoints principais

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/products` | Lista produtos |
| POST | `/products` | Cadastra produto |
| PATCH | `/products/{id}` | Altera produto ou preço-alvo |
| DELETE | `/products/{id}` | Exclui produto |
| GET | `/stores` | Lista lojas |
| POST | `/stores` | Cadastra loja |
| PATCH | `/stores/{id}` | Altera ou pausa loja |
| DELETE | `/stores/{id}` | Exclui loja personalizada |
| GET | `/product-links` | Lista URLs diretas |
| POST | `/product-links` | Vincula URL a produto e loja |
| PATCH | `/product-links/{id}` | Altera URL direta |
| DELETE | `/product-links/{id}` | Remove URL direta |
| GET | `/prices` | Lista preços |
| GET | `/prices/history` | Histórico de preços |
| GET | `/prices/export` | Exporta CSV |
| GET | `/best-offers` | Melhor oferta atual |
| GET | `/stats` | Estatísticas do dashboard |
| GET | `/promotion-sources` | Lista fontes públicas |
| POST | `/promotion-sources` | Adiciona fonte pública |
| PATCH | `/promotion-sources/{id}` | Altera ou pausa fonte |
| DELETE | `/promotion-sources/{id}` | Exclui fonte |
| GET | `/promotions` | Lista promoções encontradas |
| POST | `/promotions/scan` | Executa pesquisa manual |
| POST | `/telegram/test` | Testa mensagem e botão |
| POST | `/webhooks/telegram` | Recebe atualizações autenticadas do bot |
| GET | `/webhooks/whatsapp` | Verifica o callback da Meta |
| POST | `/webhooks/whatsapp` | Recebe mensagens assinadas da Cloud API |
| POST | `/monitor/run` | Executa rodada completa |
| GET | `/settings` | Exibe configurações |
| PUT | `/settings` | Atualiza configurações |
| GET | `/health` | Verifica API e banco |

## Testes

```bash
python -m pytest backend/tests -v
```

A suíte cobre:

- saúde da API;
- produtos;
- configuração do intervalo;
- lojas personalizadas;
- URL direta por produto e loja;
- fontes públicas de promoção;
- tabela principal de preços;
- parser brasileiro de valores;
- preço PIX;
- parcelamento;
- cupom e percentual de desconto;
- condições, validade e confiança do cupom;
- webhooks autenticados do Telegram e WhatsApp;
- deduplicação de mensagens externas;
- deduplicação de alertas;
- envio do Telegram com cliente simulado.

## Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

Serviços:

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:5173`

O banco fica no volume `ps5_data`.

## Execução somente do monitor

```bash
python -m backend.monitor
```

Nesse caso, desative o monitor iniciado pela API:

```env
START_MONITOR_WITH_API=false
```

## Boas práticas de uso

- Respeite os termos de uso, `robots.txt` e limites das lojas.
- Evite intervalos muito curtos.
- Não armazene tokens no código.
- Faça backup periódico do SQLite.
- Revise seletores quando uma loja alterar o layout.
- Confirme preço e condições no carrinho antes da compra.
- Cupons podem expirar, ser segmentados ou exigir aplicativo, cartão ou login.
