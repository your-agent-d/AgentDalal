from all_creds import *
import requests
import json
import os
from PIL import Image, ImageDraw, ImageFont
from rembg import new_session, remove
from io import BytesIO

class WhatsApp():

    def __init__(self):
        self.history_file = "history.json"
        if not os.path.exists(self.history_file):
            with open(self.history_file, "w") as f:
                json.dump({}, f)
    
    def send_text_message(self, message):  
        url = f"https://graph.facebook.com/v22.0/{whatsapp_business_phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {wa_access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": wa_phone_number,
            "type": "text",
            "text": {
                "preview_url": False,  # Set to True if your message includes a link
                "body": message
            }
        }

        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            # print("Message sent successfully!", response.json())
            output = response.json()
            msg_id = output["messages"][0]["id"]
            with open(self.history_file, "r") as f:
                history = json.load(f)
            with open(self.history_file, "w") as f:
                history[msg_id] = message
                json.dump(history, f)

            return output
        except requests.exceptions.RequestException as e:
            # print(f"Error sending message: {e}")
            return f"Error sending message: {e}"
        
    def create_and_send_sticker(self, sticker_text, item_image):
        local_path = self.create_sticker(sticker_text, item_image)
        sticker = self.send_sticker(local_path)
        msg_id = sticker["messages"][0]["id"]
        with open(self.history_file, "r") as f:
            history = json.load(f)
        with open(self.history_file, "w") as f:
            history[msg_id] = sticker_text
            json.dump(history, f)
        return sticker

    def create_sticker(self, sticker_text, item_image):
        response = requests.get(item_image, stream=True)
        response.raise_for_status()  # Raise an exception for non-200 status codes

        image = Image.open(BytesIO(response.content))
        image.save("input.png")

        output = remove(image, alpha_matting=True, alpha_matting_foreground_threshold=270,alpha_matting_background_threshold=20, alpha_matting_erode_size=11)
        output.save("input.png")
        img = Image.open("input.png")
        img_resized = img.resize((512, 512))
        img_resized.save("output.webp", "webp")

        output_image = Image.open("output.webp")
        draw = ImageDraw.Draw(output_image)

        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
            , 30)
        except IOError:
            font = ImageFont.load_default()

        lines = sticker_text.split("\n")

        # Calculate text size for each line
        line_sizes = [draw.textbbox((0, 0), line, font=font) for line in lines]
        line_widths = [bbox[2] - bbox[0] for bbox in line_sizes]
        line_heights = [bbox[3] - bbox[1] for bbox in line_sizes]

        # Compute total text height including spacing
        spacing = 15  # Adjust spacing between lines
        total_text_height = sum(line_heights) + (len(lines) - 1) * spacing

        # Define margin from bottom
        bottom_margin = 30  # Adjust this to move text higher or lower

        # Compute starting y-coordinate to position text block near the bottom
        y_start = output_image.height - total_text_height - bottom_margin

        # Draw each line
        shadowcolor = "black"
        shadowoffset = 5

        for i, (line, width, height) in enumerate(zip(lines, line_widths, line_heights)):
            x = (output_image.width - width) / 2  # Center each line horizontally
            y = y_start + sum(line_heights[:i]) + i * spacing  # Adjust y position

            # Draw shadow
            draw.text((x - shadowoffset, y - shadowoffset), line, font=font, fill=shadowcolor)
            draw.text((x + shadowoffset, y - shadowoffset), line, font=font, fill=shadowcolor)
            draw.text((x - shadowoffset, y + shadowoffset), line, font=font, fill=shadowcolor)
            draw.text((x + shadowoffset, y + shadowoffset), line, font=font, fill=shadowcolor)

            # Draw actual text
            draw.text((x, y), line, font=font, fill="white")

        # Save the output
        output_image.save("output_with_text.png")
        img = Image.open("output_with_text.png")
        img_resized = img.resize((512, 512))
        img_resized.save("output_text.webp", "webp")
        return os.path.abspath("output_text.webp")

    def send_sticker(self, sticker_path="<local-path>"):
        if sticker_path == "<local-path>":
            raise ValueError("Please provide a valid sticker path.")

        url = f"https://graph.facebook.com/v22.0/{whatsapp_business_phone_number_id}/media"
        headers = {
            "Authorization": f"Bearer {wa_access_token}"
        }
        files = {
            "file": (sticker_path, open(sticker_path, "rb"), "image/webp")
        }
        data = {
            "messaging_product": "whatsapp"
        }

        try:
            response = requests.post(url, headers=headers, files=files, data=data)
            response.raise_for_status()
            sticker_id = response.json()["id"]
        except requests.exceptions.RequestException as e:
            print(f"Error uploading sticker: {e}")
            if response is not None:
                print(response.text)  # Debugging output
            return f"Error uploading sticker: {e}"


        url = f"https://graph.facebook.com/v22.0/{whatsapp_business_phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {wa_access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": wa_phone_number,
            "type": "sticker",
            "sticker": {
                "id": sticker_id
            }
        }
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            # print("Sticker sent successfully!", response.json())
            print(response.json())
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"Error sending sticker: {e}")
            if response is not None:
                print(response.text)  # Debugging output
            return f"Error sending sticker: {e}"

    def send_audio(self, audio_path="<local-path>"):
        if audio_path == "<local-path>":
            raise ValueError("Please provide a valid audio path.")

        url = f"https://graph.facebook.com/v22.0/{whatsapp_business_phone_number_id}/media"
        headers = {
            "Authorization": f"Bearer {wa_access_token}"
        }
        files = {
            "file": (audio_path, open(audio_path, "rb"), "audio/mpeg")  # Change MIME type as needed
        }
        data = {
            "messaging_product": "whatsapp"
        }

        try:
            response = requests.post(url, headers=headers, files=files, data=data)
            response.raise_for_status()
            audio_id = response.json()["id"]  # Extract uploaded audio ID
        except requests.exceptions.RequestException as e:
            print(f"Error uploading audio: {e}")
            if response is not None:
                print(response.text)  # Debugging output
            return f"Error uploading audio: {e}"

        # Send the uploaded audio
        url = f"https://graph.facebook.com/v22.0/{whatsapp_business_phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {wa_access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": wa_phone_number,
            "type": "audio",
            "audio": {
                "id": audio_id
            }
        }

        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            print(response.json())  # Debugging output
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error sending audio: {e}")
            if response is not None:
                print(response.text)  # Debugging output
            return f"Error sending audio: {e}"
