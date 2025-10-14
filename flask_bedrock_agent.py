from flask import Flask, request, jsonify
from flask_cors import CORS
from strands import Agent, tool
from strands_tools import calculator
from strands.models import BedrockModel
import time
import threading
import json
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import traceback

# Create Flask application instance
app = Flask(__name__)

# Enable CORS for all routes
CORS(app)

# Load system prompt from file
def load_system_prompt():
    """Load the system prompt from formbuilderprompt.txt"""
    try:
        prompt_file_path = os.path.join(os.path.dirname(__file__), 'formbuilderprompt.txt')
        with open(prompt_file_path, 'r', encoding='utf-8') as file:
            return file.read().strip()
    except FileNotFoundError:
        print("Warning: formbuilderprompt.txt not found. Using default prompt.")
        return """You're a helpful AI assistant with access to several tools:
        - Calculator for mathematical operations
        - Weather information for various locations
        - Current time
        - Simple search functionality
        - Form builder for creating JSON form schemas
        
        Use these tools when appropriate to help answer user questions. Be concise and helpful."""
    except Exception as e:
        print(f"Error loading system prompt: {e}")
        return "You're a helpful AI assistant."

# Create custom tools
@tool
def get_time():
    """Get the current time"""
    import datetime
    return f"Current time is: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

@tool
def create_form():
    """Create an example form builder JSON to demonstrate the format"""
    example_form = [
        {
            "title": "Form Builder Example",
            "type": "header",
            "settings": {
                "headerType": "header",
                "color": "blue-high",
                "size": "large",
                "weight": "bold"
            }
        },
        {
            "title": "What's your name?",
            "type": "textShort",
            "required": True,
            "settings": {
                "color": "purple-low"
            }
        },
        {
            "title": "How would you rate this service?",
            "type": "radio",
            "required": True,
            "options": [
                {
                    "title": "Excellent",
                    "points": 5
                },
                {
                    "title": "Good",
                    "points": 4
                },
                {
                    "title": "Average",
                    "points": 3
                },
                {
                    "title": "Poor",
                    "points": 1,
                    "question": {
                        "type": "textLong",
                        "title": "Please explain what could be improved"
                    }
                }
            ],
            "settings": {
                "color": "teal-low"
            }
        },
        {
            "title": "Total Score",
            "type": "tally",
            "groupIds": ["ALL"]
        }
    ]
    return json.dumps(example_form, indent=2)

# Configure Bedrock model
model_id = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
model = BedrockModel(model_id=model_id)

# Load the system prompt from file
system_prompt = load_system_prompt()

# Create agent with tools
agent = Agent(
    model=model,
    tools=[get_time, create_form],
    system_prompt=system_prompt
)

def call_agent_with_timeout(user_input, timeout_seconds=30):
    """
    Call the agent with a timeout to prevent blocking
    """
    def call_agent(user_input):
        """Wrapper function to call the agent"""
        return agent(user_input)
    
    try:
        print(f"Making agent call with input: {user_input}")
        start_time = time.time()
        
        # Use ThreadPoolExecutor for cross-platform timeout
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(call_agent, user_input)
            try:
                # Wait for the result with timeout
                response = future.result(timeout=timeout_seconds)
                
                end_time = time.time()
                print(f"Agent call completed in {end_time - start_time:.2f} seconds")
                print(f"Agent response: {response}")
                
                # Extract the response text safely
                if hasattr(response, 'message') and response.message and 'content' in response.message:
                    if response.message['content'] and len(response.message['content']) > 0:
                        return {
                            "success": True,
                            "response": response.message['content'][0]['text'],
                            "execution_time": end_time - start_time
                        }
                    else:
                        return {
                            "success": False,
                            "error": "No content in response",
                            "execution_time": end_time - start_time
                        }
                else:
                    return {
                        "success": True,
                        "response": str(response),
                        "execution_time": end_time - start_time
                    }
                    
            except FuturesTimeoutError:
                error_msg = f"Agent call timed out after {timeout_seconds} seconds"
                print(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "execution_time": timeout_seconds
                }
            
    except Exception as e:
        error_msg = f"Error during agent call: {str(e)}"
        print(error_msg)
        print(f"Error type: {type(e)}")
        traceback.print_exc()
        return {
            "success": False,
            "error": error_msg,
            "execution_time": 0
        }

@app.route('/chat', methods=['POST'])
def chat():
    """Main chat endpoint for agent interaction"""
    try:
        # Get request data
        print(f"Received request for /chat endpoint :{request}")
        data = request.get_json()
        print(f"Received data: {data}")
        if not data:
            return jsonify({
                "success": False,
                "error": "No JSON data provided"
            }), 400
        
        user_input = data.get('message') or data.get('prompt') or data.get('query')
        
        if not user_input:
            return jsonify({
                "success": False,
                "error": "No message provided. Use 'message', 'prompt', or 'query' field."
            }), 400
        
        # Get timeout from request or use default
        timeout = data.get('timeout', 30)
        
        # Call agent with timeout
        result = call_agent_with_timeout(user_input, timeout)
        
        # Return result
        if result["success"]:
            return jsonify({
                "success": True,
                "response": result["response"],
                "execution_time": result["execution_time"],
                "timestamp": time.time()
            })
        else:
            return jsonify({
                "success": False,
                "error": result["error"],
                "execution_time": result["execution_time"],
                "timestamp": time.time()
            }), 500
    
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": error_msg,
            "timestamp": time.time()
        }), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "success": False,
        "error": "Endpoint not found",
        "available_endpoints": ["/", "/health", "/chat", "/tools"]
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "success": False,
        "error": "Internal server error",
        "message": str(error)
    }), 500

# Run the application
if __name__ == '__main__':
    print("Starting Bedrock Agent Flask Server...")
    print("Available endpoints:")
    print("  POST /chat - Send message to agent")
    print("\nExample usage:")
    print("curl -X POST http://localhost:5000/chat -H 'Content-Type: application/json' -d '{\"message\": \"What is 2+2?\"}'")
    print("\nStarting server on http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)