"""
LangGraph Agent with LLM integration, tool support, and skills
"""

import os
from dotenv import load_dotenv
from typing import TypedDict, Annotated, Sequence, Literal
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from tools.tools import all_tools
from skills import SkillsManager

# Load environment variables from .env file
load_dotenv()


# Define the state schema
class AgentState(TypedDict):
    """State of the agent"""
    messages: Annotated[Sequence[BaseMessage], add_messages]


def create_llm():
    """Create LLM instance with custom base URL and tool binding"""
    api_key = os.getenv("OPENAI_API_KEY", "dummy-key")
    base_url = os.getenv("OPENAI_BASE_URL", "https://myurl.com/v1")
    model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

    llm = ChatOpenAI(
        api_key=api_key,
        base_url=base_url,
        model=model,
        temperature=0.7
    )

    # Bind tools to the LLM
    return llm.bind_tools(all_tools)


def should_continue(state: AgentState) -> Literal["tools", "end"]:
    """Determine if we should continue to tools or end"""
    messages = state["messages"]
    last_message = messages[-1]

    # If the LLM makes a tool call, then we route to the "tools" node
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    # Otherwise, we stop (reply to the user)
    return "end"


def call_model(state: AgentState) -> AgentState:
    """Call the LLM with skills loaded"""
    llm = create_llm()

    messages = list(state["messages"])

    # Add system message with AGENT.md if this is the first interaction
    if len(messages) == 1 or not any(isinstance(m, SystemMessage) for m in messages):
        # Load AGENT.md (always loaded at startup)
        skills_manager = SkillsManager("./skills")
        agent_skill = skills_manager.load_skill("AGENT.md")
        base_prompt = f"""You are a helpful AI coding assistant. You can help users with programming tasks.

**Important**: When you encounter a task that might benefit from specialized knowledge (e.g., database work, API development, testing), use the `list_skills` tool to see what's available, then use `load_skill` to load relevant skill files.

When writing code:
1. Ask for clarification if the request is unclear
2. Use appropriate file paths
3. Write clean, well-commented code
4. Verify your changes by reading files when appropriate

Be concise and helpful in your responses."""

        # Add AGENT.md content if it exists
        if agent_skill and not agent_skill.startswith("Error") and not agent_skill.startswith("Skill file"):
            full_prompt = f"""{base_prompt}

# Base Agent Skills (AGENT.md - Always Loaded)

{agent_skill}"""
        else:
            full_prompt = base_prompt

        system_msg = SystemMessage(content=full_prompt)
        messages = [system_msg] + messages

    # Get LLM response
    response = llm.invoke(messages)

    return {"messages": [response]}


def build_graph():
    """Build and compile the LangGraph workflow with tools and skills"""
    # Create a new graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode(all_tools))

    # Set entry point
    workflow.set_entry_point("agent")

    # Add conditional edges
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END
        }
    )

    # Add edge from tools back to agent
    workflow.add_edge("tools", "agent")

    # Compile the graph
    app = workflow.compile()

    return app


def main():
    """Run the LangGraph agent with tools and skills"""
    # Build the graph
    app = build_graph()

    # Initialize state with a user message
    initial_state = {
        "messages": [HumanMessage(content="What skills do you have loaded?")]
    }

    # Run the agent
    print("Running LangGraph Agent with Tools and Skills...\n")

    for event in app.stream(initial_state):
        for value in event.values():
            if "messages" in value:
                for message in value["messages"]:
                    if isinstance(message, AIMessage):
                        if message.content:
                            print(f"AI: {message.content}")
                        if hasattr(message, "tool_calls") and message.tool_calls:
                            for tool_call in message.tool_calls:
                                print(f"🔧 Calling tool: {tool_call['name']}")
                                print(f"   Args: {tool_call['args']}")
                    elif isinstance(message, ToolMessage):
                        print(f"✓ Tool result: {message.content}")

    print("\n" + "="*50)


if __name__ == "__main__":
    main()
