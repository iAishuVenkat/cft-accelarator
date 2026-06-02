"""
CloudFormation Accelerator - Template Generator

Usage:
    python generate.py <config_file.yaml>
    python generate.py examples/web-app.yaml
    python generate.py examples/web-app.yaml --output-dir ./my-output
"""

import os
import sys
import yaml
import click
import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from jsonschema import validate, ValidationError


# Module type to template file mapping
MODULE_MAP = {
    # Networking
    "vpc": "vpc.yaml.j2",
    "alb": "alb.yaml.j2",
    "nlb": "nlb.yaml.j2",
    "api-gateway": "api_gateway.yaml.j2",
    "cloudfront": "cloudfront.yaml.j2",
    "route53": "route53.yaml.j2",
    # Compute
    "ecs-service": "ecs_service.yaml.j2",
    "ecs-cluster": "ecs_cluster.yaml.j2",
    "lambda": "lambda_function.yaml.j2",
    "ec2": "ec2.yaml.j2",
    "auto-scaling-group": "auto_scaling_group.yaml.j2",
    "step-functions": "step_functions.yaml.j2",
    # Database
    "rds": "rds.yaml.j2",
    "dynamodb": "dynamodb.yaml.j2",
    "elasticache": "elasticache.yaml.j2",
    "aurora": "aurora.yaml.j2",
    # Storage
    "s3": "s3.yaml.j2",
    "s3-static-site": "s3_static_site.yaml.j2",
    "efs": "efs.yaml.j2",
    # Messaging
    "sqs": "sqs.yaml.j2",
    "sns": "sns.yaml.j2",
    "eventbridge": "eventbridge.yaml.j2",
    "kinesis": "kinesis.yaml.j2",
    # Security
    "cognito": "cognito.yaml.j2",
    "waf": "waf.yaml.j2",
    "secrets-manager": "secrets_manager.yaml.j2",
    "kms": "kms.yaml.j2",
    # Monitoring
    "cloudwatch-alarm": "cloudwatch_alarm.yaml.j2",
    "cloudwatch-dashboard": "cloudwatch_dashboard.yaml.j2",
    "cloudtrail": "cloudtrail.yaml.j2",
    # CI/CD
    "codepipeline": "codepipeline.yaml.j2",
    "codebuild": "codebuild.yaml.j2",
    "ecr": "ecr.yaml.j2",
    # Integration
    "appsync": "appsync.yaml.j2",
    "ses": "ses.yaml.j2",
    # Analytics
    "glue": "glue.yaml.j2",
    "athena": "athena.yaml.j2",
}

# Default values for each component type
DEFAULTS = {
    # Networking
    "vpc": {
        "cidr": "10.0.0.0/16",
        "availability_zones": 2,
        "enable_nat_gateway": True,
    },
    "alb": {
        "internal": False,
        "ssl_certificate_arn": "",
    },
    "nlb": {
        "internal": False,
        "cross_zone": True,
    },
    "api-gateway": {
        "stage_name": "v1",
        "description": "REST API",
    },
    "cloudfront": {
        "price_class": "PriceClass_100",
        "default_ttl": 86400,
    },
    "route53": {
        "private_zone": False,
    },
    # Compute
    "ecs-service": {
        "cpu": 512,
        "memory": 1024,
        "desired_count": 2,
        "port": 80,
        "health_check_path": "/health",
    },
    "ecs-cluster": {
        "enable_container_insights": True,
    },
    "lambda": {
        "memory_size": 256,
        "timeout": 30,
        "environment_vars": {},
    },
    "ec2": {
        "instance_type": "t3.medium",
        "ami_id": "",
        "key_pair": "",
        "volume_size": 30,
        "assign_public_ip": False,
    },
    "auto-scaling-group": {
        "instance_type": "t3.medium",
        "min_size": 1,
        "max_size": 4,
        "desired_capacity": 2,
        "health_check_type": "EC2",
    },
    "step-functions": {
        "state_machine_type": "STANDARD",
        "logging_level": "ERROR",
    },
    # Database
    "rds": {
        "engine": "postgres",
        "engine_version": "15.4",
        "instance_class": "db.t3.medium",
        "allocated_storage": 20,
        "multi_az": False,
        "backup_retention_days": 7,
    },
    "dynamodb": {
        "partition_key": "id",
        "partition_key_type": "S",
        "sort_key": "",
        "sort_key_type": "S",
        "billing_mode": "PAY_PER_REQUEST",
        "enable_point_in_time_recovery": True,
    },
    "elasticache": {
        "engine": "redis",
        "node_type": "cache.t3.medium",
        "num_cache_nodes": 1,
        "engine_version": "7.0",
    },
    "aurora": {
        "engine": "aurora-postgresql",
        "engine_version": "15.4",
        "serverless": True,
        "min_capacity": 1,
        "max_capacity": 16,
    },
    # Storage
    "s3": {
        "bucket_suffix": "data",
        "versioning": True,
        "lifecycle_expiration_days": 0,
        "block_public_access": True,
    },
    "s3-static-site": {
        "index_document": "index.html",
        "error_document": "error.html",
    },
    "efs": {
        "performance_mode": "generalPurpose",
        "throughput_mode": "elastic",
        "encrypted": True,
    },
    # Messaging
    "sqs": {
        "queue_type": "standard",
        "visibility_timeout": 30,
        "message_retention_days": 4,
        "enable_dlq": True,
        "max_receive_count": 3,
    },
    "sns": {
        "display_name": "",
        "fifo_topic": False,
        "kms_encryption": True,
    },
    "eventbridge": {
        "bus_name": "custom-events",
    },
    "kinesis": {
        "shard_count": 1,
        "retention_hours": 24,
        "stream_mode": "ON_DEMAND",
    },
    # Security
    "cognito": {
        "pool_name": "app-users",
        "mfa_configuration": "OPTIONAL",
        "auto_verified_attributes": "email",
        "password_min_length": 8,
    },
    "waf": {
        "scope": "REGIONAL",
        "enable_rate_limiting": True,
        "rate_limit": 2000,
    },
    "secrets-manager": {
        "generate_password": True,
        "password_length": 32,
    },
    "kms": {
        "enable_rotation": True,
        "pending_deletion_days": 30,
    },
    # Monitoring
    "cloudwatch-alarm": {
        "comparison_operator": "GreaterThanThreshold",
        "period": 300,
        "evaluation_periods": 3,
    },
    "cloudwatch-dashboard": {
        "dashboard_name": "app-dashboard",
    },
    "cloudtrail": {
        "is_multi_region": True,
        "enable_log_file_validation": True,
    },
    # CI/CD
    "codepipeline": {
        "source_provider": "CodeCommit",
        "branch": "main",
    },
    "codebuild": {
        "compute_type": "BUILD_GENERAL1_SMALL",
        "build_image": "aws/codebuild/amazonlinux2-x86_64-standard:5.0",
        "timeout_minutes": 30,
    },
    "ecr": {
        "image_tag_mutability": "IMMUTABLE",
        "scan_on_push": True,
        "lifecycle_max_images": 30,
    },
    # Integration
    "appsync": {
        "authentication_type": "API_KEY",
    },
    "ses": {},
    # Analytics
    "glue": {
        "crawler_s3_path": "",
    },
    "athena": {
        "workgroup_name": "primary",
    },
}


def load_config(config_path: str) -> dict:
    """Load and parse the YAML config file."""
    config_file = Path(config_path)
    if not config_file.exists():
        click.echo(f"Error: Config file '{config_path}' not found.", err=True)
        sys.exit(1)

    with open(config_file, "r") as f:
        config = yaml.safe_load(f)

    return config


def validate_config(config: dict, base_dir: Path) -> None:
    """Validate config against the JSON schema."""
    schema_path = base_dir / "schemas" / "config_schema.yaml"
    with open(schema_path, "r") as f:
        schema = yaml.safe_load(f)

    try:
        validate(instance=config, schema=schema)
        click.echo("  Config validation passed.")
    except ValidationError as e:
        click.echo(f"  Config validation FAILED: {e.message}", err=True)
        sys.exit(1)


def apply_defaults(component: dict) -> dict:
    """Apply default values to a component config."""
    comp_type = component["type"]
    defaults = DEFAULTS.get(comp_type, {})

    # Merge defaults with provided values (provided values win)
    merged = {**defaults, **component}
    return merged


def generate_resource_name(project: str, environment: str, resource_type: str) -> str:
    """Generate a consistent resource name."""
    return f"{project}-{environment}-{resource_type}"


def render_module(env: Environment, component: dict, context: dict) -> str:
    """Render a single module template."""
    comp_type = component["type"]
    template_file = MODULE_MAP.get(comp_type)

    if not template_file:
        click.echo(f"  Warning: No template found for type '{comp_type}', skipping.", err=True)
        return ""

    template = env.get_template(template_file)

    # Build template context
    template_context = {
        **context,
        "component": component,
        "resource_prefix": generate_resource_name(
            context["project"], context["environment"], comp_type
        ),
    }

    return template.render(**template_context)


def generate_main_template(config: dict, component_outputs: list) -> str:
    """Generate the main CloudFormation template that includes all resources."""
    # Collect all resources and outputs from components
    all_resources = ""
    all_outputs = ""

    for output in component_outputs:
        if output.strip():
            all_resources += output + "\n"

    main_template = f"""AWSTemplateFormatVersion: '2010-09-09'
Description: '{config["project"]} - {config["environment"]} environment - Generated by CFT Accelerator'

{all_resources}"""

    return main_template


@click.command()
@click.argument("config_file", type=click.Path(exists=True))
@click.option(
    "--output-dir",
    default=None,
    help="Output directory for generated templates (default: ./output)",
)
@click.option("--dry-run", is_flag=True, help="Validate only, don't generate files")
def main(config_file: str, output_dir: str, dry_run: bool):
    """Generate CloudFormation templates from a config file.

    CONFIG_FILE: Path to your project YAML configuration file.
    """
    base_dir = Path(__file__).parent.resolve()

    click.echo("=" * 60)
    click.echo("  CloudFormation Accelerator - Template Generator")
    click.echo("=" * 60)
    click.echo()

    # Step 1: Load config
    click.echo("[1/4] Loading configuration...")
    config = load_config(config_file)
    click.echo(f"  Project: {config.get('project', 'unknown')}")
    click.echo(f"  Environment: {config.get('environment', 'unknown')}")
    click.echo(f"  Region: {config.get('region', 'unknown')}")
    click.echo(f"  Components: {len(config.get('components', []))}")
    click.echo()

    # Step 2: Validate
    click.echo("[2/4] Validating configuration...")
    validate_config(config, base_dir)
    click.echo()

    if dry_run:
        click.echo("Dry run complete. Config is valid.")
        return

    # Step 3: Render templates
    click.echo("[3/4] Generating CloudFormation templates...")

    # Setup Jinja2
    template_dir = base_dir / "modules"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )

    # Global context available to all templates
    context = {
        "project": config["project"],
        "environment": config["environment"],
        "region": config["region"],
        "tags": config.get("tags", {}),
    }

    # Render each component
    component_outputs = []
    for i, component in enumerate(config["components"]):
        comp_type = component["type"]
        click.echo(f"  [{i+1}] Generating: {comp_type}")

        # Apply defaults
        component = apply_defaults(component)

        # Render
        rendered = render_module(env, component, context)
        if rendered:
            component_outputs.append(rendered)

    click.echo()

    # Step 4: Write output
    click.echo("[4/4] Writing output files...")

    if output_dir is None:
        output_dir = base_dir / "output"
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate main template
    main_template = generate_main_template(config, component_outputs)

    output_file = output_dir / "main.yaml"
    with open(output_file, "w") as f:
        f.write(main_template)

    click.echo(f"  Written: {output_file}")
    click.echo()
    click.echo("=" * 60)
    click.echo("  Generation complete!")
    click.echo(f"  Output: {output_file}")
    click.echo()
    click.echo("  Deploy with:")
    click.echo(f"    aws cloudformation deploy \\")
    click.echo(f"      --template-file {output_file} \\")
    click.echo(f"      --stack-name {config['project']}-{config['environment']} \\")
    click.echo(f"      --capabilities CAPABILITY_NAMED_IAM")
    click.echo("=" * 60)


if __name__ == "__main__":
    main()
