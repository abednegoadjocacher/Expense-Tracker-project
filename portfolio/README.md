# 💰 Expense Tracker

A production-ready Django web application for recording, tracking, and planning daily expenses — with automatic alerts when categories approach or exceed their monthly budget or spike above your recent spending average.

## Key Features

- **Total & Category Breakdowns**: View your all-time total spend, current month spend, today's total, and detailed category breakdowns with share percentages and donut charts.
- **High-Spending & Spike Notifications**:
  - Set an optional overall monthly budget and per-category monthly budgets.
  - Receive in-app (and optional email) warnings at your chosen threshold (default 80%) and alerts when a budget reaches 100%.
  - Automatic spike detection flags categories whose monthly spend exceeds **1.5×** their 3-month rolling average.
- **Planned & Recurring Expenses**: Schedule one-off or recurring bills (`weekly`, `monthly`, `yearly`), track overdue items and projected month-end spending, and record a plan as paid in one click.
- **Reports & CSV Export**: Filter by preset periods (`This month`, `Last month`, `Last 3 months`, `This year`, `All time`, or a custom date range), inspect 12-month trends and payment methods, and export filtered transactions to CSV (hardened against spreadsheet formula injection).
- **Production Hardened**: WhiteNoise compressed static asset serving, PostgreSQL (`DATABASE_URL` / `DATABASE_NEON_URL`) with SQLite fallback, per-user timezone & multi-currency support, CSRF/HSTS/cookie security when `DJANGO_DEBUG=false`, and a `/healthz/` readiness endpoint.

## Quick Start (Local Development)

1. **Activate the virtual environment & install dependencies**
   ```powershell
   .\env\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. **Apply database migrations**
   ```powershell
   python manage.py migrate
   ```

3. **Run the development server**
   ```powershell
   python manage.py runserver
   ```
   Open `http://127.0.0.1:8000/` in your browser.

4. **Rebuild Tailwind CSS (only needed after editing templates/styles)**
   ```powershell
   python manage.py tailwind build
   ```

5. **Run the test suite**
   ```powershell
   python manage.py test
   ```

## Production Deployment

1. Copy `.env.example` to `.env` (or configure environment variables on your host) and set:
   - `DJANGO_DEBUG=false`
   - `DJANGO_SECRET_KEY=<strong-random-key>`
   - `DJANGO_ALLOWED_HOSTS=your-domain.com`
   - `DJANGO_CSRF_TRUSTED_ORIGINS=https://your-domain.com`
   - `DATABASE_URL=postgresql://...`
2. Collect static files and run migrations:
   ```bash
   python manage.py collectstatic --noinput
   python manage.py migrate --noinput
   ```
3. Start Gunicorn (or use the included `Dockerfile` / `Procfile`):
   ```bash
   gunicorn Expense_Tracker_project.wsgi:application --bind 0.0.0.0:8000 --workers 3
   ```

