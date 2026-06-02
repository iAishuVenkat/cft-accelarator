"""
CloudFormation Accelerator - Interactive Wizard

Users pick individual AWS services from the catalog, the wizard collects
their configuration inputs, builds a config file, and generates the CFT.

Usage:
    python wizard.py
"""

import sys
import yaml
import click
import subprocess
from pathlib import Path


def load_catalog(base_dir: Path) -> dict:
    """Load the service catalog."""
    catalog_path = base_dir / "catalog" / "services.yaml"
    if not catalog_path.exists():
        click.echo(f"Error: Catalog not found at {catalog_path}", err=True)
        sys.exit(1)

    with open(catalog_path, "r") as f:
        catalog = yaml.safe_load(f)

    return catalog.get("services", {})


def display_services(services: dict) -> list:
    """Display all available AWS services grouped by category."""
    categories = {}
    for key, svc in services.items():
        cat = svc.get("category", "Other")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append((key, svc))

    click.echo()
    click.echo("  Available AWS Services:")
    click.echo("  " + "─" * 55)

    index = 1
    service_list = []

    for category, items in categories.items():
        click.echo()
        click.echo(f"  [{category}]")
        for key, svc in items:
            click.echo(f"    {index}. {svc['name']}")
            click.echo(f"       {svc['description']}")
            service_list.append((key, svc))
            index += 1

    click.echo()
    return service_list


def get_project_info() -> dict:
    """Collect project-level information."""
    click.echo()
    click.echo("─" * 60)
    click.echo("  STEP 1: Project Details")
    click.echo("─" * 60)
    click.echo()

    project = click.prompt(
        "  Project name (lowercase, hyphens ok)",
        type=str
    ).strip().lower().replace(" ", "-")

    environment = click.prompt(
        "  Environment",
        type=click.Choice(["dev", "staging", "prod"]),
        default="dev"
    )

    region = click.prompt(
        "  AWS Region",
        type=str,
        default="us-east-1"
    )

    # Tags
    click.echo()
    tags = {"managed-by": "cft-accelerator"}
    add_tags = click.confirm("  Add tags to all resources?", default=True)
    if add_tags:
        team = click.prompt("    Team name", default="engineering")
        tags["team"] = team

        while click.confirm("    Add another tag?", default=False):
            key = click.prompt("      Tag key")
            value = click.prompt("      Tag value")
            tags[key] = value

    return {
        "project": project,
        "environment": environment,
        "region": region,
        "tags": tags,
    }


def match_service_by_name(input_text: str, service_list: list, services: dict) -> list:
    """Match user text input to services with smart priority matching."""
    input_lower = input_text.lower().strip()

    # 1. Exact key match (e.g., "vpc", "ecs-service", "rds", "ses", "kms")
    for key, svc in service_list:
        if key == input_lower:
            return [(key, svc)]

    # 2. Exact match on short name/abbreviation in the service name
    #    e.g., "SES" matches "SES (Email Service)", "KMS" matches "KMS (Encryption Key)"
    for key, svc in service_list:
        name_lower = svc["name"].lower()
        # Check if input matches the abbreviation (text before the first parenthesis)
        short_name = name_lower.split("(")[0].strip()
        if input_lower == short_name:
            return [(key, svc)]

    # 3. Key starts with input (e.g., "cloud" matches "cloudfront", "cloudtrail", "cloudwatch-*")
    matches = []
    for key, svc in service_list:
        if key.startswith(input_lower):
            matches.append((key, svc))
    if matches:
        return matches

    # 4. Input is a significant prefix of the key (at least 3 chars, starts with)
    if len(input_lower) >= 3:
        for key, svc in service_list:
            name_lower = svc["name"].lower()
            # Match beginning of key parts (split by dash)
            key_parts = key.split("-")
            if any(part.startswith(input_lower) for part in key_parts):
                matches.append((key, svc))
        if matches:
            return matches

    # 5. Broad substring match (only if 4+ chars to avoid "se" matching everything)
    if len(input_lower) >= 4:
        for key, svc in service_list:
            name_lower = svc["name"].lower()
            if (input_lower in key or
                input_lower in name_lower or
                input_lower.replace(" ", "-") in key):
                matches.append((key, svc))

    return matches


def select_services(services: dict, service_list: list) -> list:
    """Let user pick which AWS services they need."""
    click.echo()
    click.echo("─" * 60)
    click.echo("  STEP 2: Select AWS Services")
    click.echo("─" * 60)
    click.echo()
    click.echo("  Enter numbers OR service names (comma-separated).")
    click.echo("  Examples:  1,2,4")
    click.echo("             vpc, ecs-service, rds")
    click.echo("             s3, lambda, cloudfront")
    click.echo()

    selection = click.prompt("  Your selection").strip()
    parts = [x.strip() for x in selection.split(",") if x.strip()]

    selected = []
    selected_keys = set()

    for part in parts:
        # Try as number first
        if part.isdigit():
            idx = int(part)
            if 1 <= idx <= len(service_list):
                key, svc = service_list[idx - 1]
                if key not in selected_keys:
                    selected.append((key, svc))
                    selected_keys.add(key)
        else:
            # Try matching by name/keyword
            matches = match_service_by_name(part, service_list, services)
            if matches:
                for key, svc in matches:
                    if key not in selected_keys:
                        selected.append((key, svc))
                        selected_keys.add(key)
            else:
                click.echo(f"  Warning: Could not match '{part}' to any service, skipping.")

    if not selected:
        click.echo("  Error: No services selected. Please try again.", err=True)
        sys.exit(1)

    # Check dependencies and auto-add
    deps_added = []

    for key, svc in list(selected):
        requires = svc.get("requires", [])
        for dep in requires:
            if dep not in selected_keys:
                selected_keys.add(dep)
                dep_svc = services[dep]
                selected.insert(0, (dep, dep_svc))
                deps_added.append(dep_svc["name"])

    if deps_added:
        click.echo()
        click.echo(f"  Auto-added dependencies: {', '.join(deps_added)}")

    click.echo()
    click.echo("  You selected:")
    for key, svc in selected:
        click.echo(f"    ✓ {svc['name']}")

    return selected


def configure_service(key: str, svc: dict) -> dict:
    """Collect configuration for a single service."""
    click.echo()
    click.echo(f"  Configuring: {svc['name']}")
    click.echo(f"  {'·' * 45}")

    component = {"type": key}
    options = svc.get("options", {})

    # Ask if they want to customize or use defaults
    has_required = any(opt.get("required") for opt in options.values())

    if not has_required:
        customize = click.confirm(
            f"    Customize settings? (No = use best-practice defaults)",
            default=False
        )
        if not customize:
            # Apply all defaults
            for opt_key, opt in options.items():
                if "default" in opt and opt["default"] != {}:
                    component[opt_key] = opt["default"]
            return component

    # Collect each option
    for opt_key, opt in options.items():
        opt_type = opt.get("type", "string")
        default = opt.get("default")
        required = opt.get("required", False)
        prompt_text = f"    {opt.get('prompt', opt_key)}"

        if opt_type == "choice":
            choices = opt["choices"]
            str_choices = [str(c) for c in choices]
            value = click.prompt(
                prompt_text,
                type=click.Choice(str_choices),
                default=str(default) if default else None
            )
            # Convert back to int if original choices were int
            if isinstance(choices[0], int):
                value = int(value)
        elif opt_type == "boolean":
            value = click.confirm(prompt_text, default=default)
        elif opt_type == "integer":
            value = click.prompt(prompt_text, type=int, default=default)
        elif opt_type == "key_value":
            value = {}
            if click.confirm(f"    {opt.get('prompt', 'Add key-value pairs')}?", default=False):
                while True:
                    k = click.prompt("      Key")
                    v = click.prompt("      Value")
                    value[k] = v
                    if not click.confirm("      Add another?", default=False):
                        break
            if not value:
                continue  # Skip empty env vars
        else:
            # String type
            if required and not default:
                value = click.prompt(prompt_text, type=str)
            else:
                value = click.prompt(prompt_text, type=str, default=default)

        if value != "" and value != {}:
            component[opt_key] = value

    return component


def build_and_generate(project_info: dict, selected_services: list, base_dir: Path):
    """Build config file and run the generator."""
    click.echo()
    click.echo("─" * 60)
    click.echo("  STEP 3: Configure Each Service")
    click.echo("─" * 60)

    components = []
    for key, svc in selected_services:
        component = configure_service(key, svc)
        components.append(component)

    # Assemble final config
    config = {
        **project_info,
        "components": components,
    }

    # Write config
    click.echo()
    click.echo("─" * 60)
    click.echo("  GENERATING")
    click.echo("─" * 60)
    click.echo()

    config_filename = f"{project_info['project']}-{project_info['environment']}.yaml"
    config_path = base_dir / "output" / config_filename
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    click.echo(f"  Config saved: {config_path}")
    click.echo()

    # Run generator
    generator = base_dir / "generate.py"
    result = subprocess.run(
        [sys.executable, str(generator), str(config_path)],
        cwd=str(base_dir),
    )

    if result.returncode == 0:
        click.echo()
        click.echo("╔══════════════════════════════════════════════════════════╗")
        click.echo("║                      ALL DONE!                          ║")
        click.echo("╠══════════════════════════════════════════════════════════╣")
        click.echo(f"║  Config:   output/{config_filename:<37}║")
        click.echo(f"║  Template: output/main.yaml                             ║")
        click.echo("║                                                          ║")
        click.echo("║  Deploy with:                                            ║")
        click.echo("║    aws cloudformation deploy \\                           ║")
        click.echo("║      --template-file output/main.yaml \\                  ║")
        click.echo(f"║      --stack-name {project_info['project']}-{project_info['environment']:<27}║")
        click.echo("║      --capabilities CAPABILITY_NAMED_IAM                 ║")
        click.echo("╚══════════════════════════════════════════════════════════╝")
    else:
        click.echo("  Generation failed. Check errors above.", err=True)
        sys.exit(1)


@click.command()
def main():
    """Interactive wizard: pick AWS services, configure them, get CloudFormation."""
    base_dir = Path(__file__).parent.resolve()

    click.echo()
    click.echo("╔══════════════════════════════════════════════════════════╗")
    click.echo("║     CloudFormation Accelerator - Service Wizard         ║")
    click.echo("╠══════════════════════════════════════════════════════════╣")
    click.echo("║  Pick the AWS services you need, answer a few           ║")
    click.echo("║  questions, and get production-ready CloudFormation.     ║")
    click.echo("╚══════════════════════════════════════════════════════════╝")

    # Load catalog
    services = load_catalog(base_dir)

    # Display and select services
    service_list = display_services(services)

    # Get project info
    project_info = get_project_info()

    # Select services
    selected = select_services(services, service_list)

    # Configure and generate
    build_and_generate(project_info, selected, base_dir)


if __name__ == "__main__":
    main()
