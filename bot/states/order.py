from aiogram.fsm.state import State, StatesGroup


class OrderStates(StatesGroup):
    choosing_address = State()
    address_clarification = State()
    phone = State()
    order_text = State()
    order_amount = State()


class ReviewStates(StatesGroup):
    waiting_comment = State()
