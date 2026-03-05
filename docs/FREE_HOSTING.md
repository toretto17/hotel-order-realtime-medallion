# Free hosting: website + persistent Kafka (no cost)

This guide gets you **free persistent Kafka** and **free website hosting** so you can run the pipeline and resume from where you left off, without spending money.

---

## What you get (all free)

| Component | Service | What it gives you |
|-----------|---------|-------------------|
| **Kafka (persistent)** | [Aiven Free Kafka](https://aiven.io/free-kafka) | Managed Kafka, no credit card. Topic survives restarts → Bronze can resume from last offset. |
| **Website (Flask)** | [Render](https://render.com) | Free web service; 750 hrs/month. Deploy from GitHub; set env vars for Kafka. |
| **Pipeline (Bronze/Silver/Gold)** | Your laptop or any machine | Run `make bronze`, `make silver`, `make gold` with `KAFKA_BOOTSTRAP_SERVERS` (and security env vars) pointing to Aiven. |

**Flow:** Users open your Render URL → place orders → Flask sends to **Aiven Kafka** → you run Bronze (and Silver/Gold) locally (or on a free compute later) reading from the same Aiven Kafka. Data is persistent; next day you start Bronze again and it **resumes from the last offset**.

---

## 1. Free persistent Kafka (Aiven)

**Detailed step-by-step (every click, every value):** **[AIVEN_SETUP_STEP_BY_STEP.md](AIVEN_SETUP_STEP_BY_STEP.md)** — follow that from start to end.

Short version:

1. **Sign up:** [aiven.io/free-kafka](https://aiven.io/free-kafka) — no credit card.
2. **Create a Kafka service:** Choose region, create. Wait ~2 minutes.
3. **Get connection details:** In the Aiven console, open your Kafka service:
   - **Service URI** (or Bootstrap URI): e.g. `kafka-xxxxx.aivencloud.com:12345`
   - **Access certificate** and **Access key**: download **CA certificate** (`ca.pem`), **Service certificate** (`service.cert`), **Service key** (`service.key`) if you use client certs; for SASL you need **Username** and **Password** from the console.
   - Aiven free tier often uses **SSL** and sometimes **SASL**. Note the **security protocol** (e.g. SASL_SSL) and **SASL mechanism** (e.g. SCRAM-SHA-256).
4. **Create topic `orders`:** In Aiven console, Topics → Create topic → name: `orders`. Partitions: 1 or 2 (free tier allows a few).

**Limitations (free tier):** Service may power off after 24 h inactivity (reactivate in console). Up to 5 topics. Good for learning and demos.

---

## 2. Environment variables for Kafka (SSL/SASL)

Your **web app** and **Bronze job** already read these. Set them when using Aiven (or any managed Kafka).

| Variable | Example | Purpose |
|----------|---------|--------|
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka-xxxxx.aivencloud.com:12345` | Broker address. |
| `KAFKA_SECURITY_PROTOCOL` | `SASL_SSL` or `SSL` | Required for Aiven. |
| `KAFKA_SSL_CA_LOCATION` | `/path/to/ca.pem` | Path to CA cert (local runs). |
| `KAFKA_SSL_CA_CERT` | `-----BEGIN CERTIFICATE-----...` | **Alternative:** full CA cert as string (use on Render where you can’t upload files). |
| `KAFKA_SASL_MECHANISM` | `SCRAM-SHA-256` | If using SASL. |
| `KAFKA_SASL_USERNAME` | from Aiven console | SASL user. |
| `KAFKA_SASL_PASSWORD` | from Aiven console | SASL password. |

- **Local (Bronze on your machine):** Set `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_SECURITY_PROTOCOL`, `KAFKA_SSL_CA_LOCATION` (path to downloaded `ca.pem`), and if SASL: `KAFKA_SASL_MECHANISM`, `KAFKA_SASL_USERNAME`, `KAFKA_SASL_PASSWORD`. Config is in `config/pipeline.yaml` (env substitution).
- **Render (website):** In Render Dashboard → your Web Service → Environment: add the same vars. For CA cert use **`KAFKA_SSL_CA_CERT`** and paste the **contents** of `ca.pem` (one line or multi-line).

---

## 3. Free website hosting (Render)

**Step-by-step (every click, every value):** **[RENDER_WEBSITE_HOSTING_STEP_BY_STEP.md](RENDER_WEBSITE_HOSTING_STEP_BY_STEP.md)** — follow that from start to end to get your site live with a free URL (`https://your-app.onrender.com`) so friends and users can place orders.

Short version:

1. **Push your repo to GitHub** (if not already).
2. **Sign up:** [render.com](https://render.com) (free account); connect GitHub.
3. **New Web Service:** Select your repo. Set **Root Directory** to `web`. **Build command:** `pip install -r ../requirements.txt`. **Start command:** `gunicorn app:app`.
4. **Environment:** Add Kafka env vars. On Render you **cannot** use file paths for certs — use **contents** instead:
   - `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_SECURITY_PROTOCOL=SSL`, `KAFKA_TOPIC=orders`
   - `KAFKA_SSL_CA_CERT` = full contents of `ca.pem`
   - `KAFKA_SSL_CERT_CERT` = full contents of `service.cert`
   - `KAFKA_SSL_KEY_CERT` = full contents of `service.key`
5. **Deploy.** Your site will be at `https://your-service.onrender.com` (free domain). Optionally add a custom domain in Render Settings.

**Render free tier:** Service spins down after ~15 min inactivity; first request may take ~1 min to wake. 750 instance hours/month. No persistent disk.

---

## 4. Run the pipeline (Bronze, Silver, Gold) with Aiven

On your **local machine** (or any machine with Python, Java, Spark):

1. **Set env vars** (same as above). For Bronze you need at least:
   - `KAFKA_BOOTSTRAP_SERVERS`
   - `KAFKA_SECURITY_PROTOCOL`
   - `KAFKA_SSL_CA_LOCATION` (path to `ca.pem`)
   - If SASL: `KAFKA_SASL_MECHANISM`, `KAFKA_SASL_USERNAME`, `KAFKA_SASL_PASSWORD`
   - `BASE_PATH` (e.g. `/tmp/medallion` or an S3 path)
2. **Create topic** (if not done in Aiven): use the Aiven console or a script that uses the same bootstrap + security to create topic `orders`.
3. **Start Bronze:** `make bronze` (or `./scripts/run_bronze.sh`). It reads from Aiven Kafka and writes to `BASE_PATH/bronze/orders`. Checkpoint is under `BASE_PATH/checkpoints/bronze_orders` → **resume from last offset** when you start again.
4. **Silver:** `make silver` (after Bronze has data).
5. **Gold:** `make gold` (after Silver has data).

Because Aiven Kafka is **persistent**, when you stop Bronze and start it again later, it continues from the last committed offset — no “offset was changed” error.

---

## 5. Checklist: code and config

- **Web app** (`web/app.py`): Reads `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_TOPIC`, and optional `KAFKA_SECURITY_PROTOCOL`, `KAFKA_SSL_CA_LOCATION`, `KAFKA_SSL_CA_CERT`, `KAFKA_SASL_*`. Producer uses these for plain or SSL/SASL.
- **Pipeline config** (`config/pipeline.yaml`): `kafka` section has optional `security_protocol`, `ssl_ca_location`, `sasl_mechanism`, `sasl_username`, `sasl_password` (all from env). Leave empty for local Docker Kafka.
- **Bronze job** (`streaming/bronze_orders.py`): If security options are set in config, adds `kafka.security.protocol`, `kafka.ssl.truststore.*`, `kafka.sasl.*` for Spark’s Kafka source.

No code changes needed for a new deployment — only env vars and the steps above.

---

## 6. Summary

| Step | Action |
|------|--------|
| 1 | Sign up Aiven → create Kafka service → create topic `orders` → download CA cert, note bootstrap URI and SASL user/password if used. |
| 2 | Set Kafka env vars locally and on Render (use `KAFKA_SSL_CA_CERT` on Render for CA). |
| 3 | Deploy Flask app on Render (root `web`, start `gunicorn app:app`, add Kafka env vars). |
| 4 | Run Bronze (and Silver/Gold) locally with same Kafka env vars and `BASE_PATH`. |
| 5 | Open your Render URL → place orders → they go to Aiven Kafka → Bronze processes and resumes next time. |

This gives you **free persistent Kafka** and **free website hosting** so the project runs at no cost and Bronze can resume from where you left off. For more on why persistent Kafka is required for resume, see [SETUP_AND_RUN.md §12](SETUP_AND_RUN.md#12-live-hosting--persistent-kafka-future-scope).
