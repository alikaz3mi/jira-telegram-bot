import json
import argparse
from pathlib import Path
from typing import Any, Dict, Tuple, Type
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource


class ArgparseConfigSettingsSource(PydanticBaseSettingsSource):
    """
    A settings source class that loads variables from command-line arguments.
    It dynamically creates arguments based on the fields defined in the Pydantic settings class.
    """

    def __init__(self, settings_cls: Type[BaseSettings]):
        super().__init__(settings_cls)
        self.args, self.unknown = self._parse_args()

    def _parse_args(self):
        parser = argparse.ArgumentParser(description="Command line arguments")
        for field_name, field in self.settings_cls.model_fields.items():
            parser.add_argument(
                f"--{field_name}",
                help=f"{field_name} setting, type= {field.annotation}",
            )
        return parser.parse_known_args()

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> Tuple[Any, str, bool]:
        field_value = getattr(self.args, field_name, None)
        return field_value, field_name, False

    def __call__(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        for field_name in self.settings_cls.model_fields:
            field_value = getattr(self.args, field_name, None)
            if field_value is not None:
                d[field_name] = field_value
        return d


class JsonConfigSettingsSource(PydanticBaseSettingsSource):
    """
    A simple settings source class that loads variables from a JSON file
    at the project's root.

    Here we happen to choose to use the `env_file_encoding` from Config
    when reading `config.json`
    """

    def get_field_value(
        self, field: FieldInfo, field_name: str
    ) -> Tuple[Any, str, bool]:
        encoding = self.config.get("env_file_encoding")
        file_content_json = json.loads(Path("config.json").read_text(encoding))
        field_value = file_content_json.get(field_name)
        return field_value, field_name, False

    def prepare_field_value(
        self, field_name: str, field: FieldInfo, value: Any, value_is_complex: bool
    ) -> Any:
        return value

    def __call__(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        json_file_path = Path("config.json")

        if json_file_path.exists():
            for field_name, field in self.settings_cls.model_fields.items():
                field_value, field_key, value_is_complex = self.get_field_value(
                    field, field_name
                )
                field_value = self.prepare_field_value(
                    field_name, field, field_value, value_is_complex
                )
                if field_value is not None:
                    d[field_key] = field_value

        return d


class CustomizedSettings(BaseSettings):
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            ArgparseConfigSettingsSource(settings_cls),
            JsonConfigSettingsSource(settings_cls),
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )
