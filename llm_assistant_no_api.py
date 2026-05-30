#!/usr/bin/env python3
"""
Interactive CLI for the code assistant without API Server
Directly uses the LangGraph agent with approval system
"""

import os
import sys
import json
from typing import Optional, List, Dict, Any
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from llm_agent import build_graph
from tools.tools import all_tools, APPROVAL_REQUIRED_TOOLS
from dotenv import load_dotenv
from openai import AuthenticationError, APIConnectionError, OpenAIError

# Load environment variables from .env file
load_dotenv()
def print_connection_error(error_details):
    # ANSI colors: Red for header, Bold for labels, Reset to clear
    RED, BOLD, RESET = "\033[91m", "\033[1m", "\033[0m"
    
    print(f"\n{RED}● [SYSTEM ERROR] LLM Configuration Failed{RESET}")
    print(f"  {BOLD}Reason:{RESET}  {error_details}")
    print(f"  {BOLD}Action:{RESET}  Check your API_KEY, BASE_URL, and network connection.\n")

def create_approval_tool_node():
    def tool_node_fn(state):
        last_message = state["messages"][-1]
        if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
            return {"messages": []}

        results = []
        for tool_call in last_message.tool_calls:
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("args", {})
            tool_id = tool_call.get("id", "")

            tool = next((t for t in all_tools if t.name == tool_name), None)
            if tool is None:
                results.append(ToolMessage(
                    content=f"Error: Unknown tool '{tool_name}'",
                    tool_call_id=tool_id
                ))
                continue

            print(f"\n🔧 Using tool: {tool_name}")
            for k, v in tool_args.items():
                if k == 'content' and isinstance(v, str):
                    print(f"   {k}: ({len(v)} chars, {v.count(chr(10)) + 1} lines)")
                else:
                    print(f"   {k}: {v}")

            if tool_name in APPROVAL_REQUIRED_TOOLS:
                if not get_approval_for_tool(tool_name, tool_args):
                    results.append(ToolMessage(
                        content=f"❌ Tool '{tool_name}' execution was denied by user.",
                        tool_call_id=tool_id
                    ))
                    continue

            try:
                result_content = tool.invoke(tool_args)
                first_line = result_content.split('\n')[0][:200]
                print(f"✓ {tool_name}: {first_line}")
            except Exception as e:
                result_content = f"Error executing {tool_name}: {e}"
                print(f"✗ {tool_name}: {result_content}")

            results.append(ToolMessage(content=result_content, tool_call_id=tool_id))

        return {"messages": results}
    return tool_node_fn


def get_approval_for_tool(tool_name: str, args: dict) -> bool:
    """Ask user for approval to execute a tool"""
    print(f"\n\n⚠️  APPROVAL REQUIRED ⚠️")
    print(f"   Tool: {tool_name}")
    print(f"   Arguments:")
    
    for key, value in args.items():
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
        try:
            approval = input("   Approve this action? [y/n/v for full view]: ").strip().lower()
            if approval in ['y', 'yes']:
                return True
            elif approval in ['n', 'no']:
                return False
            elif approval in ['v', 'view']:
                # Show full content
                content_str = str(args.get('content', ''))
                print(f"\n--- Full File Content ({len(content_str)} chars) ---")
                print(content_str)
                print(f"--- End of File ---\n")
            else:
                print("   Please enter 'y', 'n', or 'v' to view full view")
        except (EOFError, KeyboardInterrupt):
            # Handle EOF or Ctrl+C by denying approval
            print("\nDenying approval due to input interruption")
            return False


def print_banner():
    """Print welcome banner"""
    print("\n" + "="*60)
    print("  🤖 AI Code Assistant (with Approval System) - No API Mode")
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
    try:
        # Build the agent graph with approval-aware tool node
        print("Initializing AI assistant...")
        app = build_graph(tool_node=create_approval_tool_node())
        
        # Initialize conversation state
        conversation_state = {
            "messages": [],
        }
        
        print(f"✓ AI Assistant initialized")
        print_banner()
        
        # Counter to prevent infinite loops
        max_iterations = 10
        iteration_count = 0
        
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
                    conversation_state = {
                        "messages": [],
                    }
                    print("✓ Conversation reset. Starting fresh!\n")
                    continue

                elif user_input.lower() == '/history':
                    if conversation_state["messages"]:
                        print(f"\n📜 Conversation History:")
                        print(f"  Total messages: {len(conversation_state['messages'])}\n")
                        for i, msg in enumerate(conversation_state["messages"], 1):
                            if hasattr(msg, 'type'):
                                role = msg.type.upper()
                            else:
                                role = getattr(msg, 'role', 'unknown').upper()
                            content = getattr(msg, 'content', str(msg))[:100]
                            print(f"  [{i}] {role}: {content}{'...' if len(getattr(msg, 'content', str(msg))) > 100 else ''}")
                    else:
                        print("No conversation history yet")
                    continue

                elif user_input.lower() == '/help':
                    print_banner()
                    continue

                # Add user message to conversation
                user_message = HumanMessage(content=user_input)
                conversation_state["messages"].append(user_message)
                
                # Reset iteration counter for new conversation
                iteration_count = 0
                
                # Process with the agent
                print("🤖 AI: ", end="", flush=True)

                try:
                    result = app.invoke(conversation_state, {"recursion_limit": 10})
                except OpenAIError as e:
                    print_connection_error(f"Generic OpenAI Error: {e}")
                    result = {"messages": [AIMessage(content="")]}
                except Exception as e:
                    print_connection_error(f"❌ An unexpected error occurred: {e}")
                    result = {"messages": [AIMessage(content="")]}

                # Update conversation state
                conversation_state = result

                # Print AI response content (last AIMessage with text)
                if isinstance(result, dict) and "messages" in result:
                    printed_ai = False
                    for msg in reversed(result["messages"]):
                        if isinstance(msg, AIMessage) and msg.content:
                            print(msg.content, end="")
                            printed_ai = True
                            break
                    if not printed_ai:
                        # Fallback: print any AI message content
                        for msg in result["messages"]:
                            if isinstance(msg, AIMessage) and msg.content:
                                print(msg.content, end="")
                                break

                print()  # New line after response
                
            except EOFError:
                print("\n\nGoodbye! Happy coding! 👋\n")
                break
            except KeyboardInterrupt:
                print("\n\nGoodbye! Happy coding! 👋\n")
                break
            except Exception as e:
                print(f"\n❌ Unexpected error: {e}")
                # Don't break on unexpected errors, continue the loop
                import traceback
                traceback.print_exc()
                
    except Exception as e:
        print(f"\n❌ Failed to initialize AI assistant: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()