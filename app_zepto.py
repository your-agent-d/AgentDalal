from flask import Flask, request, jsonify
import uuid
import logging
from all_creds import *
import os
import sys
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import requests
import threading
import socketio
import json
from pydub import AudioSegment
import mimetypes

app = Flask(__name__, static_url_path='/static')
app.config['SECRET_KEY'] = 'your_secret_key'

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Maintain conversation state per session
conversations = {}

thread_id = str(uuid.uuid4())
config = {
    "configurable": {
        "passenger_id": "3442 587242",
        "thread_id": thread_id,
    }
}

# Initialize printed events tracker
_printed = set()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def send_whatsapp_message(message):    
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
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error sending message: {e}")
        if response is not None:
            print(response.text)  # Debugging output
        return f"Error sending message: {e}"

def send_whatsapp_sticker(sticker_path="<local-path>"):
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
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error sending sticker: {e}")
        if response is not None:
            print(response.text)  # Debugging output
        return f"Error sending sticker: {e}"
 

def get_text_from_speech(aud_id, aud_type):
    """Fetches and transcribes audio from WhatsApp using Sarvam AI."""
    
    # Get media URL from WhatsApp API
    url = f"https://graph.facebook.com/v22.0/{aud_id}"
    headers = {"Authorization": f"Bearer {wa_access_token}"}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        media_url = response.json().get("url")
    except requests.exceptions.RequestException as e:
        print(f"Error retrieving media URL: {e}")
        return None
    
    # Download the media file
    response = requests.get(media_url, headers=headers, stream=True)
    if response.status_code != 200:
        print("Error downloading media file.")
        return None
    
    ogg_file = "temp_audio.ogg"
    wav_file = "temp_audio.wav"
    
    with open(ogg_file, 'wb') as file:
        for chunk in response.iter_content(chunk_size=1024):
            file.write(chunk)
    
    # Convert OGG to WAV
    audio = AudioSegment.from_file(ogg_file, format="ogg", codec="opus")
    audio.export(wav_file, format="wav")
    
    # Transcribe audio using Sarvam AI
    api_url = "https://api.sarvam.ai/speech-to-text-translate"
    api_subscription_key = "74db471c-d82a-40b6-a67e-f9beb0a2f5c1"  # Replace with a secure key storage method
    
    mime_type = mimetypes.guess_type(wav_file)[0]
    if mime_type not in ["audio/mpeg", "audio/wave", "audio/wav", "audio/x-wav"]:
        raise ValueError(f"Unsupported file type: {mime_type}")
    
    data = {
        "model": "saaras:v2",
        "language_code": "unknown",
        "with_timestamps": "false",
        "with_diarization": "false"
    }
    
    files = {"file": (wav_file, open(wav_file, "rb"), mime_type)}
    headers = {"api-subscription-key": api_subscription_key}
    
    response = requests.post(api_url, headers=headers, data=data, files=files)
    
    if response.status_code == 200:
        return response.json().get("transcript", "")
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return None


def user_msg_to_agent(user_message):

    if not user_message:
        return "No message received. Message is required"
    
    session_id = str(uuid.uuid4())  # Generate session ID if not provided

    if session_id not in conversations:
        conversations[session_id] = {"thread_id": str(uuid.uuid4()), "history": []}

    thread_id = conversations[session_id]["thread_id"]

    # Call the agent to generate a response
    ai_response = handle_user_query(user_message, config, _printed)

    # Save to conversation history
    conversations[session_id]["history"].append({"user": user_message, "ai": ai_response})

    # Return the response as JSON
    # print({"reply": ai_response, "session_id": session_id})


    # send_whatsapp_message(str(ai_response).replace("\n", "<br>"))
    return str(ai_response)

def connect_with_glitch(phone_number = "+918688927125", glitch_url = "https://thread-verbose-booklet.glitch.me/"):
    # Create a Socket.IO client instance
    sio = socketio.Client()

    @sio.event
    def connect():
        print("Connecting to Glitch server.")

    @sio.event
    def disconnect():
        print("Disconnected from Glitch server.")

    # Listen for the "whatsapp_message" event
    @sio.on('whatsapp_message')
    def on_whatsapp_message(data):
        # Convert the received data into JSON format
        json_data = json.loads(data) if isinstance(data, str) else data
        # print("Received data in JSON format:\n\n", json_data)
        # Process the message as needed, or send a response back if required

        try:
            from_number = json_data["entry"][0]["changes"][0]["value"]["messages"][0]["from"]
        except:
            from_number = None

        
        if from_number == phone_number.replace("+", ""):
            type_of_message = json_data["entry"][0]["changes"][0]["value"]["messages"][0]["type"]

            if type_of_message == "text":
                msg_received = json_data["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"]
                
            elif type_of_message == "reaction":
                msg_received = json_data["entry"][0]["changes"][0]["value"]["messages"][0]["reaction"]["emoji"]
                selected_item_id = json_data["entry"][0]["changes"][0]["value"]["messages"][0]["reaction"]["message_id"]
                with open("history.json", "r") as f:
                    history = json.load(f)
                msg_received = history[selected_item_id]
                # print("[NIRMIT] Reaction received:", msg_received)
            
            elif type_of_message == "audio":    # Might need to change "audio" to the tag in the API response
                aud_info = json_data["entry"][0]["changes"][0]["value"]["messages"][0]["audio"]
                aud_type = aud_info['mime_type']
                aud_id = aud_info['id']
                msg_received = get_text_from_speech(aud_id, aud_type)
                
            else:
                msg_received = None
            
            
            # process message here
            agent_response = user_msg_to_agent(msg_received)

            # print("[NIRMIT] Agent response:", agent_response, "\n\n")
            
            # print("[NIRMIT] Message received:", type_of_message, msg_received)
            # # return the agent's sticker response
    
    sio.connect(glitch_url)
    print("Connected to Glitch server!")

    try:
        sio.wait()
    except KeyboardInterrupt:
        print("KeyboardInterrupt caught, stopping the loop.")
        sio.disconnect()
        return
    

def create_app():
    app = Flask(__name__)
    CORS(app)
    app.config['SECRET_KEY'] = os.urandom(24)
    socketio = SocketIO(app, cors_allowed_origins="*")

    @app.route("/process_message", methods=["POST"])
    def process_message():
        print("-----------")
        data = request.json
        user_message = data.get("message", "")
        if not user_message:
            return jsonify({"error": "Message is required"}), 400
        
        session_id = data.get("session_id", str(uuid.uuid4()))  # Generate session ID if not provided

        if session_id not in conversations:
            conversations[session_id] = {"thread_id": str(uuid.uuid4()), "history": []}

        thread_id = conversations[session_id]["thread_id"]

        # Call the agent to generate a response
        ai_response = handle_user_query(user_message, config, _printed)

        # Save to conversation history
        conversations[session_id]["history"].append({"user": user_message, "ai": ai_response})

        # Return the response as JSON
        print({"reply": ai_response, "session_id": session_id})
        # send_whatsapp_message(str(ai_response).replace("\n", "<br>"))
        return jsonify({"response": str(ai_response), "session_id": str(session_id)})

    return app, socketio


if __name__ == "__main__":
    thread = threading.Thread(target=connect_with_glitch, args=(wa_phone_number, glitch_url))
    thread.start()

    from agent_dalal import handle_user_query
    app, socketio = create_app()
    socketio.run(app, debug=False)

    thread.join(2)