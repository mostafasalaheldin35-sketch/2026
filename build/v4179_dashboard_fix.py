from pathlib import Path

p = Path("buildsrc/app/v4179_patch.js")
s = p.read_text(encoding="utf-8")
start = "const prevDashCard=window.dashboardSymmetricItemCard;"
end = "const oldRenderDash=window.renderDashboardItems;"
a = s.find(start)
b = s.find(end)
if a < 0 or b < 0 or b <= a:
    raise SystemExit("v4179 dashboard card block not found")
safe = """const prevDashCard=window.dashboardSymmetricItemCard;window.dashboardSymmetricItemCard=function(i,seq=1){const chosen=selectedDashboardStates(),subs=Array.isArray(i.subItems)?i.subItems:[];if(!subs.length||!chosen.size)return prevDashCard(i,seq);const matching=subs.filter(s=>itemMatch79(s,chosen));return prevDashCard({...i,subItems:matching},seq)};
"""
s = s[:a] + safe + s[b:]
p.write_text(s, encoding="utf-8")
print("v4.8.17.9 dashboard sub-item filter safety fix applied")
