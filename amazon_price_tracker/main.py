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

AMAZON_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

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

def extract_asin(url: str) -> Optional[str]:
    """
    extracts the ASIN from an amazon product url

    :param url: the url of the amazon product page
    :return: the ASIN if found, None otherwise
    """
    match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", url)
    return match.group(1) if match else None

def create_amazon_session() -> requests.Session:
    """
    creates a requests session that can fetch amazon product pages

    :return: a warmed-up requests session
    """
    session = requests.Session()
    session.headers.update(AMAZON_HEADERS)
    session.get("https://www.amazon.com/", timeout=10)
    return session

def get_page_content(url: str, session: requests.Session) -> Optional[str]:
    """
    retrieves the html content of a given url

    :param url: the url of the amazon product page
    :param session: a warmed-up requests session
    :return: the html content if successful, None otherwise
    """
    asin = extract_asin(url)
    product_url = f"https://www.amazon.com/dp/{asin}" if asin else url

    try:
        response = session.get(product_url, timeout=10)
        response.raise_for_status()
        html_content = response.text
        if len(html_content) < 20000 and "captcha" in html_content.lower():
            cabinet.log(f"Amazon returned a captcha page for {product_url}", level="warn")
            return None
        return html_content
    except requests.RequestException as e:
        cabinet.log(f"Error fetching the page content for {product_url}: {e}", level="warn")
        return None

def parse_price_text(price_text: str) -> Optional[float]:
    """
    parses a price string into a float

    :param price_text: raw price text from the page
    :return: the price as a float if found, None otherwise
    """
    price_text = re.sub(r"[^\d.,-]", "", price_text.strip())
    if not price_text:
        return None
    if "-" in price_text:
        price_text = price_text.split("-")[0]

    if "," in price_text and "." in price_text:
        price_text = price_text.replace(",", "")
    elif "," in price_text:
        price_text = price_text.replace(",", ".")

    try:
        price = float(price_text)
    except ValueError:
        return None

    return price if price > 0 else None

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
            for element in soup.select(selector):
                price = parse_price_text(element.get_text())
                if price is not None and price >= 10:
                    return price
        except AttributeError as e:
            cabinet.log(f"Error parsing price: {e}", level="warn")
            continue

    json_price_patterns = [
        r'"priceAmount"\s*:\s*([0-9.]+)',
        r'"displayPrice"\s*:\s*"\$?([0-9.]+)"',
    ]
    for pattern in json_price_patterns:
        match = re.search(pattern, html_content)
        if match:
            price = parse_price_text(match.group(1))
            if price is not None and price >= 10:
                return price

    # Try finding any price-like text in the page
    if price is None:
        price_pattern = r'\$\s*(\d+(?:,\d{3})*(?:\.\d{2})?)'
        matches = re.findall(price_pattern, html_content)
        for match in matches:
            price = parse_price_text(match)
            if price is not None and price >= 10:
                return price

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

    session = create_amazon_session()

    for item in amazon_urls:
        url: str | None = item.get("url")
        price_threshold: int | None = item.get("price_threshold")

        if not url or price_threshold is None:
            cabinet.log(f"Missing price or url in amazon_tracker: {item}")
            continue

        html_content = get_page_content(url, session)
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
