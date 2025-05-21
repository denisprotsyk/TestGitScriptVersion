import os
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
import http.client

OUTLINE_TOKEN = os.environ["OUTLINE_TOKEN"]
OUTLINE_PAGE_ID = os.environ["OUTLINE_PAGE_ID"]
OUTLINE_HOST = os.environ["OUTLINE_HOST"]


def find_csproj_files(root_dir):
    excluded_keywords = ["Install", "ClassLibrary"]
    return [
        path for path in Path(root_dir).rglob("*.csproj")
        if not any(keyword in path.stem for keyword in excluded_keywords)
    ]


def parse_csproj(csproj_path):
    tree = ET.parse(csproj_path)
    root = tree.getroot()

    def find_first(tag):
        for elem in root.iter():
            if elem.tag.endswith(tag):
                return elem.text
        return None

    plugin_name = csproj_path.stem
    version = find_first("AssemblyVersion") or "0.0.0"

    packages = {}
    for elem in root.iter():
        if elem.tag.endswith("PackageReference"):
            name = elem.attrib.get("Include")
            ver = elem.attrib.get("Version")
            if name and ver:
                packages[name] = ver

    return {
        "plugin": plugin_name,
        "version": version,
        "timestamp": datetime.utcnow().isoformat(),
        "packages": packages
    }


def append_version_block_to_outline(data):
    version = data["version"]
    plugin = data["plugin"]
    packages = data.get("packages", {})
    timestamp = data.get("timestamp", datetime.utcnow().isoformat())

    publish_date = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%f").strftime("%d.%m.%Y")
    github_repo = os.getenv("GITHUB_REPOSITORY", "user/repo")
    release_tag = os.getenv("GITHUB_REF_NAME", "latest")
    github_link = f"https://github.com/{github_repo}/releases/tag/{release_tag}"
    download_link = "linkToSeaFile"

    quote_block = "\n".join([
        f"> **Published date:** {publish_date}\n",
        f"> **Link GitHub:** {github_link}\n",
        f"> **Download:** `{download_link}`\n",
    ])

    package_lines = "\n".join([
        f"- {name} `v{ver}`"
        for name, ver in packages.items()
    ]) or "_No packages listed._"

    new_block = f""":::tip
**{plugin}** `v{version}`
{quote_block}
{package_lines}
:::
"""

    conn = http.client.HTTPSConnection(OUTLINE_HOST)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OUTLINE_TOKEN}"
    }

    conn.request("POST", "/api/documents.info", json.dumps({"id": OUTLINE_PAGE_ID}), headers)
    response = conn.getresponse()
    result = json.loads(response.read().decode("utf-8"))

    current_text = result.get("data", {}).get("text", "")

    updated_text = new_block.strip() + "\n\n" + current_text.strip()

    payload = json.dumps({
        "id": OUTLINE_PAGE_ID,
        "title": plugin,
        "text": updated_text,
        "append": False,
        "publish": True,
        "done": True
    })

    conn.request("POST", "/api/documents.update", payload, headers)
    response = conn.getresponse()
    print(response.read().decode("utf-8"))



def main():
    root_dir = Path(".")
    csproj_files = find_csproj_files(root_dir)

    if not csproj_files:
        print("🚫 No .csproj files found")
        return

    print(f"📁 Found .csproj file: {csproj_files[0]}")
    data = parse_csproj(csproj_files[0])
    append_version_block_to_outline(data)
    print("✅ Data successfully sent to Outline")


if __name__ == "__main__":
    main()
