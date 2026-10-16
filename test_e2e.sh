#!/bin/bash
# test_e2e.sh — LMS Bien-Être v2 · parcours complet (pattern CDB : curl login-first)
# Usage : BASE=http://localhost:51840 bash test_e2e.sh   → tout doit être vert.
set -u
BASE="${BASE:-http://localhost:51840}"
JAR="/tmp/bwlms_e2e_admin_$$.txt"
JAR_S="/tmp/bwlms_e2e_student_$$.txt"
RUN_ID="$(date +%s)"
PASS=0; FAIL=0

check() {
  local raw="$1"; local want="$2"; local label="$3"
  if echo "$raw" | grep -q "$want"; then PASS=$((PASS+1)); echo "  ✓ $label"
  else FAIL=$((FAIL+1)); echo "  ✗ $label — reçu: $(echo $raw | head -c 160)"; fi
}

echo "== 1. Santé =="
R=$(curl -s $BASE/api/health)
check "$R" '"bienetre-lms"' "health OK (bienetre-lms)"

echo "== 2. Vitrine publique =="
R=$(curl -s -o /dev/null -w '%{http_code}' $BASE/)
check "$R" "200" "landing 200"
R=$(curl -s $BASE/api/public/courses)
check "$R" 'kit-demarrage' "3 formations cataloguées (kit-demarrage)"
R=$(curl -s -o /dev/null -w '%{http_code}' $BASE/formation/kit-demarrage)
check "$R" "200" "page formation publique 200"

echo "== 3. Lead vitrine =="
R=$(curl -s -X POST $BASE/api/public/lead -H 'Content-Type: application/json' \
  -d "{\"name\":\"Visiteur E2E\",\"email\":\"e2e-lead-$RUN_ID@cdb-hub.app\",\"goal\":\"remplir mon agenda\",\"school\":\"bienetre\"}")
check "$R" '"ok"' "lead vitrine capté"

echo "== 4. Auth =="
R=$(curl -s -c $JAR --max-time 5 -X POST $BASE/api/auth/login -H 'Content-Type: application/json' -d '{"email":"charles@cdb-hub.app","password":"Rosemary2026!"}')
check "$R" '"superadmin"' "login superadmin"
R=$(curl -s -c $JAR_S -X POST $BASE/api/auth/login -H 'Content-Type: application/json' -d '{"email":"demo@cdb-hub.app","password":"Demo2026!BienLms"}')
check "$R" '"student"' "login élève démo"
R=$(curl -s -b $JAR_S $BASE/api/me)
check "$R" 'CDB Bien-Être' "élève rattache l'école bienetre"

echo "== 5. Admin =="
R=$(curl -s -b $JAR $BASE/api/admin/overview)
check "$R" '"published"' "overview admin (courses/published)"
R=$(curl -s -b $JAR $BASE/api/admin/courses)
check "$R" 'systeme-complet' "liste 3 formations (systeme-complet)"
R=$(curl -s -b $JAR $BASE/api/admin/packs)
check "$R" 'accompagnement-complet' "pack complet présent"
R=$(curl -s -b $JAR $BASE/api/admin/students)
check "$R" 'demo@cdb-hub.app' "élèves listés"
R=$(curl -s -b $JAR -X PATCH $BASE/api/admin/students -H 'Content-Type: application/json' -d "{\"user_id\":$(curl -s -b $JAR $BASE/api/admin/students | python3 -c 'import json,sys; print(json.dumps(json.load(sys.stdin)[0]["id"]))' 2>/dev/null),\"tags\":\"e2e,atelier-janvier\"}")
check "$R" '"ok"' "tags élève enregistrés"

echo "== 6. Code F1 (élève rachète) =="
DEMO_ID=$(curl -s -b $JAR_S $BASE/api/me | python3 -c 'import json,sys; print(json.load(sys.stdin)["user"]["id"])')
R=$(curl -s -b $JAR_S -X POST $BASE/api/redeem -H 'Content-Type: application/json' -d '{"code":"BLW-BIEN-2026"}')
check "$R" '"ok": true' "code F1 racheté (ou déjà activé)"

echo "== 7. Code pack (débloque les 3) =="
R=$(curl -s -b $JAR_S -X POST $BASE/api/redeem -H 'Content-Type: application/json' -d '{"code":"BLW-PACK-FULL"}')
check "$(echo $R; curl -s -b $JAR_S $BASE/api/my/courses)" 'systeme-complet' "F3 accessible via code pack"

echo "== 8. Parcours leçon =="
C1=$(curl -s -b $JAR_S $BASE/api/my/courses | python3 -c "import json,sys; print([c['course_id'] for c in json.load(sys.stdin) if c['slug']=='kit-demarrage'][0])")
LID=$(curl -s -b $JAR_S $BASE/api/my/course/$C1 | python3 -c "import json,sys; print(json.load(sys.stdin)['outline'][0]['lessons'][0]['id'])")
R=$(curl -s -b $JAR_S -X POST $BASE/api/lesson/time -H 'Content-Type: application/json' -d "{\"lesson_id\":\"$LID\",\"seconds\":15}")
check "$R" '"ok"' "tick temps actif accepté"
R=$(curl -s -b $JAR_S $BASE/api/lesson/$LID)
check "$R" 'seconds_spent' "leçon renvoie seconds_spent (temps actif tracé)"
R=$(curl -s -b $JAR_S -X POST $BASE/api/progress -H 'Content-Type: application/json' -d "{\"lesson_id\":\"$LID\"}")
check "$R" '"ok"' "leçon marquée terminée"

echo "== 9. Coach ↔ élève =="
R=$(curl -s -b $JAR_S -X POST $BASE/api/lesson/$LID/comments -H 'Content-Type: application/json' -d '{"body":"E2E question élève"}')
check "$R" '"ok"' "commentaire élève créé"
R=$(curl -s -b $JAR -X POST $BASE/api/lesson/$LID/comments -H 'Content-Type: application/json' -d "{\"student\":\"$DEMO_ID\",\"body\":\"E2E réponse coach\"}")
check "$R" '"ok"' "réponse coach dans le fil élève"
R=$(curl -s -b $JAR_S $BASE/api/lesson/$LID/comments)
check "$R" '"coach"' "fil lisible par l'élève (rôle coach visible)"

echo "== 10. Quiz =="
QZ=$(curl -s -b $JAR_S $BASE/api/my/course/$C1 | python3 -c "
import json, sys
d = json.load(sys.stdin)
qid=None
for m in d['outline']:
    for l in m['lessons']:
        if l['has_quiz']: qid=l['id']
print(qid)")
QID=$(curl -s -b $JAR_S $BASE/api/lesson/$QZ | python3 -c 'import json, sys; print(json.load(sys.stdin)["quiz_id"])')
QQ=$(curl -s -b $JAR_S $BASE/api/my/quiz/$QID | python3 -c 'import json, sys; d=json.load(sys.stdin); print(",".join(x["id"] for x in d["questions"]))')
BODY=$(python3 -c "import sys; qs='$QQ'.split(','); print(json.dumps({'answers': {q:0 for q in qs}}))")
R=$(curl -s -b $JAR_S -X POST $BASE/api/quiz/$QID/attempt -H 'Content-Type: application/json' -d "$BODY")
check "$R" '"pct"' "tentative quiz renvoie score/pct"

echo "== 11. Assiduité (≥80 %) =="
R=$(curl -s -b $JAR -X POST $BASE/api/admin/attendance/$DEMO_ID -H 'Content-Type: application/json' -d "{\"course_id\":\"$C1\"}")
if echo "$R" | grep -q '"serial"' || echo "$R" | grep -q '"already"'; then PASS=$((PASS+1)); echo "  ✓ attestation assiduité (ou déjà délivrée)"
else FAIL=$((FAIL+1)); echo "  ✗ attestation assiduité — reçu: $(echo $R | head -c 200)"; fi

echo "== 12. Feedback à chaud =="
F2=$(curl -s -b $JAR_S $BASE/api/my/courses | python3 -c "import json,sys; print([c['course_id'] for c in json.load(sys.stdin) if c['slug']=='remplir-son-agenda'][0])")
R=$(curl -s -b $JAR -X POST $BASE/api/admin/attendance/$DEMO_ID -H 'Content-Type: application/json' -d "{\"course_id\":\"$F2\"}" > /dev/null; \
    curl -s -b $JAR_S -X POST $BASE/api/feedback -H 'Content-Type: application/json' -d "{\"course_id\":\"$F2\",\"rating\":5,\"comment\":\"E2E avis rempli\"}")
check "$R" '"ok"' "feedback à chaud (si F2 complété par attestation route)"
R=$(curl -s -b $JAR $BASE/api/admin/feedback)
check "$R" 'E2E avis rempli\|Aucun avis\|\[\]' "liste feedback admin"

echo "== 13. Annonces & certificats =="
R=$(curl -s -b $JAR_S $BASE/api/my/announcements)
check "$R" 'Bienvenue' "annonce de bienvenue visible élève"
R=$(curl -s -b $JAR $BASE/api/admin/leads)
check "$R" "e2e-lead-$RUN_ID" "lead E2E dans l'admin"

echo ""
echo "=========================================="
echo "  PASS: $PASS   FAIL: $FAIL"
echo "=========================================="
[ $FAIL -eq 0 ] && echo "  ✅ E2E COMPLET — tout vert" || echo "  ❌ des tests ont échoué"
exit $FAIL