from dataclasses import dataclass
from typing import Any, Optional

from pydantic import BaseModel

from browser_use.dom.history_tree_processor.service import DOMHistoryElement
from browser_use.dom.views import DOMState
# from browser_use.agent.prompts import AgentMessagePrompt


# Pydantic
class TabInfo(BaseModel):
	"""Represents information about a browser tab"""

	page_id: int
	url: str
	title: str


@dataclass
class BrowserState(DOMState):
	url: str
	title: str
	tabs: list[TabInfo]
	screenshot: Optional[str] = None


@dataclass
class BrowserStateHistory:
	url: str
	title: str
	tabs: list[TabInfo]
	interacted_element: list[DOMHistoryElement | None] | list[None]
	screenshot: Optional[str] = None
	prompt: Optional[Any] = None

	def to_dict(self) -> dict[str, Any]:
		data = {}
		data['tabs'] = [tab.model_dump() for tab in self.tabs]
		data['screenshot'] = self.screenshot
		data['interacted_element'] = [
			el.to_dict() if el else None for el in self.interacted_element
		]
		data['url'] = self.url
		data['title'] = self.title
		data['prompt'] = self.prompt
		return data


class BrowserError(Exception):
	"""Base class for all browser errors"""
