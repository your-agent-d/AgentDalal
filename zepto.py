import time
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains


class Zepto():
    def __init__(self, phone_number):
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument("--start-maximized")
        self.driver = webdriver.Chrome(options=options)
        url = "https://www.zeptonow.com/"
        self.driver.get(url)

        # self._login(phone_number)
        self.product_choices = None

    def _wait(self, seconds=5):
        time.sleep(seconds)

    def _login(self, phone_number):
        login_button = self.driver.find_element(By.XPATH, "//button[@aria-label='login']")
        login_button.click()

        self._wait()

        login_popup = self.driver.find_element(By.XPATH, "//div[@class='login-container']")
        ph_input = login_popup.find_element(By.XPATH, "//input[@placeholder='Enter Phone Number']")
        ph_input.send_keys(phone_number)

        self._wait()

        con_button = ph_input.find_element(By.XPATH, "./../../../button")
        con_button.click()

        self._wait()

        opt_popup = self.driver.find_element(By.XPATH, "//div[@class='verifyOTP-container']")
        opt_popup.find_element(By.XPATH, "//input[@inputmode='numeric']").send_keys(input("Enter otp:"))

        self._wait()
        self.driver.save_screenshot("login.png")

        loc = self.driver.find_element(By.XPATH, "//span[@data-testid='user-address']")
        loc.click()

        self._wait()

        adds_block = self.driver.find_element(By.XPATH, "//div[@data-testid='saved-address-list']")
        adds_list = adds_block.find_elements(By.XPATH, "./div")
        self.driver.save_screenshot("screenshot.png")
        adds_list[0].click()

        self._wait()

    def search_product(self, product_name):

        search_url = "https://www.zeptonow.com/search"
        self.driver.get(search_url)

        self._wait()

        search_box = self.driver.find_element(By.XPATH, "//input[@placeholder='Search for over 5000 products']")
        search_box.send_keys(product_name)

        self._wait()

        search_box.send_keys(Keys.ENTER)

        self._wait()

        self.product_choices = self.driver.find_elements(By.XPATH, "//a[@data-testid='product-card']")
        product_descp = []
        for idx, itm in enumerate(self.product_choices):
            image = itm.find_element(By.XPATH, ".//img[@data-testid='product-card-image']")
            srcset = image.get_attribute("srcset")
            if srcset:
                pattern = re.compile(r'(\S+)\s+(\d+[wx])')
                matches = pattern.findall(srcset)
                # srcset_links = [match[0] for match in matches]
                srcset_link = matches[0][0]

            product_descp.append((idx, itm.text, srcset_link))
        return product_descp

    def add_to_cart(self, idx):
        self.product_choices[idx].find_element(By.XPATH, "//button[@aria-label='Add']").click()
        self._wait()

    def pay_cart(self):

        cart = self.driver.find_element(By.XPATH, "//a[@aria-label='Cart']")
        cart.click()

        self._wait()

        self.driver.save_screenshot("cart.png")

        try:
            pay = self.driver.find_element(By.XPATH, "//p[contains(text(), 'Click to Pay ')]")
            pay.click()
            self.driver.save_screenshot("cart_clickable.png")

        except:
            self.driver.save_screenshot("popup_error.png")

            try:
                # This will make a click on the dark background area
                # to close a zepto's pop-up if it came up
                window_size = self.driver.get_window_size()
                width = window_size["width"]
                height = window_size["height"]

                # Move to a position in the dark background area (e.g., 10% from top-left)
                ActionChains(self.driver).move_by_offset(width * 0.1, height * 0.1).click().perform()

                pay = self.driver.find_element(By.XPATH, "//p[contains(text(), 'Click to Pay ')]")
                pay.click()
                self.driver.save_screenshot("res_popup_error.png")
                self._wait()

            except:
                self.driver.save_screenshot("unres.png")
                print("Some issue with Cart's page!!! Inspection Required!!!")

        self._wait()
        self.driver.save_screenshot("final.png")
        print(self.driver.current_url)
        print("didit print?")

        return "Here is the payment link to send to the user: " + self.driver.current_url + " \n Give to user and ask to click."