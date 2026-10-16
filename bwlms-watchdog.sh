#!/bin/bash
# bwlms-watchdog — relance le LMS Bien-Être s'il n'écoute plus sur 51840
if ! curl -s --max-time 4 http://127.0.0.1:51840/api/health | grep -q '"ok": true'; then
  cd /workspace/cdb-bienetre-lms
  BIENETRE_LMS_PORT=51840 setsid nohup python3 server.py >> /tmp/bwlms-prod.log 2>&1 &
fi
