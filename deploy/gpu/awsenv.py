"""Read the client's key out of the CSV and put it in the environment.

Imported by every script below so the secret is never typed, never echoed and
never lands in a shell history.
"""
import csv, os

def load(path="/home/abad-naseer/Downloads/ollm_admin_accessKeys.csv"):
    with open(path, encoding="utf-8-sig") as f:
        row = next(csv.DictReader(f))
    key = row["Access key ID"].strip()
    secret = row["Secret access key"].strip()
    os.environ["AWS_ACCESS_KEY_ID"] = key
    os.environ["AWS_SECRET_ACCESS_KEY"] = secret
    return key
