# Amazon Price Tracker

A simple price tracker for Amazon.

## dependencies
- [cabinet](https://pypi.org/project/cabinet/)
- [requests](https://pypi.org/project/requests/)

## setup
- `pip install -r requirements.md`
- `cabinet -e` to initialize cabinet for the first time
    - See [detailed instructions](https://github.com/tylerjwoodfin/cabinet?tab=readme-ov-file#mail) for configuring mail
- add an amazon_tracker object with as many urls as you want to track, following the example below.
    - When the price drops below `price_threshold`, an email will be sent to the address specified in the `email` object.

Your Cabinet settings file should look like this, at a minimum:
```json
{
    "email": {
        "from": "throwaway@example.com",
        "from_pw": "example",
        "from_name": "Cabinet (or other name of your choice)",
        "to": "destination@protonmail.com",
        "smtp_server": "example.com",
        "imap_server": "example.com",
        "port": 123
    },
    "amazon_tracker": {
        "items": [
            {
                "url": "https://amazon.com/<whatever>",
                "price_threshold": 0
            }
        ]
    }
}
```

## usage
- add to crontab as necessary
- email is sent if price is below threshold
