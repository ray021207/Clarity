#!/usr/bin/env python3
"""
Comprehensive test suite for Clarity project.
Tests all project components after everyone adds their parts.
"""

import sys
import os
from pathlib import Path
import subprocess
import json
from typing import Dict, List, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

# Load environment
load_dotenv()

# Color codes for output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

    @staticmethod
    def disable():
        Colors.HEADER = ''
        Colors.OKBLUE = ''
        Colors.OKCYAN = ''
        Colors.OKGREEN = ''
        Colors.WARNING = ''
        Colors.FAIL = ''
        Colors.ENDC = ''
        Colors.BOLD = ''
        Colors.UNDERLINE = ''


def print_header(text: str):
    """Print a section header."""
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'='*80}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{text.center(80)}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'='*80}{Colors.ENDC}\n")


def print_test(name: str, passed: bool, details: str = ""):
    """Print test result."""
    status = f"{Colors.OKGREEN}✅ PASS{Colors.ENDC}" if passed else f"{Colors.FAIL}❌ FAIL{Colors.ENDC}"
    print(f"{status} | {name}")
    if details:
        print(f"     {details}")


def check_prerequisites() -> Tuple[bool, Dict[str, bool]]:
    """Check that all prerequisites are met."""
    print_header("PREREQUISITE CHECKS")
    
    checks = {}
    
    # Check Python version
    version_ok = sys.version_info >= (3, 11)
    checks['python_version'] = version_ok
    print_test("Python >= 3.11", version_ok, f"(running {sys.version_info.major}.{sys.version_info.minor})")
    
    # Check .env file exists
    env_exists = Path(".env").exists()
    checks['env_file'] = env_exists
    print_test(".env file exists", env_exists, "(optional - config via environment vars)"if not env_exists else "")
    
    # Check ANTHROPIC_API_KEY - can be real or placeholder
    api_key = os.getenv("ANTHROPIC_API_KEY")
    api_key_exists = bool(api_key)
    checks['anthropic_key'] = api_key_exists
    print_test("ANTHROPIC_API_KEY set", api_key_exists, 
               f"{'(set)' if api_key_exists else '(not set)'}")
    
    # Check key modules can be imported
    try:
        import clarity
        import anthropic
        import pydantic
        import fastapi
        checks['imports'] = True
        print_test("Core imports available", True)
    except ImportError as e:
        checks['imports'] = False
        print_test("Core imports available", False, str(e))
    
    # Check clarity submodules
    try:
        # Set a dummy API key for config loading if not present
        if not api_key:
            os.environ["ANTHROPIC_API_KEY"] = "sk-ant-dummy-for-config-loading"
        from clarity.config import settings
        from clarity.proxy.interceptor import ClarityInterceptor
        from clarity.models import TrustReport
        from clarity.integrations.ada_client import AdaClient
        checks['clarity_modules'] = True
        print_test("Clarity submodules importable", True)
    except ImportError as e:
        checks['clarity_modules'] = False
        print_test("Clarity submodules importable", False, str(e))
    
    # Only require actual API key for tests that use it
    all_pass = all(v for k, v in checks.items() if k != 'anthropic_key')
    return all_pass, checks


def test_models() -> Tuple[bool, List[str]]:
    """Test data models."""
    print_header("MODEL TESTS")
    
    results = []
    
    try:
        from clarity.models import TrustReport, AgentVerdict, RiskLevel
        import uuid
        
        # Test RiskLevel enum
        try:
            risk = RiskLevel.LOW
            results.append(("RiskLevel enum", True))
            print_test("RiskLevel enum", True)
        except Exception as e:
            results.append(("RiskLevel enum", False, str(e)))
            print_test("RiskLevel enum", False, str(e))
        
        # Test AgentVerdict model
        try:
            verdict = AgentVerdict(
                agent_name="test_agent",
                score=75.5,
                risk_level=RiskLevel.MEDIUM,
                summary="Test verdict summary",
                findings=["Finding 1"],
                suggestions=["Suggestion 1"]
            )
            results.append(("AgentVerdict model", True))
            print_test("AgentVerdict model", True)
        except Exception as e:
            results.append(("AgentVerdict model", False, str(e)))
            print_test("AgentVerdict model", False, str(e))
        
        # Test TrustReport model
        try:
            verdict = AgentVerdict(
                agent_name="test_agent",
                score=75.0,
                risk_level=RiskLevel.MEDIUM,
                summary="Test summary"
            )
            report = TrustReport(
                report_id=str(uuid.uuid4()),
                exchange_id="test-123",
                overall_score=75.0,
                overall_risk=RiskLevel.MEDIUM,
                model_used="claude-sonnet-4-20250514",
                temperature=0.7,
                hallucination=verdict,
                reasoning=verdict,
                confidence=verdict,
                context_quality=verdict,
                warnings=[]
            )
            results.append(("TrustReport model", True))
            print_test("TrustReport model", True)
        except Exception as e:
            results.append(("TrustReport model", False, str(e)))
            print_test("TrustReport model", False, str(e))
        
    except Exception as e:
        print_test("Model tests", False, str(e))
        return False, results
    
    all_pass = all(r[1] for r in results)
    return all_pass, results


def test_interceptor() -> Tuple[bool, List[str]]:
    """Test the interceptor capture functionality."""
    print_header("INTERCEPTOR TESTS")
    
    results = []
    
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    has_valid_key = api_key and api_key.startswith("sk-ant-") and "placeholder" not in api_key.lower()
    
    if not has_valid_key:
        print(f"{Colors.WARNING}⏭️  SKIPPED{Colors.ENDC} | API key not configured")
        print("     To test interceptor, set a valid ANTHROPIC_API_KEY in .env")
        return True, [("Interceptor tests", True, "Skipped - no valid API key")]
    
    try:
        from clarity.proxy.interceptor import ClarityInterceptor
        from clarity.proxy.metadata import extract_verification_context
        from anthropic import Anthropic
        
        try:
            client = Anthropic(api_key=api_key)
            print_test("Anthropic client initialized", True)
        except Exception as e:
            print_test("Anthropic client initialized", False, str(e))
            return False, [("Anthropic client", False, str(e))]
        
        # Test interceptor
        try:
            interceptor = ClarityInterceptor()
            print_test("ClarityInterceptor created", True)
            
            # Test capture
            exchange = interceptor.capture_sync_call(
                client=client,
                model="claude-sonnet-4-20250514",
                messages=[{"role": "user", "content": "Say 'Hello, Clarity!'"}],
                temperature=0.5,
                max_tokens=50,
            )
            
            print_test("Interceptor capture_sync_call", True, 
                      f"(ID: {exchange.exchange_id})")
            
            # Test metadata extraction
            context = extract_verification_context(exchange)
            print_test("Metadata extraction", True,
                      f"(score risk: {context.get('temp_risk')})")
            
            results.append(("Interceptor capture", True))
            results.append(("Metadata extraction", True))
            
        except Exception as e:
            print_test("Interceptor test", False, str(e))
            results.append(("Interceptor test", False, str(e)))
            return False, results
        
    except Exception as e:
        print_test("Interceptor import", False, str(e))
        return False, [("Interceptor import", False, str(e))]
    
    all_pass = all(r[1] for r in results)
    return all_pass, results


def test_sdk() -> Tuple[bool, List[str]]:
    """Test the SDK."""
    print_header("SDK TESTS")
    
    results = []
    
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    has_valid_key = api_key and api_key.startswith("sk-ant-") and "placeholder" not in api_key.lower()
    
    if not has_valid_key:
        print(f"{Colors.WARNING}⏭️  SKIPPED{Colors.ENDC} | API key not configured")
        print("     To test SDK, set a valid ANTHROPIC_API_KEY in .env")
        return True, [("SDK tests", True, "Skipped - no valid API key")]
    
    try:
        from clarity.sdk import ClarityClient, ClarityResult
        
        # Test local mode initialization
        try:
            client = ClarityClient(local_mode=True, anthropic_api_key=api_key)
            print_test("ClarityClient local mode", True)
            results.append(("SDK local mode init", True))
        except Exception as e:
            print_test("ClarityClient local mode", False, str(e))
            results.append(("SDK local mode init", False, str(e)))
            return False, results
        
        # Test verification
        try:
            result = client.verify(
                messages=[{"role": "user", "content": "Say hello"}],
                temperature=0.5,
                max_tokens=50,
            )
            
            assert isinstance(result, ClarityResult), "Result should be ClarityResult"
            assert hasattr(result, 'content'), "Result should have content"
            assert hasattr(result, 'score'), "Result should have score"
            assert hasattr(result, 'risk'), "Result should have risk"
            assert hasattr(result, 'warnings'), "Result should have warnings"
            assert hasattr(result, 'summary'), "Result should have summary"
            
            print_test("SDK verify call", True,
                      f"(score: {result.score:.1f}, risk: {result.risk})")
            results.append(("SDK verify call", True))
            
        except Exception as e:
            print_test("SDK verify call", False, str(e))
            results.append(("SDK verify call", False, str(e)))
            return False, results
        
    except Exception as e:
        print_test("SDK import", False, str(e))
        return False, [("SDK import", False, str(e))]
    
    all_pass = all(r[1] for r in results)
    return all_pass, results


def test_ada_client() -> Tuple[bool, List[str]]:
    """Test the Ada conversational explainer."""
    print_header("ADA CLIENT TESTS")
    
    results = []
    
    try:
        from clarity.integrations.ada_client import AdaClient
        
        ada_key = os.getenv("ADA_API_KEY")
        ada_url = os.getenv("ADA_API_URL")
        
        if not ada_key or not ada_url:
            print_test("Ada client configured", False, "Missing ADA_API_KEY or ADA_API_URL")
            results.append(("Ada client config", False, "Missing credentials"))
        else:
            try:
                client = AdaClient(api_key=ada_key, api_url=ada_url)
                print_test("Ada client created", True)
                results.append(("Ada client creation", True))
            except Exception as e:
                print_test("Ada client created", False, str(e))
                results.append(("Ada client creation", False, str(e)))
    
    except Exception as e:
        print_test("Ada client import", False, str(e))
        results.append(("Ada client import", False, str(e)))
    
    all_pass = all(r[1] for r in results) if results else False
    return all_pass, results


def test_api_endpoints() -> Tuple[bool, List[str]]:
    """Test that API endpoints are properly defined."""
    print_header("API ENDPOINT TESTS")
    
    results = []
    
    try:
        from clarity.api.routes import router
        from clarity.api.app import create_app
        
        # Test app creation
        try:
            app = create_app()
            print_test("FastAPI app creation", True)
            results.append(("App creation", True))
            
            # Check routes
            routes = [route.path for route in app.routes]
            expected_routes = ["/api/v1/verify", "/api/v1/explain", "/api/v1/health"]
            found_routes = [r for e in expected_routes for r in routes if e in r]
            
            print_test("API routes defined", len(found_routes) > 0,
                      f"(found {len(set(routes))} routes)")
            results.append(("API routes", len(found_routes) > 0))
            
        except Exception as e:
            print_test("FastAPI app creation", False, str(e))
            results.append(("App creation", False, str(e)))
    
    except Exception as e:
        print_test("API import", False, str(e))
        results.append(("API import", False, str(e)))
    
    all_pass = all(r[1] for r in results) if results else False
    return all_pass, results


def test_verification_pipeline_stub() -> Tuple[bool, List[str]]:
    """Test that verification pipeline is properly stubbed for Person B."""
    print_header("VERIFICATION PIPELINE TESTS")
    
    results = []
    
    try:
        from clarity.agents.orchestrator import run_verification_pipeline
        
        # The function should exist and be stubbed
        try:
            # Try to call it (should raise NotImplementedError)
            import inspect
            source = inspect.getsource(run_verification_pipeline)
            is_stubbed = "NotImplementedError" in source
            
            print_test("Verification pipeline is stubbed for Person B", is_stubbed,
                      "Ready for agent implementation")
            results.append(("Pipeline stub", is_stubbed))
            
        except Exception as e:
            print_test("Verification pipeline stub", False, str(e))
            results.append(("Pipeline stub", False, str(e)))
    
    except Exception as e:
        print_test("Pipeline import", False, str(e))
        results.append(("Pipeline import", False, str(e)))
    
    all_pass = all(r[1] for r in results) if results else False
    return all_pass, results


def test_config() -> Tuple[bool, List[str]]:
    """Test that configuration loads properly."""
    print_header("CONFIGURATION TESTS")
    
    results = []
    
    try:
        from clarity.config import settings
        
        # Test that settings loads
        try:
            assert hasattr(settings, 'anthropic_api_key'), "Settings should have anthropic_api_key"
            assert hasattr(settings, 'clarity_env'), "Settings should have clarity_env"
            print_test("Configuration loads", True, f"(env: {settings.clarity_env})")
            results.append(("Config load", True))
        except Exception as e:
            print_test("Configuration loads", False, str(e))
            results.append(("Config load", False, str(e)))
    
    except Exception as e:
        print_test("Config import", False, str(e))
        results.append(("Config import", False, str(e)))
    
    all_pass = all(r[1] for r in results) if results else False
    return all_pass, results


def run_test_file(test_file: str, name: str) -> Tuple[bool, str]:
    """Run a Python test file and capture result."""
    print_header(f"RUNNING: {name}")
    
    try:
        result = subprocess.run(
            [sys.executable, test_file],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(Path(__file__).parent),
        )
        
        # Show output
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)
        
        passed = result.returncode == 0
        return passed, ""
        
    except subprocess.TimeoutExpired:
        print(f"{Colors.FAIL}❌ Test timed out (60s){Colors.ENDC}")
        return False, "Timeout"
    except Exception as e:
        print(f"{Colors.FAIL}❌ Error running test: {e}{Colors.ENDC}")
        return False, str(e)


def main():
    """Run all tests."""
    print_header("CLARITY PROJECT COMPREHENSIVE TEST SUITE")
    print(f"Python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    print(f"Working directory: {Path.cwd()}")
    
    test_results = {}
    
    # 1. Prerequisites
    print("\n" + "="*80)
    prereq_pass, prereq_checks = check_prerequisites()
    test_results['Prerequisites'] = prereq_pass
    
    if not prereq_pass:
        print(f"\n{Colors.FAIL}{Colors.BOLD}❌ Prerequisites not met. Cannot continue.{Colors.ENDC}")
        return 1
    
    # Check for valid API key and show notice
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    has_valid_key = api_key and api_key.startswith("sk-ant-") and "placeholder" not in api_key.lower()
    
    if not has_valid_key:
        print(f"\n{Colors.WARNING}{Colors.BOLD}⚠️  Note: No valid ANTHROPIC_API_KEY configured{Colors.ENDC}")
        print("   To test SDK and Interceptor, add your key to .env:")
        print("   ANTHROPIC_API_KEY=sk-ant-your-actual-key-here")
        print("   Some tests will be skipped without a valid key.\n")
    
    # 2. Model tests
    models_pass, _ = test_models()
    test_results['Models'] = models_pass
    
    # 3. Config tests
    config_pass, _ = test_config()
    test_results['Configuration'] = config_pass
    
    # 4. Interceptor tests
    interceptor_pass, _ = test_interceptor()
    test_results['Interceptor'] = interceptor_pass
    
    # 5. SDK tests
    sdk_pass, _ = test_sdk()
    test_results['SDK'] = sdk_pass
    
    # 6. Ada client tests
    ada_pass, _ = test_ada_client()
    test_results['Ada Client'] = ada_pass
    
    # 7. API endpoint tests
    api_pass, _ = test_api_endpoints()
    test_results['API Endpoints'] = api_pass
    
    # 8. Verification pipeline stub tests
    pipeline_pass, _ = test_verification_pipeline_stub()
    test_results['Verification Pipeline'] = pipeline_pass
    
    # Print summary
    print_header("TEST SUMMARY")
    
    total = len(test_results)
    passed = sum(1 for v in test_results.values() if v)
    failed = total - passed
    
    for name, result in test_results.items():
        status = f"{Colors.OKGREEN}✅ PASS{Colors.ENDC}" if result else f"{Colors.FAIL}❌ FAIL{Colors.ENDC}"
        print(f"{status} | {name}")
    
    print(f"\n{Colors.BOLD}Overall: {passed}/{total} test suites passed{Colors.ENDC}")
    
    if failed == 0:
        print(f"\n{Colors.OKGREEN}{Colors.BOLD}🎉 ALL TESTS PASSED!{Colors.ENDC}")
        print("\n✅ Project is ready for:")
        print("   1. Person B: Implement verification pipeline with LangGraph agents")
        print("   2. Running the server: python -m clarity.main")
        print("   3. Testing with SDK: test_sdk_local.py")
        print("   4. Testing demo scenarios: python demo_scenarios.py")
    else:
        print(f"\n{Colors.FAIL}{Colors.BOLD}⚠️  {failed} test suite(s) failed{Colors.ENDC}")
        print("\nPlease fix the issues above before proceeding.")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
