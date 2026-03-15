# Run the pipeline in the cloud (free) — no laptop needed

Your website runs on Render; orders go to Aiven Kafka. You want the **pipeline (Bronze → Silver → Gold)** to run **in the cloud on a schedule** so that:

- Someone orders at 3 AM → pipeline runs within ~15–30 min → data is in Bronze/Silver/Gold.
- You wake up and see orders in Gold (and all layers) without using your laptop.

Everything below uses **free tiers** only.

**Production use:** This document is the **single source** for VM + cron setup. Follow the steps in order; each step is written so you (or another operator) can track exactly what was done. A **full runbook (start to end)** is planned once the project is complete — see README and docs/NEXT_STEPS_AND_FUTURE_GOALS.md.

---

## Pros, cons, and edge cases (before you choose)

### Option A: Render Cron (scheduled job on Render)

| | |
|---|--|
| **Pros** | No VM to maintain; same account as your website; simple “run on schedule” in the UI. |
| **Cons** | Render Cron runs **short scripts** (e.g. curl, Node/Python scripts). Your pipeline uses **Spark** (Java, `spark-submit`, heavy). Cron jobs don’t get a full Spark runtime, so **you cannot run this pipeline as-is** on Render Cron. |
| **Edge cases** | Would only work if you rewrote the pipeline to something lightweight (e.g. a small script that reads from Kafka and writes to Postgres without Spark). That’s a different architecture, not “run make pipeline in the cloud.” |

**Verdict:** Not suitable for the current Spark-based pipeline. Use only if you later build a non-Spark “sync” and are okay with that.

---

### Option B: Oracle Cloud Always Free VM + cron (recommended)

| | |
|---|--|
| **Pros** | Full control: same stack as your laptop (Java, Spark, Python). Run `make pipeline` every 15–30 min via cron. **Always Free** tier: VM runs 24/7 at $0 (card for verification only). Enough CPU/RAM for Spark and your volume. Data lives on the VM (or you point to Aiven Postgres and only use VM for compute). |
| **Cons** | You must create an Oracle account, create a VM, install Java/Python/Spark, clone repo, configure `.env` and certs, and set up cron. If the VM stops (Oracle reclaims free tier, or you delete it), pipeline stops until you recreate. You are responsible for OS updates and security. |
| **Edge cases** | **VM reclaimed:** Oracle can reclaim Always Free resources if the tenant is idle or terms change; keep the VM lightly used (cron is enough). **Disk full:** Pipeline writes Parquet under `BASE_PATH`; if disk fills, runs fail — monitor disk or add a cleanup/retention. **Postgres:** If you use Aiven Postgres, Gold/Silver/Bronze can sync there so “seeing data” is in Postgres; if you only have Parquet on the VM, you need SSH or a small dashboard to view. **Cron env:** Cron runs with a minimal environment; set `JAVA_HOME`, `PATH`, and `BASE_PATH` (and source `.env`) in the crontab line or a wrapper script so `spark-submit` and scripts find everything. **Network:** VM must reach Aiven (Kafka, Postgres); outbound internet is allowed by default. |

**Verdict:** Best fit for “run the same pipeline in the cloud for free, no laptop.”

---

### Option 2 (doc): Other free Linux VMs (e.g. GCP, AWS free tier, Fly.io)

| | |
|---|--|
| **Pros** | Same idea as Oracle: full OS, install Spark, run cron. You may already have an AWS/GCP account. |
| **Cons** | Free tiers often **expire** (e.g. 12 months) or have **usage limits**; VM may be smaller or more restricted than Oracle Always Free. |
| **Edge cases** | After free tier ends, VM may stop or bill; read the provider’s free-tier terms. |

---

### Option 3 (doc): GitHub Actions (scheduled workflow)

| | |
|---|--|
| **Pros** | No VM to maintain; runs in GitHub’s runners on a schedule. |
| **Cons** | Runners are **ephemeral**: each run starts fresh. You must store **checkpoints and Parquet in persistent storage** (e.g. S3, or a free object store). Pipeline and scripts must be changed to read/write from that store; more config and secrets (Kafka, storage). |
| **Edge cases** | Free tier minutes limits; large Spark jobs may hit time limits; cold start and download of dependencies each run. |

**Verdict:** Possible but more work; prefer Oracle (or another VM) unless you specifically want “no VM, only Actions + cloud storage.”

---

## Option 1: Oracle Cloud Always Free VM + cron (recommended)

**What you get:** A small Linux VM that runs 24/7 for free. You install the pipeline and run it every 15–30 minutes with cron. Data lives on the VM. No laptop needed.

**Limits:** Oracle Always Free gives e.g. 4 ARM OCPUs + 24 GB RAM (or 2 small AMD VMs). Enough for Spark and your volume.

### Full steps at a glance

1. **Create Oracle account and VM** — Sign up at oracle.com/cloud/free, create an Ubuntu VM (Always Free shape), open SSH (22), note public IP and download SSH key.
2. **Install stack on VM** — Java 17, Python 3, pip, git; clone repo; install Python deps; download and set up Spark.
3. **Configure** — Create `.env` with Kafka (Aiven) and `BASE_PATH`; copy certs or use inline cert env vars; create `BASE_PATH` directory.
4. **Run once by hand** — `./scripts/run_pipeline.sh` to confirm Bronze → Silver → Gold work.
5. **Schedule with cron** — Add a cron line that sets `JAVA_HOME`, `PATH`, `BASE_PATH`, sources `.env`, and runs `./scripts/run_pipeline.sh` every 15 or 30 minutes; log to e.g. `~/pipeline.log`.
6. **See data** — SSH and run `make check-order`, or use Postgres (if synced) / a small dashboard later.

---

### Step-by-step from "Select an image" to pipeline running

Follow these in order. Do not skip a step.

---

#### Step 1 — Select an image (you are here)

- In the **Select an image** list, choose one of these (both are **Free**):

  - **Recommended:** **Canonical Ubuntu 22.04 Minimal aarch64**  
    Use this if you will select an **ARM** shape in the next step (VM.Standard.A1.Flex). That gives you more free RAM (e.g. 12 GB) for Spark.
  - **Alternative:** **Canonical Ubuntu 24.04 Minimal aarch64**  
    Same as above but newer LTS; pick if you prefer 24.04.

- Do **not** pick the non‑aarch64 Ubuntu if you want the larger Always Free ARM shape (A1.Flex). Image and shape must match: **aarch64** image → **ARM** shape; **x64** image → **AMD** shape. The AMD Always Free VM is often very small (e.g. 1 GB RAM), which is not enough for Spark.

- Click **Select image** to continue.

---

#### Step 2 — Name and compartment

- **Name:** e.g. `order-pipeline` (any name you like).
- **Compartment:** Leave default (root or your compartment).
- Click **Next** or continue to **Image and shape**.

---

#### Step 3 — Shape (CPU and memory)

- Click **Change shape**.
- In the shape list, enable **Ampere** (ARM) and/or **Always Free** filter if available.
- Select **VM.Standard.A1.Flex** (Always Free ARM).
- Set **OCPU:** `2` and **Memory (GB):** `12` (or at least 6 GB). More RAM is better for Spark.
- Confirm and go back to the create-instance form.

---

#### Step 4 — Networking

- **Primary VNIC:** Create new VCN and subnet (defaults are fine), or use existing.
- **Public IP:** Ensure **Assign a public IPv4 address** is enabled so you can SSH.
- **Subnet:** Create new or select existing; no need to change defaults.
- **Hostname:** Optional; leave default if you like.

---

#### Step 5 — Add SSH keys

- Choose **Generate a key pair for me** (or **Upload public key** if you already have one).
- If you generate: click **Save private key** and **Save public key** and store them safely (e.g. `~/Downloads`). You need the **private** key to connect.
- Note the **username** shown (for Ubuntu it is usually `ubuntu`).

---

#### Step 6 — Boot volume (optional)

- Defaults are fine. You can increase size if you want (e.g. 100 GB) but not required.

---

#### Step 7 — Create the instance

- Review all settings (image = Ubuntu 22.04 Minimal aarch64 or 24.04, shape = A1.Flex 2 OCPU / 12 GB, public IP, SSH key).
- Click **Create**.
- Wait until **State** is **Running**. Note the **Public IP address** (e.g. `129.xxx.xxx.xxx`).

---

#### Step 8 — Open SSH (port 22) in the cloud network

- In the left menu: **Networking** → **Virtual cloud networks** → select your VCN → **Security Lists** → default security list.
- **Add Ingress Rule:** Source = `0.0.0.0/0`, IP Protocol = TCP, Destination port = `22` (SSH). Save.
- If you use a **firewall** (e.g. iptables) on the instance, allow port 22 there too.

---

#### Step 9 — Connect to the VM

- On your **laptop** (in Terminal), using the private key and public IP:

  ```bash
  chmod 400 /path/to/your-private-key.key
  ssh -i /path/to/your-private-key.key ubuntu@<PUBLIC_IP>
  ```

- Example: `ssh -i ~/Downloads/ssh-key-2026-03-04.key ubuntu@129.153.xxx.xxx`
- Accept the host key if prompted. You should see a shell on the VM (e.g. `ubuntu@order-pipeline:~$`).

---

#### Step 10 — On the VM: install Java, Python, Git

Run these on the VM (one block at a time):

```bash
sudo apt update
sudo apt install -y openjdk-17-jdk python3 python3-pip python3-venv git
```

---

#### Step 11 — On the VM: clone your repo

Replace `YOUR_USERNAME` with your GitHub username (or use your repo URL):

```bash
cd ~
git clone https://github.com/YOUR_USERNAME/realtime-order-medallion.git
cd realtime-order-medallion
```

---

#### Step 12 — On the VM: install Python dependencies

```bash
pip3 install --user pyspark pyyaml confluent-kafka psycopg2-binary python-dotenv
```

(Add any other packages from your `requirements.txt` that the pipeline scripts import.)

---

#### Step 13 — On the VM: install Spark

For **aarch64 (ARM)** you can use the same Apache Spark tarball; it usually works with OpenJDK on ARM:

```bash
cd ~
wget https://archive.apache.org/dist/spark/spark-3.5.0/spark-3.5.0-bin-hadoop3.tgz
tar xzf spark-3.5.0-bin-hadoop3.tgz
echo 'export SPARK_HOME=~/spark-3.5.0-bin-hadoop3' >> ~/.bashrc
echo 'export PATH=$SPARK_HOME/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
```

If the download fails or the binary does not run on ARM, use PySpark only and ensure your pipeline can run with `python` (e.g. using `pyspark` from pip); you may need to adapt `run_pipeline.sh` to use `python` instead of `spark-submit` in that case.

---

#### Step 14 — On the VM: create `.env` and `BASE_PATH`

```bash
cd ~/realtime-order-medallion
mkdir -p /home/ubuntu/medallion_data
nano .env
```

In `nano`, paste the same Kafka and Postgres settings you use on your laptop (Aiven Kafka bootstrap, SSL, topic; `POSTGRES_JDBC_URL` if you use Postgres). Add at least:

```bash
BASE_PATH=/home/ubuntu/medallion_data
```

Set Kafka and Postgres variables exactly as on your laptop. Save (Ctrl+O, Enter) and exit (Ctrl+X).

---

#### Step 15 — On the VM: copy SSL certs from your laptop

From your **laptop** (new terminal), copy certs to the VM (replace paths and IP):

```bash
scp -i /path/to/your-private-key.key \
  /path/to/realtime-order-medallion/certs/ca.pem \
  /path/to/realtime-order-medallion/certs/service.cert \
  /path/to/realtime-order-medallion/certs/service.key \
  ubuntu@<VM_PUBLIC_IP>:~/realtime-order-medallion/certs/
```

On the **VM**, ensure paths in `.env` point to these files, e.g.:

```bash
KAFKA_SSL_CA_LOCATION=/home/ubuntu/realtime-order-medallion/certs/ca.pem
KAFKA_SSL_CERT_LOCATION=/home/ubuntu/realtime-order-medallion/certs/service.cert
KAFKA_SSL_KEY_LOCATION=/home/ubuntu/realtime-order-medallion/certs/service.key
```

(Or use inline cert env vars if your code supports them.)

---

#### Step 16 — On the VM: run the pipeline once by hand

```bash
cd ~/realtime-order-medallion
export BASE_PATH=/home/ubuntu/medallion_data
. ./.env
./scripts/run_pipeline.sh
```

- If it finishes without errors, Bronze → Silver → Gold ran. Check `$BASE_PATH/bronze`, `$BASE_PATH/silver`, `$BASE_PATH/gold` (and Postgres if configured).
- If you see "no new messages" from Kafka, that’s normal if there are no new orders; the pipeline still ran.

---

#### Step 17 — On the VM: ensure `cron_run.sh` exists, then set up cron (production)

**What this does:** Cron runs the pipeline every 10–15 min on the VM automatically. You do this **once**. The wrapper script `cron_run.sh` sets JAVA_HOME, Spark on PATH, BASE_PATH, sources `.env`, and runs the pipeline so cron (which has no login environment) can find `spark-submit` and your config.

**17.1 — Get the cron wrapper from the repo (normal flow)**

The script is part of the repo (no manual paste). On the VM run `git pull`; ensure `scripts/cron_run.sh` is committed and pushed from your laptop so the VM gets it. The repo should contain `scripts/cron_run.sh`. If you cloned before it was added, or your remote doesn’t have it yet, use the fallback block in 17.1b. The canonical source is the repo: commit and push `scripts/cron_run.sh` so every clone/pull gets it.

**Check that the file is there:**
```bash
cd ~/hotel-order-realtime-medallion
ls -la scripts/cron_run.sh
```

If you see the file, run `chmod +x scripts/cron_run.sh` and go to **17.2**. If the file is **missing** (e.g. VM cloned before it was added), use **17.1b** below only then.

**17.1b — Fallback: create the file only if it is missing**

Use this only when the file is not in the repo on the VM. The canonical source is the repo; this is a one-time workaround until you push and pull.

```bash
cd ~/hotel-order-realtime-medallion
cat > scripts/cron_run.sh << 'CRONEOF'
#!/usr/bin/env bash
# Production: cron wrapper — sets JAVA_HOME, Spark on PATH, BASE_PATH, sources .env, runs pipeline.
# Crontab example: */10 * * * * /home/ubuntu/hotel-order-realtime-medallion/scripts/cron_run.sh >> /home/ubuntu/pipeline.log 2>&1
set -e
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"
if [ -z "$JAVA_HOME" ]; then
  for d in /usr/lib/jvm/java-17-openjdk-amd64 /usr/lib/jvm/java-17-openjdk-arm64; do
    if [ -d "$d" ]; then JAVA_HOME="$d"; break; fi
  done
  [ -z "$JAVA_HOME" ] && { echo "JAVA_HOME not set and no java-17 found"; exit 1; }
fi
export PATH="$JAVA_HOME/bin:$PATH"
for s in "$HOME/spark-3.5.0-bin-hadoop3" "$HOME/spark" "$HOME"/spark-*; do
  [ -x "$s/bin/spark-submit" ] 2>/dev/null && export PATH="$s/bin:$PATH" && break
done
export BASE_PATH="${BASE_PATH:-/home/ubuntu/medallion_data}"
[ -f .env ] && set -a && source .env 2>/dev/null && set +a
./scripts/run_pipeline.sh
CRONEOF
chmod +x scripts/cron_run.sh
```

**Verify:** `ls -la scripts/cron_run.sh` — should show executable. Optional: run once by hand: `./scripts/cron_run.sh` to confirm it works before relying on cron.

**17.2 — Install the cron job**

Replace `REPO_PATH` below with your actual repo path on the VM (e.g. `/home/ubuntu/hotel-order-realtime-medallion`).

```bash
chmod +x /home/ubuntu/hotel-order-realtime-medallion/scripts/cron_run.sh
crontab -e
```

If prompted to choose an editor, pick **1** (nano). Add **exactly one** line (choose one schedule):

- Every **10** minutes:  
  `*/10 * * * * /home/ubuntu/hotel-order-realtime-medallion/scripts/cron_run.sh >> /home/ubuntu/pipeline.log 2>&1`
- Every **15** minutes:  
  `*/15 * * * * /home/ubuntu/hotel-order-realtime-medallion/scripts/cron_run.sh >> /home/ubuntu/pipeline.log 2>&1`
- Every **30** minutes:  
  `*/30 * * * * /home/ubuntu/hotel-order-realtime-medallion/scripts/cron_run.sh >> /home/ubuntu/pipeline.log 2>&1`

Save (Ctrl+O, Enter) and exit (Ctrl+X). Cron will run the pipeline on that schedule; you do not need to SSH to trigger it. To run once by hand: `cd ~/hotel-order-realtime-medallion && ./scripts/cron_run.sh` or `./run` if the `run` script exists.

---

#### Step 18 — Verify cron and pipeline

Use these to confirm everything is in place and to track what was done.

| Check | Command / what to see |
|-------|------------------------|
| Cron job installed | `crontab -l` — one line with `cron_run.sh` (or the long inline command). |
| Pipeline log (after one cron run) | `tail -80 /home/ubuntu/pipeline.log` — output from Bronze/Silver/Gold or “no new data” from Kafka. |
| Run once by hand | `cd ~/hotel-order-realtime-medallion && ./scripts/cron_run.sh` (or `./run` if present). |
| Trace an order | `cd ~/hotel-order-realtime-medallion && make check-order ID=web-xxxx` (after env is set). |
| Data on VM | `ls /home/ubuntu/medallion_data/bronze /home/ubuntu/medallion_data/silver /home/ubuntu/medallion_data/gold` — Parquet after orders flow. |
| Data in Postgres | If configured, query `medallion.bronze_orders`, `medallion.silver_orders`, Gold tables in Aiven/Postgres. |

**From your Mac:** `make vm-run` SSHs to the VM and runs the pipeline once (convenience only; it does not replace cron).

#### Troubleshooting: Silver “no new data” / Postgres empty

- **Bronze wrote 0 this run** → Kafka had no new messages. Bronze does not write to Postgres when there is no batch, so no new rows in `medallion.bronze_orders` that run. To backfill Postgres from existing Bronze Parquet on the VM:  
  `cd ~/hotel-order-realtime-medallion && export BASE_PATH=/home/ubuntu/medallion_data && . ./.env && python3 scripts/backfill_postgres_from_parquet.py`  
  (Optional: `... backfill_postgres_from_parquet.py --all` to backfill Silver and Gold from Parquet too.)

- **Silver says “no new Bronze data” but Bronze Parquet has data** → (1) **Root cause (fixed in code):** Bronze used to partition by `_ingestion_date`; Spark’s file source ignores paths starting with `_`, so Silver never saw those files. The project now uses `ingestion_date` (no underscore). Pull latest code so **new** Bronze data is under `ingestion_date=...` and Silver will see it. (2) **Existing data** under `_ingestion_date=...`: on the VM run  
  `mv /home/ubuntu/medallion_data/bronze/orders/_ingestion_date=2026-03-15 /home/ubuntu/medallion_data/bronze/orders/ingestion_date=2026-03-15`  
  (adjust date if needed), then run the pipeline again. (3) **Alternatively**, clear Silver checkpoints so Silver reprocesses all Bronze:  
  `python3 scripts/clean_medallion_data.py --silver-only` then `./scripts/cron_run.sh`  
  Silver will re-read all Bronze files and write to Silver Parquet (and Postgres if `POSTGRES_JDBC_URL` is set).

- **Postgres still empty after pipeline runs** → Confirm `POSTGRES_JDBC_URL` is in the VM’s `.env` and that the VM can reach the Postgres host (`nc -vz <host> <port>`). Then run the backfill command above once to sync existing Parquet → Postgres.

---

### Step 1 (original): Create an Oracle Cloud account and VM

1. Go to [oracle.com/cloud/free](https://www.oracle.com/cloud/free/) and sign up (card for verification; Always Free resources are not charged).
2. In the Oracle Cloud Console: **Compute** → **Instances** → **Create Instance**.
3. Follow **Step-by-step from "Select an image" to pipeline running** above (image → shape → networking → SSH keys → create → then Steps 8–18 on the VM).

### Step 2: On the VM — install Java, Python, Spark, repo

```bash
# Java 17 (required for Spark)
sudo apt update
sudo apt install -y openjdk-17-jdk

# Python 3 + pip
sudo apt install -y python3 python3-pip python3-venv

# Create a directory and clone your repo (use your repo URL)
sudo apt install -y git
cd ~
git clone https://github.com/YOUR_USERNAME/realtime-order-medallion.git
cd realtime-order-medallion
```

Install Python deps (no need for full `make install` if you only run pipeline):

```bash
pip3 install --user pyspark pyyaml confluent-kafka  # add any other deps from requirements.txt that the pipeline needs
```

Install Spark (or use PySpark from pip; the scripts use `spark-submit` so Spark standalone is often easier):

```bash
# Option A: Spark from Apache (use same version as in config, e.g. 3.5 or 4.0)
wget https://archive.apache.org/dist/spark/spark-3.5.0/spark-3.5.0-bin-hadoop3.tgz
tar xzf spark-3.5.0-bin-hadoop3.tgz
echo 'export SPARK_HOME=~/spark-3.5.0-bin-hadoop3' >> ~/.bashrc
echo 'export PATH=$SPARK_HOME/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
```

(This project standardizes on Spark 3.5; use the same version on the VM.)

### Step 3: Configure Kafka and paths on the VM

Create `.env` in the repo root (same as on your laptop, but with paths that exist on the VM):

```bash
cd ~/realtime-order-medallion
nano .env
```

Paste your Aiven Kafka settings (bootstrap, SSL, topic). If you use Postgres for Bronze/Silver/Gold, add `POSTGRES_JDBC_URL` (and any auth) as on your laptop. Set a **persistent base path** (not `/tmp` so it survives reboots):

```bash
BASE_PATH=/home/ubuntu/medallion_data
```

Create the directory:

```bash
mkdir -p /home/ubuntu/medallion_data
```

For SSL certs, either:

- Copy your `ca.pem`, `service.cert`, `service.key` from your laptop to the VM (e.g. `scp` into `~/realtime-order-medallion/certs/`), and in `.env` set:

  ```bash
  KAFKA_SSL_CA_LOCATION=/home/ubuntu/realtime-order-medallion/certs/ca.pem
  KAFKA_SSL_CERT_LOCATION=/home/ubuntu/realtime-order-medallion/certs/service.cert
  KAFKA_SSL_KEY_LOCATION=/home/ubuntu/realtime-order-medallion/certs/service.key
  ```

- Or use the same inline cert env vars you use on Render (`KAFKA_SSL_CA_CERT`, `KAFKA_SSL_CERT`, `KAFKA_SSL_KEY`) if your pipeline/scripts support them.

### Step 4: Run the pipeline once by hand

```bash
cd ~/realtime-order-medallion
export BASE_PATH=/home/ubuntu/medallion_data
./scripts/run_pipeline.sh
```

If this finishes without errors, Bronze/Silver/Gold ran and data is under `$BASE_PATH` (e.g. `$BASE_PATH/gold/`).

### Step 5: Schedule with cron (every 10, 15, or 30 minutes)

**Same as Step 17 above.** Follow **Step 17** in full: ensure `scripts/cron_run.sh` exists (create it from the script block in that section if missing), make it executable, then `crontab -e` and add one line. Use your repo path; examples: `*/10`, `*/15`, or `*/30` for the schedule. Cron then runs the pipeline automatically.

### Step 6: How to “see” orders in the morning

- **SSH and inspect:**  
  `ssh` into the VM and run your existing check script, e.g.  
  `make check-order ID=web-xxxx` (after installing deps and ensuring `PATH`/`JAVA_HOME` are set in cron or in a small wrapper script).

- **Optional — simple dashboard on the VM:**  
  You could run a tiny Flask app on the VM that reads Gold Parquet (or a CSV export) and serves a simple “last orders” page. Then you open `http://<VM_IP>:5001` (or similar) in the browser. (Not covered in this doc; can be a follow-up.)

- **Optional — sync Gold to free Postgres:**  
  Use a free Postgres (Neon, Supabase, etc.), add a job that writes Gold aggregates into it, and use their UI or a small dashboard to view orders. (Also a possible follow-up.)

---

## Option 2: Another free Linux VM (same idea)

If you use another provider (e.g. **Google Cloud** or **AWS** free tier, or **Fly.io** free allowance), the steps are the same:

1. Create a Linux VM / app that can run shell commands.
2. Install Java, Python, Spark, clone repo, configure `.env` and `BASE_PATH`.
3. Run the pipeline on a schedule (cron on the VM, or the provider’s “scheduled job” if it can run a script).
4. Data lives on that VM (or on attached storage). You “see” orders by SSH + script or a small dashboard/sync as above.

---

## Option 3: GitHub Actions (advanced, needs storage)

You can run the pipeline as a **scheduled workflow** (e.g. every 15–30 min) in GitHub Actions. The catch: the runner is ephemeral, so you must store **checkpoints and Parquet** in persistent storage (e.g. S3, or a free object store). That implies:

- Pushing Bronze/Silver/Gold and checkpoints to S3 (or similar) every run.
- Configuring the pipeline to read/write from that store and to use the same checkpoint path so the next run continues correctly.

This is doable but more setup (secrets for Kafka and S3, pipeline config changes). Prefer Option 1 (or 2) unless you specifically want “no VM, only Actions + cloud storage.”

---

## Summary

| Goal                         | Approach                                      |
|-----------------------------|-----------------------------------------------|
| Free, no laptop, see orders in the morning | **Oracle (or any) free VM + cron** (Option 1 or 2). |
| Pipeline runs at 3 AM        | Cron on the VM runs every 10–15–30 min (Step 17). |
| Where data lives            | On the VM under `BASE_PATH` (e.g. Gold in `$BASE_PATH/gold/`). |
| How you see data            | SSH + `make check-order` or a small dashboard/sync (optional). |

No paid services required; only free tiers for VM (and optionally Postgres/object storage if you add dashboard or sync later).

---

## Runbook (planned)

A **full runbook (start to end)** — single document from account creation through verification and common ops — is a project goal and will be created once the project is complete. See **README.md** (Future project goals) and **docs/NEXT_STEPS_AND_FUTURE_GOALS.md**. This document (PIPELINE_IN_CLOUD_FREE.md) is the authoritative step-by-step for VM + cron setup and can be used as the pipeline-in-cloud section of that runbook.
