import os
import re
from elevenlabs import ElevenLabs
import io
from pydub import AudioSegment
import requests
from all_creds import eleven_labs_api_key, zepto_login_number, anthropic_key, openai_key

os.environ["ANTHROPIC_API_KEY"] = anthropic_key
os.environ["OPENAI_API_KEY"] = openai_key
os.environ["PHONE"] = zepto_login_number

client = ElevenLabs(
    api_key=eleven_labs_api_key,
)

from langchain_core.messages.ai import AIMessage

def clean_text(text):
    # Find the last occurrence of multiple '=' characters
    match = list(re.finditer(r'=+', text))
    if match:
        last_index = match[-1].end()  # Get the position after the last '=' sequence
        return text[last_index:].strip()
    return text.strip()

import uuid

from utils import *
from tools import *
from prompts import *

from pydantic import BaseModel, Field
from typing_extensions import TypedDict
from typing import Annotated, Literal, Callable, List, Dict

from langgraph.graph import START, END
from langgraph.graph import StateGraph
# from langgraph.prebuilt import ToolNode
from langgraph.prebuilt import tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.message import AnyMessage, add_messages

from langchain_anthropic import ChatAnthropic

from langchain_core.messages import ToolMessage
# from langchain_core.runnables import RunnableLambda
# from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig

# from langchain_community.tools.tavily_search import TavilySearchResults


# ---------------- Agent Setup ----------------

llm = ChatAnthropic(model="claude-3-5-sonnet-20241022", temperature=1)

class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    user_info: str
    dialog_state: Annotated[
        list[
            Literal[
                "assistant",
                # "book_vehicle",
                # "order_food",
                "order_grocery",
                
            ]
        ],
        update_dialog_stack,
    ]

class Assistant:
    def __init__(self, runnable: Runnable):
        self.runnable = runnable

    def __call__(self, state: State, config: RunnableConfig):
        while True:
            result = self.runnable.invoke(state)

            if not result.tool_calls and (
                not result.content
                or isinstance(result.content, list)
                and not result.content[0].get("text")
            ):
                messages = state["messages"] + [("user", "Respond with a real output.")]
                state = {**state, "messages": messages}
            else:
                break
        return {"messages": result}


class CompleteOrEscalate(BaseModel):
    """A tool to mark the current task as completed and/or to escalate control of the dialog to the main assistant,
    who can re-route the dialog based on the user's needs."""

    cancel: bool = True
    reason: str

    class Config:
        json_schema_extra = {
            "example": {
                "cancel": True,
                "reason": "User changed their mind about the current task.",
            },
            "example 2": {
                "cancel": True,
                "reason": "I have fully completed the task.",
            },
            "example 3": {
                "cancel": False,
                "reason": "I need to search the user's emails or calendar for more information.",
            },
        }

# food_ordering_runnable = food_ordering_prompt | llm.bind_tools(
#     food_ordering_tools + [CompleteOrEscalate]
# )
# vehicle_booking_runnable = vehicle_booking_prompt | llm.bind_tools(
#     vehicle_booking_tools + [CompleteOrEscalate]
# )
grocery_ordering_runnable = grocery_ordering_prompt | llm.bind_tools(
    grocery_ordering_tools + [CompleteOrEscalate]
)

# # Primary Assistant
# class ToVehicleBookingAssistant(BaseModel):
#     """Transfers work to a specialized assistant to handle cab bookings and cancellations."""
#     pickup_location: str = Field(
#         description="The location where the user wants to start his journey."
#     )
#     drop_location: str = Field(
#         description="The location where the user wants to end his journey."
#     )
#     request: str = Field(
#         description="Any necessary followup questions the cab booking assistant should clarify before proceeding."
#     )

# class ToFoodOrderingAssistant(BaseModel):
#     """Transfer work to a specialized assistant to handle food ordering."""

#     item: str = Field(description="The food item the user wants to order.")

#     request: str = Field(
#         description="Any additional information or requests from the user regarding ordering the food."
#     )
    
class ToGroceryOrderingAssistant(BaseModel):
    """Transfers work to a specialized assistant to handle grocery shopping assistant"""

    # location: str = Field(
    #     description="The location where the user wants to deliver ordered groceries."
    # )
    item: str = Field(description="The grocery item the user wants to order.")
    # start_date: str = Field(description="The start date of the car rental.")
    # end_date: str = Field(description="The end date of the car rental.")
    request: str = Field(
        description="Any additional information or requests from the user regarding the grocery shopping."
    )

# The top-level assistant performs general Q&A and delegates specialized tasks to other assistants.
# The task delegation is a simple form of semantic routing / does simple intent detection
llm = ChatAnthropic(model="claude-3-5-sonnet-20240620", temperature=1)

primary_assistant_tools = []
assistant_runnable = primary_assistant_prompt | llm.bind_tools(
    primary_assistant_tools
    + [
        # ToVehicleBookingAssistant,
        # ToFoodOrderingAssistant,
        ToGroceryOrderingAssistant,
    ]
)

def create_entry_node(assistant_name: str, new_dialog_state: str) -> Callable:
    def entry_node(state: State) -> dict:
        tool_call_id = state["messages"][-1].tool_calls[0]["id"]
        return {
            "messages": [
                ToolMessage(
                    content=f"The assistant is now the {assistant_name}. Reflect on the above conversation between the host assistant and the user."
                    f" The user's intent is unsatisfied. Use the provided tools to assist the user. Remember, you are {assistant_name},"
                    " and the booking, update, other other action is not complete until after you have successfully invoked the appropriate tool."
                    " If the user changes their mind or needs help for other tasks, call the CompleteOrEscalate function to let the primary host assistant take control."
                    " Do not mention who you are - just act as the proxy for the assistant.",
                    tool_call_id=tool_call_id,
                )
            ],
            "dialog_state": new_dialog_state,
        }

    return entry_node

builder = StateGraph(State)

def user_info(state: State):
    return {"user_info": "User's name is Pavan Kalyan"}

builder.add_node("fetch_user_info", user_info)
builder.add_edge(START, "fetch_user_info")

# Shared node for exiting specialized assistants
def pop_dialog_state(state: State) -> dict:
    """Pop the dialog stack and return to the main assistant."""
    messages = []
    if state["messages"][-1].tool_calls:
        messages.append(
            ToolMessage(
                content="Resuming dialog with the host assistant. Please reflect on the past conversation and assist the user as needed.",
                tool_call_id=state["messages"][-1].tool_calls[0]["id"],
            )
        )
    return {
        "dialog_state": "pop",
        "messages": messages,
    }

# # Food Ordering Assistant
# builder.add_node(
#     "enter_food_ordering",
#     create_entry_node("Food Ordering Assistant", "food_ordering"),
# )
# builder.add_node("food_ordering", Assistant(food_ordering_runnable))
# builder.add_edge("enter_food_ordering", "food_ordering")
# builder.add_node(
#     "food_ordering_sensitive_tools",
#     create_tool_node_with_fallback(food_ordering_sensitive_tools),
# )
# builder.add_node(
#     "food_ordering_safe_tools",
#     create_tool_node_with_fallback(food_ordering_safe_tools),
# )

# def route_food_ordering(
#     state: State,
# ):
#     route = tools_condition(state)
#     if route == END:
#         return END
#     tool_calls = state["messages"][-1].tool_calls
#     did_cancel = any(tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls)
#     if did_cancel:
#         return "leave_skill"
#     safe_toolnames = [t.name for t in food_ordering_safe_tools]
#     if all(tc["name"] in safe_toolnames for tc in tool_calls):
#         return "food_ordering_safe_tools"
#     return "food_ordering_sensitive_tools"


# builder.add_edge("food_ordering_sensitive_tools", "food_ordering")
# builder.add_edge("food_ordering_safe_tools", "food_ordering")
# builder.add_conditional_edges(
#     "food_ordering",
#     route_food_ordering,
#     ["food_ordering_sensitive_tools", "food_ordering_safe_tools", "leave_skill", END],
# )
builder.add_node("leave_skill", pop_dialog_state)
builder.add_edge("leave_skill", "primary_assistant")

# # Vehicle Booking Assistant
# builder.add_node(
#     "enter_vehicle_booking",
#     create_entry_node("Vehicle Booking Assistant", "vehicle_booking"),
# )
# builder.add_node("vehicle_booking", Assistant(vehicle_booking_runnable))
# builder.add_edge("enter_vehicle_booking", "vehicle_booking")
# builder.add_node(
#     "vehicle_booking_sensitive_tools",
#     create_tool_node_with_fallback(vehicle_booking_sensitive_tools),
# )
# builder.add_node(
#     "vehicle_booking_safe_tools",
#     create_tool_node_with_fallback(vehicle_booking_safe_tools),
# )

# def route_vehicle_booking(
#     state: State,
# ):
#     route = tools_condition(state)
#     if route == END:
#         return END
#     tool_calls = state["messages"][-1].tool_calls
#     did_cancel = any(tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls)
#     if did_cancel:
#         return "leave_skill"
#     safe_toolnames = [t.name for t in vehicle_booking_safe_tools]
#     if all(tc["name"] in safe_toolnames for tc in tool_calls):
#         return "vehicle_booking_safe_tools"
#     return "vehicle_booking_sensitive_tools"


# builder.add_edge("vehicle_booking_sensitive_tools", "vehicle_booking")
# builder.add_edge("vehicle_booking_safe_tools", "vehicle_booking")
# builder.add_conditional_edges(
#     "vehicle_booking",
#     route_vehicle_booking,
#     ["vehicle_booking_sensitive_tools", "vehicle_booking_safe_tools", "leave_skill", END],
# )

# Grocery Ordering Assistant
builder.add_node(
    "enter_grocery_ordering",
    create_entry_node("Grocery Ordering Assistant", "grocery_ordering"),
)
builder.add_node("grocery_ordering", Assistant(grocery_ordering_runnable))
builder.add_edge("enter_grocery_ordering", "grocery_ordering")
builder.add_node(
    "grocery_ordering_sensitive_tools",
    create_tool_node_with_fallback(grocery_ordering_sensitive_tools),
)
builder.add_node(
    "grocery_ordering_safe_tools",
    create_tool_node_with_fallback(grocery_ordering_safe_tools),
)

def route_grocery_ordering(
    state: State,
):
    route = tools_condition(state)
    if route == END:
        return END
    tool_calls = state["messages"][-1].tool_calls
    did_cancel = any(tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls)
    if did_cancel:
        return "leave_skill"
    safe_toolnames = [t.name for t in grocery_ordering_safe_tools]
    if all(tc["name"] in safe_toolnames for tc in tool_calls):
        return "grocery_ordering_safe_tools"
    return "grocery_ordering_sensitive_tools"

builder.add_edge("grocery_ordering_sensitive_tools", "grocery_ordering")
builder.add_edge("grocery_ordering_safe_tools", "grocery_ordering")
builder.add_conditional_edges(
    "grocery_ordering",
    route_grocery_ordering,
    ["grocery_ordering_sensitive_tools", "grocery_ordering_safe_tools", "leave_skill", END],
)

# Primary assistant
builder.add_node("primary_assistant", Assistant(assistant_runnable))
builder.add_node(
    "primary_assistant_tools", create_tool_node_with_fallback(primary_assistant_tools)
)

def route_primary_assistant(
    state: State,
):
    route = tools_condition(state)
    if route == END:
        return END
    tool_calls = state["messages"][-1].tool_calls
    if tool_calls:

        # if tool_calls[0]["name"] == ToVehicleBookingAssistant.__name__:
        #     return "enter_vehicle_booking"
        # elif tool_calls[0]["name"] == ToFoodOrderingAssistant.__name__:
        #     return "enter_food_ordering"
        # elif tool_calls[0]["name"] == ToGroceryOrderingAssistant.__name__:
        #     return "enter_grocery_ordering"
        if tool_calls[0]["name"] == ToGroceryOrderingAssistant.__name__:
            return "enter_grocery_ordering"
        return "primary_assistant_tools"
    raise ValueError("Invalid route")

# The assistant can route to one of the delegated assistants,
# directly use a tool, or directly respond to the user
builder.add_conditional_edges(
    "primary_assistant",
    route_primary_assistant,
    [
        # "enter_vehicle_booking",
        # "enter_food_ordering",
        "enter_grocery_ordering",
        "primary_assistant_tools",
        END,
    ],
)
builder.add_edge("primary_assistant_tools", "primary_assistant")

# Each delegated workflow can directly respond to the user
# When the user responds, we want to return to the currently active workflow
def route_to_workflow(
    state: State,
) -> Literal[
    "primary_assistant",
    # "vehicle_booking",
    # "food_ordering",
    "grocery_ordering",
]:
    """If we are in a delegated state, route directly to the appropriate assistant."""
    dialog_state = state.get("dialog_state")
    if not dialog_state:
        return "primary_assistant"
    return dialog_state[-1]

def _print_event(event: dict, _printed: set, max_length=1500):
    current_state = event.get("dialog_state")
    if current_state:
        print("Currently in: ", current_state[-1])
    message = event.get("messages")
    if message:
        if isinstance(message, list):
            message = message[-1]
        if message.id not in _printed:
            msg_repr = message.pretty_repr(html=True)
            if len(msg_repr) > max_length:
                msg_repr = msg_repr[:max_length] + " ... (truncated)"
            print(msg_repr)
            _printed.add(message.id)
            return msg_repr
            
builder.add_conditional_edges("fetch_user_info", route_to_workflow)

# Compile graph
memory = MemorySaver()
multi_assistant_graph = builder.compile(
    checkpointer=memory,
    # Let the user approve or deny the use of sensitive tools
    interrupt_before=[
        # "update_flight_sensitive_tools",
        # "vehicle_booking_sensitive_tools",
        # "food_ordering_sensitive_tools",
        "grocery_ordering_sensitive_tools",
    ],
)
# from PIL import Image

# Image(multi_assistant_graph.get_graph(xray=True).draw_mermaid_png()).save("model.png")

import uuid


def _parse_event(event: dict, _printed: set, max_length=1500):
    # print("Event: ", event)
    current_state = event.get("dialog_state")
    if current_state:
        print("Currently in: ", current_state[-1])
    message = event.get("messages")
    if message:
        if isinstance(message, list):
            message = message[-1]
        if message.id not in _printed and isinstance(message, AIMessage):
            msg_repr = message.content
            if isinstance(message.content, list):
                msg_repr = "".join([item["text"] for item in message.content if isinstance(item, dict) and "text" in item])
            # print(msg_repr)
            # print("-"*40)

            url = "https://api.sarvam.ai/translate"

            payload = {
                "input": msg_repr,
                "source_language_code": "en-IN",
                "target_language_code": "hi-IN",
                "speaker_gender": "Male",
                "mode": "formal",
                "model": "mayura:v1",
                "enable_preprocessing": True,
                "numerals_format": "international"
            }
            headers = {"Content-Type": "application/json", "api-subscription-key": "74db471c-d82a-40b6-a67e-f9beb0a2f5c1"}

            response = requests.request("POST", url, json=payload, headers=headers)
            response = response.json()

            wa.send_text_message(response['translated_text'])
            response = client.text_to_speech.convert_as_stream(
                voice_id="JBFqnCBsd6RMkjVDRZzb",
                output_format="mp3_44100_128",
                text=response['translated_text'],
                model_id="eleven_multilingual_v2",
            )
            audio_bytes = b""
            for chunk in response:
                audio_bytes += chunk

            # Save to MP3 file
            with open("output.mp3", 'wb') as f:
                f.write(audio_bytes)
            wa.send_audio(os.path.abspath("output.mp3"))
            if len(msg_repr) > max_length:
                msg_repr = msg_repr[:max_length] + " ... (truncated)"
            return msg_repr


from anthropic import Anthropic, HUMAN_PROMPT, AI_PROMPT

# anthropic = Anthropic(api_key="my_key")
def summarize_text(text):
    """Summarizes the given text using the Claude model."""
    try:
        client = Anthropic(api_key=anthropic_key)
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            system="You are a helpful assistant. You reply as if you are giving a response to a user. Reply in first person. Address the user as 'you'. Clearly state all the options user might have.",
            max_tokens=300,
            temperature=0.5,
            messages=[
                {
                    "role": "user",
                    "content": f"Please directly summarize the response from an ai agent, don't mention anything like 'here is the summary'. Keep the URL links as is. Keep the responses consise but retain all important information for the user:\n\n{text}"
                }
            ]
        )
        return response.content[0].text
    except Exception as e:
        print(f"An error occurred: {e}")
        return None
    

def handle_user_query(question, config, _printed):
    """
    Handles a single user query and processes the AI's response.

    Args:
        question (str): The user's question.
        config (dict): Configuration containing necessary IDs and context.
        _printed (set): A set to keep track of printed events.

    Returns:
        dict: A dictionary containing the AI's response and any additional info.
    """
    if not question:
        return {"error": "No question provided."}

    # Stream the user's question to the multi-assistant graph
    events = multi_assistant_graph.stream(
        {"messages": ("user", question)}, config, stream_mode="values"
    )

    response_data = {
        "responses": [],
        "tool_invocations": []
    }

    # Process the events (AI responses)
    output = ""
    # print("Events: ", events)
    for event in events:
        cur_out = _parse_event(event, _printed)  # Collect the AI response
        output += cur_out if cur_out is not None else ""
        # _print_event(event, _printed)  # Print or log the AI response
        response_data["responses"].append(event)  # Collect responses

    # Check for tool invocation
    snapshot = multi_assistant_graph.get_state(config)

    while snapshot.next:
        # Assume tool invocation approval logic happens externally
        response_data["tool_invocations"].append(snapshot.next)

        # You can log this for debugging or send it back to the user
        result = multi_assistant_graph.invoke(None, config)

        snapshot = multi_assistant_graph.get_state(config)
    # print(output)
    # return summarize_text(output)
    
    return output


