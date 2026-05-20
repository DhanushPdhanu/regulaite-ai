"""
healthcheck.py — RegulAIte Pre-Flight Validator

Run before launching the server to confirm all 4 modules are importable
and the environment is configured correctly.

Usage:
    cd regulaite
    python healthcheck.py
"""

import os
import sys
import importlib

# ── Colour helpers (no external deps) ────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg):    print(f"  {GREEN}[PASS]{RESET} {msg}")
def fail(msg):  print(f"  {RED}[FAIL]{RESET} {msg}")
def warn(msg):  print(f"  {YELLOW}[WARN]{RESET} {msg}")
def section(s): print(f"\n{BOLD}{s}{RESET}")


def check_env_vars() -> int:
    section("1. Environment Variables")
    errors = 0
    required = {
        "ANTHROPIC_API_KEY": "Required for LLM agents — set to 'stub' for demo mode",
        "CREWAI_MODEL":      "Optional — defaults to claude-sonnet-4-20250514",
    }
    for var, note in required.items():
        val = os.getenv(var, "")
        if not val:
            warn(f"{var} not set. {note}")
        elif var == "ANTHROPIC_API_KEY" and val == "your_anthropic_api_key_here":
            warn(f"{var} is still the placeholder value. Stub mode will be used.")
        else:
            ok(f"{var} = {'*' * min(len(val), 8)}...")
    return errors


def check_python_version() -> int:
    section("2. Python Version")
    major, minor = sys.version_info[:2]
    if major == 3 and minor >= 10:
        ok(f"Python {major}.{minor} — compatible (3.10+ required)")
        return 0
    else:
        fail(f"Python {major}.{minor} — need 3.10 or higher")
        return 1


def check_packages() -> int:
    section("3. Required Packages")
    errors = 0
    packages = [
        ("fastapi",             "Shashank — server"),
        ("uvicorn",             "Shashank — server runner"),
        ("streamlit",           "Dhanush — frontend"),
        ("pydantic",            "Ullas — schemas"),
        ("crewai",              "Punith — agents"),
        ("langchain_anthropic", "Punith — LLM connector"),
        ("anthropic",           "Punith — API client"),
        ("dotenv",              "All — env loading"),
        ("PyPDF2",              "Ullas — PDF parsing"),
        ("z3",                  "Ullas — contradiction solver"),
    ]
    for pkg, owner in packages:
        try:
            importlib.import_module(pkg.replace("-", "_"))
            ok(f"{pkg:25s} ({owner})")
        except ImportError:
            # Non-blocking for optional packages
            if pkg in ("z3",):
                warn(f"{pkg:25s} ({owner}) — not installed, Z3 boosts disabled")
            else:
                fail(f"{pkg:25s} ({owner}) — run: pip install {pkg}")
                errors += 1
    return errors


def check_ullas_modules() -> int:
    section("4. Ullas (Hacker 4) — schemas, validator, bridge")
    errors = 0
    try:
        from schemas import Clause, ComplianceViolation
        # Quick smoke: instantiate a Clause
        c = Clause(
            clause_id="hc_1", page_number=1, clause_number="1.1",
            text="Test clause.", section="Test",
        )
        ok(f"schemas.py — Clause and ComplianceViolation importable")
    except ImportError as e:
        fail(f"schemas.py — {e}")
        errors += 1
    except Exception as e:
        fail(f"schemas.py Clause instantiation — {e}")
        errors += 1

    try:
        from logic.validator import validate_clauses
        ok("logic/validator.py — validate_clauses importable")
    except ImportError:
        warn("logic/validator.py — not ready yet (pre-scoring will run without Z3)")
    except Exception as e:
        warn(f"logic/validator.py — {e}")

    try:
        from memory.bridge import run_full_analysis
        ok("memory/bridge.py — run_full_analysis importable")
    except ImportError:
        warn("memory/bridge.py — not ready yet (Z3 boosts will be skipped safely)")
    except Exception as e:
        warn(f"memory/bridge.py — {e}")

    return errors


def check_punith_module() -> int:
    section("5. Punith (Hacker 3) — agents/crew.py")
    errors = 0
    try:
        from agents.crew import analyse
        import inspect
        sig = inspect.signature(analyse)
        params = list(sig.parameters.keys())
        assert params == ["clauses"], \
            f"analyse() signature wrong — expected ['clauses'], got {params}"
        ok("agents/crew.py — analyse() importable with correct signature")
    except ImportError as e:
        fail(f"agents/crew.py — {e}")
        errors += 1
    except AssertionError as e:
        fail(f"agents/crew.py — {e}")
        errors += 1
    except Exception as e:
        fail(f"agents/crew.py — {e}")
        errors += 1

    # Test stub mode (no API key needed)
    try:
        from agents.crew import _stub_result
        from schemas import Clause
        stub = _stub_result([
            Clause(clause_id="hc_stub", page_number=1,
                   clause_number="1.1", text="Test.", section="Test")
        ])
        assert "compliance_violations" in stub
        assert "fixed_clauses" in stub
        ok("agents/crew.py — _stub_result() returns correct schema")
    except Exception as e:
        fail(f"agents/crew.py _stub_result — {e}")
        errors += 1

    return errors


def check_shashank_module() -> int:
    section("6. Shashank (Hacker 2) — server.py")
    errors = 0
    try:
        import ast
        with open("server.py", encoding="utf-8", errors="replace") as f:
            source = f.read()
        ast.parse(source)
        # Check the import of Punith's analyse function exists in server.py
        if "from agents.crew import analyse" in source:
            ok("server.py — imports analyse() from agents.crew correctly")
        else:
            warn("server.py — 'from agents.crew import analyse' not found — check integration")
        ok("server.py — syntax valid")
    except FileNotFoundError:
        warn("server.py — not found yet (Shashank may still be implementing)")
    except SyntaxError as e:
        fail(f"server.py — syntax error: {e}")
        errors += 1
    return errors


def check_dhanush_module() -> int:
    section("7. Dhanush (Hacker 1) — app.py")
    errors = 0
    try:
        import ast
        with open("app.py", encoding="utf-8", errors="replace") as f:
            source = f.read()
        ast.parse(source)
        ok("app.py — syntax valid")
    except FileNotFoundError:
        warn("app.py — not found yet (Dhanush may still be implementing)")
    except SyntaxError as e:
        fail(f"app.py — syntax error: {e}")
        errors += 1
    return errors


def check_demo_contracts() -> int:
    section("8. Demo Contracts (contracts/ folder)")
    import glob
    pdfs = glob.glob("contracts/*.pdf")
    if len(pdfs) >= 1:
        ok(f"contracts/ — {len(pdfs)} PDF(s) found")
    else:
        warn("contracts/ — no PDFs found. Add at least one to contracts/")
    return 0


def main():
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  RegulAIte — Pre-Flight Health Check{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")

    total_errors = 0
    total_errors += check_python_version()
    total_errors += check_env_vars()
    total_errors += check_packages()
    total_errors += check_ullas_modules()
    total_errors += check_punith_module()
    total_errors += check_shashank_module()
    total_errors += check_dhanush_module()
    total_errors += check_demo_contracts()

    print(f"\n{BOLD}{'='*60}{RESET}")
    if total_errors == 0:
        print(f"{GREEN}{BOLD}  ALL CHECKS PASSED — safe to launch{RESET}")
        print(f"  Run:  bash run_local.sh\n")
    else:
        print(f"{RED}{BOLD}  {total_errors} BLOCKER(S) FOUND — fix before launching{RESET}")
        print(f"  Resolve the [FAIL] items above, then re-run healthcheck.py\n")
    print(f"{BOLD}{'='*60}{RESET}\n")

    sys.exit(total_errors)


if __name__ == "__main__":
    # Must run from regulaite/ directory
    if not os.path.exists("agents/crew.py"):
        print(f"{RED}ERROR: Run this script from the regulaite/ directory.{RESET}")
        print(f"  cd regulaite && python healthcheck.py")
        sys.exit(1)

    # Load .env
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    main()
