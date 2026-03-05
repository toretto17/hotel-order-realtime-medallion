# Order flow, timing, and Kafka + SSL (plain English)

This doc answers: what happens when you order from the website, when you can run Bronze/Silver/Gold, and how Kafka connection and SSL work (and how we fixed the "bad certificate" issue). It also clarifies what is production-level vs what you’d add at scale.

---

## 1. What happens when you order from the website? Is Kafka running continuously?

**In simple terms:**

1. **You open the website** (Flask app, e.g. `make web` or hosted on Render). The app must be running for you to place an order.

2. **You place an order.** The website sends that order as a **message** to **Kafka** (the message broker). So: **Browser → Flask app → Kafka topic `orders`**.

3. **Kafka stores the message.** Kafka is like a durable log: it keeps every message until its **retention period** (e.g. 7 days). So the order sits in the topic until something reads it.

4. **Who runs Kafka?**  
   This project uses **Aiven Kafka** only (no local Docker). Kafka runs **in the cloud** (Aiven's servers). It runs **continuously**. You don't start/stop it; Aiven does. When you order from your website, the message goes over the internet to Aiven Kafka and is stored there.

5. **Bronze job** is a **consumer**: it reads from the Kafka topic and writes to Bronze (e.g. Parquet). It does **not** need to be running at the exact moment you order. Kafka holds the messages; Bronze can read them later.

**Summary:** When you order, the order is sent to Kafka and stored. Kafka (on Aiven) runs all the time. Your Bronze job can run later; it will read those stored messages.

---

## 2. If I run Bronze 15–20 minutes later, will those orders be processed correctly?

**Yes.** Kafka keeps messages for a **retention period** (often 7 days by default; Aiven free tier has its own retention). So:

- You place orders at 10:00.
- You run Bronze at 10:20 (or 2 hours later, or next day).
- Bronze connects to Kafka and reads from the topic. It will see all messages that arrived since the last time it read (or from the beginning if it’s a new consumer group). Those orders will be processed and written to Bronze without any issue.

There is **no requirement** that Bronze runs “immediately” after each order. The only requirement is that you run Bronze **before** Kafka deletes old messages (i.e. within retention).

---

## 3. Can I run Silver and Gold anytime later? Any issue?

**Yes. No time limit from Kafka’s side.**

- **Silver** reads from **Bronze** (Parquet files on disk/S3), **not** from Kafka. So you run Silver **after** Bronze has written data. You can run it 1 minute later or 1 day later. The only order is: **Bronze first**, then Silver.

- **Gold** reads from **Silver** (Parquet). Run it **after** Silver has written data. Again, 1 hour or 1 day later is fine.

So the pipeline order is: **Bronze → Silver → Gold**. When you run each step can be “anytime later” as long as the previous step has already produced data.

---

## 4. Is there a timeframe after which orders are “invalid” or not processed?

**No.** Our pipeline does **not** invalidate or reject records because “too much time has passed.”

The only real limit is **Kafka’s retention**:

- Kafka keeps messages for a configured time (e.g. 7 days) or size. After that, it **deletes** old messages.
- If you run Bronze **before** retention expires, all orders in the topic are still there and will be processed.
- If you run Bronze **after** retention, messages that were deleted will never be read. So the “timeframe” is: **run Bronze before Kafka deletes the messages** (within retention). There is no extra “validation window” in our code.

### 4.1 Backfill with “earliest” but some orders still missing?

If you ran **`make clean-bronze`** and **`KAFKA_STARTING_OFFSETS=earliest make bronze`** and still don’t see certain orders (e.g. ones placed “during deployment”):

- **Most likely: Kafka retention** — The topic only keeps messages for a limited time (or size). On Aiven free tier, retention can be **24 hours or less**. Those orders were produced earlier; by the time you ran the backfill, Kafka had **already deleted** the oldest messages. So “earliest” means the earliest message **still in the topic**, not “all orders ever.”
- **What you can do:** Check retention in Aiven Console (topic `orders` → settings). For future orders: run Bronze soon after they’re placed, or keep Bronze running so it consumes continuously.

---

## 5. How Kafka connection and SSL work (what we did and why)

### 5.1 What is Kafka (broker)?

Kafka is a **distributed log**. **Producers** (e.g. your Flask app) send messages to **topics**. **Consumers** (e.g. Bronze Spark job) read from topics. The **broker** is the Kafka server that stores and serves the data. To talk to the broker, your client (Flask or Spark) must:

1. Know **where** it is (bootstrap address: host and port).
2. Use a **secure connection** if the broker requires it (TLS/SSL).
3. **Authenticate** (prove who it is) if the broker requires it.

### 5.2 Ways to connect and authenticate

| Style | What it means | When used |
|-------|----------------|-----------|
| **Plain (no security)** | Just host:port. No encryption, no auth. | Not used in this project (Aiven only). |
| **SSL/TLS** | Encrypted channel. The **server** has a certificate; the **client** verifies it using a **CA certificate** (e.g. `ca.pem`). So the client trusts the server. | Any time you don’t want traffic in clear text. |
| **Client certificate (mutual TLS)** | Same as SSL, but the **server** also requires the **client** to present a certificate. So: client trusts server (via CA), server trusts client (via client cert + key). **No username/password.** | Aiven free tier when “SASL” is not available; very common in production. |
| **SASL** | Username + password (e.g. SCRAM-SHA-256). Often combined with TLS: **SASL_SSL** = encrypted channel + password auth. | When the provider gives you a user/password for Kafka. |

### 5.3 What Aiven gave you

- **Bootstrap address:** e.g. `order-medallion-kafka-....aivencloud.com:19413` → this is **KAFKA_BOOTSTRAP_SERVERS**.
- **CA certificate** (`ca.pem`): used by the **client** to verify that it is really talking to Aiven’s Kafka (and not someone in the middle).
- **Client certificate** (`service.cert`) and **private key** (`service.key`): so that the **broker** can authenticate **your** client. “This connection is allowed because the client presented a valid certificate.”

On the free tier, the **SASL** tab for Kafka was disabled. So you could **not** use username/password for the Kafka broker. You could only use **client certificate (SSL)**. The username/password you saw were for **Schema Registry** (a different service); we don’t use that for the Kafka broker in this project.

### 5.4 What was the “bad certificate” issue?

- We had **KAFKA_SECURITY_PROTOCOL=SASL_SSL** in `.env`. So the client was saying: “I want to connect with TLS **and** authenticate with SASL (username/password).”
- Aiven’s Kafka (with SASL disabled) was configured to accept **only client certificate** auth. So the broker expected: TLS + a valid **client certificate**. It did **not** expect SASL.
- When the client tried to connect with SASL_SSL (and possibly wrong or missing SASL credentials), the broker rejected the connection and sent an SSL alert: **“bad certificate”** (alert number 42). That means: “The way you’re trying to authenticate doesn’t match what I accept.”

So the **issue** was: wrong auth mode (SASL_SSL vs SSL with client cert) and/or wrong credentials for what the broker expected.

### 5.5 How we fixed it

We switched to **client-certificate-only** auth:

1. **KAFKA_SECURITY_PROTOCOL=SSL** (not SASL_SSL). So we use TLS and **no** SASL.
2. **Three files** in config:
   - **ca.pem** → client uses this to **verify the broker** (truststore).
   - **service.cert** → client sends this to the broker so the broker can **identify the client** (keystore / certificate chain).
   - **service.key** → client’s private key; used to prove it owns `service.cert` (keystore key).

In code:

- **Flask / test script (confluent_kafka):** We set `security.protocol=SSL`, `ssl.ca.location=ca.pem`, `ssl.certificate.location=service.cert`, `ssl.key.location=service.key`. So the producer/consumer use **mutual TLS**: encrypted channel + client cert, no password.
- **Bronze (Spark Kafka connector):** We pass the same idea via options: `kafka.security.protocol=SSL`, `kafka.ssl.truststore.location=ca.pem`, `kafka.ssl.keystore.type=PEM`, `kafka.ssl.keystore.certificate.chain=service.cert`, `kafka.ssl.keystore.key=service.key`. So Spark also connects with **SSL + client certificate**.

After that, the broker accepted the connection and the test (produce + consume) succeeded.

### 5.6 Short diagram (conceptually)

```
Your app (Flask or Spark)
    │
    │ 1. Connect to bootstrap (host:port)
    │ 2. TLS handshake:
    │    - Server sends its certificate → you verify with ca.pem
    │    - You send service.cert + proof you have service.key
    │ 3. Broker checks your cert → OK → connection allowed
    │
    ▼
Aiven Kafka (broker)
```

No username/password is sent; identity is done via certificates.

---

## 6. Order ID convention (consistent across website and producer)

All order IDs use a **`web-` prefix** so everything is consistent (website-only or website + bulk producer).

| Source | Format | Example |
|--------|--------|---------|
| **Website** (user places order) | `web-` + 12 hex chars (UUID) | `web-a1b2c3d4e5f6` |
| **Producer** (`make produce` or `make produce-orders`) | `web-bulk-` + 8 digits | `web-bulk-00000001`, `web-bulk-00000111` |

- **Website:** Each order gets a unique ID like `web-` + 12-character hex (from UUID). No collision with bulk IDs.
- **Producer (bulk test data):** Order IDs are `web-bulk-00000001`, `web-bulk-00000002`, … so they match the “web order” convention and stay unique. After a full clean, the next run starts from `web-bulk-00000001` again.

Silver and Gold treat `order_id` as an opaque string; they don’t care whether it came from the website or the producer. Consistency is just: **every order has a single, unique `order_id` with the same `web-*` style.**

---

## 7. Full restart (remove all records from Bronze, Silver, Gold)

To **clear everything** and start fresh (e.g. after changing order ID format or for a clean demo):

1. **Stop** any running Bronze, Silver, or Web terminals (Ctrl+C).
2. From project root run:
   ```bash
   make clean-data
   ```
   (You can also use **`make clean`** — it does the same thing.)
   This removes:
   - All **Bronze** data and Bronze checkpoint
   - All **Silver** data and Silver checkpoints
   - All **Gold** data
   - The **producer state file** (`.produce_orders_last_id`) so the next `make produce-orders` starts from `web-bulk-00000001` again
3. **Optional (Aiven):** Kafka topic `orders` still has old messages until retention expires. If you want a truly fresh start and you control the topic, you can create a new topic or wait for retention.
4. Then follow **§7.1 Start again after clean** below.

So: **`make clean`** or **`make clean-data`** = restart everything (all layers + producer counter). After that, new orders (website or producer) use the same `web-*` order ID convention.

### 7.1 Start again after clean (step by step)

**If you use Aiven Kafka** (your `.env` has `KAFKA_BOOTSTRAP_SERVERS=...aivencloud.com` and SSL/cert paths):

- **Do not run `make kafka-up`.** Kafka runs on Aiven’s servers; you don’t start Kafka locally.

1. **Load your env** (from project root):
   ```bash
   set -a && source .env && set +a
   ```
   (On some shells: `export $(grep -v '^#' .env | xargs)`.)

2. **Optional — wait for Aiven to be reachable:**  
   `make wait-kafka`  
   (The wait script uses your `.env` and SSL/certs when talking to Aiven. If Aiven was sleeping, power it on in the console first.)

3. **Create topic** (if not already there):  
   `make topics-create`

4. **Terminal 1 — Bronze (leave running):**  
   `make bronze`

5. **Terminal 2 — Send orders:** either  
   - **Website:** `make web` → open http://127.0.0.1:5000 and place orders, or  
   - **Bulk test:** `make produce` (one order) or `make produce-orders N=50` (50 orders)

6. **After Bronze has data** (wait a trigger or a minute), in **Terminal 3:**  
   `make silver`

7. **After Silver has data:**  
   `make gold`

(This project uses Aiven Kafka only; no local Docker Kafka.)

6. **Terminal 3 — Silver, then Gold:**  
   `make silver` then `make gold`

---

## 8. Is this production-level code?

**What is already production-oriented:**

- **Architecture:** Medallion (Bronze/Silver/Gold), clear separation of raw / cleaned / aggregated.
- **Streaming:** Checkpointing, `failOnDataLoss=true` so we don’t silently skip data when offsets change.
- **Security:** TLS and client certificate support for Kafka; no hardcoded secrets; config and credentials via env and `.env` + certs in one place.
- **Operability:** Single config file (`pipeline.yaml`) with env substitution; same code path for local and Aiven.

**What a staff/senior data engineer would add for “big” production:**

| Area | What we have | What you’d add at scale |
|------|----------------|---------------------------|
| **Secrets** | `.env` + cert files on disk | Secrets manager (e.g. AWS Secrets Manager, Vault); short-lived creds; no certs on disk in prod. |
| **Monitoring** | Logs and manual checks | Metrics (consumer lag, throughput, error rate), alerting, dashboards, health endpoints. |
| **CI/CD** | Manual run | Automated tests, deploy pipelines, rollback, canary. |
| **Scale** | Single consumer, default partitions | Tune partitions and consumer parallelism; backpressure; resource limits for Spark. |
| **Schema / governance** | JSON in Kafka | Schema Registry (Avro/Protobuf), contracts, lineage. |
| **Resilience** | Basic retries | DLQ, circuit breakers, idempotent writes, exactly-once where needed. |

So: the **patterns and security** (Kafka + SSL, config, medallion, checkpointing) are production-level. The **operational hardening** (secrets manager, observability, automation) is what you’d layer on for a large, critical pipeline.

---

## Quick reference

| Question | Answer |
|----------|--------|
| When I order, must Kafka be running? | Yes. With Aiven, Kafka runs in the cloud all the time. |
| Can I run Bronze 15–20 mins later? | Yes. Kafka keeps messages; Bronze will read them. |
| Can I run Silver/Gold anytime? | Yes, after Bronze (or Silver) has written data. |
| Time limit for “valid” orders? | No; only limit is Kafka retention (run Bronze before messages are deleted). |
| Why “bad certificate”? | Broker expected client cert (SSL); we used SASL_SSL. Fix: use SSL + the three cert files. |
| Order ID format? | Website: `web-{12 hex}`. Producer: `web-bulk-{8 digits}`. All use `web-*` prefix. |
| How to restart everything? | `make clean-data` (removes Bronze, Silver, Gold, checkpoints, producer state). |
| Production-level? | Yes for design and security; add secrets manager, monitoring, and automation for scale. |
