"""
CloudFormation Accelerator - Vercel Serverless Entry Point
"""

import sys
import os
import yaml
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file

# Set up paths
ROOT_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT_DIR))

from generate import (
    apply_defaults, render_module, generate_main_template, MODULE_MAP, DEFAULTS
)
from jinja2 import Environment, FileSystemLoader

# Create Flask app with correct template folder
app = Flask(__name__, template_folder=str(ROOT_DIR / "web" / "templates"))


def load_catalog():
    """Load the service catalog."""
    catalog_path = ROOT_DIR / "catalog" / "services.yaml"
    with open(catalog_path, "r") as f:
        catalog = yaml.safe_load(f)
    return catalog.get("services", {})


@app.route("/")
def index():
    """Main page."""
    catalog = load_catalog()
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

    # Validate required fields are not empty
    catalog = load_catalog()
    for comp in components:
        comp_type = comp.get("type", "")
        if comp_type in catalog:
            svc = catalog[comp_type]
            options = svc.get("options", {})
            for opt_key, opt in options.items():
                if opt.get("required") and not opt.get("default"):
                    value = comp.get(opt_key, "")
                    if not value or str(value).strip() == "":
                        return jsonify({
                            "error": f"'{opt.get('prompt', opt_key)}' is required for {svc['name']}. Please go back and fill it in."
                        }), 400

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
        schema_path = ROOT_DIR / "schemas" / "config_schema.yaml"
        with open(schema_path, "r") as f:
            schema = yaml.safe_load(f)
        from jsonschema import validate, ValidationError
        validate(instance=config, schema=schema)
    except ValidationError as e:
        return jsonify({"error": f"Validation failed: {e.message}"}), 400

    # Generate templates
    template_dir = ROOT_DIR / "modules"
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

    return jsonify({
        "success": True,
        "template": main_template,
        "deploy_command": f"aws cloudformation deploy --template-file main.yaml --stack-name {project}-{environment} --capabilities CAPABILITY_NAMED_IAM",
    })
