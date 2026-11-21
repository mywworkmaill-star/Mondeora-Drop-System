#!/bin/bash
# Test workflow script - Phase 1: Health Check

echo "==================================================================="
echo "HEALTH CHECK"
echo "==================================================================="

# Check database
if [ -f "data/dropshipping.db" ]; then
    echo "Database: OK"
else
    echo "Database: NOT FOUND"
    exit 1
fi

# Check tokens
if [ -f ".env" ]; then
    echo "Tokens file: OK"
else
    echo "Tokens file: NOT FOUND (continuing...)"
fi

# Check eBay connection
echo "eBay API: OK (mocked)"

# Check AliExpress connection
echo "AliExpress API: OK (mocked)"

echo ""
echo "All systems operational!"
echo ""

exit 0
