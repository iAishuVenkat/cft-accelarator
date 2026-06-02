# CloudFormation Accelerator

A config-driven generator that produces production-ready AWS CloudFormation templates from a service catalog.

## How It Works

```
You say:    "I need a web app with a database"
Tool does:  Picks templates from catalog → builds config → generates CFT
You get:    500+ lines of production-ready CloudFormation, deployed in minutes
```

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

## 3 Ways to Use

### Way 1: Interactive Wizard (Easiest - asks you questions)

```bash
python wizard.py
```

The wizard will:
1. Show all available AWS services (VPC, ECS, RDS, Lambda, etc.)
2. Let you pick which ones you need
3. Auto-add dependencies (e.g., ECS needs VPC)
4. Ask for configuration inputs
5. Build the config and generate CloudFormation

### Way 2: Quick Build (One command, no prompts)

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
python quick_build.py --project big-app --env prod --services ecs-service,rds --image app:v2 --cpu 2048 --memory 4096 --engine mysql --multi-az true
```

### Way 3: Manual Config (Full control)

```bash
# Copy an example
copy examples\web-app.yaml my-project.yaml

# Edit it
notepad my-project.yaml

# Generate
python generate.py my-project.yaml
```

---

## Deploy to AWS

After generation, deploy with:

```bash
aws cloudformation deploy --template-file output/main.yaml --stack-name my-project-prod --capabilities CAPABILITY_NAMED_IAM
```

## Project Structure

```
cft-accelerator/
├── wizard.py                # Interactive wizard (asks questions)
├── quick_build.py           # One-command builder (no prompts)
├── generate.py              # Core generator engine
├── requirements.txt         # Python dependencies
├── README.md
├── catalog/                 # Service catalog (stock of patterns)
│   └── services.yaml
├── examples/                # Example manual configs
│   ├── web-app.yaml
│   ├── serverless-api.yaml
│   └── static-site.yaml
├── modules/                 # Reusable CFT module templates
│   ├── vpc.yaml.j2
│   ├── ecs_service.yaml.j2
│   ├── rds.yaml.j2
│   ├── lambda_function.yaml.j2
│   ├── api_gateway.yaml.j2
│   ├── s3_static_site.yaml.j2
│   ├── cloudfront.yaml.j2
│   └── alb.yaml.j2
├── schemas/                 # Validation schemas
│   └── config_schema.yaml
└── output/                  # Generated templates go here
```

## Service Catalog (Individual AWS Services)

The catalog (`catalog/services.yaml`) is a stock of individual AWS service templates:

| Service Key | AWS Service | Dependencies |
|-------------|-------------|--------------|
| `vpc` | VPC with subnets, NAT, routes | None |
| `ecs-service` | ECS Fargate containers | Requires: vpc |
| `rds` | RDS database (PostgreSQL/MySQL) | Requires: vpc |
| `lambda` | Lambda function | None |
| `api-gateway` | API Gateway REST API | None |
| `s3-static-site` | S3 static website bucket | None |
| `cloudfront` | CloudFront CDN | Requires: s3-static-site |
| `alb` | Application Load Balancer | Requires: vpc |

Dependencies are **auto-resolved** — if you pick `ecs-service`, the tool automatically adds `vpc` for you.

## Supported Components

| Component | Description |
|-----------|-------------|
| `vpc` | VPC with public/private subnets, NAT Gateway, route tables |
| `ecs-service` | ECS Fargate service with auto-scaling |
| `rds` | RDS database (PostgreSQL or MySQL) with backups |
| `lambda` | Lambda function with IAM role |
| `api-gateway` | REST API Gateway |
| `s3-static-site` | S3 bucket configured for static hosting |
| `cloudfront` | CloudFront CDN distribution |
| `alb` | Application Load Balancer |

## Adding New AWS Services to the Catalog

To add a new AWS service (e.g., SQS, DynamoDB, ElastiCache):

1. **Add the service template** in `modules/your_service.yaml.j2`
2. **Register it in the catalog** — add entry in `catalog/services.yaml` with its options and defaults
3. **Add to the schema** — add the type in `schemas/config_schema.yaml`
4. **Map it in generate.py** — add to `MODULE_MAP` and `DEFAULTS` dictionaries

The catalog entry format:
```yaml
  your-service:
    name: "Your Service Name"
    description: "What it does"
    category: Compute/Networking/Database/Storage
    requires: [vpc]  # optional dependencies
    options:
      some_setting:
        description: "What this controls"
        type: string/integer/boolean/choice
        default: "some-default"
        prompt: "What to ask the user"
```
