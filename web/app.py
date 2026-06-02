"""
CloudFormation Accelerator - Web UI

A Flask web app that provides a visual interface for the CFT accelerator.
Same functionality as the CLI wizard, but in the browser.

Usage:
    python web/app.py
    Then open http://localhost:5000
"""

import sys
import yaml
import os
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file

# Add parent directory to path so we can import generate module
sys.path.insert(0, str(Path(__file__).parent.parent))

from generate import (
    load_config, validate_config, apply_defaults, render_module,
    generate_main_template, MODULE_MAP, DEFAULTS
)
from jinja2 import Environment, FileSystemLoader

app = Flask(__name__, template_folder=str(Path(__file__).parent / "templates"))

BASE_DIR = Path(__file__).parent.parent.resolve()


def load_catalog():
    """Load the service catalog."""
    catalog_path = BASE_DIR / "catalog" / "services.yaml"
    with open(catalog_path, "r") as f:
        catalog = yaml.safe_load(f)
    return catalog.get("services", {})


@app.route("/")
def index():
    """Main page with service selection UI."""
    catalog = load_catalog()
    # Group by category
    categories = {}
    for key, svc in catalog.items():
        cat = svc.get("category", "Other")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append({"key": key, **svc})

    return render_template("index.html", categories=categories)


@app.route("/api/catalog")
def get_catalog():
    """Return catalog as JSON."""
    catalog = load_catalog()
    return jsonify(catalog)


@app.route("/api/generate", methods=["POST"])
def generate():
    """Generate CloudFormation from submitted config."""
    data = request.json

    project = data.get("project", "").strip().lower().replace(" ", "-")
    environment = data.get("environment", "dev")
    region = data.get("region", "us-east-1")
    tags = data.get("tags", {})
    components = data.get("components", [])

    if not project:
        return jsonify({"error": "Project name is required"}), 400
    if not components:
        return jsonify({"error": "At least one service must be selected"}), 400

    # Build config
    config = {
        "project": project,
        "environment": environment,
        "region": region,
        "tags": tags,
        "components": components,
    }

    # Validate
    try:
        schema_path = BASE_DIR / "schemas" / "config_schema.yaml"
        with open(schema_path, "r") as f:
            schema = yaml.safe_load(f)
        from jsonschema import validate, ValidationError
        validate(instance=config, schema=schema)
    except ValidationError as e:
        return jsonify({"error": f"Validation failed: {e.message}"}), 400

    # Generate templates
    template_dir = BASE_DIR / "modules"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )

    context = {
        "project": project,
        "environment": environment,
        "region": region,
        "tags": tags,
    }

    component_outputs = []
    for component in components:
        comp_type = component["type"]
        component = apply_defaults(component)
        rendered = render_module(env, component, context)
        if rendered:
            component_outputs.append(rendered)

    # Generate main template
    main_template = generate_main_template(config, component_outputs)

    # Save files
    output_dir = BASE_DIR / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    config_filename = f"{project}-{environment}.yaml"
    config_path = output_dir / config_filename
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    output_path = output_dir / "main.yaml"
    with open(output_path, "w") as f:
        f.write(main_template)

    return jsonify({
        "success": True,
        "config_file": config_filename,
        "template": main_template,
        "deploy_command": f"aws cloudformation deploy --template-file output/main.yaml --stack-name {project}-{environment} --capabilities CAPABILITY_NAMED_IAM",
    })


@app.route("/api/download")
def download_template():
    """Download the generated main.yaml."""
    output_path = BASE_DIR / "output" / "main.yaml"
    if output_path.exists():
        return send_file(output_path, as_attachment=True, download_name="main.yaml")
    return jsonify({"error": "No template generated yet"}), 404


if __name__ == "__main__":
    print("\n  CloudFormation Accelerator - Web UI")
    print("  Open http://localhost:5000 in your browser\n")
    app.run(debug=True, port=5000)
