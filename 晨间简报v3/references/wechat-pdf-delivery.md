# WeChat PDF Delivery Reference

## Chat Contact

Current WeChat contact ID:
```
<YOUR_CHAT_ID>@im.wechat
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

## Script: gen_briefing_pdf_v2.py  ← 现行版式（2026-10-28 起）

Converts markdown briefing to PDF with the v2 蓝白 layout. Usage:
```bash
~/.hermes/hermes-agent/venv/bin/python3 \
  ~/.hermes/scripts/gen_briefing_pdf_v2.py <input.md> <output.pdf>
```

- 字体：从 `/System/Library/Fonts/Supplemental/Songti.ttc` 抽宋体
  `Songti SC Regular`（face 6）/ `Songti SC Bold`（face 1），缓存到
  `$BRIEFING_FONT_CACHE` → `~/.cache/a-share-briefing/fonts` → 系统临时目录
- 版式细则：`references/pdf-layout-spec.md`（蓝白配色、宋体小四 12pt、章节自适应压排）
- 需要 `fpdf2 >= 2.8` + `fontTools`

`gen_briefing_pdf.py`（v1 旧版式，深色封面 / 9pt 正文 / STHeiti 字体）只作回退，新产出不要用。

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
