#!/usr/bin/env python3
import json
import os
import sys
from html.parser import HTMLParser
from urllib.parse import urljoin
from urllib.request import Request, urlopen


BASE_URL = "https://mcpservers.org/"
TARGET_PATH = os.path.join("data", "mcp-servers.json")

REQUIRED_GRID_CLASSES = {
    "grid",
    "grid-cols-1",
    "sm:grid-cols-2",
    "lg:grid-cols-3",
    "xl:grid-cols-4",
    "gap-6",
}

REQUIRED_CARD_CLASSES = {
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
}

TITLE_CLASSES = {"tracking-tight", "text-xl", "font-semibold"}
DESC_CLASSES = {"text-sm", "text-gray-600", "leading-relaxed"}


def fetch_html(url: str) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
        },
    )
    with urlopen(req, timeout=30) as resp:
        data = resp.read()
    return data.decode("utf-8", errors="ignore")


def attrs_to_dict(attrs):
    return {k: v for (k, v) in attrs}


def has_all_classes(attr_dict, required_classes):
    class_value = attr_dict.get("class")
    if not class_value:
        return False
    class_set = set(class_value.split())
    return required_classes.issubset(class_set)


class MCPCardStreamParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.results = []

        self.grid_depth = 0  # >0 means we are inside the grid container

        self.in_card = False
        self.card_depth = 0  # counts nested tags while in a card

        self.title_depth = 0
        self.desc_depth = 0

        self.current = None

    def handle_starttag(self, tag, attrs):
        attr_dict = attrs_to_dict(attrs)

        # Track grid container depth (start when we hit the matching div)
        if tag == "div":
            if self.grid_depth == 0 and has_all_classes(attr_dict, REQUIRED_GRID_CLASSES):
                self.grid_depth = 1
            elif self.grid_depth > 0:
                self.grid_depth += 1

        elif self.grid_depth > 0:
            # Non-div tags still increase depth while inside the grid
            self.grid_depth += 1

        # If we're inside the grid, check for a new card start
        if self.grid_depth > 0 and tag == "div":
            if not self.in_card and has_all_classes(attr_dict, REQUIRED_CARD_CLASSES):
                self.in_card = True
                self.card_depth = 1
                self.title_depth = 0
                self.desc_depth = 0
                self.current = {"title": "", "description": "", "url": None}
            elif self.in_card:
                self.card_depth += 1

            # Start collecting title/description when we enter their containers
            if self.in_card and has_all_classes(attr_dict, TITLE_CLASSES):
                self.title_depth = 1
            elif self.in_card and self.title_depth > 0:
                self.title_depth += 1

            if self.in_card and has_all_classes(attr_dict, DESC_CLASSES):
                self.desc_depth = 1
            elif self.in_card and self.desc_depth > 0:
                self.desc_depth += 1

        elif self.in_card:
            # While in card, any nested tag increases card depth
            self.card_depth += 1
            if self.title_depth > 0:
                self.title_depth += 1
            if self.desc_depth > 0:
                self.desc_depth += 1

        # Capture first link inside the card
        if self.in_card and tag == "a" and self.current and self.current.get("url") is None:
            href = attr_dict.get("href")
            if href:
                self.current["url"] = urljoin(BASE_URL, href)

    def handle_endtag(self, tag):
        # Close card tracking
        if self.in_card:
            if self.card_depth > 0:
                self.card_depth -= 1
            if tag == "div":
                if self.title_depth > 0:
                    self.title_depth -= 1
                if self.desc_depth > 0:
                    self.desc_depth -= 1

            if self.card_depth == 0:
                # Finish this card
                if self.current is not None:
                    # Normalize whitespace
                    title = self.current["title"].strip() or None
                    description = self.current["description"].strip() or None
                    url = self.current["url"]
                    self.results.append(
                        {"title": title, "description": description, "url": url}
                    )
                self.in_card = False
                self.current = None
                self.title_depth = 0
                self.desc_depth = 0

        # Track grid container depth and closing
        if self.grid_depth > 0:
            self.grid_depth -= 1

    def handle_data(self, data):
        if not self.in_card or self.current is None:
            return
        if self.title_depth > 0:
            self.current["title"] += data
        if self.desc_depth > 0:
            self.current["description"] += data


def parse_cards(html: str):
    parser = MCPCardStreamParser()
    parser.feed(html)
    return parser.results


def save_json(records, target_path: str):
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def main():
    try:
        html = fetch_html(BASE_URL)
        records = parse_cards(html)
        save_json(records, TARGET_PATH)
        print(f"Saved {len(records)} items to {TARGET_PATH}")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()