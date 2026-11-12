import sys
sys.path.insert(0, '.')
from auto_customer_communication import AutoCustomerCommunication

print('=' * 80)
print('CUSTOMER COMMUNICATION TEST - PRODUCTION MODE')
print('=' * 80)
print()

comm = AutoCustomerCommunication()
print('AutoCustomerCommunication initialized')
print()

print('Running customer communication cycle...')
try:
    comm.process_communications()
    print()
    print('TEST STATUS: SUCCESS')
except Exception as e:
    print()
    print('TEST STATUS: FAILED')
    print('ERROR: {}'.format(str(e)))
    import traceback
    traceback.print_exc()
