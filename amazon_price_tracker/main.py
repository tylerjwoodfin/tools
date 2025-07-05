"""
amazon price tracker

see README.md for more information
"""

from typing import List, Optional, TypedDict
import re
from bs4 import BeautifulSoup  # type: ignore # pylint: disable=import-error
import requests
from cabinet import Cabinet, Mail

cabinet = Cabinet()

class AmazonTrackerItem(TypedDict):
    """
    The required data type in Cabinet. See README.md for more information.
    """
    url: str
    price_threshold: int

class AmazonTrackerData(TypedDict):
    """
    The structure of the amazon_tracker data in Cabinet.
    """
    items: List[AmazonTrackerItem]

def get_page_content(url: str) -> Optional[str]:
    """
    retrieves the html content of a given url

    :param url: the url of the amazon product page
    :return: the html content if successful, None otherwise
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "TE": "Trailers"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Error fetching the page content: {e}")
        return None

def parse_price(html_content: str) -> Optional[float]:
    """
    parses the price from the html content using multiple selectors to handle different page layouts

    :param html_content: the html content of the amazon product page
    :return: the price as a float if found, None otherwise
    """
    soup = BeautifulSoup(html_content, "html.parser")

    # List of possible price selectors
    price_selectors = [
        # New price selectors
        'span.a-price span.a-offscreen',
        'span[data-a-color="price"] span.a-offscreen',
        '#corePrice_feature_div span.a-offscreen',
        '#priceblock_ourprice',
        '#priceblock_dealprice',
        '.a-price .a-offscreen',
        '#price_inside_buybox',
        '#newBuyBoxPrice',
        'span.priceToPay span.a-offscreen'
    ]

    price: Optional[float] = None

    for selector in price_selectors:
        try:
            element = soup.select_one(selector)
            if element:
                # Extract price text and clean it
                price_text = element.get_text().strip()
                # Remove currency symbols and commas, handle ranges
                price_text = re.sub(r'[^\d.,]', '', price_text)
                if '-' in price_text:
                    # If price range, take the lower price
                    price_text = price_text.split('-')[0]

                # Handle different decimal separators
                if ',' in price_text and '.' in price_text:
                    # Format like 1,234.56
                    price_text = price_text.replace(',', '')
                elif ',' in price_text:
                    # Format like 1234,56
                    price_text = price_text.replace(',', '.')

                price = float(price_text)
                if price > 0:
                    return price
        except (ValueError, AttributeError) as e:
            cabinet.log(f"Error parsing price: {e}", level="warn")
            continue

    # Try finding any price-like text in the page
    if price is None:
        price_pattern = r'\$\s*(\d+(?:,\d{3})*(?:\.\d{2})?)'
        matches = re.findall(price_pattern, html_content)
        if matches:
            try:
                price = float(matches[0].replace(',', ''))
                if price > 0:
                    return price
            except ValueError:
                pass

    cabinet.log("Could not find the price element", level="warn")
    return None

def main() -> None:
    """
    the main function of the program
    """
    mail = Mail()

    amazon_data = cabinet.get("amazon_tracker", return_type=AmazonTrackerData)

    if not amazon_data or not amazon_data.get("items"):
        cabinet.log("No Amazon items set. Exiting.")
        return

    amazon_urls = amazon_data["items"]

    if not amazon_urls:
        cabinet.log("No Amazon URLs set. Exiting.")
        return

    for item in amazon_urls:
        url: str | None = item.get("url")
        price_threshold: int | None = item.get("price_threshold")

        if not url or price_threshold is None:
            cabinet.log(f"Missing price or url in amazon_tracker: {item}")
            continue

        html_content = get_page_content(url)
        if not html_content:
            continue

        current_price = parse_price(html_content)
        if current_price is None:
            cabinet.log(f"Could not parse price for {url}")
            continue

        if current_price <= price_threshold:
            subject = "Amazon Price Alert"
            body = (
                f"The price for the item at {url} has dropped to ${current_price}, "
                f"which is below your threshold of ${price_threshold}."
            )
            mail.send(subject, body)
            cabinet.log(f"Price alert sent for {url}. Current price: ${current_price}")
        else:
            cabinet.log(
                f"Checked {url}. Current price (${current_price}) is above the threshold "
                f"(${price_threshold})."
            )

if __name__ == "__main__":
    main()
