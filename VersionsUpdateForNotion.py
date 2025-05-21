import os
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from notion_client import Client

NOTION_TOKEN = "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"
NOTION_PAGE_ID = "1f17ad7d1f0780b19d25ee87c66617f4"

notion = Client(auth=NOTION_TOKEN)


def find_csproj_files(root_dir):
    excluded_keywords = ["Install", "ClassLibrary"]
    return [
        path for path in Path(root_dir).rglob("*.csproj")
        if not any(keyword in path.stem for keyword in excluded_keywords)
    ]


def parse_csproj(csproj_path):
    tree = ET.parse(csproj_path)
    root = tree.getroot()

    ns = {'msbuild': 'http://schemas.microsoft.com/developer/msbuild/2003'}
    ET.register_namespace('', 'http://schemas.microsoft.com/developer/msbuild/2003')

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


def append_version_block_to_notion(data):
    version   = data["version"]
    plugin    = data["plugin"]
    packages  = data.get("packages", {})
    timestamp = data.get("timestamp", datetime.utcnow().isoformat())

    publish_date  = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%f").strftime("%d.%m.%Y")
    github_repo = os.getenv("GITHUB_REPOSITORY", "user/repo")
    release_tag = os.getenv("GITHUB_REF_NAME", "latest")
    github_link = f"https://github.com/{github_repo}/releases/tag/{release_tag}"
    download_link = "linkToSeaFile"

    quote_block = {
        "object": "block",
        "type": "quote",
        "quote": {
    "rich_text": [
        {"type": "text", "text": {"content": "Publish Date: "}, "annotations": {"bold": True}},
        {"type": "text", "text": {"content": publish_date}, "annotations": {"code": True, "color": "gray_background"}},
        {"type": "text", "text": {"content": "\n"}},

        {"type": "text", "text": {"content": "Link GitHub: "}, "annotations": {"bold": True}},
        {"type": "text",
         "text": {"content": github_link, "link": {"url": github_link}},
         "annotations": {"code": True, "color": "gray_background"}},
        {"type": "text", "text": {"content": "\n"}},

        {"type": "text", "text": {"content": "Link to Download: "}, "annotations": {"bold": True}},
        {"type": "text",
         "text": {"content": download_link},
         "annotations": {"code": True, "color": "gray_background"}},
    ]
}
    }

    toggle_block = {
        "object": "block",
        "type": "toggle",
        "has_children": True,
        "toggle": {
            "rich_text": [
                {"type": "text", "text": {"content": "Tools/Buttons"}}
            ]
        }
    }

    callout_resp = notion.blocks.children.append(
        block_id=NOTION_PAGE_ID,
        children=[{
            "object": "block",
            "type": "callout",
            "has_children": True,
            "callout": {
                "icon": {"type": "emoji", "emoji": "🔽"},
                "rich_text": [
    {"type": "text",
     "text": {"content": f"{plugin} "},
     "annotations": {"bold": True}},
    {"type": "text",
     "text": {"content": f"v{version}"},
     "annotations": {"code": True, "color": "red_background"}}
],
                "color": "gray_background"
            }
        }]
    )
    callout_id = callout_resp["results"][0]["id"]

    toggle_resp = notion.blocks.children.append(
        block_id=callout_id,
        children=[quote_block, toggle_block]
    )
    toggle_id = toggle_resp["results"][1]["id"]

    bulleted_packages = [
        {
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [
    {"type": "text", "text": {"content": f"{name} "}},
    {"type": "text",
     "text": {"content": f"v{ver}"},
     "annotations": {"code": True, "color": "red_background"}}
]
            }
        }
        for name, ver in packages.items()
    ]
    if bulleted_packages:
        notion.blocks.children.append(
            block_id=toggle_id,
            children=bulleted_packages
        )



def main():
    root_dir = Path(".")
    csproj_files = find_csproj_files(root_dir)

    if not csproj_files:
        print("🚫 No .csproj files found")
        return

    print(f"📁 Found .csproj file: {csproj_files[0]}")

    data = parse_csproj(csproj_files[0])
    append_version_block_to_notion(data)
    print("✅ Data successfully sent to Notion")


if __name__ == "__main__":
    main()
