import asyncio
from hh_client import HHClient

class Client:
    async def _response_available(self, page, url):
        return False

class Marker:
    def __init__(self, visible):
        self.visible = visible
        self.first = self
    def or_(self, other):
        return self
    async def is_visible(self):
        return self.visible

class Page:
    def __init__(self, positive_evidence):
        self.marker = Marker(positive_evidence)
    def locator(self, selector):
        return self.marker
    def get_by_text(self, text, **kwargs):
        return self.marker

def test_absent_apply_button_does_not_prove_delivery():
    assert not asyncio.run(HHClient._response_confirmed(Client(), Page(False), 'https://hh.ru/vacancy/example'))

def test_positive_delivery_marker_confirms():
    assert asyncio.run(HHClient._response_confirmed(Client(), Page(True), 'https://hh.ru/vacancy/example'))
