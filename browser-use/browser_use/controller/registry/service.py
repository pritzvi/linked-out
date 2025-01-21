import asyncio
from inspect import iscoroutinefunction, signature
from typing import Any, Callable, Optional, Type

from pydantic import BaseModel, create_model

from browser_use.browser.context import BrowserContext
from browser_use.controller.registry.views import (
	ActionModel,
	ActionRegistry,
	RegisteredAction,
)
from browser_use.telemetry.service import ProductTelemetry
from browser_use.telemetry.views import (
	ControllerRegisteredFunctionsTelemetryEvent,
	RegisteredFunction,
)


class Registry:
	"""Service for registering and managing actions"""

	def __init__(self):
		self.registry = ActionRegistry()
		self.telemetry = ProductTelemetry()

	def _create_param_model(self, function: Callable) -> Type[BaseModel]:
		"""Creates a Pydantic model from function signature"""
		sig = signature(function)
		params = {
			name: (param.annotation, ... if param.default == param.empty else param.default)
			for name, param in sig.parameters.items()
			if name != 'browser'
		}
		# TODO: make the types here work
		return create_model(
			f'{function.__name__}Params',
			__base__=ActionModel,
			**params,  # type: ignore
		)

	def action(
		self,
		description: str,
		param_model: Optional[Type[BaseModel]] = None,
		requires_browser: bool = False,
	):
		"""Decorator for registering actions"""

		def decorator(func: Callable):
			# Create param model from function if not provided
			actual_param_model = param_model or self._create_param_model(func)

			# Wrap sync functions to make them async
			if not iscoroutinefunction(func):

				async def async_wrapper(*args, **kwargs):
					return await asyncio.to_thread(func, *args, **kwargs)

				# Copy the signature and other metadata from the original function
				async_wrapper.__signature__ = signature(func)
				async_wrapper.__name__ = func.__name__
				async_wrapper.__annotations__ = func.__annotations__
				wrapped_func = async_wrapper
			else:
				wrapped_func = func

			action = RegisteredAction(
				name=func.__name__,
				description=description,
				function=wrapped_func,
				param_model=actual_param_model,
				requires_browser=requires_browser,
			)
			self.registry.actions[func.__name__] = action
			return func

		return decorator

	async def execute_action(
		self, action_name: str, params: dict, browser: Optional[BrowserContext] = None
	) -> Any:
		"""Execute a registered action"""
		if action_name not in self.registry.actions:
			raise ValueError(f'Action {action_name} not found')

		action = self.registry.actions[action_name]
		try:
			# Create the validated Pydantic model
			validated_params = action.param_model(**params)

			# Check if the first parameter is a Pydantic model
			sig = signature(action.function)
			parameters = list(sig.parameters.values())
			is_pydantic = parameters and issubclass(parameters[0].annotation, BaseModel)

			# Prepare arguments based on parameter type
			if action.requires_browser:
				if not browser:
					raise ValueError(
						f'Action {action_name} requires browser but none provided. This has to be used in combination of `requires_browser=True` when registering the action.'
					)
				if is_pydantic:
					return await action.function(validated_params, browser=browser)
				return await action.function(**validated_params.model_dump(), browser=browser)

			if is_pydantic:
				return await action.function(validated_params)
			return await action.function(**validated_params.model_dump())

		except Exception as e:
			raise RuntimeError(f'Error executing action {action_name}: {str(e)}') from e

	def create_action_model(self) -> Type[ActionModel]:
		"""Creates a Pydantic model from registered actions"""
		fields = {
			name: (Optional[action.param_model], None)
			for name, action in self.registry.actions.items()
		}

		self.telemetry.capture(
			ControllerRegisteredFunctionsTelemetryEvent(
				registered_functions=[
					RegisteredFunction(name=name, params=action.param_model.model_json_schema())
					for name, action in self.registry.actions.items()
				]
			)
		)

		return create_model('ActionModel', __base__=ActionModel, **fields)  # type:ignore

	def get_prompt_description(self) -> str:
		"""Get a description of all actions for the prompt"""
		return self.registry.get_prompt_description()
