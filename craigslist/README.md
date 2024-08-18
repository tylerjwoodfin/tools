# Craigslist Scraper

A simple tool to scrape the SF Bay Free Stuff section for certain items.

## usage

```bash
python3 main.py item1 item2 item3 ...
```

or

```bash
python3 main.py
```
(uses Cabinet to load requested items from `craigslist -> items`)

## dependencies
- [cabinet](https://pypi.org/project/cabinet/)
- [bs4](https://pypi.org/project/beautifulsoup4/)
- [requests](https://pypi.org/project/requests/)