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


# ============================================================
# MCP-Powered Module Generator Endpoints
# ============================================================

# Import MCP server utilities
sys.path.insert(0, str(ROOT_DIR / "mcp_server"))
from server import (
    load_cfn_spec, find_resource_type, get_properties,
    generate_template, generate_catalog_entry, generate_defaults_entry
)


@app.route("/api/mcp/search", methods=["GET"])
def mcp_search():
    """Search AWS resource types from the CloudFormation spec."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Query parameter 'q' is required"}), 400

    spec = load_cfn_spec()
    matches = find_resource_type(query, spec)

    results = []
    for rt in matches:
        props = get_properties(rt, spec)
        required = [k for k, v in props.items() if v.get("Required", False)]
        results.append({
            "resource_type": rt,
            "service": rt.split("::")[1] if "::" in rt else "",
            "resource": rt.split("::")[-1] if "::" in rt else rt,
            "total_properties": len(props),
            "required_properties": required,
        })

    return jsonify({
        "query": query,
        "count": len(results),
        "results": results,
    })


@app.route("/api/mcp/generate", methods=["POST"])
def mcp_generate():
    """Generate a Jinja2 module template for an AWS resource type."""
    data = request.json
    resource_type = data.get("resource_type", "").strip()
    service_key = data.get("service_key", "").strip()

    if not resource_type:
        return jsonify({"error": "resource_type is required"}), 400
    if not service_key:
        # Auto-generate key from resource type
        service_key = resource_type.split("::")[-1].lower()
        service_key = service_key.replace(" ", "-")

    spec = load_cfn_spec()

    if resource_type not in spec.get("ResourceTypes", {}):
        return jsonify({"error": f"'{resource_type}' not found in AWS CloudFormation spec."}), 404

    # Generate template and metadata
    template = generate_template(resource_type, spec, service_key)
    catalog_entry = generate_catalog_entry(resource_type, spec, service_key)
    defaults_entry = generate_defaults_entry(resource_type, spec, service_key)

    return jsonify({
        "success": True,
        "resource_type": resource_type,
        "service_key": service_key,
        "template": template,
        "catalog_entry": catalog_entry,
        "defaults_entry": defaults_entry,
        "module_map_entry": f'    "{service_key}": "{service_key}.yaml.j2",',
        "schema_entry": f"            - {service_key}",
    })


@app.route("/api/mcp/save", methods=["POST"])
def mcp_save():
    """Save a generated module to the modules/ directory and register it."""
    data = request.json
    service_key = data.get("service_key", "").strip()
    template_content = data.get("template", "").strip()

    if not service_key or not template_content:
        return jsonify({"error": "service_key and template are required"}), 400

    # Save the template file
    module_path = ROOT_DIR / "modules" / f"{service_key}.yaml.j2"
    with open(module_path, "w") as f:
        f.write(template_content)

    return jsonify({
        "success": True,
        "message": f"Module saved as modules/{service_key}.yaml.j2",
        "path": str(module_path),
    })
