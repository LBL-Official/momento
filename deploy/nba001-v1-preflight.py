#!/usr/bin/env python3
"""Read-only AWS identity/SSM connectivity check. Never sends SSM commands."""
import argparse
import json
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--expected-account', required=True)
    parser.add_argument('--instance', default='i-0f0849d5829476c31')
    parser.add_argument('--region', default='us-east-1')
    args = parser.parse_args()
    result = {'mode': 'READ_ONLY', 'instance': args.instance, 'region': args.region,
              'production_orders_enabled': False, 'checks': {}}
    if not shutil.which('aws'):
        result['blocker'] = 'AWS_CLI_UNAVAILABLE'
    else:
        def aws(*command):
            process = subprocess.run(['aws', '--region', args.region, '--no-cli-pager',
                                      *command, '--output', 'json'], capture_output=True,
                                     text=True, timeout=20)
            if process.returncode:
                # Do not print credential paths, tokens, or command stderr.
                raise RuntimeError('AWS_REQUEST_FAILED')
            return json.loads(process.stdout)
        try:
            identity = aws('sts', 'get-caller-identity')
            if identity['Account'] != args.expected_account:
                raise RuntimeError('AWS_ACCOUNT_MISMATCH')
            result['checks']['account_verified'] = True
            info = aws('ssm', 'describe-instance-information', '--filters',
                       f'Key=InstanceIds,Values={args.instance}')['InstanceInformationList']
            if len(info) != 1 or info[0].get('PingStatus') != 'Online':
                raise RuntimeError('SSM_INSTANCE_NOT_ONLINE')
            result['checks']['ssm_online'] = True
            result['blocker'] = 'HOST_RUNTIME_AND_LIVE_READINESS_NOT_VERIFIED'
        except (RuntimeError, KeyError, ValueError, subprocess.TimeoutExpired) as exc:
            result['blocker'] = str(exc) if isinstance(exc, RuntimeError) else 'AWS_PREFLIGHT_FAILED'
    print(json.dumps(result, indent=2))
    # Identity/online never implies ready to execute, even if both checks pass.
    return 78

if __name__ == '__main__':
    sys.exit(main())
