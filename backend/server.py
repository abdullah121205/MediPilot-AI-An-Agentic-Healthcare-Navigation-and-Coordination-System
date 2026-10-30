import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi import WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from backend.schemas import (
    ChatRequest,
    ChatResponse,
    SessionResponse,
    AppointmentRequest,
    AppointmentResponse
)

from backend.storage import (
    initialize_database,
    create_session,
    session_exists,
    save_message,
    get_session,
    save_appointment
)

from backend.agent_adapter import execute_agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="MediPilot AI Backend",
    description="Agentic Healthcare Navigation API",
    version="1.0.0",
    lifespan=lifespan
)


# Allow the frontend to connect during development.
# Restrict these origins before deployment.

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


def resolve_session(session_id):
    if session_id is None:
        return create_session()

    if not session_exists(session_id):
        raise HTTPException(
            status_code=404,
            detail="Session not found"
        )

    return session_id


async def process_chat(request: ChatRequest):
    session_id = resolve_session(request.session_id)

    session = get_session(session_id)

    history = session["messages"]

    try:
        result = await execute_agent(
            message=request.message,
            history=history,
            dry_run=request.dry_run
        )

    except Exception:
        raise HTTPException(
            status_code=502,
            detail="AI agent execution failed"
        )

    save_message(
        session_id,
        "user",
        request.message
    )

    save_message(
        session_id,
        "assistant",
        result["answer"]
    )

    return session_id, result


@app.get("/")
async def home():
    return {
        "status": "running",
        "project": "MediPilot AI",
        "module": "Member 2 Backend"
    }


# ---------------------------------
# 1. NORMAL CHAT API
# ---------------------------------

@app.post(
    "/api/chat",
    response_model=ChatResponse
)
async def chat(request: ChatRequest):

    session_id, result = await process_chat(request)

    return ChatResponse(
        session_id=session_id,
        response=result["answer"],
        trace=result["trace"]
    )


# ---------------------------------
# 2. STREAMING CHAT API
# ---------------------------------

@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):

    session_id = resolve_session(request.session_id)

    async def event_generator():

        def format_event(event, message, data=None):
            payload = {
                "session_id": session_id,
                "event": event,
                "message": message,
                "data": data or {}
            }

            return (
                f"event: {event}\n"
                f"data: {json.dumps(payload)}\n\n"
            )

        yield format_event(
            "thinking",
            "Agent request started"
        )

        session = get_session(session_id)

        try:
            result = await execute_agent(
                message=request.message,
                history=session["messages"],
                dry_run=request.dry_run
            )

            save_message(
                session_id,
                "user",
                request.message
            )

            save_message(
                session_id,
                "assistant",
                result["answer"]
            )

            # These events replay the completed
            # agent trace. They are not live tool events.

            for step in result["trace"]:

                tool_name = step.get("tool", "unknown")

                yield format_event(
                    "tool_completed",
                    f"Completed tool: {tool_name}",
                    {
                        "tool": tool_name,
                        "args": step.get("args", {})
                    }
                )

            yield format_event(
                "final_response",
                result["answer"]
            )

        except Exception:
            yield format_event(
                "error",
                "AI agent execution failed"
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


# ---------------------------------
# 3. SESSION HISTORY API
# ---------------------------------

@app.get(
    "/api/session/{session_id}",
    response_model=SessionResponse
)
async def session_history(session_id: str):

    session = get_session(session_id)

    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Session not found"
        )

    return session


# ---------------------------------
# 4. APPOINTMENT BOOKING API
# ---------------------------------

@app.post(
    "/api/appointments/book",
    response_model=AppointmentResponse
)
async def book_appointment(
    request: AppointmentRequest
):

    if not session_exists(request.session_id):
        raise HTTPException(
            status_code=404,
            detail="Session not found"
        )

    if not request.confirmed_by_user:
        raise HTTPException(
            status_code=400,
            detail="User confirmation required"
        )

    appointment_id = save_appointment(
        session_id=request.session_id,
        doctor_id=request.doctor_id,
        appointment_date=request.appointment_date,
        appointment_time=request.appointment_time
    )

    return AppointmentResponse(
        appointment_id=appointment_id,
        status="demo_confirmed",
        message=(
            "Demo appointment saved successfully. "
            "This is not a real hospital booking."
        )
    )


# ---------------------------------
# 5. WEBSOCKET CHAT API
# ---------------------------------

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):

    await websocket.accept()

    try:
        while True:

            raw_data = await websocket.receive_json()

            try:
                request = ChatRequest.model_validate(
                    raw_data
                )

                session_id = resolve_session(
                    request.session_id
                )

            except Exception as error:
                await websocket.send_json({
                    "event": "error",
                    "message": str(error)
                })
                continue

            await websocket.send_json({
                "session_id": session_id,
                "event": "thinking",
                "message": "Agent request started"
            })

            session = get_session(session_id)

            try:
                result = await execute_agent(
                    message=request.message,
                    history=session["messages"],
                    dry_run=request.dry_run
                )

                save_message(
                    session_id,
                    "user",
                    request.message
                )

                save_message(
                    session_id,
                    "assistant",
                    result["answer"]
                )

                for step in result["trace"]:

                    await websocket.send_json({
                        "session_id": session_id,
                        "event": "tool_completed",
                        "message": (
                            "Completed tool: "
                            + str(step.get("tool", "unknown"))
                        ),
                        "data": {
                            "tool": step.get("tool"),
                            "args": step.get("args", {})
                        }
                    })

                await websocket.send_json({
                    "session_id": session_id,
                    "event": "final_response",
                    "message": result["answer"]
                })

            except Exception:
                await websocket.send_json({
                    "session_id": session_id,
                    "event": "error",
                    "message": "AI agent execution failed"
                })

    except WebSocketDisconnect:
        pass
    