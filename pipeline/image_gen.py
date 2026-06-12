import asyncio
import urllib.parse
import httpx


POLLINATIONS_BASE = "https://image.pollinations.ai/prompt/"


async def generate_image(
    prompt: str,
    output_path: str,
    width: int = 1920,
    height: int = 1080,
    seed: int = 42,
) -> str:
    """Fetch image from Pollinations.ai and save to output_path."""
    encoded = urllib.parse.quote(prompt)
    url = f"{POLLINATIONS_BASE}{encoded}?width={width}&height={height}&nologo=true&seed={seed}&model=flux"

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
                resp = await client.get(url)

                if resp.status_code == 200 and len(resp.content) > 2000:
                    with open(output_path, "wb") as f:
                        f.write(resp.content)
                    return output_path

                raise Exception(f"Bad response: status={resp.status_code} size={len(resp.content)}")

        except Exception as exc:
            print(f"Image gen attempt {attempt + 1} failed: {exc}")
            if attempt < 2:
                await asyncio.sleep(6)

    print(f"Image gen failed for prompt '{prompt[:60]}...' — using placeholder")
    return _placeholder(prompt, output_path, width, height)


def _placeholder(prompt: str, output_path: str, width: int, height: int) -> str:
    """Generate a gradient placeholder image when the API fails."""
    from PIL import Image, ImageDraw
    import hashlib

    h = int(hashlib.md5(prompt.encode()).hexdigest()[:6], 16)
    r, g, b = (h >> 16) & 255, (h >> 8) & 255, h & 255

    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)
    for y in range(height):
        ratio = y / height
        draw.line(
            [(0, y), (width, y)],
            fill=(int(r * (1 - ratio) + 10), int(g * (1 - ratio) + 10), int(b * (1 - ratio) + 10)),
        )

    img.save(output_path, "JPEG", quality=85)
    return output_path
