# Deploying Vestige to Azure

A step-by-step runbook for provisioning Vestige on an Azure VM via Terraform. For the full multi-cloud reference (variables, provisioned resources, cloud-init detail), see `vestige_cloud_deployment.md`. This guide is the practical walkthrough version of that document, scoped to Azure only.

---

## 0. Before You Start

- An Azure account with an active subscription.
- This deploys a `Standard_D2s_v5` VM by default — **not** covered by Azure's free tier the way AWS's `t3.micro` is, so cost accrues from the moment `apply` finishes. Tear down (§8) when not actively using it.
- Estimated time: 15–25 minutes for a first deployment.

---

## 1. Install the Local Toolchain (Windows / PowerShell)

Run in an **administrative** PowerShell prompt:

```powershell
winget install Microsoft.AzureCLI
winget install HashiCorp.Terraform
```

Verify:

```powershell
az --version
terraform -v
```

---

## 2. Authenticate with Azure

```powershell
az login
```

This opens a browser for interactive login.

If you have more than one subscription, set the one you want to deploy into:

```powershell
az account set --subscription <SUBSCRIPTION_ID>
```

(You can find your subscription ID via `az account list --output table`.)

---

## 3. Generate an SSH Key Pair

Unlike AWS's console-managed key pairs, Azure expects you to generate your own SSH key and hand Terraform the public half.

```powershell
cd terraform/azure
ssh-keygen -t rsa -b 4096 -f .\vestige-azure-key -C "azureuser"
```

Press Enter through the prompts (a passphrase is optional — leave blank for simplicity, or set one if you prefer). This produces two files in `terraform/azure/`:

- `vestige-azure-key` (private key — never share this)
- `vestige-azure-key.pub` (public key — this is what Terraform reads)

---

## 4. Review Terraform Variables

Check `variables.tf` in `terraform/azure/` for the authoritative list, but per the blueprint these are the two documented configurable variables:

| Variable         | Type   | Default         | Description                 |
| ---------------- | ------ | --------------- | --------------------------- |
| `location`       | string | `southeastasia` | Azure region for deployment |
| `admin_username` | string | `azureuser`     | Azure VM admin username     |

If a `terraform.tfvars.example` exists, copy it to `terraform.tfvars` and adjust as needed. `location` is worth double-checking against your own region if `southeastasia` isn't the closest/cheapest one for you.

> I don't have your actual `terraform/azure/*.tf` files, so treat the table above as what the blueprint documents, not a guarantee your specific `variables.tf` matches exactly — check it directly.

---

## 5. Initialize, Plan, and Apply

```powershell
terraform init
terraform plan
terraform apply
```

Type `yes` when prompted.

This provisions (per the blueprint):

- A `Standard_D2s_v5` Linux VM running Ubuntu 22.04 LTS, with a 30GB `Standard_LRS` OS disk
- A Virtual Network (`vestige-network`, `10.0.0.0/16`) with an `internal` subnet (`10.0.2.0/24`)
- A Network Security Group (`vestige-nsg`) opening port 22 (SSH) and port 8080 (Spring Boot API) to `0.0.0.0/0`
- A static Standard SKU Public IP

> **Why `Standard_D2s_v5` and not a cheaper burstable size?** The blueprint notes that `Standard_B1s`/`Standard_B2s` deployments failed in this project due to Azure capacity restrictions in multiple regions — `D2s_v5` was the size that reliably provisioned. If you want to try a cheaper size, be aware you may hit the same regional capacity issue.

On success, Terraform prints a `backend_public_ip` output.

---

## 6. Wait for Cloud-Init to Finish

The `custom_data` script needs a minute or two after `apply` to:

1. Create a 2GB swap file
2. Install Docker (`docker.io` + `docker-compose-v2`)
3. Create `/home/ubuntu/vestige`

Check via SSH:

```powershell
ssh -i vestige-azure-key azureuser@<AZURE_PUBLIC_IP> "cloud-init status --wait"
```

> **If Docker never gets installed:** this almost always means the `custom_data` heredoc in the Terraform config is missing `#!/bin/bash` as the literal first line. Azure's cloud-init silently skips the entire script if that shebang isn't present — no error, no log entry pointing at it, Docker just never appears. This was a confirmed bug during this project's own Azure rollout (see `vestige_archive_history_catalog.md` v3.5) — if you're hitting it again, check the very first line of the `custom_data`/`user_data` block in `terraform/azure/main.tf`.

---

## 7. Deploy the Application

**Copy your config files to the server:**

```powershell
scp -i vestige-azure-key .env docker-compose.yml books_config.json azureuser@<AZURE_PUBLIC_IP>:/home/ubuntu/vestige/
```

**SSH in:**

```powershell
ssh -i vestige-azure-key azureuser@<AZURE_PUBLIC_IP>
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

**Settings → API base URL** → `http://<AZURE_PUBLIC_IP>:8080`.

---

## 9. Ongoing: Retrieving Logs

**Option A: Download Physical Log Files**

```powershell
scp -i vestige-azure-key -r azureuser@<AZURE_PUBLIC_IP>:/home/ubuntu/vestige/logs ./server_logs
```

**Option B: Export Live Docker Container Output**

```powershell
ssh -i vestige-azure-key azureuser@<AZURE_PUBLIC_IP> "sudo docker compose -f ~/vestige/docker-compose.yml logs --no-color" > cloud_docker_logs.txt
```

---

## 10. Tear Down

1. **Grab logs first** (§9), if wanted.
2. **Destroy the infrastructure:**
    ```powershell
    cd terraform/azure
    terraform destroy
    ```
    Type `yes`.
3. **Delete the orphaned Network Watcher resource group** — Azure creates this automatically alongside any VNet-having deployment, and `terraform destroy` does not remove it since Terraform never created it in the first place:
    ```powershell
    az group delete --name NetworkWatcherRG --yes --no-wait
    ```
4. **Manual cleanup:** delete `vestige-azure-key`/`vestige-azure-key.pub` from `terraform/azure/` if you're fully done with the project.

---

## Troubleshooting Notes

- **Docker never installed on first boot:** see the `#!/bin/bash` shebang note in §6 — this is the single most likely cause.
- **Provisioning fails with a capacity/SKU error:** try a different Azure region via the `location` variable — regional capacity for specific VM sizes fluctuates.
- **`api` container crash-loops against a fresh volume:** same schema-timing note as AWS — usually self-resolves via `scraper-server`'s health-gate; `SPRING_JPA_HIBERNATE_DDL_AUTO=update` is the documented fallback.

