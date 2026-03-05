# Free website hosting on Render — step-by-step (like Aiven)

This guide gets your **hotel ordering website** live on the internet so **friends and users can place orders** from a real URL. You get a **free “correct” domain**: `https://your-app-name.onrender.com`. Optionally you can attach a **custom domain** (e.g. `orders.myhotel.com`) if you own one.

**Prerequisites:** Your code is on **GitHub**, and you already have **Aiven Kafka** set up (bootstrap URI, SSL certs). Orders from the hosted site will go to Aiven Kafka; you run Bronze/Silver/Gold locally (or elsewhere) to process them.

**Postgres:** You need Postgres with **all tables** (Bronze, Silver, Gold) for Grafana and historic/debugging. That will be a separate step (sync each layer to Postgres). This doc focuses only on **hosting the website** so friends and users can place orders from a live URL.

---

## Part 1: Push your code to GitHub

1. If the project is not yet on GitHub:
   - Create a new **repository** on GitHub (e.g. `realtime-order-medallion`).
   - From your project root run:
     ```bash
     git remote add origin https://github.com/YOUR_USERNAME/realtime-order-medallion.git
     git push -u origin main
     ```
     (Use `master` if your branch is `master`.)
2. Make sure the **web app** and **requirements** are in the repo:
   - `web/app.py`
   - Project root `requirements.txt` (includes `flask`, `gunicorn`, `confluent-kafka`).
3. **Do not** push `.env` or `certs/` (they are in `.gitignore`). You will enter Kafka settings in Render’s dashboard instead.

---

## Part 2: Create a Render account

1. Open a browser and go to: **https://render.com**
2. Click **“Get started for free”** or **“Sign up”**.
3. Sign up with **GitHub** (recommended so Render can access your repo) or with email.
4. If you use GitHub, authorize Render. You should land on the Render **Dashboard**.

---

## Part 3: Create a new Web Service (your website)

1. On the Render Dashboard, click **“New +”** (top right) → **“Web Service”**.
2. **Connect a repository:**
   - If your GitHub is not connected, click **“Connect GitHub”** and select the account/org that has your repo.
   - Find your repo (e.g. `realtime-order-medallion`) and click **“Connect”** next to it.
3. **Configure the Web Service:**

   | Field | Value | Notes |
   |-------|--------|------|
   | **Name** | e.g. `realtime-order-medallion` or `hotel-orders` | This becomes your free URL: `https://NAME.onrender.com` |
   | **Region** | Choose closest to you (e.g. Oregon for US, Frankfurt for EU) | Free tier has a few options. |
   | **Branch** | `main` (or `master`) | The branch Render will deploy from. |
   | **Root Directory** | `web` | Leave empty if your start command will `cd web`; or set to `web` so Render’s working directory is `web/`. |
   | **Runtime** | **Python 3** | Render will detect Python from your repo. |
   | **Build Command** | `pip install -r ../requirements.txt` | If Root Directory is `web`, requirements are one level up. Or if Root is empty: `pip install -r requirements.txt`. |
   | **Start Command** | `gunicorn app:app` | If Root Directory is `web`, run from `web/` where `app.py` lives. If Root is empty, use: `cd web && gunicorn app:app`. |

   **Recommended (Root Directory = `web`):**
   - **Build command:** `pip install -r ../requirements.txt`
   - **Start command:** `gunicorn app:app`

   **Alternative (Root Directory empty):**
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `cd web && gunicorn app:app`

4. Click **“Advanced”** and ensure:
   - **Plan:** **Free**.

---

## Part 4: Add environment variables (Kafka / Aiven)

Render cannot read your local `.env` or cert files. You must add every Kafka-related variable in the Render dashboard.

1. In the same Web Service setup page, scroll to **“Environment Variables”**.
2. Click **“Add Environment Variable”** and add the following **one by one**. Use the **same values** as in your local `.env` (and from Aiven).

   **Required for Aiven (SSL + client cert):**

   | Key | Value | Where you get it |
   |-----|--------|-------------------|
   | `KAFKA_BOOTSTRAP_SERVERS` | `your-service.aivencloud.com:19413` | Aiven → Kafka service → Connection information → Bootstrap URI. |
   | `KAFKA_SECURITY_PROTOCOL` | `SSL` | You use SSL + client cert. |
   | `KAFKA_TOPIC` | `orders` | Your topic name. |
   | `KAFKA_SSL_CA_CERT` | (paste full contents of `ca.pem`) | Open `certs/ca.pem` in a text editor; copy **everything** from `-----BEGIN CERTIFICATE-----` to `-----END CERTIFICATE-----`. Paste as the value. You can use a single line with `\n` for newlines, or paste multiple lines. |
   | `KAFKA_SSL_CERT_CERT` | (paste full contents of `service.cert`) | Same: copy entire content of `certs/service.cert` and paste. |
   | `KAFKA_SSL_KEY_CERT` | (paste full contents of `service.key`) | Same: copy entire content of `certs/service.key` and paste. **Keep this secret.** |

   **Optional:**

   | Key | Value |
   |-----|--------|
   | `HOTEL_RESTAURANT_ID` | `R1` (or your default restaurant id) |

3. **Pasting certs:**  
   - You can paste the cert/key as **multi-line** (Render accepts it).  
   - Or as one line: replace real newlines with `\n` (e.g. `-----BEGIN CERTIFICATE-----\nMII...\n-----END CERTIFICATE-----`).

4. Do **not** add `KAFKA_SSL_CA_LOCATION`, `KAFKA_SSL_CERT_LOCATION`, or `KAFKA_SSL_KEY_LOCATION` — on Render there are no file paths; we use `KAFKA_SSL_CA_CERT`, `KAFKA_SSL_CERT_CERT`, and `KAFKA_SSL_KEY_CERT` (contents only).

---

## Part 5: Deploy

1. Click **“Create Web Service”** (or **“Deploy”**).
2. Render will **clone** your repo, run the **build command**, then the **start command**.
3. Watch the **Logs** tab. The first deploy may take 2–5 minutes.
4. When the build and start succeed, you’ll see a green **“Live”** and a URL like:
   - **https://realtime-order-medallion.onrender.com** (or whatever **Name** you chose).

That URL is your **free “correct” domain** — you can share it with friends so they can place orders.

---

## Part 6: Test orders from the hosted website

1. Open the **Render URL** in your browser (e.g. `https://your-app.onrender.com`).
2. Add items to the cart and place an order.
3. You should see a success message and an order ID (e.g. `web-abc123...`).
4. **On your machine:** With `.env` loaded, run Bronze (and optionally Silver/Gold). Bronze will read from Aiven Kafka and process the order that the hosted site just produced.

**Free tier note:** The service may **spin down** after ~15 minutes of no traffic. The **first request** after that can take ~30–60 seconds (cold start). After that it’s fast.

---

## Part 7: (Optional) Custom domain

If you want a **custom domain** (e.g. `orders.myhotel.com`):

1. You must **own** the domain (buy it from a registrar like Namecheap, Google Domains, etc., or use a free one if available).
2. In Render: open your **Web Service** → **Settings** → **Custom Domain**.
3. Click **“Add Custom Domain”** and enter your domain (e.g. `orders.myhotel.com`).
4. Render will show you a **CNAME** (e.g. `your-app.onrender.com`) or **A** record.
5. In your **domain registrar’s DNS** settings, add the CNAME or A record as instructed by Render.
6. Wait for DNS to propagate (minutes to hours). Render will then serve your site on the custom domain (with HTTPS).

**Free “domain” without buying one:** The default **https://your-app.onrender.com** is already a proper, shareable URL — that’s the free option.

---

## Checklist (quick recap)

- [ ] Code on GitHub (with `web/app.py`, root `requirements.txt`, `gunicorn` in requirements).
- [ ] Render account created; GitHub connected.
- [ ] New Web Service: Name, Region, Branch; Root Directory `web` (or empty with `cd web` in start command).
- [ ] Build: `pip install -r ../requirements.txt` (or `pip install -r requirements.txt` if root empty).
- [ ] Start: `gunicorn app:app` (or `cd web && gunicorn app:app`).
- [ ] Env vars: `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_SECURITY_PROTOCOL=SSL`, `KAFKA_TOPIC=orders`, `KAFKA_SSL_CA_CERT`, `KAFKA_SSL_CERT_CERT`, `KAFKA_SSL_KEY_CERT` (all from Aiven / your `.env`).
- [ ] Deploy; open the Render URL and place a test order.
- [ ] Run Bronze (and Silver/Gold) locally with the same Aiven Kafka to process orders from the hosted site.

---

## Troubleshooting

| Issue | What to do |
|-------|------------|
| Build fails: “No module named 'flask'” | Ensure `requirements.txt` at repo root has `flask` and `gunicorn`; build command uses the correct path (`requirements.txt` or `../requirements.txt`). |
| Build fails: “No module named 'confluent_kafka'” | Add `confluent-kafka` to the same `requirements.txt` used in the build. |
| App starts but orders fail / “connection closed” | Check env vars: `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_SECURITY_PROTOCOL=SSL`, and **all three** cert vars (`KAFKA_SSL_CA_CERT`, `KAFKA_SSL_CERT_CERT`, `KAFKA_SSL_KEY_CERT`) must be set and contain the full PEM content (including BEGIN/END lines). |
| First load very slow | Free tier spins down after inactivity; first request wakes the service (often 30–60 s). |
| Custom domain not working | Verify DNS CNAME/A at your registrar; wait for propagation; in Render, ensure the custom domain shows as “Verified”. |

---

**Next:** Postgres (Bronze, Silver, Gold tables for Grafana and debugging) will be a separate guide. This guide only covers **hosting the website** so users and friends can create orders from your live URL.
