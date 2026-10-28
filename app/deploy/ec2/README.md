# Vanimo on one EC2 instance, set up by hand (F11 + F13)

The low-cost MVP deployment for **synthetic data only** (`docs/03` §0.1): one Graviton instance running
Docker Compose (Postgres 18, API, web), Claude on Bedrock, and the three redaction backstops (Comprehend,
Bedrock Guardrails, Macie) for real. **No Entra, Graph, Outlook add-in or Teams**: every account signs in
with email + password and gets the "Kestrel Analytics" sample workspace. No inbound ports: the founder
opens the app through an SSM tunnel at `http://localhost:8080`.

The founder builds it by hand (console, CloudShell, AWS CLI) to learn AWS (F13, 2026-10-22), instead of
`cdk deploy`. The JSON files in `aws/` are exactly what the CDK stacks would create, generated from the
same definitions (`uv run python -m vanimo_infra.manual` in `app/infra`; a test fails if they drift).
The production cell (`app/infra`) is unchanged and still comes before any real mailbox data.

| File | What it is |
|---|---|
| `compose.yml` | The four containers; `.env.example` lists what `.env` must hold |
| `Caddyfile` | Web server: the built app, `/api/*` to the API, security headers |
| `aws/guardrail.json` | Bedrock guardrail: every PII type + Indian identifier regexes, all BLOCK |
| `aws/bucket-policy.json`, `aws/bucket-lifecycle.json` | L1 snapshot bucket: TLS only, SSE-S3 writes only, readable by Macie alone, 3-day expiry |
| `aws/macie-*.json` | Macie custom data identifiers (Aadhaar, PAN, GSTIN, IFSC, UPI, voter ID) |
| `aws/app-policy.json` | The instance role's permissions: Claude, Comprehend, the guardrail, snapshot writes, Macie findings |
| `compose.build.yml` | Builds the images on the instance instead of pulling them (the hand-deploy path, E17) |
| `deploy.sh` | One release on the instance: pull, migrate, start, health check, roll back on failure (F14) |
| `aws/cicd/*.json` | Automatic deploys (section I): GitHub's trust and deploy policies, the instance's ECR pull policy, the ECR lifecycle (`uv run python -m vanimo_infra.cicd` in `app/infra`) |

Placeholders `<ACCOUNT_ID>`, `<BUCKET_NAME>`, `<GUARDRAIL_ID>` are filled in by the `sed` commands below.
Everything is in **Asia Pacific (Mumbai) `ap-south-1`**.

## A. Account basics (console)

1. Sign in as an administrator user (IAM Identity Center or IAM, with MFA), never as root. Pick
   **Asia Pacific (Mumbai)** in the region menu.
2. **Budget:** Billing and Cost Management → Budgets → Create budget → monthly cost budget, $60, email
   alerts at 80% and 100%.
3. **Claude on Bedrock:** Amazon Bedrock → Playground → Chat. Choose Claude Haiku 5.5, send "hello";
   then Claude Sonnet 5.5. If Bedrock asks for Anthropic use-case details, submit them. The first use
   enables each model for the account; the app's role can then call it without Marketplace rights.

## B. Redaction backstops (CloudShell)

4. On the laptop, zip `app/deploy/ec2/aws/` and take `app/backend/vanimo/ops/macie_job.py`. Open
   **CloudShell** (the `>_` icon in the console bar) and upload both (Actions → Upload file). Then:

   ```bash
   mkdir -p vanimo && cd vanimo && unzip -o ../aws.zip && mv ../macie_job.py .
   ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
   BUCKET=vanimo-in-dev-l1-snapshots-$ACCOUNT_ID
   echo "$ACCOUNT_ID $BUCKET"
   ```

   CloudShell keeps files in `$HOME` between sessions, but not variables: re-run the two assignments
   whenever you come back.

5. **Guardrail** (then look at it in Bedrock → Guardrails, and try the console's test box with
   "Aadhaar 2341 2341 2346"):

   ```bash
   aws bedrock create-guardrail --cli-input-json file://guardrail.json   # note guardrailId
   GUARDRAIL_ID=<the guardrailId>
   aws bedrock create-guardrail-version --guardrail-identifier $GUARDRAIL_ID --description "policy 1"   # version "1"
   ```

6. **Snapshot bucket** (new buckets already block public access and encrypt with SSE-S3; versioning
   stays off):

   ```bash
   aws s3api create-bucket --bucket $BUCKET --create-bucket-configuration LocationConstraint=ap-south-1
   aws s3api put-bucket-lifecycle-configuration --bucket $BUCKET --lifecycle-configuration file://bucket-lifecycle.json
   sed -e "s/<ACCOUNT_ID>/$ACCOUNT_ID/g" -e "s/<BUCKET_NAME>/$BUCKET/g" bucket-policy.json > bucket-policy.filled.json
   aws s3api put-bucket-policy --bucket $BUCKET --policy file://bucket-policy.filled.json
   ```

7. **Macie** — enable it, add the identifiers, create the daily job (the script first tests every
   identifier in Macie's own engine against a sample and a clean line):

   ```bash
   aws macie2 enable-macie --finding-publishing-frequency FIFTEEN_MINUTES
   for f in macie-*.json; do aws macie2 create-custom-data-identifier --cli-input-json file://$f; done
   python3 -c "import boto3" 2>/dev/null || pip3 install --user boto3
   python3 macie_job.py --bucket $BUCKET --prefix vanimo-in-dev --region ap-south-1
   ```

   Then Macie → Settings → **Automated sensitive data discovery**: turn it off if it is on. The daily
   job covers our bucket; automated discovery would sample every bucket in the account and cost more.

## C. The instance's role (IAM)

8. **Policy:**

   ```bash
   sed -e "s/<ACCOUNT_ID>/$ACCOUNT_ID/g" -e "s/<BUCKET_NAME>/$BUCKET/g" -e "s/<GUARDRAIL_ID>/$GUARDRAIL_ID/g" \
     app-policy.json > app-policy.filled.json
   aws iam create-policy --policy-name VanimoAppAccess --policy-document file://app-policy.filled.json
   ```

9. **Role:** IAM → Roles → Create role → AWS service, **EC2** → attach `AmazonSSMManagedInstanceCore`
   and `VanimoAppAccess` → name `VanimoEc2Role`.

## D. The instance (EC2 console)

10. **Security group:** EC2 → Security Groups → Create: `vanimo-no-inbound`, default VPC, **no inbound
    rules**, outbound left as "all traffic".
11. **Launch instance:** name `vanimo-mvp`; **Ubuntu Server 24.04 LTS, 64-bit (Arm)**; **t4g.medium**;
    key pair: *Proceed without a key pair*; network: default VPC, auto-assign public IP on, security
    group `vanimo-no-inbound`; storage **30 GiB gp3**; Advanced details: IAM instance profile
    `VanimoEc2Role`, metadata **V2 only**, metadata **response hop limit 2** (the containers reach the
    role's credentials through Docker's network, one hop more than the host).
12. **Elastic IP:** EC2 → Elastic IPs → Allocate → Associate with `vanimo-mvp` (outbound address that
    survives stop/start).
13. **Shell:** select the instance → Connect → **Session Manager** → Connect (allow a few minutes after
    launch for it to register). Then `sudo -i` for a root shell.

## E. Install and start (on the instance)

14. **Docker:**

    ```bash
    apt-get update && apt-get install -y docker.io docker-compose-v2 docker-buildx
    docker run --rm hello-world
    ```

15. **The code.** On the laptop (repo root): `git archive --format=tar.gz -o vanimo-app.tgz HEAD app`.
    Upload it to a small private bucket of your own (S3 console, e.g. `vanimo-deploy-<account id>`; not
    the snapshot bucket), then in CloudShell make a 10-minute link:
    `aws s3 presign s3://vanimo-deploy-$ACCOUNT_ID/vanimo-app.tgz --expires-in 600`. On the instance:

    ```bash
    curl -fo /tmp/vanimo-app.tgz "<the presigned URL>"
    mkdir -p /opt/vanimo && tar -xzf /tmp/vanimo-app.tgz -C /opt/vanimo
    ```

16. **Secrets:**

    ```bash
    cd /opt/vanimo/app/deploy/ec2 && cp .env.example .env && chmod 600 .env
    for k in PG_ADMIN_PASSWORD DB_OWNER_PASSWORD DB_APP_PASSWORD VANIMO_REF_HMAC_KEY VANIMO_VAULT_MASTER_KEY; do
      sed -i "s/^$k=$/$k=$(openssl rand -hex 32)/" .env
    done
    nano .env   # fill VANIMO_GUARDRAIL_ID and VANIMO_L1_SNAPSHOT_BUCKET (version stays 1)
    ```

17. **Start** (the first build takes several minutes). Once automatic deploys run (section I), GitHub
    builds the images and this step is `deploy.sh`'s job instead:

    ```bash
    docker compose -f compose.yml -f compose.build.yml up -d --build
    docker compose ps            # postgres, api, web "healthy"/"running"; migrate "exited (0)"
    docker compose logs api | tail -50
    ```

    If the API exits at once with "missing required settings", `.env` is incomplete.

18. **Your account** (the one-time password prints here only; you change it at first sign-in):

    ```bash
    docker compose run --rm migrate python -m vanimo.ops.local_user --email you@example.com --role superadmin
    ```

## F. Open it (laptop)

19. Install the **AWS CLI v2** and the **Session Manager plugin**, and sign the CLI in
    (`aws configure sso`, or your usual profile).
20. Tunnel, then open **http://localhost:8080**:

    ```bash
    aws ssm start-session --region ap-south-1 --target <instance id> \
      --document-name AWS-StartPortForwardingSession --parameters "portNumber=8080,localPortNumber=8080"
    ```

## G. Check it works

21. **Admin → Redaction checks:** run each probe. Comprehend, the guardrail, the Indian identifiers and
    Macie must all pass. A failure here names the setting or permission that is wrong.
22. **The demo path:** review your sources and finish → **Learning** (style per audience) → **Draft**
    on a waiting thread (written by Claude on Bedrock) → the look-alike vendor's bank-details email is
    flagged before sending → **Queue**, mark as sent (sample) and see the edit loop → **Commitments** →
    **Meetings** (ask a question, cited answer).
23. **Next day:** the Macie job has scanned the first snapshot; Redaction checks shows the run.

## H. Running it

- **Costs:** about $36–51/month running all the time (`docs/03` §0.1). Stopping the instance when not in
  use saves most of the EC2 cost; the Elastic IP and the disk are still billed while it is stopped.
- **Update:** automatic once section I is done: merge into `main` and push. By hand (before section I): new
  `git archive` → upload → presign → extract over the app folder →
  `docker compose -f compose.yml -f compose.build.yml up -d --build`.
- **Logs:** `docker compose logs -f api`. **Restart:** `docker compose restart api`.
- **Data:** synthetic only, no backups. `docker compose down -v` deletes the database.
- **Tear down:** terminate the instance, release the Elastic IP, then delete the guardrail, the
  snapshot and deploy buckets, the Macie job and identifiers (and disable Macie), the role and the
  policy, and the budget if you no longer want it.

## I. Automatic deploys from GitHub (F14)

Once this section is done, **every push to `main` ships itself**: GitHub runs the tests, builds the API and
web images for the instance's Arm CPU, stores them in **ECR** (AWS's private image registry), then tells the
instance through **SSM Run Command** to pull them and restart. `deploy.sh` on the instance runs the
migrations, checks the new release's health and puts the previous release back if it fails. The workflow is
`.github/workflows/deploy.yml`; until the GitHub variables in I7 exist, `main` runs its tests and builds both
images (stored nowhere), so a broken image shows up before the first deploy. The images are built on GitHub's
Arm runners (free for public repositories), natively for the instance's CPU.

The repository is public: fill in `<ACCOUNT_ID>`, `<INSTANCE_ID>` and the other placeholders **in the console
only**. Never commit real account IDs, ARNs or `.env` values.

No AWS keys are stored in GitHub. GitHub gives each run a signed, short-lived **OIDC token**; IAM trusts
GitHub's token issuer (I1) and swaps a token for the deploy role (I4) only when it says "repository
`siddharth-kalyani/persona-agent`, branch `main`". The policies are in `aws/cicd/`, each permission
explained in `app/infra/vanimo_infra/cicd.py`. Tag every resource with `Owner`, `Project` and `Name`.

I1. **GitHub as an identity provider** (IAM → Identity providers → Add provider): **OpenID Connect**,
    provider URL `https://token.actions.githubusercontent.com`, audience `sts.amazonaws.com`. One per account;
    if it already exists, reuse it.
I2. **Two image repositories** (Elastic Container Registry → Private registry → Repositories → Create):
    `vanimo-api` and `vanimo-web`, **tag immutability: Immutable** (a release's tag can never be overwritten),
    encryption AES-256. In each: Lifecycle policy → Create rule from `aws/cicd/ecr-lifecycle-policy.json`
    (keeps the 15 most recent releases for rollbacks; storage is about $0.10 per GB-month).
I3. **The deploy policy** (IAM → Policies → Create policy → JSON): paste `aws/cicd/github-deploy-policy.json`
    with `<ACCOUNT_ID>`, `<INSTANCE_ID>` and `<DEPLOY_BUCKET>` filled in. Name: `persona-agent-dev-github-deploy`.
I4. **The deploy role** (IAM → Roles → Create role → **Web identity**): identity provider
    `token.actions.githubusercontent.com`, audience `sts.amazonaws.com`, GitHub organization
    `siddharth-kalyani`, repository `persona-agent`, branch `main`; attach the policy from I3. Name:
    `persona-agent-dev-github-deploy-role`. Then open its **Trust relationships** tab and compare with
    `aws/cicd/github-trust-policy.json` (account ID filled in): only `main` of this repository may use it.
I5. **Let the instance pull images**: IAM → Roles → the instance's role (`persona-agent-dev-ec2-role`) → Add
    permissions → Create inline policy → JSON: `aws/cicd/instance-ecr-pull-policy.json` (account ID filled
    in). Name: `persona-agent-dev-ecr-pull`. Then, on the instance (Session Manager, `sudo -i`), install
    the ECR credential helper, which signs Docker in to ECR with the instance role:

    ```bash
    apt-get update && apt-get install -y amazon-ecr-credential-helper
    mkdir -p /root/.docker
    echo '{"credHelpers": {"<ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com": "ecr-login"}}' > /root/.docker/config.json
    docker pull <ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com/vanimo-api:check   # "not found" = signed in fine
    ```

I6. **Deploy bucket** (optional tidy-up): S3 → the deploy bucket → Management → Lifecycle rule, prefix
    `releases/`, expire current versions after 30 days. Each deploy uploads one small file there.
I7. **Tell GitHub where to deploy** (GitHub → the repository → Settings → Secrets and variables → Actions →
    **Variables** → New repository variable). None of these is a secret:

    | Variable | Value |
    |---|---|
    | `AWS_DEPLOY_ROLE_ARN` | `arn:aws:iam::<ACCOUNT_ID>:role/persona-agent-dev-github-deploy-role` |
    | `AWS_REGION` | `ap-south-1` |
    | `DEPLOY_INSTANCE_ID` | the instance's ID (`i-…`) |
    | `DEPLOY_BUCKET` | the deploy bucket's name |
    | `DEPLOY_DIR` | `/opt/PersonaAgent` (the folder that holds `app/`) |

I8. **First deploy**: GitHub → Actions → **deploy** → Run workflow (branch `main`). The image builds take a few
    minutes on GitHub's Arm runners and reuse their build cache after that. The run's summary says which
    commit went out; the server's own output is in the "Deploy on the server" step.
I9. **Going back**: revert the bad commit on `main` and push (the usual way: a new, tested release), or on the
    instance: `sudo bash /opt/PersonaAgent/app/deploy/ec2/deploy.sh <ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com
    <an earlier commit SHA>`. `cat /opt/PersonaAgent/app/deploy/ec2/.deployed` shows what is running.
