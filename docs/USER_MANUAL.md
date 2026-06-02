# CloudFormation Accelerator — User Manual

## Table of Contents

1. [What is This App?](#what-is-this-app)
2. [Who is This For?](#who-is-this-for)
3. [How It Works](#how-it-works)
4. [Using the Web Interface](#using-the-web-interface)
5. [Using the Command Line](#using-the-command-line)
6. [Available AWS Services](#available-aws-services)
7. [Deploying to AWS](#deploying-to-aws)
8. [Understanding the Output](#understanding-the-output)
9. [Common Use Cases](#common-use-cases)
10. [Troubleshooting](#troubleshooting)
11. [Frequently Asked Questions](#frequently-asked-questions)

---

## What is This App?

The CloudFormation Accelerator is a tool that **generates AWS infrastructure code automatically**.

Instead of manually writing hundreds of lines of AWS CloudFormation YAML (which is time-consuming and error-prone), you simply:

1. Pick the AWS services you need (like a menu)
2. Fill in a few basic settings
3. Click "Generate"

The app produces a complete, production-ready CloudFormation template that you can deploy directly to AWS.

### Before This App

- Manually writing 500-2000 lines of YAML per project
- Remembering security best practices every time
- Wiring services together correctly from scratch
- Time spent: 2-3 days per project

### After This App

- Pick services, fill in settings, click generate
- Security, encryption, and best practices included automatically
- Services wired together correctly every time
- Time spent: 5 minutes per project

---

## Who is This For?

- **DevOps Engineers** who set up AWS infrastructure regularly
- **Developers** who need infrastructure but don't want to write CloudFormation from scratch
- **Platform Teams** who want a standardized way to create infrastructure
- **Anyone** who deploys applications on AWS

No deep CloudFormation expertise required — the tool handles the complexity.

---

## How It Works

```
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│  YOU              │      │  ACCELERATOR     │      │  AWS             │
│                  │      │                  │      │                  │
│  Pick services   │─────▶│  Generates CFT   │─────▶│  Creates infra   │
│  Fill settings   │      │  (500+ lines)    │      │  (VPCs, DBs...)  │
│  Click generate  │      │                  │      │                  │
└──────────────────┘      └──────────────────┘      └──────────────────┘
     5 minutes                  Instant                  10 minutes
```

The app contains a **catalog of 37 AWS services** — each with a pre-built template that follows AWS best practices. When you pick services, the app:

1. Reads the templates for your selected services
2. Fills in your settings (project name, region, etc.)
3. Applies security defaults (encryption, IAM least-privilege, backups)
4. Wires services together (ECS references VPC subnets, RDS gets security groups, etc.)
5. Outputs one complete CloudFormation YAML file

---

## Using the Web Interface

### Accessing the App

Open your browser and go to:
- **Live:** https://cft-accelarator.vercel.app
- **Local:** http://localhost:5000 (if running locally with `python web/app.py`)

### Step 1: Project Details

On the first screen, fill in:

| Field | What to Enter | Example |
|-------|---------------|---------|
| **Project Name** | A short name for your project (lowercase, hyphens allowed) | `my-web-app` |
| **Environment** | Development, Staging, or Production | `prod` |
| **AWS Region** | The AWS region to deploy to | `us-east-1` |

**Tags (Optional):**
Tags are labels attached to all your AWS resources. Useful for cost tracking and organization.
- Click "+ Add" to add tags
- Common tags: `team: backend`, `cost-center: engineering`

Then click **"Select Services →"**

### Step 2: Select AWS Services

You'll see all 37 available services organized by category:
- Networking (VPC, ALB, API Gateway, etc.)
- Compute (ECS, Lambda, EC2, etc.)
- Database (RDS, DynamoDB, Aurora, etc.)
- And more...

**How to select:**
- Click on any service card to select it (turns blue with a checkmark)
- Click again to deselect

**Auto-dependencies:**
If you select a service that requires another (e.g., RDS needs a VPC), the dependency is **automatically added** for you.

A floating badge at the bottom-right shows how many services you've selected.

Then click **"Configure Services →"**

### Step 3: Configure

Each selected service shows its configurable options. For example:

**ECS Service:**
- Container image (required)
- CPU units
- Memory
- Number of containers
- Port
- Health check path

**RDS Database:**
- Engine (PostgreSQL or MySQL)
- Instance size
- Storage amount
- Multi-AZ (high availability)
- Backup retention days

**Most fields have defaults** — you only need to change what's different from the standard setup.

**Required fields** are marked with a red asterisk (*). The app will alert you if these are left empty.

Then click **"🚀 Generate CloudFormation"**

### Step 4: Generate & Download

The app generates your CloudFormation template and displays:

1. **Deploy Command** — A ready-to-paste AWS CLI command
2. **Template Preview** — The full generated YAML you can scroll through
3. **Download button** — Saves `main.yaml` to your computer
4. **Copy button** — Copies the template to your clipboard

---

## Using the Command Line

### Installation

```bash
cd cft-accelerator
pip install -r requirements.txt
```

### Option A: Interactive Wizard

```bash
python wizard.py
```

The wizard will:
1. Show all available services
2. Ask you to pick (by number or name)
3. Ask for project details
4. Configure each service
5. Generate the template

**Selecting services:**
You can type numbers (`1,2,5`), names (`vpc, rds, lambda`), or keywords (`s3, dynamo, ecs`).

### Option B: Quick Build (One Command)

```bash
python quick_build.py --project my-app --env prod --services vpc,ecs-service,rds --image my-app:latest
```

**Key flags:**

| Flag | Purpose | Example |
|------|---------|---------|
| `--project` | Project name | `my-app` |
| `--env` | Environment (dev/staging/prod) | `prod` |
| `--services` | Comma-separated service list | `vpc,ecs-service,rds` |
| `--image` | Container image (for ECS) | `123456.dkr.ecr.us-east-1.amazonaws.com/app:latest` |
| `--handler` | Lambda handler | `app.handler` |
| `--runtime` | Lambda runtime | `python3.12` |
| `--engine` | Database engine | `postgres` |
| `--list` | Show all available services | (no value needed) |

**See all available services:**
```bash
python quick_build.py --list
```

### Option C: Manual Config File

Write a YAML config file:

```yaml
project: my-app
environment: prod
region: us-east-1
tags:
  team: backend
components:
  - type: vpc
    cidr: "10.0.0.0/16"
    availability_zones: 2
  - type: ecs-service
    image: my-app:latest
    cpu: 1024
    memory: 2048
    desired_count: 3
  - type: rds
    engine: postgres
    instance_class: db.t3.large
    multi_az: true
```

Then generate:
```bash
python generate.py my-config.yaml
```

---

## Available AWS Services

### Networking
| Service | Key | What It Creates |
|---------|-----|-----------------|
| VPC | `vpc` | Private network with public/private subnets, NAT gateway, route tables |
| ALB | `alb` | Application Load Balancer for HTTP/HTTPS traffic |
| NLB | `nlb` | Network Load Balancer for TCP/UDP traffic |
| API Gateway | `api-gateway` | Managed REST API with throttling |
| CloudFront | `cloudfront` | CDN for fast content delivery |
| Route 53 | `route53` | DNS hosted zone |

### Compute
| Service | Key | What It Creates |
|---------|-----|-----------------|
| ECS Fargate | `ecs-service` | Containerized app with load balancer and auto-scaling |
| ECS Cluster | `ecs-cluster` | Container cluster with Fargate capacity |
| Lambda | `lambda` | Serverless function with IAM role |
| EC2 | `ec2` | Virtual server with security group |
| Auto Scaling | `auto-scaling-group` | Group of EC2 instances that scale automatically |
| Step Functions | `step-functions` | Serverless workflow orchestration |

### Database
| Service | Key | What It Creates |
|---------|-----|-----------------|
| RDS | `rds` | PostgreSQL/MySQL database with encryption and backups |
| DynamoDB | `dynamodb` | NoSQL table with on-demand capacity |
| ElastiCache | `elasticache` | Redis or Memcached cluster |
| Aurora | `aurora` | Serverless Aurora PostgreSQL/MySQL cluster |

### Storage
| Service | Key | What It Creates |
|---------|-----|-----------------|
| S3 | `s3` | General purpose bucket with encryption |
| S3 Static Site | `s3-static-site` | Bucket configured for website hosting |
| EFS | `efs` | Shared file system for containers/EC2 |

### Messaging
| Service | Key | What It Creates |
|---------|-----|-----------------|
| SQS | `sqs` | Message queue with dead-letter queue |
| SNS | `sns` | Pub/sub notification topic |
| EventBridge | `eventbridge` | Event bus for event-driven apps |
| Kinesis | `kinesis` | Real-time data stream |

### Security
| Service | Key | What It Creates |
|---------|-----|-----------------|
| Cognito | `cognito` | User authentication with sign-up/sign-in |
| WAF | `waf` | Web application firewall with common protections |
| Secrets Manager | `secrets-manager` | Managed secret storage |
| KMS | `kms` | Encryption key with auto-rotation |

### Monitoring
| Service | Key | What It Creates |
|---------|-----|-----------------|
| CloudWatch Alarm | `cloudwatch-alarm` | Metric alarm with SNS notification |
| Dashboard | `cloudwatch-dashboard` | Monitoring dashboard |
| CloudTrail | `cloudtrail` | API audit logging |

### CI/CD
| Service | Key | What It Creates |
|---------|-----|-----------------|
| CodePipeline | `codepipeline` | Automated deployment pipeline |
| CodeBuild | `codebuild` | Build project with configurable compute |
| ECR | `ecr` | Container image registry |

### Integration & Analytics
| Service | Key | What It Creates |
|---------|-----|-----------------|
| AppSync | `appsync` | GraphQL API |
| SES | `ses` | Email sending service |
| Glue | `glue` | ETL with data catalog |
| Athena | `athena` | SQL query service |

---

## Deploying to AWS

### Prerequisites

- AWS CLI installed and configured (`aws configure`)
- IAM permissions to create the selected resources

### Deploy Command

After generating your template, deploy with:

```bash
aws cloudformation deploy \
  --template-file output/main.yaml \
  --stack-name YOUR-PROJECT-NAME-ENVIRONMENT \
  --capabilities CAPABILITY_NAMED_IAM \
  --region YOUR-REGION
```

**Example:**
```bash
aws cloudformation deploy \
  --template-file output/main.yaml \
  --stack-name my-app-prod \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

### Checking Deployment Status

```bash
aws cloudformation describe-stacks --stack-name my-app-prod
```

### Deleting Infrastructure

```bash
aws cloudformation delete-stack --stack-name my-app-prod
```

⚠️ **Warning:** This deletes all resources in the stack. RDS with deletion protection will need it disabled first.

---

## Understanding the Output

The generated `main.yaml` file contains:

### Structure
```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: 'project - environment - Generated by CFT Accelerator'

# Module 1: VPC
Resources:
  VPC: ...
  Subnets: ...
Outputs:
  VpcId: ...

# Module 2: ECS Service
Resources:
  Cluster: ...
  TaskDefinition: ...
Outputs:
  ServiceUrl: ...

# Module 3: RDS
Resources:
  Database: ...
Outputs:
  Endpoint: ...
```

### What's Included Automatically

| Feature | How It's Applied |
|---------|-----------------|
| **Encryption** | All storage (S3, RDS, EBS) encrypted by default |
| **Backups** | RDS has automated backups enabled |
| **Logging** | CloudWatch log groups created for ECS, Lambda |
| **IAM** | Least-privilege roles for each service |
| **Networking** | Private subnets for databases, public for load balancers |
| **Secrets** | Database passwords stored in Secrets Manager |
| **Auto-scaling** | ECS services scale based on CPU utilization |
| **Health checks** | Load balancers check application health |

### Cross-References

Services reference each other using CloudFormation exports:
- ECS references VPC subnets via `!ImportValue project-env-vpc-PrivateSubnets`
- RDS references VPC via `!ImportValue project-env-vpc-VpcId`
- CloudFront references S3 via `!ImportValue project-env-s3-static-site-BucketDomainName`

---

## Common Use Cases

### Web Application with Database

Select: `vpc` + `ecs-service` + `rds`

Gives you: Network, containerized app with load balancer, PostgreSQL database.

### Serverless API

Select: `lambda` + `api-gateway`

Gives you: Lambda function behind a managed REST API.

### Static Website

Select: `s3-static-site` + `cloudfront`

Gives you: S3 hosting with global CDN.

### Event-Driven Architecture

Select: `lambda` + `sqs` + `dynamodb` + `eventbridge`

Gives you: Serverless processing with queues, NoSQL storage, and event routing.

### Full Production Stack

Select: `vpc` + `ecs-service` + `rds` + `elasticache` + `waf` + `cloudtrail` + `cloudwatch-alarm`

Gives you: Complete production setup with security, caching, monitoring, and auditing.

---

## Troubleshooting

### "Validation failed" error in the web UI

**Cause:** A required field is empty.
**Fix:** Go back to Step 3 (Configure) and fill in all fields marked with *.

### Template generates but deploy fails

**Common causes:**
- Container image doesn't exist (ECS) → Push your image to ECR first
- S3 bucket name already taken → Bucket names are globally unique, change project name
- IAM permissions insufficient → Ensure your AWS user has admin or relevant permissions
- Resource name too long → Keep project names short (under 20 chars)

### "No module found for type X" warning

**Cause:** You're using a service type that doesn't have a template yet.
**Fix:** Check spelling matches the catalog exactly (use `--list` to see options).

### Duplicate resource errors in CloudFormation

**Cause:** Selecting both `alb` (standalone) and `ecs-service` (which includes its own ALB).
**Fix:** If you're using ECS, you don't need a separate ALB — the ECS module includes one.

---

## Frequently Asked Questions

**Q: Is this app free?**
A: Yes. The app itself is free and open source. AWS resources you deploy will incur standard AWS costs.

**Q: Can I edit the generated template?**
A: Absolutely. The output is standard CloudFormation YAML. You can modify it before deploying.

**Q: What if I need a service that's not in the catalog?**
A: You can add new services by creating a Jinja2 template in the `modules/` folder and registering it in the catalog.

**Q: Does the app store my data?**
A: No. The app runs entirely in your browser and the serverless backend. Nothing is stored permanently.

**Q: Can I use this for multiple environments?**
A: Yes. Generate separate templates for `dev`, `staging`, and `prod` with different settings (e.g., smaller instances for dev, multi-AZ for prod).

**Q: How do I update infrastructure after deploying?**
A: Change your config, regenerate, and run the same `aws cloudformation deploy` command. CloudFormation handles updates automatically.

**Q: Is the generated template production-ready?**
A: Yes, for most use cases. It includes encryption, proper IAM, backups, and security groups. For highly regulated environments, you may want additional customization (compliance tags, specific CIDR ranges, etc.).

---

## Support

- **Source Code:** https://github.com/iAishuVenkat/cft-accelarator
- **Issues:** Report bugs or request features via GitHub Issues
- **Live App:** https://cft-accelarator.vercel.app
