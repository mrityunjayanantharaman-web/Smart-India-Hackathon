import requests


BASE = "http://127.0.0.1:8000"
TEST_H3 = "8842d9d2e7fffff"

errors = []

print("=" * 60)
print("AGNINETRA END-TO-END DEMO TEST")
print("=" * 60)


def check(name, condition, details=""):
    if condition:
        print(f"  [OK] {name}")
    else:
        print(f"  [FAIL] {name}")
        if details:
            print(f"    {details}")
        errors.append(name)


print("\n[1] BACKEND")
try:
    response = requests.get(f"{BASE}/health", timeout=10)
    check("Health endpoint", response.status_code == 200, f"HTTP {response.status_code}")
except Exception as error:
    check("Health endpoint", False, str(error))


print("\n[2] NATIONAL INTELLIGENCE")
try:
    response = requests.get(f"{BASE}/risk-sites", timeout=20)
    check("Risk-sites endpoint", response.status_code == 200, f"HTTP {response.status_code}")
    data = response.json()
    sites = data.get("risk_sites", [])
    check("Persistent sites available", len(sites) > 0, f"Found {len(sites)}")

    required_fields = [
        "h3_cell",
        "latitude",
        "longitude",
        "risk_score",
        "priority",
        "ml_classification",
        "ml_confidence",
    ]
    if sites:
        for field in required_fields:
            check(f"Risk-site field: {field}", field in sites[0])
except Exception as error:
    check("Risk-sites endpoint", False, str(error))


print("\n[3] INVESTIGATION DOSSIER")
try:
    response = requests.get(
        f"{BASE}/dossier-data",
        params={"h3": TEST_H3},
        timeout=20,
    )
    check("Dossier endpoint", response.status_code == 200, f"HTTP {response.status_code}")
    dossier = response.json()
    check("Dossier site exists", dossier.get("h3_cell") == TEST_H3)
    check("AI classification exists", bool(dossier.get("ml_classification")))
    check("AI explanation exists", bool(dossier.get("ai_explanation")))
    explanation = dossier.get("ai_explanation", {})
    check("SHAP features available", len(explanation.get("features", [])) > 0)
except Exception as error:
    check("Dossier endpoint", False, str(error))


print("\n[4] INVESTIGATION REPORT")
try:
    response = requests.get(f"{BASE}/report/{TEST_H3}", timeout=20)
    check("PDF report endpoint", response.status_code == 200, f"HTTP {response.status_code}")
    check("PDF content type", "application/pdf" in response.headers.get("content-type", ""))
    check("Valid PDF signature", response.content[:4] == b"%PDF")
    check("PDF has content", len(response.content) > 1000, f"{len(response.content)} bytes")
except Exception as error:
    check("PDF endpoint", False, str(error))


print("\n" + "=" * 60)
print("DEMO TEST SUMMARY")
print("=" * 60)

if errors:
    print("\n[FAIL] SYSTEM TEST FAILED")
    for error in errors:
        print("  -", error)
else:
    print("\n[OK] ALL SYSTEMS PASS")
    print("""
Complete workflow verified:

    Satellite data
          |
    Persistent sites
          |
    ML classification
          |
    Risk prioritization
          |
    SHAP explanation
          |
    Investigation dossier
          |
    PDF investigation report
""")

print("=" * 60)
