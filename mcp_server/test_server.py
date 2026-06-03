"""Quick test for the MCP server logic (without running as MCP)."""

import json
import sys
import re
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.resolve()
SPEC_CACHE_PATH = BASE_DIR / "mcp_server" / "cfn_spec_cache.json"
CFN_SPEC_URL = "https://d1uauaxba7bl26.cloudfront.net/latest/gzip/CloudFormationResourceSpecification.json"


def load_cfn_spec():
    if SPEC_CACHE_PATH.exists():
        with open(SPEC_CACHE_PATH, "r") as f:
            return json.load(f)
    print("Downloading AWS CloudFormation Resource Specification...")
    import gzip
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
    SPEC_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SPEC_CACHE_PATH, "w") as f:
        json.dump(spec, f)
    return spec


def find_resource_type(query, spec):
    query_lower = query.lower().replace(" ", "").replace("-", "").replace("_", "")
    resource_types = spec.get("ResourceTypes", {})
    matches = []
    for rt in resource_types:
        rt_lower = rt.lower().replace("::", "").replace("aws", "")
        if query_lower in rt_lower:
            matches.append(rt)
    matches.sort(key=len)
    return matches[:20]


def to_snake_case(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


if __name__ == "__main__":
    print("Loading spec...")
    spec = load_cfn_spec()
    total = len(spec.get("ResourceTypes", {}))
    print(f"Loaded {total} resource types.")

    # Test searches
    for q in ["opensearch", "batch", "apprunner", "mq", "redshift", "transfer"]:
        matches = find_resource_type(q, spec)
        print(f"\n  '{q}' → {len(matches)} matches:")
        for m in matches[:3]:
            props = spec["ResourceTypes"][m].get("Properties", {})
            print(f"    {m} ({len(props)} properties)")

    # Test template generation
    print("\n\n" + "=" * 60)
    print("  GENERATED TEMPLATE: AWS::OpenSearchService::Domain")
    print("=" * 60 + "\n")

    # Import generator from server
    sys.path.insert(0, str(Path(__file__).parent))
    from server import generate_template, generate_catalog_entry

    template = generate_template("AWS::OpenSearchService::Domain", spec, "opensearch")
    print(template)

    print("\n\n" + "=" * 60)
    print("  CATALOG ENTRY")
    print("=" * 60 + "\n")
    catalog = generate_catalog_entry("AWS::OpenSearchService::Domain", spec, "opensearch")
    print(catalog)
