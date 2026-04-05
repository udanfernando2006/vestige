# Vestige

**A config-driven book availability tracker that scrapes Sri Lankan online bookstores on a schedule, persists availability history, logs scrape runs to AWS S3, and notifies you via email (and optionally Windows desktop notification) the moment a tracked book comes into stock.**

---

## What It Does

Vestige tracks book availability across multiple Sri Lankan online bookstores. Users define which books and series to track in a single YAML file — no code changes required. The scraper runs automatically (every 6 hours), checks each configured store for each configured book, writes results to PostgreSQL, uploads logs to AWS S3, and sends notifications the moment a tracked book comes back in stock.

**Core features:**

- 📚 **Config-driven** — Track books and stores via YAML. Add new books without touching code.
- 🔄 **Scheduled scraping** — Runs on a cron schedule (default: every 6 hours)
- 💾 **Immutable history** — Every result is appended to PostgreSQL as a snapshot. Users can query when a book came into stock or how availability has changed over time.
- 📤 **Audit logging** — Full scrape run results uploaded to AWS S3 for compliance and debugging
- 🔔 **Instant notifications** — Email (+ optional Windows desktop notification) the moment availability status changes
- 🎯 **Clean architecture** — No web dashboard, no real-time updates, no production infrastructure complexity. Demonstrates production patterns at appropriate scale.

---

## Technologies Demonstrated

Vestige emphasizes infrastructure, automation, and cloud operations:

| Layer                | Technology              | Skills Demonstrated                                             |
| -------------------- | ----------------------- | --------------------------------------------------------------- |
| **Orchestration**    | Kubernetes CronJob      | Pod scheduling, declarative configs, health management          |
| **Containerization** | Docker, Compose         | Multi-stage builds, image optimization, local dev environments  |
| **Cloud**            | AWS (S3, EC2, IAM)      | Object storage, compute instances, identity & access management |
| **Configuration**    | ConfigMaps, Secrets     | Externalized config, secret management, immutable deployments   |
| **Database**         | PostgreSQL + SQLAlchemy | Schema design, data persistence, ORM patterns                   |
| **Automation**       | Python, bash            | Scripting, API integration, scheduled tasks                     |
| **Monitoring**       | Logging & S3            | Audit trails, structured logging, compliance                    |

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│            books_config.yaml (your input)            │
│   (series, books, stores — managed as ConfigMap)     │
└───────────────────┬──────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────┐
│     Kubernetes CronJob (every 6 hours)               │
│   Spins up scraper container, runs, exits cleanly    │
└───────────────────┬──────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────┐
│           Python Scraper Container                   │
│                                                      │
│  ConfigLoader                                        │
│      ↓                                               │
│  ScraperFactory → [StoreScraper] → BeautifulSoup /   │
│      ↓                                    Playwright │
│      ↓                                               │
│  DBWriter ─────────────→ PostgreSQL                  │
│  S3Logger ─────────────→ AWS S3                      │
│  Notifier ─────────────→ SMTP (Email)                │
│           └──────────→ Desktop (optional)            │
└──────────────────────────────────────────────────────┘
```

**Data flow:**

1. CronJob fires, starts scraper container
2. ConfigLoader reads `books_config.yaml` (mounted as ConfigMap)
3. For each store × book, scrape the product page
4. Compare results against last known state in PostgreSQL
5. Write every result to `availability_snapshots` table (append-only)
6. Upload full run JSON to S3
7. If status changed, send notification
8. Container exits — Kubernetes cleans up

---

## Tech Stack

| Layer            | Technology         | Why This One                                      |
| ---------------- | ------------------ | ------------------------------------------------- |
| **Language**     | Python 3.12        | Dominant in scraping, readability, vast ecosystem |
| **Database**     | PostgreSQL 16      | Relational schema, true ACID, enterprise standard |
| **HTTP/HTML**    | Requests + BS4     | <br />Simple pages                                |
| **JS-rendered**  | Playwright         | Pages requiring JS execution                      |
| **ORM**          | SQLAlchemy         | Python's Prisma                                   |
| **Dev/Local**    | Docker Compose     | Multi-container setup, matches production pattern |
| **Production**   | Kubernetes CronJob | Scheduled, cloud-agnostic, highly available       |
| **Object Store** | AWS S3             | Audit logs, cheap, durable                        |
| **Email**        | SMTP               | Notifications                                     |

---

## Folder Structure

```
vestige/
├── scraper/                         # Python application
│   ├── main.py                      # Entry point: load config, run scrapers, notify
│   ├── config/
│   │   ├── loader.py                # Parse and validate books_config.yaml
│   ├── scrapers/
│   │   ├── base.py                  # Abstract BaseScraper class
│   │   ├── factory.py               # Map store name → scraper class
│   │   ├── sarasavi.py              # Store-specific scraper (example)
│   │   └── vijitha_yapa.py          # Store-specific scraper (example)
│   ├── db/
│   │   ├── models.py                # SQLAlchemy ORM models
│   │   └── writer.py                # Insert and query DB
│   ├── notifications/
│   │   ├── email_notifier.py        # SMTP sender
│   │   └── desktop_notifier.py      # Windows notification
│   ├── storage/
│   │   └── s3_logger.py             # Upload run JSON to S3
│   ├── models/
│   │   └── result.py                # AvailabilityResult dataclass
│   ├── requirements.txt
│   └── Dockerfile
│
├── k8s/                             # Kubernetes manifests
│   ├── cronjob.yaml                 # CronJob definition
│   ├── configmap.yaml               # Mount books_config.yaml
│   ├── secret.yaml                  # DB credentials, AWS keys, SMTP password
│   └── pvc.yaml                     # Persistent storage for Postgres
│
├── docker-compose.yml               # Local dev: scraper + postgres
├── books_config.yaml                # Book/series/store configuration
├── .env.example                     # Template for environment variables
└── README.md                        # This file
```

---

## Quick Start

### Prerequisites

- Docker & Docker Compose installed
- Python 3.12+ (for local development without Docker)
- Git

### 1. Clone and setup

```bash
git clone https://github.com/udan-fernando/vestige.git
cd vestige

# Copy the example env file
cp .env.example .env

# Edit .env with credentials (or use defaults for local dev)
```

### 2. Define books to track

Edit `books_config.yaml`:

```yaml
series:
    - name: "The Witcher"
      books:
          - title: "The Last Wish"
            isbn: "9780316452465"
          - title: "Sword of Destiny"
            isbn: "9780316389709"

stores:
    - name: "sarasavi"
      base_url: "https://sarasavi.lk"
    - name: "vijitha_yapa"
      base_url: "https://vijithayapa.com"

notifications:
    email:
        enabled: true
        smtp_host: "smtp.gmail.com"
        smtp_user: "user-email@gmail.com"
        smtp_password: "${SMTP_PASSWORD}"
        notify_to: "recipient@example.com"
    desktop:
        enabled: true # Windows only
```

### 3. Run locally with Docker Compose

```bash
# Builds scraper image and spins up postgres + scraper
docker-compose up --build

# The scraper runs once and exits
# Check postgres for results:
docker-compose exec postgres psql -U postgres -d book_tracker \
  -c "SELECT * FROM availability_snapshots;"

# Stop services
docker-compose down
```

### 4. Deploy to Kubernetes

```bash
# If using minikube locally:
minikube start
eval $(minikube docker-env)  # Use minikube's Docker daemon

# Build image
docker build -t vestige:latest scraper/

# Create namespace
kubectl create namespace book-tracker

# Create secrets (base64-encode your credentials first)
kubectl apply -f k8s/secret.yaml -n book-tracker

# Deploy ConfigMap, PVC, and CronJob
kubectl apply -f k8s/configmap.yaml -n book-tracker
kubectl apply -f k8s/pvc.yaml -n book-tracker
kubectl apply -f k8s/cronjob.yaml -n book-tracker

# Watch CronJob runs
kubectl get cronjob -n book-tracker
kubectl get jobs -n book-tracker --watch
kubectl logs -n book-tracker job/<job-name>
```

---

## How to Add a New Store Scraper

1. Create `scraper/scrapers/new_store.py`:

```python
from scrapers.base import BaseScraper
from models.result import AvailabilityResult
import requests
from bs4 import BeautifulSoup

class NewStoreScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            store_name="New Store",
            base_url="https://newstore.lk"
        )

    def scrape(self, isbn: str, title: str) -> AvailabilityResult:
        url = f"{self.base_url}/search?isbn={isbn}"
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")

        in_stock = self._is_in_stock(soup)

        return AvailabilityResult(
            store=self.store_name,
            isbn=isbn,
            title=title,
            in_stock=in_stock,
            url=url,
            scraped_at=datetime.utcnow()
        )

    def _is_in_stock(self, soup) -> bool:
        # Parse store-specific HTML to detect stock status
        return soup.find("button", {"class": "out-of-stock"}) is None
```

2. Register in `scraper/scrapers/factory.py`:

```python
from scrapers.new_store import NewStoreScraper

ScraperFactory.register("new_store", NewStoreScraper)
```

3. Add to `books_config.yaml` and redeploy.

---

## Configuration Reference

### `books_config.yaml`

```yaml
series:
    - name: string # Series name
      books:
          - title: string # Book title
            isbn: string # ISBN-13 or ISBN-10

stores:
    - name: string # Unique name (used to load scraper)
      base_url: string # Base URL for this store

notifications:
    email:
        enabled: boolean
        smtp_host: string
        smtp_user: string
        smtp_password: string # Can be ${ENV_VAR}
        notify_to: string # Recipient email
    desktop:
        enabled: boolean # Windows only
```

### Environment Variables

See `.env.example` for the full list. Key ones:

```bash
DATABASE_URL=postgresql://user:pass@postgres:5432/book_tracker
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
S3_BUCKET_NAME=your-bucket
SMTP_PASSWORD=your-smtp-password
NOTIFY_EMAIL=recipient@example.com
```

---

## Common Tasks

### View availability history

```sql
SELECT book_id, store_id, in_stock, scraped_at
FROM availability_snapshots
WHERE book_id = 1
ORDER BY scraped_at DESC
LIMIT 10;
```

### Find when a book came into stock

```sql
SELECT
    b.title,
    s.name as store,
    a.scraped_at as came_in_stock
FROM availability_snapshots a
JOIN books b ON a.book_id = b.id
JOIN stores s ON a.store_id = s.id
WHERE b.title = 'The Last Wish'
  AND a.in_stock = TRUE
ORDER BY a.scraped_at ASC
LIMIT 1;
```

### Check S3 logs

```bash
aws s3 ls s3://your-bucket/scrape-runs/
aws s3 cp s3://your-bucket/scrape-runs/2026-04-05T12:00:00Z.json - | jq '.'
```

---

## Contributing

Contributions are welcome. Please open an issue or PR with your proposal.

---

## Troubleshooting

**Scraper fails to scrape a store:**

- Check the store's HTML structure hasn't changed
- Verify headers (User-Agent) aren't being blocked
- Test with `requests.get()` in isolation first

**Database connection refused:**

- If using Docker Compose, wait for postgres health check: `docker-compose logs postgres`
- Verify `DATABASE_URL` matches postgres credentials in `.env`

**S3 upload fails:**

- Verify `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` have S3 permissions
- Check AWS IAM policy allows `s3:PutObject` on the bucket

**Notifications not sending:**

- Check SMTP credentials and `smtp_host` are correct
- Gmail requires app-specific password, not account password
- Verify firewall allows outbound SMTP (port 587 or 465)

**Kubernetes job never runs:**

- Check cron schedule syntax: `kubectl describe cronjob <name> -n book-tracker`
- Verify image exists in your cluster's registry
- Check logs: `kubectl logs -n book-tracker job/<job-name>`

---

## Roadmap

- [ ] Multi-language support (beyond Sri Lankan sites)
- [ ] Web dashboard (React + PostgreSQL)
- [ ] Price tracking alongside availability
- [ ] Telegram notifications
- [ ] GraphQL API for querying history
- [ ] Alerting rules (e.g., "notify only on certain series")

---

## License

MIT

---

## Author

**Udan Fernando**

Vestige demonstrates production DevOps and cloud infrastructure skills: container orchestration with Kubernetes, infrastructure-as-code patterns, cloud service integration (AWS), and operational best practices (logging, configuration management, health checks). Built to showcase real-world deployment patterns in a pragmatic context.
