#!/usr/bin/env python3
import json
import sys
import time
from dataclasses import asdict, dataclass
from typing import List, Optional

import requests
from bs4 import BeautifulSoup, Tag

BASE_URL = "https://mcpservers.org"
LISTING_PATH = "/"
OUTPUT_PATH = "/workspace/data/mcp-servers.json"


@dataclass
class MCPServer:
    title: str
    description: str
    url: str


def fetch_html(url: str, max_retries: int = 3, timeout: int = 15) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
        )
    }

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            if attempt == max_retries:
                raise
            sleep_seconds = 1.5 * attempt
            print(f"Request failed (attempt {attempt}/{max_retries}): {exc}. Retrying in {sleep_seconds:.1f}s...", file=sys.stderr)
            time.sleep(sleep_seconds)

    raise RuntimeError("Unreachable: retries exhausted without raising")


def element_has_classes(element: Tag, required_classes: List[str]) -> bool:
    classes = element.get("class", [])
    if not isinstance(classes, list):
        return False
    classes_set = set(classes)
    return all(req in classes_set for req in required_classes)


def extract_card_title(card: Tag) -> Optional[str]:
    title_div = card.find(
        lambda tag: isinstance(tag, Tag)
        and tag.name == "div"
        and element_has_classes(tag, ["tracking-tight", "text-xl", "font-semibold"])
    )
    if title_div and title_div.get_text(strip=True):
        return title_div.get_text(strip=True)
    return None


def extract_card_description(card: Tag) -> Optional[str]:
    desc_div = card.find(
        lambda tag: isinstance(tag, Tag)
        and tag.name == "div"
        and element_has_classes(tag, ["text-sm", "text-gray-600", "leading-relaxed"])
    )
    if desc_div and desc_div.get_text(strip=True):
        return desc_div.get_text(strip=True)
    return None


def extract_card_url(card: Tag) -> Optional[str]:
    # Find the first anchor in the footer area
    anchor = card.find("a", href=True)
    if not anchor:
        return None
    href = anchor.get("href")
    if not href:
        return None
    if href.startswith("http://") or href.startswith("https://"):
        return href
    # Normalize relative URL
    if not href.startswith("/"):
        href = "/" + href
    return f"{BASE_URL}{href}"


def parse_servers_from_html(html: str) -> List[MCPServer]:
    soup = BeautifulSoup(html, "lxml")

    grid_required_classes = [
        "grid",
        "grid-cols-1",
        "sm:grid-cols-2",
        "lg:grid-cols-3",
        "xl:grid-cols-4",
        "gap-6",
    ]
    grid_container = soup.find(
        lambda tag: isinstance(tag, Tag)
        and tag.name == "div"
        and element_has_classes(tag, grid_required_classes)
    )

    if not grid_container:
        raise RuntimeError("Could not locate the grid container with the expected classes.")

    card_required_classes = [
        "rounded-xl",
        "border",
        "bg-card",
        "text-card-foreground",
        "shadow",
        "flex",
        "flex-col",
        "hover:shadow-lg",
        "transition-shadow",
        "duration-300",
        "border-opacity-40",
    ]

    servers: List[MCPServer] = []

    card_divs = grid_container.find_all(
        lambda tag: isinstance(tag, Tag)
        and tag.name == "div"
        and element_has_classes(tag, card_required_classes)
    )

    for card in card_divs:
        title = extract_card_title(card) or ""
        description = extract_card_description(card) or ""
        url = extract_card_url(card) or ""

        # Skip entirely empty cards
        if not any([title, description, url]):
            continue

        servers.append(MCPServer(title=title, description=description, url=url))

    return servers


def save_servers_to_json(servers: List[MCPServer], output_path: str = OUTPUT_PATH) -> None:
    data = [asdict(server) for server in servers]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main() -> int:
    url = f"{BASE_URL}{LISTING_PATH}"
    print(f"Fetching: {url}")
    html = fetch_html(url)
    servers = parse_servers_from_html(html)
    print(f"Parsed {len(servers)} servers")
    save_servers_to_json(servers, OUTPUT_PATH)
    print(f"Saved to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())