from aiogram.fsm.state import State, StatesGroup


class OrderStates(StatesGroup):
    choosing_address = State()
    confirm_saved_profile = State()
    address_clarification = State()
    phone = State()
    order_text = State()


class ReviewStates(StatesGroup):
    waiting_comment = State()
