#
# Copyright (c) 2023 Airbyte, Inc., all rights reserved.
#

from __future__ import annotations

import datetime
import importlib
import inspect
import re
from functools import partial
from typing import Any, Callable, Dict, List, Mapping, MutableMapping, Optional, Tuple, Type, Union, get_args, get_origin, get_type_hints

from airbyte_cdk.models import FailureType, Level
from airbyte_cdk.sources.connector_state_manager import ConnectorStateManager
from airbyte_cdk.sources.declarative.async_job.job_orchestrator import AsyncJobOrchestrator
from airbyte_cdk.sources.declarative.async_job.job_tracker import JobTracker
from airbyte_cdk.sources.declarative.async_job.repository import AsyncJobRepository
from airbyte_cdk.sources.declarative.async_job.status import AsyncJobStatus
from airbyte_cdk.sources.declarative.auth import DeclarativeOauth2Authenticator, JwtAuthenticator
from airbyte_cdk.sources.declarative.auth.declarative_authenticator import DeclarativeAuthenticator, NoAuth
from airbyte_cdk.sources.declarative.auth.jwt import JwtAlgorithm
from airbyte_cdk.sources.declarative.auth.oauth import DeclarativeSingleUseRefreshTokenOauth2Authenticator
from airbyte_cdk.sources.declarative.auth.selective_authenticator import SelectiveAuthenticator
from airbyte_cdk.sources.declarative.auth.token import (
    ApiKeyAuthenticator,
    BasicHttpAuthenticator,
    BearerAuthenticator,
    LegacySessionTokenAuthenticator,
)
from airbyte_cdk.sources.declarative.auth.token_provider import InterpolatedStringTokenProvider, SessionTokenProvider, TokenProvider
from airbyte_cdk.sources.declarative.checks import CheckStream
from airbyte_cdk.sources.declarative.concurrency_level import ConcurrencyLevel
from airbyte_cdk.sources.declarative.datetime import MinMaxDatetime
from airbyte_cdk.sources.declarative.declarative_stream import DeclarativeStream
from airbyte_cdk.sources.declarative.decoders import (
    Decoder,
    IterableDecoder,
    JsonDecoder,
    JsonlDecoder,
    PaginationDecoderDecorator,
    XmlDecoder,
)
from airbyte_cdk.sources.declarative.extractors import DpathExtractor, RecordFilter, RecordSelector, ResponseToFileExtractor
from airbyte_cdk.sources.declarative.extractors.record_filter import ClientSideIncrementalRecordFilterDecorator
from airbyte_cdk.sources.declarative.extractors.record_selector import SCHEMA_TRANSFORMER_TYPE_MAPPING
from airbyte_cdk.sources.declarative.incremental import (
    ChildPartitionResumableFullRefreshCursor,
    CursorFactory,
    DatetimeBasedCursor,
    DeclarativeCursor,
    GlobalSubstreamCursor,
    PerPartitionCursor,
    PerPartitionWithGlobalCursor,
    ResumableFullRefreshCursor,
)
from airbyte_cdk.sources.declarative.interpolation import InterpolatedString
from airbyte_cdk.sources.declarative.interpolation.interpolated_mapping import InterpolatedMapping
from airbyte_cdk.sources.declarative.migrations.legacy_to_per_partition_state_migration import LegacyToPerPartitionStateMigration
from airbyte_cdk.sources.declarative.models import CustomStateMigration
from airbyte_cdk.sources.declarative.models.declarative_component_schema import AddedFieldDefinition as AddedFieldDefinitionModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import AddFields as AddFieldsModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import ApiKeyAuthenticator as ApiKeyAuthenticatorModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import AsyncJobStatusMap as AsyncJobStatusMapModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import AsyncRetriever as AsyncRetrieverModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import BasicHttpAuthenticator as BasicHttpAuthenticatorModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import BearerAuthenticator as BearerAuthenticatorModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import CheckStream as CheckStreamModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import CompositeErrorHandler as CompositeErrorHandlerModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import ConcurrencyLevel as ConcurrencyLevelModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import ConstantBackoffStrategy as ConstantBackoffStrategyModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import CursorPagination as CursorPaginationModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import CustomAuthenticator as CustomAuthenticatorModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import CustomBackoffStrategy as CustomBackoffStrategyModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import CustomErrorHandler as CustomErrorHandlerModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import CustomIncrementalSync as CustomIncrementalSyncModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import CustomPaginationStrategy as CustomPaginationStrategyModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import CustomPartitionRouter as CustomPartitionRouterModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import CustomRecordExtractor as CustomRecordExtractorModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import CustomRecordFilter as CustomRecordFilterModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import CustomRequester as CustomRequesterModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import CustomRetriever as CustomRetrieverModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import CustomSchemaLoader as CustomSchemaLoader
from airbyte_cdk.sources.declarative.models.declarative_component_schema import CustomTransformation as CustomTransformationModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import DatetimeBasedCursor as DatetimeBasedCursorModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import DeclarativeStream as DeclarativeStreamModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import DefaultErrorHandler as DefaultErrorHandlerModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import DefaultPaginator as DefaultPaginatorModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import DpathExtractor as DpathExtractorModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import (
    ExponentialBackoffStrategy as ExponentialBackoffStrategyModel,
)
from airbyte_cdk.sources.declarative.models.declarative_component_schema import HttpRequester as HttpRequesterModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import HttpResponseFilter as HttpResponseFilterModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import InlineSchemaLoader as InlineSchemaLoaderModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import IterableDecoder as IterableDecoderModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import JsonDecoder as JsonDecoderModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import JsonFileSchemaLoader as JsonFileSchemaLoaderModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import JsonlDecoder as JsonlDecoderModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import JwtAuthenticator as JwtAuthenticatorModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import JwtHeaders as JwtHeadersModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import JwtPayload as JwtPayloadModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import KeysToLower as KeysToLowerModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import (
    LegacySessionTokenAuthenticator as LegacySessionTokenAuthenticatorModel,
)
from airbyte_cdk.sources.declarative.models.declarative_component_schema import (
    LegacyToPerPartitionStateMigration as LegacyToPerPartitionStateMigrationModel,
)
from airbyte_cdk.sources.declarative.models.declarative_component_schema import ListPartitionRouter as ListPartitionRouterModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import MinMaxDatetime as MinMaxDatetimeModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import NoAuth as NoAuthModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import NoPagination as NoPaginationModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import OAuthAuthenticator as OAuthAuthenticatorModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import OffsetIncrement as OffsetIncrementModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import PageIncrement as PageIncrementModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import ParentStreamConfig as ParentStreamConfigModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import RecordFilter as RecordFilterModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import RecordSelector as RecordSelectorModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import RemoveFields as RemoveFieldsModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import RequestOption as RequestOptionModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import RequestPath as RequestPathModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import SelectiveAuthenticator as SelectiveAuthenticatorModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import SessionTokenAuthenticator as SessionTokenAuthenticatorModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import SimpleRetriever as SimpleRetrieverModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import Spec as SpecModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import SubstreamPartitionRouter as SubstreamPartitionRouterModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import ValueType
from airbyte_cdk.sources.declarative.models.declarative_component_schema import WaitTimeFromHeader as WaitTimeFromHeaderModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import WaitUntilTimeFromHeader as WaitUntilTimeFromHeaderModel
from airbyte_cdk.sources.declarative.models.declarative_component_schema import XmlDecoder as XmlDecoderModel
from airbyte_cdk.sources.declarative.partition_routers import (
    CartesianProductStreamSlicer,
    ListPartitionRouter,
    SinglePartitionRouter,
    SubstreamPartitionRouter,
)
from airbyte_cdk.sources.declarative.partition_routers.substream_partition_router import ParentStreamConfig
from airbyte_cdk.sources.declarative.requesters import HttpRequester, RequestOption
from airbyte_cdk.sources.declarative.requesters.error_handlers import CompositeErrorHandler, DefaultErrorHandler, HttpResponseFilter
from airbyte_cdk.sources.declarative.requesters.error_handlers.backoff_strategies import (
    ConstantBackoffStrategy,
    ExponentialBackoffStrategy,
    WaitTimeFromHeaderBackoffStrategy,
    WaitUntilTimeFromHeaderBackoffStrategy,
)
from airbyte_cdk.sources.declarative.requesters.http_job_repository import AsyncHttpJobRepository
from airbyte_cdk.sources.declarative.requesters.paginators import DefaultPaginator, NoPagination, PaginatorTestReadDecorator
from airbyte_cdk.sources.declarative.requesters.paginators.strategies import (
    CursorPaginationStrategy,
    CursorStopCondition,
    OffsetIncrement,
    PageIncrement,
    StopConditionPaginationStrategyDecorator,
)
from airbyte_cdk.sources.declarative.requesters.request_option import RequestOptionType
from airbyte_cdk.sources.declarative.requesters.request_options import (
    DatetimeBasedRequestOptionsProvider,
    DefaultRequestOptionsProvider,
    InterpolatedRequestOptionsProvider,
    RequestOptionsProvider,
)
from airbyte_cdk.sources.declarative.requesters.request_path import RequestPath
from airbyte_cdk.sources.declarative.requesters.requester import HttpMethod
from airbyte_cdk.sources.declarative.retrievers import AsyncRetriever, SimpleRetriever, SimpleRetrieverTestReadDecorator
from airbyte_cdk.sources.declarative.schema import DefaultSchemaLoader, InlineSchemaLoader, JsonFileSchemaLoader
from airbyte_cdk.sources.declarative.spec import Spec
from airbyte_cdk.sources.declarative.stream_slicers import StreamSlicer
from airbyte_cdk.sources.declarative.transformations import AddFields, RecordTransformation, RemoveFields
from airbyte_cdk.sources.declarative.transformations.add_fields import AddedFieldDefinition
from airbyte_cdk.sources.declarative.transformations.keys_to_lower_transformation import KeysToLowerTransformation
from airbyte_cdk.sources.message import InMemoryMessageRepository, LogAppenderMessageRepositoryDecorator, MessageRepository
from airbyte_cdk.sources.streams.concurrent.cursor import ConcurrentCursor, CursorField
from airbyte_cdk.sources.streams.concurrent.state_converters.datetime_stream_state_converter import (
    CustomFormatConcurrentStreamStateConverter,
    DateTimeStreamStateConverter,
)
from airbyte_cdk.sources.streams.http.error_handlers.response_models import ResponseAction
from airbyte_cdk.sources.types import Config
from airbyte_cdk.sources.utils.transform import TransformConfig, TypeTransformer
from isodate import parse_duration
from pydantic.v1 import BaseModel

ComponentDefinition = Mapping[str, Any]


class ModelToComponentFactory:

    EPOCH_DATETIME_FORMAT = "%s"

    def __init__(
        self,
        limit_pages_fetched_per_slice: Optional[int] = None,
        limit_slices_fetched: Optional[int] = None,
        emit_connector_builder_messages: bool = False,
        disable_retries: bool = False,
        disable_cache: bool = False,
        message_repository: Optional[MessageRepository] = None,
    ):
        self._init_mappings()
        self._limit_pages_fetched_per_slice = limit_pages_fetched_per_slice
        self._limit_slices_fetched = limit_slices_fetched
        self._emit_connector_builder_messages = emit_connector_builder_messages
        self._disable_retries = disable_retries
        self._disable_cache = disable_cache
        self._message_repository = message_repository or InMemoryMessageRepository(  # type: ignore
            self._evaluate_log_level(emit_connector_builder_messages)
        )

    def _init_mappings(self) -> None:
        self.PYDANTIC_MODEL_TO_CONSTRUCTOR: Mapping[Type[BaseModel], Callable[..., Any]] = {
            AddedFieldDefinitionModel: self.create_added_field_definition,
            AddFieldsModel: self.create_add_fields,
            ApiKeyAuthenticatorModel: self.create_api_key_authenticator,
            BasicHttpAuthenticatorModel: self.create_basic_http_authenticator,
            BearerAuthenticatorModel: self.create_bearer_authenticator,
            CheckStreamModel: self.create_check_stream,
            CompositeErrorHandlerModel: self.create_composite_error_handler,
            ConcurrencyLevelModel: self.create_concurrency_level,
            ConstantBackoffStrategyModel: self.create_constant_backoff_strategy,
            CursorPaginationModel: self.create_cursor_pagination,
            CustomAuthenticatorModel: self.create_custom_component,
            CustomBackoffStrategyModel: self.create_custom_component,
            CustomErrorHandlerModel: self.create_custom_component,
            CustomIncrementalSyncModel: self.create_custom_component,
            CustomRecordExtractorModel: self.create_custom_component,
            CustomRecordFilterModel: self.create_custom_component,
            CustomRequesterModel: self.create_custom_component,
            CustomRetrieverModel: self.create_custom_component,
            CustomSchemaLoader: self.create_custom_component,
            CustomStateMigration: self.create_custom_component,
            CustomPaginationStrategyModel: self.create_custom_component,
            CustomPartitionRouterModel: self.create_custom_component,
            CustomTransformationModel: self.create_custom_component,
            DatetimeBasedCursorModel: self.create_datetime_based_cursor,
            DeclarativeStreamModel: self.create_declarative_stream,
            DefaultErrorHandlerModel: self.create_default_error_handler,
            DefaultPaginatorModel: self.create_default_paginator,
            DpathExtractorModel: self.create_dpath_extractor,
            ExponentialBackoffStrategyModel: self.create_exponential_backoff_strategy,
            SessionTokenAuthenticatorModel: self.create_session_token_authenticator,
            HttpRequesterModel: self.create_http_requester,
            HttpResponseFilterModel: self.create_http_response_filter,
            InlineSchemaLoaderModel: self.create_inline_schema_loader,
            JsonDecoderModel: self.create_json_decoder,
            JsonlDecoderModel: self.create_jsonl_decoder,
            KeysToLowerModel: self.create_keys_to_lower_transformation,
            IterableDecoderModel: self.create_iterable_decoder,
            XmlDecoderModel: self.create_xml_decoder,
            JsonFileSchemaLoaderModel: self.create_json_file_schema_loader,
            JwtAuthenticatorModel: self.create_jwt_authenticator,
            LegacyToPerPartitionStateMigrationModel: self.create_legacy_to_per_partition_state_migration,
            ListPartitionRouterModel: self.create_list_partition_router,
            MinMaxDatetimeModel: self.create_min_max_datetime,
            NoAuthModel: self.create_no_auth,
            NoPaginationModel: self.create_no_pagination,
            OAuthAuthenticatorModel: self.create_oauth_authenticator,
            OffsetIncrementModel: self.create_offset_increment,
            PageIncrementModel: self.create_page_increment,
            ParentStreamConfigModel: self.create_parent_stream_config,
            RecordFilterModel: self.create_record_filter,
            RecordSelectorModel: self.create_record_selector,
            RemoveFieldsModel: self.create_remove_fields,
            RequestPathModel: self.create_request_path,
            RequestOptionModel: self.create_request_option,
            LegacySessionTokenAuthenticatorModel: self.create_legacy_session_token_authenticator,
            SelectiveAuthenticatorModel: self.create_selective_authenticator,
            SimpleRetrieverModel: self.create_simple_retriever,
            SpecModel: self.create_spec,
            SubstreamPartitionRouterModel: self.create_substream_partition_router,
            WaitTimeFromHeaderModel: self.create_wait_time_from_header,
            WaitUntilTimeFromHeaderModel: self.create_wait_until_time_from_header,
            AsyncRetrieverModel: self.create_async_retriever,
        }

        # Needed for the case where we need to perform a second parse on the fields of a custom component
        self.TYPE_NAME_TO_MODEL = {cls.__name__: cls for cls in self.PYDANTIC_MODEL_TO_CONSTRUCTOR}

    def create_component(
        self, model_type: Type[BaseModel], component_definition: ComponentDefinition, config: Config, **kwargs: Any
    ) -> Any:
        """
        Takes a given Pydantic model type and Mapping representing a component definition and creates a declarative component and
        subcomponents which will be used at runtime. This is done by first parsing the mapping into a Pydantic model and then creating
        creating declarative components from that model.

        :param model_type: The type of declarative component that is being initialized
        :param component_definition: The mapping that represents a declarative component
        :param config: The connector config that is provided by the customer
        :return: The declarative component to be used at runtime
        """

        component_type = component_definition.get("type")
        if component_definition.get("type") != model_type.__name__:
            raise ValueError(f"Expected manifest component of type {model_type.__name__}, but received {component_type} instead")

        declarative_component_model = model_type.parse_obj(component_definition)

        if not isinstance(declarative_component_model, model_type):
            raise ValueError(f"Expected {model_type.__name__} component, but received {declarative_component_model.__class__.__name__}")

        return self._create_component_from_model(model=declarative_component_model, config=config, **kwargs)

    def _create_component_from_model(self, model: BaseModel, config: Config, **kwargs: Any) -> Any:
        if model.__class__ not in self.PYDANTIC_MODEL_TO_CONSTRUCTOR:
            raise ValueError(f"{model.__class__} with attributes {model} is not a valid component type")
        component_constructor = self.PYDANTIC_MODEL_TO_CONSTRUCTOR.get(model.__class__)
        if not component_constructor:
            raise ValueError(f"Could not find constructor for {model.__class__}")
        return component_constructor(model=model, config=config, **kwargs)

    @staticmethod
    def create_added_field_definition(model: AddedFieldDefinitionModel, config: Config, **kwargs: Any) -> AddedFieldDefinition:
        interpolated_value = InterpolatedString.create(model.value, parameters=model.parameters or {})
        return AddedFieldDefinition(
            path=model.path,
            value=interpolated_value,
            value_type=ModelToComponentFactory._json_schema_type_name_to_type(model.value_type),
            parameters=model.parameters or {},
        )

    def create_add_fields(self, model: AddFieldsModel, config: Config, **kwargs: Any) -> AddFields:
        added_field_definitions = [
            self._create_component_from_model(
                model=added_field_definition_model,
                value_type=ModelToComponentFactory._json_schema_type_name_to_type(added_field_definition_model.value_type),
                config=config,
            )
            for added_field_definition_model in model.fields
        ]
        return AddFields(fields=added_field_definitions, parameters=model.parameters or {})

    def create_keys_to_lower_transformation(self, model: KeysToLowerModel, config: Config, **kwargs: Any) -> KeysToLowerTransformation:
        return KeysToLowerTransformation()

    @staticmethod
    def _json_schema_type_name_to_type(value_type: Optional[ValueType]) -> Optional[Type[Any]]:
        if not value_type:
            return None
        names_to_types = {
            ValueType.string: str,
            ValueType.number: float,
            ValueType.integer: int,
            ValueType.boolean: bool,
        }
        return names_to_types[value_type]

    @staticmethod
    def create_api_key_authenticator(
        model: ApiKeyAuthenticatorModel, config: Config, token_provider: Optional[TokenProvider] = None, **kwargs: Any
    ) -> ApiKeyAuthenticator:
        if model.inject_into is None and model.header is None:
            raise ValueError("Expected either inject_into or header to be set for ApiKeyAuthenticator")

        if model.inject_into is not None and model.header is not None:
            raise ValueError("inject_into and header cannot be set both for ApiKeyAuthenticator - remove the deprecated header option")

        if token_provider is not None and model.api_token != "":
            raise ValueError("If token_provider is set, api_token is ignored and has to be set to empty string.")

        request_option = (
            RequestOption(
                inject_into=RequestOptionType(model.inject_into.inject_into.value),
                field_name=model.inject_into.field_name,
                parameters=model.parameters or {},
            )
            if model.inject_into
            else RequestOption(
                inject_into=RequestOptionType.header,
                field_name=model.header or "",
                parameters=model.parameters or {},
            )
        )
        return ApiKeyAuthenticator(
            token_provider=(
                token_provider
                if token_provider is not None
                else InterpolatedStringTokenProvider(api_token=model.api_token or "", config=config, parameters=model.parameters or {})
            ),
            request_option=request_option,
            config=config,
            parameters=model.parameters or {},
        )

    def create_legacy_to_per_partition_state_migration(
        self,
        model: LegacyToPerPartitionStateMigrationModel,
        config: Mapping[str, Any],
        declarative_stream: DeclarativeStreamModel,
    ) -> LegacyToPerPartitionStateMigration:
        retriever = declarative_stream.retriever
        if not isinstance(retriever, SimpleRetrieverModel):
            raise ValueError(
                f"LegacyToPerPartitionStateMigrations can only be applied on a DeclarativeStream with a SimpleRetriever. Got {type(retriever)}"
            )
        partition_router = retriever.partition_router
        if not isinstance(partition_router, (SubstreamPartitionRouterModel, CustomPartitionRouterModel)):
            raise ValueError(
                f"LegacyToPerPartitionStateMigrations can only be applied on a SimpleRetriever with a Substream partition router. Got {type(partition_router)}"
            )
        if not hasattr(partition_router, "parent_stream_configs"):
            raise ValueError("LegacyToPerPartitionStateMigrations can only be applied with a parent stream configuration.")

        return LegacyToPerPartitionStateMigration(declarative_stream.retriever.partition_router, declarative_stream.incremental_sync, config, declarative_stream.parameters)  # type: ignore # The retriever type was already checked

    def create_session_token_authenticator(
        self, model: SessionTokenAuthenticatorModel, config: Config, name: str, **kwargs: Any
    ) -> Union[ApiKeyAuthenticator, BearerAuthenticator]:
        decoder = self._create_component_from_model(model=model.decoder, config=config) if model.decoder else JsonDecoder(parameters={})
        login_requester = self._create_component_from_model(
            model=model.login_requester, config=config, name=f"{name}_login_requester", decoder=decoder
        )
        token_provider = SessionTokenProvider(
            login_requester=login_requester,
            session_token_path=model.session_token_path,
            expiration_duration=parse_duration(model.expiration_duration) if model.expiration_duration else None,
            parameters=model.parameters or {},
            message_repository=self._message_repository,
            decoder=decoder,
        )
        if model.request_authentication.type == "Bearer":
            return ModelToComponentFactory.create_bearer_authenticator(
                BearerAuthenticatorModel(type="BearerAuthenticator", api_token=""),  # type: ignore # $parameters has a default value
                config,
                token_provider=token_provider,  # type: ignore # $parameters defaults to None
            )
        else:
            return ModelToComponentFactory.create_api_key_authenticator(
                ApiKeyAuthenticatorModel(type="ApiKeyAuthenticator", api_token="", inject_into=model.request_authentication.inject_into),  # type: ignore # $parameters and headers default to None
                config=config,
                token_provider=token_provider,
            )

    @staticmethod
    def create_basic_http_authenticator(model: BasicHttpAuthenticatorModel, config: Config, **kwargs: Any) -> BasicHttpAuthenticator:
        return BasicHttpAuthenticator(
            password=model.password or "", username=model.username, config=config, parameters=model.parameters or {}
        )

    @staticmethod
    def create_bearer_authenticator(
        model: BearerAuthenticatorModel, config: Config, token_provider: Optional[TokenProvider] = None, **kwargs: Any
    ) -> BearerAuthenticator:
        if token_provider is not None and model.api_token != "":
            raise ValueError("If token_provider is set, api_token is ignored and has to be set to empty string.")
        return BearerAuthenticator(
            token_provider=(
                token_provider
                if token_provider is not None
                else InterpolatedStringTokenProvider(api_token=model.api_token or "", config=config, parameters=model.parameters or {})
            ),
            config=config,
            parameters=model.parameters or {},
        )

    @staticmethod
    def create_check_stream(model: CheckStreamModel, config: Config, **kwargs: Any) -> CheckStream:
        return CheckStream(stream_names=model.stream_names, parameters={})

    def create_composite_error_handler(self, model: CompositeErrorHandlerModel, config: Config, **kwargs: Any) -> CompositeErrorHandler:
        error_handlers = [
            self._create_component_from_model(model=error_handler_model, config=config) for error_handler_model in model.error_handlers
        ]
        return CompositeErrorHandler(error_handlers=error_handlers, parameters=model.parameters or {})

    @staticmethod
    def create_concurrency_level(model: ConcurrencyLevelModel, config: Config, **kwargs: Any) -> ConcurrencyLevel:
        return ConcurrencyLevel(
            default_concurrency=model.default_concurrency,
            max_concurrency=model.max_concurrency,
            config=config,
            parameters={},
        )

    def create_concurrent_cursor_from_datetime_based_cursor(
        self,
        state_manager: ConnectorStateManager,
        model_type: Type[BaseModel],
        component_definition: ComponentDefinition,
        stream_name: str,
        stream_namespace: Optional[str],
        config: Config,
        stream_state: MutableMapping[str, Any],
        **kwargs: Any,
    ) -> Tuple[ConcurrentCursor, DateTimeStreamStateConverter]:

        component_type = component_definition.get("type")
        if component_definition.get("type") != model_type.__name__:
            raise ValueError(f"Expected manifest component of type {model_type.__name__}, but received {component_type} instead")

        datetime_based_cursor_model = model_type.parse_obj(component_definition)

        if not isinstance(datetime_based_cursor_model, DatetimeBasedCursorModel):
            raise ValueError(f"Expected {model_type.__name__} component, but received {datetime_based_cursor_model.__class__.__name__}")

        interpolated_cursor_field = InterpolatedString.create(
            datetime_based_cursor_model.cursor_field, parameters=datetime_based_cursor_model.parameters or {}
        )
        cursor_field = CursorField(interpolated_cursor_field.eval(config=config))

        interpolated_partition_field_start = InterpolatedString.create(
            datetime_based_cursor_model.partition_field_start or "start_time", parameters=datetime_based_cursor_model.parameters or {}
        )
        interpolated_partition_field_end = InterpolatedString.create(
            datetime_based_cursor_model.partition_field_end or "end_time", parameters=datetime_based_cursor_model.parameters or {}
        )

        slice_boundary_fields = (
            interpolated_partition_field_start.eval(config=config),
            interpolated_partition_field_end.eval(config=config),
        )

        datetime_format = datetime_based_cursor_model.datetime_format

        cursor_granularity = (
            parse_duration(datetime_based_cursor_model.cursor_granularity) if datetime_based_cursor_model.cursor_granularity else None
        )

        lookback_window = None
        interpolated_lookback_window = (
            InterpolatedString.create(datetime_based_cursor_model.lookback_window, parameters=datetime_based_cursor_model.parameters or {})
            if datetime_based_cursor_model.lookback_window
            else None
        )
        if interpolated_lookback_window:
            evaluated_lookback_window = interpolated_lookback_window.eval(config=config)
            if evaluated_lookback_window:
                lookback_window = parse_duration(evaluated_lookback_window)

        connector_state_converter: DateTimeStreamStateConverter
        connector_state_converter = CustomFormatConcurrentStreamStateConverter(
            datetime_format=datetime_format,
            input_datetime_formats=datetime_based_cursor_model.cursor_datetime_formats,
            is_sequential_state=True,
            cursor_granularity=cursor_granularity,
            # type: ignore  # Having issues w/ inspection for GapType and CursorValueType as shown in existing tests. Confirmed functionality is working in practice
        )

        start_date_runtime_value: Union[InterpolatedString, str, MinMaxDatetime]
        if isinstance(datetime_based_cursor_model.start_datetime, MinMaxDatetimeModel):
            start_date_runtime_value = self.create_min_max_datetime(model=datetime_based_cursor_model.start_datetime, config=config)
        else:
            start_date_runtime_value = datetime_based_cursor_model.start_datetime

        end_date_runtime_value: Optional[Union[InterpolatedString, str, MinMaxDatetime]]
        if isinstance(datetime_based_cursor_model.end_datetime, MinMaxDatetimeModel):
            end_date_runtime_value = self.create_min_max_datetime(model=datetime_based_cursor_model.end_datetime, config=config)
        else:
            end_date_runtime_value = datetime_based_cursor_model.end_datetime

        interpolated_start_date = MinMaxDatetime.create(
            interpolated_string_or_min_max_datetime=start_date_runtime_value, parameters=datetime_based_cursor_model.parameters
        )
        interpolated_end_date = (
            None if not end_date_runtime_value else MinMaxDatetime.create(end_date_runtime_value, datetime_based_cursor_model.parameters)
        )

        # If datetime format is not specified then start/end datetime should inherit it from the stream slicer
        if not interpolated_start_date.datetime_format:
            interpolated_start_date.datetime_format = datetime_format
        if interpolated_end_date and not interpolated_end_date.datetime_format:
            interpolated_end_date.datetime_format = datetime_format

        start_date = interpolated_start_date.get_datetime(config=config)
        end_date_provider = (
            partial(interpolated_end_date.get_datetime, config) if interpolated_end_date else connector_state_converter.get_end_provider()
        )

        if (datetime_based_cursor_model.step and not datetime_based_cursor_model.cursor_granularity) or (
            not datetime_based_cursor_model.step and datetime_based_cursor_model.cursor_granularity
        ):
            raise ValueError(
                f"If step is defined, cursor_granularity should be as well and vice-versa. "
                f"Right now, step is `{datetime_based_cursor_model.step}` and cursor_granularity is `{datetime_based_cursor_model.cursor_granularity}`"
            )

        # When step is not defined, default to a step size from the starting date to the present moment
        step_length = datetime.timedelta.max
        interpolated_step = (
            InterpolatedString.create(datetime_based_cursor_model.step, parameters=datetime_based_cursor_model.parameters or {})
            if datetime_based_cursor_model.step
            else None
        )
        if interpolated_step:
            evaluated_step = interpolated_step.eval(config)
            if evaluated_step:
                step_length = parse_duration(evaluated_step)

        return (
            ConcurrentCursor(
                stream_name=stream_name,
                stream_namespace=stream_namespace,
                stream_state=stream_state,
                message_repository=self._message_repository,  # type: ignore  # message_repository is always instantiated with a value by factory
                connector_state_manager=state_manager,
                connector_state_converter=connector_state_converter,
                cursor_field=cursor_field,
                slice_boundary_fields=slice_boundary_fields,
                start=start_date,  # type: ignore  # Having issues w/ inspection for GapType and CursorValueType as shown in existing tests. Confirmed functionality is working in practice
                end_provider=end_date_provider,  # type: ignore  # Having issues w/ inspection for GapType and CursorValueType as shown in existing tests. Confirmed functionality is working in practice
                lookback_window=lookback_window,
                slice_range=step_length,
                cursor_granularity=cursor_granularity,
            ),
            connector_state_converter,
        )

    @staticmethod
    def create_constant_backoff_strategy(model: ConstantBackoffStrategyModel, config: Config, **kwargs: Any) -> ConstantBackoffStrategy:
        return ConstantBackoffStrategy(
            backoff_time_in_seconds=model.backoff_time_in_seconds,
            config=config,
            parameters=model.parameters or {},
        )

    def create_cursor_pagination(
        self, model: CursorPaginationModel, config: Config, decoder: Decoder, **kwargs: Any
    ) -> CursorPaginationStrategy:
        if isinstance(decoder, PaginationDecoderDecorator):
            if not isinstance(decoder.decoder, (JsonDecoder, XmlDecoder)):
                raise ValueError(
                    f"Provided decoder of {type(decoder.decoder)=} is not supported. Please set JsonDecoder or XmlDecoder instead."
                )
            decoder_to_use = decoder
        else:
            if not isinstance(decoder, (JsonDecoder, XmlDecoder)):
                raise ValueError(f"Provided decoder of {type(decoder)=} is not supported. Please set JsonDecoder or XmlDecoder instead.")
            decoder_to_use = PaginationDecoderDecorator(decoder=decoder)

        return CursorPaginationStrategy(
            cursor_value=model.cursor_value,
            decoder=decoder_to_use,
            page_size=model.page_size,
            stop_condition=model.stop_condition,
            config=config,
            parameters=model.parameters or {},
        )

    def create_custom_component(self, model: Any, config: Config, **kwargs: Any) -> Any:
        """
        Generically creates a custom component based on the model type and a class_name reference to the custom Python class being
        instantiated. Only the model's additional properties that match the custom class definition are passed to the constructor
        :param model: The Pydantic model of the custom component being created
        :param config: The custom defined connector config
        :return: The declarative component built from the Pydantic model to be used at runtime
        """

        custom_component_class = self._get_class_from_fully_qualified_class_name(model.class_name)
        component_fields = get_type_hints(custom_component_class)
        model_args = model.dict()
        model_args["config"] = config

        # There are cases where a parent component will pass arguments to a child component via kwargs. When there are field collisions
        # we defer to these arguments over the component's definition
        for key, arg in kwargs.items():
            model_args[key] = arg

        # Pydantic is unable to parse a custom component's fields that are subcomponents into models because their fields and types are not
        # defined in the schema. The fields and types are defined within the Python class implementation. Pydantic can only parse down to
        # the custom component and this code performs a second parse to convert the sub-fields first into models, then declarative components
        for model_field, model_value in model_args.items():
            # If a custom component field doesn't have a type set, we try to use the type hints to infer the type
            if isinstance(model_value, dict) and "type" not in model_value and model_field in component_fields:
                derived_type = self._derive_component_type_from_type_hints(component_fields.get(model_field))
                if derived_type:
                    model_value["type"] = derived_type

            if self._is_component(model_value):
                model_args[model_field] = self._create_nested_component(model, model_field, model_value, config)
            elif isinstance(model_value, list):
                vals = []
                for v in model_value:
                    if isinstance(v, dict) and "type" not in v and model_field in component_fields:
                        derived_type = self._derive_component_type_from_type_hints(component_fields.get(model_field))
                        if derived_type:
                            v["type"] = derived_type
                    if self._is_component(v):
                        vals.append(self._create_nested_component(model, model_field, v, config))
                    else:
                        vals.append(v)
                model_args[model_field] = vals

        kwargs = {class_field: model_args[class_field] for class_field in component_fields.keys() if class_field in model_args}
        return custom_component_class(**kwargs)

    @staticmethod
    def _get_class_from_fully_qualified_class_name(full_qualified_class_name: str) -> Any:
        split = full_qualified_class_name.split(".")
        module = ".".join(split[:-1])
        class_name = split[-1]
        try:
            return getattr(importlib.import_module(module), class_name)
        except AttributeError:
            raise ValueError(f"Could not load class {full_qualified_class_name}.")

    @staticmethod
    def _derive_component_type_from_type_hints(field_type: Any) -> Optional[str]:
        interface = field_type
        while True:
            origin = get_origin(interface)
            if origin:
                # Unnest types until we reach the raw type
                # List[T] -> T
                # Optional[List[T]] -> T
                args = get_args(interface)
                interface = args[0]
            else:
                break
        if isinstance(interface, type) and not ModelToComponentFactory.is_builtin_type(interface):
            return interface.__name__
        return None

    @staticmethod
    def is_builtin_type(cls: Optional[Type[Any]]) -> bool:
        if not cls:
            return False
        return cls.__module__ == "builtins"

    @staticmethod
    def _extract_missing_parameters(error: TypeError) -> List[str]:
        parameter_search = re.search(r"keyword-only.*:\s(.*)", str(error))
        if parameter_search:
            return re.findall(r"\'(.+?)\'", parameter_search.group(1))
        else:
            return []

    def _create_nested_component(self, model: Any, model_field: str, model_value: Any, config: Config) -> Any:
        type_name = model_value.get("type", None)
        if not type_name:
            # If no type is specified, we can assume this is a dictionary object which can be returned instead of a subcomponent
            return model_value

        model_type = self.TYPE_NAME_TO_MODEL.get(type_name, None)
        if model_type:
            parsed_model = model_type.parse_obj(model_value)
            try:
                # To improve usability of the language, certain fields are shared between components. This can come in the form of
                # a parent component passing some of its fields to a child component or the parent extracting fields from other child
                # components and passing it to others. One example is the DefaultPaginator referencing the HttpRequester url_base
                # while constructing a SimpleRetriever. However, custom components don't support this behavior because they are created
                # generically in create_custom_component(). This block allows developers to specify extra arguments in $parameters that
                # are needed by a component and could not be shared.
                model_constructor = self.PYDANTIC_MODEL_TO_CONSTRUCTOR.get(parsed_model.__class__)
                constructor_kwargs = inspect.getfullargspec(model_constructor).kwonlyargs
                model_parameters = model_value.get("$parameters", {})
                matching_parameters = {kwarg: model_parameters[kwarg] for kwarg in constructor_kwargs if kwarg in model_parameters}
                return self._create_component_from_model(model=parsed_model, config=config, **matching_parameters)
            except TypeError as error:
                missing_parameters = self._extract_missing_parameters(error)
                if missing_parameters:
                    raise ValueError(
                        f"Error creating component '{type_name}' with parent custom component {model.class_name}: Please provide "
                        + ", ".join((f"{type_name}.$parameters.{parameter}" for parameter in missing_parameters))
                    )
                raise TypeError(f"Error creating component '{type_name}' with parent custom component {model.class_name}: {error}")
        else:
            raise ValueError(
                f"Error creating custom component {model.class_name}. Subcomponent creation has not been implemented for '{type_name}'"
            )

    @staticmethod
    def _is_component(model_value: Any) -> bool:
        return isinstance(model_value, dict) and model_value.get("type") is not None

    def create_datetime_based_cursor(self, model: DatetimeBasedCursorModel, config: Config, **kwargs: Any) -> DatetimeBasedCursor:
        start_datetime: Union[str, MinMaxDatetime] = (
            model.start_datetime if isinstance(model.start_datetime, str) else self.create_min_max_datetime(model.start_datetime, config)
        )
        end_datetime: Union[str, MinMaxDatetime, None] = None
        if model.is_data_feed and model.end_datetime:
            raise ValueError("Data feed does not support end_datetime")
        if model.is_data_feed and model.is_client_side_incremental:
            raise ValueError("`Client side incremental` cannot be applied with `data feed`. Choose only 1 from them.")
        if model.end_datetime:
            end_datetime = (
                model.end_datetime if isinstance(model.end_datetime, str) else self.create_min_max_datetime(model.end_datetime, config)
            )

        end_time_option = (
            RequestOption(
                inject_into=RequestOptionType(model.end_time_option.inject_into.value),
                field_name=model.end_time_option.field_name,
                parameters=model.parameters or {},
            )
            if model.end_time_option
            else None
        )
        start_time_option = (
            RequestOption(
                inject_into=RequestOptionType(model.start_time_option.inject_into.value),
                field_name=model.start_time_option.field_name,
                parameters=model.parameters or {},
            )
            if model.start_time_option
            else None
        )

        return DatetimeBasedCursor(
            cursor_field=model.cursor_field,
            cursor_datetime_formats=model.cursor_datetime_formats if model.cursor_datetime_formats else [],
            cursor_granularity=model.cursor_granularity,
            datetime_format=model.datetime_format,
            end_datetime=end_datetime,
            start_datetime=start_datetime,
            step=model.step,
            end_time_option=end_time_option,
            lookback_window=model.lookback_window,
            start_time_option=start_time_option,
            partition_field_end=model.partition_field_end,
            partition_field_start=model.partition_field_start,
            message_repository=self._message_repository,
            is_compare_strictly=model.is_compare_strictly,
            config=config,
            parameters=model.parameters or {},
        )

    def create_declarative_stream(self, model: DeclarativeStreamModel, config: Config, **kwargs: Any) -> DeclarativeStream:
        # When constructing a declarative stream, we assemble the incremental_sync component and retriever's partition_router field
        # components if they exist into a single CartesianProductStreamSlicer. This is then passed back as an argument when constructing the
        # Retriever. This is done in the declarative stream not the retriever to support custom retrievers. The custom create methods in
        # the factory only support passing arguments to the component constructors, whereas this performs a merge of all slicers into one.
        combined_slicers = self._merge_stream_slicers(model=model, config=config)

        primary_key = model.primary_key.__root__ if model.primary_key else None
        stop_condition_on_cursor = (
            model.incremental_sync and hasattr(model.incremental_sync, "is_data_feed") and model.incremental_sync.is_data_feed
        )
        client_side_incremental_sync = None
        if (
            model.incremental_sync
            and hasattr(model.incremental_sync, "is_client_side_incremental")
            and model.incremental_sync.is_client_side_incremental
        ):
            supported_slicers = (DatetimeBasedCursor, GlobalSubstreamCursor, PerPartitionWithGlobalCursor)
            if combined_slicers and not isinstance(combined_slicers, supported_slicers):
                raise ValueError("Unsupported Slicer is used. PerPartitionWithGlobalCursor should be used here instead")
            client_side_incremental_sync = {
                "date_time_based_cursor": self._create_component_from_model(model=model.incremental_sync, config=config),
                "substream_cursor": (
                    combined_slicers if isinstance(combined_slicers, (PerPartitionWithGlobalCursor, GlobalSubstreamCursor)) else None
                ),
            }

        if model.incremental_sync and isinstance(model.incremental_sync, DatetimeBasedCursorModel):
            cursor_model = model.incremental_sync

            end_time_option = (
                RequestOption(
                    inject_into=RequestOptionType(cursor_model.end_time_option.inject_into.value),
                    field_name=cursor_model.end_time_option.field_name,
                    parameters=cursor_model.parameters or {},
                )
                if cursor_model.end_time_option
                else None
            )
            start_time_option = (
                RequestOption(
                    inject_into=RequestOptionType(cursor_model.start_time_option.inject_into.value),
                    field_name=cursor_model.start_time_option.field_name,
                    parameters=cursor_model.parameters or {},
                )
                if cursor_model.start_time_option
                else None
            )

            request_options_provider = DatetimeBasedRequestOptionsProvider(
                start_time_option=start_time_option,
                end_time_option=end_time_option,
                partition_field_start=cursor_model.partition_field_end,
                partition_field_end=cursor_model.partition_field_end,
                config=config,
                parameters=model.parameters or {},
            )
        else:
            request_options_provider = None

        transformations = []
        if model.transformations:
            for transformation_model in model.transformations:
                transformations.append(self._create_component_from_model(model=transformation_model, config=config))
        retriever = self._create_component_from_model(
            model=model.retriever,
            config=config,
            name=model.name,
            primary_key=primary_key,
            stream_slicer=combined_slicers,
            request_options_provider=request_options_provider,
            stop_condition_on_cursor=stop_condition_on_cursor,
            client_side_incremental_sync=client_side_incremental_sync,
            transformations=transformations,
        )
        cursor_field = model.incremental_sync.cursor_field if model.incremental_sync else None

        if model.state_migrations:
            state_transformations = [
                self._create_component_from_model(state_migration, config, declarative_stream=model)
                for state_migration in model.state_migrations
            ]
        else:
            state_transformations = []

        if model.schema_loader:
            schema_loader = self._create_component_from_model(model=model.schema_loader, config=config)
        else:
            options = model.parameters or {}
            if "name" not in options:
                options["name"] = model.name
            schema_loader = DefaultSchemaLoader(config=config, parameters=options)

        return DeclarativeStream(
            name=model.name or "",
            primary_key=primary_key,
            retriever=retriever,
            schema_loader=schema_loader,
            stream_cursor_field=cursor_field or "",
            state_migrations=state_transformations,
            config=config,
            parameters=model.parameters or {},
        )

    def _merge_stream_slicers(self, model: DeclarativeStreamModel, config: Config) -> Optional[StreamSlicer]:
        stream_slicer = None
        if (
            hasattr(model.retriever, "partition_router")
            and isinstance(model.retriever, SimpleRetrieverModel)
            and model.retriever.partition_router
        ):
            stream_slicer_model = model.retriever.partition_router

            if isinstance(stream_slicer_model, list):
                stream_slicer = CartesianProductStreamSlicer(
                    [self._create_component_from_model(model=slicer, config=config) for slicer in stream_slicer_model], parameters={}
                )
            else:
                stream_slicer = self._create_component_from_model(model=stream_slicer_model, config=config)

        if model.incremental_sync and stream_slicer:
            incremental_sync_model = model.incremental_sync
            if hasattr(incremental_sync_model, "global_substream_cursor") and incremental_sync_model.global_substream_cursor:
                cursor_component = self._create_component_from_model(model=incremental_sync_model, config=config)
                return GlobalSubstreamCursor(stream_cursor=cursor_component, partition_router=stream_slicer)
            else:
                cursor_component = self._create_component_from_model(model=incremental_sync_model, config=config)
                return PerPartitionWithGlobalCursor(
                    cursor_factory=CursorFactory(
                        lambda: self._create_component_from_model(model=incremental_sync_model, config=config),
                    ),
                    partition_router=stream_slicer,
                    stream_cursor=cursor_component,
                )
        elif model.incremental_sync:
            return self._create_component_from_model(model=model.incremental_sync, config=config) if model.incremental_sync else None
        elif stream_slicer:
            # For the Full-Refresh sub-streams, we use the nested `ChildPartitionResumableFullRefreshCursor`
            return PerPartitionCursor(
                cursor_factory=CursorFactory(create_function=partial(ChildPartitionResumableFullRefreshCursor, {})),
                partition_router=stream_slicer,
            )
        elif hasattr(model.retriever, "paginator") and model.retriever.paginator and not stream_slicer:
            # For the regular Full-Refresh streams, we use the high level `ResumableFullRefreshCursor`
            return ResumableFullRefreshCursor(parameters={})
        else:
            return None

    def create_default_error_handler(self, model: DefaultErrorHandlerModel, config: Config, **kwargs: Any) -> DefaultErrorHandler:
        backoff_strategies = []
        if model.backoff_strategies:
            for backoff_strategy_model in model.backoff_strategies:
                backoff_strategies.append(self._create_component_from_model(model=backoff_strategy_model, config=config))

        response_filters = []
        if model.response_filters:
            for response_filter_model in model.response_filters:
                response_filters.append(self._create_component_from_model(model=response_filter_model, config=config))
        response_filters.append(HttpResponseFilter(config=config, parameters=model.parameters or {}))

        return DefaultErrorHandler(
            backoff_strategies=backoff_strategies,
            max_retries=model.max_retries,
            response_filters=response_filters,
            config=config,
            parameters=model.parameters or {},
        )

    def create_default_paginator(
        self,
        model: DefaultPaginatorModel,
        config: Config,
        *,
        url_base: str,
        decoder: Optional[Decoder] = None,
        cursor_used_for_stop_condition: Optional[DeclarativeCursor] = None,
    ) -> Union[DefaultPaginator, PaginatorTestReadDecorator]:
        if decoder:
            if not isinstance(decoder, (JsonDecoder, XmlDecoder)):
                raise ValueError(f"Provided decoder of {type(decoder)=} is not supported. Please set JsonDecoder or XmlDecoder instead.")
            decoder_to_use = PaginationDecoderDecorator(decoder=decoder)
        else:
            decoder_to_use = PaginationDecoderDecorator(decoder=JsonDecoder(parameters={}))
        page_size_option = (
            self._create_component_from_model(model=model.page_size_option, config=config) if model.page_size_option else None
        )
        page_token_option = (
            self._create_component_from_model(model=model.page_token_option, config=config) if model.page_token_option else None
        )
        pagination_strategy = self._create_component_from_model(model=model.pagination_strategy, config=config, decoder=decoder_to_use)
        if cursor_used_for_stop_condition:
            pagination_strategy = StopConditionPaginationStrategyDecorator(
                pagination_strategy, CursorStopCondition(cursor_used_for_stop_condition)
            )
        paginator = DefaultPaginator(
            decoder=decoder_to_use,
            page_size_option=page_size_option,
            page_token_option=page_token_option,
            pagination_strategy=pagination_strategy,
            url_base=url_base,
            config=config,
            parameters=model.parameters or {},
        )
        if self._limit_pages_fetched_per_slice:
            return PaginatorTestReadDecorator(paginator, self._limit_pages_fetched_per_slice)
        return paginator

    def create_dpath_extractor(
        self, model: DpathExtractorModel, config: Config, decoder: Optional[Decoder] = None, **kwargs: Any
    ) -> DpathExtractor:
        if decoder:
            decoder_to_use = decoder
        else:
            decoder_to_use = JsonDecoder(parameters={})
        model_field_path: List[Union[InterpolatedString, str]] = [x for x in model.field_path]
        return DpathExtractor(decoder=decoder_to_use, field_path=model_field_path, config=config, parameters=model.parameters or {})

    @staticmethod
    def create_exponential_backoff_strategy(model: ExponentialBackoffStrategyModel, config: Config) -> ExponentialBackoffStrategy:
        return ExponentialBackoffStrategy(factor=model.factor or 5, parameters=model.parameters or {}, config=config)

    def create_http_requester(self, model: HttpRequesterModel, decoder: Decoder, config: Config, *, name: str) -> HttpRequester:
        authenticator = (
            self._create_component_from_model(model=model.authenticator, config=config, url_base=model.url_base, name=name, decoder=decoder)
            if model.authenticator
            else None
        )
        error_handler = (
            self._create_component_from_model(model=model.error_handler, config=config)
            if model.error_handler
            else DefaultErrorHandler(backoff_strategies=[], response_filters=[], config=config, parameters=model.parameters or {})
        )

        request_options_provider = InterpolatedRequestOptionsProvider(
            request_body_data=model.request_body_data,
            request_body_json=model.request_body_json,
            request_headers=model.request_headers,
            request_parameters=model.request_parameters,
            config=config,
            parameters=model.parameters or {},
        )

        assert model.use_cache is not None  # for mypy
        assert model.http_method is not None  # for mypy

        use_cache = model.use_cache and not self._disable_cache

        return HttpRequester(
            name=name,
            url_base=model.url_base,
            path=model.path,
            authenticator=authenticator,
            error_handler=error_handler,
            http_method=HttpMethod[model.http_method.value],
            request_options_provider=request_options_provider,
            config=config,
            disable_retries=self._disable_retries,
            parameters=model.parameters or {},
            message_repository=self._message_repository,
            use_cache=use_cache,
            decoder=decoder,
            stream_response=decoder.is_stream_response() if decoder else False,
        )

    @staticmethod
    def create_http_response_filter(model: HttpResponseFilterModel, config: Config, **kwargs: Any) -> HttpResponseFilter:
        if model.action:
            action = ResponseAction(model.action.value)
        else:
            action = None

        failure_type = FailureType(model.failure_type.value) if model.failure_type else None

        http_codes = (
            set(model.http_codes) if model.http_codes else set()
        )  # JSON schema notation has no set data type. The schema enforces an array of unique elements

        return HttpResponseFilter(
            action=action,
            failure_type=failure_type,
            error_message=model.error_message or "",
            error_message_contains=model.error_message_contains or "",
            http_codes=http_codes,
            predicate=model.predicate or "",
            config=config,
            parameters=model.parameters or {},
        )

    @staticmethod
    def create_inline_schema_loader(model: InlineSchemaLoaderModel, config: Config, **kwargs: Any) -> InlineSchemaLoader:
        return InlineSchemaLoader(schema=model.schema_ or {}, parameters={})

    @staticmethod
    def create_json_decoder(model: JsonDecoderModel, config: Config, **kwargs: Any) -> JsonDecoder:
        return JsonDecoder(parameters={})

    @staticmethod
    def create_jsonl_decoder(model: JsonlDecoderModel, config: Config, **kwargs: Any) -> JsonlDecoder:
        return JsonlDecoder(parameters={})

    @staticmethod
    def create_iterable_decoder(model: IterableDecoderModel, config: Config, **kwargs: Any) -> IterableDecoder:
        return IterableDecoder(parameters={})

    @staticmethod
    def create_xml_decoder(model: XmlDecoderModel, config: Config, **kwargs: Any) -> XmlDecoder:
        return XmlDecoder(parameters={})

    @staticmethod
    def create_json_file_schema_loader(model: JsonFileSchemaLoaderModel, config: Config, **kwargs: Any) -> JsonFileSchemaLoader:
        return JsonFileSchemaLoader(file_path=model.file_path or "", config=config, parameters=model.parameters or {})

    @staticmethod
    def create_jwt_authenticator(model: JwtAuthenticatorModel, config: Config, **kwargs: Any) -> JwtAuthenticator:
        jwt_headers = model.jwt_headers or JwtHeadersModel(kid=None, typ="JWT", cty=None)
        jwt_payload = model.jwt_payload or JwtPayloadModel(iss=None, sub=None, aud=None)
        return JwtAuthenticator(
            config=config,
            parameters=model.parameters or {},
            algorithm=JwtAlgorithm(model.algorithm.value),
            secret_key=model.secret_key,
            base64_encode_secret_key=model.base64_encode_secret_key,
            token_duration=model.token_duration,
            header_prefix=model.header_prefix,
            kid=jwt_headers.kid,
            typ=jwt_headers.typ,
            cty=jwt_headers.cty,
            iss=jwt_payload.iss,
            sub=jwt_payload.sub,
            aud=jwt_payload.aud,
            additional_jwt_headers=model.additional_jwt_headers,
            additional_jwt_payload=model.additional_jwt_payload,
        )

    @staticmethod
    def create_list_partition_router(model: ListPartitionRouterModel, config: Config, **kwargs: Any) -> ListPartitionRouter:
        request_option = (
            RequestOption(
                inject_into=RequestOptionType(model.request_option.inject_into.value),
                field_name=model.request_option.field_name,
                parameters=model.parameters or {},
            )
            if model.request_option
            else None
        )
        return ListPartitionRouter(
            cursor_field=model.cursor_field,
            request_option=request_option,
            values=model.values,
            config=config,
            parameters=model.parameters or {},
        )

    @staticmethod
    def create_min_max_datetime(model: MinMaxDatetimeModel, config: Config, **kwargs: Any) -> MinMaxDatetime:
        return MinMaxDatetime(
            datetime=model.datetime,
            datetime_format=model.datetime_format or "",
            max_datetime=model.max_datetime or "",
            min_datetime=model.min_datetime or "",
            parameters=model.parameters or {},
        )

    @staticmethod
    def create_no_auth(model: NoAuthModel, config: Config, **kwargs: Any) -> NoAuth:
        return NoAuth(parameters=model.parameters or {})

    @staticmethod
    def create_no_pagination(model: NoPaginationModel, config: Config, **kwargs: Any) -> NoPagination:
        return NoPagination(parameters={})

    def create_oauth_authenticator(self, model: OAuthAuthenticatorModel, config: Config, **kwargs: Any) -> DeclarativeOauth2Authenticator:
        if model.refresh_token_updater:
            # ignore type error because fixing it would have a lot of dependencies, revisit later
            return DeclarativeSingleUseRefreshTokenOauth2Authenticator(  # type: ignore
                config,
                InterpolatedString.create(model.token_refresh_endpoint, parameters=model.parameters or {}).eval(config),
                access_token_name=InterpolatedString.create(
                    model.access_token_name or "access_token", parameters=model.parameters or {}
                ).eval(config),
                refresh_token_name=model.refresh_token_updater.refresh_token_name,
                expires_in_name=InterpolatedString.create(model.expires_in_name or "expires_in", parameters=model.parameters or {}).eval(
                    config
                ),
                client_id=InterpolatedString.create(model.client_id, parameters=model.parameters or {}).eval(config),
                client_secret=InterpolatedString.create(model.client_secret, parameters=model.parameters or {}).eval(config),
                access_token_config_path=model.refresh_token_updater.access_token_config_path,
                refresh_token_config_path=model.refresh_token_updater.refresh_token_config_path,
                token_expiry_date_config_path=model.refresh_token_updater.token_expiry_date_config_path,
                grant_type=InterpolatedString.create(model.grant_type or "refresh_token", parameters=model.parameters or {}).eval(config),
                refresh_request_body=InterpolatedMapping(model.refresh_request_body or {}, parameters=model.parameters or {}).eval(config),
                scopes=model.scopes,
                token_expiry_date_format=model.token_expiry_date_format,
                message_repository=self._message_repository,
                refresh_token_error_status_codes=model.refresh_token_updater.refresh_token_error_status_codes,
                refresh_token_error_key=model.refresh_token_updater.refresh_token_error_key,
                refresh_token_error_values=model.refresh_token_updater.refresh_token_error_values,
            )
        # ignore type error because fixing it would have a lot of dependencies, revisit later
        return DeclarativeOauth2Authenticator(  # type: ignore
            access_token_name=model.access_token_name or "access_token",
            client_id=model.client_id,
            client_secret=model.client_secret,
            expires_in_name=model.expires_in_name or "expires_in",
            grant_type=model.grant_type or "refresh_token",
            refresh_request_body=model.refresh_request_body,
            refresh_token=model.refresh_token,
            scopes=model.scopes,
            token_expiry_date=model.token_expiry_date,
            token_expiry_date_format=model.token_expiry_date_format,  # type: ignore
            token_expiry_is_time_of_expiration=bool(model.token_expiry_date_format),
            token_refresh_endpoint=model.token_refresh_endpoint,
            config=config,
            parameters=model.parameters or {},
            message_repository=self._message_repository,
        )

    @staticmethod
    def create_offset_increment(model: OffsetIncrementModel, config: Config, decoder: Decoder, **kwargs: Any) -> OffsetIncrement:
        if isinstance(decoder, PaginationDecoderDecorator):
            if not isinstance(decoder.decoder, (JsonDecoder, XmlDecoder)):
                raise ValueError(
                    f"Provided decoder of {type(decoder.decoder)=} is not supported. Please set JsonDecoder or XmlDecoder instead."
                )
            decoder_to_use = decoder
        else:
            if not isinstance(decoder, (JsonDecoder, XmlDecoder)):
                raise ValueError(f"Provided decoder of {type(decoder)=} is not supported. Please set JsonDecoder or XmlDecoder instead.")
            decoder_to_use = PaginationDecoderDecorator(decoder=decoder)
        return OffsetIncrement(
            page_size=model.page_size,
            config=config,
            decoder=decoder_to_use,
            inject_on_first_request=model.inject_on_first_request or False,
            parameters=model.parameters or {},
        )

    @staticmethod
    def create_page_increment(model: PageIncrementModel, config: Config, **kwargs: Any) -> PageIncrement:
        return PageIncrement(
            page_size=model.page_size,
            config=config,
            start_from_page=model.start_from_page or 0,
            inject_on_first_request=model.inject_on_first_request or False,
            parameters=model.parameters or {},
        )

    def create_parent_stream_config(self, model: ParentStreamConfigModel, config: Config, **kwargs: Any) -> ParentStreamConfig:
        declarative_stream = self._create_component_from_model(model.stream, config=config)
        request_option = self._create_component_from_model(model.request_option, config=config) if model.request_option else None
        return ParentStreamConfig(
            parent_key=model.parent_key,
            request_option=request_option,
            stream=declarative_stream,
            partition_field=model.partition_field,
            config=config,
            incremental_dependency=model.incremental_dependency or False,
            parameters=model.parameters or {},
            extra_fields=model.extra_fields,
        )

    @staticmethod
    def create_record_filter(model: RecordFilterModel, config: Config, **kwargs: Any) -> RecordFilter:
        return RecordFilter(condition=model.condition or "", config=config, parameters=model.parameters or {})

    @staticmethod
    def create_request_path(model: RequestPathModel, config: Config, **kwargs: Any) -> RequestPath:
        return RequestPath(parameters={})

    @staticmethod
    def create_request_option(model: RequestOptionModel, config: Config, **kwargs: Any) -> RequestOption:
        inject_into = RequestOptionType(model.inject_into.value)
        return RequestOption(field_name=model.field_name, inject_into=inject_into, parameters={})

    def create_record_selector(
        self,
        model: RecordSelectorModel,
        config: Config,
        *,
        transformations: List[RecordTransformation],
        decoder: Optional[Decoder] = None,
        client_side_incremental_sync: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> RecordSelector:
        assert model.schema_normalization is not None  # for mypy
        extractor = self._create_component_from_model(model=model.extractor, decoder=decoder, config=config)
        record_filter = self._create_component_from_model(model.record_filter, config=config) if model.record_filter else None
        if client_side_incremental_sync:
            record_filter = ClientSideIncrementalRecordFilterDecorator(
                config=config,
                parameters=model.parameters,
                condition=model.record_filter.condition if (model.record_filter and hasattr(model.record_filter, "condition")) else None,
                **client_side_incremental_sync,
            )
        schema_normalization = TypeTransformer(SCHEMA_TRANSFORMER_TYPE_MAPPING[model.schema_normalization])

        return RecordSelector(
            extractor=extractor,
            config=config,
            record_filter=record_filter,
            transformations=transformations,
            schema_normalization=schema_normalization,
            parameters=model.parameters or {},
        )

    @staticmethod
    def create_remove_fields(model: RemoveFieldsModel, config: Config, **kwargs: Any) -> RemoveFields:
        return RemoveFields(field_pointers=model.field_pointers, condition=model.condition or "", parameters={})

    def create_selective_authenticator(self, model: SelectiveAuthenticatorModel, config: Config, **kwargs: Any) -> DeclarativeAuthenticator:
        authenticators = {name: self._create_component_from_model(model=auth, config=config) for name, auth in model.authenticators.items()}
        # SelectiveAuthenticator will return instance of DeclarativeAuthenticator or raise ValueError error
        return SelectiveAuthenticator(  # type: ignore[abstract]
            config=config,
            authenticators=authenticators,
            authenticator_selection_path=model.authenticator_selection_path,
            **kwargs,
        )

    @staticmethod
    def create_legacy_session_token_authenticator(
        model: LegacySessionTokenAuthenticatorModel, config: Config, *, url_base: str, **kwargs: Any
    ) -> LegacySessionTokenAuthenticator:
        return LegacySessionTokenAuthenticator(
            api_url=url_base,
            header=model.header,
            login_url=model.login_url,
            password=model.password or "",
            session_token=model.session_token or "",
            session_token_response_key=model.session_token_response_key or "",
            username=model.username or "",
            validate_session_url=model.validate_session_url,
            config=config,
            parameters=model.parameters or {},
        )

    def create_simple_retriever(
        self,
        model: SimpleRetrieverModel,
        config: Config,
        *,
        name: str,
        primary_key: Optional[Union[str, List[str], List[List[str]]]],
        stream_slicer: Optional[StreamSlicer],
        request_options_provider: Optional[RequestOptionsProvider] = None,
        stop_condition_on_cursor: bool = False,
        client_side_incremental_sync: Optional[Dict[str, Any]] = None,
        transformations: List[RecordTransformation],
    ) -> SimpleRetriever:
        decoder = self._create_component_from_model(model=model.decoder, config=config) if model.decoder else JsonDecoder(parameters={})
        requester = self._create_component_from_model(model=model.requester, decoder=decoder, config=config, name=name)
        record_selector = self._create_component_from_model(
            model=model.record_selector,
            config=config,
            decoder=decoder,
            transformations=transformations,
            client_side_incremental_sync=client_side_incremental_sync,
        )
        url_base = model.requester.url_base if hasattr(model.requester, "url_base") else requester.get_url_base()

        # Define cursor only if per partition or common incremental support is needed
        cursor = stream_slicer if isinstance(stream_slicer, DeclarativeCursor) else None

        if not isinstance(stream_slicer, DatetimeBasedCursor) or type(stream_slicer) is not DatetimeBasedCursor:
            # Many of the custom component implementations of DatetimeBasedCursor override get_request_params() (or other methods).
            # Because we're decoupling RequestOptionsProvider from the Cursor, custom components will eventually need to reimplement
            # their own RequestOptionsProvider. However, right now the existing StreamSlicer/Cursor still can act as the SimpleRetriever's
            # request_options_provider
            request_options_provider = stream_slicer or DefaultRequestOptionsProvider(parameters={})
        elif not request_options_provider:
            request_options_provider = DefaultRequestOptionsProvider(parameters={})

        stream_slicer = stream_slicer or SinglePartitionRouter(parameters={})

        cursor_used_for_stop_condition = cursor if stop_condition_on_cursor else None
        paginator = (
            self._create_component_from_model(
                model=model.paginator,
                config=config,
                url_base=url_base,
                decoder=decoder,
                cursor_used_for_stop_condition=cursor_used_for_stop_condition,
            )
            if model.paginator
            else NoPagination(parameters={})
        )

        ignore_stream_slicer_parameters_on_paginated_requests = model.ignore_stream_slicer_parameters_on_paginated_requests or False

        if self._limit_slices_fetched or self._emit_connector_builder_messages:
            return SimpleRetrieverTestReadDecorator(
                name=name,
                paginator=paginator,
                primary_key=primary_key,
                requester=requester,
                record_selector=record_selector,
                stream_slicer=stream_slicer,
                request_option_provider=request_options_provider,
                cursor=cursor,
                config=config,
                maximum_number_of_slices=self._limit_slices_fetched or 5,
                ignore_stream_slicer_parameters_on_paginated_requests=ignore_stream_slicer_parameters_on_paginated_requests,
                parameters=model.parameters or {},
            )
        return SimpleRetriever(
            name=name,
            paginator=paginator,
            primary_key=primary_key,
            requester=requester,
            record_selector=record_selector,
            stream_slicer=stream_slicer,
            request_option_provider=request_options_provider,
            cursor=cursor,
            config=config,
            ignore_stream_slicer_parameters_on_paginated_requests=ignore_stream_slicer_parameters_on_paginated_requests,
            parameters=model.parameters or {},
        )

    def _create_async_job_status_mapping(
        self, model: AsyncJobStatusMapModel, config: Config, **kwargs: Any
    ) -> Mapping[str, AsyncJobStatus]:
        api_status_to_cdk_status = {}
        for cdk_status, api_statuses in model.dict().items():
            if cdk_status == "type":
                # This is an element of the dict because of the typing of the CDK but it is not a CDK status
                continue

            for status in api_statuses:
                if status in api_status_to_cdk_status:
                    raise ValueError(
                        f"API status {status} is already set for CDK status {cdk_status}. Please ensure API statuses are only provided once"
                    )
                api_status_to_cdk_status[status] = self._get_async_job_status(cdk_status)
        return api_status_to_cdk_status

    def _get_async_job_status(self, status: str) -> AsyncJobStatus:
        match status:
            case "running":
                return AsyncJobStatus.RUNNING
            case "completed":
                return AsyncJobStatus.COMPLETED
            case "failed":
                return AsyncJobStatus.FAILED
            case "timeout":
                return AsyncJobStatus.TIMED_OUT
            case _:
                raise ValueError(f"Unsupported CDK status {status}")

    def create_async_retriever(
        self,
        model: AsyncRetrieverModel,
        config: Config,
        *,
        name: str,
        primary_key: Optional[Union[str, List[str], List[List[str]]]],  # this seems to be needed to match create_simple_retriever
        stream_slicer: Optional[StreamSlicer],
        client_side_incremental_sync: Optional[Dict[str, Any]] = None,
        transformations: List[RecordTransformation],
        **kwargs: Any,
    ) -> AsyncRetriever:

        decoder = self._create_component_from_model(model=model.decoder, config=config) if model.decoder else JsonDecoder(parameters={})
        record_selector = self._create_component_from_model(
            model=model.record_selector,
            config=config,
            decoder=decoder,
            transformations=transformations,
            client_side_incremental_sync=client_side_incremental_sync,
        )
        stream_slicer = stream_slicer or SinglePartitionRouter(parameters={})
        creation_requester = self._create_component_from_model(
            model=model.creation_requester, decoder=decoder, config=config, name=f"job creation - {name}"
        )
        polling_requester = self._create_component_from_model(
            model=model.polling_requester, decoder=decoder, config=config, name=f"job polling - {name}"
        )
        job_download_components_name = f"job download - {name}"
        download_requester = self._create_component_from_model(
            model=model.download_requester, decoder=decoder, config=config, name=job_download_components_name
        )
        download_retriever = SimpleRetriever(
            requester=download_requester,
            record_selector=RecordSelector(
                extractor=ResponseToFileExtractor(),
                record_filter=None,
                transformations=[],
                schema_normalization=TypeTransformer(TransformConfig.NoTransform),
                config=config,
                parameters={},
            ),
            primary_key=None,
            name=job_download_components_name,
            paginator=(
                self._create_component_from_model(model=model.download_paginator, decoder=decoder, config=config, url_base="")
                if model.download_paginator
                else NoPagination(parameters={})
            ),
            config=config,
            parameters={},
        )
        abort_requester = (
            self._create_component_from_model(model=model.abort_requester, decoder=decoder, config=config, name=f"job abort - {name}")
            if model.abort_requester
            else None
        )
        delete_requester = (
            self._create_component_from_model(model=model.delete_requester, decoder=decoder, config=config, name=f"job delete - {name}")
            if model.delete_requester
            else None
        )
        status_extractor = self._create_component_from_model(model=model.status_extractor, decoder=decoder, config=config, name=name)
        urls_extractor = self._create_component_from_model(model=model.urls_extractor, decoder=decoder, config=config, name=name)
        job_repository: AsyncJobRepository = AsyncHttpJobRepository(
            creation_requester=creation_requester,
            polling_requester=polling_requester,
            download_retriever=download_retriever,
            abort_requester=abort_requester,
            delete_requester=delete_requester,
            status_extractor=status_extractor,
            status_mapping=self._create_async_job_status_mapping(model.status_mapping, config),
            urls_extractor=urls_extractor,
        )

        return AsyncRetriever(
            job_orchestrator_factory=lambda stream_slices: AsyncJobOrchestrator(
                job_repository,
                stream_slices,
                JobTracker(1),  # FIXME eventually make the number of concurrent jobs in the API configurable. Until then, we limit to 1
                self._message_repository,
                has_bulk_parent=False,  # FIXME work would need to be done here in order to detect if a stream as a parent stream that is bulk
            ),
            record_selector=record_selector,
            stream_slicer=stream_slicer,
            config=config,
            parameters=model.parameters or {},
        )

    @staticmethod
    def create_spec(model: SpecModel, config: Config, **kwargs: Any) -> Spec:
        return Spec(
            connection_specification=model.connection_specification,
            documentation_url=model.documentation_url,
            advanced_auth=model.advanced_auth,
            parameters={},
        )

    def create_substream_partition_router(
        self, model: SubstreamPartitionRouterModel, config: Config, **kwargs: Any
    ) -> SubstreamPartitionRouter:
        parent_stream_configs = []
        if model.parent_stream_configs:
            parent_stream_configs.extend(
                [
                    self._create_message_repository_substream_wrapper(model=parent_stream_config, config=config)
                    for parent_stream_config in model.parent_stream_configs
                ]
            )

        return SubstreamPartitionRouter(parent_stream_configs=parent_stream_configs, parameters=model.parameters or {}, config=config)

    def _create_message_repository_substream_wrapper(self, model: ParentStreamConfigModel, config: Config) -> Any:
        substream_factory = ModelToComponentFactory(
            limit_pages_fetched_per_slice=self._limit_pages_fetched_per_slice,
            limit_slices_fetched=self._limit_slices_fetched,
            emit_connector_builder_messages=self._emit_connector_builder_messages,
            disable_retries=self._disable_retries,
            disable_cache=self._disable_cache,
            message_repository=LogAppenderMessageRepositoryDecorator(
                {"airbyte_cdk": {"stream": {"is_substream": True}}, "http": {"is_auxiliary": True}},
                self._message_repository,
                self._evaluate_log_level(self._emit_connector_builder_messages),
            ),
        )
        return substream_factory._create_component_from_model(model=model, config=config)

    @staticmethod
    def create_wait_time_from_header(model: WaitTimeFromHeaderModel, config: Config, **kwargs: Any) -> WaitTimeFromHeaderBackoffStrategy:
        return WaitTimeFromHeaderBackoffStrategy(
            header=model.header,
            parameters=model.parameters or {},
            config=config,
            regex=model.regex,
            max_waiting_time_in_seconds=model.max_waiting_time_in_seconds if model.max_waiting_time_in_seconds is not None else None,
        )

    @staticmethod
    def create_wait_until_time_from_header(
        model: WaitUntilTimeFromHeaderModel, config: Config, **kwargs: Any
    ) -> WaitUntilTimeFromHeaderBackoffStrategy:
        return WaitUntilTimeFromHeaderBackoffStrategy(
            header=model.header, parameters=model.parameters or {}, config=config, min_wait=model.min_wait, regex=model.regex
        )

    def get_message_repository(self) -> MessageRepository:
        return self._message_repository

    def _evaluate_log_level(self, emit_connector_builder_messages: bool) -> Level:
        return Level.DEBUG if emit_connector_builder_messages else Level.INFO
