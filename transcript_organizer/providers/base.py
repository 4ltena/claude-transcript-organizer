from abc import ABC, abstractmethod


class Provider(ABC):
    @abstractmethod
    def propose_findings(self, text: str, schema: dict) -> dict:
        ...


class MockProvider(Provider):
    def __init__(self, findings=None, fail=False):
        self._findings = findings or []
        self._fail = fail

    def propose_findings(self, text: str, schema: dict) -> dict:
        if self._fail:
            raise RuntimeError("mock failure")
        return {"findings": list(self._findings)}
