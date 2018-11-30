# -*- coding: utf-8 -*-

import asyncio
import json
import ipaddress
from unittest.mock import MagicMock, patch, call
import pytest


from foglamp.common.configuration_manager import ConfigurationManager, ConfigurationManagerSingleton, _valid_type_strings, _logger
from foglamp.common.storage_client.payload_builder import PayloadBuilder
from foglamp.common.storage_client.storage_client import StorageClientAsync
from foglamp.common.storage_client.exceptions import StorageServerError
from foglamp.common.audit_logger import AuditLogger

__author__ = "Ashwin Gopalakrishnan"
__copyright__ = "Copyright (c) 2017 OSIsoft, LLC"
__license__ = "Apache 2.0"
__version__ = "${VERSION}"


@pytest.allure.feature("unit")
@pytest.allure.story("common", "configuration_manager")
class TestConfigurationManager:
    @pytest.fixture()
    def reset_singleton(self):
        # executed before each test
        ConfigurationManagerSingleton._shared_state = {}
        yield
        ConfigurationManagerSingleton._shared_state = {}

    def test_supported_validate_type_strings(self):
        assert 12 == len(_valid_type_strings)
        assert ['IPv4', 'IPv6', 'JSON', 'URL', 'X509 certificate', 'boolean', 'enumeration', 'float', 'integer', 'password', 'script', 'string'] == _valid_type_strings

    def test_constructor_no_storage_client_defined_no_storage_client_passed(
            self, reset_singleton):
        # first time initializing ConfigurationManager without storage client
        # produces error
        with pytest.raises(TypeError) as excinfo:
            ConfigurationManager()
        assert 'Must be a valid Storage object' in str(excinfo.value)

    def test_constructor_no_storage_client_defined_storage_client_passed(
            self, reset_singleton):
        # first time initializing ConfigurationManager with storage client
        # works
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        assert hasattr(c_mgr, '_storage')
        assert isinstance(c_mgr._storage, StorageClientAsync)
        assert hasattr(c_mgr, '_registered_interests')

    def test_constructor_storage_client_defined_storage_client_passed(
            self, reset_singleton):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        # second time initializing ConfigurationManager with new storage client
        # works
        storage_client_mock2 = MagicMock(spec=StorageClientAsync)
        c_mgr2 = ConfigurationManager(storage_client_mock2)
        assert hasattr(c_mgr2, '_storage')
        # ignore new storage client
        assert isinstance(c_mgr2._storage, StorageClientAsync)
        assert hasattr(c_mgr2, '_registered_interests')

    def test_constructor_storage_client_defined_no_storage_client_passed(
            self, reset_singleton):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        # second time initializing ConfigurationManager without storage client
        # works
        c_mgr2 = ConfigurationManager()
        assert hasattr(c_mgr2, '_storage')
        assert isinstance(c_mgr2._storage, StorageClientAsync)
        assert hasattr(c_mgr2, '_registered_interests')
        assert 0 == len(c_mgr._registered_interests)

    def test_register_interest_no_category_name(self, reset_singleton):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with pytest.raises(ValueError) as excinfo:
            c_mgr.register_interest(None, 'callback')
        assert 'Failed to register interest. category_name cannot be None' in str(
            excinfo.value)

    def test_register_interest_no_callback(self, reset_singleton):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with pytest.raises(ValueError) as excinfo:
            c_mgr.register_interest('name', None)
        assert 'Failed to register interest. callback cannot be None' in str(
            excinfo.value)

    def test_register_interest(self, reset_singleton):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        c_mgr.register_interest('name', 'callback')
        assert 'callback' in c_mgr._registered_interests['name']
        assert 1 == len(c_mgr._registered_interests)

    def test_unregister_interest_no_category_name(self, reset_singleton):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with pytest.raises(ValueError) as excinfo:
            c_mgr.unregister_interest(None, 'callback')
        assert 'Failed to unregister interest. category_name cannot be None' in str(
            excinfo.value)

    def test_unregister_interest_no_callback(self, reset_singleton):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with pytest.raises(ValueError) as excinfo:
            c_mgr.unregister_interest('name', None)
        assert 'Failed to unregister interest. callback cannot be None' in str(
            excinfo.value)

    def test_unregister_interest(self, reset_singleton):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        c_mgr.register_interest('name', 'callback')
        assert 1 == len(c_mgr._registered_interests)
        c_mgr.unregister_interest('name', 'callback')
        assert len(c_mgr._registered_interests) is 0

    @pytest.mark.asyncio
    async def test__run_callbacks(self, reset_singleton):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        c_mgr.register_interest('name', 'configuration_manager_callback')
        await c_mgr._run_callbacks('name')

    @pytest.mark.asyncio
    async def test__run_callbacks_invalid_module(self, reset_singleton):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        c_mgr.register_interest('name', 'invalid')
        with patch.object(_logger, "error") as log_error:
            with pytest.raises(Exception) as excinfo:
                await c_mgr._run_callbacks('name')
            import sys
            if sys.version_info[1] >= 6:
                assert excinfo.type is ModuleNotFoundError
            else:
                assert excinfo.type is ImportError
            assert "No module named 'invalid'" == str(excinfo.value)
        assert 1 == log_error.call_count
        log_error.assert_called_once_with('Unable to import callback module %s for category_name %s', 'invalid', 'name', exc_info=True)

    @pytest.mark.asyncio
    async def test__run_callbacks_norun(self, reset_singleton):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        c_mgr.register_interest('name', 'configuration_manager_callback_norun')
        with patch.object(_logger, "error") as log_error:
            with pytest.raises(Exception) as excinfo:
                await c_mgr._run_callbacks('name')
            assert excinfo.type is AttributeError
            assert 'Callback module configuration_manager_callback_norun does not have method run' in str(
                excinfo.value)
        assert 1 == log_error.call_count
        log_error.assert_called_once_with('Callback module %s does not have method run', 'configuration_manager_callback_norun', exc_info=True)

    @pytest.mark.asyncio
    async def test__run_callbacks_nonasync(self, reset_singleton):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        c_mgr.register_interest(
            'name', 'configuration_manager_callback_nonasync')
        with patch.object(_logger, "error") as log_error:
            with pytest.raises(Exception) as excinfo:
                await c_mgr._run_callbacks('name')
            assert excinfo.type is AttributeError
            assert 'Callback module configuration_manager_callback_nonasync run method must be a coroutine function' in str(
                excinfo.value)
        assert 1 == log_error.call_count
        log_error.assert_called_once_with('Callback module %s run method must be a coroutine function', 'configuration_manager_callback_nonasync', exc_info=True)

    @pytest.mark.asyncio
    async def test__validate_category_val_valid_config_use_default_val(self, reset_singleton):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        test_config = {
            "test_item_name": {
                "description": "test description val",
                "type": "string",
                "default": "test default val"
            },
        }
        c_return_value = await c_mgr._validate_category_val(category_val=test_config, set_value_val_from_default_val=True)
        assert isinstance(c_return_value, dict)
        assert len(c_return_value) is 1
        test_item_val = c_return_value.get("test_item_name")
        assert isinstance(test_item_val, dict)
        assert len(test_item_val) is 4
        assert test_item_val.get("description") is "test description val"
        assert test_item_val.get("type") is "string"
        assert test_item_val.get("default") is "test default val"
        assert test_item_val.get("value") is "test default val"

        # deep copy check to make sure test_config wasn't modified in the
        # method call
        assert test_config is not c_return_value
        assert isinstance(test_config, dict)
        assert len(test_config) is 1
        test_item_val = test_config.get("test_item_name")
        assert isinstance(test_item_val, dict)
        assert len(test_item_val) is 3
        assert test_item_val.get("description") is "test description val"
        assert test_item_val.get("type") is "string"
        assert test_item_val.get("default") is "test default val"

    @pytest.mark.asyncio
    async def test__validate_category_val_invalid_config_use_default_val(self):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        test_config = {
            "test_item_name": {
                "description": "test description val",
                "type": "IPv4",
                "default": "test default val",
                "displayName": "{}"
            },
        }

        with pytest.raises(Exception) as excinfo:
            await c_mgr._validate_category_val(category_val=test_config, set_value_val_from_default_val=True)
        assert excinfo.type is ValueError
        assert "Unrecognized value for item_name test_item_name" == str(excinfo.value)

    @pytest.mark.asyncio
    async def test__validate_category_val_valid_config_use_value_val(self, reset_singleton):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        test_config = {
            "test_item_name": {
                "description": "test description val",
                "type": "string",
                "default": "test default val",
                "value": "test value val"
            },
        }
        c_return_value = await c_mgr._validate_category_val(category_val=test_config, set_value_val_from_default_val=False)
        assert isinstance(c_return_value, dict)
        assert len(c_return_value) is 1
        test_item_val = c_return_value.get("test_item_name")
        assert isinstance(test_item_val, dict)
        assert len(test_item_val) is 4
        assert test_item_val.get("description") is "test description val"
        assert test_item_val.get("type") is "string"
        assert test_item_val.get("default") is "test default val"
        assert test_item_val.get("value") is "test value val"
        # deep copy check to make sure test_config wasn't modified in the
        # method call
        assert test_config is not c_return_value
        assert isinstance(test_config, dict)
        assert len(test_config) is 1
        test_item_val = test_config.get("test_item_name")
        assert isinstance(test_item_val, dict)
        assert len(test_item_val) is 4
        assert test_item_val.get("description") is "test description val"
        assert test_item_val.get("type") is "string"
        assert test_item_val.get("default") is "test default val"
        assert test_item_val.get("value") is "test value val"

    @pytest.mark.asyncio
    async def test__validate_category_optional_attributes_and_use_value(self, reset_singleton):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        test_config = {
            "test_item_name": {
                "description": "test description val",
                "type": "string",
                "default": "test default val",
                "value": "test value val",
                "readonly": "false",
                "length": "100"
            },
        }
        c_return_value = await c_mgr._validate_category_val(category_val=test_config, set_value_val_from_default_val=False)
        assert isinstance(c_return_value, dict)
        assert len(c_return_value) is 1
        test_item_val = c_return_value.get("test_item_name")
        assert isinstance(test_item_val, dict)
        assert 6 == len(test_item_val) is 6
        assert "test description val" == test_item_val.get("description")
        assert "string" == test_item_val.get("type")
        assert "test default val" == test_item_val.get("default")
        assert "test value val" == test_item_val.get("value")
        assert "false" == test_item_val.get("readonly")
        assert "100" == test_item_val.get("length")

        # deep copy check to make sure test_config wasn't modified in the
        # method call
        assert test_config is not c_return_value
        assert isinstance(test_config, dict)
        assert len(test_config) is 1
        test_item_val = test_config.get("test_item_name")
        assert isinstance(test_item_val, dict)
        assert 6 == len(test_item_val) is 6
        assert "test description val" == test_item_val.get("description")
        assert "string" == test_item_val.get("type")
        assert "test default val" == test_item_val.get("default")
        assert "test value val" == test_item_val.get("value")
        assert "false" == test_item_val.get("readonly")
        assert "100" == test_item_val.get("length")

    @pytest.mark.asyncio
    async def test__validate_category_optional_attributes_and_use_default_val(self, reset_singleton):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        test_config = {
            "test_item_name": {
                "description": "test description val",
                "type": "string",
                "default": "test default val",
                "readonly": "false",
                "length": "100"
            },
        }
        c_return_value = await c_mgr._validate_category_val(category_val=test_config, set_value_val_from_default_val=True)
        assert isinstance(c_return_value, dict)
        assert 1 == len(c_return_value)
        test_item_val = c_return_value.get("test_item_name")
        assert isinstance(test_item_val, dict)
        assert 6 == len(test_item_val)
        assert "test description val" == test_item_val.get("description")
        assert "string" == test_item_val.get("type")
        assert "test default val" == test_item_val.get("default")
        assert "test default val" == test_item_val.get("value")
        assert "false" == test_item_val.get("readonly")
        assert "100" == test_item_val.get("length")

        # deep copy check to make sure test_config wasn't modified in the
        # method call
        assert test_config is not c_return_value
        assert isinstance(test_config, dict)
        assert 1 == len(test_config)
        test_item_val = test_config.get("test_item_name")
        assert isinstance(test_item_val, dict)
        assert 5 == len(test_item_val)
        assert "test description val" == test_item_val.get("description")
        assert "string" == test_item_val.get("type")
        assert "test default val" == test_item_val.get("default")
        assert "false" == test_item_val.get("readonly")
        assert "100" == test_item_val.get("length")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("config, item_name, message", [
        ({
             "test_item_name": {
                 "description": "test description val",
                 "type": "string",
                 "default": "test default val",
                 "readonly": "unexpected",
             },
         }, "readonly", "boolean"),
        ({
             "test_item_name": {
                 "description": "test description val",
                 "type": "string",
                 "default": "test default val",
                 "order": "unexpected",
             },
         }, "order", "an integer"),
        ({
             "test_item_name": {
                 "description": "test description val",
                 "type": "string",
                 "default": "test default val",
                 "length": "unexpected",
             },
         }, "length", "an integer"),
        ({
             "test_item_name": {
                 "description": "test description val",
                 "type": "float",
                 "default": "test default val",
                 "minimum": "unexpected",
             },
         }, "minimum", "an integer or float"),
        ({
             "test_item_name": {
                 "description": "test description val",
                 "type": "integer",
                 "default": "test default val",
                 "maximum": "unexpected",
             },
         }, "maximum", "an integer or float")
    ])
    async def test__validate_category_val_optional_attributes_unrecognized_entry_name(self, config, item_name, message):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with pytest.raises(Exception) as excinfo:
            await c_mgr._validate_category_val(category_val=config, set_value_val_from_default_val=True)
        assert excinfo.type is ValueError
        assert "Entry value must be {} for item name {}".format(message, item_name) == str(excinfo.value)

    @pytest.mark.asyncio
    async def test__validate_category_val_config_without_value_use_value_val(self):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        test_config = {
            "test_item_name": {
                "description": "test description val",
                "type": "string",
                "default": "test default val",
            },
        }
        with pytest.raises(ValueError) as excinfo:
            await c_mgr._validate_category_val(category_val=test_config, set_value_val_from_default_val=False)
        assert 'Missing entry_name value for item_name test_item_name' in str(
            excinfo.value)

    @pytest.mark.asyncio
    async def test__validate_category_val_config_not_dictionary(self):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        test_config = ()
        with pytest.raises(TypeError) as excinfo:
            await c_mgr._validate_category_val(category_val=test_config, set_value_val_from_default_val=False)
        assert 'category_val must be a dictionary' in str(excinfo.value)

    @pytest.mark.asyncio
    async def test__validate_category_val_item_name_not_string(self):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        test_config = {
            5: {
                "description": "test description val",
                "type": "string",
                "default": "test default val",
            },
        }
        with pytest.raises(TypeError) as excinfo:
            await c_mgr._validate_category_val(category_val=test_config, set_value_val_from_default_val=False)
        assert 'item_name must be a string' in str(excinfo.value)

    @pytest.mark.asyncio
    async def test__validate_category_val_item_value_not_dictionary(self):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        test_config = {
            "test_item_name": ()
        }
        with pytest.raises(TypeError) as excinfo:
            await c_mgr._validate_category_val(category_val=test_config, set_value_val_from_default_val=False)
        assert 'item_value must be a dict for item_name test_item_name' in str(
            excinfo.value)

    @pytest.mark.asyncio
    async def test__validate_category_val_config_entry_name_not_string(self):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        test_config = {
            "test_item_name": {
                "description": "test description val",
                "type": "string",
                "default": "test default val",
                5: "bla"
            },
        }
        with pytest.raises(TypeError) as excinfo:
            await c_mgr._validate_category_val(category_val=test_config, set_value_val_from_default_val=False)
        assert 'entry_name must be a string for item_name test_item_name' in str(
            excinfo.value)

    @pytest.mark.asyncio
    async def test__validate_category_val_config_entry_val_not_string(self):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        test_config = {
            "test_item_name": {
                "description": "test description val",
                "type": "string",
                "default": "test default val",
                "something": 5
            },
        }
        with pytest.raises(TypeError) as excinfo:
            await c_mgr._validate_category_val(category_val=test_config, set_value_val_from_default_val=False)
        assert 'entry_val must be a string for item_name test_item_name and entry_name something' in str(
            excinfo.value)

    @pytest.mark.asyncio
    async def test__validate_category_val_config_unrecognized_entry_name(self):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        test_config = {
            "test_item_name": {
                "description": "test description val",
                "type": "string",
                "default": "test default val",
                "unrecognized": "unexpected",
            },
        }
        with pytest.raises(ValueError) as excinfo:
            await c_mgr._validate_category_val(category_val=test_config, set_value_val_from_default_val=True)
        assert 'Unrecognized entry_name unrecognized for item_name test_item_name' in str(
            excinfo.value)

    @pytest.mark.parametrize("config, exception_name, exception_msg", [
        ({"description": "test description", "type": "enumeration", "default": "A"},
         KeyError, "'options required for enumeration type'"),
        ({"description": "test description", "type": "enumeration", "default": "A", "options": ""},
         TypeError, "entry_val must be a list for item_name test_item_name and entry_name options"),
        ({"description": "test description", "type": "enumeration", "default": "A", "options": []},
         ValueError, "entry_val cannot be empty list for item_name test_item_name and entry_name options"),
        ({"description": "test description", "type": "enumeration", "default": "C", "options": ["A", "B"]},
         ValueError, "entry_val does not exist in options list for item_name test_item_name and entry_name options"),
        ({"description": 1, "type": "enumeration", "default": "A", "options": ["A", "B"]},
         TypeError, "entry_val must be a string for item_name test_item_name and entry_name description")
    ])
    @pytest.mark.asyncio
    async def test__validate_category_val_enum_type_bad(self, config, exception_name, exception_msg):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        test_config = {"test_item_name": config}
        with pytest.raises(Exception) as excinfo:
            await c_mgr._validate_category_val(category_val=test_config, set_value_val_from_default_val=False)
        assert excinfo.type is exception_name
        assert exception_msg == str(excinfo.value)

    @pytest.mark.asyncio
    async def test__validate_category_val_with_enum_type(self, reset_singleton):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        test_config = {
            "test_item_name": {
                "description": "test description val",
                "type": "enumeration",
                "default": "A",
                "options": ["A", "B", "C"]
            }
        }
        c_return_value = await c_mgr._validate_category_val(category_val=test_config, set_value_val_from_default_val=True)
        assert isinstance(c_return_value, dict)
        assert 1 == len(c_return_value)
        test_item_val = c_return_value.get("test_item_name")
        assert isinstance(test_item_val, dict)
        assert 5 == len(test_item_val)
        assert "test description val" == test_item_val.get("description")
        assert "enumeration" == test_item_val.get("type")
        assert "A" == test_item_val.get("default")
        assert "A" == test_item_val.get("value")

        # deep copy check to make sure test_config wasn't modified in the
        # method call
        assert test_config is not c_return_value
        assert isinstance(test_config, dict)
        assert 1 == len(test_config)
        test_item_val = test_config.get("test_item_name")
        assert isinstance(test_item_val, dict)
        assert 4 == len(test_item_val)
        assert "test description val" == test_item_val.get("description")
        assert "enumeration" == test_item_val.get("type")
        assert "A" == test_item_val.get("default")

    @pytest.mark.parametrize("test_input, test_value, clean_value", [
        ("boolean", "false", "false"),
        ("integer", "123", "123"),
        ("string", "blah", "blah"),
        ("IPv4", "127.0.0.1", "127.0.0.1"),
        ("IPv6", "2001:db8::", "2001:db8::"),
        ("password", "not implemented", "not implemented"),
        ("X509 certificate", "not implemented", "not implemented"),
        ("JSON", "{\"foo\": \"bar\"}", '{"foo": "bar"}')
    ])
    @pytest.mark.asyncio
    async def test__validate_category_val_valid_type(self, reset_singleton, test_input, test_value, clean_value):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        test_config = {
            "test_item_name": {
                "description": "test description val",
                "type": test_input,
                "default": test_value,
            },
        }
        c_return_value = await c_mgr._validate_category_val(category_val=test_config, set_value_val_from_default_val=True)
        assert c_return_value["test_item_name"]["type"] == test_input
        assert c_return_value["test_item_name"]["value"] == clean_value

    @pytest.mark.asyncio
    async def test__validate_category_val_invalid_type(self, reset_singleton):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        test_config = {
            "test_item_name": {
                "description": "test description val",
                "type": "blablabla",
                "default": "test default val",
            },
        }
        with pytest.raises(ValueError) as excinfo:
            await c_mgr._validate_category_val(category_val=test_config, set_value_val_from_default_val=True)
        assert 'Invalid entry_val for entry_name "type" for item_name test_item_name. valid: {}'.format(
            _valid_type_strings) in str(excinfo.value)

    @pytest.mark.parametrize("test_input", ["type", "description", "default"])
    @pytest.mark.asyncio
    async def test__validate_category_val_missing_entry(self, reset_singleton, test_input):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        test_config = {
            "test_item_name": {
                "description": "test description val",
                "type": "string",
                "default": "test default val",
            },
        }
        del test_config['test_item_name'][test_input]
        with pytest.raises(ValueError) as excinfo:
            await c_mgr._validate_category_val(category_val=test_config, set_value_val_from_default_val=True)
        assert 'Missing entry_name {} for item_name {}'.format(
            test_input, "test_item_name") in str(excinfo.value)

    @pytest.mark.asyncio
    async def test__validate_category_val_config_without_default_notuse_value_val(self, reset_singleton):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        test_config = {
            "test_item_name": {
                "description": "test description val",
                "type": "string",
            },
        }
        with pytest.raises(ValueError) as excinfo:
            await c_mgr._validate_category_val(category_val=test_config, set_value_val_from_default_val=True)
        assert 'Missing entry_name default for item_name test_item_name' in str(
            excinfo.value)

    @pytest.mark.asyncio
    async def test__validate_category_val_config_with_default_andvalue_val_notuse_value_val(self, reset_singleton):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        test_config = {
            "test_item_name": {
                "description": "test description val",
                "type": "string",
                "default": "test default val",
                "value": "test value val"
            },
        }
        with pytest.raises(ValueError) as excinfo:
            await c_mgr._validate_category_val(category_val=test_config, set_value_val_from_default_val=True)
        assert 'Specifying value_name and value_val for item_name test_item_name is not allowed if desired behavior is to use default_val as value_val' in str(
            excinfo.value)

    @pytest.mark.asyncio
    async def test__merge_category_vals_same_items_different_values(self, reset_singleton, mocker):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        test_config_new = {
            "test_item_name": {
                "description": "test description val",
                "type": "string",
                "default": "test default val",
                "value": "test value val"
            },
        }
        test_config_storage = {
            "test_item_name": {
                "description": "test description val storage",
                "type": "string",
                "default": "test default val storage",
                "value": "test value val storage"
            },
        }

        mocker.patch.object(AuditLogger, '__init__', return_value=None)
        mocker.patch.object(AuditLogger, 'information', return_value=asyncio.sleep(.1))

        c_return_value = await c_mgr._merge_category_vals(test_config_new, test_config_storage, keep_original_items=True, category_name='test')
        assert isinstance(c_return_value, dict)
        assert len(c_return_value) is 1
        test_item_val = c_return_value.get("test_item_name")
        assert isinstance(test_item_val, dict)
        assert len(test_item_val) is 4
        assert test_item_val.get("description") is "test description val"
        assert test_item_val.get("type") is "string"
        assert test_item_val.get("default") is "test default val"
        # use value val from storage
        assert test_item_val.get("value") is "test value val storage"
        # return new dictionary, do not modify parameters passed in
        assert test_config_new is not c_return_value
        assert test_config_storage is not c_return_value
        assert test_config_new is not test_config_storage

    @pytest.mark.asyncio
    async def test__merge_category_vals_deprecated(self, reset_singleton, mocker):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        test_config_new = {
            "test_item_name1": {
                "description": "test description val storage1",
                "type": "string",
                "default": "test default val storage1",
                "value": "test value val storage1",
                "deprecated": "true"
            },
            "test_item_name2": {
                "description": "test description val2",
                "type": "string",
                "default": "test default val2",
                "value": "test value val2"
            },
        }
        test_config_storage = {
            "test_item_name1": {
                "description": "test description val storage1",
                "type": "string",
                "default": "test default val storage1",
                "value": "test value val storage1"
            },
            "test_item_name2": {
                "description": "test description val storage2",
                "type": "string",
                "default": "test default val storage2",
                "value": "test value val storage2"
            },
        }
        expected_new_value = {
            "test_item_name2": {
                "description": "test description val2",
                "type": "string",
                "default": "test default val2",
                "value": "test value val storage2"
            },
        }
        mocker.patch.object(AuditLogger, '__init__', return_value=None)
        mocker.patch.object(AuditLogger, 'information', return_value=asyncio.sleep(.1))

        c_return_value = await c_mgr._merge_category_vals(test_config_new, test_config_storage, keep_original_items=True, category_name='test')
        assert expected_new_value == c_return_value

    @pytest.mark.asyncio
    async def test__merge_category_vals_no_mutual_items_ignore_original(self, reset_singleton, mocker):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        test_config_new = {
            "test_item_name": {
                "description": "test description val",
                "type": "string",
                "default": "test default val",
                "value": "test value val"
            },
        }
        test_config_storage = {
            "test_item_name_storage": {
                "description": "test description val storage",
                "type": "string",
                "default": "test default val storage",
                "value": "test value val storage"
            },
        }

        mocker.patch.object(AuditLogger, '__init__', return_value=None)
        mocker.patch.object(AuditLogger, 'information', return_value=asyncio.sleep(.1))

        c_return_value = await c_mgr._merge_category_vals(test_config_new, test_config_storage, keep_original_items=False, category_name='test')
        assert isinstance(c_return_value, dict)
        # ignore "test_item_name_storage" and include "test_item_name"
        assert len(c_return_value) is 1
        test_item_val = c_return_value.get("test_item_name")
        assert isinstance(test_item_val, dict)
        assert len(test_item_val) is 4
        assert test_item_val.get("description") is "test description val"
        assert test_item_val.get("type") is "string"
        assert test_item_val.get("default") is "test default val"
        assert test_item_val.get("value") is "test value val"
        assert test_config_new is not c_return_value
        assert test_config_storage is not c_return_value
        assert test_config_new is not test_config_storage

    @pytest.mark.asyncio
    async def test__merge_category_vals_no_mutual_items_include_original(self, reset_singleton, mocker):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        test_config_new = {
            "test_item_name": {
                "description": "test description val",
                "type": "string",
                "default": "test default val",
                "value": "test value val"
            },
        }
        test_config_storage = {
            "test_item_name_storage": {
                "description": "test description val storage",
                "type": "string",
                "default": "test default val storage",
                "value": "test value val storage"
            },
        }

        mocker.patch.object(AuditLogger, '__init__', return_value=None)
        mocker.patch.object(AuditLogger, 'information', return_value=asyncio.sleep(.1))

        c_return_value = await c_mgr._merge_category_vals(test_config_new, test_config_storage, keep_original_items=True, category_name='test')
        assert isinstance(c_return_value, dict)
        # include "test_item_name_storage" and "test_item_name"
        assert len(c_return_value) is 2
        test_item_val = c_return_value.get("test_item_name")
        assert isinstance(test_item_val, dict)
        assert len(test_item_val) is 4
        assert test_item_val.get("description") is "test description val"
        assert test_item_val.get("type") is "string"
        assert test_item_val.get("default") is "test default val"
        assert test_item_val.get("value") is "test value val"
        test_item_val = c_return_value.get("test_item_name_storage")
        assert isinstance(test_item_val, dict)
        assert len(test_item_val) is 4
        assert test_item_val.get(
            "description") is "test description val storage"
        assert test_item_val.get("type") is "string"
        assert test_item_val.get("default") is "test default val storage"
        assert test_item_val.get("value") is "test value val storage"
        assert test_config_new is not c_return_value
        assert test_config_storage is not c_return_value
        assert test_config_new is not test_config_storage

    @pytest.mark.asyncio
    async def test_create_category_good_newval_bad_storageval_good_update(self, reset_singleton):

        async def async_mock(return_value):
            return return_value

        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with patch.object(_logger, 'exception') as log_exc:
            with patch.object(ConfigurationManager, '_validate_category_val', side_effect=[async_mock({}), Exception()]) as valpatch:
                with patch.object(ConfigurationManager, '_read_category_val', return_value=async_mock({})) as readpatch:
                    with patch.object(ConfigurationManager, '_merge_category_vals') as mergepatch:
                        with patch.object(ConfigurationManager, '_run_callbacks', return_value=async_mock(None)) as callbackpatch:
                            cat = await c_mgr.create_category('catname', 'catvalue', 'catdesc')
                            assert cat is None
                        callbackpatch.assert_called_once_with('catname')
                    mergepatch.assert_not_called()
                readpatch.assert_called_once_with('catname')
            valpatch.assert_has_calls([call('catvalue', True), call({}, False)])
        assert 1 == log_exc.call_count
        log_exc.assert_called_once_with('category_value for category_name %s from storage is corrupted; using category_value without merge', 'catname')

    @pytest.mark.asyncio
    async def test_create_category_good_newval_bad_storageval_bad_update(self, reset_singleton):

        async def async_mock(return_value):
            return return_value

        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with patch.object(_logger, 'exception') as log_exc:
            with patch.object(ConfigurationManager, '_validate_category_val', side_effect=[async_mock({}), Exception()]) as valpatch:
                with patch.object(ConfigurationManager, '_read_category_val', return_value=async_mock({})) as readpatch:
                    with patch.object(ConfigurationManager, '_merge_category_vals') as mergepatch:
                        with patch.object(ConfigurationManager, '_run_callbacks') as callbackpatch:
                            with pytest.raises(Exception) as excinfo:
                                await c_mgr.create_category('catname', 'catvalue', 'catdesc')
                            assert excinfo.type is TypeError
                        callbackpatch.assert_called_once_with('catname')
                    mergepatch.assert_not_called()
                readpatch.assert_called_once_with('catname')
            valpatch.assert_has_calls([call('catvalue', True), call({}, False)])
        assert 2 == log_exc.call_count
        calls = [call('category_value for category_name %s from storage is corrupted; using category_value without merge', 'catname'),
                 call('Unable to create new category based on category_name %s and category_description %s and category_json_schema %s', 'catname', 'catdesc')]
        assert log_exc.has_calls(calls, any_order=True)

    # (merged_value)
    @pytest.mark.asyncio
    async def test_create_category_good_newval_good_storageval_nochange(self, reset_singleton):

        async def async_mock(return_value):
            return return_value

        all_cat_names = [('rest_api', 'FogLAMP Admin and User REST API', 'rest_api'), ('catname', 'catdesc', 'catname')]
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with patch.object(ConfigurationManager, '_validate_category_val', side_effect=[async_mock({}), async_mock({})]) as valpatch:
            with patch.object(ConfigurationManager, '_read_category_val', return_value=async_mock({})) as readpatch:
                with patch.object(ConfigurationManager, '_read_all_category_names', return_value=async_mock(all_cat_names)) as read_all_patch:
                    with patch.object(ConfigurationManager, '_merge_category_vals', return_value=async_mock({})) as mergepatch:
                        with patch.object(ConfigurationManager, '_run_callbacks') as callbackpatch:
                            with patch.object(ConfigurationManager, '_update_category') as updatepatch:
                                cat = await c_mgr.create_category('catname', 'catvalue', 'catdesc')
                                assert cat is None
                            updatepatch.assert_not_called()
                        callbackpatch.assert_not_called()
                    mergepatch.assert_called_once_with({}, {}, False, 'catname')
                read_all_patch.assert_called_once_with()
            readpatch.assert_called_once_with('catname')
        valpatch.assert_has_calls([call('catvalue', True), call({}, False)])

    @pytest.mark.asyncio
    async def test_create_category_good_newval_good_storageval_good_update(self, reset_singleton):

        async def async_mock(return_value):
            return return_value

        all_cat_names = [('rest_api', 'FogLAMP Admin and User REST API', 'rest_api'), ('catname', 'catdesc', 'catname')]
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with patch.object(ConfigurationManager, '_validate_category_val', side_effect=[async_mock({}), async_mock({})]) as valpatch:
            with patch.object(ConfigurationManager, '_read_category_val', return_value=async_mock({})) as readpatch:
                with patch.object(ConfigurationManager, '_read_all_category_names', return_value=async_mock(all_cat_names)) as read_all_patch:
                    with patch.object(ConfigurationManager, '_merge_category_vals', return_value=async_mock({'bla': 'bla'})) as mergepatch:
                        with patch.object(ConfigurationManager, '_run_callbacks', return_value=async_mock(None)) as callbackpatch:
                            with patch.object(ConfigurationManager, '_update_category', return_value=async_mock(None)) as updatepatch:
                                cat = await c_mgr.create_category('catname', 'catvalue', 'catdesc')
                                assert cat is None
                            updatepatch.assert_called_once_with('catname', {'bla': 'bla'}, 'catdesc', 'catname')
                        callbackpatch.assert_called_once_with('catname')
                    mergepatch.assert_called_once_with({}, {}, False, 'catname')
                read_all_patch.assert_called_once_with()
            readpatch.assert_called_once_with('catname')
        valpatch.assert_has_calls([call('catvalue', True), call({}, False)])

    @pytest.mark.asyncio
    async def test_create_category_good_newval_good_storageval_bad_update(self, reset_singleton):

        async def async_mock(return_value):
            return return_value

        all_cat_names = [('rest_api', 'FogLAMP Admin and User REST API', 'rest_api'), ('catname', 'catdesc', 'catname')]
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with patch.object(_logger, 'exception') as log_exc:
            with patch.object(ConfigurationManager, '_validate_category_val', side_effect=[async_mock({}), async_mock({})]) as valpatch:
                with patch.object(ConfigurationManager, '_read_category_val', return_value=async_mock({})) as readpatch:
                    with patch.object(ConfigurationManager, '_read_all_category_names', return_value=async_mock(all_cat_names)) as read_all_patch:
                        with patch.object(ConfigurationManager, '_merge_category_vals', return_value=async_mock({'bla': 'bla'})) as mergepatch:
                            with patch.object(ConfigurationManager, '_run_callbacks') as callbackpatch:
                                with pytest.raises(Exception) as excinfo:
                                    await c_mgr.create_category('catname', 'catvalue', 'catdesc')
                                assert excinfo.type is TypeError
                            callbackpatch.assert_not_called()
                        mergepatch.assert_called_once_with({}, {}, False, 'catname')
                    read_all_patch.assert_called_once_with()
                readpatch.assert_called_once_with('catname')
            valpatch.assert_has_calls([call('catvalue', True), call({}, False)])
        assert 1 == log_exc.call_count
        log_exc.assert_called_once_with('Unable to create new category based on category_name %s and category_description %s '
                                        'and category_json_schema %s', 'catname', 'catdesc', {'bla': 'bla'})

    @pytest.mark.asyncio
    async def test_create_category_good_newval_no_storageval_good_create(self, reset_singleton):

        async def async_mock(return_value):
            return return_value

        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with patch.object(ConfigurationManager, '_validate_category_val', return_value=async_mock(None)) as valpatch:
            with patch.object(ConfigurationManager, '_read_category_val', return_value=async_mock(None)) as readpatch:
                with patch.object(ConfigurationManager, '_create_new_category', return_value=async_mock(None)) as createpatch:
                    with patch.object(ConfigurationManager, '_run_callbacks', return_value=async_mock(None)) as callbackpatch:
                        await c_mgr.create_category('catname', 'catvalue', "catdesc")
                    callbackpatch.assert_called_once_with('catname')
                createpatch.assert_called_once_with('catname', None, 'catdesc', None)
            readpatch.assert_called_once_with('catname')
        valpatch.assert_called_once_with('catvalue', True)

    @pytest.mark.asyncio
    async def test_create_category_good_newval_no_storageval_bad_create(self, reset_singleton):

        async def async_mock(return_value):
            return return_value

        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with patch.object(_logger, 'exception') as log_exc:
            with patch.object(ConfigurationManager, '_validate_category_val', return_value=async_mock(None)) as valpatch:
                with patch.object(ConfigurationManager, '_read_category_val', return_value=async_mock(None)) as readpatch:
                    with patch.object(ConfigurationManager, '_create_new_category', side_effect=StorageServerError(None, None, None)) as createpatch:
                        with patch.object(ConfigurationManager, '_run_callbacks') as callbackpatch:
                            with pytest.raises(StorageServerError):
                                await c_mgr.create_category('catname', 'catvalue', "catdesc")
                        callbackpatch.assert_not_called()
                    createpatch.assert_called_once_with('catname', None, 'catdesc', None)
                readpatch.assert_called_once_with('catname')
            valpatch.assert_called_once_with('catvalue', True)
        assert 1 == log_exc.call_count
        log_exc.assert_called_once_with('Unable to create new category based on category_name %s and category_description %s and category_json_schema %s', 'catname', 'catdesc', None)

    @pytest.mark.asyncio
    async def test_create_category_good_newval_keyerror_bad_create(self, reset_singleton):

        async def async_mock(return_value):
            return return_value

        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with patch.object(_logger, 'exception') as log_exc:
            with patch.object(ConfigurationManager, '_validate_category_val', return_value=async_mock(None)) as valpatch:
                with patch.object(ConfigurationManager, '_read_category_val', return_value=async_mock(None)) as readpatch:
                    with patch.object(ConfigurationManager, '_create_new_category', side_effect=KeyError()) as createpatch:
                        with patch.object(ConfigurationManager, '_run_callbacks') as callbackpatch:
                            with pytest.raises(KeyError):
                                await c_mgr.create_category('catname', 'catvalue', "catdesc")
                        callbackpatch.assert_not_called()
                    createpatch.assert_called_once_with('catname', None, 'catdesc', None)
                readpatch.assert_called_once_with('catname')
            valpatch.assert_called_once_with('catvalue', True)
        assert 1 == log_exc.call_count
        log_exc.assert_called_once_with('Unable to create new category based on category_name %s and category_description %s and category_json_schema %s', 'catname', 'catdesc', None)

    @pytest.mark.asyncio
    async def test_create_category_bad_newval(self, reset_singleton):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with patch.object(_logger, 'exception') as log_exc:
            with patch.object(ConfigurationManager, '_validate_category_val', side_effect=Exception()) as valpatch:
                with patch.object(ConfigurationManager, '_read_category_val') as readpatch:
                    with patch.object(ConfigurationManager, '_create_new_category') as createpatch:
                        with patch.object(ConfigurationManager, '_run_callbacks') as callbackpatch:
                            with pytest.raises(Exception):
                                await c_mgr.create_category('catname', 'catvalue', "catdesc")
                        callbackpatch.assert_not_called()
                    createpatch.assert_not_called()
                readpatch.assert_not_called()
            valpatch.assert_called_once_with('catvalue', True)
        assert 1 == log_exc.call_count
        log_exc.assert_called_once_with('Unable to create new category based on category_name %s and category_description %s and category_json_schema %s', 'catname', 'catdesc', '')

    @pytest.mark.asyncio
    async def test_set_category_item_value_entry_good_update(self, reset_singleton):

        async def async_mock(return_value):
            return return_value

        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        category_name = 'catname'
        item_name = 'itemname'
        new_value_entry = 'newvalentry'
        storage_value_entry = {'value': 'test', 'description': 'Test desc', 'type': 'string', 'default': 'test'}
        c_mgr._cacheManager.update(category_name, {item_name: storage_value_entry})
        with patch.object(ConfigurationManager, '_read_item_val', return_value=async_mock(storage_value_entry)) as readpatch:
            with patch.object(ConfigurationManager, '_update_value_val', return_value=async_mock(None)) as updatepatch:
                with patch.object(ConfigurationManager, '_run_callbacks', return_value=async_mock(None)) as callbackpatch:
                    await c_mgr.set_category_item_value_entry(category_name, item_name, new_value_entry)
                callbackpatch.assert_called_once_with(category_name)
            updatepatch.assert_called_once_with(category_name, item_name, new_value_entry)
        readpatch.assert_called_once_with(category_name, item_name)

    @pytest.mark.asyncio
    async def test_set_category_item_value_entry_bad_update(self, reset_singleton):

        async def async_mock():
            return {'value': 'test', 'description': 'Test desc', 'type': 'string', 'default': 'test'}

        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        category_name = 'catname'
        item_name = 'itemname'
        new_value_entry = 'newvalentry'
        with patch.object(_logger, 'exception') as log_exc:
            with patch.object(ConfigurationManager, '_read_item_val', return_value=async_mock()) as readpatch:
                with patch.object(ConfigurationManager, '_update_value_val', side_effect=Exception()) as updatepatch:
                    with patch.object(ConfigurationManager, '_run_callbacks') as callbackpatch:
                        with pytest.raises(Exception):
                            await c_mgr.set_category_item_value_entry(category_name, item_name, new_value_entry)
                    callbackpatch.assert_not_called()
                updatepatch.assert_called_once_with(category_name, item_name, new_value_entry)
            readpatch.assert_called_once_with(category_name, item_name)
        assert 1 == log_exc.call_count
        log_exc.assert_called_once_with('Unable to set item value entry based on category_name %s and item_name %s and value_item_entry %s', 'catname', 'itemname', 'newvalentry')

    @pytest.mark.asyncio
    async def test_set_category_item_value_entry_bad_storage(self, reset_singleton):

        async def async_mock(return_value):
            return return_value

        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)

        category_name = 'catname'
        item_name = 'itemname'
        new_value_entry = 'newvalentry'
        with patch.object(_logger, 'exception') as log_exc:
            with patch.object(ConfigurationManager, '_read_item_val', return_value=async_mock(None)) as readpatch:
                with patch.object(ConfigurationManager, '_update_value_val') as updatepatch:
                    with patch.object(ConfigurationManager, '_run_callbacks') as callbackpatch:
                        with pytest.raises(ValueError) as excinfo:
                            await c_mgr.set_category_item_value_entry(category_name, item_name, new_value_entry)
                        assert 'No detail found for the category_name: {} and item_name: {}'.format(category_name, item_name) in str(excinfo.value)
                    callbackpatch.assert_not_called()
                updatepatch.assert_not_called()
            readpatch.assert_called_once_with(category_name, item_name)
        assert 1 == log_exc.call_count
        log_exc.assert_called_once_with('Unable to set item value entry based on category_name %s and item_name %s and value_item_entry %s', 'catname', 'itemname', 'newvalentry')

    @pytest.mark.asyncio
    async def test_set_category_item_value_entry_no_change(self, reset_singleton):

        async def async_mock(return_value):
            return return_value

        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)

        category_name = 'catname'
        item_name = 'itemname'
        new_value_entry = 'newvalentry'

        with patch.object(ConfigurationManager, '_read_item_val', return_value=async_mock(new_value_entry)) as readpatch:
            with patch.object(ConfigurationManager, '_update_value_val') as updatepatch:
                with patch.object(ConfigurationManager, '_run_callbacks') as callbackpatch:
                    await c_mgr.set_category_item_value_entry(category_name, item_name, new_value_entry)
                callbackpatch.assert_not_called()
            updatepatch.assert_not_called()
        readpatch.assert_called_once_with(category_name, item_name)

    async def test_set_category_item_invalid_type_value(self, reset_singleton):
        async def async_mock(return_value):
            return return_value

        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        category_name = 'catname'
        item_name = 'itemname'
        new_value_entry = 'newvalentry'
        with patch.object(_logger, 'exception') as log_exc:
            with patch.object(ConfigurationManager, '_read_item_val', return_value=async_mock({'value': 'test', 'description': 'Test desc', 'type': 'boolean', 'default': 'test'})) as readpatch:
                with pytest.raises(Exception) as excinfo:
                    await c_mgr.set_category_item_value_entry(category_name, item_name, new_value_entry)
                assert excinfo.type is TypeError
                assert 'Unrecognized value name for item_name itemname' == str(excinfo.value)
            readpatch.assert_called_once_with(category_name, item_name)
        assert 1 == log_exc.call_count

    @pytest.mark.asyncio
    async def test_set_category_item_value_entry_with_enum_type(self, reset_singleton):
        async def async_mock(return_value):
            return return_value

        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)

        category_name = 'catname'
        item_name = 'itemname'
        new_value_entry = 'foo'
        storage_value_entry = {"value": "woo", "default": "woo", "description": "enum types", "type": "enumeration", "options": ["foo", "woo"]}
        c_mgr._cacheManager.update(category_name, {item_name: storage_value_entry})
        with patch.object(ConfigurationManager, '_read_item_val', return_value=async_mock(storage_value_entry)) as readpatch:
            with patch.object(ConfigurationManager, '_update_value_val', return_value=async_mock(None)) as updatepatch:
                with patch.object(ConfigurationManager, '_run_callbacks', return_value=async_mock(None)) as callbackpatch:
                    await c_mgr.set_category_item_value_entry(category_name, item_name, new_value_entry)
                callbackpatch.assert_called_once_with(category_name)
            updatepatch.assert_called_once_with(category_name, item_name, new_value_entry)
        readpatch.assert_called_once_with(category_name, item_name)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("new_value_entry, message", [
        ("", "entry_val cannot be empty"),
        ("blah", "new value does not exist in options enum")
    ])
    async def test_set_category_item_value_entry_with_enum_type_exceptions(self, new_value_entry, message):
        async def async_mock():
            return {"default": "woo", "description": "enum types", "type": "enumeration",
                    "options": ["foo", "woo"]}

        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        category_name = 'catname'
        item_name = 'itemname'

        with patch.object(_logger, 'exception') as log_exc:
            with patch.object(ConfigurationManager, '_read_item_val', return_value=async_mock()) as readpatch:
                with pytest.raises(Exception) as excinfo:
                    await c_mgr.set_category_item_value_entry(category_name, item_name, new_value_entry)
                assert excinfo.type is ValueError
                assert message == str(excinfo.value)
            readpatch.assert_called_once_with(category_name, item_name)
        assert 1 == log_exc.call_count

    @pytest.mark.asyncio
    async def test_get_all_category_names_good(self, reset_singleton):

        async def async_mock(return_value):
            return return_value

        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with patch.object(ConfigurationManager, '_read_all_category_names', return_value=async_mock('bla')) as readpatch:
            ret_val = await c_mgr.get_all_category_names()
            assert 'bla' == ret_val
        readpatch.assert_called_once_with()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("value", [
        "True", "False"
    ])
    async def test_get_all_category_names_with_root(self, reset_singleton, value):

        async def async_mock(return_value):
            return return_value

        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with patch.object(ConfigurationManager, '_read_all_groups', return_value=async_mock('bla')) as readpatch:
            ret_val = await c_mgr.get_all_category_names(root=value)
            assert 'bla' == ret_val
        readpatch.assert_called_once_with(value, False)

    @pytest.mark.asyncio
    async def test_get_all_category_names_bad(self, reset_singleton):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with patch.object(_logger, 'exception') as log_exc:
            with patch.object(ConfigurationManager, '_read_all_category_names', side_effect=Exception()) as readpatch:
                with pytest.raises(Exception):
                    await c_mgr.get_all_category_names()
            readpatch.assert_called_once_with()
        assert 1 == log_exc.call_count
        log_exc.assert_called_once_with('Unable to read all category names')

    @pytest.mark.asyncio
    async def test_get_category_all_items_good(self, reset_singleton):

        async def async_mock(return_value):
            return return_value

        category_name = 'catname'
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with patch.object(ConfigurationManager, '_read_category_val', return_value=async_mock('bla')) as readpatch:
            ret_val = await c_mgr.get_category_all_items(category_name)
            assert 'bla' == ret_val
        readpatch.assert_called_once_with(category_name)

    @pytest.mark.asyncio
    async def test_get_category_all_items_bad(self, reset_singleton):
        category_name = 'catname'
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with patch.object(_logger, 'exception') as log_exc:
            with patch.object(ConfigurationManager, '_read_category_val', side_effect=Exception()) as readpatch:
                with pytest.raises(Exception):
                    await c_mgr.get_category_all_items(category_name)
            readpatch.assert_called_once_with(category_name)
        assert 1 == log_exc.call_count
        log_exc.assert_called_once_with('Unable to get all category names based on category_name %s', 'catname')

    @pytest.mark.asyncio
    async def test_get_category_item_good(self, reset_singleton):

        async def async_mock(return_value):
            return return_value

        category_name = 'catname'
        item_name = 'item_name'
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with patch.object(ConfigurationManager, '_read_item_val', return_value=async_mock('bla')) as read_item_patch:
            with patch.object(ConfigurationManager, '_read_category_val', return_value=async_mock(None)) as read_cat_patch:
                ret_val = await c_mgr.get_category_item(category_name, item_name)
                assert 'bla' == ret_val
            read_cat_patch.assert_called_once_with(category_name)
        read_item_patch.assert_called_once_with(category_name, item_name)

    @pytest.mark.asyncio
    async def test_get_category_item_bad(self, reset_singleton):
        category_name = 'catname'
        item_name = 'item_name'
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with patch.object(_logger, 'exception') as log_exc:
            with patch.object(ConfigurationManager, '_read_item_val', side_effect=Exception()) as readpatch:
                with pytest.raises(Exception):
                    await c_mgr.get_category_item(category_name, item_name)
            readpatch.assert_called_once_with(category_name, item_name)
        assert 1 == log_exc.call_count
        log_exc.assert_called_once_with('Unable to get category item based on category_name %s and item_name %s', 'catname', 'item_name')

    @pytest.mark.asyncio
    async def test_get_category_item_value_entry_good(self, reset_singleton):

        async def async_mock(return_value):
            return return_value

        category_name = 'catname'
        item_name = 'item_name'
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with patch.object(ConfigurationManager, '_read_value_val', return_value=async_mock('bla')) as readpatch:
            ret_val = await c_mgr.get_category_item_value_entry(category_name, item_name)
            assert 'bla' == ret_val
        readpatch.assert_called_once_with(category_name, item_name)

    @pytest.mark.asyncio
    async def test_get_category_item_value_entry_bad(self, reset_singleton):
        category_name = 'catname'
        item_name = 'item_name'
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with patch.object(_logger, 'exception') as log_exc:
            with patch.object(ConfigurationManager, '_read_value_val', side_effect=Exception()) as readpatch:
                with pytest.raises(Exception):
                    await c_mgr.get_category_item_value_entry(category_name, item_name)
            readpatch.assert_called_once_with(category_name, item_name)
        assert 1 == log_exc.call_count
        log_exc.assert_called_once_with('Unable to get the "value" entry based on category_name %s and item_name %s', 'catname', 'item_name')

    @pytest.mark.asyncio
    async def test__create_new_category_good(self, reset_singleton):
        @asyncio.coroutine
        def mock_coro():
            return {'response': [{'display_name': 'catname', 'category_name': 'catname', 'category_val': 'catval', 'description': 'catdesc'}]}

        async def async_mock(return_value):
            return return_value

        category_name = 'catname'
        category_val = 'catval'
        category_description = 'catdesc'

        attrs = {"insert_into_tbl.return_value": mock_coro()}
        storage_client_mock = MagicMock(spec=StorageClientAsync, **attrs)
        c_mgr = ConfigurationManager(storage_client_mock)

        with patch.object(AuditLogger, '__init__', return_value=None):
            with patch.object(AuditLogger, 'information', return_value=async_mock(None)) as auditinfopatch:
                with patch.object(PayloadBuilder, '__init__', return_value=None):
                    with patch.object(PayloadBuilder, 'INSERT', return_value=PayloadBuilder) as pbinsertpatch:
                        with patch.object(PayloadBuilder, 'payload', return_value=None) as pbpayloadpatch:
                            await c_mgr._create_new_category(category_name, category_val, category_description)
                        pbpayloadpatch.assert_called_once_with()
                    pbinsertpatch.assert_called_once_with(display_name=category_name, description=category_description, key=category_name, value=category_val)
            auditinfopatch.assert_called_once_with('CONAD', {'category': category_val, 'name': category_name})
        storage_client_mock.insert_into_tbl.assert_called_once_with(
            'configuration', None)

    @pytest.mark.asyncio
    async def test_create_new_category_deprecated(self, reset_singleton):
        @asyncio.coroutine
        def mock_coro():
            return {'response': [{
                'category_name': 'catname',
                'category_val': 'catval',
                'description': 'catdesc'
            }]
            }

        async def async_mock(return_value):
            return return_value

        category_name = 'catname'
        category_val = {
            "test_item_name1": {
                "description": "test description val1",
                "type": "string",
                "default": "test default val1",
                "deprecated": "true"
            },
            "test_item_name2": {
                "description": "test description val2",
                "type": "string",
                "default": "test default val2"
            },

        }
        category_val_actual = {
            "test_item_name2": {
                "description": "test description val2",
                "type": "string",
                "default": "test default val2"
            },
        }

        category_description = 'catdesc'

        attrs = {"insert_into_tbl.return_value": mock_coro()}
        storage_client_mock = MagicMock(spec=StorageClientAsync, **attrs)
        c_mgr = ConfigurationManager(storage_client_mock)

        with patch.object(AuditLogger, '__init__', return_value=None):
            with patch.object(AuditLogger, 'information', return_value=async_mock(None)) as auditinfopatch:
                with patch.object(PayloadBuilder, '__init__', return_value=None):
                    with patch.object(PayloadBuilder, 'INSERT', return_value=PayloadBuilder) as pbinsertpatch:
                        with patch.object(PayloadBuilder, 'payload', return_value=None) as pbpayloadpatch:
                            await c_mgr._create_new_category(category_name, category_val, category_description)
                        pbpayloadpatch.assert_called_once_with()
                    pbinsertpatch.assert_called_once_with(display_name=category_name, description=category_description, key=category_name, value=category_val_actual)
            auditinfopatch.assert_called_once_with('CONAD', {'category': category_val_actual, 'name': category_name})
        storage_client_mock.insert_into_tbl.assert_called_once_with('configuration', None)

    @pytest.mark.asyncio
    async def test__read_all_category_names_1_row(self, reset_singleton):
        @asyncio.coroutine
        def mock_coro():
            return {'rows': [{'key': 'key1', 'description': 'description1', 'display_name': 'display key'}]}

        attrs = {"query_tbl_with_payload.return_value": mock_coro()}
        storage_client_mock = MagicMock(spec=StorageClientAsync, **attrs)

        c_mgr = ConfigurationManager(storage_client_mock)
        ret_val = await c_mgr._read_all_category_names()
        args, kwargs = storage_client_mock.query_tbl_with_payload.call_args
        assert 'configuration' == args[0]
        p = json.loads(args[1])
        assert {"return": ["key", "description", "value", "display_name", {"column": "ts", "alias": "timestamp", "format": "YYYY-MM-DD HH24:MI:SS.MS"}]} == p
        assert [('key1', 'description1', 'display key')] == ret_val

    @pytest.mark.asyncio
    async def test__read_all_category_names_2_row(self, reset_singleton):
        @asyncio.coroutine
        def mock_coro():
            return {'rows': [{'key': 'key1', 'description': 'description1', 'display_name': 'display key1'}, {'key': 'key2', 'description': 'description2', 'display_name': 'display key2'}]}

        attrs = {"query_tbl_with_payload.return_value": mock_coro()}
        storage_client_mock = MagicMock(spec=StorageClientAsync, **attrs)
        c_mgr = ConfigurationManager(storage_client_mock)
        ret_val = await c_mgr._read_all_category_names()
        args, kwargs = storage_client_mock.query_tbl_with_payload.call_args
        assert 'configuration' == args[0]
        p = json.loads(args[1])
        assert {"return": ["key", "description", "value", "display_name", {"column": "ts", "alias": "timestamp", "format": "YYYY-MM-DD HH24:MI:SS.MS"}]} == p
        assert [('key1', 'description1', 'display key1'), ('key2', 'description2', 'display key2')] == ret_val

    @pytest.mark.asyncio
    async def test__read_all_category_names_0_row(self, reset_singleton):
        @asyncio.coroutine
        def mock_coro():
            return {'rows': []}

        attrs = {"query_tbl_with_payload.return_value": mock_coro()}
        storage_client_mock = MagicMock(spec=StorageClientAsync, **attrs)
        c_mgr = ConfigurationManager(storage_client_mock)
        ret_val = await c_mgr._read_all_category_names()
        args, kwargs = storage_client_mock.query_tbl_with_payload.call_args
        assert 'configuration' == args[0]
        p = json.loads(args[1])
        assert {"return": ["key", "description", "value", "display_name", {"column": "ts", "alias": "timestamp", "format": "YYYY-MM-DD HH24:MI:SS.MS"}]} == p
        assert [] == ret_val

    @pytest.mark.asyncio
    @pytest.mark.parametrize("value, expected_result", [
        (True, [('General', 'General', 'GEN'), ('Advanced', 'Advanced', 'ADV')]),
        (False, [('service', 'FogLAMP service', 'SERV'), ('rest_api', 'User REST API', 'API')])
    ])
    async def test__read_all_groups(self, reset_singleton, value, expected_result):
        @asyncio.coroutine
        def q_result(*args):
            table = args[0]
            payload = json.loads(args[1])
            if table == "configuration":
                assert {"return": ["key", "description", "display_name"]} == payload
                return {"rows": [{"key": "General", "description": "General", "display_name": "GEN"}, {"key": "Advanced", "description": "Advanced", "display_name": "ADV"}, {"key": "service", "description": "FogLAMP service", "display_name": "SERV"}, {"key": "rest_api", "description": "User REST API", "display_name": "API"}], "count": 4}

            if table == "category_children":
                assert {"return": ["child"], "modifier": "distinct"} == payload
                return {"rows": [{"child": "SMNTR"}, {"child": "service"}, {"child": "rest_api"}], "count": 3}

        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with patch.object(storage_client_mock, 'query_tbl_with_payload', side_effect=q_result) as query_tbl_patch:
            ret_val = await c_mgr._read_all_groups(root=value, children=False)
            assert expected_result == ret_val
        assert 2 == query_tbl_patch.call_count

    @pytest.mark.asyncio
    async def test__read_category_val_1_row(self, reset_singleton):
        @asyncio.coroutine
        def mock_coro():
            return {'rows': [{'value': 'value1'}]}
        category_name = 'catname'

        attrs = {"query_tbl_with_payload.return_value": mock_coro()}
        storage_client_mock = MagicMock(spec=StorageClientAsync, **attrs)
        c_mgr = ConfigurationManager(storage_client_mock)

        with patch.object(PayloadBuilder, '__init__', return_value=None):
            with patch.object(PayloadBuilder, 'SELECT', return_value=PayloadBuilder) as pbselectpatch:
                with patch.object(PayloadBuilder, 'WHERE', return_value=PayloadBuilder) as pbwherepatch:
                    with patch.object(PayloadBuilder, 'payload', return_value=None) as pbpayloadpatch:
                        ret_val = await c_mgr._read_category_val(category_name)
                        assert 'value1' == ret_val
                    pbpayloadpatch.assert_called_once_with()
                pbwherepatch.assert_called_once_with(["key", "=", category_name])
            pbselectpatch.assert_called_once_with('value')
        storage_client_mock.query_tbl_with_payload.assert_called_once_with(
            'configuration', None)

    @pytest.mark.asyncio
    async def test__read_category_val_0_row(self, reset_singleton):
        @asyncio.coroutine
        def mock_coro():
            return {'rows': []}

        category_name = 'catname'

        attrs = {"query_tbl_with_payload.return_value": mock_coro()}
        storage_client_mock = MagicMock(spec=StorageClientAsync, **attrs)
        c_mgr = ConfigurationManager(storage_client_mock)

        with patch.object(PayloadBuilder, '__init__', return_value=None):
            with patch.object(PayloadBuilder, 'SELECT', return_value=PayloadBuilder) as pbselectpatch:
                with patch.object(PayloadBuilder, 'WHERE', return_value=PayloadBuilder) as pbwherepatch:
                    with patch.object(PayloadBuilder, 'payload', return_value=None) as pbpayloadpatch:
                        ret_val = await c_mgr._read_category_val(category_name)
                        assert ret_val is None
                    pbpayloadpatch.assert_called_once_with()
                pbwherepatch.assert_called_once_with(["key", "=", category_name])
            pbselectpatch.assert_called_once_with('value')
        storage_client_mock.query_tbl_with_payload.assert_called_once_with(
            'configuration', None)

    @pytest.mark.asyncio
    async def test__read_item_val_0_row(self, reset_singleton):
        @asyncio.coroutine
        def mock_coro():
            return {'rows': []}

        category_name = 'catname'
        item_name = 'itemname'

        attrs = {"query_tbl_with_payload.return_value": mock_coro()}
        storage_client_mock = MagicMock(spec=StorageClientAsync, **attrs)
        c_mgr = ConfigurationManager(storage_client_mock)
        ret_val = await c_mgr._read_item_val(category_name, item_name)
        assert ret_val is None

    @pytest.mark.asyncio
    async def test__read_item_val_1_row(self, reset_singleton):
        @asyncio.coroutine
        def mock_coro():
            return {'rows': [{'value': 'value1'}]}

        category_name = 'catname'
        item_name = 'itemname'
        attrs = {"query_tbl_with_payload.return_value": mock_coro()}
        storage_client_mock = MagicMock(spec=StorageClientAsync, **attrs)
        c_mgr = ConfigurationManager(storage_client_mock)
        ret_val = await c_mgr._read_item_val(category_name, item_name)
        assert ret_val == 'value1'

    @pytest.mark.asyncio
    async def test__read_value_val_0_row(self, reset_singleton):
        @asyncio.coroutine
        def mock_coro():
            return {'rows': []}

        category_name = 'catname'
        item_name = 'itemname'

        attrs = {"query_tbl_with_payload.return_value": mock_coro()}
        storage_client_mock = MagicMock(spec=StorageClientAsync, **attrs)
        c_mgr = ConfigurationManager(storage_client_mock)
        ret_val = await c_mgr._read_value_val(category_name, item_name)
        assert ret_val is None

    @pytest.mark.asyncio
    async def test__read_value_val_1_row(self, reset_singleton):
        @asyncio.coroutine
        def mock_coro():
            return {'rows': [{'value': 'value1'}]}

        category_name = 'catname'
        item_name = 'itemname'

        attrs = {"query_tbl_with_payload.return_value": mock_coro()}
        storage_client_mock = MagicMock(spec=StorageClientAsync, **attrs)
        c_mgr = ConfigurationManager(storage_client_mock)
        ret_val = await c_mgr._read_value_val(category_name, item_name)
        assert ret_val == 'value1'

    @pytest.mark.asyncio
    async def test__update_value_val(self, reset_singleton):
        async def async_mock(return_value):
            return return_value

        @asyncio.coroutine
        def mock_coro():
            return {"rows": []}

        category_name = 'catname'
        item_name = 'itemname'
        new_value_val = 'newval'

        attrs = {"query_tbl_with_payload.return_value": mock_coro(), "update_tbl.return_value": mock_coro()}
        storage_client_mock = MagicMock(spec=StorageClientAsync, **attrs)
        c_mgr = ConfigurationManager(storage_client_mock)

        with patch.object(AuditLogger, '__init__', return_value=None):
            with patch.object(AuditLogger, 'information', return_value=async_mock(None)) as auditinfopatch:
                await c_mgr._update_value_val(category_name, item_name, new_value_val)
        auditinfopatch.assert_called_once_with(
            'CONCH', {
                'category': category_name, 'item': item_name, 'oldValue': None, 'newValue': new_value_val})

    @pytest.mark.asyncio
    async def test__update_value_val_storageservererror(self, reset_singleton):
        @asyncio.coroutine
        def mock_coro():
            return {"rows": []}

        category_name = 'catname'
        item_name = 'itemname'
        new_value_val = 'newval'

        attrs = {"query_tbl_with_payload.return_value": mock_coro(), "update_tbl.return_value": mock_coro()}
        storage_client_mock = MagicMock(spec=StorageClientAsync, **attrs)
        c_mgr = ConfigurationManager(storage_client_mock)

        with patch.object(AuditLogger, '__init__', return_value=None):
            with patch.object(AuditLogger, 'information', return_value=None) as auditinfopatch:
                with patch.object(ConfigurationManager, '_update_value_val',
                                  side_effect=StorageServerError(None, None, None)) as createpatch:
                    with pytest.raises(StorageServerError):
                        await c_mgr._update_value_val(category_name, item_name, new_value_val)
                createpatch.assert_called_once_with('catname', 'itemname', 'newval')

        assert 0 == auditinfopatch.call_count

    @pytest.mark.asyncio
    async def test__update_value_val_keyerror(self, reset_singleton):
        @asyncio.coroutine
        def mock_coro():
            return {"rows": []}

        category_name = 'catname'
        item_name = 'itemname'
        new_value_val = 'newval'

        attrs = {"query_tbl_with_payload.return_value": mock_coro(), "update_tbl.return_value": mock_coro()}
        storage_client_mock = MagicMock(spec=StorageClientAsync, **attrs)
        c_mgr = ConfigurationManager(storage_client_mock)

        with patch.object(AuditLogger, '__init__', return_value=None):
            with patch.object(AuditLogger, 'information', return_value=None) as auditinfopatch:
                with patch.object(ConfigurationManager, '_update_value_val',
                                  side_effect=KeyError()) as createpatch:
                    with pytest.raises(KeyError):
                        await c_mgr._update_value_val(category_name, item_name, new_value_val)
                createpatch.assert_called_once_with('catname', 'itemname', 'newval')

        assert 0 == auditinfopatch.call_count

    @pytest.mark.asyncio
    async def test__update_category(self, reset_singleton):
        @asyncio.coroutine
        def mock_coro():
            return {"response": "dummy"}

        category_name = 'catname'
        category_description = 'catdesc'
        category_val = 'catval'

        @asyncio.coroutine
        def mock_coro2():
            return category_val

        attrs = {"update_tbl.return_value": mock_coro()}
        storage_client_mock = MagicMock(spec=StorageClientAsync, **attrs)
        c_mgr = ConfigurationManager(storage_client_mock)

        with patch.object(PayloadBuilder, '__init__', return_value=None):
            with patch.object(PayloadBuilder, 'SET', return_value=PayloadBuilder) as pbsetpatch:
                with patch.object(PayloadBuilder, 'WHERE', return_value=PayloadBuilder) as pbwherepatch:
                    with patch.object(PayloadBuilder, 'payload', return_value=None) as pbpayloadpatch:
                        with patch.object(c_mgr, '_read_category_val', return_value=mock_coro2()) as readpatch:
                            await c_mgr._update_category(category_name, category_val, category_description)
                        readpatch.assert_called_once_with(category_name)
                    pbpayloadpatch.assert_called_once_with()
                pbwherepatch.assert_called_once_with(["key", "=", category_name])
            pbsetpatch.assert_called_once_with(description=category_description, value=category_val, display_name=category_name)
        storage_client_mock.update_tbl.assert_called_once_with('configuration', None)

    @pytest.mark.asyncio
    async def test__update_category_storageservererror(self, reset_singleton):
        @asyncio.coroutine
        def mock_coro():
            return {"response": "dummy"}

        category_name = 'catname'
        category_description = 'catdesc'
        category_val = 'catval'

        attrs = {"update_tbl.return_value": mock_coro()}
        storage_client_mock = MagicMock(spec=StorageClientAsync, **attrs)
        c_mgr = ConfigurationManager(storage_client_mock)

        with patch.object(PayloadBuilder, '__init__', return_value=None):
            with patch.object(PayloadBuilder, 'SET', return_value=PayloadBuilder) as pbsetpatch:
                with patch.object(PayloadBuilder, 'WHERE', return_value=PayloadBuilder) as pbwherepatch:
                    with patch.object(PayloadBuilder, 'payload', return_value=None) as pbpayloadpatch:
                        with patch.object(ConfigurationManager, '_update_category',
                                          side_effect=StorageServerError(None, None, None)) as createpatch:
                            with pytest.raises(StorageServerError):
                                await c_mgr._update_category(category_name, category_val, category_description)
                        createpatch.assert_called_once_with('catname', 'catval', 'catdesc')
                    assert 0 == pbpayloadpatch.call_count
                assert 0 == pbwherepatch.call_count
            assert 0 == pbsetpatch.call_count
        assert 0 == storage_client_mock.update_tbl.call_count

    @pytest.mark.asyncio
    async def test__update_category_keyerror(self, reset_singleton):
        @asyncio.coroutine
        def mock_coro():
            return {"noresponse": "dummy"}

        category_name = 'catname'
        category_description = 'catdesc'
        category_val = 'catval'

        attrs = {"update_tbl.return_value": mock_coro()}
        storage_client_mock = MagicMock(spec=StorageClientAsync, **attrs)
        c_mgr = ConfigurationManager(storage_client_mock)

        with patch.object(PayloadBuilder, '__init__', return_value=None):
            with patch.object(PayloadBuilder, 'SET', return_value=PayloadBuilder) as pbsetpatch:
                with patch.object(PayloadBuilder, 'WHERE', return_value=PayloadBuilder) as pbwherepatch:
                    with patch.object(PayloadBuilder, 'payload', return_value=None) as pbpayloadpatch:
                        with pytest.raises(KeyError):
                            await c_mgr._update_category(category_name, category_val, category_description)
                    pbpayloadpatch.assert_called_once_with()
                pbwherepatch.assert_called_once_with(["key", "=", category_name])
            pbsetpatch.assert_called_once_with(description=category_description, value=category_val, display_name=category_name)
        storage_client_mock.update_tbl.assert_called_once_with('configuration', None)

    async def test_get_category_child(self):
        async def async_mock(return_value):
            return return_value

        category_name = 'HTTP SOUTH'
        all_child_ret_val = [{'parent': 'south', 'child': category_name}]
        child_info_ret_val = [{'key': category_name, 'description': 'HTTP South Plugin', 'display_name': category_name}]

        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with patch.object(ConfigurationManager, '_read_category_val', return_value=async_mock('bla')) as patch_read_cat_val:
            with patch.object(ConfigurationManager, '_read_all_child_category_names', return_value=async_mock(all_child_ret_val)) as patch_read_all_child:
                with patch.object(ConfigurationManager, '_read_child_info', return_value=async_mock(child_info_ret_val)) as patch_read_child_info:
                    ret_val = await c_mgr.get_category_child(category_name)
                    assert [{'displayName': category_name, 'description': 'HTTP South Plugin', 'key': category_name}] == ret_val
                patch_read_child_info.assert_called_once_with([{'child': category_name, 'parent': 'south'}])
            patch_read_all_child.assert_called_once_with(category_name)
        patch_read_cat_val.assert_called_once_with(category_name)

    async def test_get_category_child_no_exist(self):
        async def async_mock(return_value):
            return return_value

        category_name = 'HTTP SOUTH'
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with patch.object(ConfigurationManager, '_read_category_val', return_value=async_mock(None)) as patch_read_cat_val:
            with pytest.raises(ValueError) as excinfo:
                await c_mgr.get_category_child(category_name)
            assert 'No such {} category exist'.format(category_name) == str(excinfo.value)
        patch_read_cat_val.assert_called_once_with(category_name)

    @pytest.mark.parametrize("cat_name, children, message", [
        (1, ["coap"], 'category_name must be a string'),
        ("south", "coap", 'children must be a list')
    ])
    async def test_create_child_category_type_error(self, cat_name, children, message):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with pytest.raises(TypeError) as excinfo:
            await c_mgr.create_child_category(cat_name, children)
        assert message == str(excinfo.value)

    @pytest.mark.parametrize("ret_cat_name, ret_child_name, message", [
        (None, None, 'No such south category exist'),
        ("south", None, 'No such coap child exist')
    ])
    async def test_create_child_category_no_exists(self, ret_cat_name, ret_child_name, message):
        @asyncio.coroutine
        def q_result(*args):
            if args[0] == cat_name:
                return async_mock(ret_cat_name)
            if args[0] == child_name:
                return async_mock(ret_child_name)

        async def async_mock(return_value):
            return return_value

        cat_name = 'south'
        child_name = ["coap"]
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with patch.object(ConfigurationManager, '_read_category_val', side_effect=q_result):
            with pytest.raises(ValueError) as excinfo:
                await c_mgr.create_child_category(cat_name, child_name)
            assert message == str(excinfo.value)

    async def test_create_child_category(self, reset_singleton):
        @asyncio.coroutine
        def q_result(*args):
            if args[0] == cat_name:
                return async_mock('blah1')
            if args[0] == child_name:
                return async_mock('blah2')

        async def async_mock(return_value):
            return return_value

        cat_name = 'south'
        child_name = "coap"
        all_child_ret_val = [{'parent': cat_name, 'child': 'http'}]

        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with patch.object(ConfigurationManager, '_read_category_val', side_effect=q_result):
            with patch.object(ConfigurationManager, '_read_all_child_category_names',
                              return_value=async_mock(all_child_ret_val)) as patch_readall_child:
                with patch.object(ConfigurationManager, '_create_child',
                                  return_value=async_mock('inserted')) as patch_create_child:
                    ret_val = await c_mgr.create_child_category(cat_name, [child_name])
                    assert {'children': ['http', 'coap']} == ret_val
            patch_readall_child.assert_called_once_with(cat_name)
        patch_create_child.assert_called_once_with(cat_name, child_name)

    async def test_create_child_category_if_exists(self, reset_singleton):
        @asyncio.coroutine
        def q_result(*args):
            if args[0] == cat_name:
                return async_mock('blah1')
            if args[0] == child_name:
                return async_mock('blah2')

        async def async_mock(return_value):
            return return_value

        cat_name = 'south'
        child_name = "coap"
        all_child_ret_val = [{'parent': cat_name, 'child': child_name}]

        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with patch.object(ConfigurationManager, '_read_category_val', side_effect=q_result):
            with patch.object(ConfigurationManager, '_read_all_child_category_names',
                              return_value=async_mock(all_child_ret_val)) as patch_readall_child:
                ret_val = await c_mgr.create_child_category(cat_name, [child_name])
                assert {'children': ['coap']} == ret_val
            patch_readall_child.assert_called_once_with(cat_name)

    @pytest.mark.parametrize("cat_name, child_name, message", [
        (1, "coap", 'category_name must be a string'),
        ("south", 1, 'child_category must be a string')
    ])
    async def test_delete_child_category_type_error(self, cat_name, child_name, message):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with pytest.raises(TypeError) as excinfo:
            await c_mgr.delete_child_category(cat_name, child_name)
        assert message == str(excinfo.value)

    @pytest.mark.parametrize("ret_cat_name, ret_child_name, message", [
        (None, None, 'No such south category exist'),
        ("south", None, 'No such coap child exist')
    ])
    async def test_delete_child_category_no_exists(self, ret_cat_name, ret_child_name, message):
        @asyncio.coroutine
        def q_result(*args):
            if args[0] == cat_name:
                return async_mock(ret_cat_name)
            if args[0] == child_name:
                return async_mock(ret_child_name)

        async def async_mock(return_value):
            return return_value

        cat_name = 'south'
        child_name = 'coap'
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with patch.object(ConfigurationManager, '_read_category_val', side_effect=q_result):
            with pytest.raises(ValueError) as excinfo:
                await c_mgr.delete_child_category(cat_name, child_name)
            assert message == str(excinfo.value)

    async def test_delete_child_category(self, reset_singleton):
        @asyncio.coroutine
        def mock_coro():
            return expected_result

        @asyncio.coroutine
        def q_result(*args):
            if args[0] == cat_name:
                return async_mock('blah1')
            if args[0] == child_name:
                return async_mock('blah2')

        async def async_mock(return_value):
            return return_value

        expected_result = {"response": "deleted", "rows_affected": 1}
        attrs = {"delete_from_tbl.return_value": mock_coro()}
        cat_name = 'south'
        child_name = 'coap'
        all_child_ret_val = [{'parent': cat_name, 'child': child_name}]
        payload = {"where": {"column": "parent", "condition": "=", "value": "south", "and": {"column": "child", "condition": "=", "value": "coap"}}}
        storage_client_mock = MagicMock(spec=StorageClientAsync, **attrs)
        c_mgr = ConfigurationManager(storage_client_mock)
        with patch.object(ConfigurationManager, '_read_category_val', side_effect=q_result):
            with patch.object(ConfigurationManager, '_read_all_child_category_names', return_value=async_mock(all_child_ret_val)) as patch_read_all_child:
                ret_val = await c_mgr.delete_child_category(cat_name, child_name)
                assert [child_name] == ret_val
            patch_read_all_child.assert_called_once_with(cat_name)
        args, kwargs = storage_client_mock.delete_from_tbl.call_args
        assert 'category_children' == args[0]
        assert payload == json.loads(args[1])

    async def test_delete_child_category_key_error(self, reset_singleton):
        @asyncio.coroutine
        def mock_coro():
            return expected_result

        @asyncio.coroutine
        def q_result(*args):
            if args[0] == cat_name:
                return async_mock('blah1')
            if args[0] == child_name:
                return async_mock('blah2')

        async def async_mock(return_value):
            return return_value

        expected_result = {"message": "blah"}
        attrs = {"delete_from_tbl.return_value": mock_coro()}
        cat_name = 'south'
        child_name = 'coap'
        storage_client_mock = MagicMock(spec=StorageClientAsync, **attrs)
        c_mgr = ConfigurationManager(storage_client_mock)
        with patch.object(ConfigurationManager, '_read_category_val', side_effect=q_result):
            with pytest.raises(ValueError) as excinfo:
                await c_mgr.delete_child_category(cat_name, child_name)
            assert 'blah' == str(excinfo.value)

    async def test_delete_child_category_storage_exception(self, reset_singleton):
        @asyncio.coroutine
        def q_result(*args):
            if args[0] == cat_name:
                return async_mock('blah1')
            if args[0] == child_name:
                return async_mock('blah2')

        async def async_mock(return_value):
            return return_value

        cat_name = 'south'
        child_name = 'coap'
        msg = {"entryPoint": "delete", "message": "failed"}
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with patch.object(ConfigurationManager, '_read_category_val', side_effect=q_result):
            with patch.object(storage_client_mock, 'delete_from_tbl', side_effect=StorageServerError(code=400, reason="blah", error=msg)):
                with pytest.raises(ValueError) as excinfo:
                    await c_mgr.delete_child_category(cat_name, child_name)
                assert str(msg) == str(excinfo.value)

    async def test_delete_parent_category(self, reset_singleton):
        @asyncio.coroutine
        def mock_coro():
            return expected_result

        async def async_mock(return_value):
            return return_value

        expected_result = {"response": "deleted", "rows_affected": 1}
        attrs = {"delete_from_tbl.return_value": mock_coro()}
        storage_client_mock = MagicMock(spec=StorageClientAsync, **attrs)
        c_mgr = ConfigurationManager(storage_client_mock)

        with patch.object(ConfigurationManager, '_read_category_val', return_value=async_mock('bla')) as patch_read_cat_val:
            ret_val = await c_mgr.delete_parent_category("south")
            assert expected_result == ret_val
        patch_read_cat_val.assert_called_once_with('south')
        storage_client_mock.delete_from_tbl.assert_called_once_with('category_children', '{"where": {"column": "parent", "condition": "=", "value": "south"}}')

    async def test_delete_parent_category_bad_cat_name(self):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with pytest.raises(TypeError) as excinfo:
            await c_mgr.delete_parent_category(1)
        assert 'category_name must be a string' == str(excinfo.value)

    async def test_delete_parent_category_no_exists(self):
        async def async_mock(return_value):
            return return_value

        category_name = 'blah'
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with patch.object(ConfigurationManager, '_read_category_val', return_value=async_mock(None)) as patch_read_cat_val:
            with pytest.raises(ValueError) as excinfo:
                await c_mgr.delete_parent_category(category_name)
            assert 'No such {} category exist'.format(category_name) == str(excinfo.value)
        patch_read_cat_val.assert_called_once_with(category_name)

    async def test_delete_parent_category_key_error(self, reset_singleton):
        @asyncio.coroutine
        def mock_coro():
            return {"message": "blah"}

        async def async_mock(return_value):
            return return_value

        attrs = {"delete_from_tbl.return_value": mock_coro()}
        storage_client_mock = MagicMock(spec=StorageClientAsync, **attrs)
        c_mgr = ConfigurationManager(storage_client_mock)

        with patch.object(ConfigurationManager, '_read_category_val', return_value=async_mock('blah')) as patch_read_cat_val:
            with pytest.raises(ValueError) as excinfo:
                await c_mgr.delete_parent_category("south")
            assert 'blah' == str(excinfo.value)
        patch_read_cat_val.assert_called_once_with("south")

    async def test_delete_parent_category_storage_exception(self, reset_singleton):
        async def async_mock(return_value):
            return return_value

        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        msg = {"entryPoint": "delete", "message": "failed"}
        with patch.object(ConfigurationManager, '_read_category_val', return_value=async_mock('blah')) as patch_read_cat_val:
            with patch.object(storage_client_mock, 'delete_from_tbl', side_effect=StorageServerError(code=400, reason="blah", error=msg)):
                with pytest.raises(ValueError) as excinfo:
                    await c_mgr.delete_parent_category("south")
                assert str(msg) == str(excinfo.value)
        patch_read_cat_val.assert_called_once_with("south")

    @pytest.mark.skip(reason="TODO")
    async def test_delete_recursively_parent_category(self, reset_singleton):
        pass

    async def test__read_all_child_category_names(self, reset_singleton):
        @asyncio.coroutine
        def mock_coro():
            return {'rows': [{'parent': 'south', 'child': 'http'}], 'count': 1}

        attrs = {"query_tbl_with_payload.return_value": mock_coro()}
        storage_client_mock = MagicMock(spec=StorageClientAsync, **attrs)
        c_mgr = ConfigurationManager(storage_client_mock)
        payload = {"return": ["parent", "child"], "where": {"value": "south", "condition": "=", "column": "parent"}}
        ret_val = await c_mgr._read_all_child_category_names('south')
        assert [{'parent': 'south', 'child': 'http'}] == ret_val
        args, kwargs = storage_client_mock.query_tbl_with_payload.call_args
        assert 'category_children' == args[0]
        assert payload == json.loads(args[1])

    async def test__read_child_info(self, reset_singleton):
        @asyncio.coroutine
        def mock_coro():
            return {'rows': [{'description': 'HTTP South Plugin', 'key': 'HTTP SOUTH'}], 'count': 1}

        attrs = {"query_tbl_with_payload.return_value": mock_coro()}
        storage_client_mock = MagicMock(spec=StorageClientAsync, **attrs)
        child_cat_names = [{'child': 'HTTP SOUTH', 'parent': 'south'}]
        payload = {"return": ["key", "description", "display_name"], "where": {"column": "key", "condition": "=", "value": "HTTP SOUTH"}}
        c_mgr = ConfigurationManager(storage_client_mock)
        ret_val = await c_mgr._read_child_info(child_cat_names)
        assert [{'description': 'HTTP South Plugin', 'key': 'HTTP SOUTH'}] == ret_val
        args, kwargs = storage_client_mock.query_tbl_with_payload.call_args
        assert 'configuration' == args[0]
        assert payload == json.loads(args[1])

    async def test__create_child(self):
        @asyncio.coroutine
        def mock_coro():
            return {"response": "inserted", "rows_affected": 1}

        attrs = {"insert_into_tbl.return_value": mock_coro()}
        storage_client_mock = MagicMock(spec=StorageClientAsync, **attrs)
        c_mgr = ConfigurationManager(storage_client_mock)
        payload = {"child": "http", "parent": "south"}

        ret_val = await c_mgr._create_child("south", "http")
        assert 'inserted' == ret_val

        args, kwargs = storage_client_mock.insert_into_tbl.call_args
        assert 'category_children' == args[0]
        assert payload == json.loads(args[1])

    async def test__create_child_key_error(self, reset_singleton):
        @asyncio.coroutine
        def mock_coro():
            return {"message": "blah"}

        attrs = {"insert_into_tbl.return_value": mock_coro()}
        storage_client_mock = MagicMock(spec=StorageClientAsync, **attrs)

        c_mgr = ConfigurationManager(storage_client_mock)
        with pytest.raises(ValueError) as excinfo:
            await c_mgr._create_child("south", "http")
        assert 'blah' == str(excinfo.value)

    async def test__create_child_storage_exception(self, reset_singleton):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        msg = {"entryPoint": "insert", "message": "UNIQUE constraint failed"}
        with patch.object(storage_client_mock, 'insert_into_tbl', side_effect=StorageServerError(code=400, reason="blah", error=msg)):
            with pytest.raises(ValueError) as excinfo:
                await c_mgr._create_child("south", "http")
            assert str(msg) == str(excinfo.value)

    @pytest.mark.parametrize("item_type, item_val, result", [
        ("boolean", "True", "true"),
        ("boolean", "true", "true"),
        ("boolean", "false", "false"),
        ("boolean", "False", "false")
    ])
    async def test__clean(self, item_type, item_val, result):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        assert result == c_mgr._clean(item_type, item_val)

    @pytest.mark.parametrize("item_type, item_val, result", [
        ("boolean", "false", True),
        ("boolean", "true", True),
        ("integer", "123", True),
        ("float", "123456", True),
        ("float", "0", True),
        ("float", "NaN", True),
        ("float", "123.456", True),
        ("float", "123.E4", True),
        ("float", ".1", True),
        ("float", "6.523e-07", True),
        ("float", "6e7777", True),
        ("float", "1.79e+308", True),
        ("float", "infinity", True),
        ("float", "0E0", True),
        ("float", "+1e1", True),
        ("IPv4", "127.0.0.1", ipaddress.IPv4Address('127.0.0.1')),
        ("IPv6", "2001:db8::", ipaddress.IPv6Address('2001:db8::')),
        ("JSON", {}, True),  # allow a dict
        ("JSON", "{}", True),
        ("JSON", "1", True),
        ("JSON", "[]", True),
        ("JSON", "1.2", True),
        ("JSON", "{\"age\": 31}", True),
        ("URL", "http://somevalue.do", True),
        ("URL", "http://www.example.com", True),
        ("URL", "https://www.example.com", True),
        ("URL", "http://blog.example.com", True),
        ("URL", "http://www.example.com/product", True),
        ("URL", "http://www.example.com/products?id=1&page=2", True),
        ("URL", "http://255.255.255.255", True),
        ("URL", "http://255.255.255.255:8080", True),
        ("URL", "http://127.0.0.1:8080", True),
        ("URL", "http://localhost", True),
        ("URL", "http://0.0.0.0:8081", True),
        ("URL", "http://fe80::4", True),
        ("URL", "https://pi-server:5460/ingress/messages", True),
        ("URL", "https://dat-a.osisoft.com/api/omf", True),
        ("URL", "coap://host", True),
        ("URL", "coap://host.co.in", True),
        ("URL", "coaps://host:6683", True),
        ("password", "not implemented", None),
        ("X509 certificate", "not implemented", None)
    ])
    async def test__validate_type_value(self, item_type, item_val, result):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        assert result == c_mgr._validate_type_value(item_type, item_val)

    @pytest.mark.parametrize("item_type, item_val", [
        ("float", ""),
        ("float", "nana"),
        ("float", "1,234"),
        ("float", "NULL"),
        ("float", ",1"),
        ("float", "123.EE4"),
        ("float", "12.34.56"),
        ("float", "1,234"),
        ("float", "#12"),
        ("float", "12%"),
        ("float", "x86E0"),
        ("float", "86-5"),
        ("float", "True"),
        ("float", "+1e1.3"),
        ("float", "-+1"),
        ("float", "(1)"),
        ("boolean", "blah"),
        ("JSON", "Blah"),
        ("JSON", True),
        ("JSON", "True"),
        ("JSON", []),
        ("JSON", None),
        ("URL", "blah"),
        ("URL", "example.com"),
        ("URL", "123:80")
        # TODO: can not use urlopen hence we may want to check
        # result.netloc with some regex, but limited
        # ("URL", "http://somevalue.a"),
        # ("URL", "http://25.25.25. :80"),
        # ("URL", "http://25.25.25.25: 80"),
        # ("URL", "http://www.example.com | http://www.example2.com")
    ])
    async def test__validate_type_value_bad_data(self, item_type, item_val):
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        assert c_mgr._validate_type_value(item_type, item_val) is False

    @pytest.mark.parametrize("cat_info, config_item_list, exc_type, exc_msg", [
        (None, {}, NameError, "No such Category found for testcat"),
        ({'enableHttp': {'default': 'true', 'description': 'Enable HTTP', 'type': 'boolean', 'value': 'true'}},
         {"blah": "12"}, KeyError, "'blah config item not found'"),
        ({'enableHttp': {'default': 'true', 'description': 'Enable HTTP', 'type': 'boolean', 'value': 'true'}},
         {"enableHttp": False}, TypeError, "new value should be of type string"),
        ({'authentication': {'default': 'optional', 'options': ['mandatory', 'optional'], 'type': 'enumeration', 'description': 'API Call Authentication', 'value': 'optional'}},
         {"authentication": ""}, ValueError, "entry_val cannot be empty"),
        ({'authentication': {'default': 'optional', 'options': ['mandatory', 'optional'], 'type': 'enumeration', 'description': 'API Call Authentication', 'value': 'optional'}},
         {"authentication": "false"}, ValueError, "new value does not exist in options enum"),
        ({'authProviders': {'default': '{"providers": ["username", "ldap"] }', 'description': 'Authentication providers to use for the interface', 'type': 'JSON', 'value': '{"providers": ["username", "ldap"] }'}},
         {"authProviders": 3}, TypeError, "new value should be a valid dict Or a string literal, in double quotes"),
        ({'enableHttp': {'default': 'true', 'description': 'Enable HTTP', 'type': 'boolean', 'value': 'true'}},
         {"enableHttp": "blah"}, TypeError, "Unrecognized value name for item_name enableHttp")
    ])
    async def test_update_configuration_item_bulk_exceptions(self, cat_info, config_item_list, exc_type, exc_msg,
                                                             category_name='testcat'):
        async def async_mock(return_value):
            return return_value

        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with patch.object(c_mgr, 'get_category_all_items', return_value=async_mock(cat_info)) as patch_get_all_items:
            with patch.object(_logger, 'exception') as patch_log_exc:
                with pytest.raises(Exception) as exc_info:
                    await c_mgr.update_configuration_item_bulk(category_name, config_item_list)
                assert exc_type == exc_info.type
                assert exc_msg == str(exc_info.value)
            assert 1 == patch_log_exc.call_count
        patch_get_all_items.assert_called_once_with(category_name)

    async def test_update_configuration_item_bulk(self, category_name='rest_api'):
        async def async_mock(return_value):
            return return_value

        cat_info = {'enableHttp': {'default': 'true', 'description': 'Enable HTTP', 'type': 'boolean', 'value': 'true'}}
        config_item_list = {"enableHttp": "false"}
        update_result = {"response": "updated", "rows_affected": 1}
        read_val = {'allowPing': {'default': 'true', 'description': 'Allow access to ping', 'value': 'true', 'type': 'boolean'},
                    'enableHttp': {'default': 'true', 'description': 'Enable HTTP', 'value': 'false', 'type': 'boolean'}}
        payload = {'updates': [{'json_properties': [{'path': ['enableHttp', 'value'], 'column': 'value', 'value': 'false'}],
                                'return': ['key', 'description', {'format': 'YYYY-MM-DD HH24:MI:SS.MS', 'column': 'ts'}, 'value'],
                                'where': {'value': 'rest_api', 'column': 'key', 'condition': '='}}]}
        audit_details = {'items': {'enableHttp': {'oldValue': 'true', 'newValue': 'false'}}, 'category': category_name}
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with patch.object(c_mgr, 'get_category_all_items', return_value=async_mock(cat_info)) as patch_get_all_items:
            with patch.object(c_mgr._storage, 'update_tbl', return_value=async_mock(update_result)) as patch_update:
                with patch.object(c_mgr, '_read_category_val', return_value=async_mock(read_val)) as patch_read_val:
                    with patch.object(AuditLogger, '__init__', return_value=None):
                        with patch.object(AuditLogger, 'information', return_value=async_mock(None)) as patch_audit:
                            with patch.object(ConfigurationManager, '_run_callbacks', return_value=async_mock(None)) \
                                    as patch_callback:
                                await c_mgr.update_configuration_item_bulk(category_name, config_item_list)
                            patch_callback.assert_called_once_with(category_name)
                        patch_audit.assert_called_once_with('CONCH', audit_details)
                patch_read_val.assert_called_once_with(category_name)
            args, kwargs = patch_update.call_args
            assert 'configuration' == args[0]
            assert payload == json.loads(args[1])
        patch_get_all_items.assert_called_once_with(category_name)

    async def test_update_configuration_item_bulk_no_change(self, category_name='rest_api'):
        async def async_mock(return_value):
            return return_value

        cat_info = {'enableHttp': {'default': 'true', 'description': 'Enable HTTP', 'type': 'boolean', 'value': 'true'}}
        config_item_list = {"enableHttp": "true"}
        storage_client_mock = MagicMock(spec=StorageClientAsync)
        c_mgr = ConfigurationManager(storage_client_mock)
        with patch.object(c_mgr, 'get_category_all_items', return_value=async_mock(cat_info)) as patch_get_all_items:
            with patch.object(c_mgr._storage, 'update_tbl') as patch_update:
                with patch.object(AuditLogger, 'information') as patch_audit:
                    with patch.object(ConfigurationManager, '_run_callbacks') as patch_callback:
                        result = await c_mgr.update_configuration_item_bulk(category_name, config_item_list)
                        assert result is None
                    patch_callback.assert_not_called()
                patch_audit.assert_not_called()
            patch_update.assert_not_called()
        patch_get_all_items.assert_called_once_with(category_name)
