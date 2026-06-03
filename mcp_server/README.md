# CFT Accelerator MCP Server

An MCP server that generates Jinja2 CloudFormation module templates for any AWS service using the official AWS CloudFormation Resource Specification.

## Setup

### 1. Install dependencies

```bash
cd mcp_server
pip install -r requirements.txt
```

### 2. Configure in Kiro

Add to your `.kiro/settings/mcp.json`:

```json
{
  "mcpServers": {
    "cft-generator": {
      "command": "python",
      "args": ["E:/IAC/cft-accelerator/mcp_server/server.py"],
      "disabled": false
    }
  }
}
```

### 3. Use in Kiro

Once configured, you can say things like:

- "Search for AWS OpenSearch resource types"
- "Generate a CFT module for AWS::OpenSearchService::Domain"
- "Save the module as opensearch"

## Available Tools

| Tool | Description |
|------|-------------|
| `list_aws_services` | Search AWS resource types by keyword |
| `generate_cft_module` | Generate a complete Jinja2 template + catalog entry + defaults |
| `save_module` | Save the generated template to the modules/ directory |

## How It Works

1. Downloads the official AWS CloudFormation Resource Specification (cached locally)
2. Looks up the resource type you asked for
3. Reads all properties (names, types, required flags)
4. Builds a Jinja2 template with parameterized values
5. Generates catalog entry, defaults, and schema entries
6. Returns everything you need to add the service to the accelerator
