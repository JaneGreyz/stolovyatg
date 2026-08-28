from __future__ import annotations

from aiogram.types import Message, MessageOriginChannel, MessageOriginChat


def extract_forwarded_post(message: Message) -> tuple[int | str, int] | None:
    """Определить исходный чат и ID поста из пересланного сообщения."""
    if message.forward_from_chat:
        msg_id = message.forward_from_message_id or message.message_id
        return message.forward_from_chat.id, msg_id

    origin = message.forward_origin
    if origin:
        if isinstance(origin, MessageOriginChannel):
            return origin.chat.id, origin.message_id
        if isinstance(origin, MessageOriginChat):
            return origin.chat.id, origin.message_id

    if message.sender_chat and message.forward_from_message_id:
        return message.sender_chat.id, message.forward_from_message_id

    return None
