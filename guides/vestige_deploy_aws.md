# Deploying Vestige to AWS

A step-by-step runbook for provisioning Vestige on AWS EC2 via Terraform. For the full multi-cloud reference (variables, provisioned resources, cloud-init detail), see `vestige_cloud_deployment.md`. This guide is the practical walkthrough version of that document, scoped to AWS only.

---

## 0. Before You Start

- An AWS account with billing enabled.
- This deploys to the **AWS Free Tier** by default (`t3.micro`), but you are responsible for monitoring usage — tear down (§8) when not actively using it.
- Estimated time: 15–25 minutes for a first deployment.

---

## 1. Install the Local Toolchain (Windows / PowerShell)

Run in an **administrative** PowerShell prompt:

```powershell
winget install Amazon.AWSCLI
winget install HashiCorp.Terraform
```

Verify:

```powershell
aws --version
terraform -v
```

---

## 2. Set Up AWS Credentials

**Do not use your AWS root account for this.** Create a dedicated IAM user first:

1. In the AWS Console, go to **IAM → Users → Create user**.
2. Name it something like `vestige-deployer`.
3. Attach permissions sufficient to manage EC2, VPC, and Security Groups (or `AdministratorAccess` if you're comfortable with that for a personal/learning project — narrower is better if you want to practice least-privilege).
4. Under the user's **Security credentials** tab, create an **Access key** (choose "Command Line Interface (CLI)" as the use case).
5. Save the **Access Key ID** and **Secret Access Key** — the secret is shown only once.

Configure the CLI with these credentials:

```powershell
aws configure
```

- **AWS Access Key ID:** (paste yours)
- **AWS Secret Access Key:** (paste yours)
- **Default region name:** `us-east-1`
- **Default output format:** press Enter for default

This writes `~/.aws/credentials`, which Terraform will read automatically.

---

## 3. Create an EC2 Key Pair

Terraform needs an existing key pair to associate with the instance — it doesn't generate one for you.

1. In the AWS Console, go to **EC2 → Key Pairs → Create key pair**.
2. Name it `vestige-key` (matching the name referenced in `vestige_cloud_deployment.md` §2B — check your `terraform/aws` variables if you used a different name).
3. Choose `.pem` format.
4. Download it, and move it into your project root (the same folder you'll run Terraform commands from).

**Lock down the key's permissions on Windows** (OpenSSH will refuse to use an over-permissive key):

```powershell
icacls .\vestige-key.pem /inheritance:r
icacls .\vestige-key.pem /grant:r "$($env:USERNAME):(F)"
```

---

## 4. Review Terraform Variables

```powershell
cd terraform/aws
```

Check `variables.tf` for the exact variable names and defaults your version defines. Per the blueprint, the region defaults to `us-east-1`. If a `terraform.tfvars.example` exists in this folder, copy it:

```powershell
cp terraform.tfvars.example terraform.tfvars
```

Fill in whatever it asks for (key pair name, region override, etc.) — **do not commit `terraform.tfvars`**, it's gitignored for a reason if it holds anything sensitive.

> I don't have your actual `terraform/aws/*.tf` files, so I can't confirm every variable name here — check `variables.tf` directly for the authoritative list before filling in `terraform.tfvars`.

---

## 5. Initialize, Plan, and Apply

```powershell
terraform init
terraform plan
terraform apply
```

- `init` downloads the AWS provider (`hashicorp/aws ~> 5.0`) and sets up local state.
- `plan` shows exactly what will be created — review it before proceeding.
- `apply` will prompt for confirmation; type `yes`.

This provisions (per the blueprint):

- A `t3.micro` EC2 instance running Ubuntu 24.04, with a 25GB `gp3` root volume
- A security group (`vestige-backend-sg`) opening port 22 (SSH) and port 8080 (Spring Boot API) to `0.0.0.0/0`
- The default VPC

On success, Terraform prints a `backend_public_ip` output — copy it, you'll need it repeatedly below.

---

## 6. Wait for Cloud-Init to Finish

The instance's first-boot script (cloud-init) needs a minute or two after `apply` completes to:

1. Create a 2GB swap file
2. Install Docker (`docker.io` + the `docker-compose-v2` plugin)
3. Create `/home/ubuntu/vestige`

You can watch for it to finish via SSH:

```powershell
ssh -i vestige-key.pem ubuntu@<EC2_PUBLIC_IP> "cloud-init status --wait"
```

This blocks until cloud-init reports `done`.

---

## 7. Deploy the Application

**Copy your config files to the server:**

```powershell
scp -i vestige-key.pem .env docker-compose.yml books_config.json ubuntu@<EC2_PUBLIC_IP>:/home/ubuntu/vestige/
```

**SSH in:**

```powershell
ssh -i vestige-key.pem ubuntu@<EC2_PUBLIC_IP>
```

**On the server, edit `docker-compose.yml`:**

```bash
cd vestige
nano docker-compose.yml
```

Remove (or comment out) the `build:` blocks under `api`, `scraper`, and `scraper-server` — the cloud server pulls prebuilt images from GHCR, it doesn't build from source.

**Edit `.env`:**

```bash
nano .env
```

Any database URL referencing `localhost` or `127.0.0.1` must be changed to `postgres` (the container's service name inside the Compose network).

**Confirm `books_config.json` is a valid object, not an empty array:**

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

**Verify it's running:**

```bash
sudo docker compose ps
curl http://localhost:8080/actuator/health
```

---

## 8. Point Your Desktop App at This Server

In the Vestige desktop app: **Settings → API base URL** → `http://<EC2_PUBLIC_IP>:8080`.

Since this points at a non-local address, the Docker-lifecycle auto-start/stop feature won't engage — that's expected, it's scoped to `localhost`/`127.0.0.1` only.

---

## 9. Ongoing: Retrieving Logs

**Option A: Download Physical Log Files**

```powershell
scp -i vestige-key.pem -r ubuntu@<EC2_PUBLIC_IP>:/home/ubuntu/vestige/logs ./server_logs
```

**Option B: Export Live Docker Container Output**

```powershell
ssh -i vestige-key.pem ubuntu@<EC2_PUBLIC_IP> "cd vestige && sudo docker compose logs --no-color" > cloud_docker_logs.txt
```

---

## 10. Tear Down

**Don't leave this running when you're not using it** — even Free Tier resources are worth cleaning up.

1. **Grab logs first** (§9), if you want them.
2. **Destroy the infrastructure:**
    ```powershell
    cd terraform/aws
    terraform destroy
    ```
    Type `yes` to confirm.
3. **Manual cleanup** (Terraform doesn't own these): delete the `vestige-key` Key Pair and the `vestige-deployer` IAM user from the AWS Console if you're fully done with the project, to avoid orphaned credentials.

---

## Troubleshooting Notes

- **`api` container won't start against a fresh volume:** Hibernate's `validate` ddl mode expects the schema to already exist. This usually self-resolves because `scraper-server`'s own SQLAlchemy startup creates the schema first, and `api` waits on `scraper-server` being healthy. If it doesn't self-resolve, `SPRING_JPA_HIBERNATE_DDL_AUTO=update` is the documented one-time fallback — switch it back to `validate` afterward.
- **Can't SSH in:** double-check the `icacls` permission steps in §3 — Windows OpenSSH silently refuses a `.pem` file with overly broad permissions.
- **`docker compose pull` doesn't seem to update anything:** it only refreshes the local image cache — you need an explicit `docker compose up -d` (or `--force-recreate`) afterward to actually restart containers on the new image.

