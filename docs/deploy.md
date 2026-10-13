# Deploying Daftar

Three pieces, each on its own host: the database on Neon, the API on Render (from the backend Dockerfile), and the web app on
Vercel. The browser only ever talks to the web app; the web app talks to the API from its server (the BFF), so the API needs no
CORS list. Receipts live in Cloudinary and email goes out over SMTP through a Google account.

Order matters: database, then API, then web app, then email links and the check.

Nothing secret is kept in the repository. You type each value into the host's dashboard. Claude never opens `.env`.

## 0. Before you start

1. Push the repository to GitHub (you do this; Claude never pushes).
2. Make two long random values and keep them somewhere safe (a password manager):
   - `SECRET_KEY`: 48 or more characters, mixed, with no word like "secret" or "password".
     `python -c "import secrets; print(secrets.token_urlsafe(48))"`
   - `BFF_SHARED_SECRET`: another one, made the same way. It is typed into both the API and the web app and must match.
3. Have your Cloudinary URL (`cloudinary://API_KEY:API_SECRET@CLOUD_NAME`, from the Cloudinary dashboard, Settings, API Keys)
   and a Google app password for the account that sends the email (section 6).

## 1. Database: Neon

1. Create a project (PostgreSQL 16 or newer) in a region near your users.
2. In the dashboard open Connection details. Choose the **direct** connection, not the pooled one (untick "Pooled
   connection"). The pooled endpoint refuses the connection options the API sets (statement and lock timeouts), and one API
   process keeps only ten connections, which a direct connection handles easily.
3. Copy the owner connection string. It looks like
   `postgresql://neondb_owner:PASSWORD@ep-xxxx.region.aws.neon.tech/neondb?sslmode=require`.
   **Change the start to `postgresql+psycopg://`** (the API needs that exact scheme). This is the `MIGRATION_DATABASE_URL`.
4. Open the SQL editor and make the application role (choose a strong password):
   ```sql
   CREATE ROLE daftar_app LOGIN PASSWORD 'a-long-random-password';
   ```
5. Build the application URL from the same host: replace the user and password with `daftar_app` and its password, keep
   `/neondb?sslmode=require`, and keep the `postgresql+psycopg://` start. This is the `DATABASE_URL`.

The migrations run as the owner and give `daftar_app` exactly the access it needs (it cannot change the schema, and the audit
log is insert and select only).

## 2. Run the migrations (from your computer)

Migrations are never run at boot. Run them yourself, before the first deploy and after any release that adds one.

1. Make a file named `.env.deploy` in the repository root (it is ignored by git; never commit it) with:
   ```
   ENVIRONMENT=production
   SECRET_KEY=<the secret key>
   DATABASE_URL=<the daftar_app URL>
   MIGRATION_DATABASE_URL=<the owner URL>
   BFF_SHARED_SECRET=<the shared secret>
   STORAGE_BACKEND=cloudinary
   CLOUDINARY_URL=<your cloudinary url>
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_SECURE=false
   SMTP_USER=<the google account>
   SMTP_PASS=<its app password>
   SMTP_FROM_EMAIL=info@visionpme.ca
   SMTP_FROM_NAME=Daftar
   ```
2. Build the API image and migrate:
   ```
   docker build -t daftar-api ./backend
   docker run --rm --env-file .env.deploy daftar-api alembic upgrade head
   ```
   It ends with "Running upgrade ... 0006". Re-running is harmless.

## 3. Demonstration data (only for a demo site)

A live database is never seeded by accident. For a demonstration site (the four demo accounts, forty expenses, vouchers, two
closed periods and five receipts uploaded to Cloudinary) add `ALLOW_DEMO_SEED=true` to `.env.deploy` and run:
```
docker run --rm --env-file .env.deploy daftar-api python -m app.seed
```
Remove `ALLOW_DEMO_SEED` afterwards. It prints the four accounts; they all use the password `daftar-demo-2026`. **Change those
passwords (or deactivate the accounts) before real use**, and set `DEMO_MODE=false` on the web app then.

For a real install do not seed. Make the first Admin another way (ask Claude for a one-off command) and invite everyone else
from the Users screen.

## 4. The API: Render

1. New, Blueprint, choose the repository: Render reads `render.yaml` (service `daftar-api`, Docker, root `backend`, health
   check `/health`). Or create a Web Service by hand with the same settings. One instance only: the rate limiter keeps its
   counters in the process.
2. Enter the secret values in the dashboard (Environment):

   | Variable | Value |
   |---|---|
   | `ENVIRONMENT` | `production` (already set) |
   | `SECRET_KEY` | the key from step 0 |
   | `DATABASE_URL` | the `daftar_app` URL from step 1 |
   | `BFF_SHARED_SECRET` | the shared secret from step 0 |
   | `WEB_BASE_URL` | the Vercel address from step 5, with no trailing slash. Enter it after step 5, then redeploy |
   | `STORAGE_BACKEND` | `cloudinary` (already set) |
   | `CLOUDINARY_URL` | your Cloudinary URL |
   | `SMTP_HOST` | `smtp.gmail.com` (already set) |
   | `SMTP_PORT` | `587` (already set) |
   | `SMTP_SECURE` | `false` (already set) |
   | `SMTP_USER` | the Google account that sends the mail |
   | `SMTP_PASS` | that account's app password (16 characters, no spaces) |
   | `SMTP_FROM_EMAIL` | the address mail comes from, `info@visionpme.ca` |
   | `SMTP_FROM_NAME` | the name shown beside it, for example `Daftar` (no quotes) |
   | `DISPLAY_TIMEZONE` | `Asia/Karachi` (already set) |

   `MIGRATION_DATABASE_URL` is **not** set on Render: only you run migrations, from your computer.
3. The API refuses to start in production with a weak key, with receipts or email not configured, or with debug on. If the
   first deploy fails, read its log: the message names the setting.
4. Note the address, `https://daftar-api-xxxx.onrender.com`. Open `/version`: it shows the version and the commit. The
   interactive documentation pages are switched off on a live API.

The free Render plan sleeps after inactivity, so the first request after a pause takes about a minute and can time out a login.
Use the paid Starter plan for anything shown to other people.

## 5. The web app: Vercel

1. Add New, Project, import the repository. **Root Directory: `frontend`**. Framework Next.js (detected). Leave the install
   and build commands as they are (pnpm and `next build`).
2. Environment variables:

   | Variable | Value |
   |---|---|
   | `API_BASE_URL` | the Render address, no trailing slash |
   | `BFF_SHARED_SECRET` | the same value as on Render |
   | `DISPLAY_TIMEZONE` | `Asia/Karachi` |
   | `DEMO_MODE` | `true` for a demonstration site (it lists the demo accounts under the sign-in form), otherwise `false` |

3. Deploy. Note the address, `https://your-project.vercel.app` (or add your own domain under Domains).
4. Go back to Render and set `WEB_BASE_URL` to that address, then redeploy the API (invitation and reset links use it).

## 6. Email: Google SMTP

1. The Google account needs 2-step verification. Then create an app password (Google Account, Security, 2-Step Verification,
   App passwords) and use those 16 characters as `SMTP_PASS`. The normal account password does not work.
2. `SMTP_USER` is that account. `SMTP_FROM_EMAIL` must be that address or an alias added in Gmail under Settings, Accounts,
   "Send mail as"; otherwise Google rewrites or refuses the sender.
3. Setting `SMTP_USER` is what switches real sending on (`MAIL_BACKEND` can stay empty).
4. Render's free web services block outbound SMTP ports (25, 465 and 587). Use a paid instance for the API, or the email will
   fail with a connection timeout.
5. Gmail limits a normal account to about 500 messages a day, which is plenty here.
6. Check it from your computer with the same values in `.env`: `docker compose exec backend python -m app.mail_check you@example.com`.

## 7. Check that it works

Open these in order:

1. `https://<render>/health` shows ok, and `https://<render>/version` shows the commit you deployed.
2. `https://<vercel>/login` shows the sign-in page with the illustration. In a private window sign in as `admin@daftar.pk`
   (demo data only).
3. Walk the demonstration (all four roles, in both themes):
   - **Admin:** Home with figures and charts, Users (invite yourself at a real address and check the email arrives), Audit log.
   - **Staff:** New expense with a photo of a receipt, send it. Confirm the receipt preview opens and the image is in Cloudinary.
   - **Approver:** the notification bell and Approvals, approve the expense; confirm drafts are not visible.
   - **Accountant:** generate the voucher, post it, void it, and check the reversal; export an expense CSV and a report.
   - A restricted address, such as `/users` as Staff, sends you home.
4. Reload a page after waiting more than fifteen minutes: the session refreshes without signing you out.

## Updating later

Push to GitHub. Vercel and Render redeploy on their own. If the release added a migration, run step 2 before it goes live
(migrations here only add, so the old API keeps working while the migration runs).

## If something is wrong

| Symptom | Likely cause |
|---|---|
| Render deploy fails at start | A production setting is missing or weak; the log names it |
| Sign-in works then every page says unauthorised | `BFF_SHARED_SECRET` differs between Render and Vercel |
| Every page is slow or errors after a pause | The free Render plan is asleep; use Starter |
| "role daftar_app does not exist" when migrating | Step 1.4 was skipped, or run on the wrong database |
| Connection error mentioning options | The pooled Neon string was used; use the direct one |
| Invitation emails do not arrive | `SMTP_USER` or `SMTP_PASS` is missing or wrong (a Google app password is needed), the sender is not the account or one of its aliases, or Render's free plan is blocking SMTP. The API log says `email failed` with the server's reason |
| Receipts do not show after a restart | `STORAGE_BACKEND` is not `cloudinary` |
