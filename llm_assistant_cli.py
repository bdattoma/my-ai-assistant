#!/usr/bin/env python3
"""
Interactive CLI for the code assistant with approval system
"""

import requests
import sys
import json
from typing import Optional

API_URL = "http://localhost:8000"


class CodeAssistantClient:
    def __init__(self, api_url: str = API_URL):
        self.api_url = api_url
        self.session_id: Optional[str] = None

    def check_server(self) -> bool:
        """Check if the server is running"""
        try:
            response = requests.get(f"{self.api_url}/", timeout=2)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def send_message_stream(self, message: str):
        """Send a message to the agent and stream the response"""
        payload = {"message": message}
        if self.session_id:
            payload["session_id"] = self.session_id

        try:
            response = requests.post(
                f"{self.api_url}/chat/stream",
                json=payload,
                stream=True,
                timeout=120
            )
            response.raise_for_status()

            ai_response_started = False

            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data = json.loads(line[6:])

                        if data['type'] == 'session_id':
                            # Store session ID for future messages
                            if not self.session_id:
                                self.session_id = data['session_id']

                        elif data['type'] == 'content':
                            # Start AI response if not already started
                            if not ai_response_started:
                                print("\n🤖 AI: ", end="", flush=True)
                                ai_response_started = True
                            # Print the content chunk
                            print(data['content'], end="", flush=True)

                        elif data['type'] == 'tool_call':
                            print(f"\n\n🔧 Using tool: {data['name']}")
                            print(f"   Arguments: {json.dumps(data['args'], indent=2)}")

                        elif data['type'] == 'approval_required':
                            # Ask user for approval
                            print(f"\n\n⚠️  APPROVAL REQUIRED ⚠️")
                            print(f"   Tool: {data['tool_name']}")
                            print(f"   Arguments:")
                            for key, value in data['args'].items():
                                if key == 'content':
                                    content_str = str(value)
                                    print(f"     {key}: (Content is {len(content_str)} characters, {content_str.count(chr(10)) + 1} lines)")
                                    print(f"\n--- File Content Preview (first 500 chars) ---")
                                    print(content_str[:500])
                                    if len(content_str) > 500:
                                        print(f"... ({len(content_str) - 500} more characters)")
                                    print(f"--- End Preview ---\n")
                                else:
                                    print(f"     {key}: {value}")

                            # Prompt user
                            print()
                            while True:
                                approval = input("   Approve this action? [y/n/v for full view]: ").strip().lower()
                                if approval in ['y', 'yes']:
                                    approved = True
                                    break
                                elif approval in ['n', 'no']:
                                    approved = False
                                    break
                                elif approval in ['v', 'view']:
                                    # Show full content
                                    content_str = str(data['args'].get('content', ''))
                                    print(f"\n--- Full File Content ({len(content_str)} chars) ---")
                                    print(content_str)
                                    print(f"--- End of File ---\n")
                                else:
                                    print("   Please enter 'y', 'n', or 'v' to view full content")

                            # Send approval to server
                            self.send_approval(data['approval_id'], approved)
                            return True

                        elif data['type'] == 'tool_executing':
                            print(f"\n   ▶ Executing {data['name']}...")

                        elif data['type'] == 'tool_result':
                            print(f"   ✓ Result: {data['content']}")

                        elif data['type'] == 'tool_rejected':
                            print(f"\n   ✗ {data['message']}")

                        elif data['type'] == 'error':
                            print(f"\n   ❌ Error: {data['content']}")

                        elif data['type'] == 'done':
                            if ai_response_started:
                                print()  # New line after response
                            return True

            return True

        except requests.exceptions.RequestException as e:
            print(f"\n❌ Error: {e}")
            return False

    def send_approval(self, approval_id: str, approved: bool):
        """Send approval decision to the server and stream the continuation"""
        try:
            response = requests.post(
                f"{self.api_url}/approve",
                json={
                    "approval_id": approval_id,
                    "approved": approved,
                    "session_id": self.session_id
                },
                stream=True,
                timeout=120
            )
            response.raise_for_status()

            ai_response_started = False

            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data = json.loads(line[6:])

                        if data['type'] == 'content':
                            if not ai_response_started:
                                print("\n🤖 AI: ", end="", flush=True)
                                ai_response_started = True
                            print(data['content'], end="", flush=True)

                        elif data['type'] == 'tool_executing':
                            print(f"\n   ▶ Executing {data['name']}...")

                        elif data['type'] == 'tool_result':
                            print(f"   ✓ Result: {data['content']}")

                        elif data['type'] == 'tool_rejected':
                            print(f"\n   ✗ {data['message']}")

                        elif data['type'] == 'error':
                            print(f"\n   ❌ Error: {data['content']}")

                        elif data['type'] == 'done':
                            if ai_response_started:
                                print()
                            return True

        except requests.exceptions.RequestException as e:
            print(f"\n❌ Error sending approval: {e}")
            return False

    def reset_session(self):
        """Reset the current session"""
        if self.session_id:
            try:
                requests.delete(f"{self.api_url}/session/{self.session_id}")
            except:
                pass
        self.session_id = None

    def get_history(self):
        """Get conversation history"""
        if not self.session_id:
            return None
        try:
            response = requests.get(f"{self.api_url}/session/{self.session_id}")
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return None


def print_banner():
    """Print welcome banner"""
    print("\n" + "="*60)
    print("  🤖 AI Code Assistant (with Approval System)")
    print("="*60)
    print("\nI can help you write, read, and manage files!")
    print("You'll be asked to approve before I write any files.")
    print("\nCommands:")
    print("  /exit or /quit  - Exit the chat")
    print("  /reset          - Start a new conversation")
    print("  /history        - Show conversation history")
    print("  /help           - Show this help message")
    print("\nExamples:")
    print("  • Create a Python file that calculates fibonacci numbers")
    print("  • Write a React component for a todo list")
    print("  • Read the contents of config.json")
    print("  • List all files in the current directory")
    print()


def main():
    client = CodeAssistantClient()

    # Check if server is running
    print("Checking server connection...")
    if not client.check_server():
        print(f"❌ Error: Cannot connect to server at {API_URL}")
        print("\nPlease start the server first:")
        print("  python agent_api_server.py")
        sys.exit(1)

    print(f"✓ Connected to server at {API_URL}")
    print_banner()

    while True:
        try:
            # Get user input
            user_input = input("💬 You: ").strip()

            if not user_input:
                continue

            # Handle commands
            if user_input.lower() in ['/exit', '/quit']:
                print("\nGoodbye! Happy coding! 👋\n")
                break

            elif user_input.lower() == '/reset':
                client.reset_session()
                print("✓ Conversation reset. Starting fresh!\n")
                continue

            elif user_input.lower() == '/history':
                history = client.get_history()
                if history:
                    print(f"\n📜 Conversation History:")
                    print(f"  Session ID: {history['session_id']}")
                    print(f"  Total messages: {history['total_messages']}\n")
                    for i, msg in enumerate(history['messages'], 1):
                        role = msg['role'].upper()
                        content = msg.get('content', '')
                        print(f"\n  [{i}] {role}:")
                        if content:
                            print(f"      {content[:100]}{'...' if len(content) > 100 else ''}")
                        if 'tool_calls' in msg and msg['tool_calls']:
                            print(f"      Tool calls: {msg['tool_calls']}")
                else:
                    print("No conversation history yet")
                continue

            elif user_input.lower() == '/help':
                print_banner()
                continue

            # Send message to agent with streaming
            client.send_message_stream(user_input)

        except KeyboardInterrupt:
            print("\n\nGoodbye! Happy coding! 👋\n")
            break
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")


if __name__ == "__main__":
    main()
