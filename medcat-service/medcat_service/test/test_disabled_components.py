"""Regression tests for component selection without loading model packs."""

import logging
import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from medcat.cat import CAT
from medcat.components.addons.addons import AddonComponent
from medcat.components.types import CoreComponent, CoreComponentType
from medcat.config import Config
from medcat.pipeline import Pipeline

from medcat_service.config import Settings, parse_disabled_components
from medcat_service.dependencies import get_medcat_processor
from medcat_service.nlp_processor import MedCatProcessor
from medcat_service.routers.process import router
from medcat_service.types import ModelCardInfo


class TestDisabledComponentsSettings(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(os.environ, {}, clear=True))

    def test_default_runs_all_components(self):
        self.assertEqual(Settings().disabled_components, ())

    def test_environment_variable_parses_comma_separated_names(self):
        with patch.dict(os.environ, {"APP_DISABLED_COMPONENTS": " rel_cat, , meta_cat.Status, "}):
            self.assertEqual(Settings().disabled_components, ("rel_cat", "meta_cat.Status"))

    def test_parse_empty_and_iterable_values(self):
        for value, expected in (
            (None, ()),
            ("", ()),
            (" , , ", ()),
            ([], ()),
            (["rel_cat", "meta_cat"], ("rel_cat", "meta_cat")),
            (("rel_cat",), ("rel_cat",)),
        ):
            with self.subTest(value=value):
                self.assertEqual(parse_disabled_components(value), expected)


class TestDisabledComponentsRequests(unittest.TestCase):
    """Exercise the real router, processor and CAT pipeline with component spies."""

    TEXT = "Patient was prescribed aspirin."
    ALL_COMPONENTS = ["ner:dictionary", "meta_cat.Status", "meta_cat.Subject", "rel_cat.relations"]
    RELATIONS = [{"label": "test_relation"}]

    def setUp(self):
        self.enterContext(patch.dict(os.environ, {}, clear=True))
        self.executed = []

        # Keep MedCAT's normal execution path, replacing only model inference
        # and document serialization with lightweight fixtures.
        self.ner = self._component("dictionary", "ner:dictionary", core=True)
        self.ner.get_type.return_value = CoreComponentType.ner
        self.status = self._component("Status", "meta_cat.Status", addon_type="meta_cat")
        self.subject = self._component("Subject", "meta_cat.Subject", addon_type="meta_cat")
        self.rel_cat = self._component("relations", "rel_cat.relations", addon_type="rel_cat")

        self.pipeline = Pipeline.__new__(Pipeline)
        self.pipeline._tokenizer = Mock(side_effect=lambda text: SimpleNamespace(linked_ents=[], relations=[]))
        self.pipeline._components = [self.ner]
        self.pipeline._addons = [self.status, self.subject, self.rel_cat]
        self.original_components = self.pipeline._components
        self.original_addons = self.pipeline._addons

        self.cat = CAT.__new__(CAT)
        self.cat.config = Config()
        self.cat._pipeline = self.pipeline
        self.cat.usage_monitor = Mock(should_monitor=False)
        self.cat._doc_to_out = Mock(side_effect=lambda doc, only_cui: {"entities": {}, "relations": doc.relations})

        self.processor = MedCatProcessor.__new__(MedCatProcessor)
        self.processor.cat = self.cat
        self.processor.service_settings = Settings()
        self.processor.log = logging.getLogger(__name__)
        self.processor.app_version = "test"
        self.processor.model_card_info = ModelCardInfo(
            ontologies=None, meta_cat_model_names=[], rel_cat_model_names=[], model_last_modified_on=None
        )

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_medcat_processor] = lambda: self.processor
        self.client = self.enterContext(TestClient(app, raise_server_exceptions=False))

    def _component(self, name, full_name, *, core=False, addon_type=None):
        component = Mock(spec=CoreComponent if core else AddonComponent)
        component.name = name
        component.full_name = full_name
        component.is_core.return_value = core
        component.addon_type = addon_type

        def run(doc):
            self.executed.append(full_name)
            if addon_type == "rel_cat":
                doc.relations.extend(self.RELATIONS)
            return doc

        component.side_effect = run
        return component

    def _request(self, disabled_components=None):
        self.executed.clear()
        params = {} if disabled_components is None else {"disabled_components": disabled_components}
        return self.client.post("/api/process", params=params, json={"content": {"text": self.TEXT}})

    def _assert_success(self, response, expected_components):
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()["result"]
        self.assertTrue(result["success"])
        self.assertEqual(self.executed, expected_components)
        self.assertEqual(result["relations"], self.RELATIONS if "rel_cat.relations" in expected_components else [])

    def _assert_pipeline_unchanged(self):
        self.assertIs(self.processor.cat, self.cat)
        self.assertIs(self.cat.pipe, self.pipeline)
        self.assertIs(self.pipeline._components, self.original_components)
        self.assertIs(self.pipeline._addons, self.original_addons)
        self.assertEqual(self.pipeline._components, [self.ner])
        self.assertEqual(self.pipeline._addons, [self.status, self.subject, self.rel_cat])

    def _set_environment_default(self, value):
        with patch.dict(os.environ, {"APP_DISABLED_COMPONENTS": value}):
            self.processor.service_settings = Settings()

    def test_skipping_component_does_not_affect_next_request(self):
        self._assert_success(self._request("rel_cat"), self.ALL_COMPONENTS[:-1])
        self.rel_cat.assert_not_called()
        self._assert_pipeline_unchanged()

        self._assert_success(self._request(), self.ALL_COMPONENTS)
        self.rel_cat.assert_called_once()
        self._assert_pipeline_unchanged()

    def test_failed_request_does_not_affect_next_request(self):
        normal_inference = self.ner.side_effect
        self.ner.side_effect = RuntimeError("inference failed")
        with self.assertLogs("API", "ERROR"):
            response = self._request("rel_cat")
        self.assertEqual(response.status_code, 500)
        self.rel_cat.assert_not_called()
        self._assert_pipeline_unchanged()

        self.ner.side_effect = normal_inference
        self._assert_success(self._request(), self.ALL_COMPONENTS)
        self.rel_cat.assert_called_once()
        self._assert_pipeline_unchanged()

    def test_omitted_parameter_uses_environment_default(self):
        self._set_environment_default("rel_cat")

        self._assert_success(self._request(), self.ALL_COMPONENTS[:-1])
        self.rel_cat.assert_not_called()
        self._assert_pipeline_unchanged()

    def test_empty_parameter_overrides_environment_default_for_one_request(self):
        self._set_environment_default("rel_cat")

        self._assert_success(self._request(""), self.ALL_COMPONENTS)
        self._assert_success(self._request(), self.ALL_COMPONENTS[:-1])
        self.assertEqual(self.processor.service_settings.disabled_components, ("rel_cat",))
        self.rel_cat.assert_called_once()
        self._assert_pipeline_unchanged()

    def test_explicit_selection_replaces_environment_default_for_one_request(self):
        self._set_environment_default("rel_cat")

        self._assert_success(self._request("meta_cat"), ["ner:dictionary", "rel_cat.relations"])
        self._assert_success(self._request(), self.ALL_COMPONENTS[:-1])
        self.assertEqual(self.processor.service_settings.disabled_components, ("rel_cat",))
        self._assert_pipeline_unchanged()

    def test_component_names_types_and_full_names_are_case_insensitive(self):
        for name, skipped in (
            ("ner", ["ner:dictionary"]),
            ("DICTIONARY", ["ner:dictionary"]),
            ("ner:dictionary", ["ner:dictionary"]),
            ("rel_cat", ["rel_cat.relations"]),
            ("relations", ["rel_cat.relations"]),
            (" REL_CAT.RELATIONS ", ["rel_cat.relations"]),
            ("meta_cat", ["meta_cat.Status", "meta_cat.Subject"]),
            ("status", ["meta_cat.Status"]),
            ("META_CAT.STATUS", ["meta_cat.Status"]),
        ):
            with self.subTest(name=name):
                expected = [component for component in self.ALL_COMPONENTS if component not in skipped]
                self._assert_success(self._request(name), expected)
                self._assert_pipeline_unchanged()

    def test_multiple_names_ignore_whitespace_and_empty_entries(self):
        self._assert_success(self._request(" rel_cat, , META_CAT.STATUS, "), ["ner:dictionary", "meta_cat.Subject"])
        self.status.assert_not_called()
        self.rel_cat.assert_not_called()

    def test_unknown_name_warns_without_disabling_other_components(self):
        with self.assertLogs(self.processor.log, "WARNING") as logs:
            response = self._request("does_not_exist,rel_cat")

        self._assert_success(response, self.ALL_COMPONENTS[:-1])
        self.assertEqual(len(logs.records), 1)
        self.assertIn("does_not_exist", logs.records[0].getMessage())
        self.assertNotIn("rel_cat", logs.records[0].getMessage())
        self._assert_pipeline_unchanged()

    def test_filtered_pipeline_logs_usage_once_when_enabled(self):
        self.cat.usage_monitor.should_monitor = True

        self._assert_success(self._request("rel_cat"), self.ALL_COMPONENTS[:-1])
        self.cat.usage_monitor.log_inference.assert_called_once_with(len(self.TEXT), 0)

    def test_filtered_pipeline_does_not_log_usage_when_disabled(self):
        self._assert_success(self._request("rel_cat"), self.ALL_COMPONENTS[:-1])
        self.cat.usage_monitor.log_inference.assert_not_called()


if __name__ == "__main__":
    unittest.main()
