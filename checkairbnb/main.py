import requests
from securedata import securedata
from securedata import mail

review_count_current = securedata.getItem("airbnb", "review_count")
try:
    url = "https://www.airbnb.com/rooms/52246747"
    r = requests.get(url)

    if ' reviews</button></span>' in r.text:
        review_count_new = r.text.split(
            ' reviews</button></span>')[0].split(">")[-1]
        rating = r.text.split(
            '<button aria-label="Rated ')[1].split(" out of")[0]
        if review_count_current < int(review_count_new):
            securedata.log(f"New Airbnb review; now {review_count_new}")
            mail.send("New Airbnb Review",
                      f"You have a new review on Airbnb. Your rating is now {rating}. Go to <a href='https://tyler.cloud/airbnb'>the listing page</a> and check it out!")
            securedata.setItem("airbnb", "review_count", int(review_count_new))
        elif review_count_current > int(review_count_new):
            securedata.log(
                f"Airbnb review count decrease from {review_count_current} to {review_count_new}", level="warn")
            securedata.setItem("airbnb", "review_count", int(review_count_new))
        else:
            securedata.log(
                f"Checked Airbnb review count; still {review_count_current}")


except Exception as e:
    securedata.log(f"Error checking Airbnb: {e}", level="error")
