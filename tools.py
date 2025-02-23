import os
from zepto import Zepto


from typing import List, Tuple
from langchain_core.tools import tool

from all_creds import *

from whatsapp import WhatsApp
wa = WhatsApp()

zepto = Zepto(zepto_login_number)
print("Zepto setup")

# ---------------- WhatsApp ----------------
@tool
def send_whatsapp_message(
    message: str = "Hello, how can I help you?"
) -> str:
    """
    Send a message to the user using WhatsApp.

    Args:
        message (str): Message to send. Defaults to "Hello, how can I help you?".

    Returns:
        str: Message status
    """
    return wa.send_text_message(message)

@tool
def create_and_send_whatsapp_sticker(
    sticker_text: str = "milk\n30 rs (20% discount)",
    item_image: str = "https://example.com/image.jpg",
) -> str:
    """
    Creates and send a sticker message to the user using WhatsApp for every search result.

    Args:
        sticker_text (str): very short text to put on the sticker (not more than 6 words). It is a two line text, separated by a '\n'. The first line is product name and the second line is info about price and discount in short. example: milk\n30 rs (20% discount).
        item_image (str): URL of the item image. Defaults to "https://example.com/image.jpg".

    Returns:
        str: Message status
    """
    global wa
    return wa.create_and_send_sticker(sticker_text, item_image)


# ---------------- Zepto ----------------

@tool
def search_grocery_products(
    product_name: str = "milk"
) -> List[Tuple]:
    """
    Search for products using a web scraper (Zepto in this case).

    Args:
        product_name (str): Name of the product to search. Defaults to "milk".

    Returns:
        List[Tuple]: A list of tuples of the format (product_index, product_description, image_link)
    """
    product_elements = zepto.search_product(product_name)
    return product_elements

@tool
def add_product_to_grocery_cart(
    product_index: int = 0
) -> str:
    """
    Add product to the cart.

    Args:
        product_index (int): Index of the product to add. Defaults to 0.

    Returns:
        str: Action status
    """
    try:
        zepto.add_to_cart(product_index)
        return "Product added to cart"
    except:
        return "Product not added to cart"
    
@tool
def pay_for_grocery_cart() -> str:
    """
    Pay for the cart.

    Returns:
        str: Payment url
    """
    print("reached here for payment")
    output_text = zepto.pay_cart()
    print("*"*50)
    print(output_text)
    return zepto.pay_cart()

grocery_ordering_safe_tools = [search_grocery_products, add_product_to_grocery_cart, send_whatsapp_message, create_and_send_whatsapp_sticker]
grocery_ordering_sensitive_tools = [pay_for_grocery_cart]
grocery_ordering_tools = grocery_ordering_safe_tools + grocery_ordering_sensitive_tools