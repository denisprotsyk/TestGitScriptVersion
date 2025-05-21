import requests

# Авторизация
auth_url = "https://cloud.bim-prove.com.ua/api2/auth-token/"
auth_payload = {
    "username": "it@bim-prove.com",
    "password": "BIMproveDev1"
}
auth_headers = {
    "accept": "application/json",
    "content-type": "application/json"
}

auth_response = requests.post(auth_url, json=auth_payload, headers=auth_headers)
token = auth_response.json()["token"]
print("Token:", token)

upload_link_url = "https://cloud.bim-prove.com.ua/api2/repos/d57a61c0-5532-4910-88a2-99fa457fe7af/upload-link/?p=/"
headers = {
    "accept": "application/json",
    "Authorization": f"Token {token}"
}

upload_link_response = requests.get(upload_link_url, headers=headers)
upload_link = upload_link_response.text.strip('"')
print("Upload link:", upload_link)

file_path = "VersionsUpdateForOutline.py"
files = {
    'file': open(file_path, 'rb')
}
data = {
    'parent_dir': '/',
    'relative_path': '',
    'replace': '1'
}

upload_response = requests.post(
    upload_link + '?ret-json=1',
    data=data,
    files=files
)

print("Upload response:", upload_response.text)