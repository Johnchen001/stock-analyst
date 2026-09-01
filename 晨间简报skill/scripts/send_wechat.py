#!/Users/hr_chen/.hermes/hermes-agent/venv/bin/python3
"""Send WeChat messages via Hermes iLink Bot.

Usage:
  ~/.hermes/scripts/send_wechat.py list
  ~/.hermes/scripts/send_wechat.py <chat_id> <message>

Examples:
  ~/.hermes/scripts/send_wechat.py list
  ~/.hermes/scripts/send_wechat.py o9cq800hCSIovrI8HvOMYOQ-QHAY@im.wechat "你好"
  echo "hello" | ~/.hermes/scripts/send_wechat.py o9cq...@im.wechat
"""
import sys
import os
import json
import asyncio

# Load .env
env_path = os.path.expanduser('~/.hermes/.env')
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                os.environ[k.strip()] = v.strip()

sys.path.insert(0, os.path.expanduser('~/.hermes/hermes-agent'))
os.chdir(os.path.expanduser('~/.hermes/hermes-agent'))

from gateway.platforms.weixin import send_weixin_direct

def list_contacts():
    tokens_dir = os.path.expanduser('~/.hermes/weixin/accounts/')
    if not os.path.isdir(tokens_dir):
        print("No WeChat accounts directory found.")
        return
    for fname in os.listdir(tokens_dir):
        if fname.endswith('.context-tokens.json'):
            path = os.path.join(tokens_dir, fname)
            with open(path) as f:
                tokens = json.load(f)
            account = fname.replace('.context-tokens.json', '')
            print(f"\nAccount: {account}")
            for uid in tokens:
                print(f"  └ chat_id: {uid}")

async def send(chat_id, message):
    token = os.environ.get('WEIXIN_TOKEN', '')
    account_id = os.environ.get('WEIXIN_ACCOUNT_ID', '')
    base_url = os.environ.get('WEIXIN_BASE_URL', 'https://ilinkai.weixin.qq.com')

    result = await send_weixin_direct(
        extra={
            "account_id": account_id,
            "base_url": base_url,
            "token": token,
        },
        token=token,
        chat_id=chat_id,
        message=message,
    )

    if result.get("success"):
        print(f"✅ Sent to {chat_id}")
        return True
    else:
        print(f"❌ Failed: {result.get('error', 'unknown error')}")
        return False

async def main():
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help'):
        print(__doc__)
        return

    if sys.argv[1] == 'list':
        list_contacts()
        return

    chat_id = sys.argv[1]
    message = ' '.join(sys.argv[2:]) if len(sys.argv) > 2 else ''
    if not message:
        message = sys.stdin.read().strip()
    if not message:
        print("Error: no message provided.")
        sys.exit(1)

    await send(chat_id, message)

if __name__ == '__main__':
    asyncio.run(main())
