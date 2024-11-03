# Amazon Price Tracker

A simple price tracker for Amazon.

## dependencies
- [cabinet](https://pypi.org/project/cabinet/)
- [requests](https://pypi.org/project/requests/)

## setup
- `cabinet -e`
- add an amazon_tracker object with as many urls as you want to track.

```json
"amazon_tracker": {
    "items": [
        {
            "url": "https://amazon.com/<whatever>",
            "price_threshold": 0, // prices below this will trigger email
        }
    ]
},
```

## usage
- add to crontab as necessary
- email is sent if price is below threshold
