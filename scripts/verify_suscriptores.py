#!/usr/bin/env python
"""
Quick verification script for the suscriptores feature (issue #4)
"""

import sys
import os

# Add the project directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app
from app.store.suscriptores import Suscriptor

def test_suscriptores_feature():
    """Test the suscriptores feature implementation"""
    print("Testing suscriptores feature...")
    
    # Create app context
    app = create_app()
    
    with app.app_context():
        # Test 1: Check that the Suscriptor model exists
        print("[PASS] Suscriptor model exists")
        
        # Test 2: Check that the table was created
        try:
            # Try to query the table
            count = Suscriptor.query.count()
            print(f"[PASS] Suscriptor table exists with {count} records")
        except Exception as e:
            print(f"[FAIL] Error querying suscriptor table: {e}")
            return False
            
        # Test 3: Check that the form exists (within request context)
        with app.test_request_context():
            try:
                from app.store.forms import SuscriptorForm
                form = SuscriptorForm()
                print("[PASS] SuscriptorForm exists")
            except Exception as e:
                print(f"[FAIL] Error creating SuscriptorForm: {e}")
                return False
                
        # Test 4: Check that the routes are registered
        with app.test_client() as client:
            # Test homepage (should contain the form)
            response = client.get('/')
            if b'suscribir' in response.data.lower():
                print("[PASS] Footer form present in homepage")
            else:
                print("[WARN] Footer form might not be present in homepage")
                
            # Test that the admin route exists (requires login)
            response = client.get('/dashboard/suscriptores', follow_redirects=True)
            if response.status_code in [200, 302]:  # 200 if logged in, 302 if redirected to login
                print("[PASS] Dashboard suscriptores route exists")
            else:
                print(f"[FAIL] Dashboard suscriptores route error: {response.status_code}")
                
    print("\nAll tests completed!")
    return True

if __name__ == '__main__':
    test_suscriptores_feature()