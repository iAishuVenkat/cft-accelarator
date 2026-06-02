# ☁️ CloudFormation Accelerator

A config-driven generator that produces production-ready AWS CloudFormation templates from a catalog of 37 AWS services.

**Live Demo:** [cft-accelarator.vercel.app](https://cft-accelarator.vercel.app)

## What It Does

```
You pick:    AWS services you need (VPC, ECS, RDS, Lambda, SQS, etc.)
Tool does:   Assembles config → validates → generates complete CloudFormation
You get:     500+ lines of production-ready YAML, deployed in minutes
```

Turns what normally takes 2-3 days of manual YAML writing into a 5-minute process.

---

## Quick Start

### Prerequisites

- Python 3.8+
- pip

### Installation

```bash
cd cft-accelerator
pip install -r requirements.txt
```

---

## 4 Ways to Use

### 1. Web UI (Visual — hosted on Vercel)

Visit the live app or run locally:

```bash
python web/app.py
# Open http://localhost:5000
```

4-step wizard in the browser:
1. Enter project name, environment, region
2. Click services you need
3. Configure settings
4. Generate & download CloudFormation

### 2. Interactive CLI Wizard

```bash
python wizard.py
```

Asks questions, accepts both numbers and service names (e.g., `vpc, rds, lambda`).

### 3. Quick Build (One Command)

```bash
# See available services
python quick_build.py --list

# Web app with database (auto-adds VPC)
python quick_build.py --project my-app --env prod --services ecs-service,rds --image my-app:latest

# Serverless API
python quick_build.py --project my-api --env dev --services lambda,api-gateway --handler app.handler --runtime python3.12

# Static website with CDN
python quick_build.py --project my-site --env prod --services s3-static-site,cloudfront

# Override defaults
python quick_build.py --project big-app --env prod --services ecs-service,rds --image app:v2 --cpu 2048 --memory 4096 --engine mysql
```

### 4. Manual Config (Full Control)

```bash
# Write your own config
notepad my-project.yaml

# Generate
python generate.py my-project.yaml
```

---

## Deploy to AWS

After generation:

```bash
aws cloudformation deploy \
  --template-file output/main.yaml \
  --stack-name my-project-prod \
  --capabilities CAPABILITY_NAMED_IAM
```

---

## Service Catalog (37 AWS Services)

The catalog (`catalog/services.yaml`) contains individual AWS service templates:

| Category | Services |
|----------|----------|
| **Networking** | VPC, ALB, NLB, API Gateway, CloudFront, Route 53 |
| **Compute** | ECS Fargate, ECS Cluster, Lambda, EC2, Auto Scaling Group, Step Functions |
| **Database** | RDS, DynamoDB, ElastiCache, Aurora |
| **Storage** | S3 (general), S3 (static site), EFS |
| **Messaging** | SQS, SNS, EventBridge, Kinesis |
| **Security** | Cognito, WAF, Secrets Manager, KMS |
| **Monitoring** | CloudWatch Alarm, CloudWatch Dashboard, CloudTrail |
| **CI/CD** | CodePipeline, CodeBuild, ECR |
| **Integration** | AppSync, SES |
| **Analytics** | Glue, Athena |

Dependencies are **auto-resolved** — picking `ecs-service` auto-adds `vpc`.

---

## Project Structure

```
cft-accelerator/
├── web/                     # Web UI (Flask)
│   ├── app.py
│   └── templates/index.html
├── api/                     # Vercel serverless entry point
│   └── index.py
├── catalog/                 # Service catalog (stock of templates)
│   └── services.yaml
├── modules/                 # 37 Jinja2 CFT module templates
│   ├── vpc.yaml.j2
│   ├── ecs_service.yaml.j2
│   ├── rds.yaml.j2
│   ├── lambda_function.yaml.j2
│   ├── ... (37 total)
│   └── athena.yaml.j2
├── schemas/                 # Validation schema
│   └── config_schema.yaml
├── examples/                # Example manual configs
│   ├── web-app.yaml
│   ├── serverless-api.yaml
│   └── static-site.yaml
├── output/                  # Generated templates
├── generate.py              # Core generator engine
├── wizard.py                # Interactive CLI wizard
├── quick_build.py           # One-command builder
├── requirements.txt         # Python dependencies
└── vercel.json              # Vercel deployment config
```

---

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│  SERVICE CATALOG (37 AWS service templates)                  │
│  vpc │ ecs │ rds │ lambda │ sqs │ cognito │ waf │ ...       │
└─────────────────────────┬───────────────────────────────────┘
                          │
       User picks services (UI / CLI / config file)
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  BUILDER                                                    │
│  • Reads catalog for selected services                      │
│  • Auto-adds dependencies (e.g., ECS needs VPC)            │
│  • Applies best-practice defaults                           │
│  • Validates required fields                                │
│  • Assembles config YAML                                    │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  GENERATOR (generate.py)                                    │
│  • Picks Jinja2 module templates                            │
│  • Renders with project context                             │
│  • Produces complete CloudFormation YAML                     │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
              output/main.yaml (deploy to AWS)
```

---

## Key Features

- **37 AWS services** in the catalog, ready to combine
- **Auto-dependency resolution** — pick RDS, VPC gets added
- **Best-practice defaults** — encryption, backups, IAM least-privilege baked in
- **Validation** — catches errors before generating (empty fields, invalid types)
- **No duplicate resource conflicts** — unique logical IDs per module
- **3 interfaces** — Web UI, interactive CLI, one-command CLI
- **Free hosting** on Vercel

---

## Adding New AWS Services

1. Create a Jinja2 template: `modules/your_service.yaml.j2`
2. Register in catalog: add entry in `catalog/services.yaml`
3. Add to schema: add type in `schemas/config_schema.yaml`
4. Map in generator: add to `MODULE_MAP` and `DEFAULTS` in `generate.py`

Catalog entry format:
```yaml
your-service:
  name: "Your Service Name"
  description: "What it does"
  category: Compute
  requires: [vpc]  # optional
  options:
    some_setting:
      type: string
      default: "value"
      required: true
      prompt: "What to ask the user"
```

---

## Hosting on Vercel (Free)

1. Push to GitHub
2. Go to [vercel.com](https://vercel.com) → Import repo
3. Deploy (auto-detects `vercel.json`)
4. Every `git push` auto-redeploys

---

## Tech Stack

- **Backend:** Python, Flask, Jinja2
- **Validation:** jsonschema
- **Frontend:** Vanilla HTML/CSS/JS (no framework, no build step)
- **Hosting:** Vercel (serverless Python)
- **Templates:** Jinja2 → CloudFormation YAML

---

## License

MIT
