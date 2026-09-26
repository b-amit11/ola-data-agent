import pytest
from ola_agent.provider import GroqProvider
from ola_agent.schemas import Route


def test_live_provider_requires_key(monkeypatch):
    monkeypatch.delenv('GROQ_API_KEY',raising=False)
    with pytest.raises(ValueError,match='GROQ_API_KEY'): GroqProvider()


def test_live_adapter_structured_schema_without_network(monkeypatch):
    import langchain_groq
    captured={}
    class FakeModel:
        def __init__(self,**kwargs):captured.update(kwargs)
        def with_structured_output(self,schema,method):
            assert schema is Route and method=='json_mode'
            return self
        def invoke(self,messages):
            assert messages[0][0]=='system' and 'JSON schema' in messages[0][1]
            return Route(destination='sql',message='fixture')
    monkeypatch.setenv('GROQ_API_KEY','test-placeholder-not-a-key')
    monkeypatch.setattr(langchain_groq,'ChatGroq',FakeModel)
    provider=GroqProvider()
    assert provider.route('Count rides').destination=='sql' and provider.calls==1
    assert captured['max_retries']==0 and captured['timeout']==30
