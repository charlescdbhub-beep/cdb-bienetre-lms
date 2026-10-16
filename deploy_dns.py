#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
deploy_dns.py — crée le CNAME lms.cdb-hub.app → tunnel (API Cloudflare).
Idempotent : si l'enregistrement existe déjà, il est signalé.
"""
import json
import urllib.request

TOKEN = open("/workspace/.secrets/cloudflare_token.txt").read().strip()
ZONE_ID = "4a2a06bd49fc58be78929b0e2c22d103"
TUNNEL_ID = "06a0e7c2-0dc7-4f13-aaa6-6b8b33d0bc8c"
NAME = "lms.cdb-hub.app"

def cf(method, path, body=None):
    req = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4{path}",
        data=json.dumps(body).encode() if body else None,
        headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"},
        method=method)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

# existe-t-il déjà ?
lst = cf("GET", f"/zones/{ZONE_ID}/dns_records?name={NAME}")
result = lst.get("result", [])
if result:
    rec = result[0]
    target = rec.get("content", "")
    expected = f"{TUNNEL_ID}.cfargotunnel.com"
    if target == expected and rec.get("proxied"):
        print("CNAME déjà présent et correct :", rec["id"])
    else:
        up = cf("PUT", f"/zones/{ZONE_ID}/dns_records/{rec['id']}",
                {"type": "CNAME", "name": NAME, "content": expected, "proxied": True, "ttl": 1})
        print("CNAME corrigé:", up.get("success"), up.get("errors"))
else:
    rec = cf("POST", f"/zones/{ZONE_ID}/dns_records",
             {"type": "CNAME", "name": NAME, "content": f"{TUNNEL_ID}.cfargotunnel.com",
              "proxied": True, "ttl": 1})
    print("CNAME créé:", rec.get("success"), "| id:", (rec.get("result") or {}).get("id"), "| errors:", rec.get("errors"))