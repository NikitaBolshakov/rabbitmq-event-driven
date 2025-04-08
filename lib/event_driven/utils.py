from typing import Optional
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefinedType
from copy import deepcopy
from typing import Any, Type, TypeVar
from pydantic import BaseModel
from pydantic.main import create_model
from typing import Optional
from pydantic.fields import FieldInfo
from typing import Union

def check_event_key_exists(base_model: type[BaseModel], field_name: str) -> bool:
    for field_name, model_field in base_model.model_fields.items():
        if model_field.json_schema_extra.get('event_key') if model_field.json_schema_extra else False:
            return True
    return False

def all_optional_overrides(base_model: type[BaseModel]) -> dict[str, tuple[Any, Any]]:
    fields_overrides = {}

    for field_name, model_field in base_model.model_fields.items():
        original_type = model_field.annotation
        new_type = Union[original_type, None]
        fields_overrides[field_name] = (new_type, None)

    return fields_overrides

def all_except_event_key_optional_overrides(base_model: type[BaseModel]) -> dict[str, tuple[Any, Any]]:
    fields_overrides = {}
    
    
    for field_name, model_field in base_model.model_fields.items():
        is_event_key = model_field.json_schema_extra.get('event_key') if model_field.json_schema_extra else False
        if is_event_key:
            continue
        
        original_type = model_field.annotation
        

        new_type = Union[original_type, None]
        fields_overrides[field_name] = (new_type, None) 
    
    return fields_overrides

def event_key_optional_overrides(base_model: type[BaseModel]) -> dict[str, tuple[Any, Any]]:
    fields_overrides = {}

    for field_name, model_field in base_model.model_fields.items():
        is_event_key = model_field.json_schema_extra.get('event_key') if model_field.json_schema_extra else False
        if is_event_key:
            new_type = Union[model_field.annotation, None]
            fields_overrides[field_name] = (new_type, None)
    
    return fields_overrides


def is_default_type(field_type):
    return field_type in {int, float, str, bool, list, dict, tuple}

def make_field_optional(field: FieldInfo, default: Any = None) -> Any:
    new = deepcopy(field)
    if not isinstance(field.default, PydanticUndefinedType):
        new.default = field.default
    else:
        new.default = default
    return Optional[field.annotation]


BaseModelT = TypeVar('BaseModelT', bound=BaseModel)

# Make partial model decorator
def make_partial_model(cls: Type[BaseModelT]) -> Type[BaseModelT]:
    def make_partial_model_internals(model: Type[BaseModelT]) -> Type[BaseModelT]:
        return create_model(  # type: ignore
            f'Partial{model.__name__}',
            __base__=model,
            __module__=model.__module__,
            **{
            field_name: make_field_optional(field_info)
            for field_name, field_info in model.model_fields.items()
        }
        )
    return make_partial_model_internals(cls)