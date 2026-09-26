from pathlib import Path
from streamlit.testing.v1 import AppTest


def test_demo_app_and_disabled_live_without_key(monkeypatch):
    monkeypatch.setenv('GROQ_API_KEY','')
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=30)
    assert not app.exception
    app.button[0].click().run(timeout=30)
    assert not app.exception
    assert 'result' in app.session_state
    assert app.session_state['result']['model_calls']==0
    # An empty environment value prevents dotenv from loading a real local key.
    app.sidebar.radio[0].set_value('Live LLM').run()
    assert not app.exception
    assert app.button[0].disabled
