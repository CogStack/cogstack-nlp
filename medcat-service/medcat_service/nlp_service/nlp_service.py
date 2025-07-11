#!/usr/bin/env python
import injector

from medcat_service.nlp_processor import MedCatProcessor


class NlpService:
    """"
    NLP Service class is an abstract wrapper class around the actual NLP processor.
    NLP processor will be provided via dependency injection.
    It should help with tests.
    """
    def __init__(self):
        self.nlp = None

    def get_processor(self) -> MedCatProcessor:
        """
        Returns the wrapped NLP processor
        :return:
        """
        if self.nlp is None:
            raise RuntimeError("NLP processor not set")
        return self.nlp


class MedCatService(NlpService):
    """"
    MedCAT Service -- wrapper around MedCAT NLP processor
    """
    @injector.inject
    def __init__(self, nlp_processor: MedCatProcessor):
        super().__init__()
        self.nlp = nlp_processor
