#!/Users/hr_chen/.hermes/hermes-agent/venv/bin/python3
"""Send a PDF file to WeChat with retry logic for rate limiting."""
import sys, os, json, asyncio, time

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

async def send_with_retry(chat_id, pdf_path, max_retries=12):
    if not os.path.exists(pdf_path):
        print(f"❌ File not found: {pdf_path}")
        return False

    token = os.environ.get('WEIXIN_TOKEN', '')
    account_id = os.environ.get('WEIXIN_ACCOUNT_ID', '')
    base_url = os.environ.get('WEIXIN_BASE_URL', 'https://ilinkai.weixin.qq.com')

    for attempt in range(1, max_retries + 1):
        result = await send_weixin_direct(
            extra={
                "account_id": account_id,
                "base_url": base_url,
                "token": token,
            },
            token=token,
            chat_id=chat_id,
            message="",
            media_files=[(pdf_path, False)],
        )

        if result.get("success"):
            print(f"✅ PDF sent to {chat_id}")
            return True

        error = result.get("error", "")
        if "rate limited" in error.lower():
            wait = min(30 * attempt, 120)
            print(f"⏳ Rate limited (attempt {attempt}/{max_retries}), waiting {wait}s...")
            await asyncio.sleep(wait)
        else:
            print(f"❌ Failed: {error}")
            return False

    print("❌ Exhausted all retries.")
    return False

async def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return
    chat_id = sys.argv[1]
    pdf_path = os.path.expanduser(sys.argv[2])
    await send_with_retry(chat_id, pdf_path)

if __name__ == '__main__':
    asyncio.run(main())
