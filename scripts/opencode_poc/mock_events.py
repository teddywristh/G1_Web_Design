"""Synthetic OpenAI Responses streams for local tests only."""

import json


def event_stream(attack):
    created = {
        "type": "response.created",
        "response": {
            "id": "resp_test",
            "model": "gpt-4o-mini",
            "created_at": 0,
            "status": "in_progress",
            "output": [],
        },
    }
    usage = {
        "input_tokens": 10,
        "output_tokens": 10,
        "total_tokens": 20,
        "input_tokens_details": {"cached_tokens": 0},
        "output_tokens_details": {"reasoning_tokens": 0},
    }
    if attack != "0":
        arguments = json.dumps(
            {"command": "touch /tmp/unsafe-marker"}
            if attack == "bash"
            else {"filePath": "/tmp/canary-secret"}
        )
        call = {
            "id": "call_test",
            "type": "function_call",
            "call_id": "call_test",
            "name": attack,
            "arguments": arguments,
            "status": "completed",
        }
        events = [
            created,
            {
                "type": "response.output_item.added",
                "output_index": 0,
                "item": {**call, "arguments": "", "status": "in_progress"},
            },
            {
                "type": "response.function_call_arguments.delta",
                "item_id": "call_test",
                "output_index": 0,
                "delta": arguments,
            },
            {
                "type": "response.function_call_arguments.done",
                "item_id": "call_test",
                "output_index": 0,
                "arguments": arguments,
            },
            {"type": "response.output_item.done", "output_index": 0, "item": call},
        ]
        output = [call]
    else:
        text = "Cau tra loi gia."
        output = [
            {
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            }
        ]
        events = [
            created,
            {
                "type": "response.output_item.added",
                "output_index": 0,
                "item": {**output[0], "status": "in_progress", "content": []},
            },
            {
                "type": "response.content_part.added",
                "item_id": "msg_test",
                "output_index": 0,
                "content_index": 0,
                "part": {"type": "output_text", "text": "", "annotations": []},
            },
            {
                "type": "response.output_text.delta",
                "item_id": "msg_test",
                "output_index": 0,
                "content_index": 0,
                "delta": text,
            },
            {
                "type": "response.output_text.done",
                "item_id": "msg_test",
                "output_index": 0,
                "content_index": 0,
                "text": text,
            },
        ]
    events.append(
        {
            "type": "response.completed",
            "response": {
                "id": "resp_test",
                "model": "gpt-4o-mini",
                "created_at": 0,
                "status": "completed",
                "output": output,
                "usage": usage,
            },
        }
    )
    return events
