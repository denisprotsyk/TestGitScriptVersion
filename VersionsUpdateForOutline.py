import os
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
import http.client

import requests

# Outline
OUTLINE_TOKEN = "ol_api_JSh21UxJ5vsvrb9oC2UaIaJS095qzQDHhZyR09"
OUTLINE_PAGE_ID = "RpUtdxc1IA"
OUTLINE_HOST = "outline.bim-prove.com.ua"

# GitHub
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_REPOSITORY = os.getenv("GITHUB_REPOSITORY", "user/repo")
GITHUB_REF_NAME = os.getenv("GITHUB_REF_NAME", "latest")

# Seafile
SEAFILE_USERNAME = "it@bim-prove.com"
SEAFILE_PASSWORD = "BIMproveDev1"
SEAFILE_REPO_ID = "d57a61c0-5532-4910-88a2-99fa457fe7af"
SEAFILE_HOST = "https://cloud.bim-prove.com.ua"


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

def download_github_release_asset():
    api_url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/tags/{GITHUB_REF_NAME}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(api_url, headers=headers)
    release = response.json()

    for asset in release.get("assets", []):
        if asset["name"].endswith(".msi"):
            api_asset_url = asset["url"]  # 👈 это API URL, а не browser_download_url
            local_path = asset["name"]

            r = requests.get(api_asset_url, headers={
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/octet-stream"
            })

            print(f"⬇ Downloaded {asset['name']} — {len(r.content)} bytes")

            with open(local_path, "wb") as f:
                f.write(r.content)

            print(f"✅ Saved MSI file: {local_path}, size: {os.path.getsize(local_path)} bytes")

            return local_path

    raise FileNotFoundError("MSI asset not found in release.")

def upload_to_seafile(file_path):
    auth_url = f"{SEAFILE_HOST}/api2/auth-token/"
    auth_payload = {"username": SEAFILE_USERNAME, "password": SEAFILE_PASSWORD}
    auth_headers = {"accept": "application/json", "content-type": "application/json"}

    auth_response = requests.post(auth_url, json=auth_payload, headers=auth_headers)
    token = auth_response.json()["token"]

    upload_link_url = f"{SEAFILE_HOST}/api2/repos/{SEAFILE_REPO_ID}/upload-link/?p=/"
    headers = {"Authorization": f"Token {token}", "accept": "application/json"}
    upload_link = requests.get(upload_link_url, headers=headers).text.strip('"')

    with open(file_path, "rb") as file_obj:
        files = {'file': file_obj}
        data = {'parent_dir': '/', 'replace': '1'}
        upload_response = requests.post(f"{upload_link}?ret-json=1", data=data, files=files)
        upload_result = upload_response.json()
        print("📦 Seafile upload response:", upload_result)

        if isinstance(upload_result, list) and upload_result:
            file_id = upload_result[0].get("id")
            file_name = upload_result[0].get("name")
            return f"{SEAFILE_HOST}/seafhttp/files/{file_id}/{file_name}"
        else:
            raise ValueError("❌ Unexpected response from Seafile")

def append_version_block_to_outline(data, download_link):
    version = data["version"]
    plugin = data["plugin"]
    packages = data.get("packages", {})
    timestamp = data.get("timestamp", datetime.utcnow().isoformat())

    publish_date = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%f").strftime("%d.%m.%Y")
    github_link = f"https://github.com/{GITHUB_REPOSITORY}/releases/tag/{GITHUB_REF_NAME}"

    quote_block = "\n".join([
        f"> **Published date:** {publish_date}",
        f"> **Link GitHub:** {github_link}",
        f"> **Download:** `{download_link}`",
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
    print(conn.getresponse().read().decode("utf-8"))

def main():
    csproj_files = find_csproj_files(".")
    if not csproj_files:
        print("🚫 No .csproj files found")
        return

    print(f"📁 Found .csproj file: {csproj_files[0]}")
    data = parse_csproj(csproj_files[0])

    print("⬇ Downloading MSI from GitHub...")
    msi_file = download_github_release_asset()

    print("⬆ Uploading to Seafile...")
    download_link = upload_to_seafile(msi_file)

    print("📝 Sending block to Outline...")
    append_version_block_to_outline(data, download_link)

    print("✅ Done")

if __name__ == "__main__":
    main()
