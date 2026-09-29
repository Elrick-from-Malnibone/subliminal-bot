from aiogram.fsm.state import State, StatesGroup


class SubliminalStates(StatesGroup):
    waiting_for_topic = State()
    waiting_for_custom_text = State()
    waiting_for_custom_topic = State()
    choosing_solfeggio = State()
    choosing_binaural = State()
    choosing_voice = State()
    choosing_track = State()
    choosing_track_item = State()
    choosing_length = State()
    waiting_for_name = State()
    waiting_for_broadcast = State()