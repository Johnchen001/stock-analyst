#!/usr/bin/env bash
# Send WeChat message via Hermes iLink Bot
exec ~/.hermes/hermes-agent/venv/bin/python3 ~/.hermes/scripts/send_wechat_py.py "$@"
