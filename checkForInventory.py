from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from sys import path
import os
import pwd
import mail
import datetime

userDir = pwd.getpwuid(os.getuid())[0]

path.insert(0, f'/home/{userDir}/Git/SecureData')
import secureData

begin_time = datetime. datetime. now()

WINDOW_SIZE = "1920, 1080"
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument(f"--window-size={WINDOW_SIZE}")

print("Starting the search")
driver = webdriver.Chrome(executable_path='/usr/lib/chromium-browser/chromedriver/chromedriver', options=chrome_options)

title = driver.title
print(title)

# notify about selected product
def notify(item, url):
    mail.send(f"{item} in Stock!", f"<a href='url'>{url}")

# search

print("Looking for PS5 on Best Buy")
driver.get("https://www.bestbuy.com/site/sony-playstation-5-console/6426149.p?skuId=6426149")
print(driver.title)

el = driver.find_element(By.TAG_NAME, 'body')
str = el.text
if(str.find("Add to Cart") != -1):
    notify("PS5", "https://www.bestbuy.com/site/sony-playstation-5-console/6426149.p?skuId=6426149")

print('Looking for PS5 on Amazon')
driver.get("https://www.amazon.com/PlayStation-5-Digital/dp/B08FC6MR62?ref_=ast_sto_dp")
print(driver.title)

el = driver.find_element(By.TAG_NAME, 'body')
str = el.text
if(str.find("Add to Cart") != -1):
    notify("PS5", "https://www.amazon.com/PlayStation-5-Digital/dp/B08FC6MR62?ref_=ast_sto_dp")

print('Looking for 3080 TI at Best Buy')
driver.get("https://www.bestbuy.com/site/evga-nvidia-geforce-rtx-3080-ti-ftw3-ultra-gaming-12gb-gddr6x-pci-express-4-0-graphics-card/6467808.p?skuId=6467808")
print(driver.title)

el = driver.find_element(By.TAG_NAME, 'body')
str = el.text
if(str.find("Add to Cart") != -1):
    notify("3080 TI", "https://www.bestbuy.com/site/evga-nvidia-geforce-rtx-3080-ti-ftw3-ultra-gaming-12gb-gddr6x-pci-express-4-0-graphics-card/6467808.p?skuId=6467808")

print('Looking for 3090 at Best Buy')
driver.get("https://www.bestbuy.com/site/evga-geforce-rtx-3090-xc3-ultra-gaming-24gb-gddr6-pci-express-4-0-graphics-card/6434198.p?skuId=6434198")
print(driver.title)

el = driver.find_element(By.TAG_NAME, 'body')
str = el.text
if(str.find("Add to Cart") != -1):
    notify("3090", "https://www.bestbuy.com/site/evga-geforce-rtx-3090-xc3-ultra-gaming-24gb-gddr6-pci-express-4-0-graphics-card/6434198.p?skuId=6434198")

# driver.close()

driver.delete_all_cookies()
print('Looking for PS5 Digital Edition at Gamestop')
# driver = webdriver.Chrome(executable_path='/usr/lib/chromium-browser/chromedriver/chromedriver')
driver.get("https://www.gamestop.com/video-games/playstation-5/consoles/products/playstation-5-digital-edition/11108141.html?condition=New")
print(driver.title)

el = driver.find_element(By.TAG_NAME, 'body')
str = el.text
if(str.find("ADD TO CART") != -1):
    notify("PS5", "https://www.gamestop.com/video-games/playstation-5/consoles/products/playstation-5-digital-edition/11108141.html?condition=New")

print('Looking for PS5 at Gamestop')
driver.get("https://www.gamestop.com/video-games/playstation-5/consoles/products/playstation-5/11108140.html?condition=New")
print(driver.title)

el = driver.find_element(By.TAG_NAME, 'body')
str = el.text
if(str.find("ADD TO CART") != -1):
    notify("PS5", "https://www.gamestop.com/video-games/playstation-5/consoles/products/playstation-5/11108140.html?condition=New")

driver.close()

print(f"Finished searching in {datetime. datetime. now() - begin_time}ms")