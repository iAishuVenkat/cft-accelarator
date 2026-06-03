"""
CloudFormation Accelerator - MCP Server

An MCP server that generates Jinja2 CFT module templates for any AWS service
using the official AWS CloudFormation Resource Specification.

Tools:
  - list_aws_services: List all available AWS resource types
  - generate_cft_module: Generate a Jinja2 template for an AWS service
  - add_to_accelerator: Register the generated module in the accelerator catalog

Usage:
  Configured in .kiro/settings/mcp.json or run standalone:
    python mcp_server/server.py
"""

import json
import sys
import re
import urllib.request
from pathlib import Path
from typing import Any

# MCP SDK
try:
    from mcp.server import Server
    from mcp.server.stdio import run_server
    from mcp.types import Tool, TextContent
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False


# Paths
BASE_DIR = Path(__file__).parent.parent.resolve()
SPEC_CACHE_PATH = BASE_DIR / "mcp_server" / "cfn_spec_cache.json"
MODULES_DIR = BASE_DIR / "modules"
CATALOG_PATH = BASE_DIR / "catalog" / "services.yaml"

# AWS CloudFormation Resource Spec URL
CFN_SPEC_URL = "https://d1uauaxba7bl26.cloudfront.net/latest/gzip/CloudFormationResourceSpecification.json"

# Best practice configurations for common services
BEST_PRACTICES = {
    "encryption": "SSESpecification or similar encryption enabled",
    "logging": "CloudWatch logging enabled where applicable",
    "tags": "Tags propagated from project context",
    "deletion": "DeletionPolicy: Retain for stateful resources",
}


def load_cfn_spec() -> dict:
    """Load the AWS CloudFormation Resource Specification (cached)."""
    if SPEC_CACHE_PATH.exists():
        with open(SPEC_CACHE_PATH, "r") as f:
            return json.load(f)

    # Download fresh spec
    import gzip
    print("Downloading AWS CloudFormation Resource Specification...", file=sys.stderr)
    try:
        req = urllib.request.Request(CFN_SPEC_URL)
        req.add_header('Accept-Encoding', 'gzip')
        with urllib.request.urlopen(req, timeout=60) as response:
            data = response.read()
            # Decompress if gzipped
            try:
                data = gzip.decompress(data)
            except Exception:
                pass
            spec = json.loads(data.decode("utf-8"))

        # Cache it
        SPEC_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(SPEC_CACHE_PATH, "w") as f:
            json.dump(spec, f)

        return spec
    except Exception as e:
        print(f"Error downloading spec: {e}", file=sys.stderr)
        return {"ResourceTypes": {}, "PropertyTypes": {}}


def find_resource_type(query: str, spec: dict) -> list:
    """Find matching resource types from the spec."""
    query_lower = query.lower().replace(" ", "").replace("-", "").replace("_", "")
    resource_types = spec.get("ResourceTypes", {})

    matches = []
    for rt in resource_types:
        rt_lower = rt.lower().replace("::", "").replace("aws", "")
        # Exact service match
        if query_lower in rt_lower:
            matches.append(rt)

    # Sort: shorter names first (more specific)
    matches.sort(key=len)
    return matches[:20]


def get_properties(resource_type: str, spec: dict) -> dict:
    """Get properties for a resource type."""
    rt_info = spec.get("ResourceTypes", {}).get(resource_type, {})
    return rt_info.get("Properties", {})


def property_to_cfn_type(prop_info: dict) -> str:
    """Convert property spec to a display type."""
    ptype = prop_info.get("PrimitiveType", "")
    if ptype:
        return ptype
    item_type = prop_info.get("Type", "")
    if item_type == "List":
        return "List"
    if item_type == "Map":
        return "Map"
    return item_type or "Unknown"


def property_to_jinja_default(prop_name: str, prop_info: dict) -> str:
    """Generate a sensible Jinja2 placeholder for a property."""
    ptype = prop_info.get("PrimitiveType", prop_info.get("Type", ""))

    if ptype == "Boolean":
        # Default booleans based on common patterns
        if any(kw in prop_name.lower() for kw in ["encrypt", "enable", "active", "public"]):
            return "true"
        return "false"
    elif ptype == "Integer":
        return "{{ component." + to_snake_case(prop_name) + " }}"
    elif ptype == "String":
        return "{{ component." + to_snake_case(prop_name) + " }}"
    else:
        return "{{ component." + to_snake_case(prop_name) + " }}"


def to_snake_case(name: str) -> str:
    """Convert CamelCase to snake_case."""
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def to_kebab_case(name: str) -> str:
    """Convert CamelCase to kebab-case."""
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1-\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1-\2', s1).lower()


def generate_template(resource_type: str, spec: dict, service_key: str) -> str:
    """Generate a complete Jinja2 CFT module template."""
    properties = get_properties(resource_type, spec)
    service_short = resource_type.split("::")[-1]

    # Classify properties
    required_props = {k: v for k, v in properties.items() if v.get("Required", False)}
    optional_props = {k: v for k, v in properties.items() if not v.get("Required", False)}

    # Build the template
    lines = []
    lines.append(f"# ============================================================")
    lines.append(f"# {service_short} Module - {{{{ resource_prefix }}}}")
    lines.append(f"# Generated by CFT Accelerator MCP Server")
    lines.append(f"# Resource Type: {resource_type}")
    lines.append(f"# ============================================================")
    lines.append(f"")
    lines.append(f"Resources:")
    lines.append(f"  {service_short}Resource:")
    lines.append(f"    Type: {resource_type}")

    # Add DeletionPolicy for stateful resources
    if any(kw in resource_type.lower() for kw in ["table", "bucket", "database", "cluster", "instance", "filesystem"]):
        lines.append(f"    DeletionPolicy: Retain")

    lines.append(f"    Properties:")

    # Required properties
    for prop_name, prop_info in required_props.items():
        ptype = property_to_cfn_type(prop_info)
        snake = to_snake_case(prop_name)

        if ptype == "String":
            lines.append(f"      {prop_name}: {{{{ component.{snake} }}}}")
        elif ptype == "Integer" or ptype == "Long":
            lines.append(f"      {prop_name}: {{{{ component.{snake} }}}}")
        elif ptype == "Boolean":
            lines.append(f"      {prop_name}: {{{{ component.{snake} | lower }}}}")
        elif ptype == "List":
            lines.append(f"      {prop_name}:")
            lines.append(f"        - {{{{ component.{snake} }}}}")
        else:
            lines.append(f"      {prop_name}: {{{{ component.{snake} }}}}")

    # Key optional properties (skip overly complex ones)
    simple_optional = {k: v for k, v in optional_props.items()
                       if v.get("PrimitiveType") in ("String", "Integer", "Boolean", "Long")}

    for prop_name, prop_info in list(simple_optional.items())[:15]:
        ptype = property_to_cfn_type(prop_info)
        snake = to_snake_case(prop_name)

        lines.append(f"      {{% if component.{snake} is defined and component.{snake} %}}")
        if ptype == "Boolean":
            lines.append(f"      {prop_name}: {{{{ component.{snake} | lower }}}}")
        else:
            lines.append(f"      {prop_name}: {{{{ component.{snake} }}}}")
        lines.append(f"      {{% endif %}}")

    # Tags (if supported)
    if "Tags" in properties:
        lines.append(f"      Tags:")
        lines.append(f"        {{% for key, value in tags.items() %}}")
        lines.append(f"        - Key: {{{{ key }}}}")
        lines.append(f"          Value: {{{{ value }}}}")
        lines.append(f"        {{% endfor %}}")

    # Outputs
    lines.append(f"")
    lines.append(f"Outputs:")
    lines.append(f"  {service_short}Ref:")
    lines.append(f"    Description: {service_short} reference")
    lines.append(f"    Value: !Ref {service_short}Resource")
    lines.append(f"    Export:")
    lines.append(f"      Name: {{{{ resource_prefix }}}}-Ref")
    lines.append(f"")
    lines.append(f"  {service_short}Arn:")
    lines.append(f"    Description: {service_short} ARN")
    lines.append(f"    Value: !GetAtt {service_short}Resource.Arn")
    lines.append(f"    Export:")
    lines.append(f"      Name: {{{{ resource_prefix }}}}-Arn")

    return "\n".join(lines)


def generate_catalog_entry(resource_type: str, spec: dict, service_key: str) -> str:
    """Generate a catalog entry for services.yaml."""
    properties = get_properties(resource_type, spec)
    service_short = resource_type.split("::")[-1]
    service_name = resource_type.split("::")[1]

    # Determine category
    category_map = {
        "EC2": "Compute", "ECS": "Compute", "Lambda": "Compute",
        "RDS": "Database", "DynamoDB": "Database", "ElastiCache": "Database",
        "S3": "Storage", "EFS": "Storage",
        "SQS": "Messaging", "SNS": "Messaging", "Events": "Messaging",
        "Cognito": "Security", "KMS": "Security", "WAFv2": "Security",
        "CloudWatch": "Monitoring", "CloudTrail": "Monitoring",
        "CodePipeline": "CICD", "CodeBuild": "CICD",
        "ApiGateway": "Networking", "ElasticLoadBalancingV2": "Networking",
    }
    category = category_map.get(service_name, "Other")

    # Build options from required + key optional properties
    required_props = {k: v for k, v in properties.items() if v.get("Required", False)}
    simple_optional = {k: v for k, v in properties.items()
                       if not v.get("Required", False)
                       and v.get("PrimitiveType") in ("String", "Integer", "Boolean", "Long")}

    lines = []
    lines.append(f"  {service_key}:")
    lines.append(f'    name: "{service_short}"')
    lines.append(f'    description: "AWS {service_name} {service_short} resource"')
    lines.append(f'    category: {category}')
    lines.append(f"    options:")

    # Required properties as options
    for prop_name, prop_info in required_props.items():
        ptype = prop_info.get("PrimitiveType", "string")
        snake = to_snake_case(prop_name)
        lines.append(f"      {snake}:")
        lines.append(f'        description: "{prop_name}"')
        if ptype == "Boolean":
            lines.append(f"        type: boolean")
            lines.append(f"        default: false")
        elif ptype in ("Integer", "Long"):
            lines.append(f"        type: integer")
            lines.append(f"        default: 1")
        else:
            lines.append(f"        type: string")
            lines.append(f"        required: true")
        lines.append(f'        prompt: "{prop_name}"')

    # A few optional properties
    for prop_name, prop_info in list(simple_optional.items())[:8]:
        ptype = prop_info.get("PrimitiveType", "string")
        snake = to_snake_case(prop_name)
        lines.append(f"      {snake}:")
        lines.append(f'        description: "{prop_name}"')
        if ptype == "Boolean":
            lines.append(f"        type: boolean")
            lines.append(f"        default: false")
        elif ptype in ("Integer", "Long"):
            lines.append(f"        type: integer")
            lines.append(f"        default: 0")
        else:
            lines.append(f"        type: string")
            lines.append(f'        default: ""')
        lines.append(f'        prompt: "{prop_name}"')

    return "\n".join(lines)


def generate_defaults_entry(resource_type: str, spec: dict, service_key: str) -> str:
    """Generate DEFAULTS dict entry for generate.py."""
    properties = get_properties(resource_type, spec)

    simple_props = {k: v for k, v in properties.items()
                    if v.get("PrimitiveType") in ("String", "Integer", "Boolean", "Long")}

    lines = []
    lines.append(f'    "{service_key}": {{')
    for prop_name, prop_info in list(simple_props.items())[:10]:
        ptype = prop_info.get("PrimitiveType", "")
        snake = to_snake_case(prop_name)
        if ptype == "Boolean":
            lines.append(f'        "{snake}": False,')
        elif ptype in ("Integer", "Long"):
            lines.append(f'        "{snake}": 0,')
        else:
            lines.append(f'        "{snake}": "",')
    lines.append(f"    }},")

    return "\n".join(lines)


# ============================================================
# MCP Server Setup
# ============================================================

def setup_mcp_server():
    """Set up and return the MCP server (only if SDK available)."""
    if not MCP_AVAILABLE:
        return None

    server = Server("cft-accelerator-mcp")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """Return available tools."""
        return [
            Tool(
                name="list_aws_services",
                description="Search AWS CloudFormation resource types. Returns matching resource type names you can use with generate_cft_module.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search term (e.g., 'opensearch', 'batch', 'apprunner', 'mq', 'redshift')"
                        }
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="generate_cft_module",
                description="Generate a complete Jinja2 CloudFormation module template for an AWS resource type. Also returns catalog entry and defaults to add to the accelerator.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "resource_type": {
                            "type": "string",
                            "description": "Full AWS resource type (e.g., 'AWS::OpenSearchService::Domain', 'AWS::Batch::JobQueue')"
                        },
                        "service_key": {
                            "type": "string",
                            "description": "Short key for the accelerator (e.g., 'opensearch', 'batch-job-queue')"
                        }
                    },
                    "required": ["resource_type", "service_key"]
                }
            ),
            Tool(
                name="save_module",
                description="Save a generated module template to the accelerator's modules/ directory.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "service_key": {
                            "type": "string",
                            "description": "Module key (e.g., 'opensearch'). Will be saved as modules/{service_key}.yaml.j2"
                        },
                        "template_content": {
                            "type": "string",
                            "description": "The Jinja2 template content to save"
                        }
                    },
                    "required": ["service_key", "template_content"]
                }
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle tool calls."""

        if name == "list_aws_services":
            query = arguments.get("query", "")
            spec = load_cfn_spec()
            matches = find_resource_type(query, spec)

            if not matches:
                return [TextContent(type="text", text=f"No AWS resource types found matching '{query}'")]

            result = f"Found {len(matches)} matching resource types:\n\n"
            for rt in matches:
                props = get_properties(rt, spec)
                required = [k for k, v in props.items() if v.get("Required", False)]
                result += f"  - {rt}\n"
                if required:
                    result += f"    Required: {', '.join(required[:5])}\n"
                result += f"    Properties: {len(props)} total\n\n"

            return [TextContent(type="text", text=result)]

        elif name == "generate_cft_module":
            resource_type = arguments.get("resource_type", "")
            service_key = arguments.get("service_key", "")

            spec = load_cfn_spec()

            if resource_type not in spec.get("ResourceTypes", {}):
                return [TextContent(type="text", text=f"Error: '{resource_type}' not found in AWS CloudFormation spec.\nUse list_aws_services to find the correct type name.")]

            # Generate all pieces
            template = generate_template(resource_type, spec, service_key)
            catalog_entry = generate_catalog_entry(resource_type, spec, service_key)
            defaults_entry = generate_defaults_entry(resource_type, spec, service_key)

            result = f"""# Generated Module for {resource_type}
# Service Key: {service_key}

## 1. Template (save as modules/{service_key}.yaml.j2)

```yaml
{template}
```

## 2. Catalog Entry (add to catalog/services.yaml)

```yaml
{catalog_entry}
```

## 3. Defaults Entry (add to generate.py DEFAULTS dict)

```python
{defaults_entry}
```

## 4. Module Map Entry (add to generate.py MODULE_MAP dict)

```python
    "{service_key}": "{service_key}.yaml.j2",
```

## 5. Schema Entry (add to schemas/config_schema.yaml enum list)

```yaml
            - {service_key}
```
"""
            return [TextContent(type="text", text=result)]

        elif name == "save_module":
            service_key = arguments.get("service_key", "")
            template_content = arguments.get("template_content", "")

            if not service_key or not template_content:
                return [TextContent(type="text", text="Error: service_key and template_content are required.")]

            output_path = MODULES_DIR / f"{service_key}.yaml.j2"
            with open(output_path, "w") as f:
                f.write(template_content)

            return [TextContent(type="text", text=f"Module saved to: {output_path}")]

        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    return server


async def main():
    """Run the MCP server."""
    from mcp.server.stdio import stdio_server

    srv = setup_mcp_server()
    if srv is None:
        print("Error: MCP SDK not installed. Run: pip install mcp", file=sys.stderr)
        sys.exit(1)

    async with stdio_server() as (read_stream, write_stream):
        await srv.run(read_stream, write_stream, srv.create_initialization_options())


if __name__ == "__main__":
    if not MCP_AVAILABLE:
        print("Error: MCP SDK not installed. Run: pip install mcp", file=sys.stderr)
        sys.exit(1)
    import asyncio
    asyncio.run(main())
