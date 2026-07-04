# Deploying Vestige to GCP

A step-by-step runbook for provisioning Vestige on a Google Compute Engine VM via Terraform. For the full multi-cloud reference (variables, provisioned resources, cloud-init detail), see `vestige_cloud_deployment.md`. This guide is the practical walkthrough version of that document, scoped to GCP only.

---

## 0. Before You Start

- A GCP account with billing enabled and a project created.
- This deploys an `n2-standard-2` VM by default — check GCP's current free-tier terms if cost matters; this size is unlikely to be free-tier eligible. Tear down (§8) when not actively using it.
- Estimated time: 15–25 minutes for a first deployment.

---

## 1. Install the Local Toolchain (Windows / PowerShell)

Run in an **administrative** PowerShell prompt:

```powershell
winget install Google.CloudSDK
winget install HashiCorp.Terraform
```

Verify:
```powershell
gcloud --version
terraform -v
```

---

## 2. Authenticate with GCP

```powershell
gcloud auth login
```

This opens a browser for interactive login. Then set your default project:

```powershell
gcloud config set project <PROJECT_ID>
```

`<PROJECT_ID>` must be an existing GCP project — create one in the GCP Console first if you haven't.

---

## 3. Generate an SSH Key Pair

```powershell
cd terraform/gcp
ssh-keygen -t rsa -b 4096 -f .\vestige-gcp-key -C "ubuntu"
```

This produces:
- `vestige-gcp-key` (private key)
- `vestige-gcp-key.pub` (public key — Terraform reads this)

Both live in `terraform/gcp/`.

---

## 4. Review Terraform Variables

Check `variables.tf` in `terraform/gcp/` for the authoritative list, but per the blueprint:

| Variable | Type | Default | Description |
|---|---|---|---|
| `project_id` | string | — (**required**, no default) | GCP Project ID |
| `region` | string | `asia-southeast1` | GCP region for deployment |
| `zone` | string | `asia-southeast1-a` | GCP zone for the VM |
| `ssh_user` | string | `ubuntu` | VM admin username |
| `ssh_pub_key_path` | string | `~/.ssh/id_rsa.pub` | Path to the public SSH key |

**Two things to get right before `apply`:**
- `project_id` has no default — you must supply it (matching the project you set in §2).
- `ssh_pub_key_path` defaults to `~/.ssh/id_rsa.pub`, which is **not** the key you just generated in §3 (`terraform/gcp/vestige-gcp-key.pub`). Override this variable to point at the key you actually generated, or copy your generated key to the default path — otherwise Terraform will provision a VM using whatever key happens to already be at `~/.ssh/id_rsa.pub` (or fail if nothing's there).

Copy `terraform.tfvars.example` to `terraform.tfvars` if present, and fill in at minimum:

```hcl
project_id        = "your-actual-project-id"
ssh_pub_key_path  = "./vestige-gcp-key.pub"
```

> I don't have your actual `terraform/gcp/*.tf` files, so confirm the exact variable names in `variables.tf` before relying on the table above.

---

## 5. Initialize, Plan, and Apply

```powershell
terraform init
terraform plan
terraform apply
```

Type `yes` when prompted.

This provisions (per the blueprint):
- An `n2-standard-2` Compute VM running Ubuntu 22.04 LTS, with a 30GB `pd-standard` boot disk
- A VPC (`vestige-vpc`) with auto-created subnetworks
- A firewall rule (`vestige-allow-ssh-http`) opening port 22 (SSH) and port 8080 (Spring Boot API) to `0.0.0.0/0`
- A static public IP (`vestige-static-ip`)

> **Region lock-in warning:** GCP static IP resources are pinned to a single region. If you change the `region` variable *after* your first deployment (e.g. from `us-central1` to `asia-southeast1`), Terraform will throw an API error, because the existing static IP can't move regions. If you need to change region, run `terraform destroy` first (or manually release the external IP) before re-applying with the new region.

On success, Terraform prints a `backend_public_ip` output.

---

## 6. Wait for Cloud-Init to Finish

GCP's bootstrap script differs slightly from AWS/Azure — it installs Docker from the **official Docker CE repository** rather than Ubuntu's `docker.io` package, and creates `/home/<ssh_user>/vestige/logs` directly (not just `/home/<ssh_user>/vestige`). Give it a minute or two, then check:

```powershell
ssh <GCP_SSH_USER>@<GCP_PUBLIC_IP> "cloud-init status --wait"
```

> **If Docker never gets installed:** same root cause as Azure — the `user-data` script must start with `#!/bin/bash` as its literal first line, or GCP's cloud-init silently skips it entirely. Check the first line of the relevant block in `terraform/gcp/main.tf` if this happens.

---

## 7. Deploy the Application

**Copy your config files to the server** (note: no `-i` key flag needed if you've set up an SSH config alias, but the explicit key path works regardless):

```powershell
scp .env docker-compose.yml books_config.json <GCP_SSH_USER>@<GCP_PUBLIC_IP>:/home/<GCP_SSH_USER>/vestige/
```

**SSH in:**

```powershell
ssh <GCP_SSH_USER>@<GCP_PUBLIC_IP>
```

**Edit `docker-compose.yml`** — remove/comment the `build:` blocks under `api`, `scraper`, `scraper-server`:

```bash
cd vestige
nano docker-compose.yml
```

**Edit `.env`** — change any `localhost`/`127.0.0.1` database reference to `postgres`:

```bash
nano .env
```

**Confirm `books_config.json` is a valid object:**

```json
{
  "series": [],
  "books": [],
  "stores": [],
  "tracking": []
}
```

**Start the stack:**

```bash
sudo docker compose up -d
```

**Verify:**

```bash
sudo docker compose ps
curl http://localhost:8080/actuator/health
```

---

## 8. Point Your Desktop App at This Server

**Settings → API base URL** → `http://<GCP_PUBLIC_IP>:8080`.

---

## 9. Ongoing: Retrieving Logs

```powershell
scp -r <GCP_SSH_USER>@<GCP_PUBLIC_IP>:/home/<GCP_SSH_USER>/vestige/logs ./server_logs
```

Or, for raw container logs without needing to `scp` the whole logs directory:

```powershell
ssh <GCP_SSH_USER>@<GCP_PUBLIC_IP> "cd vestige && sudo docker compose logs --no-color" > cloud_docker_logs.txt
```

---

## 10. Tear Down

1. **Grab logs first** (§9), if wanted.
2. **Destroy the infrastructure:**
   ```powershell
   cd terraform/gcp
   terraform destroy
   ```
   Type `yes`.
3. **Manual cleanup:** delete `vestige-gcp-key`/`vestige-gcp-key.pub` from `terraform/gcp/` if you're fully done with the project.

---

## Troubleshooting Notes

- **Docker never installed on first boot:** check the `#!/bin/bash` first-line requirement in §6.
- **`terraform apply` fails with a static-IP region error:** you've hit the region lock-in issue in §5 — destroy first, then re-apply with the new region.
- **SSH connects but `docker` commands fail with "permission denied":** confirm you're using the `ssh_user` value your Terraform config actually provisioned (`ubuntu` by default) — a mismatched username is a common copy-paste error between the three cloud guides, since AWS uses `ubuntu`, Azure uses `azureuser`, and GCP's `ssh_user` variable could be set to either depending on what you configured.
- **`api` container crash-loops against a fresh volume:** same schema-timing note as AWS/Azure — usually self-resolves via `scraper-server`'s health-gate; `SPRING_JPA_HIBERNATE_DDL_AUTO=update` is the documented fallback.

