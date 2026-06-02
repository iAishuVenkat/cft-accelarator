"""
CloudFormation Accelerator - Quick Build (Non-Interactive)

Specify individual AWS services via command line, tool builds
the config from catalog templates and generates CloudFormation.

Usage:
    python quick_build.py --project my-app --env prod --services vpc,ecs-service,rds --image my-app:latest
    python quick_build.py --project my-api --env dev --services lambda,api-gateway --handler app.handler --runtime python3.12
    python quick_build.py --project my-site --env prod --services s3-static-site,cloudfront
    python quick_build.py --list  (show all available services)
"""

import sys
import yaml
import click
import subprocess
from pathlib import Path


def load_catalog(base_dir: Path) -> dict:
    """Load the service catalog."""
    catalog_path = base_dir / "catalog" / "services.yaml"
    with open(catalog_path, "r") as f:
        catalog = yaml.safe_load(f)
    return catalog.get("services", {})


def list_services(services: dict):
    """Print all available services."""
    click.echo()
    click.echo("Available AWS services in catalog:")
    click.echo("─" * 60)

    categories = {}
    for key, svc in services.items():
        cat = svc.get("category", "Other")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append((key, svc))

    for category, items in categories.items():
        click.echo(f"\n  [{category}]")
        for key, svc in items:
            requires = svc.get("requires", [])
            dep_note = f" (requires: {', '.join(requires)})" if requires else ""
            click.echo(f"    {key:<20} {svc['name']}{dep_note}")

    click.echo()
    click.echo("Usage example:")
    click.echo("  python quick_build.py --project my-app --services vpc,ecs-service,rds --image my-app:latest")
    click.echo()


def resolve_dependencies(requested: list, services: dict) -> list:
    """Auto-add required dependencies."""
    resolved = []
    resolved_keys = set()

    for key in requested:
        if key not in services:
            click.echo(f"Error: Unknown service '{key}'. Use --list to see available services.", err=True)
            sys.exit(1)

        svc = services[key]
        # Add dependencies first
        for dep in svc.get("requires", []):
            if dep not in resolved_keys:
                resolved.append(dep)
                resolved_keys.add(dep)
                click.echo(f"  Auto-added dependency: {dep}")

        if key not in resolved_keys:
            resolved.append(key)
            resolved_keys.add(key)

    return resolved


def build_component(key: str, svc: dict, cli_args: dict) -> dict:
    """Build a component config from catalog defaults + CLI overrides."""
    component = {"type": key}
    options = svc.get("options", {})

    for opt_key, opt in options.items():
        # Check if user provided this via CLI
        cli_value = cli_args.get(opt_key)
        if cli_value is not None:
            component[opt_key] = cli_value
        elif "default" in opt and opt["default"] != {}:
            component[opt_key] = opt["default"]
        elif opt.get("required"):
            click.echo(f"Error: --{opt_key} is required for service '{key}'.", err=True)
            sys.exit(1)

    return component


@click.command()
@click.option("--project", "-p", help="Project name (lowercase, hyphens ok)")
@click.option("--env", "-e", "environment", default="dev", help="Environment: dev, staging, prod")
@click.option("--region", "-r", default="us-east-1", help="AWS region")
@click.option("--services", "-s", help="Comma-separated AWS services (e.g., vpc,ecs-service,rds)")
@click.option("--image", default=None, help="Container image for ECS")
@click.option("--handler", default=None, help="Lambda handler")
@click.option("--runtime", default=None, help="Lambda runtime")
@click.option("--cpu", default=None, type=int, help="ECS CPU units")
@click.option("--memory", default=None, type=int, help="ECS memory MB")
@click.option("--engine", default=None, help="RDS/Aurora/ElastiCache engine")
@click.option("--instance-class", "instance_class", default=None, help="RDS instance class")
@click.option("--instance-type", "instance_type", default=None, help="EC2/ASG instance type")
@click.option("--multi-az", "multi_az", default=None, type=bool, help="RDS Multi-AZ")
@click.option("--table-name", "table_name", default=None, help="DynamoDB table name")
@click.option("--repository-name", "repository_name", default=None, help="ECR repository name")
@click.option("--domain", default=None, help="Domain name (Route53/SES)")
@click.option("--secret-name", "secret_name", default=None, help="Secrets Manager secret name")
@click.option("--alias", default=None, help="KMS key alias")
@click.option("--repo-name", "repo_name", default=None, help="CodePipeline repository name")
@click.option("--api-name", "api_name", default=None, help="AppSync API name")
@click.option("--database-name", "database_name", default=None, help="Glue database name")
@click.option("--output-location", "output_location", default=None, help="Athena output S3 path")
@click.option("--alarm-name", "alarm_name", default=None, help="CloudWatch alarm name")
@click.option("--metric-name", "metric_name", default=None, help="CloudWatch metric name")
@click.option("--namespace", default=None, help="CloudWatch metric namespace")
@click.option("--threshold", default=None, type=int, help="CloudWatch alarm threshold")
@click.option("--team", default="engineering", help="Team tag")
@click.option("--list", "list_only", is_flag=True, help="List all available services")
@click.option("--dry-run", is_flag=True, help="Generate config only, don't produce CFT")
def main(project, environment, region, services, image, handler, runtime,
         cpu, memory, engine, instance_class, instance_type, multi_az,
         table_name, repository_name, domain, secret_name, alias,
         repo_name, api_name, database_name, output_location,
         alarm_name, metric_name, namespace, threshold,
         team, list_only, dry_run):
    """Build CloudFormation by specifying individual AWS services.

    Example:
        python quick_build.py --project my-app --services vpc,ecs-service,rds --image my-app:latest
    """
    base_dir = Path(__file__).parent.resolve()
    catalog = load_catalog(base_dir)

    # List mode
    if list_only:
        list_services(catalog)
        return

    # Validate required inputs
    if not project:
        click.echo("Error: --project is required.", err=True)
        sys.exit(1)
    if not services:
        click.echo("Error: --services is required. Use --list to see available services.", err=True)
        sys.exit(1)

    # Parse services
    requested = [s.strip() for s in services.split(",")]

    click.echo()
    click.echo(f"  Project:  {project} ({environment})")
    click.echo(f"  Region:   {region}")
    click.echo(f"  Services: {', '.join(requested)}")
    click.echo()

    # Resolve dependencies
    resolved = resolve_dependencies(requested, catalog)

    # CLI args that can override defaults
    cli_args = {}
    if image:
        cli_args["image"] = image
    if handler:
        cli_args["handler"] = handler
    if runtime:
        cli_args["runtime"] = runtime
    if cpu:
        cli_args["cpu"] = cpu
    if memory:
        cli_args["memory"] = memory
    if engine:
        cli_args["engine"] = engine
    if instance_class:
        cli_args["instance_class"] = instance_class
    if instance_type:
        cli_args["instance_type"] = instance_type
    if multi_az is not None:
        cli_args["multi_az"] = multi_az
    if table_name:
        cli_args["table_name"] = table_name
    if repository_name:
        cli_args["repository_name"] = repository_name
    if domain:
        cli_args["domain_name"] = domain
        cli_args["domain"] = domain
    if secret_name:
        cli_args["secret_name"] = secret_name
    if alias:
        cli_args["alias"] = alias
    if repo_name:
        cli_args["repo_name"] = repo_name
    if api_name:
        cli_args["api_name"] = api_name
    if database_name:
        cli_args["database_name"] = database_name
    if output_location:
        cli_args["output_location"] = output_location
    if alarm_name:
        cli_args["alarm_name"] = alarm_name
    if metric_name:
        cli_args["metric_name"] = metric_name
    if namespace:
        cli_args["namespace"] = namespace
    if threshold:
        cli_args["threshold"] = threshold

    # Build components
    components = []
    for key in resolved:
        svc = catalog[key]
        component = build_component(key, svc, cli_args)
        components.append(component)

    # Assemble config
    config = {
        "project": project,
        "environment": environment,
        "region": region,
        "tags": {"team": team, "managed-by": "cft-accelerator"},
        "components": components,
    }

    # Write config
    config_filename = f"{project}-{environment}.yaml"
    config_path = base_dir / "output" / config_filename
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    click.echo(f"  Config saved: output/{config_filename}")

    if dry_run:
        click.echo("  Dry run complete - config generated, CFT not produced.")
        return

    # Generate CFT
    click.echo()
    generator = base_dir / "generate.py"
    result = subprocess.run(
        [sys.executable, str(generator), str(config_path)],
        cwd=str(base_dir),
    )

    if result.returncode != 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
