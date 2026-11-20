# Babban Garrage — functional starter v0.1

This is a Flask + SQLite mobile-first web application, NOT a FlutterFlow project or Android APK. It is a partial implementation, not the full requested production system. Code is provided without a software subscription; hosting, backups, domains, messaging and payment providers may cost money. GitHub Pages cannot execute this Python backend. A GitHub repository stores the code; use Python-compatible hosting with persistent disk to run it.

## Run
Requires Python 3.12+. From the extracted project directory:
```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export OWNER_PASSWORD='choose-a-unique-password-12-plus-characters'
export SECRET_KEY='replace-with-a-long-random-persistent-secret'
python app.py
```
Open http://localhost:5000. Initial username: owner. Windows PowerShell: use `$env:OWNER_PASSWORD="..."` and `$env:SECRET_KEY="..."`; activate with `.venv\Scripts\Activate.ps1`.
Owner password creates the first account ONLY; changing the environment variable does not reset existing credentials. No password reset UI yet. Do not commit credentials or the database.

Production command: `gunicorn --workers 1 --bind 0.0.0.0:8080 app:app` behind HTTPS. Set HTTPS_ONLY=1 when served through HTTPS. Set DATABASE_PATH to a file on persistent storage. The containing directory must already exist. Back up and restore-test the database. Ephemeral hosting loses records. Do not expose the local development server to the internet.

## Phone + GitHub
Extract ZIP, create a private repository and upload the CONTENTS of this folder using GitHub's Add file > Upload files. Uploading only the ZIP will not deploy it. Connect a Python-compatible host to the repository, configure environment variables and persistent storage, install requirements, and use the production command above. This package does not deploy anything or create a GitHub repository automatically. Do not put credentials into GitHub files.

## Connected features implemented
- Owner/staff accounts, hashed passwords, server-side role checks, CSRF tokens.
- Owner creates/deactivates staff; deactivation blocks existing sessions on next protected request.
- Customers with multiple vehicles; customer search includes registration numbers.
- Assigned jobs with seven statuses; staff sees only assigned jobs, own attendance and salary entries.
- Simple non-GST direct/job-linked bill; unique job-to-bill constraint prevents duplicate bills for one job.
- Partial confirmed payments, overpayment prevention in a write transaction, sequential invoice/receipt IDs.
- Billing/collection/expenses kept separate; outstanding unpaid bill totals.
- Printable bill with receipt entries. Browser print-to-PDF only.
- Stock item register, expenses, manual attendance and salary earned/payment/advance ledger.
- Staff cannot mutate attendance, salary, business records or job progress in this version.
- Money stored in integer paise. Dates displayed DD/MM/YYYY except browser-native date controls.

## NOT implemented / must not assume complete
- GST (inclusive/exclusive rates, CGST/SGST/IGST), line items, labour/parts breakup, discounts, roundoff.
- Inventory movements, stock deduction, scanning, low-stock thresholds or alerts.
- Customer opening balances, advances/application, customer running ledger/profile or complete vehicle history.
- Job photos, multiple mechanics, estimates/delivery dates, inspection/internal notes and status audit trail.
- Standalone PDF generation, native share, separate downloadable receipt documents, UPI QR and verified payment integration.
- WhatsApp/SMS reminders, delivery tracking, automated sends.
- Weekly/monthly reports, profit, expenses categories and business timezone handling.
- Salary rate configuration/proration, monthly closing, advances recovery allocation, historical corrections.
- Owner settings/address/GSTIN, staff detailed profile/photos/private notes, fine-grained permissions.
- Edit workflows, financial reversal audit logs, duplicate-submission protection for payments/expenses/salary, pagination, loading indicators.
- Offline mode, installable PWA, APK, automated backups, MFA, login rate limiting and password reset.

Salary: Earned increases amount due to staff. Payment and Advance decrease it. Never enter the same disbursement as both Advance and Payment. Negative balance means staff has received more than earned. This is a simplified running ledger, not a payroll engine.

## Release gate
Do not rely on real financial records until completing missing features and independent security/accounting review. Add login throttling and HTTPS before public exposure. Database files and backups must be inaccessible to public static serving. Add authenticated APIs/row-level policies if moving the UI to a separate frontend; current access enforcement lives in server routes, not direct-client database rules. Owners must not hand staff database credentials. Test role isolation, forged POST requests, duplicate bills, simultaneous partial payments, deactivation, database backup/restore and timezone boundaries.

Validation here: Python syntax compilation passed. Runtime tests could not be executed because Flask is not installed in the generation environment. No functional testing or security certification is claimed.
