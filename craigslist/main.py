"""
Craigslist Scraper
"""

import sys
from typing import List
import requests
from bs4 import BeautifulSoup
from cabinet import Cabinet, Mail

def scrape_craigslist(cli_items: List[str] = []) -> None: # pylint: disable=dangerous-default-value
    """
    Scrape Craigslist for requested free items
    """

    url = "https://sfbay.craigslist.org/search/zip?postal=94108&search_distance=3"
    response = requests.get(url, timeout=10)
    soup = BeautifulSoup(response.text, 'html.parser')
    cab: Cabinet = Cabinet()
    mail: Mail = Mail()

    # Use command-line arguments if provided, otherwise use Cabinet
    if cli_items:
        requested_items = [item.lower() for item in cli_items]
    else:
        requested_items: List[str] = cab.get("craigslist", "items") or []

    found_items: List[str] = cab.get("craigslist", "sent") or []
    is_found_items: bool = False

    for post in soup.find_all('li', class_='cl-static-search-result', limit=8):
        title_div = post.find('div', class_='title')
        if title_div:
            title = title_div.text.strip().lower()

            # Get the post URL
            post_url = post.find('a')['href']

            # check if any of the requested items are in the title
            for item in requested_items:
                if item in title and post_url not in found_items:
                    mail.send(f"Found {item}", f"<a href='{post_url}'>{title}</a>")
                    found_items.append(post_url)
                    is_found_items = True

    # add any sent items to the list
    if is_found_items:
        cab.put("craigslist", "sent", found_items)
    else:
        print("No items found")

if __name__ == "__main__":
    # If command-line arguments are provided, use them as requested items
    if len(sys.argv) > 1:
        scrape_craigslist(sys.argv[1:])
    else:
        scrape_craigslist()
