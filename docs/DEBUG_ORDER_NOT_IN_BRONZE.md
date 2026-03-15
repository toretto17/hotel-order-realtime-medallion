# Debug: Order not showing in Bronze / Kafka connection issues

When an order (e.g. `web-567ebca2749c`) doesn’t appear in Bronze or Silver, work through these steps.

---

## 1. Run the order check on the correct machine

The order check must run **where the pipeline runs** (the VM), with **that machine’s BASE_PATH**.

- **On your Mac:** The script uses `BASE_PATH` from the environment; default is `/tmp/medallion`. So you were checking **local** Parquet, not the VM’s. Result “NOT FOUND” there does **not** mean the order is missing on the VM.
- **On the VM:** Use the VM’s data path.

**On the VM (SSH in first, e.g. `make login-ssh`):**

```bash
cd ~/hotel-order-realtime-medallion
export BASE_PATH=/home/ubuntu/medallion_data
set -a && [ -f .env ] && source .env && set +a
python3 scripts/check_order_in_medallion.py web-567ebca2749c
```

Interpretation:

- **FOUND in Bronze, NOT in Silver** → Kafka and Bronze are fine; Silver didn’t see the new file (run pipeline again or see pipeline troubleshooting).
- **NOT FOUND in Bronze** → Either the order never reached Kafka (website/producer), or the VM consumer (Bronze) can’t connect or is misconfigured. Continue below.

---

## 2. Website → Kafka (producer): did the order reach the topic?

The website (e.g. on Render) produces to **Aiven Kafka** using env vars. If any of these are wrong or missing, the app may still return “Order received” but the message never reaches Kafka.

**On Render (or wherever the web app runs):**

1. **Env vars (must all be set):**
   - `KAFKA_BOOTSTRAP_SERVERS` — same Aiven Kafka URI (e.g. `...aivencloud.com:19413`).
   - `KAFKA_SECURITY_PROTOCOL=SSL`
   - `KAFKA_TOPIC=orders`
   - For SSL client cert (Aiven): **one** of:
     - **File paths** (only if the host has the files): `KAFKA_SSL_CA_LOCATION`, `KAFKA_SSL_CERT_LOCATION`, `KAFKA_SSL_KEY_LOCATION`, or  
     - **PEM content** (typical on Render): `KAFKA_SSL_CA_CERT`, `KAFKA_SSL_CERT_CERT`, `KAFKA_SSL_KEY_CERT` (full PEM strings, with `\n` for newlines if pasted in UI).

2. **If the site shows an error** when placing an order (e.g. 502 or “Failed to send order”), the producer failed. Check Render logs and the env vars above.

3. **Quick producer test from your Mac** (same Kafka as website):  
   From project root with `.env` pointing at Aiven:
   ```bash
   make test-kafka
   ```
   If this succeeds, Aiven Kafka is reachable and credentials work from your network. Then confirm the **website** uses the **exact same** `KAFKA_BOOTSTRAP_SERVERS` and the same certs (for the same Aiven service).

---

## 3. VM → Kafka (consumer): can Bronze connect to Aiven?

Bronze on the VM reads from the **same** Aiven Kafka topic `orders`. If the VM can’t connect or uses wrong certs, it will see no new messages.

**On the VM:**

1. **Env and cert paths** in the VM’s `.env`:
   - `KAFKA_BOOTSTRAP_SERVERS` — same as website (e.g. `...aivencloud.com:19413`).
   - `KAFKA_SSL_CA_LOCATION`, `KAFKA_SSL_CERT_LOCATION`, `KAFKA_SSL_KEY_LOCATION` — paths to files **on the VM** (e.g. `/home/ubuntu/hotel-order-realtime-medallion/certs/ca.pem`).  
   Certs must be the same Aiven Kafka service (ca.pem, service.cert, service.key).

2. **Test Kafka from the VM** (no Spark):
   ```bash
   cd ~/hotel-order-realtime-medallion
   set -a && source .env && set +a
   python3 scripts/test_kafka_connection.py
   ```
   - If this **fails**: fix VM’s Kafka config (bootstrap, SSL paths, cert files).  
   - If this **succeeds**: VM can talk to Aiven; then the issue is either (a) no messages in the topic when Bronze ran, or (b) Bronze/Spark config (e.g. wrong topic or starting offset).

3. **Topic and offset:** Bronze uses topic `orders` and by default `startingOffsets: latest`. So it only sees messages produced **after** the job started. If the website sent the order **before** you started Bronze (or before the last time Bronze ran), that message may already be “past” for this run. Either produce a **new** order after Bronze is running (or after you run the pipeline), or temporarily set `KAFKA_STARTING_OFFSETS=earliest` and run Bronze again (then set back to `latest` if you don’t want to reprocess old data).

---

## 4. Checklist summary

| Check | Where | Action |
|-------|--------|--------|
| Order in Bronze/Silver? | **VM** | `export BASE_PATH=/home/ubuntu/medallion_data` then `python3 scripts/check_order_in_medallion.py <order_id>` |
| Kafka reachable + credentials | Mac or VM | `source .env` then `python3 scripts/test_kafka_connection.py` |
| Website Kafka env | Render | Same `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_TOPIC=orders`, SSL certs (paths or PEM vars) |
| VM Kafka env | VM `.env` | Same bootstrap; SSL cert **paths** pointing to cert files on VM |
| New order after Bronze | - | Place order **after** starting pipeline (or run pipeline after placing order) so Bronze sees the message |

---

## 5. If the website is on Render

See **docs/RENDER_WEBSITE_HOSTING_STEP_BY_STEP.md**: Render cannot use file paths for certs. You must set:

- `KAFKA_SSL_CA_CERT` = full CA PEM string  
- `KAFKA_SSL_CERT_CERT` = full client cert PEM string  
- `KAFKA_SSL_KEY_CERT` = full client key PEM string  

(Exact names depend on what `web/app.py` reads; see `_kafka_producer_config()` and use the same env var names.)

If any of these are missing or wrong, the website may still respond “Order received” (e.g. if it saved to SQLite) but the produce to Kafka can fail; check Render logs for errors during order submit.
