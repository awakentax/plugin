#!/usr/bin/env python3
"""Check the distributable package without credentials or third-party dependencies."""

import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def package_path(value):
    path = Path(value)
    require(not path.is_absolute() and ".." not in path.parts,
            f"Path must be relative to the package: {value}")
    resolved = (ROOT / path).resolve()
    require(resolved.is_relative_to(ROOT) and resolved.exists(),
            f"Missing or external package path: {value}")
    return resolved


def main():
    manifest = json.loads((ROOT / ".cursor-plugin/plugin.json").read_text())
    require(re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", manifest["name"]),
            "Invalid plugin name")
    require(re.fullmatch(r"\d+\.\d+\.\d+", manifest["version"]), "Invalid release version")
    require(manifest.get("description") and manifest.get("author", {}).get("name"),
            "Missing listing description or author")
    for name in ("README.md", "LICENSE"):
        package_path(name)
    ET.parse(package_path(manifest["logo"]))

    skill_root = package_path(manifest["skills"])
    skills = sorted(skill_root.glob("*/SKILL.md"))
    require(skills, "No skills discovered")
    for skill in skills:
        text = skill.read_text()
        require(text.startswith("---\n") and "\n---\n" in text[4:],
                f"Missing skill frontmatter: {skill}")
        frontmatter = text.split("---", 2)[1]
        name = re.search(r"^name: ([a-z0-9-]+)$", frontmatter, re.M)
        require(name and name[1] == skill.parent.name, f"Invalid skill name: {skill}")
        require(re.search(r"^description: \S.+$", frontmatter, re.M),
                f"Missing skill description: {skill}")
        for target in re.findall(r"\]\(([^)]+)\)", text):
            if not target.startswith(("https:", "http:", "#")):
                package_path(str((skill.parent / target.split("#", 1)[0]).relative_to(ROOT)))

    mcp = json.loads(package_path(manifest["mcpServers"]).read_text())
    servers = mcp["mcpServers"]
    require(set(servers) == {"awaken"}, "Unexpected MCP server")
    server = servers["awaken"]
    require(server["url"] == "https://mcp.awaken.tax/mcp", "Unexpected Awaken endpoint")
    require(set(server) == {"url", "auth"},
            "OAuth server must not include manual credential headers or a local command")
    auth = server["auth"]
    require(set(auth) == {"CLIENT_ID", "scopes"},
            "Cursor is a public OAuth client; no client secret is needed")
    require(auth["CLIENT_ID"] == "https://cursor.com/oauth/mcp-client.json",
            "Use the Cursor metadata identity recognized by Awaken")
    require(auth["scopes"] == ["read", "write"],
            "Request reviewed scopes so Awaken can offer read or read + write consent")
    require(not manifest.get("variables") and "${" not in json.dumps(mcp),
            "OAuth installation must not require manually supplied credentials")

    print(f"Package checks passed: {manifest['name']} {manifest['version']}, "
          f"{len(skills)} skill, hosted MCP, Cursor public-client OAuth.")
    print("Authenticated Cursor smoke testing is a separate manual check.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, TypeError, ET.ParseError) as error:
        print(f"Package check failed: {error}", file=sys.stderr)
        sys.exit(1)
