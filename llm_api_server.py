"""
FastAPI server for the LangGraph LLM Agent with tool approval
"""

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, List
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage, BaseMessage
from llm_agent import build_graph, AgentState
from tools import APPROVAL_REQUIRED_TOOLS, all_tools
import uuid
import json

# Load environment variables from .env file
load_dotenv()

app = FastAPI(title="LangGraph LLM Agent API with Tools and Skills", version="1.0")

# Build the graph once at startup
agent = build_graph()

# In-memory session storage
sessions: Dict[str, AgentState] = {}

# Pending approvals storage
pending_approvals: Dict[str, Dict] = {}


class ChatRequest(BaseModel):
    """Request model for chat"""
    message: str
    session_id: Optional[str] = None


class ApprovalRequest(BaseModel):
    """Request model for tool approval"""
    approval_id: str
    approved: bool
    session_id: str


@app.get("/")
def read_root():
    """Health check endpoint"""
    return {"status": "ok", "service": "LangGraph LLM Agent with Approval"}


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Chat with the LLM agent using streaming with approval for sensitive operations.
    """
    try:
        # Get or create session
        session_id = request.session_id or str(uuid.uuid4())

        if session_id in sessions:
            # Continue existing conversation
            state = sessions[session_id]
            # Add new user message
            state["messages"].append(HumanMessage(content=request.message))
        else:
            # Initialize new conversation
            state = {
                "messages": [HumanMessage(content=request.message)]
            }

        async def generate():
            """Generate streaming response with approval mechanism"""
            # Send session ID first
            yield f"data: {json.dumps({'type': 'session_id', 'session_id': session_id})}\n\n"

            final_state = state.copy()
            ai_message_with_tool = None

            # Use astream_events for token-level streaming
            async for event in agent.astream_events(state, version="v2"):
                kind = event["event"]

                # Stream LLM tokens as they're generated
                if kind == "on_chat_model_stream":
                    content = event["data"]["chunk"].content
                    if content:
                        yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"

                # Handle tool calls
                elif kind == "on_chat_model_end":
                    message = event["data"]["output"]
                    if hasattr(message, "tool_calls") and message.tool_calls:
                        #ai_message_with_tool = message
                        for tool_call in message.tool_calls:
                            tool_name = tool_call.get('name')

                            if tool_name in APPROVAL_REQUIRED_TOOLS:
                                # Need approval - pause streaming
                                approval_id = str(uuid.uuid4())

                                # Update state with the AI message before storing
                                state_with_ai_msg = final_state.copy()
                                state_with_ai_msg["messages"] = list(final_state.get("messages", []))
                                state_with_ai_msg["messages"].append(message)

                                # Store pending approval
                                pending_approvals[approval_id] = {
                                    'session_id': session_id,
                                    'tool_call': tool_call,
                                    'state': state_with_ai_msg,
                                    'message': message
                                }

                                # Send approval request
                                yield f"data: {json.dumps({'type': 'approval_required', 'approval_id': approval_id, 'tool_name': tool_name, 'args': tool_call.get('args')})}\n\n"
                                return
                            else:
                                # Normal tool call
                                yield f"data: {json.dumps({'type': 'tool_call', 'name': tool_name, 'args': tool_call.get('args')})}\n\n"

                # Handle tool execution
                elif kind == "on_tool_end":
                    tool_output = event["data"].get("output")
                    if tool_output:
                        yield f"data: {json.dumps({'type': 'tool_result', 'content': str(tool_output)})}\n\n"

                # Capture final state
                elif kind == "on_chain_end" and event["name"] == "LangGraph":
                    final_state = event["data"]["output"]

            # Store the final state
            sessions[session_id] = final_state

            # Send done signal
            yield f"data: {json.dumps({'type': 'done', 'message_count': len(final_state.get('messages', []))})}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/approve")
async def approve_tool(request: ApprovalRequest):
    """
    Approve or reject a pending tool call and continue execution
    """
    try:
        if request.approval_id not in pending_approvals:
            raise HTTPException(status_code=404, detail="Approval request not found")

        approval_data = pending_approvals[request.approval_id]

        if approval_data['session_id'] != request.session_id:
            raise HTTPException(status_code=403, detail="Session ID mismatch")

        tool_call = approval_data['tool_call']
        current_state = approval_data['state']

        async def generate():
            """Continue execution based on approval"""
            nonlocal current_state

            if request.approved:
                # Execute the tool
                tool_name = tool_call.get('name')
                tool_args = tool_call.get('args')

                yield f"data: {json.dumps({'type': 'tool_executing', 'name': tool_name})}\n\n"

                # Find and execute the tool
                tool_func = None
                for tool in all_tools:
                    if tool.name == tool_name:
                        tool_func = tool
                        break

                if tool_func:
                    try:
                        result = tool_func.invoke(tool_args)
                        yield f"data: {json.dumps({'type': 'tool_result', 'content': result})}\n\n"

                        # The state should already have the AI message, but ensure it's there
                        messages_list = list(current_state.get("messages", []))
                        ai_message = approval_data.get('message')

                        # Check if AI message is already in the list
                        if ai_message and ai_message not in messages_list:
                            messages_list.append(ai_message)

                        # Add tool message to state
                        tool_msg = ToolMessage(
                            content=result,
                            tool_call_id=tool_call.get('id', 'unknown')
                        )
                        messages_list.append(tool_msg)

                        # Update state with new messages
                        current_state["messages"] = messages_list

                        # Continue the agent loop with streaming
                        final_output = None
                        async for event in agent.astream_events(current_state, version="v2"):
                            kind = event["event"]

                            if kind == "on_chat_model_stream":
                                content = event["data"]["chunk"].content
                                if content:
                                    yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"

                            elif kind == "on_chain_end" and event["name"] == "LangGraph":
                                final_output = event["data"]["output"]

                        # Store final state
                        if final_output:
                            current_state = final_output
                        sessions[request.session_id] = current_state

                    except Exception as e:
                        import traceback
                        error_detail = traceback.format_exc()
                        yield f"data: {json.dumps({'type': 'error', 'content': f'Tool execution failed: {str(e)}\\n{error_detail}'})}\n\n"
            else:
                # User rejected the tool call
                yield f"data: {json.dumps({'type': 'tool_rejected', 'message': 'Tool execution cancelled by user'})}\n\n"

                # Add a message indicating the rejection
                rejection_msg = AIMessage(content="I understand you don't want me to run the tool. How else can I help you?")
                current_state["messages"].append(rejection_msg)
                sessions[request.session_id] = current_state

                yield f"data: {json.dumps({'type': 'content', 'content': rejection_msg.content})}\n\n"

            # Clean up pending approval
            del pending_approvals[request.approval_id]

            yield f"data: {json.dumps({'type': 'done', 'message_count': len(current_state['messages'])})}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/session/{session_id}")
def get_session(session_id: str):
    """Get the conversation history for a session"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    state = sessions[session_id]
    messages = []
    for msg in state["messages"]:
        if isinstance(msg, HumanMessage):
            messages.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            msg_data = {"role": "assistant", "content": msg.content}
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                msg_data["tool_calls"] = msg.tool_calls
            messages.append(msg_data)
        elif isinstance(msg, SystemMessage):
            messages.append({"role": "system", "content": msg.content})
        elif isinstance(msg, ToolMessage):
            messages.append({"role": "tool", "content": msg.content})

    return {
        "session_id": session_id,
        "messages": messages,
        "total_messages": len(messages)
    }


@app.delete("/session/{session_id}")
def delete_session(session_id: str):
    """Delete a conversation session"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    del sessions[session_id]
    return {"status": "deleted", "session_id": session_id}


@app.get("/sessions")
def list_sessions():
    """List all active sessions"""
    return {
        "total": len(sessions),
        "sessions": list(sessions.keys())
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
