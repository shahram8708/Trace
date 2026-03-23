# Trace

**Trace is a web application that helps you permanently retain what you read by automatically extracting key concepts from articles, books, and PDFs, then scheduling them for daily spaced-repetition review sessions using the SM-2 algorithm — powered by Google Gemini AI.**

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)
![Flask](https://img.shields.io/badge/Flask-3.0%2B-lightgrey?logo=flask)
![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL%20%7C%20SQLite-336791?logo=postgresql)
![Celery](https://img.shields.io/badge/Queue-Celery%205.3%2B-brightgreen?logo=celery)
![Redis](https://img.shields.io/badge/Cache-Redis%206%2B-red?logo=redis)
![Razorpay](https://img.shields.io/badge/Payments-Razorpay-blue)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Screenshots / Demo

*(Add screenshots of your application here — include the homepage, the dashboard, and a review session.)*

Based on the templates in the codebase, here's what each key screen looks like:

- **Homepage (`/`)** — A marketing landing page with a hero section explaining the spaced-repetition concept, a "How It Works" section, pricing tiers (Free vs Pro), and calls to action for signup.
- **Dashboard (`/dashboard`)** — Shows today's due concepts count, overall retention score (0–100%), streak counter, a 7-day review activity bar chart, and a domain-by-domain retention breakdown.
- **Review Session (`/review/session`)** — A full-screen flashcard interface. One concept at a time is shown, the user writes their recall response, then rates their recall quality (1–5). The SM-2 algorithm immediately schedules the next review.
- **Knowledge Map (`/map`)** — An interactive force-directed graph (D3.js) showing every concept as a node and AI-suggested connections as edges. Nodes are coloured by retention strength and sized by review count.
- **Import Hub (`/import`)** — Four import methods in one place: URL, plain text, PDF upload, and Kindle CSV export.

---

## Table of Contents

- [The Problem This Solves](#the-problem-this-solves)
- [Features](#features)
- [Technology Stack](#technology-stack)
- [Architecture Overview](#architecture-overview)
- [Database Schema](#database-schema)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Environment Variables](#environment-variables-configuration)
- [Running the Application](#running-the-application)
- [Usage Guide](#usage-guide)
- [API Documentation](#api-documentation)
- [Running Tests](#running-tests)
- [Deployment](#deployment)
- [Configuration Reference](#configuration-reference)
- [Contributing](#contributing)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)
- [Security](#security)
- [License](#license)
- [Acknowledgments](#acknowledgments)
- [Contact and Support](#contact-and-support)

---

## The Problem This Solves

You read a great article on mental models. You finish a book on systems thinking. You skim three research summaries before a big meeting. And within a week — sometimes within a day — almost all of it is gone. Not forgotten in a dramatic, obvious way. Just quietly unavailable when you need it. You remember that you read *something* about feedback loops, but you can't reconstruct the actual insight.

This is the forgetting curve, and it's brutal. Hermann Ebbinghaus mapped it in 1885 and nothing has fundamentally changed: without deliberate reinforcement, we lose the majority of new information within 24 to 48 hours. The people who seem to remember everything they read aren't smarter — they have a system.

The problem with most "note-taking" solutions is that they're write-only. You save something to Notion, Obsidian, or a bookmark folder, and it sits there forever, never surfacing again. Even if your notes are beautifully organised, you're not actually practising retrieval — which is the only thing that builds durable memory. Flashcard apps like Anki get the science right, but they put all the friction on you: you have to extract the concepts yourself, format them into cards, and maintain a growing deck across dozens of topics.

Trace was built to collapse that friction. You paste a URL, upload a PDF, or paste text, and Gemini AI automatically identifies 3–8 transferable, standalone concepts — not summaries, but actual frameworks and principles you can apply. Those concepts enter your personal review queue, and Trace schedules each one using the SM-2 spaced-repetition algorithm: the same algorithm that powers Anki, but running automatically in the background. You open Trace in the morning, spend 5–10 minutes on your daily review, and over months your knowledge compounds in a way that passive reading never could.

---

## Features

### 🧠 Core Spaced-Repetition Engine

- **SM-2 Algorithm Implementation** — The same algorithm used by Anki and SuperMemo. After each review, the ease factor and interval are updated based on your recall quality (rated 1–5). Concepts you know well get pushed further out; ones you struggle with come back the next day.
- **Retention Strength Score** — Each concept has a real-time retention score (0–100%) calculated from an exponential decay model using the days since last review and the current interval. Displayed as a colour-coded badge (green/yellow/red).
- **Session Queue Builder** — Every review session combines overdue concepts (ordered oldest-first) with up to 5 new, never-reviewed concepts. No manual deck management.
- **Mature Concept Tracking** — Concepts with an interval exceeding 21 days are marked "mature," indicating they've been durably encoded.
- **Overdue Concepts View** — A dedicated `/review/overdue` page lists all concepts past their due date so nothing falls through the cracks.
- **Daily Review Streak** — A streak counter tracks consecutive days with at least one review completed. Longest streak is also stored. A "streak at risk" flag is set if you haven't reviewed in two days, giving reminder emails a trigger.

### 📥 Import Methods

- **URL Import** — Paste any article URL and Trace uses `trafilatura` to extract the clean article text, stripping ads, navigation, and boilerplate. Includes URL safety validation before fetching.
- **Plain Text Import** — Paste any text directly. Useful for book passages, meeting notes, lecture transcripts, or anything you've already copied.
- **PDF Upload** — Upload a PDF up to a configurable size limit (default 10 MB). Text is extracted using `pdfplumber`. Password-protected or image-only PDFs are handled gracefully with error messaging.
- **Kindle CSV Import** — Upload a Kindle highlights export (`.csv`). The importer parses the CSV, groups highlights by book title, and builds a consolidated source text for each book.

### 🤖 AI Extraction (Google Gemini)

- **Automatic Concept Extraction** — After any import, Gemini 2.5 Flash analyses the source text and identifies 3–8 standalone, transferable concepts — frameworks, principles, mental models, and actionable distinctions. Not summaries. Each concept has a name (3–7 words), a description (1–3 sentences), and a verbatim source excerpt.
- **Async Processing via Celery** — Extraction runs in a background Celery task, not during the HTTP request. A polling endpoint (`/import/status/<id>`) lets the browser check extraction status without blocking.
- **AI-Suggested Concept Connections** — Gemini also analyses your entire concept library and proposes relationships between concepts: "builds on," "contradicts," "applies to," "example of," or "related to." You can accept or dismiss each suggestion.
- **Free Tier Extraction Limit** — Free users get a configurable number of AI extractions per month (default 5, set via `DAILY_AI_EXTRACTIONS_FREE`). Premium users have no limit.

### 🗺️ Knowledge Map (Premium)

- **Interactive Force-Directed Graph** — A D3.js-powered visualisation of your entire concept library as a network. Nodes represent concepts; edges represent connections. Coloured by domain tag.
- **Retention-Aware Node Sizing** — Nodes are sized by total review count and coloured by retention strength. Concepts you know well glow; concepts you've neglected fade.
- **Manual Connection Creation** — In addition to AI suggestions, you can manually draw a connection between any two concepts and label it with a relationship type.
- **Connection Accept/Dismiss** — AI-suggested connections appear in a panel. Accept adds the edge to the graph; dismiss removes it from future suggestions.
- **Graph Truncation** — For very large libraries (500+ concepts), the graph renders the 500 most-reviewed concepts to maintain performance.

### 📊 Reports & Analytics

- **Weekly Report Email** — A Celery Beat scheduled task sends a weekly HTML email with: total reviews this week vs last week, domain-by-domain retention changes, overall retention score, and streak status.
- **Reports Dashboard (`/reports`)** — An in-app version of the weekly summary. Shows a bar chart of reviews per day over the past 7 days, domain retention breakdown, and concept maturity statistics.
- **Review History (`/review/history`)** — Full paginated log of every review event: when you reviewed it, what quality you rated it, your written response, and the new interval that was scheduled.
- **Domain Retention Summary** — On both the review hub and dashboard, a breakdown of average retention by domain tag shows you which subjects are fading fastest.

### 📚 Library & Concept Management

- **Source Library (`/library`)** — Every imported source (URL, text, PDF, Kindle book) is stored with its title, type, author, word count, and concept count. Filterable and searchable.
- **Concept Library (`/concepts`)** — Your full concept library, paginated (24 per page). Filterable by domain, sortable by name, date added, retention strength, or overdue status. Searchable by name and description.
- **Concept Detail View** — Each concept has a detail page showing its full description, source excerpt, SM-2 parameters (ease factor, interval, repetitions), review history, retention chart, and any connections to other concepts.
- **Manual Concept Editing** — Edit any concept's name, description, source excerpt, and domain tag. Useful when AI extraction needs a small correction.
- **Concept Deactivation** — Concepts can be "archived" (set `is_active = False`) rather than deleted, preserving your review history.
- **Projects (`/projects`)** — Group concepts under a named project (e.g., "Q3 OKR Planning," "Reading: Deep Work"). Projects have domain tags and a configurable reminder frequency.

### 🔔 Notifications & Email

- **Email Verification** — All new accounts require email verification using `itsdangerous` tokens that expire in 24 hours. Resend functionality included.
- **Password Reset** — Token-based password reset flow with a 1-hour expiry.
- **Review Reminder Emails** — Celery Beat sends a daily email to users who have due concepts and have set a preferred reminder time, but haven't yet reviewed today.
- **Application Reminder Emails** — When a concept is linked to a project, periodic "application prompts" ask whether you've had a chance to apply the concept in that context.
- **Weekly Report Emails** — Automated weekly HTML digest of your learning progress.
- **Subscription Emails** — Confirmation on subscription activation, cancellation notice on cancellation, and payment failure alerts.
- **Account Deletion Email** — Sent when a user requests account deletion.

### 💳 Billing & Subscriptions (Razorpay)

- **Free Tier** — 50 concepts, 5 imports/month, 5 AI extractions/month.
- **Pro Monthly & Annual Plans** — Unlimited concepts, unlimited imports, unlimited AI extractions, plus access to the Knowledge Map. Billed in INR via Razorpay subscriptions (₹999/month or ₹8,999/year based on admin panel MRR calculations).
- **Razorpay Webhook Handler** — `POST /billing/webhook` processes `payment.captured`, `subscription.charged`, `subscription.cancelled`, and `payment.failed` events.
- **Subscription Cancellation & Reactivation** — Users can cancel their subscription (access revoked immediately) or reactivate it from the billing settings page.

### 👤 User Account & Profile

- **3-Step Onboarding** — After signup and verification, new users go through: (1) setting their name and domains of interest, (2) choosing preferred content types, and (3) a quick tour.
- **Settings Page** — Update name, email, password.
- **Notification Preferences** — Toggle review reminders, weekly reports, and application reminders independently.
- **Review Reminder Time** — Set a preferred time of day for review reminder emails.
- **Integrations Page** — A waitlist/placeholder page for future integrations (Kindle, Readwise, Pocket, etc.).
- **Account Deletion** — Self-serve account deletion with a confirmation step. Sends a goodbye email and cascades deletion to all user data.
- **Data Export** — Download all your concepts and review history as a JSON or CSV file.

### 🔧 Admin Panel

- **Admin Dashboard (`/admin`)** — Total users, verified users, premium users, monthly/annual breakdown, MRR estimate, total concepts, total reviews, reviews this week, new signups this week, failed AI extractions, and live Celery queue depth.
- **User Management (`/admin/users`)** — Search users by email or name, filter by tier (free/monthly/annual), sort by signup date/last login/concept count. Paginated.
- **User Detail View (`/admin/users/<id>`)** — Full profile of any user: subscription history, concepts, recent reviews. Admin can manually verify or toggle premium status.
- **Blog Editor (`/admin/blog`)** — Create and publish Markdown blog posts with a slug, meta description, cover image, and published-at timestamp. Rendered on the public blog at `/blog`.

### Create an Admin Account

You need an admin account for later testing. In your terminal (with virtual environment active), open the Flask shell:

```
flask shell
```

In the Flask shell, type:
```python
from app.models.user import User
from app.extensions import db
from werkzeug.security import generate_password_hash

admin = User(
    email='admin@traceyourknowledge.com',
    password_hash=generate_password_hash('AdminPass123!'),
    first_name='Admin',
    is_verified=True,
    is_admin=True,
    is_premium=True,
    subscription_tier='monthly',
    onboarding_complete=True
)
db.session.add(admin)
db.session.commit()
print("Admin created successfully!")
```

Type `exit()` to leave Flask shell.

Log in with admin account to verify:
- Email: `admin@traceyourknowledge.com`
- Password: `AdminPass123!`

Expected: Logged in and redirected to /dashboard (onboarding already complete)

Log out and log back in with the regular test account:
- Email: `priya.testuser@gmail.com`
- Password: `TestPass123!`

---

## Technology Stack

### Backend

| Technology | Role |
|---|---|
| **Python 3.10+** | Primary language |
| **Flask ≥3.0.0** | Web framework; application factory pattern with blueprints |
| **Flask-SQLAlchemy ≥3.1.0** | ORM on top of SQLAlchemy 2.0 |
| **Flask-Migrate ≥4.0.0** | Alembic-powered database migrations |
| **Flask-Login ≥0.6.0** | Session management and `@login_required` decorator |
| **Flask-WTF ≥1.2.0** | WTForms integration and CSRF protection |
| **Flask-Mail ≥0.10.0** | Transactional email sending |
| **Flask-Limiter ≥3.5.0** | Rate limiting (200/day, 50/hour global; tighter limits on auth routes) |
| **Flask-Caching ≥2.1.0** | Response and query caching layer |
| **Werkzeug ≥3.0.0** | WSGI utilities, password hashing via PBKDF2:SHA256 |
| **itsdangerous ≥2.1.0** | Signed tokens for email verification and password reset |
| **Gunicorn ≥21.0.0** | Production WSGI server |
| **psycopg2-binary ≥2.9.0** | PostgreSQL adapter |
| **Celery ≥5.3.0** | Distributed task queue for AI extraction and scheduled emails |
| **Redis ≥5.0.0** | Celery broker and result backend in production |

### AI / Machine Learning

| Technology | Role |
|---|---|
| **google-genai ≥1.0.0** | Official Google Generative AI SDK |
| **Gemini 2.5 Flash** | Model used for concept extraction and connection suggestion |
| **SM-2 Algorithm** | Spaced repetition scheduling (custom Python implementation in `sm2_engine.py`) |

### Content Processing

| Technology | Role |
|---|---|
| **trafilatura ≥1.6.0** | Web article extraction — strips ads, nav, and boilerplate from URLs |
| **pdfplumber ≥0.11.0** | PDF text extraction |
| **python-magic ≥0.4.27** | MIME type validation for uploaded files |
| **Pillow ≥10.0.0** | Image processing (cover image handling) |

### Frontend

| Technology | Role |
|---|---|
| **Bootstrap 5** (CDN) | CSS framework and component library |
| **D3.js** | Force-directed knowledge map visualisation |
| **Chart.js** | Bar charts on dashboard and review hub |
| **Jinja2** | Server-side HTML templating (bundled with Flask) |
| **Markdown ≥3.5.0 + Pygments ≥2.17.0** | Server-side Markdown rendering with syntax highlighting for concept descriptions |

### Payments

| Technology | Role |
|---|---|
| **Razorpay ≥1.4.0** | Indian payment gateway for subscriptions (INR billing) |

### DevOps

| Technology | Role |
|---|---|
| **Gunicorn** | Production WSGI server |
| **Nginx** | Reverse proxy for static files and SSL termination |
| **systemd** | Process supervision for Gunicorn, Celery worker, and Celery beat |
| **Flower ≥2.0.0** | Celery task monitoring UI |

---

## Architecture Overview

Trace is a Flask application structured using the **application factory pattern** with Blueprints. The `create_app()` function in `trace/app/__init__.py` assembles the app from 13 blueprints, each responsible for a distinct feature domain: `auth`, `dashboard`, `import_bp`, `review`, `concepts`, `library`, `map`, `projects`, `reports`, `billing`, `profile`, `onboarding`, `admin`, and `main`.

Request handling follows a straightforward path: Nginx accepts incoming HTTP connections and proxies them to Gunicorn (running on port 8000), which dispatches to Flask. Flask routes the request through the appropriate Blueprint, which queries the PostgreSQL database via SQLAlchemy ORM models, renders a Jinja2 template, and returns HTML. API endpoints (for the review session, import status polling, and billing) return JSON instead.

Computationally expensive work is handled **asynchronously**. When a user imports content, the route handler creates a `SourceItem` record and an `AIExtractionQueue` entry, then fires a Celery task (`process_ai_extraction_async`) to the Redis broker and returns immediately. The browser polls `/import/status/<id>` every few seconds until the task completes. Celery Beat also runs three scheduled tasks: daily review reminder emails, daily application reminders, and weekly report emails.

The services layer (`trace/app/services/`) contains all business logic: `sm2_engine.py` for the spaced repetition algorithm, `ai_extractor.py` and `gemini_parser.py` for Gemini API calls, `razorpay_service.py` for billing, `email_service.py` for transactional mail, and `report_generator.py` for weekly analytics. Routes are kept thin — they handle HTTP concerns (form validation, authentication checks, redirects) and delegate to services.

```
Trace-main/
├── run.py                          # Dev entry point — loads .env, runs migrations, starts Flask
├── celery_worker.py                # Celery app factory and Beat schedule
├── requirements.txt                # All Python dependencies
├── .env.example                    # Required environment variables (copy to .env)
├── deploy/
│   ├── gunicorn.service            # systemd unit for Gunicorn
│   ├── celery-worker.service       # systemd unit for Celery worker
│   ├── celery-beat.service         # systemd unit for Celery beat scheduler
│   ├── nginx.conf                  # Nginx reverse proxy config
│   └── README.md                   # Deployment instructions
└── trace/
    └── app/
        ├── __init__.py             # Application factory (create_app)
        ├── config.py               # DevelopmentConfig, ProductionConfig, TestingConfig
        ├── extensions.py           # Flask extension instances (db, mail, limiter, etc.)
        ├── tasks.py                # Celery task definitions
        ├── models/                 # SQLAlchemy ORM models
        │   ├── user.py
        │   ├── concept.py
        │   ├── source_item.py
        │   ├── review_event.py
        │   ├── connection.py
        │   ├── project.py
        │   ├── application_event.py
        │   ├── ai_extraction_queue.py
        │   └── blog_post.py
        ├── routes/                 # Blueprint route handlers (thin)
        ├── services/               # Business logic (thick)
        │   ├── sm2_engine.py       # SM-2 spaced repetition algorithm
        │   ├── ai_extractor.py     # Gemini concept extraction + connection suggestion
        │   ├── razorpay_service.py # Subscription billing
        │   ├── email_service.py    # Transactional emails
        │   ├── report_generator.py # Weekly analytics
        │   ├── streak_manager.py   # Daily review streak tracking
        │   ├── connection_suggester.py  # Concept connection suggestions
        │   ├── content_fetcher.py  # URL article extraction
        │   ├── pdf_processor.py    # PDF text extraction
        │   └── kindle_importer.py  # Kindle CSV parsing
        ├── utils/
        │   ├── free_tier.py        # Free tier limit checks
        │   ├── decorators.py       # @premium_required, @admin_required, @onboarding_required
        │   ├── tokens.py           # itsdangerous token generation/validation
        │   ├── gemini_parser.py    # Gemini response parsing with retry logic
        │   └── markdown_renderer.py # Server-side Markdown to HTML
        ├── templates/              # Jinja2 HTML templates
        └── static/                 # CSS, JS, and images
```

---

## Database Schema

### User

The central entity. Represents a registered account. Stores authentication credentials, subscription state, onboarding status, review streak, and notification preferences.

| Column | Type | Description | Constraints |
|---|---|---|---|
| `id` | Integer | Primary key | PK |
| `email` | String(255) | Login email, normalised to lowercase | Unique, Not null, Indexed |
| `password_hash` | String(255) | PBKDF2:SHA256 hash | Not null |
| `first_name` | String(100) | Display name | Optional |
| `created_at` | DateTime | Account creation timestamp | Not null |
| `last_login` | DateTime | Last successful login | Optional |
| `is_verified` | Boolean | Email verified | Default false |
| `is_premium` | Boolean | Has active subscription | Default false |
| `subscription_tier` | String(50) | `free`, `monthly`, or `annual` | Default "free" |
| `subscription_expires` | DateTime | When premium access expires | Optional |
| `razorpay_customer_id` | String(100) | Razorpay customer ID | Optional |
| `razorpay_subscription_id` | String(100) | Active Razorpay subscription ID | Optional |
| `onboarding_complete` | Boolean | Has completed 3-step onboarding | Default false |
| `domains_of_interest` | JSON | Array of domain strings from onboarding | Optional |
| `notifications_preferences` | JSON | Dict of notification toggles | Default `{}` |
| `current_streak_days` | Integer | Active daily review streak | Default 0 |
| `longest_streak_days` | Integer | All-time best streak | Default 0 |
| `total_reviews_completed` | Integer | Lifetime review count | Default 0 |
| `is_admin` | Boolean | Admin panel access | Default false |

### Concept

A single learnable unit extracted from a source. Stores SM-2 state and retention metrics.

| Column | Type | Description | Constraints |
|---|---|---|---|
| `id` | Integer | Primary key | PK |
| `user_id` | Integer | Owning user | FK → users.id, CASCADE |
| `source_item_id` | Integer | Source this came from | FK → source_items.id, SET NULL |
| `name` | String(300) | Short concept name (3–7 words) | Not null |
| `description` | Text | 1–3 sentence explanation | Not null |
| `source_excerpt` | Text | Verbatim passage from source | Optional |
| `domain_tag` | String(100) | Categorical domain label | Optional |
| `next_review_due` | Date | Next scheduled review date | Optional |
| `sm2_ease_factor` | Float | SM-2 ease factor (min 1.3) | Default 2.5 |
| `sm2_interval` | Integer | Current interval in days | Default 1 |
| `sm2_repetitions` | Integer | Successful review streak | Default 0 |
| `retention_strength` | Float | Exponential decay score 0.0–1.0 | Default 0.0 |
| `total_reviews` | Integer | Lifetime review count | Default 0 |
| `is_active` | Boolean | Soft-delete flag | Default true |
| `is_mature` | Boolean | Interval > 21 days | Default false |

### SourceItem

A piece of content the user imported (article, text, PDF, or Kindle book).

| Column | Type | Description | Constraints |
|---|---|---|---|
| `id` | Integer | Primary key | PK |
| `user_id` | Integer | Owning user | FK → users.id, CASCADE |
| `title` | String(500) | Article/book title | Optional |
| `source_url` | String(2000) | Original URL (for URL imports) | Optional |
| `source_type` | String(50) | `url`, `text`, `pdf`, `kindle` | Not null |
| `full_text` | Text | Extracted plain text content | Optional |
| `domain_tags` | JSON | Array of domain strings | Optional |
| `is_processed` | Boolean | AI extraction completed | Default false |
| `concept_count` | Integer | Number of extracted concepts | Default 0 |
| `author` | String(300) | Author if available | Optional |
| `word_count` | Integer | Extracted text word count | Default 0 |

### ReviewEvent

A single review action — one concept reviewed in one session.

| Column | Type | Description | Constraints |
|---|---|---|---|
| `id` | Integer | Primary key | PK |
| `user_id` | Integer | Reviewing user | FK → users.id, CASCADE |
| `concept_id` | Integer | Concept that was reviewed | FK → concepts.id, CASCADE |
| `reviewed_at` | DateTime | Timestamp of review | Default now |
| `quality_rating` | Integer | User's recall rating (1–5) | Not null |
| `user_response_text` | Text | What the user typed as their recall | Optional |
| `previous_interval` | Integer | Interval before this review | Optional |
| `new_interval` | Integer | Interval after this review | Optional |
| `session_id` | String(50) | Groups reviews within a session | Optional |

### ConceptConnection

A directed relationship between two concepts, either AI-suggested or manually created.

| Column | Type | Description | Constraints |
|---|---|---|---|
| `id` | Integer | Primary key | PK |
| `user_id` | Integer | Owning user | FK → users.id, CASCADE |
| `concept_a_id` | Integer | Source concept | FK → concepts.id, CASCADE |
| `concept_b_id` | Integer | Target concept | FK → concepts.id, CASCADE |
| `relationship_type` | String(100) | One of: builds on, contradicts, applies to, example of, related to | Not null |
| `connection_source` | String(50) | `ai` or `manual` | Not null |
| `is_active` | Boolean | Soft-delete | Default true |

**Unique constraint:** `(user_id, concept_a_id, concept_b_id)` — prevents duplicate connections.

### Project

A named goal or context for tracking concept application.

| Column | Type | Description | Constraints |
|---|---|---|---|
| `id` | Integer | Primary key | PK |
| `user_id` | Integer | Owning user | FK → users.id, CASCADE |
| `name` | String(300) | Project name | Not null |
| `description` | Text | What the project is about | Optional |
| `domain_tags` | JSON | Related domain tags | Optional |
| `reminder_frequency` | String(50) | `weekly` or `daily` | Default "weekly" |

### ApplicationEvent

Tracks whether a user has applied a concept within a project context.

| Column | Type | Description | Constraints |
|---|---|---|---|
| `id` | Integer | Primary key | PK |
| `user_id` | Integer | FK → users.id, CASCADE | Not null |
| `concept_id` | Integer | FK → concepts.id, CASCADE | Not null |
| `project_id` | Integer | FK → projects.id, CASCADE | Not null |
| `prompt_text` | Text | AI-generated "have you applied this?" question | Optional |
| `user_response` | String(50) | `applied`, `not_yet`, or null (pending) | Optional |

### AIExtractionQueue

Tracks the status of background AI extraction tasks.

| Column | Type | Description | Constraints |
|---|---|---|---|
| `id` | Integer | Primary key | PK |
| `source_item_id` | Integer | FK → source_items.id, CASCADE | Not null |
| `status` | String(50) | `pending`, `processing`, `completed`, `failed` | Default "pending" |
| `extracted_concepts_json` | JSON | Array of extracted concept dicts | Optional |
| `model_used` | String(100) | Which Gemini model was used | Default "gemini-2.5-flash" |
| `error_message` | Text | Error details on failure | Optional |

### BlogPost

Admin-managed blog content displayed on the public-facing website.

| Column | Type | Description | Constraints |
|---|---|---|---|
| `id` | Integer | Primary key | PK |
| `title` | String(500) | Post title | Not null |
| `slug` | String(500) | URL-safe identifier | Unique, Not null |
| `content` | Text | Markdown body | Not null |
| `is_published` | Boolean | Visible to public | Default false |
| `author` | String(200) | Byline | Default "Trace Team" |

**Relationships:** Users have many Concepts (cascade delete), many SourceItems (cascade delete), many ReviewEvents (cascade delete), many Projects (cascade delete), and many ConceptConnections (cascade delete). Concepts belong to one User and optionally one SourceItem (SET NULL on delete). ReviewEvents belong to one User and one Concept (both cascade delete). ConceptConnections belong to one User and two Concepts.

---

## Getting Started

### Prerequisites

Before you start, make sure you have everything below installed and configured.

**Runtime:**
- **Python 3.10 or higher** — Run `python --version` to check. Expected: `Python 3.10.x` or higher.
- **pip** — Comes with Python. Check with `pip --version`.

**Database (choose one):**
- **SQLite** — Works out of the box for local development. No setup needed.
- **PostgreSQL 14+** — Required for production. Check with `psql --version`.

**Task Queue (optional for local dev, required for production):**
- **Redis 6.0+** — For Celery. In development, Celery runs in "eager" mode (tasks execute inline, no Redis needed). Check with `redis-cli ping`.

**External accounts (required for full functionality):**
- **Google Cloud account** — For the Gemini API. You'll need to enable the Generative Language API and create an API key at [aistudio.google.com](https://aistudio.google.com/app/apikey).
- **Email account or SMTP service** — For transactional emails (Mailtrap, SendGrid, or your own SMTP). Required for email verification to work.
- **Razorpay account** — For billing. Required only if you're enabling subscriptions. Create test/live keys at [razorpay.com](https://razorpay.com).

**System library:**
- **libmagic** — Required by `python-magic` for MIME type detection of uploaded files.
  - Ubuntu/Debian: `sudo apt-get install libmagic1`
  - macOS: `brew install libmagic`

---

### Installation

Follow these steps exactly. Don't skip any.

**Step 1 — Clone the repository:**
```bash
git clone https://github.com/shahram8708/trace.git
cd trace
```

**Step 2 — Create a virtual environment:**
```bash
# macOS / Linux
python3 -m venv venv

# Windows
python -m venv venv
```

**Step 3 — Activate the virtual environment:**
```bash
# macOS / Linux
source venv/bin/activate

# Windows (Command Prompt)
venv\Scripts\activate.bat

# Windows (PowerShell)
venv\Scripts\Activate.ps1
```

**Step 4 — Install all Python dependencies:**
```bash
pip install -r requirements.txt
```

**Step 5 — Copy the example environment file:**
```bash
# macOS / Linux
cp .env.example .env

# Windows
copy .env.example .env
```

**Step 6 — Edit your `.env` file** (see the [Environment Variables](#environment-variables-configuration) section below for what each one means).

At minimum, set `SECRET_KEY`, `GOOGLE_API_KEY`, and optionally `DATABASE_URL`. The app will run with SQLite if `DATABASE_URL` is not set.

**Step 7 — Initialise the database:**

For a fresh install (no `migrations/` folder yet):
```bash
flask --app run:create_app db init
flask --app run:create_app db migrate -m "Initial schema"
flask --app run:create_app db upgrade
```

Or just run the development server — `run.py` calls `db.create_all()` automatically as a fallback if no migrations directory exists:
```bash
python run.py
```

**Step 8 — Start the development server:**
```bash
python run.py
```

Open your browser to `http://localhost:5000`. You should see the Trace marketing homepage with a "Get Started" button. Click it to create an account.

> **Note on email verification:** In development, if you don't have SMTP configured, the verification email won't send. Check your Flask logs — the verification URL is printed there so you can paste it directly into your browser.

---

### Environment Variables Configuration

Copy `.env.example` to `.env` and fill in the following:

#### Application

| Variable | Required | Description | Example |
|---|---|---|---|
| `FLASK_ENV` | Optional | `development` or `production` | `development` |
| `FLASK_DEBUG` | Optional | `1` for debug mode, `0` for off | `1` |
| `SECRET_KEY` | **Required** | Random string for session signing and CSRF. Generate with `python -c "import secrets; print(secrets.token_hex(32))"` | `a8f3d2e1b4c7...` |
| `BASE_URL` | Optional | Full base URL of your deployment (used in emails) | `https://trace.yourdomain.com` |

#### Database

| Variable | Required | Description | Example |
|---|---|---|---|
| `DATABASE_URL` | Optional | PostgreSQL or SQLite URL. Defaults to `sqlite:///trace_dev.db` if not set. | `postgresql://user:pass@localhost/trace` |

#### Background Tasks

| Variable | Required (prod) | Description | Example |
|---|---|---|---|
| `REDIS_URL` | Required in prod | Redis connection URL for Celery. Not needed in dev (uses in-memory). | `redis://localhost:6379/0` |

#### AI (Google Gemini)

| Variable | Required | Description | How to get it |
|---|---|---|---|
| `GOOGLE_API_KEY` | **Required** | Google Gemini API key | [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) |

#### Email (SMTP)

| Variable | Required | Description | Example |
|---|---|---|---|
| `MAIL_SERVER` | **Required** | SMTP server hostname | `smtp.mailtrap.io` |
| `MAIL_PORT` | **Required** | SMTP port | `587` |
| `MAIL_USE_TLS` | **Required** | Enable TLS (`1` or `0`) | `1` |
| `MAIL_USERNAME` | **Required** | SMTP username | `your-smtp-user` |
| `MAIL_PASSWORD` | **Required** | SMTP password | `your-smtp-password` |
| `MAIL_DEFAULT_SENDER` | **Required** | From address for outgoing mail | `hello@trace.app` |

#### Payments (Razorpay)

| Variable | Required | Description | How to get it |
|---|---|---|---|
| `RAZORPAY_KEY_ID` | Required for billing | Public key ID | Razorpay Dashboard → Settings → API Keys |
| `RAZORPAY_KEY_SECRET` | Required for billing | Secret key | Same as above |
| `RAZORPAY_WEBHOOK_SECRET` | Required for billing | Webhook signing secret | Razorpay Dashboard → Webhooks |

#### Free Tier Limits

| Variable | Optional | Description | Default |
|---|---|---|---|
| `FREE_CONCEPT_LIMIT` | Optional | Max active concepts for free users | `50` |
| `DAILY_AI_EXTRACTIONS_FREE` | Optional | Max AI extractions per month for free users | `5` |
| `MAX_PDF_SIZE_MB` | Optional | Max PDF upload size in MB | `10` |

---

## Running the Application

### Development Mode

The app needs just one process in development (Celery tasks run inline/eagerly):

```bash
# Terminal 1 — Flask development server
python run.py
```

The server starts at `http://localhost:5000` with auto-reload disabled (set in `run.py` — enable with `use_reloader=True` if you prefer). Debug mode is controlled by `FLASK_DEBUG` in your `.env`.

### Production Mode (Multiple Processes)

In production you need three separate processes. Run each in its own terminal or, better, as systemd services using the files in `deploy/`:

```bash
# Terminal 1 — Gunicorn WSGI server (4 workers)
gunicorn -w 4 -b 127.0.0.1:8000 "run:create_app()"

# Terminal 2 — Celery worker (processes AI extraction tasks)
celery -A celery_worker.celery worker --loglevel=info

# Terminal 3 — Celery beat (scheduled tasks: reminders, weekly reports)
celery -A celery_worker.celery beat --loglevel=info
```

### Running with systemd (Recommended for Linux Production)

The `deploy/` folder contains ready-to-use systemd unit files:

```bash
sudo cp deploy/gunicorn.service /etc/systemd/system/
sudo cp deploy/celery-worker.service /etc/systemd/system/
sudo cp deploy/celery-beat.service /etc/systemd/system/

# Update WorkingDirectory, EnvironmentFile, and User in each file to match your server
sudo systemctl daemon-reload
sudo systemctl enable --now gunicorn.service
sudo systemctl enable --now celery-worker.service
sudo systemctl enable --now celery-beat.service
```

Check logs with:
```bash
journalctl -u gunicorn.service -f
journalctl -u celery-worker.service -f
```

---

## Usage Guide

### Creating an Account and Getting Started

1. Go to `http://localhost:5000` and click **Get Started** or navigate to `/signup`.
2. Enter your email, first name, and a password. Click **Create account**.
3. Check your email for a verification link. Click it (or copy the URL from Flask logs in dev).
4. You'll be redirected to `/login`. Sign in.
5. Complete the 3-step onboarding: enter your name, select your domains of interest (e.g., "Psychology," "Business," "Technology"), and choose your preferred content types.

### Importing Content

Go to `/import` or click **Import** in the navigation.

**From a URL:**
1. Click **Import from URL**.
2. Paste the full URL of an article (e.g., `https://fs.blog/mental-models/`).
3. Click **Fetch & Extract**. Trace fetches the article text and queues an AI extraction job.
4. You'll be redirected to a processing screen that polls for completion.
5. When done, you'll see the extracted concepts. Review each one — you can edit the name, description, or remove ones that aren't useful — then click **Save to Library**.

**From PDF:**
1. Click **Import PDF**.
2. Upload a `.pdf` file (up to the configured size limit).
3. The same AI extraction flow runs.

**From Kindle:**
1. On your Kindle, go to **My Clippings** and export it, or use [Kindle Export](https://read.amazon.com/kp/notebook) to get a CSV of your highlights.
2. Upload the CSV at `/import/kindle`.
3. Highlights are grouped by book title. Select which books to import.

**From plain text:**
1. Click **Import Text**.
2. Paste any text — a book passage, meeting notes, a research abstract.
3. Give it a title, hit **Extract Concepts**.

### Running a Review Session

1. Go to `/review` (the review hub). You'll see how many concepts are due today, your current streak, and recent activity.
2. If concepts are due, click **Start Session**.
3. For each concept:
   - Read the concept name and try to recall the full description in your head (or type it out in the response box).
   - Click **Reveal** to see the full description and your source excerpt.
   - Rate your recall from 1 (complete blank) to 5 (perfect, effortless recall).
   - The SM-2 algorithm calculates when you'll see this concept next.
4. When the queue is empty, you see a completion screen with your session stats and updated streak.

### Exploring the Knowledge Map

Go to `/map` (requires Pro subscription). The force-directed graph shows all your active concepts. Nodes are coloured by domain and sized by review count. Concepts you know well (high retention) appear brighter.

- **Zoom and pan** with mouse wheel and drag.
- **Click a node** to see the concept's name, description, and retention score in a side panel.
- **Accept or dismiss** AI-suggested connections that appear in the suggestions panel on the right.
- **Draw manual connections** by holding Shift and dragging between two nodes.

### Setting up Projects

Go to `/projects/new` to create a project. Give it a name (e.g., "Applying: Thinking Fast and Slow to Product Decisions") and optional domain tags. Once created, you can link individual concepts to the project from their detail pages. Trace will periodically prompt you to reflect on whether you've applied each concept in that context.

---

## API Documentation

The following endpoints accept and return JSON (used by the frontend JavaScript):

### `GET /import/status/<source_item_id>`
Polls the AI extraction status for a given source item.

**Authentication:** Required (session cookie)

**Response:**
```json
{
  "status": "completed",
  "concepts": [
    {
      "name": "Desirable Difficulty",
      "description": "Introducing manageable challenges during learning improves long-term retention.",
      "source_excerpt": "When learning feels difficult, deep processing is occurring."
    }
  ]
}
```
Status values: `pending`, `processing`, `completed`, `failed`

---

### `POST /review/submit`
Submits a quality rating for a single concept review.

**Authentication:** Required

**Request body:**
```json
{
  "concept_id": 42,
  "quality_rating": 4,
  "user_response_text": "Spacing effect improves long-term retention...",
  "session_id": "abc123def456"
}
```

**Response:**
```json
{
  "success": true,
  "next_review_date": "2026-04-01",
  "interval_label": "In 9 days",
  "new_interval": 9
}
```

---

### `POST /billing/create-order`
Creates a Razorpay subscription order.

**Authentication:** Required, email must be verified

**Request body:**
```json
{ "plan_type": "monthly" }
```

**Response:**
```json
{
  "success": true,
  "key_id": "rzp_live_xxx",
  "subscription_id": "sub_xxx"
}
```

---

### `POST /billing/verify-payment`
Verifies Razorpay payment signature and activates the subscription.

**Request body:**
```json
{
  "razorpay_payment_id": "pay_xxx",
  "razorpay_subscription_id": "sub_xxx",
  "razorpay_signature": "xxx",
  "plan_type": "monthly"
}
```

---

### `POST /map/suggest-connections`
Triggers AI-powered connection suggestions for the current user's concept library.

**Authentication:** Required (premium)

**Response:**
```json
{
  "success": true,
  "suggestions": [
    {
      "concept_a_id": 12,
      "concept_b_id": 47,
      "relationship_type": "builds on",
      "reason": "Concept A establishes the foundation that Concept B extends."
    }
  ]
}
```

---

## Running Tests

The project uses pytest with the Flask test client.

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_auth.py

# Run with coverage report
pytest --cov=trace --cov-report=html
# Then open htmlcov/index.html

# Run only tests matching a keyword
pytest -k "test_login"
```

A successful run will end with something like:
```
=================== X passed in Y.XXs ===================
```

The test suite uses `TestingConfig` which sets `SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"` and disables CSRF validation, so no external database or browser is needed.

---

## Deployment

Trace is designed for deployment on a Linux VPS (e.g., Ubuntu 22.04 on DigitalOcean, Linode, or AWS EC2). The `deploy/` folder has all the configuration files you need.

### Pre-deployment checklist

- [ ] `SECRET_KEY` set to a random 32-byte hex string
- [ ] `DATABASE_URL` pointing to a production PostgreSQL instance
- [ ] `REDIS_URL` pointing to a production Redis instance
- [ ] `GOOGLE_API_KEY` set and the Generative Language API enabled
- [ ] SMTP credentials configured
- [ ] `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, and `RAZORPAY_WEBHOOK_SECRET` set if billing is live
- [ ] `FLASK_DEBUG=0`
- [ ] `FLASK_ENV=production`

### Setting up the server

```bash
# 1. Install system dependencies
sudo apt-get update
sudo apt-get install -y python3.10 python3.10-venv python3-pip postgresql redis-server nginx libmagic1

# 2. Create app directory and clone
sudo mkdir -p /opt/trace
sudo chown $USER:$USER /opt/trace
git clone https://github.com/shahram8708/trace.git /opt/trace

# 3. Create virtualenv and install dependencies
python3 -m venv /opt/trace/venv
/opt/trace/venv/bin/pip install -r /opt/trace/requirements.txt

# 4. Set up environment file
cp /opt/trace/.env.example /opt/trace/.env
# Edit /opt/trace/.env with production values

# 5. Run database migrations
cd /opt/trace
/opt/trace/venv/bin/flask --app run:create_app db upgrade

# 6. Set up systemd services (update paths in each .service file first)
sudo cp deploy/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now gunicorn.service celery-worker.service celery-beat.service

# 7. Set up Nginx
sudo cp deploy/nginx.conf /etc/nginx/sites-available/trace
# Edit server_name in the config
sudo ln -s /etc/nginx/sites-available/trace /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### Production security

- The `ProductionConfig` class enforces `SESSION_COOKIE_SECURE = True` and `REMEMBER_COOKIE_SECURE = True` — ensure you're running HTTPS (use Certbot: `sudo certbot --nginx`).
- The `ProductionConfig.validate()` method raises a `RuntimeError` at startup if `SECRET_KEY` is the dev default or `REDIS_URL` is missing.
- Set Razorpay webhook endpoint to `https://yourdomain.com/billing/webhook` in the Razorpay dashboard.

---

## Configuration Reference

| Setting | Config class | Default | Notes |
|---|---|---|---|
| `SECRET_KEY` | Config | `dev-secret-key-change-me` | Must override in production |
| `DATABASE_URL` | Config | `sqlite:///trace_dev.db` | PostgreSQL required in production |
| `RATELIMIT_DEFAULT` | Config | `200 per day;50 per hour` | Auth routes have tighter limits |
| `PERMANENT_SESSION_LIFETIME` | Config | 365 days | How long users stay logged in |
| `CELERY_TASK_ALWAYS_EAGER` | DevelopmentConfig | `True` | Tasks run synchronously in dev |
| `CELERY_BROKER_URL` | DevelopmentConfig | `memory://` | No Redis needed in dev |
| `SESSION_COOKIE_SECURE` | ProductionConfig | `True` | Requires HTTPS |
| `FREE_CONCEPT_LIMIT` | env var | `50` | Max concepts for free tier |
| `DAILY_AI_EXTRACTIONS_FREE` | env var | `5` | Max AI extractions/month for free |
| `MAX_PDF_SIZE_MB` | env var | `10` | Max uploaded PDF size |

---

## Contributing

We'd love your help making this better. Here's how to contribute:

1. Fork the repository on GitHub
2. Create a feature branch: `git checkout -b feature/your-amazing-feature`
3. Make your changes in the appropriate module (keep routes thin, services thick)
4. Write or update tests for your changes
5. Ensure tests pass: `pytest`
6. Commit with a clear message: `git commit -m 'Add: brief description of what you added'`
7. Push your branch: `git push origin feature/your-amazing-feature`
8. Open a Pull Request describing what you changed and why

### Code Standards

Looking at the codebase, here's what we follow:

- **Python**: 4-space indentation, snake_case for variables and functions, PascalCase for classes
- **Type hints**: Used on function signatures throughout the services layer (please continue this)
- **Imports**: Standard library first, third-party second, local third — separated by blank lines
- **Comments**: Sparse but present for non-obvious logic; extensive `print()` statements in Celery tasks for debugging (these are intentional and production-useful)
- **Templates**: Jinja2, extend `dashboard_base.html` for authenticated pages and `base.html` for public pages

### Types of contributions we welcome

- Bug fixes (especially around the Razorpay webhook handling or Gemini response parsing)
- New import methods (Readwise, Pocket, web clipper)
- Improved SM-2 implementation or alternative algorithms (FSRS)
- Test coverage additions
- Accessibility improvements in templates
- Performance improvements to the Knowledge Map for large libraries

### What NOT to do

- Don't add new Python dependencies without a compelling reason and a note in the PR
- Don't change the Razorpay billing logic without extensive testing
- Don't disable CSRF in new routes without the CSRF-exempt decorator being justified

---

## Troubleshooting

**Problem:** `ModuleNotFoundError: No module named 'magic'` on startup
**Cause:** `libmagic` system library is not installed.
**Solution:**
```bash
# Ubuntu/Debian
sudo apt-get install libmagic1
# macOS
brew install libmagic
```

---

**Problem:** `OperationalError: no such table: users` on first run
**Cause:** Database hasn't been initialised yet.
**Solution:**
```bash
python run.py  # run.py calls db.create_all() on startup
# OR
flask --app run:create_app db upgrade
```

---

**Problem:** Stuck on "Processing..." after importing a URL
**Cause:** In production, the Celery worker isn't running. In development, this shouldn't happen (tasks run eagerly).
**Solution:**
```bash
# Check Celery worker is running
systemctl status celery-worker.service
# Or start it manually
celery -A celery_worker.celery worker --loglevel=debug
```

---

**Problem:** Email verification link not arriving
**Cause:** SMTP not configured in `.env`, or the mail server is rejecting connections.
**Solution:** In development, check Flask logs — the verification URL is logged. For production, verify your `MAIL_*` environment variables and test with:
```python
flask shell
>>> from trace.app.extensions import mail
>>> from flask_mail import Message
>>> mail.send(Message("Test", recipients=["you@example.com"], body="test"))
```

---

**Problem:** `RuntimeError: Razorpay credentials are not configured`
**Cause:** `RAZORPAY_KEY_ID` or `RAZORPAY_KEY_SECRET` is missing from `.env`.
**Solution:** Add both keys. If you don't have a Razorpay account yet and just want to test, you can comment out the billing blueprint registration in `create_app()` temporarily.

---

**Problem:** `RuntimeError: REDIS_URL must be set in production for Celery`
**Cause:** `ProductionConfig.validate()` runs at startup and requires Redis in production.
**Solution:** Set `REDIS_URL=redis://localhost:6379/0` in your production `.env`, or use `DevelopmentConfig` for local testing.

---

**Problem:** Knowledge Map shows blank / no nodes
**Cause:** User has no active concepts, or is not on a premium account.
**Solution:** Import at least one source and complete AI extraction first. The map requires a premium subscription — check that `user.is_premium` is `True` in the database.

---

**Problem:** `google.genai.errors.APIError: 429 RESOURCE_EXHAUSTED`
**Cause:** You've hit the Gemini API rate limit (common on free-tier API keys).
**Solution:** The `call_gemini_with_retry` function in `gemini_parser.py` includes exponential backoff retry logic. For high-volume usage, upgrade to a paid Gemini API tier.

---

## Roadmap

Based on placeholder content and the integrations waitlist page found in the codebase:

- [ ] **Readwise Integration** — Import highlights directly from Readwise without CSV export
- [ ] **Pocket Integration** — Import articles queued in Pocket
- [ ] **FSRS Algorithm** — Implement Free Spaced Repetition Scheduler (newer, more accurate than SM-2) as an opt-in alternative
- [ ] **Browser Extension** — Clip articles from any page directly into the import queue
- [ ] **Mobile-Optimised Review** — Improve the review session UI for small screens
- [ ] **Collaborative Concept Libraries** — Share a concept library with a team or study group
- [ ] **Spaced Writing** — Prompt users to write a short paragraph applying a concept, not just recall it
- [ ] **Concept Tags** — Multi-tag support beyond single `domain_tag`
- [ ] **Export to Anki** — Export concept library as an Anki-compatible `.apkg` deck

---

## Security

Trace implements multiple layers of security:

**Authentication & Session Security:**
- Passwords are hashed using PBKDF2:SHA256 with a 16-byte random salt (via Werkzeug)
- Sessions use signed cookies with a `SECRET_KEY`
- `SESSION_COOKIE_HTTPONLY = True` prevents JavaScript access to session cookies
- `SESSION_COOKIE_SAMESITE = "Lax"` mitigates CSRF via cross-site requests
- In production, `SESSION_COOKIE_SECURE = True` enforces HTTPS-only cookies
- Login is rate-limited to 10 attempts per 15 minutes per IP

**CSRF Protection:**
- Flask-WTF provides CSRF tokens on all forms
- The Razorpay webhook endpoint (`/billing/webhook`) is explicitly `@csrf.exempt` and uses Razorpay's HMAC-SHA256 signature verification instead

**Input Validation:**
- All form inputs validated with WTForms validators before processing
- URL imports pass through `is_url_safe()` validation before fetching
- PDF MIME type is verified with `python-magic` before processing
- Gemini prompt responses are validated for expected JSON structure before parsing

**Rate Limiting:**
- Global rate limit: 200 requests/day, 50/hour per IP (Flask-Limiter)
- Signup: 5 per hour
- Login: 10 per 15 minutes
- Password reset: 5 per hour
- Verification resend: 3 per hour

**Reporting Vulnerabilities:**
Please do not open public GitHub issues for security vulnerabilities. Instead, email **shahram8708@gmail.com** with a description of the vulnerability, steps to reproduce, and potential impact. We'll respond within 48 hours.

**Data Storage:**
All user data (concepts, review history, source text) is stored in your own database instance. No data is sent to third parties except: Gemini API (concept extraction — source text is sent), Razorpay (payment processing — email and name only), and your configured SMTP provider (email address only).

---

## License

This project is licensed under the **MIT License** — you can use it freely in your own projects, commercial or otherwise, as long as you include the original copyright notice. See the `LICENSE` file for full details.

*(No LICENSE file was found in the repository. Add one — see [choosealicense.com](https://choosealicense.com/licenses/mit/) for a ready-to-use MIT license text.)*

---

## Acknowledgments

This project stands on the shoulders of some excellent open-source work:

- **[Flask](https://flask.palletsprojects.com/)** — The micro-framework that powers the entire server. Its Blueprint system makes the codebase stay organised as it grows.
- **[SQLAlchemy 2.0](https://www.sqlalchemy.org/)** — The ORM. The new `select()` style API makes queries feel like actual Python.
- **[Celery](https://docs.celeryq.dev/)** — Makes async AI extraction feel seamless. Background tasks that just work.
- **[trafilatura](https://trafilatura.readthedocs.io/)** — Remarkably good at extracting readable article text from messy HTML. Handles most real-world articles without configuration.
- **[pdfplumber](https://github.com/jsvine/pdfplumber)** — Clean, Pythonic PDF text extraction. Better than most alternatives for mixed-layout documents.
- **[D3.js](https://d3js.org/)** — The knowledge map wouldn't exist without it. Force-directed graphs are genuinely difficult to build from scratch.
- **[google-genai](https://pypi.org/project/google-genai/)** — The official Gemini SDK. Gemini 2.5 Flash is fast enough and smart enough for the extraction prompts without incurring GPT-4 costs.
- **[Piotr Wozniak](https://supermemo.guru/wiki/Piotr_Wozniak)** — Creator of the SM-2 algorithm that the entire spaced repetition engine is built on. His research on the forgetting curve and optimal review scheduling made apps like Anki (and Trace) possible.
- **[Razorpay](https://razorpay.com/)** — INR billing without the pain of Stripe's limited Indian payment support.
- **[Flask-Limiter](https://flask-limiter.readthedocs.io/)** — Rate limiting in three lines of code. Security that actually gets used because it's not annoying to add.

---

## Contact and Support

- **Bug reports and feature requests:** [Open a GitHub Issue](https://github.com/shahram8708/trace/issues)
- **Email:** shahram8708@gmail.com 
- **Security vulnerabilities:** security@trace.app

---

*Built with care for everyone who reads more than they can remember.*