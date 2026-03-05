#!/usr/bin/env python3
"""
Test Runner for Shape Matching Training Module

This script provides a convenient interface for running different types of tests
with various options and configurations.
"""

import argparse
import sys
import subprocess
from pathlib import Path


def run_pytest(test_type='all', verbose=True, coverage=False, parallel=False, markers=None):
    """
    Run pytest with specified options
    
    Args:
        test_type: Type of tests to run ('unit', 'integration', 'all')
        verbose: Enable verbose output
        coverage: Enable coverage reporting
        parallel: Enable parallel test execution
        markers: Additional pytest markers to apply
    """
    
    # Base pytest command
    cmd = ['python', '-m', 'pytest']
    
    # Add test path based on type
    if test_type == 'unit':
        cmd.append('tests/unit/')
    elif test_type == 'integration':
        cmd.append('tests/integration/')
    elif test_type == 'all':
        cmd.append('tests/')
    else:
        raise ValueError(f"Invalid test type: {test_type}")
    
    # Add verbose flag
    if verbose:
        cmd.append('-v')
    
    # Add coverage options
    if coverage:
        cmd.extend(['--cov=.', '--cov-report=html', '--cov-report=term'])
    
    # Add parallel execution
    if parallel:
        cmd.extend(['-n', 'auto'])  # Requires pytest-xdist
    
    # Add custom markers
    if markers:
        cmd.extend(['-m', markers])
    
    # Add other useful options
    cmd.extend([
        '--tb=short',
        '--strict-markers',
        '--color=yes'
    ])
    
    print(f"Running command: {' '.join(cmd)}")
    
    # Run the tests
    try:
        result = subprocess.run(cmd, cwd=Path(__file__).parent)
        return result.returncode == 0
    except KeyboardInterrupt:
        print("\nTests interrupted by user")
        return False
    except Exception as e:
        print(f"Error running tests: {e}")
        return False


def run_quick_tests():
    """Run quick tests (unit tests, excluding slow markers)"""
    return run_pytest(test_type='unit', markers='not slow')


def run_full_tests():
    """Run full test suite including integration and performance tests"""
    return run_pytest(test_type='all', coverage=True, parallel=True)


def run_performance_tests():
    """Run only performance tests"""
    return run_pytest(test_type='all', markers='performance')


def check_dependencies():
    """Check that required testing dependencies are installed"""
    required_packages = [
        'pytest',
        'numpy', 
        'opencv-python',
        'scikit-learn'
    ]
    
    optional_packages = {
        'pytest-cov': 'for coverage reporting',
        'pytest-xdist': 'for parallel test execution',
        'pytest-benchmark': 'for performance benchmarking'
    }
    
    missing_required = []
    missing_optional = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_required.append(package)
    
    for package, description in optional_packages.items():
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_optional.append((package, description))
    
    if missing_required:
        print("❌ Missing required packages:")
        for package in missing_required:
            print(f"  - {package}")
        return False
    
    print("✅ All required packages are available")
    
    if missing_optional:
        print("\n💡 Optional packages that could enhance testing:")
        for package, description in missing_optional:
            print(f"  - {package}: {description}")
    
    return True


def main():
    """Main test runner interface"""
    parser = argparse.ArgumentParser(
        description="Test Runner for Shape Matching Training Module",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Run quick unit tests
  %(prog)s --full             # Run all tests with coverage
  %(prog)s --integration      # Run only integration tests
  %(prog)s --performance      # Run only performance tests
  %(prog)s --markers "slow"   # Run only slow tests
  %(prog)s --check-deps       # Check dependencies
        """
    )
    
    # Test type options
    test_group = parser.add_mutually_exclusive_group()
    test_group.add_argument('--unit', action='store_true',
                           help='Run unit tests only')
    test_group.add_argument('--integration', action='store_true',
                           help='Run integration tests only')
    test_group.add_argument('--performance', action='store_true',
                           help='Run performance tests only')
    test_group.add_argument('--full', action='store_true',
                           help='Run full test suite')
    
    # Additional options
    parser.add_argument('--coverage', action='store_true',
                       help='Enable coverage reporting')
    parser.add_argument('--parallel', action='store_true',
                       help='Run tests in parallel')
    parser.add_argument('--markers', type=str,
                       help='Pytest markers to apply (e.g., "not slow")')
    parser.add_argument('--verbose', action='store_true', default=True,
                       help='Enable verbose output')
    parser.add_argument('--check-deps', action='store_true',
                       help='Check test dependencies')
    
    args = parser.parse_args()
    
    # Check dependencies if requested
    if args.check_deps:
        return 0 if check_dependencies() else 1
    
    # Check dependencies before running tests
    if not check_dependencies():
        print("\nPlease install missing required packages before running tests.")
        print("Example: pip install pytest numpy opencv-python scikit-learn")
        return 1
    
    # Determine a test type
    if args.unit:
        test_type = 'unit'
    elif args.integration:
        test_type = 'integration'
    elif args.performance:
        success = run_performance_tests()
        return 0 if success else 1
    elif args.full:
        success = run_full_tests()
        return 0 if success else 1
    else:
        # Default: run quick tests
        success = run_quick_tests()
        return 0 if success else 1
    
    # Run specified tests
    success = run_pytest(
        test_type=test_type,
        verbose=args.verbose,
        coverage=args.coverage,
        parallel=args.parallel,
        markers=args.markers
    )
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())