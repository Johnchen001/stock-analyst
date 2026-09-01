# WeChat PDF Delivery Reference

## Chat Contact

Current WeChat contact ID:
```
o9cq800hCSIovrI8HvOMYOQ-QHAY@im.wechat
```

## Script: send_wechat_pdf.py

Basic PDF sender. Usage:
```bash
~/.hermes/scripts/send_wechat_pdf.py <chat_id> <pdf_path>
```

## Script: send_wechat_pdf_retry.py

PDF sender with exponential-backoff retry (up to 12 attempts, 30s base):
```bash
~/.hermes/scripts/send_wechat_pdf_retry.py <chat_id> <pdf_path>
```

## Script: gen_briefing_pdf.py

Converts markdown briefing to PDF. Usage:
```bash
python3 ~/.hermes/scripts/gen_briefing_pdf.py <input.md> <output.pdf>
```

Uses macOS system fonts:
- `/System/Library/Fonts/STHeiti Light.ttc` (regular weight)
- `/System/Library/Fonts/STHeiti Medium.ttc` (bold weight)

## Rate Limit Handling

iLink Bot API rate limit error message:
```
[Weixin] send failed to=<chat_id>: iLink sendmessage rate limited; cooldown active for 30.0s
```

The retry script handles this. Manual workaround if stuck:
1. Kill all gateway processes: `kill $(pgrep -f "gateway.*run") 2>/dev/null`
2. Wait 60s for server-side cooldown to expire
3. Retry

## API: send_weixin_direct

Located in `gateway/platforms/weixin.py`, function signature:
```python
async def send_weixin_direct(
    *,
    extra: Dict[str, Any],
    token: Optional[str],
    chat_id: str,
    message: str,
    media_files: Optional[List[Tuple[str, bool]]] = None,
) -> Dict[str, Any]:
```

- `media_files`: list of `(file_path, is_voice)` tuples
- Images (.jpg/.jpeg/.png/.gif/.webp/.bmp) sent via `send_image_file`
- All other extensions (including .pdf) sent via `send_document`
