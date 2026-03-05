# Aiven Free Kafka — Step-by-step setup (start to end)

Follow this **line by line**. Every click and every value is listed so you don’t miss anything.

---

## Free tier: how long and what’s limited

| What | Detail |
|------|--------|
| **How long is it free?** | **No end date.** You can use the free tier as long as you want (no “trial days” or expiry). |
| **Power off after inactivity** | If **no data is produced or consumed for 24 hours**, the service **automatically powers off** to save resources. You get a notification. You can **power it back on** anytime from the Aiven Console (one click); your topic and data are still there. |
| **Deletion** | If the service stays **powered off for more than 180 days in a row**, Aiven may delete it (you get a warning first). Normal use or powering on within 180 days keeps it. |
| **One free Kafka per account** | Each organization can have **one** free Kafka service. |
| **Topics** | Up to **5 topics**, each with **2 partitions**. Our project uses one topic: `orders`. |
| **Throughput** | About **250 KiB/s** (enough for learning, demos, and light use). |
| **Not included** | No SLA, no Kafka Connect/MirrorMaker, no custom config; fixed retention. |

**Summary:** Free forever for this use case. If you don’t use it for 24 hours it sleeps; you wake it in the console. Keep using it or power it on within 180 days and it won’t be deleted.

---

## Part 1: Create your Aiven account and project

### Step 1.1 — Open Aiven Free Kafka page

1. Open your browser.
2. Go to: **https://aiven.io/free-kafka**
3. You should see the Aiven “Free Kafka” marketing page.

### Step 1.2 — Start sign-up

1. On that page, find and click the button that says **“Get started”** or **“Create free account”** or **“Sign up”**.
2. You may be asked to sign up with **Email**, **Google**, or **GitHub**. Choose one (e.g. **Email**).
3. If you chose **Email**:
   - Enter your **email address**.
   - Enter a **password** (meet their requirements, e.g. 8+ characters).
   - Accept terms if shown.
   - Click **Sign up** / **Create account**.
4. If asked to verify email, check your inbox and click the verification link.
5. After login you should land in the **Aiven Console** (e.g. **https://console.aiven.io/**).

### Step 1.3 — Create or select a project

1. In the Aiven Console, check the top bar or left sidebar for **“Project”**.
2. If you see **“Create your first project”** or an empty list:
   - Click **“Create project”** (or similar).
   - **Project name:** e.g. `realtime-order-medallion` or `my-kafka-project`.
   - Click **Create**.
3. If you already have a project, select it from the project dropdown so you’re inside that project.
4. You should now be inside one project (e.g. **Overview** or **Services**).

---

## Part 2: Create the free Kafka service

### Step 2.1 — Start creating a service

1. In the left sidebar, click **“Services”**.
2. Click the **“Create service”** button (or **“+ Create service”**).

### Step 2.2 — Choose Kafka and Free tier

1. You’ll see a list of products (e.g. Apache Kafka®, MySQL, etc.).
2. Select **“Apache Kafka®”** (or **“Aiven for Apache Kafka®”**).
3. Find **“Service tier”** or **“Plan”**.
4. Select **“Free”** (not Starter or other paid tiers).
5. If you see **“Cloud”** or **“Region”** (e.g. Asia Pacific, Australia, Europe, North America):
   - **India / South Asia:** choose **Asia Pacific** (lowest latency; often includes Singapore or Mumbai).
   - **US:** North America. **Europe:** Europe. **Australia:** Australia. Free tier may show only some options; pick the one closest to you.

### Step 2.3 — Service name and create

1. Find the **“Service name”** field (sometimes under “Service basics”). Aiven may **pre-fill** something like **`kafka-35ab48f5`** (random characters).
2. You can either:
   - **Keep the pre-filled name** (e.g. `kafka-35ab48f5`) — it works fine; or
   - **Replace it** with a name that matches your project, e.g. **`order-medallion-kafka`** or **`realtime-order-kafka`**.
3. Rules: only **letters, numbers, hyphens**; **no spaces**. Examples: `order-medallion-kafka`, `realtime-order-kafka`, `my-kafka`.
4. Scroll down and review the **summary** (product: Kafka, plan: Free, region, name).
5. Click **“Create service”** (or **“Create”**).

### Step 2.4 — Wait until the service is running

1. You’ll be taken to the service page. Status will be something like **“Powering on”** or **“Creating”**.
2. Wait until the status changes to **“Running”** (often **1–3 minutes**). Do not close the page; you can refresh.
3. When it says **“Running”**, continue to Part 3.

---

## Part 3: Create the `orders` topic

### Step 3.1 — Open Topics

1. Make sure you’re on the page of your **Kafka service** (the one you just created).
2. In the left menu of that service (or tabs at the top), find **“Topics”**.
3. Click **“Topics”**.

### Step 3.2 — Create topic

1. Click **“Create topic”** (or **“+ Create topic”**).
2. **Topic name:** type exactly: **`orders`** (lowercase, no spaces). This must match what the pipeline and web app use.
3. Leave **partitions** as default (e.g. **2**; free tier allows a few partitions).
4. If you see **“Enable advanced configuration”**, you can leave it **off** for now.
5. Click **“Create topic”** (or **“Create”**).
6. The topic **`orders`** should appear in the list. No need to wait; it’s ready.

---

## Part 4: Get connection details (bootstrap, CA cert, SASL)

### Step 4.1 — Open the service overview / connection info

1. Go back to your Kafka service (click the service name in the breadcrumb or **Services** → your service).
2. Open the **“Overview”** tab (or the first tab that shows connection info).
3. Find the **“Connection information”** (or **“Connection details”**) section. It may be in a box with tabs like **“Connection info”**, **“Kafka”**, or **“Default”**.

### Step 4.2 — Authentication: SASL vs client certificate (production)

1. In Connection information you may see tabs: **“Apache Kafka”**, **“SASL”**, **“Schema Registry”**, etc.
2. **Important:** **Schema Registry** has its own username/password — that is **not** for the Kafka broker. Do **not** put Schema Registry credentials into `KAFKA_SASL_USERNAME` or `KAFKA_SASL_PASSWORD`. They are for a different service (Avro/schema storage); our pipeline only uses the Kafka broker.
3. **If the “SASL” tab (next to Apache Kafka) is disabled or missing:** Aiven may only expose **client certificate** auth for Kafka on your plan. In that case use **SSL + client certificate only** (the 3 files: `ca.pem`, `service.cert`, `service.key`). This is **production-grade**: no password in config, cert-based mutual TLS. Set `KAFKA_SECURITY_PROTOCOL=SSL` and the cert paths in `.env`; leave SASL vars empty.
4. **If the SASL tab is available:** You can use either SASL (username/password) or client certificate. For production, both are valid; client cert avoids storing a password and is often preferred for machines.

### Step 4.3 — Copy Bootstrap / Service URI (this is KAFKA_BOOTSTRAP_SERVERS)

1. In the same Connection information section, look for:
   - **“Bootstrap URI”**, or  
   - **“Service URI”**, or  
   - **“Bootstrap servers”**, or  
   - **“Host”** and **“Port”** (e.g. `kafka-xxxxx-xxxx.aivencloud.com:12345`).
2. Copy the **full address** including port. It usually looks like:
   - `kafka-xxxxxxxx-xxxxxxxx.aivencloud.com:12345`
3. **Save this somewhere** (e.g. a text file). This is your **`KAFKA_BOOTSTRAP_SERVERS`** value.
   - Example: `KAFKA_BOOTSTRAP_SERVERS=kafka-abc123def456.aivencloud.com:12345`

### Step 4.4 — SASL username and password (only if SASL tab is available)

**Do not use Schema Registry username/password** — those are for Schema Registry, not for the Kafka broker. Our pipeline does not use Schema Registry.

The **Kafka SASL password** (if you use SASL) is only in the **Aiven Console**; it’s not in the 3 downloaded files (ca.pem, service.cert, service.key).

1. In Connection information, if you have a **“SASL”** tab **next to “Apache Kafka”** (not Schema Registry), click it.
2. You’ll see **SASL username** (e.g. `avnadmin`) → **`KAFKA_SASL_USERNAME`**, and **SASL password** (click **“Show”** or **“Copy”**) → **`KAFKA_SASL_PASSWORD`** in `.env`.
3. If the **SASL tab is disabled or you can’t open it:** Use **client certificate only** (recommended). Set `KAFKA_SECURITY_PROTOCOL=SSL`, set the three cert paths in `.env`, and leave all SASL vars empty. The web app and Bronze job both support SSL + client cert.

### Step 4.5 — Download CA certificate (ca.pem)

1. In the same Connection information section, find **“CA Certificate”** (or **“TLS CA certificate”**).
2. Click **“Download”** (or the download icon). A file like **`ca.pem`** will be saved.
3. Move or remember the path to this file, e.g.:
   - **Mac/Linux:** e.g. `~/Downloads/ca.pem` or put it in your project: `realtime-order-medallion/ca.pem`
   - **Windows:** e.g. `C:\Users\YourName\Downloads\ca.pem`
4. **For local runs (Bronze):** You’ll set **`KAFKA_SSL_CA_LOCATION`** to this path (e.g. `/Users/you/realtime-order-medallion/ca.pem`).
5. **For Render (website):** You’ll open `ca.pem` in a text editor, copy **the entire contents** (including `-----BEGIN CERTIFICATE-----` and `-----END CERTIFICATE-----`), and paste that into the **`KAFKA_SSL_CA_CERT`** environment variable.

### Step 4.6 — Note security protocol and SASL mechanism

1. Aiven typically uses:
   - **Security protocol:** **`SASL_SSL`** (not plain SSL or PLAINTEXT).
   - **SASL mechanism:** **`SCRAM-SHA-256`** or **`SCRAM-SHA-512`** (sometimes **`PLAIN`**). Check the Connection information or the “Connect” / “Connection parameters” section; it often says which mechanism.
2. **Write down:**
   - **`KAFKA_SECURITY_PROTOCOL`** = **`SASL_SSL`**
   - **`KAFKA_SASL_MECHANISM`** = the one shown (e.g. **`SCRAM-SHA-256`**)

---

## Part 5: Summary — values to use

Fill these from the steps above. Use them in **environment variables** (local and on Render).  
**When the SASL tab is not available:** use **SSL + client certificate only**; you do **not** need SASL username/password.

| Variable | Where you got it | Example value |
|----------|-------------------|----------------|
| **KAFKA_BOOTSTRAP_SERVERS** | Step 4.3 — Bootstrap/Service URI | `kafka-abc123def456.aivencloud.com:12345` |
| **KAFKA_SECURITY_PROTOCOL** | Use **`SSL`** for client cert only | `SSL` |
| **KAFKA_SSL_CA_LOCATION** | Step 4.5 — path to `ca.pem` (local) | `.../certs/ca.pem` |
| **KAFKA_SSL_CERT_LOCATION** | Path to `service.cert` in `certs/` | `.../certs/service.cert` |
| **KAFKA_SSL_KEY_LOCATION** | Path to `service.key` in `certs/` | `.../certs/service.key` |
| **KAFKA_SSL_CA_CERT** | Full contents of `ca.pem` (for Render only) | `-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----` |
| **KAFKA_SASL_*** | Only if SASL tab is available for Kafka | (leave empty when using client cert) |
| **KAFKA_TOPIC** | Part 3 | `orders` |

---

## Single place to update (config + password)

So that **tomorrow** you only update one place if the URI, password, or certs change:

1. **Copy `.env.example` to `.env`** (in the project root). Fill in your real values. **Never commit `.env`** — it’s in `.gitignore` and may contain the SASL password.
2. **Store the SASL password** in a password manager if you like; when you run the app, paste it into `.env` as `KAFKA_SASL_PASSWORD=...` or export it in the terminal. The code only reads env vars; it doesn’t need a separate “password manager” — the single place is **`.env`**.
3. **Move the 3 downloaded files** from `~/Downloads/` into the project so paths stay stable:
   - Create folder: `realtime-order-medallion/certs/` (it exists with a `.gitkeep`).
   - Copy there: `ca.pem`, `service.cert`, `service.key` from your Downloads.
   - In `.env` set:
     - `KAFKA_SSL_CA_LOCATION=/Users/rahulshah/realtime-order-medallion/certs/ca.pem`
     - (If using client cert) `KAFKA_SSL_CERT_LOCATION=.../certs/service.cert`, `KAFKA_SSL_KEY_LOCATION=.../certs/service.key`
   - The `certs/` folder is in `.gitignore` (except `.gitkeep`), so certs are not committed.
4. **If Aiven changes** the service URI, password, or you re-download certs: edit **only `.env`** (and replace the 3 files in `certs/` if they changed). Then run the app again — no code changes.

**Summary:** One place = **`.env`** (and the 3 files in **`certs/`**). Update those when something changes.

---

## Part 6: Set env vars locally (to run Bronze / Silver / Gold)

**Option A — Use `.env` (recommended: one place to update)**  
From the project root, copy the example and load it in the same terminal before running any command:

```bash
cp .env.example .env
# Edit .env and fill in your real values (bootstrap URI, password, paths to certs).
# Then in the same terminal, load .env and run:
set -a && source .env && set +a
make bronze
```

(On some shells you may need `export $(grep -v '^#' .env | xargs)` instead of `set -a && source .env && set +a`.)

**Option B — Export by hand**  
In the terminal, export each variable, then run `make bronze`:

```bash
export KAFKA_BOOTSTRAP_SERVERS="order-medallion-kafka-realtime-order-medallion.d.aivencloud.com:19413"
export KAFKA_SECURITY_PROTOCOL="SASL_SSL"
export KAFKA_SSL_CA_LOCATION="/Users/rahulshah/realtime-order-medallion/certs/ca.pem"
export KAFKA_SASL_MECHANISM="SCRAM-SHA-256"
export KAFKA_SASL_USERNAME="<your-username-from-console>"
export KAFKA_SASL_PASSWORD="<your-password-from-console>"
export KAFKA_TOPIC="orders"
export BASE_PATH="/tmp/medallion"
make bronze
```

Then run:

```bash
make bronze
```

(Silver and Gold don’t need Kafka; run them after Bronze has data.)

---

## Part 7: Optional — test the web app locally with Aiven

1. Put `ca.pem` in your project folder and set **KAFKA_SSL_CA_LOCATION** to its path.
2. In the **same terminal** where you set the env vars above, run:

   ```bash
   make web
   ```

3. Open **http://127.0.0.1:5000**, place an order. The order should go to Aiven Kafka. With Bronze running (from Part 6), it will be written to Bronze.

---

## Checklist (nothing missed)

- [ ] Part 1: Aiven account created; inside one project.
- [ ] Part 2: Kafka service created; plan = **Free**; status = **Running**.
- [ ] Part 3: Topic **`orders`** created.
- [ ] Part 4: Bootstrap URI, SASL username, SASL password, and **ca.pem** downloaded and path/contents noted.
- [ ] Part 5: All 7 env vars written down (or saved).
- [ ] Part 6: Env vars exported in terminal; **`make bronze`** runs and connects.
- [ ] (Optional) Part 7: **`make web`** runs; order reaches Aiven and Bronze.

If any step fails (e.g. “Create service” not found, or no SASL password), check the current Aiven docs: [Create a free tier Kafka service](https://aiven.io/docs/products/kafka/free-tier/create-free-tier-kafka-service) and [Connection information](https://console.aiven.io/).
